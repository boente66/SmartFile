from __future__ import annotations


class TransportError(Exception):
    """Erro base da camada de transporte corporativo."""


class TransportConfigurationError(TransportError):
    """Configuração incompatível ou estruturalmente inválida."""


class TransportRetryableError(TransportError):
    """Falha temporária que pode ser tentada novamente."""


class TransportIntegrityError(TransportRetryableError):
    """O conteúdo transferido não corresponde ao documento local."""


class TransportCancelledError(TransportError):
    """Operação interrompida cooperativamente."""


class TransportModeNotImplementedError(TransportConfigurationError):
    """O modo é configurável, mas ainda não possui conector físico."""


class TransportReconciliationError(TransportConfigurationError):
    """A identidade histórica do destino exige decisão administrativa."""


class CredentialVaultError(TransportError):
    """Erro seguro na gestão de credenciais do transporte."""


class CredentialVaultUnavailableError(CredentialVaultError):
    """O cofre seguro do sistema operacional não está disponível."""


class CredentialNotFoundError(CredentialVaultError):
    """A referência não existe no cofre seguro."""


class CredentialInUseError(CredentialVaultError):
    """A credencial ainda é necessária por target ou job histórico."""
