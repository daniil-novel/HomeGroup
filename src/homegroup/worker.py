from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler

from homegroup.application.ports import TelegramGateway
from homegroup.application.services import HomeGroupService
from homegroup.infrastructure.config import Settings
from homegroup.infrastructure.db.session import create_session_factory


class HomeGroupWorker:
    def __init__(
        self,
        settings: Settings,
        service: HomeGroupService,
        telegram_gateway: TelegramGateway,
    ) -> None:
        self.settings = settings
        self.service = service
        self.telegram_gateway = telegram_gateway
        self.session_factory = create_session_factory(settings)

    def run(self) -> None:
        scheduler = BlockingScheduler(timezone=self.settings.timezone)
        scheduler.add_job(
            self.publish_morning_summary,
            "cron",
            hour=self.settings.morning_time.hour,
            minute=self.settings.morning_time.minute,
        )
        scheduler.add_job(
            self.publish_evening_summary,
            "cron",
            hour=self.settings.evening_time.hour,
            minute=self.settings.evening_time.minute,
        )
        scheduler.add_job(
            self.publish_weekly_review,
            "cron",
            day_of_week=self.settings.weekly_review_day.lower()[:3],
            hour=self.settings.weekly_review_time.hour,
            minute=self.settings.weekly_review_time.minute,
        )
        scheduler.add_job(self.create_backup, "cron", hour=3, minute=0)
        scheduler.add_job(self.publish_diagnostics, "interval", minutes=30)
        scheduler.start()

    def publish_morning_summary(self) -> None:
        self._publish("Утро", "today")

    def publish_evening_summary(self) -> None:
        self._publish("Вечер", "today")

    def publish_weekly_review(self) -> None:
        self._publish("Неделя", "week")

    def create_backup(self) -> None:
        with self.session_factory() as session:
            archive_path = self.service.create_backup(session)
        self.telegram_gateway.publish_system_message(f"Backup создан: {archive_path.name}")

    def publish_diagnostics(self) -> None:
        with self.session_factory() as session:
            diagnostics = self.service.diagnostics(session)
        self.telegram_gateway.publish_system_message(f"Diagnostics: {diagnostics}")

    def _publish(self, title: str, topic_slug: str) -> None:
        with self.session_factory() as session:
            summary = self.service.generate_summary(session, title)
        self.telegram_gateway.publish_summary(topic_slug, summary)
