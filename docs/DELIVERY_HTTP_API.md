# SmartFile — Contrato HTTP de entrega documental 1:1

## Escopo

Este contrato transporta solicitações e documentos entre duas instalações
SmartFile cadastradas na mesma organização lógica. Ele é independente da Cloud
Layer e do Corporate Transport/NAS. A versão 1 usa HTTP para laboratório LAN.

O header obrigatório `X-SmartFile-Instance` carrega o UUID permanente do peer.
O servidor valida essa identidade contra o cadastro local; IP nunca é usado como
identidade. HTTPS, assinatura das mensagens e chaves por instalação são
evoluções futuras e não estão declaradas como implementadas nesta beta.

## Endpoints

| Método | Endpoint | Função |
|---|---|---|
| `POST` | `/api/v1/requests` | Replica uma solicitação para a instalação responsável |
| `POST` | `/api/v1/deliveries` | Cria a entrega remota e seus itens pendentes |
| `POST` | `/api/v1/deliveries/{protocol}/items/{item_uuid}` | Transfere um item em streaming |
| `POST` | `/api/v1/deliveries/{protocol}/complete` | Valida que todos os itens foram verificados |
| `GET` | `/api/v1/deliveries/{protocol}` | Consulta estado, entrega, visto e confirmação |
| `POST` | `/api/v1/deliveries/{protocol}/viewed` | Contrato reservado para evento de visualização |
| `POST` | `/api/v1/deliveries/{protocol}/acknowledge` | Contrato reservado para confirmação |

## Regras de integridade

- metadata JSON: máximo de 1 MiB;
- item: limite de 4 GiB nesta versão;
- leitura e envio em chunks de até 1 MiB;
- `Content-Length` deve coincidir com o snapshot do item;
- SHA-256 é calculado enquanto o arquivo temporário é escrito;
- falha de tamanho, stream ou checksum remove o temporário;
- o rename atômico ocorre somente após a verificação;
- `DELIVERED` exige todos os itens em `VERIFIED`;
- nomes lógicos não podem conter diretórios, barras, NUL ou traversal.

## Identificadores

- `request_uuid`: correlação da solicitação entre bancos SQLite independentes;
- `delivery_uuid`: identidade interna segura da entrega;
- `protocol_number`: identificador humano no formato
  `SF-AAAAMMDD-SEQUENCIAL-SUFIXO`;
- `instance_id`: UUID permanente com prefixo `SF-`;
- IDs inteiros locais de usuários/documentos não são usados para correlacionar
  registros entre máquinas. Usuários são mapeados pelo nome de login ativo na
  organização local.

## Falhas e retry

Erros HTTP e de rede são propagados como erros de domínio. Entregas offline
ficam em `QUEUED`, com backoff crescente até uma hora e limite de oito falhas
automáticas. Depois disso entram em `FAILED`; o retry manual zera a contagem.
Solicitações ainda não entregues são reenviadas de forma idempotente, usando o
UUID para impedir duplicação.
