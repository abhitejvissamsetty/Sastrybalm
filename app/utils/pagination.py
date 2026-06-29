from dataclasses import dataclass, field
from typing import Any

DEFAULT_PER_PAGE = 25


@dataclass
class Page:
    items: list[Any]
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        return max(1, (self.total + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def prev_page(self) -> int:
        return self.page - 1

    @property
    def next_page(self) -> int:
        return self.page + 1

    @property
    def start_item(self) -> int:
        return (self.page - 1) * self.per_page + 1 if self.total > 0 else 0

    @property
    def end_item(self) -> int:
        return min(self.page * self.per_page, self.total)


def paginate(query, page: int = 1, per_page: int = DEFAULT_PER_PAGE) -> Page:
    page = max(1, page)
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return Page(items=items, total=total, page=page, per_page=per_page)
