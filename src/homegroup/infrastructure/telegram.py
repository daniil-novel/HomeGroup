from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import cast

import structlog
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from telethon import TelegramClient
from telethon.errors import RPCError, UserAlreadyParticipantError
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    EditAdminRequest,
    InviteToChannelRequest,
    ToggleForumRequest,
)
from telethon.tl.functions.messages import (
    CreateForumTopicRequest,
    EditForumTopicRequest,
    GetForumTopicsRequest,
)
from telethon.tl.types import Channel, ChatAdminRights
from telethon.tl.types import User as TelegramUser

from homegroup.application.bootstrap import BUILTIN_TEMPLATES, TOPIC_DEFINITIONS
from homegroup.application.ports import ProvisioningGateway, TelegramGateway
from homegroup.application.services import HomeGroupService
from homegroup.domain.enums import EntityType, TopicSlug, UserRole
from homegroup.infrastructure.config import Settings
from homegroup.infrastructure.db.models import Chat, MessageLink, Topic, User
from homegroup.infrastructure.db.session import create_session_factory

logger = structlog.get_logger(__name__)


def render_entity_card(title: str, lines: list[str], mini_app_url: str | None = None) -> str:
    body = "\n".join(f"• {line}" for line in lines if line)
    footer = f"\n\nMini App: {mini_app_url}" if mini_app_url else ""
    return f"{title}\n\n{body}{footer}"


def is_public_base_url(base_url: str) -> bool:
    lowered = base_url.lower()
    return not any(marker in lowered for marker in ("localhost", "127.0.0.1"))


def build_topic_seed_message(
    slug: str,
    title: str,
    *,
    base_url: str,
    bot_username: str | None = None,
) -> str:
    screen_map = {
        TopicSlug.TODAY.value: "today",
        TopicSlug.WEEK.value: "week",
        TopicSlug.CALENDAR.value: "calendar",
        TopicSlug.PURCHASES.value: "purchases",
        TopicSlug.CHORES.value: "chores",
        TopicSlug.DECISIONS.value: "decisions",
        TopicSlug.NOTES.value: "notes",
        TopicSlug.TEMPLATES.value: "templates",
        TopicSlug.ARCHIVE.value: "archive",
        TopicSlug.SYSTEM.value: "settings",
    }
    intro_map = {
        TopicSlug.TODAY.value: "Здесь держим план дня, занятость и договорённости на вечер.",
        TopicSlug.WEEK.value: "Здесь фиксируем недельные цели, офисные дни, совместные планы и выходные.",
        TopicSlug.CALENDAR.value: "Сюда складываем события, встречи, тренировки и поездки.",
        TopicSlug.PURCHASES.value: "Здесь ведём покупки, бюджеты, подтверждения и статусы.",
        TopicSlug.CHORES.value: "Сюда попадают бытовые задачи, расписание и ответственность по дому.",
        TopicSlug.DECISIONS.value: "Здесь оформляем вопросы, варианты, driver/approver и итоговые решения.",
        TopicSlug.NOTES.value: "Это inbox для быстрых заметок и идей до разборки по сущностям.",
        TopicSlug.TEMPLATES.value: "Здесь лежат шаблоны утренних, вечерних и недельных ритуалов.",
        TopicSlug.ARCHIVE.value: "Сюда уходит завершённое и архивные записи для поиска и истории.",
        TopicSlug.SYSTEM.value: "Служебная тема для диагностики, backup и технических сообщений.",
    }

    lines = [title, "", intro_map.get(slug, "Рабочая тема HomeGroup.")]
    template = BUILTIN_TEMPLATES.get(slug)
    if template is not None:
        lines.extend(["", "Шаблон для старта:", template[1]])
    if slug == TopicSlug.SYSTEM.value:
        commands = (
            "/today /week /calendar /buy /chore /decision /note /status /settings "
            "/archive /sync /rebuild /export /diagnostics"
        )
        lines.extend(["", "Команды бота:", commands])
    if bot_username:
        lines.extend(["", f"Бот: @{bot_username}"])
    screen = screen_map.get(slug)
    if screen and is_public_base_url(base_url):
        lines.extend(["", f"Mini App: {base_url.rstrip('/')}/mini-app/{screen}"])
    else:
        lines.extend(["", "Mini App будет активирован после безопасной публикации backend."])
    return "\n".join(lines)


@dataclass(slots=True)
class ProvisionedAccount:
    telegram_user_id: int
    username: str | None
    display_name: str
    role: UserRole


@dataclass(slots=True)
class DisabledTelegramGateway(TelegramGateway):
    def publish_summary(self, topic_slug: str, text: str) -> None:
        logger.info("telegram.summary.skipped", topic_slug=topic_slug, text=text)

    def publish_system_message(self, text: str) -> None:
        logger.info("telegram.system.skipped", text=text)

    def upsert_entity_card(self, entity_type: str, entity_id: str, body: str, topic_slug: str) -> None:
        logger.info(
            "telegram.card.skipped",
            entity_type=entity_type,
            entity_id=entity_id,
            topic_slug=topic_slug,
        )


class AiogramTelegramGateway(TelegramGateway):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bot = Bot(token=settings.bot_token) if settings.bot_token else None

    def publish_summary(self, topic_slug: str, text: str) -> None:
        self._send_text(f"[{topic_slug}] {text}")

    def publish_system_message(self, text: str) -> None:
        self._send_text(f"[system] {text}")

    def upsert_entity_card(self, entity_type: str, entity_id: str, body: str, topic_slug: str) -> None:
        self._send_text(f"[{topic_slug}:{entity_type}:{entity_id}]\n{body}")

    def _send_text(self, text: str) -> None:
        if self.bot is None:
            logger.info("telegram.disabled", text=text)
            return
        logger.info("telegram.send", text=text)


class TelethonProvisioningService(ProvisioningGateway):
    def __init__(self, settings: Settings, service: HomeGroupService) -> None:
        self.settings = settings
        self.service = service
        self.session_factory = create_session_factory(settings)

    def provision(self) -> str:
        if not all(
            [
                self.settings.telegram_api_id,
                self.settings.telegram_api_hash,
                self.settings.telegram_owner_phone,
            ]
        ):
            raise RuntimeError("Telegram provisioning credentials are not configured.")

        async def runner() -> str:
            async with TelegramClient(
                self.settings.telegram_session_name,
                self.settings.telegram_api_id,
                self.settings.telegram_api_hash,
            ) as client:
                chat = await self._ensure_chat(client)
                if not bool(getattr(chat, "forum", False)):
                    await client(ToggleForumRequest(channel=chat, enabled=True, tabs=False))
                owner = await client.get_me()
                if owner is None:
                    raise RuntimeError("Unable to resolve Telegram owner profile.")
                accounts = [self._account_from_telegram_user(owner, UserRole.OWNER_A)]
                if self.settings.telegram_second_user_username:
                    second_user = await self._invite_participant(
                        client,
                        chat,
                        self.settings.telegram_second_user_username,
                    )
                    if second_user is not None:
                        accounts.append(self._account_from_telegram_user(second_user, UserRole.OWNER_B))
                bot_username, bot_id = await self._resolve_bot_identity()
                bot_user = await self._invite_participant(client, chat, bot_username)
                if bot_user is not None:
                    bot_account = self._account_from_telegram_user(bot_user, UserRole.BOT)
                    accounts.append(
                        ProvisionedAccount(
                            telegram_user_id=bot_id,
                            username=bot_username,
                            display_name=bot_account.display_name,
                            role=UserRole.BOT,
                        )
                    )
                    await self._grant_bot_admin(client, chat, bot_user)
                topics = await self._ensure_topics(client, chat)
                await self._hide_general_topic(client, chat)
                self._sync_database(chat, accounts, topics)
                await self._ensure_topic_seed_messages(client, chat, topics, bot_username)
                return f"Provisioned chat {chat.id} with {len(topics)} topics"

        return asyncio.run(runner())

    async def _ensure_chat(self, client: TelegramClient) -> Channel:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if (
                isinstance(entity, Channel)
                and entity.title == "Дом"
                and bool(getattr(entity, "megagroup", False))
            ):
                return entity
        result = await client(
            CreateChannelRequest(
                title="Дом",
                about="Наше расписание, покупки, быт, решения и общая рутина",
                megagroup=True,
                forum=True,
            )
        )
        return cast(Channel, result.chats[0])

    async def _invite_participant(
        self,
        client: TelegramClient,
        chat: Channel,
        username: str,
    ) -> TelegramUser | None:
        entity = cast(TelegramUser, await client.get_entity(username))
        try:
            await client(
                InviteToChannelRequest(
                    channel=chat,
                    users=[entity],
                )
            )
        except UserAlreadyParticipantError:
            logger.info("telegram.participant.already_member", username=username)
        except RPCError as exc:
            logger.warning("telegram.participant.invite_failed", username=username, error=str(exc))
            return None
        return entity

    async def _resolve_bot_identity(self) -> tuple[str, int]:
        if not self.settings.bot_token:
            raise RuntimeError("Bot token is required to add the bot to the HomeGroup chat.")
        bot = Bot(token=self.settings.bot_token)
        try:
            bot_info = await bot.get_me()
            if bot_info.username is None:
                raise RuntimeError("Bot username is missing.")
            return bot_info.username, bot_info.id
        finally:
            await bot.session.close()

    async def _grant_bot_admin(self, client: TelegramClient, chat: Channel, bot_user: object) -> None:
        await client(
            EditAdminRequest(
                channel=chat,
                user_id=bot_user,
                admin_rights=ChatAdminRights(
                    change_info=True,
                    delete_messages=True,
                    invite_users=True,
                    pin_messages=True,
                    manage_call=True,
                    other=True,
                    manage_topics=True,
                ),
                rank="HomeGroup",
            )
        )

    async def _ensure_topics(self, client: TelegramClient, chat: Channel) -> dict[str, int]:
        topics = await self._fetch_topics(client, chat)
        for topic in TOPIC_DEFINITIONS:
            title = str(topic["title"])
            if title in topics:
                continue
            await client(
                CreateForumTopicRequest(
                    peer=chat,
                    title=title,
                )
            )
        return await self._fetch_topics(client, chat)

    async def _fetch_topics(self, client: TelegramClient, chat: Channel) -> dict[str, int]:
        result = await client(
            GetForumTopicsRequest(
                peer=chat,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )
        topics: dict[str, int] = {}
        for topic in result.topics:
            title = getattr(topic, "title", None)
            thread_id = getattr(topic, "top_message", None)
            if isinstance(title, str) and isinstance(thread_id, int):
                topics[title] = thread_id
        return topics

    async def _hide_general_topic(self, client: TelegramClient, chat: Channel) -> None:
        result = await client(
            GetForumTopicsRequest(
                peer=chat,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )
        for topic in result.topics:
            topic_id = getattr(topic, "id", None)
            title = getattr(topic, "title", None)
            hidden = bool(getattr(topic, "hidden", False))
            if topic_id == 1 or title == "General":
                if not hidden and isinstance(topic_id, int):
                    await client(EditForumTopicRequest(peer=chat, topic_id=topic_id, hidden=True))
                return

    def _sync_database(
        self,
        chat: Channel,
        accounts: list[ProvisionedAccount],
        topics: dict[str, int],
    ) -> None:
        with self.session_factory() as session:
            self.service.ensure_defaults(session)
            db_chat = session.scalar(select(Chat).where(Chat.telegram_chat_id == chat.id))
            if db_chat is None:
                db_chat = Chat(
                    telegram_chat_id=chat.id,
                    chat_type="supergroup",
                    is_forum=True,
                    title=chat.title or "Дом",
                    description="Наше расписание, покупки, быт, решения и общая рутина",
                )
                session.add(db_chat)
                session.flush()
            else:
                db_chat.chat_type = "supergroup"
                db_chat.is_forum = True
                db_chat.title = chat.title or db_chat.title
                db_chat.description = "Наше расписание, покупки, быт, решения и общая рутина"

            for account in accounts:
                user = session.scalar(select(User).where(User.telegram_user_id == account.telegram_user_id))
                if user is None:
                    user = User(
                        telegram_user_id=account.telegram_user_id,
                        username=account.username,
                        display_name=account.display_name,
                        role=account.role,
                    )
                    session.add(user)
                else:
                    user.username = account.username
                    user.display_name = account.display_name
                    user.role = account.role
                    user.is_active = True

            for topic_definition in TOPIC_DEFINITIONS:
                slug = str(topic_definition["slug"])
                title = str(topic_definition["title"])
                thread_id = topics.get(title)
                topic = session.scalar(
                    select(Topic).where(
                        Topic.chat_id == db_chat.id,
                        Topic.slug == slug,
                    )
                )
                if topic is None:
                    topic = Topic(
                        chat_id=db_chat.id,
                        slug=slug,
                        title=title,
                        telegram_message_thread_id=thread_id,
                        content_type=str(topic_definition["content_type"]),
                        is_system=bool(topic_definition["is_system"]),
                    )
                    session.add(topic)
                else:
                    topic.title = title
                    topic.telegram_message_thread_id = thread_id
                    topic.content_type = str(topic_definition["content_type"])
                    topic.is_system = bool(topic_definition["is_system"])
            session.commit()

    async def _ensure_topic_seed_messages(
        self,
        client: TelegramClient,
        chat: Channel,
        topics: dict[str, int],
        bot_username: str,
    ) -> None:
        for topic_definition in TOPIC_DEFINITIONS:
            slug = str(topic_definition["slug"])
            title = str(topic_definition["title"])
            thread_id = topics.get(title)
            if thread_id is None:
                continue
            body = build_topic_seed_message(
                slug,
                title,
                base_url=self.settings.base_url,
                bot_username=bot_username,
            )
            await self._upsert_topic_seed_message(client, chat, thread_id, slug, body)

    async def _upsert_topic_seed_message(
        self,
        client: TelegramClient,
        chat: Channel,
        thread_id: int,
        slug: str,
        body: str,
    ) -> None:
        entity_id = f"topic-{slug}"
        with self.session_factory() as session:
            message_link = session.scalar(
                select(MessageLink).where(
                    MessageLink.entity_type == EntityType.TEMPLATE,
                    MessageLink.entity_id == entity_id,
                )
            )

            if message_link is not None:
                try:
                    await client.edit_message(chat, message_link.telegram_message_id, body)
                    await client.pin_message(chat, message_link.telegram_message_id, notify=False)
                except RPCError:
                    session.delete(message_link)
                    session.commit()
                else:
                    return

            message = await client.send_message(chat, body, reply_to=thread_id, link_preview=False)
            session.add(
                MessageLink(
                    entity_type=EntityType.TEMPLATE,
                    entity_id=entity_id,
                    telegram_chat_id=chat.id,
                    telegram_message_id=message.id,
                    telegram_message_thread_id=thread_id,
                )
            )
            session.commit()
            await client.pin_message(chat, message.id, notify=False)

    @staticmethod
    def _account_from_telegram_user(entity: TelegramUser, role: UserRole) -> ProvisionedAccount:
        first_name = getattr(entity, "first_name", None)
        last_name = getattr(entity, "last_name", None)
        username = getattr(entity, "username", None)
        display_name = " ".join(part for part in [first_name, last_name] if part) or username or "Unknown"
        telegram_user_id = int(getattr(entity, "id"))
        return ProvisionedAccount(
            telegram_user_id=telegram_user_id,
            username=username,
            display_name=display_name,
            role=role,
        )


def build_dispatcher(settings: Settings, service: HomeGroupService) -> Dispatcher:
    router = Router()
    session_factory = create_session_factory(settings)

    def quick_actions() -> InlineKeyboardBuilder:
        builder = InlineKeyboardBuilder()
        builder.button(text="Открыть Mini App", url=f"{settings.base_url}/mini-app/dashboard")
        builder.adjust(1)
        return builder

    @router.message(Command("start"))
    @router.message(Command("help"))
    async def start_handler(message: Message) -> None:
        await message.answer(
            "HomeGroup готов. Доступны команды /today /week /buy /chore /decision /note /status /settings /archive /diagnostics",
            reply_markup=quick_actions().as_markup(),
        )

    @router.message(Command("today"))
    async def today_handler(message: Message) -> None:
        with session_factory() as session:
            dashboard = service.dashboard(session)
        text = service.ai_client.summarize(
            "Сегодня",
            [f"Событий: {len(dashboard.today_events)}", f"Бытовых задач: {len(dashboard.chores_today)}"],
        )
        await message.answer(text, reply_markup=quick_actions().as_markup())

    @router.message(Command("week"))
    async def week_handler(message: Message) -> None:
        with session_factory() as session:
            dashboard = service.dashboard(session)
        goals = ", ".join(dashboard.weekly_goals) if dashboard.weekly_goals else "цели не заполнены"
        await message.answer(f"Неделя\n\nГлавные цели: {goals}", reply_markup=quick_actions().as_markup())

    @router.message(Command("status"))
    async def status_handler(message: Message) -> None:
        with session_factory() as session:
            diagnostics = service.diagnostics(session)
        await message.answer(str(diagnostics), reply_markup=quick_actions().as_markup())

    @router.message(Command("diagnostics"))
    async def diagnostics_handler(message: Message) -> None:
        with session_factory() as session:
            diagnostics = service.diagnostics(session)
        await message.answer(f"Диагностика: {diagnostics}")

    @router.message(Command("settings"))
    async def settings_handler(message: Message) -> None:
        await message.answer(
            f"Настройки доступны в Mini App: {settings.base_url}/mini-app/settings",
            reply_markup=quick_actions().as_markup(),
        )

    @router.message(Command("archive"))
    async def archive_handler(message: Message) -> None:
        await message.answer(
            f"Архив доступен в Mini App: {settings.base_url}/mini-app/archive",
            reply_markup=quick_actions().as_markup(),
        )

    @router.message(Command("setup"))
    @router.message(Command("sync"))
    @router.message(Command("rebuild"))
    async def setup_handler(message: Message) -> None:
        with session_factory() as session:
            service.ensure_defaults(session)
            diagnostics = service.diagnostics(session)
        await message.answer(f"Системный контур синхронизирован.\n{diagnostics}")

    @router.message(Command("export"))
    async def export_handler(message: Message) -> None:
        with session_factory() as session:
            archive_path = service.create_backup(session)
        await message.answer(f"Backup создан: {archive_path.name}")

    @router.message(Command("buy"))
    async def buy_handler(message: Message) -> None:
        await message.answer(
            "Создать покупку можно в Mini App: /mini-app/purchases",
            reply_markup=quick_actions().as_markup(),
        )

    @router.message(Command("chore"))
    async def chore_handler(message: Message) -> None:
        await message.answer(
            "Создать бытовую задачу можно в Mini App: /mini-app/chores",
            reply_markup=quick_actions().as_markup(),
        )

    @router.message(Command("decision"))
    async def decision_handler(message: Message) -> None:
        await message.answer(
            "Создать решение можно в Mini App: /mini-app/decisions",
            reply_markup=quick_actions().as_markup(),
        )

    @router.message(Command("calendar"))
    async def calendar_handler(message: Message) -> None:
        await message.answer(
            "Календарь доступен в Mini App: /mini-app/calendar",
            reply_markup=quick_actions().as_markup(),
        )

    @router.message(Command("evening"))
    async def evening_handler(message: Message) -> None:
        with session_factory() as session:
            summary = service.generate_summary(session, "Вечер")
        await message.answer(summary)

    @router.message(Command("note"))
    async def note_handler(message: Message) -> None:
        await message.answer(
            "Заметки и inbox доступны в Mini App: /mini-app/notes",
            reply_markup=quick_actions().as_markup(),
        )

    @router.message(F.text)
    async def free_text_handler(message: Message) -> None:
        if message.text is None:
            return
        classification = service.classify_message(message.text)
        await message.answer(f"Похоже на: {classification.value}")

    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def handle_update(dispatcher: Dispatcher, settings: Settings, update_data: dict[str, object]) -> None:
    if not settings.bot_token:
        logger.info("webhook.skipped_no_token")
        return
    bot = Bot(token=settings.bot_token)
    update = Update.model_validate(update_data)
    await dispatcher.feed_webhook_update(bot=bot, update=update)
