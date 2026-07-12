class SignatureError(RuntimeError):
    """Falha genérica no domínio de assinaturas digitais."""


class CertificateLoadError(SignatureError):
    """Certificado não pôde ser carregado."""


class InvalidCertificatePasswordError(CertificateLoadError):
    """Senha do certificado inválida."""


class CertificateExpiredError(CertificateLoadError):
    """Certificado expirado."""


class CertificateNotYetValidError(CertificateLoadError):
    """Certificado ainda não entrou em validade."""


class UnsupportedCertificateError(CertificateLoadError):
    """Formato ou algoritmo do certificado não suportado."""


class SignatureValidationError(SignatureError):
    """Falha ao validar uma assinatura existente."""


class TimestampError(SignatureError):
    """Falha ao obter ou incorporar carimbo RFC 3161."""


class PKCS11Error(SignatureError):
    """Reservada para futura integração com certificados A3."""


class SignedOutputError(SignatureError):
    """O PDF assinado não pôde ser produzido com segurança."""
