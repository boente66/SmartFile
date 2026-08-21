# Relatório técnico — SmartFile Fase 7

## Resultado

A Fase 7 implementa o domínio separado de solicitações, cesta e entrega 1:1 por
protocolo. O documento continua sendo registro oficial do GED; a cesta guarda
referências; o HTTP transporta em chunks; UUID identifica a instalação; IP
somente localiza; visto e confirmação encerram o ciclo auditável.

## Arquitetura

```text
DeliveryWorkspaceView
  → DocumentDeliveryController
    → DocumentRequestService / DeliveryBasketService / DocumentDeliveryService
      → Repositories → SQLite schema 18
    → DeliveryCoordinator
      → Queue Worker / Send Worker
      → DeliveryHttpClient ⇄ DeliveryHttpServer
```

Corporate Transport/NAS e Cloud Layer permanecem independentes e não foram
usados como atalho para a entrega entre usuários.

## Persistência

A migration 18 preserva solicitações legadas, converte `OVERDUE` persistido em
`OPEN` e passa a calcular atraso pelo prazo. Foram adicionadas identidades de
solicitação, timestamps do workflow, instalações, vínculos documentais,
entregas, itens e histórico de domínio.

## Segurança e resiliência

- UUID permanente por instalação; IP não autentica nem identifica;
- peer precisa estar previamente cadastrado na organização local;
- validação de destinatário, usuário ativo, protocolo, UUID, tamanho e nome;
- bloqueio de path traversal;
- temporário, flush, fsync, SHA-256 e promoção atômica;
- timeout de cliente e servidor;
- fila persistente, backoff, limite automático e retry manual;
- operações de rede fora da thread da interface;
- DocumentService permanece a única entrada de documento recebido no GED.

## Limitações declaradas

Esta beta fornece HTTP para laboratório LAN confiável. Um incremento posterior
da mesma beta adicionou descoberta mDNS local e autorização explícita, sem mudar
o protocolo de transferência desta fase. HTTPS, chaves/certificados por
instalação, Socket.IO, múltiplos destinatários e servidor central continuam como
evoluções futuras. Não se deve expor a porta diretamente à Internet.

## Validação

A suíte da fase cobre migration, transições, cesta, protocolos únicos, UUID
persistente, mudança de IP, traversal, checksum incorreto, chunks limitados,
duas instâncias locais, entrega, visto, confirmação e destinatário offline com
retry. O resultado completo da suíte e dos pacotes deve ser registrado no
relatório final da publicação.

Resultado final local em 15/08/2026:

- `python -m pytest -q`: **320 passed**;
- `python -m compileall`: aprovado;
- `pip check`: nenhuma dependência quebrada;
- `git diff --check`: aprovado;
- integração HTTP automatizada A ⇄ B: aprovada;
- fluxo offline → retry → `DELIVERED`: aprovado;
- Manual do Usuário PDF regenerado;
- `.deb` amd64 reconstruído, auditado e aprovado em dois smoke tests;
- artefato: `smartfile_0.9.0~beta2_amd64.deb` (221.769.208 bytes);
- SHA-256: `779b5105665284d3da880af8e7fdcdcac7b1ec79b6d17b9ab4610e61bb420fb4`;
- `lintian`: não executado localmente porque não está instalado; permanece no CI.

O instalador Windows não é compilado no Linux. O push para `main` aciona o
workflow Windows oficial, que executa testes, PyInstaller, auditoria, smoke test,
Inno Setup e checksum antes de publicar o artefato temporário.
