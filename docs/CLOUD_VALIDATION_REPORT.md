# SmartFile — Relatório de validação da Cloud Layer

Data: 14/07/2026

## Classificação

- ✔ **Validado em ambiente real:** conectividade aos endpoints OAuth, callback
  loopback, detecção de porta ocupada e escrita/leitura/remoção no Secret Service.
- ✔ **Validado por testes automatizados:** contratos OAuth, persistência segura,
  providers, fila, workers, isolamento por organização, estados, erros HTTP,
  renovação simulada, upload, download, rename, move, delete e fluxos do GED.
- ⚠ **Depende de configuração externa:** consentimento e operações com contas
  reais OneDrive/Google Drive. O ambiente não possui Client IDs nem contas ligadas.
- ✖ **Não implementado:** criação automática de pasta raiz remota e importação
  automática de arquivos remotos novos para o catálogo documental.

Esta classificação não declara a Cloud Layer pronta para produção com contas reais.

## Ambiente encontrado

- OneDrive: `MISSING`.
- Google Drive: `MISSING`.
- Variáveis OAuth: ausentes.
- Recursos OAuth empacotados: ausentes.
- Contas em `cloud_accounts`: nenhuma.
- Organização local: `Minha Organização`, modo `LOCAL`.
- Keyring: Secret Service disponível e funcional.

## Problemas encontrados e corrigidos

1. A fila era global e um worker podia processar jobs de outra organização.
   A seleção, contagem e execução agora aceitam e respeitam `organization_id`.
2. Contas em `REAUTH_REQUIRED` ou `ERROR` eram lidas como desconectadas devido ao
   filtro `ACTIVE`. O estado agora parte da conta vinculada em `cloud_settings`.
3. Erros HTTP 401, 403, 404, 413, 429 e 5xx eram excessivamente genéricos.
   Foram traduzidos para erros de domínio, sem incluir corpo sensível da resposta.
4. Falhas antes do bloco de tratamento podiam deixar jobs em `RUNNING`.
   Aquisição do provider agora faz parte do processamento protegido e gera retry.
5. Download offline era marcado como `PENDING_UPLOAD`. Agora permanece
   `PENDING_DOWNLOAD`.
6. Upload grande no Google Drive carregava o arquivo inteiro em memória. Agora usa
   blocos de 8 MiB, alinhados ao múltiplo obrigatório de 256 KiB.
7. Renovação silenciosa MSAL escolhia a primeira conta do cache. Agora seleciona a
   identidade vinculada à organização por `account_hint`.
8. Testes podiam escrever tokens fictícios no keyring real. A suíte usa fallback
   isolado e não deixa credenciais temporárias no sistema.
9. O estado visual `DISABLED` não tinha texto próprio. Agora possui mensagem clara.

## Validações reais sem conta

- descoberta OAuth Microsoft: HTTP 200;
- descoberta OAuth Google: HTTP 200;
- Microsoft Graph sem token: HTTP 401;
- Google Drive sem token: HTTP 403;
- servidor callback em `127.0.0.1`: aprovado;
- porta callback ocupada: detectada;
- Secret Service: escrita, leitura e remoção aprovadas;
- limpeza das entradas temporárias: aprovada.

## Cobertura automatizada

- 183 testes aprovados;
- OneDrive e Google: OAuth simulado, PKCE, perfil e refresh;
- upload pequeno e grande, download, metadata, rename, move e delete;
- fila offline, retry, limite de tentativas e reconexão;
- isolamento de contas, configurações e jobs entre organizações;
- TokenStore, fallback Fernet e migração de tokens legados;
- ausência de tokens no SQLite, logs, auditoria e arquivos rastreados;
- estados `NOT_CONFIGURED`, `DISCONNECTED`, `AUTHENTICATING`, `CONNECTED`,
  `TOKEN_EXPIRED`, `REAUTH_REQUIRED`, `ERROR` e `DISABLED`;
- Scanner → GED → Storage → Cloud Queue;
- workers mantêm o sinal `QThread.finished` nativo.

## Pontos que exigem contas reais

### OneDrive

- conta pessoal;
- conta corporativa/tenant;
- consentimento real;
- perfil real retornado pelo Graph;
- renovação real do cache MSAL;
- CRUD de arquivos e throttling real;
- remoção de consentimento no portal Microsoft.

### Google Drive

- consentimento real;
- emissão e renovação de refresh token;
- CRUD real;
- sessão resumível interrompida e retomada;
- remoção de consentimento na conta Google.

## Configuração necessária para produção

Consulte `docs/OAUTH_DESENVOLVIMENTO.md`. Em resumo:

- registrar o SmartFile como cliente público Desktop no Microsoft Entra;
- configurar `http://localhost` e o tenant adequado;
- criar OAuth Client Google do tipo Desktop e habilitar Drive API;
- fornecer configurações por recurso empacotado, ambiente ou configuração
  administrativa;
- não distribuir tokens, arquivos pessoais ou segredo de backend;
- executar o roteiro real em Linux e Windows antes da liberação.

## Limitações e riscos restantes

- sem credenciais externas, nenhuma conta real foi autenticada nesta execução;
- `remote_root_id` não é criado automaticamente;
- alterações remotas novas não criam registros locais automaticamente;
- desconexão remove o token local, mas não revoga consentimento no provedor;
- retomada de upload após interrupção reinicia pelo job; não persiste a URI da
  sessão entre reinicializações;
- o fallback Fernet protege o arquivo, mas a chave fica no mesmo perfil local;
- testes de firewall, proxy corporativo, MFA e Conditional Access dependem do
  ambiente de produção.

## Referências verificadas

- Microsoft MSAL Python — aquisição interativa e silenciosa:
  https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens
- Microsoft Graph — respostas de erro:
  https://learn.microsoft.com/en-us/graph/errors
- Microsoft Graph — upload session:
  https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession
- Google OAuth para aplicativos desktop:
  https://developers.google.com/identity/protocols/oauth2/native-app
- Google Drive — uploads:
  https://developers.google.com/workspace/drive/api/guides/manage-uploads
- Google Drive — tratamento de erros:
  https://developers.google.com/workspace/drive/api/guides/handle-errors
