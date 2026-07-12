from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers, timestamps
from pyhanko.sign.fields import SigSeedSubFilter
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.stamp import TextStampStyle

from app.errors.signature_exceptions import (
    SignatureError, SignatureValidationError, SignedOutputError, TimestampError,
)
from app.models.signature_request import SignatureRequest
from app.models.signature_result import SignatureResult
from app.models.signature_validation_result import SignatureValidationResult
from app.services.certificate_service import CertificateService

logger = logging.getLogger(__name__)


class PDFSignatureService:
    def __init__(self, certificate_service: CertificateService | None = None):
        self.certificate_service = certificate_service or CertificateService()

    def sign(self, request: SignatureRequest) -> SignatureResult:
        import fitz
        with fitz.open(request.input_path) as document:
            page_count = document.page_count
        request.validate(page_count)
        logger.info(
            "Iniciando assinatura input=%s output=%s perfil=%s",
            request.input_path, request.output_path, request.pades_profile,
        )
        signer = self.certificate_service.load_a1(
            request.certificate_path, request.certificate_password
        )
        metadata = signers.PdfSignatureMetadata(
            field_name=request.field_name,
            name=request.signer_name,
            reason=request.reason,
            location=request.location,
            contact_info=request.contact_info,
            subfilter=SigSeedSubFilter.PADES,
        )
        field_spec = None
        stamp_style = None
        if request.visible:
            field_spec = fields.SigFieldSpec(
                sig_field_name=request.field_name,
                on_page=request.page_number - 1,
                box=(int(request.x1), int(request.y1), int(request.x2), int(request.y2)),
            )
            stamp_style = TextStampStyle(
                stamp_text="Assinado digitalmente por %(signer)s\n%(ts)s"
            )
        timestamper = None
        produced_profile = "PAdES-B-B"
        if request.timestamp_url:
            timestamper = timestamps.HTTPTimeStamper(request.timestamp_url)
            produced_profile = "PAdES-B-T"

        output = request.output_path.expanduser().resolve()
        temporary = output.with_name(f".{output.stem}.{uuid4().hex}.tmp.pdf")
        try:
            with request.input_path.open("rb") as source, temporary.open("wb") as target:
                writer = IncrementalPdfFileWriter(source)
                pdf_signer = signers.PdfSigner(
                    metadata,
                    signer=signer,
                    timestamper=timestamper,
                    stamp_style=stamp_style,
                    new_field_spec=field_spec,
                )
                pdf_signer.sign_pdf(writer, output=target)
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise SignedOutputError("A saída assinada não foi produzida corretamente.")
            os.replace(temporary, output)
            logger.info("Assinatura concluída output=%s perfil=%s", output, produced_profile)
            return SignatureResult(
                output_path=output, field_name=request.field_name,
                requested_profile=request.pades_profile,
                produced_profile=produced_profile, visible=request.visible,
            )
        except Exception as exc:
            if temporary.exists():
                temporary.unlink()
            if request.timestamp_url and not isinstance(exc, SignatureError):
                raise TimestampError(f"Falha ao obter carimbo de tempo: {exc}") from exc
            if isinstance(exc, SignatureError):
                raise
            raise SignedOutputError(f"Não foi possível assinar o PDF: {exc}") from exc
        finally:
            request.certificate_password = ""
            del signer

    def validate(self, path: Path) -> list[SignatureValidationResult]:
        pdf_path = Path(path).expanduser().resolve()
        if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
            raise SignatureValidationError("Arquivo PDF inválido para validação.")
        results = []
        try:
            with pdf_path.open("rb") as stream:
                reader = PdfFileReader(stream)
                for embedded in reader.embedded_signatures:
                    results.append(self._validation_result(embedded))
            return results
        except SignatureValidationError:
            raise
        except Exception as exc:
            raise SignatureValidationError(f"Falha ao validar assinaturas: {exc}") from exc

    def _validation_result(self, embedded) -> SignatureValidationResult:
        cert = embedded.signer_cert
        now = datetime.now(timezone.utc)
        not_before = cert["tbs_certificate"]["validity"]["not_before"].native
        not_after = cert["tbs_certificate"]["validity"]["not_after"].native
        try:
            status = validate_pdf_signature(embedded)
            intact = bool(getattr(status, "intact", False))
            valid = bool(getattr(status, "valid", False))
            trusted = bool(getattr(status, "trusted", False))
            revoked = getattr(status, "revoked", None)
            modified = not intact or not bool(getattr(status, "docmdp_ok", True))
            if modified: state = "MODIFIED"
            elif revoked: state = "REVOKED"
            elif now > not_after: state = "EXPIRED"
            elif now < not_before: state = "INDETERMINATE"
            elif intact and valid and trusted: state = "VALID"
            elif intact and valid: state = "UNTRUSTED"
            else: state = "INVALID"
            details = status.bottom_line
        except Exception as exc:
            intact = valid = trusted = modified = False
            revoked = None
            state = "INDETERMINATE"
            details = str(exc)
        return SignatureValidationResult(
            field_name=embedded.field_name,
            state=state,
            signer_name=cert.subject.human_friendly,
            issuer=cert.issuer.human_friendly,
            serial_number=str(cert.serial_number),
            certificate_valid_from=str(not_before), certificate_valid_to=str(not_after),
            signing_time=str(getattr(embedded, "self_reported_timestamp", "") or ""),
            timestamp_present=getattr(embedded, "attached_timestamp_data", None) is not None,
            integrity_ok=intact, trusted=trusted, revoked=revoked, modified=modified,
            pades_profile="PAdES-B-B",
            visible=self._is_visible(embedded),
            details=details,
        )

    @staticmethod
    def _is_visible(embedded) -> bool:
        field = getattr(embedded, "sig_field", None)
        if field is None:
            return False
        rectangle = field.get("/Rect")
        if not rectangle or len(rectangle) != 4:
            return False
        return float(rectangle[2]) > float(rectangle[0]) and float(rectangle[3]) > float(rectangle[1])
