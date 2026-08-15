from dataclasses import dataclass, field


@dataclass(slots=True)
class DeliveryBasketItem:
    document_id: int
    logical_name: str
    size: int
    source: str = "GED"


@dataclass(slots=True)
class DeliveryBasket:
    source_type: str = "DIRECT"
    request_id: int | None = None
    recipient_user_id: int | None = None
    items: list[DeliveryBasketItem] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.items)

    def add(self, item: DeliveryBasketItem) -> None:
        if not any(existing.document_id == item.document_id for existing in self.items):
            self.items.append(item)

    def remove(self, document_id: int) -> None:
        self.items = [item for item in self.items if item.document_id != document_id]

    def clear(self) -> None:
        self.items.clear()
