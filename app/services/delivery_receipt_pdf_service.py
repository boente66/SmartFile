from __future__ import annotations

import os
import base64
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
            if y > 570:
                page = document.new_page(width=self.PAGE.width,height=self.PAGE.height)
                y = 54
            y = self._declaration(page, y, request)
            self._signature(page, y, request)
            if request.qr_payload:
                from app.services.signature_verification_service import SignatureVerificationService
                SignatureVerificationService.insert_qr(document, request.qr_payload,
                    document.page_count, (395, 674, 485, 764), request.qr_human_code)
            self._footers(document, request.protocol_number)
            document.set_metadata({
                "title": f"Comprovante de recebimento {request.protocol_number}",
                "author": "SmartFile",
                "subject": f"Identificador {request.receipt_uuid}",
            })
            document.save(temporary, garbage=4, deflate=True)
            document.close()
            # Windows only exposes a synchronizable file handle when it was
            # opened with write access.  ``r+b`` does not alter the already
            # generated PDF, but keeps the durability barrier portable.
            with temporary.open("r+b") as handle:
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
        identity=request.corporate_identity
        start_y=52
        if identity and identity.authority_instance_id:
            color=tuple(int(identity.header_color[i:i+2],16)/255 for i in (1,3,5))
            text=identity.foreground(identity.header_color)
            foreground=tuple(int(text[i:i+2],16)/255 for i in (1,3,5))
            page.draw_rect(fitz.Rect(48,26,547,98),color=color,fill=color)
            if identity.logo:page.insert_image(fitz.Rect(55,32,101,78),stream=base64.b64decode(identity.logo),keep_proportion=True)
            x=109 if identity.logo else 55
            title=identity.title(request.organization_name)+'\n'+identity.unit
            for size in (10,9,8,7):
                if page.insert_textbox(fitz.Rect(x,32,538,82),title,fontsize=size,color=foreground)>=0:break
            page.insert_text((55,92),'Gerado pelo SmartFile',fontsize=8,color=foreground)
            start_y=126
        else:
            page.insert_text((48,start_y),'SMARTFILE',fontsize=17,color=(.05,.25,.14))
            start_y+=30
        page.insert_text((48,start_y),'COMPROVANTE DE ENVIO' if request.receipt_kind=='SENT' else 'COMPROVANTE DE RECEBIMENTO',fontsize=14)
        values=[('Protocolo',request.protocol_number),('Organização de origem',request.organization_name),
            ('Organização de destino',request.organization_name),('Remetente',request.sender_name),
            ('Destinatário',request.recipient_name),('Usuário SmartFile',request.signer_username or request.recipient_name),
            ('Instalação remetente',request.sender_instance_id or 'Não informada (legado)'),
            ('Instalação destinatária',request.recipient_instance_id or 'Não informada (legado)'),
            ('Enviado/preparado em' if request.receipt_kind=='SENT' else 'Recebido em',request.received_at),('Confirmado em',request.confirmed_at),
            ('Status',request.status),('Identificador',request.receipt_uuid)]
        if identity and identity.show_legal_details_on_receipts:
            values.extend((label,value) for label,value in [('Razão social',identity.legal_name),('CNPJ',identity.cnpj),('Endereço',identity.address)] if value)
        y=start_y+20
        for label,value in values:
            line=f'{label}: {value or "—"}'
            # Technical fields use flexible height and are never covered by the branding.
            for height in (22,36,54):
                if page.insert_textbox(fitz.Rect(48,y,547,y+height),line,fontsize=8.5)>=0:
                    y+=height;break
            else:raise DeliveryIntegrityError('Campo do comprovante excede o espaço disponível.')
        page.draw_line((48,y),(547,y),color=(.75,.8,.84),width=.7)
        return y+24

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
    def _declaration(page: fitz.Page, y: float, request=None) -> float:
        y = min(max(y + 12, 430), 610)
        if request is not None and request.receipt_kind=='SENT':
            page.insert_text((48,y),'REGISTRO DO ENVIO',fontsize=11)
            page.insert_textbox(fitz.Rect(48,y+18,547,y+65),
                'Este comprovante registra o protocolo e o estado do envio no momento de sua geração. '
                'Não constitui confirmação de recebimento pelo destinatário. Consulte o status e o comprovante de recebimento.',fontsize=9)
            return y+82
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
        if not request.signature_image:
            page.insert_text((48,min(y,760)),'Comprovante gerado pelo SmartFile; não constitui assinatura visual.',fontsize=8)
            return
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
