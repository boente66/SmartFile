import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.cloud.token_store import CloudTokenStore


@pytest.fixture(autouse=True)
def isolate_cloud_keyring(monkeypatch):
    """Impede que tokens fictícios dos testes alcancem o keyring real do usuário."""
    monkeypatch.setattr(
        CloudTokenStore, "_keyring_set",
        classmethod(lambda cls, reference, payload: False),
    )
    monkeypatch.setattr(
        CloudTokenStore, "_keyring_get",
        classmethod(lambda cls, reference: None),
    )
    monkeypatch.setattr(
        CloudTokenStore, "_keyring_delete",
        classmethod(lambda cls, reference: None),
    )
