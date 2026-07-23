# Relatório formal de evolução organizacional, Cloud Layer e pacote Linux

## 1. Identificação

| Campo | Valor |
|---|---|
| Projeto | SmartFile |
| Versão avaliada | 0.9.0-beta.1 |
| Data | 23 de julho de 2026 |
| Plataforma de build | Linux x86_64, Python 3.12.3 |
| Banco | SQLite, schema 12 |
| Pacote | `smartfile_0.9.0~beta1_amd64.deb` |
| Classificação | Protótipo beta não oficial |

## 2. Objetivo e escopo

Esta evolução mantém o SmartFile local-first e acrescenta o espelhamento da
estrutura organizacional na nuvem. O escopo compreendeu:

- raiz remota isolada por organização;
- correspondência entre pastas lógicas e pastas remotas;
- reconciliação de criação, renomeação, movimentação e exclusão;
- upload e movimentação de documentos para o pai remoto correto;
- invalidação segura dos mapeamentos ao trocar conta ou provedor;
- migration compatível com bancos existentes;
- atualização do Manual do Usuário e da arquitetura;
- regressão automatizada completa;
- reconstrução e validação do pacote Debian.

Não foram reescritos os provedores, o sistema de autenticação, a fila, o storage
interno nem os módulos Scanner, PDF Tools, Visualizador ou Assinaturas.

## 3. Diagnóstico inicial

A auditoria confirmou que os documentos eram enviados individualmente, mas que:

- `remote_root_id` não era preparado pela sincronização;
- `folder_id` não definia o destino do upload;
- não existia persistência da relação pasta local/pasta remota;
- operações `MOVE` e `RENAME` existiam no modelo de fila, porém não eram
  processadas pelo serviço;
- a hierarquia organizacional não era reproduzida no OneDrive ou Google Drive.

O SQLite já era e permanece a fonte principal. Não foi identificada necessidade
de transferir o banco para a nuvem.

## 4. Arquivos auditados

Foram auditados os componentes de nuvem, persistência e integração, incluindo:

- `app/cloud/cloud_manager.py`;
- `app/cloud/cloud_provider.py`;
- `app/cloud/cloud_sync_service.py`;
- `app/cloud/cloud_job_queue.py`;
- `app/cloud/cloud_models.py`;
- `app/cloud/cloud_python_auth_service.py`;
- `app/cloud/cloud_oauth_config_service.py`;
- `app/cloud/cloud_token_store.py`;
- `app/cloud/providers/onedrive_provider.py`;
- `app/cloud/providers/google_drive_provider.py`;
- workers de autenticação, upload, download e sincronização;
- `app/services/document_service.py`;
- repositories de organizações, pastas e documentos;
- migrations, schema SQL e testes relacionados;
- documentação e receita de empacotamento Linux.

## 5. Arquitetura final

```text
DocumentController
        │
        ▼
DocumentService ───────────────► SQLite + storage interno
        │
        ▼
CloudJobQueue
        │
        ▼
CloudSyncService
        │
        ▼
CloudProvider
   ┌────┴─────────┐
   ▼              ▼
OneDrive       Google Drive
```

Estrutura remota:

```text
SmartFile/
└── Nome da Organização (organization_id)/
    ├── Pasta lógica/
    │   └── Subpasta/
    └── documentos sem pasta
```

A Cloud Layer continua sendo o único ponto autorizado a conversar com os
provedores. A pasta da organização inclui seu identificador local para evitar
colisão entre nomes iguais. Cada organização conserva conta, provedor, raiz e
mapeamentos independentes.

## 6. Persistência e migration

O schema foi elevado de 11 para 12. A tabela acrescentada foi:

```text
cloud_folder_mappings
├── organization_id
├── folder_id
├── provider
├── remote_id
├── remote_parent_id
├── remote_name
└── synced_at
```

A chave primária composta impede mais de um mapeamento para a mesma pasta,
organização e provedor. Chaves estrangeiras preservam a integridade com
organizações e pastas. A migration usa `CREATE TABLE IF NOT EXISTS`, não remove
dados e é aplicada tanto a bancos novos quanto legados.

Ao alterar conta ou provedor, `remote_root_id`, `delta_token` e mapeamentos
incompatíveis são descartados. Isso impede que IDs remotos de uma conta sejam
usados em outra.

## 7. Fluxos implementados

### 7.1 Preparação da estrutura

1. O serviço obtém o provedor configurado para a organização.
2. Localiza ou cria `SmartFile`.
3. Localiza ou cria a raiz exclusiva da organização.
4. Persiste `remote_root_id`.
5. Percorre as pastas locais respeitando a ordem pai-filho.
6. Cria ou reconcilia cada pasta e persiste seu mapeamento.

### 7.2 Upload

1. O documento é salvo no storage interno.
2. Seus metadados são gravados no SQLite.
3. A operação entra na `CloudJobQueue`.
4. A estrutura remota é garantida.
5. O upload usa o identificador remoto correspondente ao `folder_id`.
6. Estado, versão e identificador remoto são persistidos.

### 7.3 Reorganização

- renomear pasta: renomeia a pasta remota mapeada;
- mover pasta: atualiza o pai remoto;
- mover documento: cria um trabalho `MOVE`;
- excluir pasta: documentos são deslocados de forma segura e a pasta remota é
  removida após a reconciliação;
- recurso remoto ausente: a pasta pode ser recriada; documento ausente é marcado
  como `REMOTE_DELETED`.

### 7.4 Operação offline

O documento local permanece disponível. Erros de conexão são traduzidos para
estados da fila e podem ser repetidos posteriormente. A nuvem não substitui o
storage interno.

## 8. Segurança

- o arquivo `smartfile.db` não é enviado aos provedores;
- tokens não integram nomes, logs ou mapeamentos de pasta;
- o contrato de provider recebe somente identificadores e arquivos necessários;
- a troca de conta limpa referências remotas incompatíveis;
- o backup administrativo continua separado da sincronização;
- documentos locais são preservados em erro de cota ou indisponibilidade remota.

## 9. Arquivos criados

- `app/repositories/cloud_folder_repository.py`;
- `docs/RELATORIO_FORMAL_EVOLUCAO_ORGANIZACIONAL_E_PACOTE_LINUX.md`.

## 10. Arquivos modificados

- `app/cloud/cloud_manager.py`;
- `app/cloud/cloud_models.py`;
- `app/cloud/cloud_provider.py`;
- `app/cloud/cloud_sync_service.py`;
- `app/cloud/providers/google_drive_provider.py`;
- `app/cloud/providers/onedrive_provider.py`;
- `app/database/migrations.py`;
- `app/database/schema.sql`;
- `app/repositories/document_repository.py`;
- `app/repositories/folder_repository.py`;
- `app/services/document_service.py`;
- `tests/test_administration.py`;
- `tests/test_auth.py`;
- `tests/test_cloud_layer.py`;
- `tests/test_persistence.py`;
- `tests/test_storage_quota.py`;
- `docs/Arquitetura.md`;
- `docs/Manual_Usuario.md`;
- `docs/RELEASE_NOTES_0.9.0-beta.1.md`;
- `README.md`;
- `CHANGELOG.md`.

## 11. Testes executados

| Verificação | Resultado |
|---|---|
| `pytest -q` | **200 aprovados** em 157,99 s |
| Testes direcionados de Cloud, persistência e organizações | **36 aprovados** |
| `python -m compileall -q app tests` | Aprovado |
| `python -m pip check` | Nenhuma dependência quebrada |
| `git diff --check` | Aprovado |
| Build PyInstaller onedir | Aprovado |
| Inspeção do archive: migration, sync service e novo repository | Aprovada |
| Smoke test do bundle fora do venv | Aprovado |
| Auditoria de conteúdo sensível do pacote | Aprovada |
| Validação de dependências ELF | Aprovada |
| Construção por `dpkg-deb` | Aprovada |
| Conferência SHA-256 | Aprovada |
| Lintian | Não executado: ferramenta ausente no host |
| Instalação em SO limpo | Não executada neste ambiente |
| Contas reais OneDrive/Google Drive | Não utilizadas nesta execução |

Os testes automatizados cobrem idempotência da raiz, subpastas, destino de
upload, renomeação, movimentação, exclusão, troca de conta, migration e
preservação local em falha de cota.

## 12. Pacote Debian gerado

| Campo | Valor |
|---|---|
| Caminho | `release/smartfile_0.9.0~beta1_amd64.deb` |
| Tamanho | 218.296.798 bytes |
| Installed-Size | 538.016 KiB |
| SHA-256 | `ad947280eeb88132190e8701f44c36035481d9058288a75794152f06a0b7a062` |
| Arquitetura | amd64 |
| Classificação | Beta não oficial |

O arquivo de conferência é
`release/smartfile_0.9.0~beta1_amd64.deb.sha256`.

## 13. Impactos e compatibilidade

- bancos existentes recebem a migration automaticamente;
- documentos atuais não são removidos nem movidos no storage;
- organizações em modo local não criam estrutura remota;
- uma primeira sincronização após a atualização pode criar a raiz e as pastas;
- a mudança do contrato comum exige que providers adicionais futuros
  implementem `ensure_folder`;
- Scanner, PDF Tools, Visualizador e Assinaturas não tiveram o layout ou a lógica
  alterados.

## 14. Limitações e riscos conhecidos

- validação real depende de Client IDs válidos, consentimento e contas dos
  provedores;
- alterações remotas concorrentes podem exigir resolução manual de conflito;
- não há sincronização do banco SQLite, colaboração em tempo real ou
  versionamento remoto completo;
- o pacote não possui assinatura GPG;
- `lintian` e instalação em máquina virtual limpa ainda devem ser executados;
- hardware de scanner e integrações externas dependem do ambiente do usuário;
- o plugin TIFF do Qt não integra o bundle por exigir `libtiff.so.5`; TIFF
  continua atendido pelo Pillow.

## 15. Classificação final

| Item | Classificação |
|---|---|
| Arquitetura e isolamento organizacional | ✔ Validado por testes automatizados |
| Migration 12 e compatibilidade com banco legado | ✔ Validado por testes automatizados |
| Reconciliação de pastas | ✔ Validado por testes automatizados |
| Não regressão da aplicação | ✔ Validado por testes automatizados |
| Pacote Debian e checksum | ✔ Validado no ambiente de build |
| Operação com contas reais | ⚠ Depende de configuração externa |
| Instalação Linux em ambiente limpo | ⚠ Pendente de homologação |
| Prontidão geral | **Beta funcional para avaliação, não produção** |

## 16. Procedimento de homologação recomendado

1. Conferir o SHA-256.
2. Instalar o `.deb` em Linux Mint/Ubuntu/Debian amd64 limpo.
3. Criar duas organizações e conectar provedores distintos.
4. Criar pastas e subpastas, importar documentos e sincronizar.
5. Renomear, mover e excluir pastas.
6. Desconectar a rede, operar localmente e reconectar.
7. Confirmar a estrutura remota e o isolamento entre organizações.
8. Criar e validar um backup ZIP administrativo.
9. Registrar qualquer problema em uma issue sem anexar tokens ou documentos
   pessoais.
