from typing import Generic, TypeVar

from pydantic import BaseModel, computed_field

T = TypeVar("T")


class HistoryPage(BaseModel, Generic[T]):
    """Opt-in history metadata; legacy list responses remain available."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @computed_field
    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size
