from pathlib import Path

from app.models.physical_storage_usage import PhysicalStorageUsage
from app.services.canonical_artifact_service import CanonicalArtifactService


class PhysicalStorageService:
    """Informação física separada da quota, incluindo artefatos históricos e órfãos."""
    def __init__(self,database):self.database=database

    @staticmethod
    def _sum(paths,root,cancelled=None):
        seen=set();size=0;root=Path(root).resolve()
        for value in paths:
            if cancelled and cancelled():raise InterruptedError("Cálculo cancelado.")
            if not value:continue
            path=Path(value)
            try:
                if path.is_symlink():continue
                path=path.resolve(strict=True)
                if root not in path.parents or not path.is_file():continue
                stat=path.stat();key=(stat.st_dev,stat.st_ino)
                if key not in seen:size+=stat.st_size;seen.add(key)
            except OSError:continue
        return size

    def for_organization(self,organization_id,*,cancelled=None):
        paths=self.database.paths
        documents=self.database.fetch_all('SELECT storage_path FROM documents WHERE organization_id=? AND managed=1',(organization_id,))
        validations=self.database.fetch_all('SELECT artifact_storage_ref FROM validation_records WHERE organization_id=?',(organization_id,))
        receipts=self.database.fetch_all('SELECT pdf_path FROM delivery_acknowledgement_receipts WHERE organization_id=?',(organization_id,))
        inbox=self.database.fetch_all('SELECT i.received_path FROM document_delivery_items i JOIN document_deliveries d ON d.id=i.delivery_id WHERE d.organization_id=?',(organization_id,))
        artifacts=CanonicalArtifactService(paths)
        refs=[]
        for row in validations:
            if row[0]:
                try:refs.append(artifacts.path(organization_id,row[0]))
                except ValueError:continue
        roots=[paths.storage,paths.data_dir/'validation_artifacts',paths.data_dir/'delivery_receipts',paths.data_dir/'delivery_inbox']
        total=sum(self._sum(root.rglob('*') if root.is_dir() else (),root,cancelled) for root in roots)
        return PhysicalStorageUsage(self._sum((r[0] for r in documents),roots[0],cancelled),self._sum(refs,roots[1],cancelled),
            self._sum((r[0] for r in receipts),roots[2],cancelled),self._sum((r[0] for r in inbox),roots[3],cancelled),total)
