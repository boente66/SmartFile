from datetime import datetime, timezone
from pathlib import Path

from pyhanko.sign import signers

from app.errors.signature_exceptions import (
    CertificateExpiredError, CertificateLoadError,
    CertificateNotYetValidError, InvalidCertificatePasswordError,
)


class CertificateService:
    def load_a1(self, path: Path, password: str):
        certificate = Path(path).expanduser().resolve()
        if not certificate.is_file() or certificate.suffix.lower() not in {".pfx", ".p12"}:
            raise CertificateLoadError("Selecione um certificado A1 .pfx ou .p12 válido.")
        try:
            signer = signers.SimpleSigner.load_pkcs12(
                str(certificate), passphrase=password.encode("utf-8")
            )
        except Exception as exc:
            raise InvalidCertificatePasswordError(
                "Não foi possível abrir o certificado. Verifique a senha."
            ) from exc
        if signer is None:
            raise InvalidCertificatePasswordError("Senha do certificado inválida.")
        cert = signer.signing_cert
        now = datetime.now(timezone.utc)
        not_before = cert["tbs_certificate"]["validity"]["not_before"].native
        not_after = cert["tbs_certificate"]["validity"]["not_after"].native
        if now < not_before:
            raise CertificateNotYetValidError("O certificado ainda não é válido.")
        if now > not_after:
            raise CertificateExpiredError("O certificado está expirado.")
        return signer
