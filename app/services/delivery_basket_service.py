from app.models.delivery_basket import DeliveryBasket, DeliveryBasketItem


class DeliveryBasketService:
    """Cesta referencial: mantém IDs oficiais, nunca bytes dos documentos."""
    def __init__(self, document_service, context):
        self.documents = document_service; self.context = context
        self.basket = DeliveryBasket()

    def begin(self, *, request_id: int | None = None, recipient_user_id: int | None = None) -> DeliveryBasket:
        self.basket = DeliveryBasket("REQUEST" if request_id else "DIRECT", request_id, recipient_user_id)
        return self.basket

    def add_document(self, document_id: int) -> DeliveryBasket:
        self.context.require_permission("delivery.create")
        document = self.documents.get_document(document_id)
        if document is None or document.status != "ACTIVE": raise ValueError("Documento indisponível.")
        self.basket.add(DeliveryBasketItem(document.id, document.name, document.size))
        return self.basket

    def remove_document(self, document_id: int) -> DeliveryBasket:
        self.basket.remove(document_id); return self.basket

    def clear(self) -> None: self.basket.clear()
