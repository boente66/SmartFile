# Auditoria empresarial — SmartFile 0.9.0-beta.10

## Referência e escopo

Main atualizada antes das alterações. HEAD inicial:
19d2738b4b8b782c5b4edb74aef4f50b0c2602fc.
Base: 0.9.0-beta.9, schema 23; suíte inicial: 620 testes aprovados.
Entrega: 0.9.0-beta.10, schema 24. Inspeção do código real e regressões locais.
Público informado pela organização: uso empresarial por adultos.

## Lacunas comprovadas e correções

- Audit_log e history anteriores não conservavam todos os snapshots de ator,
  instalação, origem e documento após exclusão. Reutilizados e ampliados, com
  UUID públicos, hashes e triggers de proteção do histórico consolidado.
- Workers e filas não transportavam o escopo individual completo. Agora capturam
  ator e organização antes da execução, conservam esse escopo e rejeitam mistura
  de organizações ou troca indevida do usuário autenticado.
- A seleção de membership podia utilizar o papel de outro usuário quando a lista
  continha associações de vários usuários. A seleção exige usuário autenticado
  e associação ACTIVE.
- Alterações externas de bytes não tinham observação explícita separada de autoria.
  A abertura registra CONTENT_CHANGED_OBSERVED, com hash anterior/novo, sem atribuir
  ao observador a autoria de edição externa desconhecida.
- Conversões com múltiplas saídas passam a registrar cada arquivo publicado.
  Exportação auditada verifica SHA-256 e está acessível no menu contextual.
- Uma falha no upgrade podia deixar alterações parciais com schema ainda 23.
  O upgrade empresarial agora conserva transação e reverte integralmente em falha.
- Consulta QR somente por hash podia esconder outros registros correspondentes.
  Agora retorna todos, exige seleção do registro específico e protege FKs nulas
  contra reassociação. Dados consolidados de revogação são imutáveis. Consultas
  posteriores à exclusão recuperam a identidade documental do histórico preservado;
  artefatos fora do GED recebem identificação pública e nome próprios na auditoria.
- Comprovantes e relatórios não tinham identidade institucional controlada.
  Implementado Modo Design BUSINESS para OWNER/ADMIN, com prévia, imagens raster
  limitadas, contraste mínimo, fallback e cadastro institucional por organização.
- Comprovante de envio preserva evidências sem antecipar confirmação do destinatário.
  Recebimento, confirmação, downloads e acessos são auditados com escopo verificado.
- Armazenamento físico separa GED, artefatos de validação, receipts e inbox sem alterar
  quota. O cálculo físico é cancelável e executado em background. Backup passa a incluir inbox. Senha A1 é limpa também em falha preliminar.

## Casos cobertos

Digitalização e criação de saídas; importação; abertura, exportação e downloads;
rename/move; favoritos e metadados; alteração observada de conteúdo; lixeira,
restauração e exclusão permanente; A1 e assinatura visual; criação, consulta,
exportação e revogação QR; preparação e vínculo de documentos; envio, recebimento,
comprovantes e confirmação; fila Cloud/OneDrive e backup.

Metadados não representam alteração de bytes. Eventos de conteúdo preservam
SHA-256 anterior/novo. Operações automáticas são identificadas como SYSTEM;
a conta OneDrive não substitui o usuário SmartFile.

Documento → Histórico/Auditoria oferece consulta contextual. BUSINESS administrativo
permite filtros por usuário, documento, ação, período e instalação e exportação
CSV/PDF. Views recebem DTOs e emitem sinais; controllers coordenam services;
services usam repositories/database.

## Arquivos principais

- app/services/audit_service.py; history_service.py; document_service.py;
  document_validation_service.py; document_delivery_service.py; audit_report_service.py.
- app/auth/session_context.py; app/models/audit_actor.py; controllers e workers
  de captura, conversão, assinatura, Cloud, validação e entregas.
- app/services/organization_identity_service.py; physical_storage_service.py;
  app/models/corporate_identity.py; organization_identity_repository.py;
  corporate_design_dialog.py; organization_audit_dialog.py; corporate_header.py.
- app/database/schema.sql; migrations.py; entidades e repositories ampliados.
- tests/test_enterprise_traceability.py; tests/fixtures/schema_v23.sql;
  regressões existentes atualizadas para schema 24.
- Manual_Usuario.md/PDF; Documentacao_Tecnica.md/PDF; PRIVACIDADE_EMPRESARIAL.md;
  notas, versão e configuração dos instaladores Linux/Windows.

## Validação

Validação local: **664 testes aprovados** (620 da base + 44 regressões).
Teste focado adicional da tela corporativa: **1 aprovado**.
Gates aprovados: python -m pytest -q, python -m compileall -q app run.py,
python -m pip check e git diff --check.
Migração: banco novo, upgrade do schema 23 real, rollback em falha forçada
e PRAGMA foreign_key_check aprovados.
Instaladores devem corresponder ao commit validado e incluir documentação atualizada.
Resultados nativos e commit dos pacotes são registrados nas
[notas públicas da entrega](https://github.com/boente66/SmartFile/releases/tag/v0.9.0-beta.10)
após aprovação dos gates Linux/Windows.

## Limites preservados

Auditoria permanece por instalação; esta entrega não consolida automaticamente
logs de computadores diferentes. UUIDs públicos de documentos acompanham entregas
LAN; configuração institucional é compartilhada por fonte LAN explicitamente
associada à mesma organização. Conta OneDrive comum não faz essa associação.
O mecanismo usa a confiança do transporte LAN existente, sem novo protocolo
criptográfico de autenticação. Replicação é validada com instalações de teste,
sem nova homologação física de múltiplos computadores.

Eventos antigos sem evidência de ator/instalação mantêm informação desconhecida.
Um editor externo do OneDrive não é identificado automaticamente pelo SmartFile.
O histórico é protegido contra edição comum; acesso administrativo direto ao
arquivo SQLite continua fora dessa garantia. Retenção e finalidade devem ser
estabelecidas pela organização conforme sua base legal.

CNPJ é validado localmente, inclusive alfanumérico; titularidade cadastral não é
consultada. Não há certificação de conformidade legal nem coleta etária adicional.
Veja PRIVACIDADE_EMPRESARIAL.md, com referências oficiais LGPD/ECA Digital.

Scanner físico: homologado para captura e geração correta de PDF.
Reconhecimento automático universal do tamanho da folha:
funcionalidade experimental/assistiva, ainda não homologada para todos os formatos.
Nenhuma aquisição física ou refinamento desse detector nesta rodada.
