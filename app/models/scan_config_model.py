# app/models/scan_config_model.py

from dataclasses import dataclass


@dataclass
class ScanConfigModel:
    """
    Configuração usada para digitalização.
    """

    device_name: str
    dpi: int = 300
    color_mode: str = "color"  # color | gray | bw

    VALID_COLOR_MODES = {"color", "gray", "bw"}

    def validate(self):

        if not self.device_name:
            raise ValueError("Nenhum dispositivo selecionado")

        if self.dpi <= 0:
            raise ValueError("DPI inválido")

        if self.color_mode not in self.VALID_COLOR_MODES:
            raise ValueError(
                f"Modo de cor inválido: {self.color_mode}"
            )