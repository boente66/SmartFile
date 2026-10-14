import json

from app.repositories.base_repository import BaseRepository


class OrganizationIdentityRepository(BaseRepository):
    def get(self, organization_id, kind='corporate_identity'):
        row = self._fetch_one('SELECT value FROM app_settings WHERE key=?', (f'{kind}:{organization_id}',))
        return json.loads(row['value']) if row and row['value'] else None

    def save(self, organization_id, values, kind='corporate_identity'):
        self._write('INSERT INTO app_settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                    (f'{kind}:{organization_id}', json.dumps(values, ensure_ascii=False)))

    def bind_public_identity(self, organization_id, public_uuid):
        self._write('UPDATE organizations SET public_uuid=? WHERE id=?', (public_uuid, organization_id))
