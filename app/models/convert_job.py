# app/models/convert_job.py

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConvertJob:
    """
    Modelo que representa UMA conversão.

    Não executa nada.
    Apenas descreve a operação.
    """

    input_path: Path
    output_path: Path
    source_format: str
    target_format: str

    # -------------------------
    # Identidade da conversão
    # -------------------------
    @property
    def conversion_key(self) -> str:
        """
        Exemplo:
        PDF->JPG
        CSV->XLSX
        """
        return f"{self.source_format.upper()}->{self.target_format.upper()}"

    # -------------------------
    # Diretório de saída
    # -------------------------
    @property
    def output_dir(self) -> Path:
        return self.output_path.parent

    # -------------------------
    # Validação
    # -------------------------
    def validate(self):

        if not self.input_path:
            raise ValueError("Arquivo de entrada não definido")

        if not self.input_path.exists():
            raise ValueError("Arquivo de entrada não existe")

        if not self.output_path:
            raise ValueError("Arquivo de saída não definido")

        if self.input_path.resolve() == self.output_path.resolve():
            raise ValueError("Entrada e saída não podem ser o mesmo arquivo")

        if not self.output_path.parent.exists():
            raise ValueError("Diretório de saída não existe")