from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar

from homegroup.infrastructure.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class Repository(Protocol[ModelT]):
    def get(self, entity_id: str) -> ModelT | None: ...

    def list_all(self) -> list[ModelT]: ...

    def add(self, entity: ModelT) -> ModelT: ...

    def add_many(self, entities: Iterable[ModelT]) -> list[ModelT]: ...

    def delete(self, entity: ModelT) -> None: ...
