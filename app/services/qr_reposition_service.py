"""Reposition only an identifiable SmartFile QR from registered, unchanged bytes."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

import fitz
from PIL import Image

from app.services.signature_verification_service import SignatureVerificationService
from app.services.validation_locator_service import ValidationLocatorService
from app.utils.atomic_output import atomic_output
from app.utils.export_destination import require_external_output


@dataclass(frozen=True)
class QrLocation:
    page_number: int
    rect: tuple
    page_size: tuple
    streams: tuple
    record: object
    digitally_signed: bool


@dataclass(frozen=True)
class RepositionResult:
    output_path: Path


class QrRepositionService:
    def __init__(self, validation_service):
        self.validation_service = validation_service

    def inspect(self, path, page_number, point=None):
        service = self.validation_service
        organization = service.active_organization_id()
        service._require(organization, 'tools.use')
        service._require(organization, 'validation.view')
        sha, _ = service.artifacts.hash_file(path)
        records = service.repository.lookup_all_by_hash(sha, organization)
        with fitz.open(path) as document:
            if not 1 <= page_number <= document.page_count:
                raise ValueError('Página inválida.')
            page = document[page_number - 1]
            signed = any(w.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE for p in document for w in (p.widgets() or ()))
            for record in records:
                if record.status != 'ACTIVE':
                    continue
                expected = SignatureVerificationService.qr_png(ValidationLocatorService.build_payload(record))
                with Image.open(BytesIO(expected)) as image:
                    expected_pixels = image.convert('RGB').tobytes()
                    expected_size = image.size
                for image in page.get_images(full=True):
                    data = document.extract_image(image[0])
                    with Image.open(BytesIO(data['image'])) as candidate:
                        if candidate.size != expected_size or candidate.convert('RGB').tobytes() != expected_pixels:
                            continue
                    for rect in page.get_image_rects(image[0]):
                        visual = rect * page.rotation_matrix
                        if point is not None and not visual.contains(fitz.Point(*point)):
                            continue
                        # Old SmartFile versions wrote one isolated stream for the image,
                        # and one isolated stream for its two-line validation label.
                        draw = re.compile(rb'\s*q\s+[-+\d.eE\s]+cm\s+/' + re.escape(image[7].encode()) + rb'\s+Do\s+Q\s*')
                        code = 'SFV-' + '-'.join(record.human_code[i:i+4] for i in range(3, len(record.human_code), 4))
                        candidates = []
                        for xref in page.get_contents():
                            stream = document.xref_stream(xref)
                            if draw.fullmatch(stream):
                                candidates.append(xref)
                            elif (b'<56616c6964617220646f63756d656e746f>' in stream
                                  and code.encode().hex().encode() in stream.lower()
                                  and stream.count(b'TJ') == 2 and stream.count(b'BT') == 1):
                                candidates.append(xref)
                        if len(candidates) != 2 or len(page.get_image_rects(image[0])) != 1:
                            continue
                        return QrLocation(page_number, tuple(visual), (page.rect.width, page.rect.height), tuple(candidates), record, signed)
        raise ValueError('Não foi encontrado neste ponto um QR SmartFile ativo e verificável. Abra a cópia original registrada; QRs externos ou PDFs alterados não são removidos automaticamente.')

    @staticmethod
    def remove(document, location, *, remove_signatures=False):
        for xref in location.streams:
            document.update_stream(xref, b'')
        if remove_signatures:
            for page in document:
                for widget in list(page.widgets() or ()):
                    if widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                        page.delete_widget(widget)

    def move(self, source, output, page_number, rect):
        source, output = Path(source), Path(output)
        if output.suffix.lower() != '.pdf':
            raise ValueError('A saída deve possuir extensão .pdf.')
        service = self.validation_service
        require_external_output(output, service.database.paths)
        location = self.inspect(source, page_number)
        if location.digitally_signed:
            raise ValueError('O PDF A1 precisa ser assinado novamente após reposicionar o QR.')
        def produce(payload, code):
            with fitz.open(source) as document:
                self.remove(document, location)
                SignatureVerificationService.insert_qr(document, payload, page_number, rect, code)
                with atomic_output(output) as temporary:
                    document.save(temporary, garbage=0, deflate=True)
            return RepositionResult(output)
        result = service.finalize(produce, logical_name=output.name,
                                  artifact_type=location.record.artifact_type,
                                  signature_type=location.record.signature_type,
                                  document_id=location.record.document_id, source_path=source)
        service.record_derivative('QR_REPOSITION', source, output)
        return result
