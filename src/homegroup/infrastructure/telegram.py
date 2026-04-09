from __future__ import annotations

import asyncio
from dataclasses import dataclass

import structlog
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder
from telethon import TelegramClient
from telethon.tl.functions.channels import (
    CreateChannelRequest,
    InviteToChannelRequest,
    ToggleForumRequest,
)
from telethon.tl.functions.messages import CreateForumTopicRequest

from homegroup.application.bootstrap import TOPIC_DEFINITIONS
from homegroup.application.ports import ProvisioningGateway, TelegramGateway
from homegroup.application.services import HomeGroupService
from homegroup.infrastructure.config import Settings
from homegroup.infrastructure.db.session import create_session_factory

logger = structlog.get_logger(__name__)


def render_entity_card(title: str, lines: list[str], mini_app_url: str | None = None) -> str:
    body = "\n".join(f"• {line}" for line in lines if line)
    footer = f"\n\nMini App: {mini_app_url}" if mini_app_url else ""
    return f"{title}\n\n{body}{footer}"


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
                "homegroup_provisioning",
                self.settings.telegram_api_id,
                self.settings.telegram_api_hash,
            ) as client:
                result = await client(
                    CreateChannelRequest(
                        title="Дом",
                        about="Наше расписание, покупки, быт, решения и общая рутина",
                        megagroup=True,
                        forum=True,
                    )
                )
                chat = result.chats[0]
                await client(ToggleForumRequest(channel=chat, enabled=True))
                if self.settings.telegram_second_user_username:
                    await client(
                        InviteToChannelRequest(
                            channel=chat,
                            users=[self.settings.telegram_second_user_username],
                        )
                    )
                for topic in TOPIC_DEFINITIONS:
                    await client(
                        CreateForumTopicRequest(
                            peer=chat,
                            title=str(topic["title"]),
                        )
                    )
                return f"Provisioned chat {chat.id}"

        return asyncio.run(runner())


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
