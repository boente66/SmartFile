from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SignatureRequest:
    input_path: Path
    output_path: Path
    certificate_path: Path
    certificate_password: str
    visible: bool = False
    page_number: int | None = None
    x1: float | None = None
    y1: float | None = None
    x2: float | None = None
    y2: float | None = None
    signer_name: str | None = None
    reason: str | None = None
    location: str | None = None
    contact_info: str | None = None
    field_name: str = "SmartFileSignature"
    timestamp_url: str | None = None
    pades_profile: str = "PAdES-B-B"

    def validate(self, page_count: int | None = None) -> None:
        for path, label, suffixes in (
            (self.input_path, "PDF de entrada", {".pdf"}),
            (self.certificate_path, "Certificado A1", {".pfx", ".p12"}),
        ):
            resolved = path.expanduser().resolve()
            if not resolved.is_file() or resolved.suffix.lower() not in suffixes:
                raise ValueError(f"{label} inválido.")
        output = self.output_path.expanduser().resolve()
        if output.suffix.lower() != ".pdf":
            raise ValueError("A saída deve possuir extensão .pdf.")
        if output.exists() or output == self.input_path.expanduser().resolve():
            raise ValueError("A saída não pode sobrescrever um arquivo existente.")
        if not output.parent.is_dir():
            raise ValueError("Diretório de saída inválido.")
        if not self.certificate_password:
            raise ValueError("Informe a senha do certificado.")
        if self.pades_profile != "PAdES-B-B":
            raise ValueError("Somente o perfil PAdES-B-B está habilitado nesta fase.")
        if self.visible:
            if self.page_number is None or self.page_number < 1:
                raise ValueError("Página da assinatura visível inválida.")
            if page_count is not None and self.page_number > page_count:
                raise ValueError("Página da assinatura fora do documento.")
            coordinates = (self.x1, self.y1, self.x2, self.y2)
            if any(value is None for value in coordinates):
                raise ValueError("Defina a área da assinatura visível.")
            if self.x2 <= self.x1 or self.y2 <= self.y1:
                raise ValueError("Área da assinatura visível inválida.")
