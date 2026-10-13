"""Publicação local sem sobrescrita, independente de Qt e do domínio."""
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile


def publish_file(source: Path, target: Path) -> None:
    """Publica bytes completos; destino existente, inclusive symlink, é recusado."""
    with source.open('r+b' if os.name == 'nt' else 'rb') as handle:
        os.fsync(handle.fileno())
    try:
        os.link(source, target)
    except FileExistsError:
        raise
    except OSError:
        if os.name != 'nt':
            raise
        # No Windows, rename recusa um destino existente (não usar replace).
        os.rename(source, target)


@contextmanager
def atomic_output(target: Path):
    target = Path(target).expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(target):
        raise FileExistsError(f'O arquivo de saída já existe: {target}')
    descriptor, filename = tempfile.mkstemp(prefix=f'.{target.stem}-', suffix=target.suffix, dir=target.parent)
    os.close(descriptor)
    temporary = Path(filename)
    try:
        yield temporary
        publish_file(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
