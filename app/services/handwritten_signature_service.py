from __future__ import annotations

import logging
import os
from pathlib import Path
from uuid import uuid4

import fitz
from PyQt6.QtGui import QImage

from app.errors.handwritten_signature_exceptions import (
    ExistingDigitalSignatureWarning,
    SignatureImageError,
    SignedDocumentWriteError,
)
from app.models.handwritten_signature_request import HandwrittenSignatureRequest
from app.models.handwritten_signature_result import HandwrittenSignatureResult

logger = logging.getLogger(__name__)


class HandwrittenSignatureService:
    """Incorpora uma marca manuscrita visual sem criar assinatura criptográfica."""

    def has_digital_signatures(self, path: Path) -> bool:
        source = self._validated_pdf(path)
        try:
            with fitz.open(source) as document:
                return any(
                    widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE
                    for page in document
                    for widget in (page.widgets() or ())
                )
        except Exception as exc:
            raise SignatureImageError("Não foi possível verificar as assinaturas do PDF.") from exc

    def page_size(self, path: Path, page_number: int) -> tuple[float, float]:
        source = self._validated_pdf(path)
        with fitz.open(source) as document:
            if not 1 <= page_number <= document.page_count:
                from app.errors.handwritten_signature_exceptions import InvalidSignaturePageError
                raise InvalidSignaturePageError("A página selecionada não existe no documento.")
            rectangle = document[page_number - 1].rect
            return float(rectangle.width), float(rectangle.height)

    def apply(self, request: HandwrittenSignatureRequest) -> HandwrittenSignatureResult:
        source = self._validated_pdf(request.input_path)
        had_signatures = self.has_digital_signatures(source)
        if had_signatures and not request.existing_signatures_confirmed:
            raise ExistingDigitalSignatureWarning(
                "Este PDF possui assinatura digital. Alterar seu conteúdo pode invalidá-la."
            )
        page_size = self.page_size(source, request.page_number)
        request.validate(self._page_count(source), page_size)
        self._validate_image(request.signature_image)

        output = request.output_path.expanduser().resolve()
        temporary = output.with_name(f".{output.stem}.{uuid4().hex}.tmp.pdf")
        logger.info(
            "Aplicando assinatura manuscrita input=%s output=%s pagina=%s",
            source, output, request.page_number,
        )
        try:
            with fitz.open(source) as document:
                page = document[request.page_number - 1]
                rectangle = fitz.Rect(
                    request.x,
                    request.y,
                    request.x + request.width,
                    request.y + request.height,
                )
                page.insert_image(rectangle, stream=request.signature_image, keep_proportion=True, overlay=True)
                if request.add_caption:
                    self._insert_caption(page, request)
                document.save(temporary, garbage=0, deflate=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise SignedDocumentWriteError("O PDF de saída não foi gerado corretamente.")
            os.replace(temporary, output)
        except ExistingDigitalSignatureWarning:
            raise
        except Exception as exc:
            raise SignedDocumentWriteError("Não foi possível salvar o PDF com a assinatura manuscrita.") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning("Não foi possível remover o temporário %s", temporary)

        logger.info("Assinatura manuscrita concluída output=%s", output)
        return HandwrittenSignatureResult(
            output_path=output,
            page_number=request.page_number,
            had_digital_signatures=had_signatures,
            signer_name=request.signer_name,
        )

    @staticmethod
    def _insert_caption(page: fitz.Page, request: HandwrittenSignatureRequest) -> None:
        name = request.signer_name or "Assinante"
        timestamp = request.signed_at.astimezone().strftime("%d/%m/%Y %H:%M")
        text = f"{name}\nAssinado eletronicamente em {timestamp}"
        top = min(request.y + request.height + 3, page.rect.height - 28)
        caption = fitz.Rect(request.x, top, request.x + request.width, min(top + 28, page.rect.height))
        page.insert_textbox(caption, text, fontsize=7, color=(0.15, 0.15, 0.15), align=0, overlay=True)

    @staticmethod
    def _validate_image(data: bytes) -> None:
        image = QImage.fromData(data, "PNG")
        if image.isNull() or not image.hasAlphaChannel():
            raise SignatureImageError("A assinatura deve ser uma imagem PNG transparente válida.")

    @staticmethod
    def _validated_pdf(path: Path) -> Path:
        try:
            source = Path(path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise SignatureImageError("O PDF informado não existe.") from exc
        if not source.is_file() or source.suffix.lower() != ".pdf":
            raise SignatureImageError("O arquivo informado não é um PDF válido.")
        return source

    @staticmethod
    def _page_count(path: Path) -> int:
        with fitz.open(path) as document:
            return document.page_count
