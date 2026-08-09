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

## Persistência

Os documentos são armazenados localmente em SQLite através de uma camada de serviço e repositório.

## Interface

A interface gráfica é construída com PyQt6.
