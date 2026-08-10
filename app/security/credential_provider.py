from __future__ import annotations

from abc import ABC, abstractmethod

from app.errors.transport_exceptions import CredentialVaultUnavailableError


class CredentialProvider(ABC):
    """Contrato mínimo para armazenamento externo ao SQLite."""

    @abstractmethod
    def store(self, reference: str, secret: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, reference: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, reference: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, reference: str) -> bool:
        raise NotImplementedError


class OSCredentialProvider(CredentialProvider):
    """Usa Secret Service no Linux e Credential Manager no Windows."""

    SERVICE_NAME = "SmartFile.Transport"

    def store(self, reference: str, secret: str) -> None:
        try:
            import keyring

            keyring.set_password(self.SERVICE_NAME, reference, secret)
        except Exception:
            raise CredentialVaultUnavailableError(
                "O cofre seguro do sistema operacional não está disponível."
            ) from None

    def get(self, reference: str) -> str | None:
        try:
            import keyring

            return keyring.get_password(self.SERVICE_NAME, reference)
        except Exception:
            raise CredentialVaultUnavailableError(
                "Não foi possível acessar o cofre seguro do sistema operacional."
            ) from None

    def delete(self, reference: str) -> None:
        try:
            import keyring

            keyring.delete_password(self.SERVICE_NAME, reference)
        except Exception as exc:
            try:
                import keyring.errors

                if isinstance(exc, keyring.errors.PasswordDeleteError):
                    return
            except Exception:
                pass
            raise CredentialVaultUnavailableError(
                "Não foi possível remover a credencial do cofre seguro."
            ) from None

    def exists(self, reference: str) -> bool:
        return self.get(reference) is not None
