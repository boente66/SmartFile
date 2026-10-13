from pathlib import Path
from datetime import datetime

def safe_output_path(output_path: Path) -> Path:
    """
    Gera um caminho de saída seguro, evitando sobrescrever arquivos existentes.
    Se o arquivo já existir, adiciona um sufixo com a data e hora atual.
    """
    if not output_path.exists() and not output_path.is_symlink():
        return output_path

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = output_path.with_name(f"{output_path.stem}_{timestamp}{output_path.suffix}")
    counter = 2
    while candidate.exists() or candidate.is_symlink():
        candidate = output_path.with_name(f"{output_path.stem}_{timestamp}_{counter}{output_path.suffix}")
        counter += 1
    return candidate


def export_filename(name: str, suffix: str = "", extension: str = ".pdf") -> str:
    import re
    from pathlib import PureWindowsPath
    stem = Path(name.replace("\\", "/")).stem
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', stem).strip(' .') or 'documento'
    if PureWindowsPath(stem).is_reserved():stem = '_' + stem
    while len(stem.encode('utf-8')) > 180:stem = stem[:-1]
    return stem + suffix + extension
