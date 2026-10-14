from app.models.delivery_basket import DeliveryBasket, DeliveryBasketItem
from app.services.organization_feature_service import OrganizationFeatureService


class DeliveryBasketService:
    """Cesta referencial: mantém IDs oficiais, nunca bytes dos documentos."""
    def __init__(self, document_service, context):
        self.documents = document_service; self.context = context
        self.features = OrganizationFeatureService(document_service.database)
        self.audit = document_service.audit
        self.basket = DeliveryBasket()

    def begin(self, *, request_id: int | None = None, recipient_user_id: int | None = None) -> DeliveryBasket:
        self._require_business()
        self.audit.record('DELIVERY_PREPARATION_STARTED', organization_id=self.context.active_organization.id,
            target_type='document_request' if request_id else 'delivery_basket', target_id=request_id)
        self.basket = DeliveryBasket("REQUEST" if request_id else "DIRECT", request_id, recipient_user_id)
        return self.basket

    def add_document(self, document_id: int) -> DeliveryBasket:
        self._require_business()
        self.context.require_permission("delivery.create")
        document = self.documents.get_document(document_id)
        if document is None or document.status != "ACTIVE": raise ValueError("Documento indisponível.")
        linked = any(item.document_id == document_id for item in self.basket.items)
        self.basket.add(DeliveryBasketItem(document.id, document.name, document.size))
        if not linked:
            self.audit.record('DELIVERY_PREPARED', organization_id=document.organization_id,
                target_type='document', target_id=document.id, document=document,
                sha256_after=document.checksum, details={'request_id':self.basket.request_id})
        return self.basket

    def remove_document(self, document_id: int) -> DeliveryBasket:
        self.basket.remove(document_id); return self.basket

    def clear(self) -> None: self.basket.clear()

    def _require_business(self) -> None:
        organization = getattr(self.context, "active_organization", None)
        if organization is None:
            raise PermissionError("Ative uma organização.")
        self.features.require(organization, "document_requests")
