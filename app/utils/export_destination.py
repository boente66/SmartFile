"""Protege diretórios internos contra saídas não registradas de ferramentas."""
from pathlib import Path


def is_internal_output(output, paths):
    candidate = Path(output).expanduser().resolve()
    roots = [paths.storage, paths.temp]
    roots += [paths.data_dir/name for name in ('avatars','validation_artifacts','delivery_inbox','delivery_receipts')]
    return any(candidate == root.resolve() or root.resolve() in candidate.parents for root in roots)


def require_external_output(output, paths):
    if is_internal_output(output, paths):
        raise ValueError('Escolha uma pasta fora do armazenamento interno do SmartFile para salvar a cópia.')
