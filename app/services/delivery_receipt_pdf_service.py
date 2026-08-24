from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import fitz

from app.errors.delivery_exceptions import DeliveryIntegrityError
from app.models.delivery_receipt_request import DeliveryReceiptRequest


class DeliveryReceiptPdfService:
    """Gera comprovantes A4 atômicos sem modificar documentos recebidos."""

    PAGE = fitz.paper_rect("a4")

    def generate(self, request: DeliveryReceiptRequest) -> Path:
        output = request.output_path.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.stem}.{uuid4().hex}.part.pdf")
        document = fitz.open()
        try:
            page = document.new_page(width=self.PAGE.width, height=self.PAGE.height)
            y = self._header(page, request)
            y = self._documents(document, page, y, request)
            page = document[-1]
            y = self._declaration(page, y)
            self._signature(page, y, request)
            self._footers(document, request.protocol_number)
            document.set_metadata({
                "title": f"Comprovante de recebimento {request.protocol_number}",
                "author": "SmartFile",
                "subject": f"Identificador {request.receipt_uuid}",
            })
            document.save(temporary, garbage=4, deflate=True)
            document.close()
            with temporary.open("rb") as handle:
                os.fsync(handle.fileno())
            with fitz.open(temporary) as validation:
                if validation.page_count < 1:
                    raise DeliveryIntegrityError("O comprovante PDF não possui páginas.")
            os.replace(temporary, output)
            return output
        except Exception as exc:
            if not document.is_closed:
                document.close()
            raise DeliveryIntegrityError(
                "Não foi possível gerar o comprovante de recebimento."
            ) from exc
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _header(page: fitz.Page, request: DeliveryReceiptRequest) -> float:
        page.insert_text((48, 52), "SMARTFILE", fontsize=17, color=(0.05, 0.25, 0.14))
        page.insert_text((48, 82), "COMPROVANTE DE RECEBIMENTO", fontsize=16)
        values = (
            ("Protocolo", request.protocol_number),
            ("Organização", request.organization_name),
            ("Remetente", request.sender_name),
            ("Destinatário", request.recipient_name),
            ("Recebido em", request.received_at),
            ("Confirmado em", request.confirmed_at),
            ("Identificador", request.receipt_uuid),
        )
        y = 112.0
        for label, value in values:
            page.insert_text((48, y), f"{label}:", fontsize=9, color=(0.25, 0.3, 0.38))
            page.insert_text((145, y), str(value or "—"), fontsize=9)
            y += 18
        page.draw_line((48, y), (547, y), color=(0.75, 0.8, 0.84), width=0.7)
        return y + 26

    def _documents(
        self, document: fitz.Document, page: fitz.Page, y: float,
        request: DeliveryReceiptRequest,
    ) -> float:
        page.insert_text((48, y), "DOCUMENTOS RECEBIDOS", fontsize=11)
        y += 22
        for index, item in enumerate(request.documents, 1):
            if y > 700:
                page = document.new_page(width=self.PAGE.width, height=self.PAGE.height)
                y = 54
            block = (
                f"{index}. {item.name}\n"
                f"    Tamanho: {self._size(item.size)}\n"
                f"    SHA-256: {item.sha256}"
            )
            page.insert_textbox(
                fitz.Rect(48, y, 547, y + 54), block, fontsize=8.2,
                lineheight=1.25,
            )
            y += 62
        return y

    @staticmethod
    def _declaration(page: fitz.Page, y: float) -> float:
        y = min(max(y + 12, 430), 610)
        page.insert_text((48, y), "DECLARAÇÃO", fontsize=11)
        y += 20
        page.insert_textbox(
            fitz.Rect(48, y, 547, y + 44),
            "Confirmo o recebimento dos documentos relacionados ao protocolo acima.",
            fontsize=9.5,
        )
        return y + 52

    @staticmethod
    def _signature(page: fitz.Page, y: float, request: DeliveryReceiptRequest) -> None:
        area = fitz.Rect(48, y, 265, min(y + 82, 744))
        page.insert_image(area, stream=request.signature_image, keep_proportion=True)
        label_y = min(area.y1 + 14, 770)
        method = (
            "desenhada no SmartFile" if request.signature_method == "DRAWN"
            else "imagem fornecida pelo signatário"
        )
        page.insert_text((48, label_y), request.recipient_name, fontsize=9)
        page.insert_text(
            (48, label_y + 14), f"Assinatura visual — {method}",
            fontsize=8, color=(0.3, 0.35, 0.42),
        )

    @staticmethod
    def _footers(document: fitz.Document, protocol: str) -> None:
        for index, page in enumerate(document, 1):
            page.draw_line((48, 802), (547, 802), color=(0.75, 0.8, 0.84), width=0.5)
            page.insert_text(
                (48, 820),
                f"SmartFile · Protocolo {protocol} · Página {index}/{document.page_count}",
                fontsize=7.5, color=(0.35, 0.4, 0.48),
            )

    @staticmethod
    def _size(value: int) -> str:
        if value >= 1024 * 1024:
            return f"{value / (1024 * 1024):.2f} MB"
        return f"{value / 1024:.1f} KB"

