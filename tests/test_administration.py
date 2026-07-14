from pathlib import Path

import pytest
from PIL import Image

from app.auth.session_context import SessionContext
from app.database.database import Database
from app.errors.auth_exceptions import AdministrationError, LastOwnerError, MembershipError, AvatarError
from app.models.registration_request import RegistrationRequest
from app.services.auth_service import AuthService
from app.services.member_service import MemberService
from app.services.organization_admin_service import OrganizationAdminService
from app.services.profile_service import ProfileService


def request(name="Pessoa",username="pessoa",organization="Empresa ABC",template="BUSINESS"):
    return RegistrationRequest(display_name=name,username=username,email=f"{username}@example.com",password="senha-segura",password_confirmation="senha-segura",template_code=template,organization_name=organization,organization_description="Organização de teste",organization_color="#16a34a")


def build_services(tmp_path):
    database=Database(str(tmp_path/"smartfile.db")); context=SessionContext(); auth=AuthService(database,context); auth.register_first_user(request()); return database,context,auth


def test_custom_organization_and_administration_migration(tmp_path):
    database,context,_=build_services(tmp_path)
    assert context.active_organization.name=="Empresa ABC"
    assert database.connect().execute("PRAGMA user_version").fetchone()[0]==9
    assert {r["name"] for r in database.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")} >= {"audit_log","organization_members"}
    assert len(database.fetch_all("SELECT * FROM folders WHERE organization_id=?",(context.active_organization.id,)))==8


def test_create_edit_duplicate_and_archive_organization(tmp_path):
    database,context,_=build_services(tmp_path); service=OrganizationAdminService(database,context); source=context.active_organization
    second=service.create("Faculdade","Estudos",template="STUDENT")
    assert len(service.folders.list_folders(second.id))==6
    service.update(second.id,"Faculdade Atualizada","Nova descrição",color="#7c3aed")
    duplicate=service.duplicate(second.id,"Faculdade Cópia")
    assert len(service.folders.list_folders(duplicate.id))==6
    assert service.organizations.repository.count_documents(duplicate.id)==0
    assert service.members.count_active(duplicate.id)==1
    cloud=database.fetch_one("SELECT * FROM cloud_settings WHERE organization_id=?",(duplicate.id,))
    assert cloud["sync_mode"]=="LOCAL" and cloud["cloud_account_id"] is None
    service.archive(second.id,"Faculdade Atualizada")
    assert service.organizations.repository.find_by_id(second.id).archived_at is not None
    assert service.organizations.repository.count_documents(source.id)==0
    actions={row.action for row in service.audit.list_for_organization(second.id)}
    assert {"ORGANIZATION_CREATED","ORGANIZATION_UPDATED","ORGANIZATION_ARCHIVED"} <= actions


def test_archive_requires_exact_name_and_another_active_organization(tmp_path):
    database,context,_=build_services(tmp_path); service=OrganizationAdminService(database,context)
    with pytest.raises(AdministrationError): service.archive(context.active_organization.id,"errado")
    with pytest.raises(AdministrationError): service.archive(context.active_organization.id,"Empresa ABC")


def test_members_roles_last_owner_and_transfer(tmp_path):
    database,context,_=build_services(tmp_path); members=MemberService(database,context); organization_id=context.active_organization.id
    with pytest.raises(LastOwnerError): members.change_role(organization_id,context.current_user.id,"ADMIN")
    user,membership=members.create_user(organization_id,"Leitor","leitor","senha-temporaria",role="VIEWER")
    assert user.must_change_password and membership.role=="VIEWER"
    members.change_role(organization_id,user.id,"EDITOR")
    with pytest.raises(MembershipError): members.change_role(organization_id,user.id,"OWNER")
    with pytest.raises(MembershipError): members.transfer_ownership(organization_id,user.id,"incorreta")
    members.transfer_ownership(organization_id,user.id,"senha-segura")
    assert members.members.find(organization_id,user.id).role=="OWNER"
    assert members.members.find(organization_id,context.current_user.id).role=="ADMIN"
    assert context.has_permission("organization.transfer_ownership") is False
    with pytest.raises(MembershipError): members.change_role(organization_id,user.id,"VIEWER")


def test_add_existing_duplicate_deactivate_reactivate_and_remove(tmp_path):
    database,context,_=build_services(tmp_path); members=MemberService(database,context); oid=context.active_organization.id
    user,_=members.create_user(oid,"Editor","editor","senha-temporaria",role="EDITOR")
    with pytest.raises(MembershipError): members.add_existing(oid,"editor","VIEWER")
    members.deactivate(oid,user.id); assert members.members.find(oid,user.id).status=="INACTIVE"
    members.reactivate(oid,user.id); assert members.members.find(oid,user.id).status=="ACTIVE"
    members.remove(oid,user.id); assert members.members.find(oid,user.id).status=="REMOVED"


def test_profile_validates_avatar_and_updates_session_user(tmp_path):
    database,context,_=build_services(tmp_path); profile=ProfileService(database,context); avatar=tmp_path/"avatar.png"; Image.new("RGB",(128,128),"green").save(avatar)
    updated=profile.update("Pessoa Atualizada","novo@example.com","11999999999",str(avatar))
    assert updated.display_name=="Pessoa Atualizada" and Path(updated.avatar_path).is_file()
    invalid=tmp_path/"avatar.txt"; invalid.write_text("não é imagem")
    with pytest.raises(AvatarError): profile.update("Pessoa Atualizada",avatar_source=str(invalid))


def test_create_organization_rolls_back_on_template_failure(tmp_path,monkeypatch):
    database,context,_=build_services(tmp_path); service=OrganizationAdminService(database,context); before=database.fetch_one("SELECT COUNT(*) total FROM organizations")["total"]
    monkeypatch.setattr(service.templates,"create_template_folders",lambda *_:(_ for _ in ()).throw(RuntimeError("falha")))
    with pytest.raises(RuntimeError): service.create("Falha",template="PERSONAL")
    assert database.fetch_one("SELECT COUNT(*) total FROM organizations")["total"]==before
