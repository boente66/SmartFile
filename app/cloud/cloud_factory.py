from app.cloud.cloud_models import CloudProviderType
from app.cloud.cloud_provider import CloudProvider, Transport
from app.cloud.providers.google_drive_provider import GoogleDriveProvider
from app.cloud.providers.onedrive_provider import OneDriveProvider


class CloudFactory:
    @staticmethod
    def create(provider: str, access_token: str = "", transport: Transport | None = None) -> CloudProvider:
        normalized = CloudProviderType(provider)
        if normalized == CloudProviderType.ONEDRIVE:
            return OneDriveProvider(access_token, transport)
        if normalized == CloudProviderType.GOOGLE_DRIVE:
            return GoogleDriveProvider(access_token, transport)
        raise ValueError(f"Provedor não suportado: {provider}")
