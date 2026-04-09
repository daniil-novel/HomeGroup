from __future__ import annotations

from collections.abc import Iterable
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from homegroup.application.audit import AuditEntry
from homegroup.application.repositories import Repository
from homegroup.infrastructure.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class SQLAlchemyRepository(Generic[ModelT], Repository[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get(self, entity_id: str) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def list_all(self) -> list[ModelT]:
        return list(self.session.scalars(select(self.model)))

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        return entity

    def add_many(self, entities: Iterable[ModelT]) -> list[ModelT]:
        items = list(entities)
        self.session.add_all(items)
        return items

    def delete(self, entity: ModelT) -> None:
        self.session.delete(entity)


class AuditRepository(SQLAlchemyRepository[Base]):
    def add_entry(self, entry: AuditEntry) -> None:
        self.session.add(entry.to_model())
