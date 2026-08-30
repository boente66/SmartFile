from __future__ import annotations

from app.entities.multicloud_entity import (
    CloudReplicaEntity,
    LogicalCloudObjectEntity,
    MulticloudPlanActionEntity,
    MulticloudPlanEntity,
    RemoteCatalogNodeEntity,
    RemoteMountEntity,
)
from app.repositories.base_repository import BaseRepository


class RemoteMountRepository(BaseRepository):
    def create(self, value: RemoteMountEntity) -> RemoteMountEntity:
        cursor = self._write(
            """INSERT INTO remote_mounts
               (organization_id,cloud_account_id,provider,remote_root_id,
                remote_root_name,logical_mount_name,collection_key,status,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (value.organization_id,value.cloud_account_id,value.provider,
             value.remote_root_id,value.remote_root_name,value.logical_mount_name,
             value.collection_key,value.status,value.created_at),
        )
        value.id = cursor.lastrowid
        return value

    def find(self, mount_id: int, organization_id: int) -> RemoteMountEntity | None:
        row = self._fetch_one(
            "SELECT * FROM remote_mounts WHERE id=? AND organization_id=?",
            (mount_id, organization_id),
        )
        return self._mount(row) if row else None

    def list_for_organization(self, organization_id: int) -> list[RemoteMountEntity]:
        return [self._mount(row) for row in self._fetch_all(
            "SELECT * FROM remote_mounts WHERE organization_id=? ORDER BY logical_mount_name,id",
            (organization_id,),
        )]

    def set_status(self, mount_id: int, organization_id: int, status: str,
                   *, scanned_at: str | None = None, error: str | None = None) -> None:
        self._write(
            """UPDATE remote_mounts SET status=?,last_scan_at=COALESCE(?,last_scan_at),
               last_error=? WHERE id=? AND organization_id=?""",
            (status,scanned_at,error,mount_id,organization_id),
        )

    def unmount(self, mount_id: int, organization_id: int) -> bool:
        # CASCADE remove apenas o espelho local. Nenhum provider é chamado.
        with self.database.transaction() as connection:
            cursor=connection.execute(
                "DELETE FROM remote_mounts WHERE id=? AND organization_id=?",
                (mount_id,organization_id),
            )
            connection.execute(
                """DELETE FROM logical_cloud_objects WHERE organization_id=?
                   AND NOT EXISTS (SELECT 1 FROM cloud_replicas r
                                   WHERE r.logical_object_id=logical_cloud_objects.id)""",
                (organization_id,),
            )
            return cursor.rowcount>0

    @staticmethod
    def _mount(row) -> RemoteMountEntity:
        return RemoteMountEntity(**{key: row[key] for key in row.keys()})


class RemoteCatalogRepository(BaseRepository):
    def upsert(self, value: RemoteCatalogNodeEntity) -> RemoteCatalogNodeEntity:
        self._write(
            """INSERT INTO remote_catalog_nodes
               (organization_id,mount_id,cloud_account_id,provider,remote_id,
                remote_parent_id,logical_path,node_type,name,mime_type,size,
                modified_at,provider_hash,version,status,discovered_at,last_seen_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(mount_id,remote_id) DO UPDATE SET
                remote_parent_id=excluded.remote_parent_id,
                logical_path=excluded.logical_path,node_type=excluded.node_type,
                name=excluded.name,mime_type=excluded.mime_type,size=excluded.size,
                modified_at=excluded.modified_at,provider_hash=excluded.provider_hash,
                version=excluded.version,status='ACTIVE',last_seen_at=excluded.last_seen_at""",
            (value.organization_id,value.mount_id,value.cloud_account_id,value.provider,
             value.remote_id,value.remote_parent_id,value.logical_path,value.node_type,
             value.name,value.mime_type,value.size,value.modified_at,value.provider_hash,
             value.version,value.status,value.discovered_at,value.last_seen_at),
        )
        row = self._fetch_one(
            "SELECT * FROM remote_catalog_nodes WHERE mount_id=? AND remote_id=?",
            (value.mount_id,value.remote_id),
        )
        return self._node(row)

    def mark_missing_before(self, mount_id: int, scan_started_at: str) -> None:
        self._write(
            """UPDATE remote_catalog_nodes SET status='MISSING'
               WHERE mount_id=? AND last_seen_at<?""",
            (mount_id,scan_started_at),
        )

    def list_for_mount(self, mount_id: int, organization_id: int,
                       *, active_only: bool = True) -> list[RemoteCatalogNodeEntity]:
        suffix = " AND status='ACTIVE'" if active_only else ""
        return [self._node(row) for row in self._fetch_all(
            "SELECT * FROM remote_catalog_nodes WHERE mount_id=? AND organization_id=?"
            + suffix + " ORDER BY logical_path", (mount_id,organization_id),
        )]

    def list_for_collection(self, organization_id: int, collection_key: str):
        return [self._node(row) for row in self._fetch_all(
            """SELECT n.* FROM remote_catalog_nodes n JOIN remote_mounts m ON m.id=n.mount_id
               WHERE n.organization_id=? AND m.collection_key=? AND n.status='ACTIVE'
               ORDER BY n.logical_path,n.mount_id""",
            (organization_id,collection_key),
        )]

    def find_path(self, mount_id: int, organization_id: int, logical_path: str):
        row=self._fetch_one(
            """SELECT * FROM remote_catalog_nodes WHERE mount_id=? AND organization_id=?
               AND logical_path=? AND status='ACTIVE'""",
            (mount_id,organization_id,logical_path),
        )
        return self._node(row) if row else None

    @staticmethod
    def _node(row) -> RemoteCatalogNodeEntity:
        return RemoteCatalogNodeEntity(**{key: row[key] for key in row.keys()})


class LogicalCloudRepository(BaseRepository):
    def rebuild_collection(self, organization_id: int, collection_key: str,
                           nodes: list[RemoteCatalogNodeEntity], now: str) -> None:
        """Reconstrói relações derivadas; o inventário remoto permanece intacto."""
        with self.database.transaction() as connection:
            old = connection.execute(
                "SELECT id FROM logical_cloud_objects WHERE organization_id=? AND collection_key=?",
                (organization_id,collection_key),
            ).fetchall()
            if old:
                marks = ",".join("?" for _ in old)
                connection.execute(
                    f"DELETE FROM cloud_replicas WHERE logical_object_id IN ({marks})",
                    tuple(row["id"] for row in old),
                )
            connection.execute(
                "DELETE FROM logical_cloud_objects WHERE organization_id=? AND collection_key=?",
                (organization_id,collection_key),
            )
            grouped: dict[str,list[RemoteCatalogNodeEntity]] = {}
            for node in nodes:
                grouped.setdefault(node.logical_path, []).append(node)
            for logical_path, replicas in grouped.items():
                state = self._identity(replicas)
                cursor = connection.execute(
                    """INSERT INTO logical_cloud_objects
                       (organization_id,collection_key,logical_path,logical_name,
                        object_type,identity_state,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (organization_id,collection_key,logical_path,replicas[0].name,
                     replicas[0].node_type,state,now,now),
                )
                for replica in replicas:
                    connection.execute(
                        """INSERT INTO cloud_replicas
                           (organization_id,logical_object_id,mount_id,catalog_node_id,
                            cloud_account_id,provider,remote_id,provider_hash,
                            replica_status,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (organization_id,cursor.lastrowid,replica.mount_id,replica.id,
                         replica.cloud_account_id,replica.provider,replica.remote_id,
                         replica.provider_hash,
                         "DIVERGED" if state == "DIVERGED" else "PRESENT",now,now),
                    )

    @staticmethod
    def _identity(values: list[RemoteCatalogNodeEntity]) -> str:
        if len(values) == 1:
            return "UNRELATED"
        hashes = [item.provider_hash for item in values]
        if all(hashes) and len(set(hashes)) == 1:
            return "VERIFIED_MATCH"
        if len({item.node_type for item in values}) > 1:
            return "DIVERGED"
        if all(hashes) and len(set(hashes)) > 1:
            return "DIVERGED"
        if len({item.size for item in values}) > 1:
            return "DIVERGED"
        return "CANDIDATE_MATCH"

    def objects(self, organization_id: int, collection_key: str | None = None):
        query = "SELECT * FROM logical_cloud_objects WHERE organization_id=?"
        params: tuple[object,...] = (organization_id,)
        if collection_key is not None:
            query += " AND collection_key=?"; params += (collection_key,)
        return [LogicalCloudObjectEntity(**{k:r[k] for k in r.keys()})
                for r in self._fetch_all(query+" ORDER BY logical_path",params)]

    def replicas(self, logical_object_id: int, organization_id: int):
        return [CloudReplicaEntity(**{k:r[k] for k in r.keys()}) for r in self._fetch_all(
            "SELECT * FROM cloud_replicas WHERE logical_object_id=? AND organization_id=?",
            (logical_object_id,organization_id),
        )]


class MulticloudPlanRepository(BaseRepository):
    def create_plan(self, plan: MulticloudPlanEntity) -> MulticloudPlanEntity:
        cursor=self._write(
            """INSERT INTO multicloud_plans
               (organization_id,plan_uuid,status,created_at) VALUES (?,?,?,?)""",
            (plan.organization_id,plan.plan_uuid,plan.status,plan.created_at),
        );plan.id=cursor.lastrowid;return plan

    def add_action(self, value: MulticloudPlanActionEntity) -> MulticloudPlanActionEntity:
        cursor=self._write(
            """INSERT OR IGNORE INTO multicloud_plan_actions
               (organization_id,plan_id,action_type,source_replica_id,target_mount_id,
                target_parent_remote_id,logical_object_id,risk_level,reason,status,
                idempotency_key,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (value.organization_id,value.plan_id,value.action_type,value.source_replica_id,
             value.target_mount_id,value.target_parent_remote_id,value.logical_object_id,
             value.risk_level,value.reason,value.status,value.idempotency_key,value.created_at),
        );value.id=cursor.lastrowid or None;return value

    def actions(self, plan_id: int, organization_id: int):
        return [MulticloudPlanActionEntity(**{k:r[k] for k in r.keys()})
                for r in self._fetch_all(
                    "SELECT * FROM multicloud_plan_actions WHERE plan_id=? AND organization_id=? ORDER BY id",
                    (plan_id,organization_id),
                )]

    def find_plan(self, plan_id: int, organization_id: int):
        row=self._fetch_one(
            "SELECT * FROM multicloud_plans WHERE id=? AND organization_id=?",
            (plan_id,organization_id),
        )
        return MulticloudPlanEntity(**{k:row[k] for k in row.keys()}) if row else None

    def authorize(self, plan_id: int, organization_id: int, action_ids: list[int],
                  user_id: int, now: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """UPDATE multicloud_plans SET status='AUTHORIZED',authorized_at=?,
                   authorized_by_user_id=? WHERE id=? AND organization_id=? AND status='DRAFT'""",
                (now,user_id,plan_id,organization_id),
            )
            if action_ids:
                marks=",".join("?" for _ in action_ids)
                connection.execute(
                    f"""UPDATE multicloud_plan_actions SET status='AUTHORIZED'
                        WHERE plan_id=? AND organization_id=? AND status='PROPOSED'
                          AND id IN ({marks})""",
                    (plan_id,organization_id,*action_ids),
                )

    def set_plan_status(self, plan_id: int, organization_id: int, status: str,
                        *, completed_at: str | None=None, error: str | None=None) -> None:
        self._write(
            """UPDATE multicloud_plans SET status=?,completed_at=?,last_error=?
               WHERE id=? AND organization_id=?""",
            (status,completed_at,error,plan_id,organization_id),
        )

    def set_action_status(self, action_id: int, organization_id: int, status: str,
                          *, completed_at: str | None=None, error: str | None=None) -> None:
        self._write(
            """UPDATE multicloud_plan_actions SET status=?,completed_at=?,last_error=?
               WHERE id=? AND organization_id=?""",
            (status,completed_at,error,action_id,organization_id),
        )

    def replica_detail(self, replica_id: int, organization_id: int):
        return self._fetch_one(
            """SELECT r.*,o.logical_name,o.logical_path,n.size,n.mime_type
               FROM cloud_replicas r
               JOIN logical_cloud_objects o ON o.id=r.logical_object_id
               JOIN remote_catalog_nodes n ON n.id=r.catalog_node_id
               WHERE r.id=? AND r.organization_id=?""",
            (replica_id,organization_id),
        )
