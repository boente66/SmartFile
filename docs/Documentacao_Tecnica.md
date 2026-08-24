# Documentação Técnica

## Arquitetura

O projeto separa views, controllers, services, repositories, models, workers e
coordinators. A composição explícita acontece no `AppController`, sem service
locator e reutilizando a instância de banco da sessão.

Na camada empresarial, `DocumentRequestController` controla solicitações,
`CorporateTransportController` controla configuração e teste do transporte,
`CorporateTransportCoordinator` mantém o processamento NAS em background e
`OrganizationSettingsController` concentra os pontos de entrada administrativos.

Um controller traduz eventos de interface em casos de uso. Um coordinator
controla lifecycle recorrente e independente de telas. Um worker executa apenas
uma tarefa demorada fora da thread Qt. Regras, permissões e auditoria permanecem
nos services de domínio.

## Transporte corporativo e reconciliation

`OrganizationTransportService` cria snapshots físicos imutáveis em
`organization_transport_targets`. `organization_transport_settings` aponta para
o target atual, enquanto cada `transport_job` conserva seu próprio
`transport_target_id`. Assim, alteração de endpoint ou rotação de credencial não
redireciona jobs históricos. O único campo mutável do lifecycle do target é o
estado `ACTIVE`/`RETIRED`.

Jobs migrados sem prova de origem recebem `NEEDS_RECONCILIATION`. O repositório
não os entrega à fila normal, `mark_running` aplica a mesma barreira no banco e o
service recusa processamento direto. Caminhos remotos continuam validados pelo
adapter contra a raiz do target correspondente.

## Credential Vault

`CredentialVaultService` depende do contrato `CredentialProvider`. A
implementação `OSCredentialProvider` usa `keyring`: Secret Service no Linux e
Credential Manager no Windows. O SQLite persiste somente refs no formato
`smartfile:transport:<organization_id>:<uuid>`; username e senha existem apenas
no objeto transitório e no cofre.

Rotação cria nova referência e novo target. Uma referência antiga não é apagada
enquanto houver target ativo, job pendente/falho ou upload remoto ainda sem
DELETE concluído. Como SQLite e keyring não compartilham transação, falha de banco
após `store` executa compensação no cofre. Indisponibilidade do keyring não impede
a inicialização da aplicação e nunca produz fallback em texto puro.

## Persistência

Os documentos são armazenados localmente em SQLite através de uma camada de serviço e repositório.
O schema atual é 20. As migrations preservam organizações, documentos,
transportes e entregas existentes. A tabela
`delivery_acknowledgement_receipts` mantém o comprovante separado do documento
original, com UUID, SHA-256, estado de fila e timestamps de envio/recebimento.

## Interface

A interface gráfica é construída com PyQt6.
