from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.auth.session_context import SessionContext
from app.cloud.cloud_models import RemoteItemType,RemoteMetadata
from app.database.database import Database
from app.models.registration_request import RegistrationRequest
from app.services.auth_service import AuthService
from app.services.multicloud_reconciliation_service import MulticloudReconciliationService
from app.services.organization_feature_service import OrganizationFeatureService
from app.services.remote_inventory_service import RemoteInventoryService
from app.services.document_delivery_service import DocumentDeliveryService
from app.views.sidebar_view import SidebarView
from PyQt6.QtWidgets import QApplication


class FakeProvider:
    def __init__(self,root_name,tree):self.root_name=root_name;self.tree=tree;self.writes=[]
    def get_metadata(self,remote_id):
        return RemoteMetadata(remote_id,self.root_name,item_type=RemoteItemType.FOLDER)
    def list_children(self,parent_id=None):return list(self.tree.get(parent_id,[]))
    def download(self,remote_id,destination):destination.write_bytes(b"same-content");return destination
    def upload(self,request):
        self.writes.append((request.remote_name,request.remote_parent_id))
        return RemoteMetadata("uploaded",request.remote_name,size=request.local_path.stat().st_size,item_type=RemoteItemType.FILE)


class FakeCloudManager:
    def __init__(self,accounts,providers):self.accounts=accounts;self.providers=providers
    def account(self,account_id,organization_id):
        value=self.accounts[account_id]
        if value.organization_id!=organization_id:raise PermissionError("Conta de outra organização")
        return value
    def provider_for_account(self,organization_id,account_id,**_):
        self.account(account_id,organization_id);return self.providers[account_id]


def setup_personal(tmp_path):
    database=Database(str(tmp_path/"smartfile.db"));context=SessionContext()
    AuthService(database,context).register_first_user(RegistrationRequest(
        display_name="Pessoa",username="pessoa",email="pessoa@example.com",
        password="Senha#Segura1",password_confirmation="Senha#Segura1",
        template_code="PERSONAL",organization_name="Casa",
    ))
    org=context.active_organization;now=datetime.now(timezone.utc).isoformat()
    ids=[]
    for provider in ("ONEDRIVE","GOOGLE_DRIVE"):
        cursor=database.execute_query(
            """INSERT INTO cloud_accounts
               (organization_id,provider,email,display_name,access_token,refresh_token,
                status,created_at) VALUES (?,?,?,?,?,?,?,?)""",
            (org.id,provider,f"{provider}@example.com",provider,"TOKEN_STORE","TOKEN_STORE","ACTIVE",now),
        );ids.append(cursor.lastrowid)
    accounts={item:SimpleNamespace(id=item,organization_id=org.id,provider=provider)
              for item,provider in zip(ids,("ONEDRIVE","GOOGLE_DRIVE"))}
    return database,context,accounts,ids


def file(remote_id,name,hash_value,size=12):
    return RemoteMetadata(remote_id,name,size=size,item_type=RemoteItemType.FILE,
                          provider_hash=hash_value)


def test_profile_matrix_excludes_business_and_multicloud(tmp_path):
    policy=OrganizationFeatureService()
    assert policy.for_profile("PERSONAL").has("multicloud_workspace")
    assert policy.for_profile("STUDENT").has("multicloud_workspace")
    assert not policy.for_profile("BUSINESS").has("multicloud_workspace")
    assert not policy.for_profile("EMPTY").has("multicloud_workspace")
    assert not policy.for_profile("PERSONAL").has("document_requests")


def test_non_business_hides_delivery_route_and_service_rejects_it(tmp_path):
    database,context,_accounts,_ids=setup_personal(tmp_path)
    app=QApplication.instance() or QApplication([])
    sidebar=SidebarView();features=OrganizationFeatureService(database).for_organization(
        context.active_organization
    );sidebar.apply_profile_features(features)
    assert sidebar._buttons["deliveries"].isHidden()
    with pytest.raises(PermissionError):
        DocumentDeliveryService(database,context)._require(
            context.active_organization.id,"delivery.view"
        )
    sidebar.close();assert app is not None


def test_mount_and_scan_are_metadata_only_and_merge_verified_replicas(tmp_path):
    database,context,accounts,ids=setup_personal(tmp_path)
    providers={
        ids[0]:FakeProvider("Arquivo A",{"root-a":[file("a1","prova.pdf","sha")]}),
        ids[1]:FakeProvider("Arquivo B",{"root-b":[file("b1","prova.pdf","sha")]}),
    }
    service=RemoteInventoryService(database,FakeCloudManager(accounts,providers),context)
    first=service.mount(context.active_organization.id,ids[0],"ONEDRIVE","root-a","A","A",collection_key="estudos")
    second=service.mount(context.active_organization.id,ids[1],"GOOGLE_DRIVE","root-b","B","B",collection_key="estudos")
    before=database.fetch_one("SELECT COUNT(*) total FROM documents")["total"]
    assert service.scan(context.active_organization.id,first.id)==1
    assert service.scan(context.active_organization.id,second.id)==1
    after=database.fetch_one("SELECT COUNT(*) total FROM documents")["total"]
    logical=service.logical.objects(context.active_organization.id,"estudos")
    assert before==after==0
    assert len(logical)==1 and logical[0].identity_state=="VERIFIED_MATCH"
    assert providers[ids[0]].writes==providers[ids[1]].writes==[]
    assert service.unmount(context.active_organization.id,first.id)
    assert providers[ids[0]].writes==[]


def test_same_name_with_different_hash_is_diverged(tmp_path):
    database,context,accounts,ids=setup_personal(tmp_path)
    providers={ids[0]:FakeProvider("A",{"a":[file("a1","igual.pdf","one")]}),
               ids[1]:FakeProvider("B",{"b":[file("b1","igual.pdf","two")]})}
    service=RemoteInventoryService(database,FakeCloudManager(accounts,providers),context)
    for account_id,provider,root in ((ids[0],"ONEDRIVE","a"),(ids[1],"GOOGLE_DRIVE","b")):
        mount=service.mount(context.active_organization.id,account_id,provider,root,root,root,collection_key="c")
        service.scan(context.active_organization.id,mount.id)
    assert service.logical.objects(context.active_organization.id,"c")[0].identity_state=="DIVERGED"


def test_plan_never_executes_before_explicit_authorization(tmp_path):
    database,context,accounts,ids=setup_personal(tmp_path)
    providers={ids[0]:FakeProvider("A",{"a":[file("a1","only.pdf","one")]}),
               ids[1]:FakeProvider("B",{"b":[]})}
    manager=FakeCloudManager(accounts,providers)
    inventory=RemoteInventoryService(database,manager,context)
    mounts=[]
    for account_id,provider,root in ((ids[0],"ONEDRIVE","a"),(ids[1],"GOOGLE_DRIVE","b")):
        mount=inventory.mount(context.active_organization.id,account_id,provider,root,root,root,collection_key="c")
        inventory.scan(context.active_organization.id,mount.id);mounts.append(mount)
    reconcile=MulticloudReconciliationService(database,manager,context)
    plan,actions=reconcile.build_plan(context.active_organization.id,"c")
    assert len(actions)==1 and providers[ids[1]].writes==[]
    with pytest.raises(Exception):reconcile.execute(context.active_organization.id,plan.id)
    reconcile.authorize(context.active_organization.id,plan.id,[actions[0].id])
    assert reconcile.execute(context.active_organization.id,plan.id)=="COMPLETED"
    assert providers[ids[1]].writes==[("only.pdf","b")]
    assert not list(database.temp_dir.glob("multicloud-*.part"))


def test_schema_21_upgrades_only_to_22_without_reapplying_cloud_migration(tmp_path):
    path=tmp_path/"upgrade.db";database=Database(str(path))
    database.execute_query("PRAGMA user_version=21");database.close()
    migrated=Database(str(path))
    assert migrated.fetch_one("PRAGMA user_version")[0]==22
    assert migrated.fetch_one("SELECT 1 FROM sqlite_master WHERE name='remote_mounts'")
