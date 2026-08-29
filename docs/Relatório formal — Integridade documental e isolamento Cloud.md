Relatório formal — Integridade documental e isolamento Cloud
Implementação concluída, publicada na main e distribuída nos instaladores da versão 0.9.0-beta.3.
Diagnóstico
O erro FOREIGN KEY constraint failed era causado por referências ao documento em tabelas de solicitações e entregas durante a exclusão permanente.
Também foi identificado que contas e caches OAuth poderiam ser consultados sem vinculação obrigatória à organização, criando risco de reutilização cruzada entre organizações.
Correções realizadas
Exclusão documental
- Arquivo movido para quarentena antes da exclusão.
- Operação de banco executada em transação.
- Arquivo restaurado automaticamente se a transação falhar.
- Cota liberada somente após exclusão confirmada.
- Jobs Cloud operacionais removidos.
- Vínculos de solicitação removidos por CASCADE.
- Itens de entrega preservados com document_id = NULL.
- Nome, tamanho e SHA-256 históricos preservados.
- Solicitações, entregas e comprovantes permanecem disponíveis.
- Histórico textual preservado e desvinculado do documento removido.
- Esvaziar lixeira utiliza o mesmo fluxo seguro.
- PRAGMA foreign_key_check permanece sem violações.
Isolamento Cloud
Agora possuem escopo obrigatório de organização:
- contas Cloud;
- tokens;
- caches OAuth/MSAL;
- configurações;
- pasta raiz remota;
- mapeamentos de pastas;
- cotas remotas;
- filas e jobs;
- processamento dos workers;
- callbacks assíncronos da interface.
Uma organização não pode configurar, consultar ou remover a conta pertencente a outra organização.
Migração 20 → 21
O schema foi atualizado para 21, preservando dados existentes.
Caso uma conta antiga esteja compartilhada entre organizações:
- a primeira organização mantém a credencial;
- as demais recebem registros independentes;
- tokens não são copiados;
- o estado passa para REAUTH_REQUIRED;
- o usuário deve autenticar novamente;
- caches e tokens órfãos são removidos com segurança.
Arquivos principais modificados
- Camada Cloud: cloud_manager, modelos, OAuth, autenticação Python e sincronização.
- Persistência: schema.sql, migrations.py e document_repository.py.
- Serviços: document_service.py e auth_service.py.
- Interface/controladores: proteção contra retorno assíncrono de outra organização.
- Worker de autenticação Cloud.
- Notas da versão.
- Testes Cloud, entrega, transporte, armazenamento e integridade documental.
Novo teste criado:
- tests/test_document_integrity_and_cloud_isolation.py
Testes
- Suíte local: 404 testes aprovados.
- compileall: aprovado.
- pip check: nenhuma dependência quebrada.
- git diff --check: aprovado.
- Migração real simulada do schema 20 para 21: aprovada.
- Rollback da quarentena: aprovado.
- Lixeira com documentos vinculados e comuns: aprovada.
- Isolamento entre organizações: aprovado.
- foreign_key_check: nenhuma inconsistência.
Workflows oficiais:
- Testes Python
- Pacote Linux
- Pacote Windows
O .deb foi instalado, iniciado, reinstalado e removido com preservação dos dados no Ubuntu 22.04 e 24.04.
Publicação
- Branch: main
- Commit: aa93c608a59b7371eacb8e2ed499fdb4ec34cd37
- Worktree local: limpo e sincronizado com origin/main.
- Release SmartFile 0.9.0 Beta 3
Downloads atualizados:
- Linux .deb
- Windows Setup
- Windows Portable
SHA-256:
- .deb: 3ddbb07bbe511054a37672c877b04898df03c3ad7e8c79b41b62027364dd16c0
- Setup: 3ac810c23b4fb1bf21ee014d9118991fcf1047305f9e7188fff3c967b30229b2
- Portable: df7c9e3cf2c0bfd9cd15bb774393e7eb10e937e373ac5df1aa069f5f9d352c65
Observação: os instaladores foram substituídos mantendo a mesma versão 0.9.0-beta.3. Portanto, instalações existentes não receberão alerta de “nova versão” somente por essa substituição; esse alerta ocorrerá quando for publicada uma versão numericamente superior.