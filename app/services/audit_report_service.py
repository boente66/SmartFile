from dataclasses import fields
import base64
import csv
from pathlib import Path

import fitz

from app.entities.audit_log_entity import AuditLogEntity
from app.services.audit_service import AuditService
from app.services.organization_identity_service import OrganizationIdentityService
from app.utils.atomic_output import atomic_output


class AuditReportService:
    def __init__(self, database, context):
        self.audit = AuditService(database, context)
        self.identity = OrganizationIdentityService(database, context)

    @staticmethod
    def _cell(value):
        text = str(value) if value is not None else ''
        return "'" + text if text.lstrip().startswith(('=','+','-','@')) else text

    def export(self, organization_id, destination, kind, filters=None):
        self.identity._admin(organization_id)
        rows = self.audit.list_for_organization(organization_id, 5000, **(filters or {}))
        identity = self.identity.get(organization_id)
        columns = tuple(field.name for field in fields(AuditLogEntity))
        with atomic_output(Path(destination)) as temporary:
            if kind == 'CSV':
                with temporary.open('w',encoding='utf-8-sig',newline='') as output:
                    writer=csv.writer(output)
                    writer.writerow(columns)
                    for row in rows:writer.writerow([self._cell(getattr(row,k)) for k in columns])
            elif kind == 'PDF':
                document=fitz.open()
                font = fitz.Font("cjk")
                def new_page():
                    page = document.new_page(width=595, height=842)
                    page.insert_font(fontname="audit_unicode", fontbuffer=font.buffer)
                    return page
                try:
                    page=None;y=0
                    for row in rows or [None]:
                        if page is None or y>680:
                            page=new_page()
                            background=tuple(int(identity.header_color[i:i+2],16)/255 for i in (1,3,5))
                            foreground=tuple(int(identity.foreground(identity.header_color)[i:i+2],16)/255 for i in (1,3,5))
                            page.draw_rect(fitz.Rect(36,28,559,110),color=background,fill=background)
                            if identity.logo:page.insert_image(fitz.Rect(44,37,94,87),stream=base64.b64decode(identity.logo),keep_proportion=True)
                            x=104 if identity.logo else 44
                            page.insert_textbox(fitz.Rect(x,35,548,72),identity.title()+'\n'+identity.unit,fontsize=11,color=foreground,fontname="audit_unicode")
                            page.insert_text((44,98),'SmartFile — Relatório administrativo de auditoria',fontsize=9,color=foreground,fontname="audit_unicode")
                            y=134
                        if row is None:
                            page.insert_text((36,y),'Nenhum evento no período.',fontsize=10,fontname="audit_unicode")
                            break
                        text='\n'.join(f'{key}: {getattr(row,key) if getattr(row,key) is not None else "—"}' for key in columns if key!='id')
                        # Each event occupies its own page when it would not fit; never silently truncate evidence.
                        needed=max(90,len(text.splitlines())*11+len(text)//100*10)
                        if y+needed>780:
                            page=new_page();y=42
                        box=fitz.Rect(36,y,559,780)
                        size=8
                        result=page.insert_textbox(box,text,fontsize=size,fontname="audit_unicode")
                        if result<0:
                            raise ValueError('O evento excede o espaço do relatório PDF. Use CSV para preservar toda a evidência.')
                        y=780-result+22
                    for index,page in enumerate(document,1):
                        page.insert_text((36,820),f'SmartFile · Página {index}/{document.page_count} · Eventos somente para leitura',fontsize=7,fontname="audit_unicode")
                    document.save(temporary,deflate=True)
                finally:
                    document.close()
            else:
                raise ValueError('Formato de relatório inválido.')
        self.audit.record('AUDIT_REPORT_EXPORTED',organization_id=organization_id,
            target_type='audit_report',details={'format':kind,'events':len(rows)})
        return Path(destination)
