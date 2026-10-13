# Auditoria prévia — QR antifraude

12/10/2026. Repositório boente66/SmartFile, main real e origin/main iguais.
HEAD inicial: e767dae8e58b96044798ec484de2d17ef74c8ada. Working tree inicialmente
limpo. Checkpoint anterior: 2997f10, branch checkpoint/consolidation-scanner-20261012.
Versão inicial 0.9.0-beta.6; CURRENT_SCHEMA_VERSION 22. Suíte inicial antes de qualquer alteração funcional: **513 passed em 455,78 s**,
exit 0, com QT offscreen e sockets locais autorizados.

## QR e assinatura

SignatureVerificationService usa ReportLab QrCodeWidget e Pillow RGB PNG, payload
HTTPS informado por documento, quiet zone de quatro módulos. Inserção via PyMuPDF,
página/retângulo configuráveis, mínimo 40 pt e bounds de page.rect. PDFSignatureService
insere QR antes do pyHanko IncrementalPdfFileWriter/PAdES-B-B; TSA RFC3161 opcional
produz B-T. QR em PDF previamente assinado é recusado. Sem QR, permite assinatura
incremental adicional. Validação existente distingue integridade e confiança, mas
não possui registro canônico. Manuscrita usa PyMuPDF e PNG normalizado pelo
SignatureImageService (QImage), exclusivamente visual; permite nova cópia após
confirmação de assinatura prévia. Nesta tarefa QR em PDF assinado será recusado
mesmo com essa confirmação. Sem API Gov.br ou nova CA.

As specs Linux/Windows já coletam reportlab.graphics.barcode; Pillow, OpenCV
headless, PyMuPDF e pyHanko existentes serão reutilizados. Testes existentes cobrem
URL, leitura OpenCV, evidência visual, assinatura A1 real e original preservado.

## Storage, exclusão e retenção

DocumentStorageService: UUID, SHA-256 streaming, cópia temporária, os.replace,
checagem pós-promoção e contenção na raiz; sem fsync e sem domínio imutável isolado
por organização. Remove/export comuns destinam-se ao GED. Não é adequado como
storage canônico sem camada adicional. Reutilizar AppPaths, padrão de hash e banco;
criar camada mínima específica com referências relativas e sem overwrite.

Comprovantes possuem storage separado delivery_receipts/protocolo, SHA-256,
fsync portátil e promoção. DeliveryReceiptPdfService produz PDF antes da fila LAN;
assinatura é visual. Não recebe documento de volta no GED (proteção contra recursão).

Permanent delete remove/quarentena somente storage GED; history.document_id tem
cascade. AuditService/audit_log é separado. ValidationRecord deve ter SET NULL nos
vínculos opcionais e snapshots, audit independente e artifact separado.
Organizações são excluídas logicamente. Banco usa lock RLock, transações IMMEDIATE,
SQLite WAL, schema.sql para novo e migrations idempotentes para existentes.

Risco encontrado e informado ao usuário antes de commit: backup completo atual
inclui banco/storage/avatars, mas omite comprovantes. A nova área canônica e os
comprovantes devem entrar no backup; não usar storage editável como referência
histórica. Nenhum documento real será publicado automaticamente.

## Autorização, UI, segredos e nuvem

SessionContext usa permissões granulares com wildcard. OWNER tem *, ADMIN tem
permissions document.*, EDITOR cria/importa, VIEWER abre/lê. Adicionar validation.*
para ADMIN, create/view/export para EDITOR, view/export para VIEWER; criação de
comprovante respeita delivery.acknowledge existente. Não limitar a BUSINESS: os
fluxos de assinatura atuais são ferramentas gerais e validação local deve existir
nos mesmos perfis. Services protegerão organização ativa e permissão; contexto
None preserva uso interno/testes sem sessão, nunca será um endpoint público.

PDFViewerController/ PDFViewerContext existentes serão reutilizados para leitura
canônica; original não será importado ao GED automaticamente. Workers de assinatura
já existem. Criar diálogo leve, controller e worker para hash/validação sem bloquear
UI, com geração de resultados e prevenção de respostas antigas.

CredentialVaultService mantém referências opacas no cofre do SO; não há necessidade
de HMAC ou novos segredos. CloudSyncService sincroniza documentos GED mediante
configuração; não é hosting público e não sincronizará artifact automaticamente.
DeliveryHttpServer é LAN, verifica pares/protocolos, não fornece API pública de
validação. Não alterar estes domínios nem o scanner.

## Distribuição

Linux workflow compila em Ubuntu 22.04 e testa instalação 22.04/24.04. Build deste
host Ubuntu 24.04 não provou ABI 22.04 na etapa anterior. Windows workflow produz
Setup e Portable com Inno Setup e PyInstaller em runner nativo. GitHub CLI autenticado,
sem copiar credenciais. Atualizar versão/metadata/notas/workflows para beta.7 após
validação funcional. A autorização atual inclui GitHub, instaladores e anúncio;
publicar somente com os artefatos efetivamente aprovados. Nunca anunciar build
local como compatibilidade nativa comprovada.

## Evidência adicional de distribuição

A auditoria dos logs reais do GitHub encontrou falha Linux no commit e767dae
(run 38287519178): QtMultimedia/libffmpegmediaplugin requer libpulse.so.0, ausente
no runner. O workflow de build passa a instalar libpulse0, e o pacote declara
essa dependência de runtime. Sem relaxar auditoria ABI ou ignorar bibliotecas
não resolvidas. O Windows desse commit anterior passou (run 38287519410).

## Implementação auditada (antes → depois)

Antes: QR HTTPS por documento, sem ValidationRecord, sem artifact imutável e sem
central de comparação. Depois: URI local versionada por padrão, base opcional por
organização com snapshot, registro/artefato próprios, código humano e hash final.
ReportLab/Pillow/OpenCV, pyHanko, workers de assinatura, AppPaths, Database,
SessionContext, AuditService, receipt renderer e PDF Viewer foram reutilizados.

Criados ValidationRecord, ArtifactType, SignatureType, DocumentValidationResult,
PublicValidationResult, ValidationRepository, DocumentValidationService,
CanonicalArtifactService, ValidationLocatorService, DocumentValidationController,
DocumentValidationDialog e DocumentValidationWorker. Schema 23 em banco novo e
migration 22→23; vínculos opcionais SET NULL e índices por org/hash/documento.
Triggers impedem delete, alterações dos metadados finais e transições inválidas.

Assinaturas geram PENDING antes do QR, preservam bytes finais e ativam somente
após conferência. Manuscrita preserva metadata PDF existente; imagem normalizada
não reaproveita metadata da imagem de origem. QR em PDF previamente assinado é
recusado; A1 sem QR mantém assinatura incremental existente. Comprovantes têm
token/artifact/hash próprios; não são reenviados como documento GED.

Ativação usa tipo de artefato persistido (não o objeto recebido) para escolher
a permissão. Finalização/cancelamento público exige criador e organização ativa.
Compensação privada de operação já autorizada mantém o registro capturado após
troca de organização. Nenhuma consulta interna por ID ignora organization_id.
A central descarta resultados antigos e fecha original ao mudar organização.

Tokens CSPRNG, códigos com unique/retry, hash streaming, referência org/token.pdf,
recusa de traversal/symlinks, promoção sem overwrite, flush/fsync e metadados ACTIVE
transacionais foram adicionados. Falha pós-promoção pode reter órfão/PENDING, nunca
aprovação; recuperação autorizada após 24 h marca FAILED sem apagar evidência.
Arquivo divergente não herda assinatura do original nem é chamado automaticamente
de fraude. A assinatura é avaliada separadamente no original registrado.

Risco histórico de backup identificado na auditoria foi corrigido: ZIP completo
inclui validation_artifacts e delivery_receipts. Testes conferem bytes. O artifact
físico real, os scans e credenciais não entram no Git ou nos instaladores.

Não implementados: servidor/hosting público, upload/publicação automática, HMAC
improvisado, nova CA, Gov.br API, Cloud Layer nova, OCR/diff visual, handler externo
de URI, câmera de celular ou alteração do scanner. Não se promete WORM certificado
ou proteção contra controle simultâneo de DB e filesystem por administrador hostil.

Versão final planejada: 0.9.0-beta.7; schema final: 23. Autorização atual do usuário
inclui atualização GitHub, instaladores e anúncio da nova versão. O fechamento
funcional será enviado antes dos builds nativos; publicação dependerá dos checks
e artefatos efetivamente aprovados. A identificação final será o commit desta
implementação no histórico Git e a release correspondente.

## Regressão de QR rotacionado

O payload SFV1-YXDdXTcBCXBNxdYKuMlVuAm3kO6RGug1d6bQOtYLqgE reproduziu
falha do decoder em página a 180° com o QR anterior (nível L). A inserção agora
compensa /Rotate também na imagem, além das coordenadas, mantendo o QR visualmente
orientado, e usa correção de erro M. Os testes têm dois payloads determinísticos
em 0/90/180/270°, incluindo exatamente o que falhou. Não se enfraqueceu a asserção
de leitura: o decoder precisa devolver o payload completo exato.

Após a correção e revisão de autorização: **66 testes focados passaram em 60,97 s**.
Compileall e diff check passaram. O smoke da aplicação fonte passou (exit 0),
incluindo domínio canônico e exportação byte a byte. A suíte completa final foi concluída antes de commit/push.

## Validação final local

- Suíte inicial: 513 passed em 455,78 s.
- Suíte completa final: **572 passed em 657,85 s (10 min 57 s)**, exit 0.
- 66 testes focados passaram após correção do QR e autorização.
- A primeira rodada completa apontou falha de leitura de QR a 180°: reproduzida e
  corrigida; a suíte final mantém asserção de leitura integral e passou. Uma rodada
  específica também teve timeout de 2 s em teste HTTP LAN preexistente; o cenário
  passou na suíte completa final, sem relaxar timeout ou alterar o servidor LAN.
- Compileall de app/run.py: passou. pip check: No broken requirements found.
- git diff --check: passou. Smoke fonte: exit 0.
- Banco novo: schema 23, foreign_key_check []. Migração 22→23: schema 23,
  foreign_key_check []; teste também cobre idempotência e preservação após delete.
- Hash streaming de 10 MiB sintéticos em /tmp, cache quente: 38,57 ms neste host;
  observação pontual, sem promessa de SLA.
- Tests de packaging Linux/Windows passaram na suíte final; builds/instalação
  nativos serão verificados no GitHub antes de publicar os instaladores.
- Versão 0.9.0-beta.7, schema 23. Nenhuma alteração no detector/scanner nesta tarefa.
- Nenhuma release publicada até este commit funcional. A publicação subsequente
  está autorizada pelo pedido atual do usuário e será registrada no fechamento.

## Validação nativa do primeiro commit e correção final de URI

Commit funcional inicial: 517c45c945e8a54ed897a76dd70627ae0099db6b, enviado à main.
GitHub Python tests: run 38326884728, sucesso. Windows Setup/Portable: run
38326884703, sucesso. Linux .deb: run 38326884744, sucesso, com auditoria ABI,
instalação/reinstalação e preservação de dados na remoção em Ubuntu 22.04 e 24.04.

Na revisão de compatibilidade, a configuração aceitava esquema HTTPS em maiúsculas,
mas o parser reconhecia somente o prefixo minúsculo. A base agora normaliza somente
o esquema e o parser aceita sua variação de case, sem alterar o token.
**25 testes específicos passaram em 131,19 s**, incluindo URL snapshot e rejeições
de bases/payloads inválidos. O commit dessa correção terá as suítes e builds nativos
repetidos; somente seus artefatos serão usados na release. Nenhuma release publicada
até aqui.

## Fechamento funcional definitivo

A prova A1 integrada foi ampliada: mesma imagem QR na cópia com bytes alterados,
HASH_MISMATCH, assinatura do original separada e abrir/exportar canônico com bytes
e SHA-256 idênticos ao PDF assinado. A ativação também exige is_pdf, recusando uma
imagem renomeada para .pdf antes de preservar/ativar o artefato. Os dois testes
focados passaram em 13,70 s.

Suíte completa após todos os ajustes: **574 passed em 426,29 s (7 min 6 s)**, exit 0.
Os checks do commit c1a4a7451f240ade344934edeb08531648cdbe7c passaram no GitHub:
Python 38327969912, Linux 38327969906 e Windows 38327969919. O commit deste
fechamento será a fonte dos artefatos finais, com novos builds e suítes nativos.
Não há alteração do scanner, da Cloud Layer, do cofre ou publicação de documentos.
Schema 23 e versão 0.9.0-beta.7. Nenhuma release publicada nesta fase funcional.

## Publicação final — 12/10/2026

Implementação final enviada à main: `d047836aae1afba94f42a0f57cd8b842d52b097a`.
Versão **0.9.0-beta.7**, schema **23**. Suíte local definitiva: **574 testes
aprovados em 426,29 s**. Sem nova aquisição física ou refinamento do detector.

Todos os checks nativos do mesmo commit foram aprovados:

- [Python tests](https://github.com/boente66/SmartFile/actions/runs/38331316729).
- [Linux build/ABI/instalação](https://github.com/boente66/SmartFile/actions/runs/38331316743), incluindo instalação/reinstalação e preservação dos dados na remoção em Ubuntu 22.04 e 24.04.
- [Windows tests/Setup/Portable/smoke](https://github.com/boente66/SmartFile/actions/runs/38331318734).

A pedido do usuário, a [release beta.7](https://github.com/boente66/SmartFile/releases/tag/v0.9.0-beta.7)
foi publicada como pré-release, com anúncio, Linux amd64, Windows x64 Setup e
Portable, e respectivos checksums. A tag aponta ao commit funcional acima.
Os seis assets foram conferidos como uploaded; os digests SHA-256 dos três
pacotes retornados pelo GitHub correspondem aos arquivos recuperados do CI.
O nome público Debian usa `.beta7`; sua versão interna permanece `0.9.0~beta7`.
Nenhum documento, scan, banco ou credencial foi incluído nos instaladores.

| Instalador | Bytes | SHA-256 |
| --- | ---: | --- |
| smartfile_0.9.0.beta7_amd64.deb | 256807172 | `1494ad7c6b894f5e4a39340ab813d2fd15baca7da10627b32b0e4b3e73656ee9` |
| SmartFile-0.9.0-beta.7-Windows-x64-Setup.exe | 119775581 | `42abba2ca5c906769d892710555ccac39f47838797da6df50ed41cd758abc27c` |
| SmartFile-0.9.0-beta.7-Windows-x64-Portable.zip | 171556123 | `0ae6094f755a0301fe551ca138a044804d738f9179b21938ee75a0ee892dc4ec` |

Scanner físico: homologado para captura e geração correta de PDF.
Reconhecimento automático universal do tamanho da folha:
funcionalidade experimental/assistiva, ainda não homologada para todos os formatos.
Estados PARTIAL/REVIEW são preservados quando a geometria não é confiável.

QR local funciona na instalação e organização autorizadas sem URL pública
obrigatória. O QR localiza o registro, e a comparação verifica os bytes do original
canônico. Base HTTPS continua opcional, sem servidor público ou publicação
automática de documentos. Multicloud, Solicitações e notificações permanecem
consolidados. Este fechamento altera somente documentação; os instaladores
publicados usam exatamente o commit funcional testado.
