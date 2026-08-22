from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION
from app.delivery.delivery_http_client import DeliveryHttpClient
from app.services.document_delivery_service import DocumentDeliveryService
from app.services.lan_device_discovery_service import LanDeviceDiscoveryService


def test_delivery_protocol_has_one_neutral_source_of_truth():
    assert DELIVERY_PROTOCOL_VERSION == "1"
    assert not hasattr(DocumentDeliveryService, "PROTOCOL_VERSION")
    assert not hasattr(LanDeviceDiscoveryService, "PROTOCOL_VERSION")
    assert (
        DeliveryHttpClient.identity.__globals__["DELIVERY_PROTOCOL_VERSION"]
        == DELIVERY_PROTOCOL_VERSION
    )
