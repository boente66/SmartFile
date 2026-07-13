from datetime import datetime, timezone
from pathlib import Path

from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_models import CloudAuthResult
from app.cloud.cloud_oauth_config_service import CloudOAuthConfigService
from app.cloud.cloud_python_auth_service import CloudPythonAuthService
from app.database.database import Database


def test_oauth_configuration_is_encrypted_and_supports_both_providers(tmp_path: Path):
    database=Database(str(tmp_path/"smartfile.db")); service=CloudOAuthConfigService(database)
    service.save_onedrive("microsoft-client-id","common")
    google=tmp_path/"client_secret.json"; google.write_text('{"installed":{"client_id":"google-client-id","client_secret":"desktop-secret","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","redirect_uris":["http://localhost"]}}')
    service.save_google_client_file(str(google))
    assert service.is_configured("ONEDRIVE") and service.is_configured("GOOGLE_DRIVE")
    raw=(database.data_dir/".cloud_oauth_config").read_text()
    assert "microsoft-client-id" not in raw and "desktop-secret" not in raw


def test_msal_interactive_flow_is_used(tmp_path: Path,monkeypatch):
    database=Database(str(tmp_path/"smartfile.db")); config=CloudOAuthConfigService(database); config.save_onedrive("client-id","organizations")
    captured={}
    class Application:
        def __init__(self,client_id,authority,token_cache=None): captured.update(client_id=client_id,authority=authority,token_cache=token_cache)
        def get_accounts(self): return []
        def acquire_token_silent(self,*_args,**_kwargs): return None
        def acquire_token_interactive(self,**kwargs): captured.update(kwargs); return {"access_token":"access","refresh_token":"refresh","expires_in":3600,"id_token_claims":{"preferred_username":"user@example.com","name":"Pessoa"}}
    import msal
    monkeypatch.setattr(msal,"PublicClientApplication",Application)
    result=CloudPythonAuthService(database).authenticate("ONEDRIVE")
    assert result.access_token=="access" and result.email=="user@example.com"
    assert captured["client_id"]=="client-id" and captured["redirect_uri"]=="http://localhost"


def test_google_installed_app_local_server_flow_is_used(tmp_path: Path,monkeypatch):
    database=Database(str(tmp_path/"smartfile.db")); config=CloudOAuthConfigService(database); google=tmp_path/"google.json"; google.write_text('{"installed":{"client_id":"google-id","client_secret":"secret","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","redirect_uris":["http://localhost"]}}'); config.save_google_client_file(str(google)); captured={}
    class Credentials:
        token="google-access"; refresh_token="google-refresh"; expiry=datetime.now(timezone.utc)
    class Flow:
        def run_local_server(self,**kwargs): captured.update(kwargs); return Credentials()
    from google_auth_oauthlib.flow import InstalledAppFlow
    monkeypatch.setattr(InstalledAppFlow,"from_client_config",lambda client_config,scopes:(captured.update(client_config=client_config,scopes=scopes) or Flow()))
    service=CloudPythonAuthService(database); monkeypatch.setattr(service,"_google_profile",lambda _token:{"email":"google@example.com","name":"Google User"})
    result=service.authenticate("GOOGLE_DRIVE")
    assert result.access_token=="google-access" and result.email=="google@example.com"
    assert captured["open_browser"] is True and captured["port"]==0


def test_python_auth_result_is_saved_encrypted_and_activates_provider(tmp_path: Path):
    database=Database(str(tmp_path/"smartfile.db")); manager=CloudManager(database); organization_id=manager.database.fetch_one("SELECT id FROM organizations LIMIT 1")["id"]
    account=manager.save_authentication_result(organization_id,"ONEDRIVE",CloudAuthResult(access_token="secret-access",refresh_token="secret-refresh",expires_at=datetime.now(timezone.utc),email="user@example.com"))
    stored=database.fetch_one("SELECT * FROM cloud_accounts WHERE id=?",(account.id,)); settings=manager.settings(organization_id)
    assert "secret-access" not in stored["access_token"] and "secret-refresh" not in stored["refresh_token"]
    assert settings.sync_mode=="ONEDRIVE" and settings.cloud_account_id==account.id
