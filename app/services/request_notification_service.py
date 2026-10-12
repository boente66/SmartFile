"""Persistent, user/organization-scoped reading state independent of request status."""
import json
from app.repositories.base_repository import BaseRepository


class RequestNotificationService:
    def __init__(self, database):
        self.repository = BaseRepository(database=database)
        self.scope = None
        self.known = set()
        self.unread = set()
        self.sound = True
        self.animation = True

    def _key(self):
        return f"requests.notifications.{self.scope[0]}.{self.scope[1]}"

    def activate(self, organization_id, user_id, requests):
        self.scope = (organization_id,user_id)
        row = self.repository._fetch_one("SELECT value FROM app_settings WHERE key=?",(self._key(),))
        data = json.loads(row["value"]) if row else {}
        current = {r.id for r in requests if r.organization_id == organization_id and r.assigned_to_user_id == user_id and r.requested_by_user_id != user_id}
        self.known = set(data.get("known",current))
        self.unread = set(data.get("unread",current))
        self.sound = data.get("sound",True)
        self.animation = data.get("animation",True)
        self._save()

    def observe(self, organization_id, user_id, requests):
        if self.scope != (organization_id,user_id):
            self.activate(organization_id,user_id,requests)
            return set()
        current = {r.id for r in requests if r.organization_id == organization_id
                   and r.assigned_to_user_id == user_id and r.requested_by_user_id != user_id}
        new = current-self.known
        self.known |= current
        self.unread |= new
        if new:self._save()
        return new

    def mark_read(self, request_id):
        if request_id in self.unread:
            self.unread.discard(request_id);self._save()

    def preferences(self, sound, animation):
        self.sound,self.animation = sound,animation
        self._save()

    def _save(self):
        if self.scope is None:return
        self.repository._write("INSERT INTO app_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (self._key(),json.dumps({"known":sorted(self.known),"unread":sorted(self.unread),"sound":self.sound,"animation":self.animation})))


def request_stage(status):
    return {"OPEN":0,"IN_PROGRESS":1,"OVERDUE":1,"ATTENDED":2,"DELIVERING":3,"DELIVERED":3,"COMPLETED":4,"CANCELLED":4}.get(status,0)
