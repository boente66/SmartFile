from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.errors.handwritten_signature_exceptions import (
    EmptySignatureError,
    InvalidSignaturePageError,
    InvalidSignaturePositionError,
    SignatureImageError,
)


@dataclass(slots=True)
class HandwrittenSignatureRequest:
    input_path: Path
    output_path: Path
    page_number: int
    x: float
    y: float
    width: float
    height: float
    signature_image: bytes
    signer_name: str | None
    signed_at: datetime
    color: str
    stroke_width: float
    add_caption: bool
    existing_signatures_confirmed: bool = False

    def validate(self, page_count: int, page_size: tuple[float, float]) -> None:
        source = self.input_path.expanduser().resolve()
        output = self.output_path.expanduser().resolve()
        if not source.is_file() or source.suffix.lower() != ".pdf":
            raise SignatureImageError("Selecione um arquivo PDF válido.")
        if output.suffix.lower() != ".pdf" or output == source:
            raise InvalidSignaturePositionError("A saída deve ser um novo arquivo PDF.")
        if not output.parent.is_dir():
            raise InvalidSignaturePositionError("A pasta de saída não existe.")
        if output.exists():
            raise InvalidSignaturePositionError("O arquivo de saída já existe. Escolha um novo nome.")
        if not 1 <= self.page_number <= page_count:
            raise InvalidSignaturePageError("A página selecionada não existe no documento.")
        if not self.signature_image:
            raise EmptySignatureError("Desenhe a assinatura antes de continuar.")
        if len(self.signature_image) > 10 * 1024 * 1024:
            raise SignatureImageError("A imagem da assinatura excede o limite de 10 MB.")
        if self.width <= 0 or self.height <= 0 or self.x < 0 or self.y < 0:
            raise InvalidSignaturePositionError("A posição ou o tamanho da assinatura é inválido.")
        page_width, page_height = page_size
        if self.x + self.width > page_width + 0.01 or self.y + self.height > page_height + 0.01:
            raise InvalidSignaturePositionError("A assinatura deve permanecer dentro da página.")
