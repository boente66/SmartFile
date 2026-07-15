# RELATÓRIO TÉCNICO FORMAL DE IMPLEMENTAÇÃO E VALIDAÇÃO

## Cloud Layer — SmartFile

| Controle do documento | Informação |
|---|---|
| Projeto | SmartFile |
| Componente | Cloud Layer |
| Natureza | Auditoria, correção, estabilização e validação |
| Data de emissão | 14 de julho de 2026 |
| Branch avaliada | `main` |
| Revisão Git de referência | `e1081d9` |
| Situação das alterações | Implementadas no diretório de trabalho; publicação no Git não integra este relatório |
| Versão do relatório | 1.0 |

## 1. Finalidade

Este relatório formaliza as atividades executadas para auditar, corrigir,
estabilizar e validar a Cloud Layer do SmartFile, responsável pela integração
indireta do Mini GED com Microsoft OneDrive e Google Drive.

O trabalho respeitou as seguintes restrições:

- preservação da arquitetura existente;
- ausência de novos providers;
- manutenção dos contratos públicos;
- armazenamento local mantido como fonte primária dos documentos;
- comunicação com os provedores exclusivamente por meio da Cloud Layer;
- ausência de alterações funcionais desnecessárias nos módulos Scanner, PDF
  Tools, Visualizador, Assinaturas, Organizações e Usuários.

## 2. Escopo

Foram incluídos no escopo:

1. configuração e autenticação OAuth;
2. armazenamento e remoção segura de tokens;
3. providers OneDrive e Google Drive;
4. fila, workers e serviço de sincronização;
5. isolamento de contas, configurações e trabalhos por organização;
6. integração do módulo Documentos com a fila;
7. fluxo Scanner para GED e posterior enfileiramento;
8. estados e mensagens da interface da nuvem;
9. tratamento de indisponibilidade, autenticação e erros HTTP;
10. migrations, schema, sessão, auditoria e testes relacionados.

Não fizeram parte do escopo a criação de novos recursos, novos provedores,
compartilhamento, colaboração, sincronização em tempo real ou alteração da
arquitetura pública.

## 3. Critério de classificação das evidências

Cada resultado deste relatório utiliza uma das classificações abaixo:

| Símbolo | Classificação | Interpretação |
|---|---|---|
| ✔ | Validado em ambiente real | Verificado usando recursos efetivos do sistema operacional ou endpoints públicos reais |
| ✔ | Validado por testes automatizados | Confirmado por teste repetível com dependências externas controladas ou simuladas |
| ⚠ | Depende de configuração externa | Exige cliente OAuth, consentimento, conta ou infraestrutura externa indisponível nesta execução |
| ✖ | Não implementado | Comportamento não existente na versão auditada |

Uma validação automatizada não é apresentada como equivalente a uma operação
executada com conta real.

## 4. Componentes auditados

Foram analisados os seguintes componentes:

- `CloudManager`;
- `CloudPythonAuthService`;
- `CloudOAuthConfigurationService`;
- `CloudTokenStore` e mecanismo de fallback cifrado;
- `OneDriveProvider`;
- `GoogleDriveProvider`;
- contrato `CloudProvider`;
- `CloudSyncService`;
- `CloudJobQueue`;
- workers de autenticação, upload, download e sincronização;
- `DocumentController`, `DocumentService` e integração da `DocumentView`;
- fluxo de inclusão do Scanner no GED;
- `SessionContext`;
- migrations e schema SQLite;
- estados da interface da nuvem;
- testes de Cloud, OAuth, autenticação, administração e segurança.

## 5. Diagnóstico do ambiente

Na data da validação, o ambiente apresentava:

| Item | Situação | Classificação |
|---|---|---|
| Configuração OAuth OneDrive | `MISSING` | ⚠ Depende de configuração externa |
| Configuração OAuth Google Drive | `MISSING` | ⚠ Depende de configuração externa |
| Variáveis OAuth | Ausentes | ⚠ Depende de configuração externa |
| Contas vinculadas | Nenhuma | ⚠ Depende de configuração externa |
| Organização existente | `Minha Organização`, modo local | ✔ Validado em ambiente real |
| Keyring do sistema | Secret Service disponível e funcional | ✔ Validado em ambiente real |
| Tokens no SQLite | Nenhum | ✔ Validado em ambiente real |
| Credenciais rastreadas no repositório | Nenhuma encontrada | ✔ Validado por testes automatizados |

Esta condição impediu a realização de login e operações completas com contas
reais, mas não impediu a auditoria estrutural, os testes automatizados e as
validações reais de rede, callback e keyring.

## 6. Não conformidades identificadas

| ID | Não conformidade | Risco |
|---|---|---|
| NC-01 | Seleção global da fila sem filtro obrigatório da organização solicitante | Processamento cruzado entre organizações |
| NC-02 | Contas em `REAUTH_REQUIRED` ou `ERROR` podiam ser apresentadas como desconectadas | Diagnóstico incorreto e experiência confusa |
| NC-03 | Respostas HTTP relevantes eram convertidas em erros genéricos | Tratamento inadequado de autenticação, permissão e retry |
| NC-04 | Falha anterior ao tratamento protegido podia deixar trabalho em `RUNNING` | Trabalho bloqueado na fila |
| NC-05 | Download offline podia retornar ao estado de upload pendente | Inconsistência do fluxo documental |
| NC-06 | Upload grande do Google Drive carregava o arquivo completo em memória | Consumo excessivo de memória |
| NC-07 | Renovação MSAL podia escolher a primeira conta disponível no cache | Uso da identidade errada em cenário multi-organização |
| NC-08 | Testes podiam acessar o keyring real com tokens fictícios | Contaminação do ambiente de desenvolvimento |
| NC-09 | Estado visual `DISABLED` não possuía mensagem específica | Informação insuficiente ao usuário |
| NC-10 | Timeout, cancelamento e falha de callback não eram totalmente traduzidos | Possível exposição de erro técnico ao usuário |

## 7. Implementação realizada

As não conformidades foram tratadas da seguinte forma:

1. seleção, contagem e processamento da fila passaram a aceitar e respeitar
   `organization_id`;
2. workers de upload, download e sincronização passaram a executar somente no
   contexto organizacional solicitado;
3. a resolução do estado de autenticação passou a considerar a conta efetivamente
   vinculada, inclusive quando estiver em reautenticação ou erro;
4. erros HTTP 401, 403, 404, 409, 413, 429, 5xx e quota foram convertidos em erros
   de domínio apropriados;
5. corpos de resposta potencialmente sensíveis deixaram de integrar mensagens de
   erro destinadas ao usuário;
6. erros de autenticação passaram a marcar a conta como necessitando
   reautenticação;
7. trabalhos interrompidos por falha transitória retornam ao estado pendente
   correspondente;
8. uploads grandes no Google Drive passaram a utilizar streaming em blocos de
   8 MiB, respeitando o alinhamento exigido pelo protocolo;
9. renovação silenciosa MSAL passou a selecionar a identidade associada à
   organização por indicação de e-mail;
10. callbacks inválidos, porta ocupada, timeout e cancelamento passaram a gerar
    exceções de domínio e mensagens controladas;
11. testes de TokenStore passaram a isolar o keyring real;
12. a interface passou a apresentar mensagem própria para o estado `DISABLED`.

Não foram criados providers adicionais nem removidas APIs públicas existentes.

## 8. Arquivos afetados

### 8.1 Código de produção modificado

- `app/cloud/cloud_job_queue.py`;
- `app/cloud/cloud_manager.py`;
- `app/cloud/cloud_provider.py`;
- `app/cloud/cloud_python_auth_service.py`;
- `app/cloud/cloud_sync_service.py`;
- `app/cloud/providers/google_drive_provider.py`;
- `app/controllers/document_controller.py`;
- `app/views/document_view.py`;
- `app/workers/cloud_download_worker.py`;
- `app/workers/cloud_sync_worker.py`;
- `app/workers/cloud_upload_worker.py`.

### 8.2 Testes modificados

- `tests/conftest.py`;
- `tests/test_cloud_layer.py`;
- `tests/test_cloud_oauth_security.py`;
- `tests/test_cloud_python_auth.py`.

### 8.3 Documentação criada

- `docs/CLOUD_VALIDATION_REPORT.md`;
- `docs/RELATORIO_FORMAL_IMPLEMENTACAO_CLOUD_LAYER.md`.

## 9. Evidências de testes automatizados

| Verificação | Resultado | Classificação |
|---|---|---|
| Suíte `pytest` | 183 testes aprovados | ✔ Validado por testes automatizados |
| Compilação Python | Aprovada por `compileall` | ✔ Validado por testes automatizados |
| Integridade de dependências | `pip check`: nenhuma dependência quebrada | ✔ Validado por testes automatizados |
| Qualidade do diff textual | `git diff --check`: aprovado para arquivos-fonte | ✔ Validado por testes automatizados |
| Isolamento de fila por organização | Aprovado | ✔ Validado por testes automatizados |
| Estados da interface | Oito estados cobertos | ✔ Validado por testes automatizados |
| Erros HTTP | 401, 403, 404, 413, 429 e 503 cobertos | ✔ Validado por testes automatizados |
| Upload grande | Streaming e alinhamento verificados | ✔ Validado por testes automatizados |
| Callback expirado | Erro de domínio verificado | ✔ Validado por testes automatizados |
| Seleção de conta MSAL | Identidade vinculada verificada | ✔ Validado por testes automatizados |
| Scanner para fila | Fluxo coberto | ✔ Validado por testes automatizados |
| Persistência segura | Ausência de tokens no SQLite, logs e auditoria | ✔ Validado por testes automatizados |

## 10. Evidências obtidas em ambiente real

| Verificação | Resultado | Classificação |
|---|---|---|
| Endpoint de descoberta Microsoft | HTTP 200 | ✔ Validado em ambiente real |
| Endpoint de descoberta Google | HTTP 200 | ✔ Validado em ambiente real |
| Microsoft Graph sem token | HTTP 401 esperado | ✔ Validado em ambiente real |
| Google Drive sem token | HTTP 403 esperado | ✔ Validado em ambiente real |
| Callback em `127.0.0.1` | Recepção local aprovada | ✔ Validado em ambiente real |
| Porta localhost ocupada | Detecção aprovada | ✔ Validado em ambiente real |
| Secret Service/keyring | Escrita, leitura e remoção aprovadas | ✔ Validado em ambiente real |
| Limpeza pós-teste | Nenhuma credencial temporária restante | ✔ Validado em ambiente real |

Essas verificações confirmam a infraestrutura local e a comunicação básica com os
serviços públicos. Elas não constituem autenticação com uma conta real.

## 11. Validações pendentes com contas reais

| Provedor | Verificação pendente | Classificação |
|---|---|---|
| OneDrive | Login em conta pessoal e consentimento | ⚠ Depende de configuração externa |
| OneDrive | Login em conta corporativa/tenant | ⚠ Depende de configuração externa |
| OneDrive | Perfil, refresh, upload, download, rename, move e delete | ⚠ Depende de configuração externa |
| OneDrive | Throttling, quota e consentimento removido | ⚠ Depende de configuração externa |
| Google Drive | Login, consentimento e emissão de refresh token | ⚠ Depende de configuração externa |
| Google Drive | Upload, download, rename, move e delete | ⚠ Depende de configuração externa |
| Google Drive | Sessão resumível interrompida e renovação real | ⚠ Depende de configuração externa |
| Ambos | Proxy, firewall, MFA e políticas corporativas | ⚠ Depende de configuração externa |

## 12. Limitações conhecidas

| Limitação | Classificação |
|---|---|
| Criação automática da pasta raiz remota | ✖ Não implementado |
| Importação automática de novos arquivos criados diretamente na nuvem | ✖ Não implementado |
| Revogação remota do consentimento ao desconectar | ✖ Não implementado |
| Persistência da URI de upload resumível entre reinicializações | ✖ Não implementado |
| Validação ponta a ponta com contas reais | ⚠ Depende de configuração externa |
| Validação em Windows com Credential Manager | ⚠ Depende de configuração externa |

O fallback cifrado protege o material armazenado, porém sua chave permanece no
mesmo perfil local. Para ambientes corporativos, recomenda-se integração com um
cofre de credenciais administrado pelo sistema operacional.

## 13. Requisitos para homologação e produção

Antes da liberação em produção, deverão ser providenciados:

1. registro do SmartFile como aplicação Desktop no Microsoft Entra;
2. definição dos tenants e tipos de conta Microsoft autorizados;
3. configuração do redirect loopback permitido;
4. criação de cliente OAuth Google do tipo Desktop;
5. ativação da Google Drive API e configuração da tela de consentimento;
6. contas exclusivas de homologação, sem documentos pessoais ou corporativos
   sensíveis;
7. execução da matriz real em Linux e Windows;
8. testes de expiração, revogação, quota, throttling, arquivo grande, perda de
   rede, proxy, MFA e reconexão;
9. aprovação da política de armazenamento de credenciais;
10. registro das evidências da homologação real.

Client IDs e configurações públicas deverão ser fornecidos por recurso
empacotado, ambiente ou configuração administrativa. Tokens, refresh tokens,
segredos, códigos de autorização e caches não deverão ser versionados nem
registrados em logs.

## 14. Avaliação de segurança

| Controle | Resultado | Classificação |
|---|---|---|
| Token em texto puro no SQLite | Não encontrado | ✔ Validado em ambiente real |
| Token em logs ou auditoria | Não encontrado | ✔ Validado por testes automatizados |
| Credencial no repositório | Não encontrada | ✔ Validado por testes automatizados |
| Armazenamento no keyring | Operacional | ✔ Validado em ambiente real |
| Remoção local de token | Coberta | ✔ Validado por testes automatizados |
| Fallback cifrado e migração | Cobertos | ✔ Validado por testes automatizados |
| Revogação remota | Ausente | ✖ Não implementado |

## Adendo — Administração OAuth e exclusão de contas

Após a emissão inicial deste relatório, foram implementados e validados:

- exclusão da própria conta mediante senha atual e confirmação textual;
- anonimização dos dados pessoais, revogação de sessões e remoção de vínculos;
- bloqueio da exclusão quando for necessária transferência de propriedade;
- remoção do login de nuvem, tokens locais e cache OAuth não compartilhado;
- preservação dos documentos locais e dos registros de auditoria;
- botão **Configurar provedor** exclusivo do administrador global;
- separação entre `is_superuser` e o papel `ADMIN` de uma organização;
- migration 11, que garante um administrador global em instalações existentes;
- instruções administrativas específicas para Microsoft Entra e Google Cloud.

O total da suíte após as correções OAuth passou para 183 testes aprovados.

## 15. Conclusão técnica

A Cloud Layer apresenta arquitetura coerente com o modelo local-first do
SmartFile e, após as correções descritas, demonstrou estabilidade nos testes
automatizados. A suíte de 183 testes foi aprovada, assim como compilação,
integridade de dependências e verificações de qualidade do diff.

Foram confirmados em ambiente real o keyring, o callback loopback, a detecção de
porta ocupada e a disponibilidade dos endpoints públicos. Não houve autenticação
com conta real porque o ambiente não dispunha de Client IDs OAuth nem contas
vinculadas.

### Classificação final

**⚠ DEPENDE DE CONFIGURAÇÃO EXTERNA — APROVADA TECNICAMENTE PARA HOMOLOGAÇÃO,
MAS NÃO APROVADA AINDA PARA PRODUÇÃO COM CONTAS REAIS.**

A aprovação para produção deverá ocorrer somente após a execução e documentação
da matriz de homologação real descrita neste relatório.

## 16. Termo de aceite

| Responsabilidade | Nome | Data | Assinatura/aceite |
|---|---|---|---|
| Elaboração técnica |  | 14/07/2026 |  |
| Revisão técnica |  |  |  |
| Homologação OneDrive |  |  |  |
| Homologação Google Drive |  |  |  |
| Aprovação para produção |  |  |  |

## 17. Referências

- Microsoft MSAL Python — aquisição de tokens:
  <https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens>
- Microsoft Graph — respostas de erro:
  <https://learn.microsoft.com/en-us/graph/errors>
- Microsoft Graph — sessão de upload:
  <https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession>
- Google OAuth para aplicações instaladas:
  <https://developers.google.com/identity/protocols/oauth2/native-app>
- Google Drive — uploads:
  <https://developers.google.com/workspace/drive/api/guides/manage-uploads>
- Google Drive — tratamento de erros:
  <https://developers.google.com/workspace/drive/api/guides/handle-errors>
- Documento técnico complementar: `docs/CLOUD_VALIDATION_REPORT.md`.
