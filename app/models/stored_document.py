from dataclasses import dataclass


@dataclass(frozen=True)
class StoredDocument:
    internal_name: str
    storage_path: str
    relative_path: str
    size: int
