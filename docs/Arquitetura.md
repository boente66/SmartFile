# Arquitetura

## Camadas

- Views: telas e componentes da interface;
- Controllers: orquestração entre interface e lógica;
- Services: regras de negócio e casos de uso;
- Repositories: acesso a dados locais;
- Entities e Models: representação de dados da aplicação;
- Workers: operações demoradas fora da thread da interface.
- Coordinators: lifecycle recorrente de processos de aplicação independentes de uma tela.

Views não executam SQL, serviços não conversam diretamente com widgets e os
provedores externos não são acessados pelos módulos de domínio.

## Camada de aplicação empresarial

O `AppController` é o composition root da aplicação autenticada. Ele reutiliza
a mesma instância de `Database` e compõe explicitamente:

```text
AppController
├── DocumentController
├── DocumentRequestController
├── CorporateTransportController
├── CorporateTransportCoordinator
└── OrganizationSettingsController
```

As responsabilidades são distintas:

- **domínio/service:** valida permissões e regras, persiste por repositories e
  registra os eventos de auditoria;
- **controller:** recebe intenções da View, chama casos de uso do service e
  traduz o resultado para apresentação;
- **coordinator:** mantém timer, organização ativa, prevenção de concorrência e
  shutdown de um processo que precisa sobreviver à troca de telas;
- **worker:** executa uma única operação potencialmente demorada fora da thread
  da interface e devolve resultado por sinais Qt.

Solicitações documentais seguem a direção:

```text
DocumentRequestsDialog
        ↓ sinais
DocumentRequestController
        ↓
DocumentRequestService
        ↓
DocumentRequestRepository
```

A View não conhece o service. Permissões e validações continuam no backend.

Configuração e execução do transporte também são independentes:

```text
OrganizationTransportDialog
        ↓
CorporateTransportController → OrganizationTransportService

CorporateTransportCoordinator
        ↓
TransportWorker
        ↓
CorporateTransportService → TransportJobQueue → NASTransportAdapter
```

O coordinator inicia com a sessão autenticada, consulta jobs sem depender da
tela Documentos, impede dois workers para o mesmo banco e organização, cancela
com segurança na troca de organização e solicita interrupção no logout/encerramento.
Resultados chegam à UI apenas por sinais Qt.

## Persistência local

O SQLite e o storage gerenciado são a fonte principal do Mini GED. O banco
centraliza organizações, pastas lógicas, documentos, histórico, filas e
metadados. Arquivos são preservados no storage local mesmo quando a nuvem está
indisponível.

## Sincronização organizacional

Toda integração externa passa pela Cloud Layer:

```text
DocumentService
      │
      ▼
CloudJobQueue → CloudSyncService → CloudProvider
                                     ├── OneDriveProvider
                                     └── GoogleDriveProvider
```

Cada organização possui sua própria configuração, raiz remota e mapeamentos de
pastas. A estrutura criada no provedor é:

```text
SmartFile/
└── Nome da Organização (id)/
    ├── Pasta lógica/
    │   └── Subpasta/
    └── documentos sem pasta
```

`CloudSyncService` cria a raiz de forma idempotente, reconcilia criação,
renomeação, movimentação e exclusão de pastas, e posiciona os documentos no pai
remoto correspondente. `cloud_folder_mappings` relaciona a identidade local da
pasta ao identificador do provedor. A troca de conta ou provedor invalida esses
mapeamentos para impedir reutilização de IDs de outra conta.

O arquivo `smartfile.db` não é enviado à nuvem. Banco, tokens e configurações
sensíveis permanecem locais. OneDrive e Google Drive recebem somente a cópia dos
documentos e a hierarquia organizacional necessária à sincronização.

## Backup

O backup administrativo ZIP é independente da Cloud Layer. Ele cria um snapshot
consistente do SQLite, inclui o storage gerenciado e configurações permitidas,
gera manifesto e checksums e nunca reutiliza a nuvem como única cópia.
