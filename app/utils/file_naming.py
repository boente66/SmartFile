from pathlib import Path
from datetime import datetime

def safe_output_path(output_path: Path) -> Path:
    """
    Gera um caminho de saída seguro, evitando sobrescrever arquivos existentes.
    Se o arquivo já existir, adiciona um sufixo com a data e hora atual.
    """
    if not output_path.exists():
        return output_path

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_name = f"{output_path.stem}_{timestamp}{output_path.suffix}"

    return output_path.with_name(new_name)

