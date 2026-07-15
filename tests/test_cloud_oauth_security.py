import json
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from app.auth.session_context import SessionContext
from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_models import (
    CloudAuthResult,
    CloudConfigurationSource,
    CloudOAuthState,
)
from app.cloud.cloud_oauth_config_service import CloudOAuthConfigurationService
from app.cloud.token_store import CloudTokenStore
from app.database.database import Database
from app.errors.cloud_exceptions import CloudPermissionError
from app.views.document_view import DocumentView
from app.controllers.document_controller import DocumentController


def _google_config(client_id="google-client"):
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": "public-desktop-value",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def test_configuration_priority_bundled_environment_admin_development(tmp_path, monkeypatch):
    database = Database(str(tmp_path / "smartfile.db"))
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / "onedrive.json").write_text(json.dumps({"client_id": "bundled", "tenant": "common"}))
    service = CloudOAuthConfigurationService(database, bundled)
    service.save_onedrive("admin", "organizations")
    monkeypatch.setenv("SMARTFILE_ONEDRIVE_CLIENT_ID", "environment")
    monkeypatch.setenv("SMARTFILE_DEV_ONEDRIVE_CLIENT_ID", "development")

    assert service.get_onedrive_config()["client_id"] == "bundled"
    assert service.config_source("ONEDRIVE") == CloudConfigurationSource.BUNDLED

    (bundled / "onedrive.json").unlink()
    assert service.get_onedrive_config()["client_id"] == "environment"
    assert service.config_source("ONEDRIVE") == CloudConfigurationSource.ENVIRONMENT

    monkeypatch.delenv("SMARTFILE_ONEDRIVE_CLIENT_ID")
    assert service.get_onedrive_config()["client_id"] == "admin"
    assert service.config_source("ONEDRIVE") == CloudConfigurationSource.ADMIN_LOCAL


def test_google_environment_and_missing_configuration(tmp_path, monkeypatch):
    database = Database(str(tmp_path / "smartfile.db"))
    service = CloudOAuthConfigurationService(database, tmp_path / "missing")
    assert not service.is_provider_configured("GOOGLE_DRIVE")
    assert service.config_source("GOOGLE_DRIVE") == CloudConfigurationSource.MISSING
    monkeypatch.setenv("SMARTFILE_GOOGLE_DRIVE_CLIENT_CONFIG", json.dumps(_google_config()))
    assert service.is_provider_configured("GOOGLE_DRIVE")
    assert service.config_source("GOOGLE_DRIVE") == CloudConfigurationSource.ENVIRONMENT


def test_token_store_leaves_only_reference_in_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(CloudTokenStore, "_keyring_set", classmethod(lambda cls, ref, payload: False))
    monkeypatch.setattr(CloudTokenStore, "_keyring_get", classmethod(lambda cls, ref: None))
    database = Database(str(tmp_path / "smartfile.db"))
    manager = CloudManager(database)
    organization_id = database.fetch_one("SELECT id FROM organizations LIMIT 1")["id"]
    account = manager.save_authentication_result(
        organization_id,
        "ONEDRIVE",
        CloudAuthResult(access_token="access-secret", refresh_token="refresh-secret"),
    )
    row = database.fetch_one("SELECT access_token,refresh_token,token_ref FROM cloud_accounts WHERE id=?", (account.id,))
    serialized = " ".join(str(value) for value in row)
    assert "access-secret" not in serialized and "refresh-secret" not in serialized
    assert row["token_ref"].startswith("cloud:")
    assert manager.account(account.id).access_token == "access-secret"
    fallback = (database.data_dir / ".cloud_token_store").read_text()
    assert "access-secret" not in fallback and "refresh-secret" not in fallback


def test_cloud_permissions_are_enforced_in_service(tmp_path):
    database = Database(str(tmp_path / "smartfile.db"))
    context = SessionContext()
    context.permissions = {"cloud.view"}
    manager = CloudManager(database, session_context=context)
    organization_id = database.fetch_one("SELECT id FROM organizations LIMIT 1")["id"]
    with pytest.raises(CloudPermissionError):
        manager.save_authentication_result(
            organization_id, "ONEDRIVE", CloudAuthResult(access_token="not-saved")
        )


def test_common_user_never_sees_technical_oauth_action():
    app = QApplication.instance() or QApplication([])
    view = DocumentView()
    common = SessionContext()
    from app.models.user_model import UserModel
    common.current_user = UserModel(1,"comum",None,"Comum",None,True,False,None)
    common.permissions = {"cloud.view", "cloud.connect"}
    view.apply_cloud_permissions(common)
    assert not view.oauth_settings_action.isVisible()
    assert view.btn_configure_provider.isHidden()
    common.current_user = UserModel(2,"admin",None,"Administrador",None,True,True,None)
    view.apply_cloud_permissions(common)
    assert view.oauth_settings_action.isVisible()
    assert not view.btn_configure_provider.isHidden()
    view.close()
    app.processEvents()


def test_all_required_oauth_states_are_explicit():
    assert {state.value for state in CloudOAuthState} == {
        "NOT_CONFIGURED", "DISCONNECTED", "AUTHENTICATING", "CONNECTED",
        "TOKEN_EXPIRED", "REAUTH_REQUIRED", "ERROR", "DISABLED",
    }


def test_common_connection_flow_does_not_open_technical_dialog():
    source = inspect.getsource(DocumentController.on_add_cloud_account)
    assert "CloudApiSettingsDialog" not in source
    assert "CloudConfigurationMissingError" in source


def test_msal_cache_is_kept_out_of_oauth_configuration_file(tmp_path, monkeypatch):
    monkeypatch.setattr(CloudTokenStore, "_keyring_set", classmethod(lambda cls, ref, payload: False))
    monkeypatch.setattr(CloudTokenStore, "_keyring_get", classmethod(lambda cls, ref: None))
    database = Database(str(tmp_path / "smartfile.db"))
    service = CloudOAuthConfigurationService(database)
    service.save_cache("ONEDRIVE", "serialized-msal-secret")
    assert service.load_cache("ONEDRIVE") == "serialized-msal-secret"
    encrypted_config = service.path.read_text(encoding="utf-8")
    assert "serialized-msal-secret" not in encrypted_config
    assert "serialized-msal-secret" not in (database.data_dir / ".cloud_token_store").read_text()


def test_oauth_cache_can_be_removed_without_deleting_public_provider_config(tmp_path, monkeypatch):
    database = Database(str(tmp_path / "smartfile.db")); service = CloudOAuthConfigurationService(database)
    service.save_onedrive("public-client-id", "common")
    service.save_cache("ONEDRIVE", "private-cache")
    service.delete_cache("ONEDRIVE")
    assert service.load_cache("ONEDRIVE") is None
    assert service.get_onedrive_config()["client_id"] == "public-client-id"


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("NOT_CONFIGURED", "não configurada"),
        ("DISCONNECTED", "Armazenamento local"),
        ("AUTHENTICATING", "Autenticando"),
        ("CONNECTED", "Conta Real"),
        ("TOKEN_EXPIRED", "expirada"),
        ("REAUTH_REQUIRED", "autenticação necessária"),
        ("ERROR", "Erro na conexão"),
        ("DISABLED", "indisponível para este perfil"),
    ],
)
def test_every_oauth_state_has_a_clear_interface_message(state, expected):
    app = QApplication.instance() or QApplication([])
    view = DocumentView()
    settings = SimpleNamespace(sync_mode="ONEDRIVE" if state == "CONNECTED" else "LOCAL", paused=False, last_sync=None)
    account = SimpleNamespace(display_name="Conta Real", email="real@example.test") if state == "CONNECTED" else None
    view.set_cloud_settings(settings, account, state)
    assert expected in view.cloud_status_label.text()
    view.close(); app.processEvents()
