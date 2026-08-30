# Relatório formal — Perfis exclusivos e acervo remoto multicloud

## 1. Diagnóstico inicial

A base estava no schema 21 e na versão pública `0.9.0-beta.3`. O mapeamento
corporativo de pastas e a sincronização oficial já existiam e foram
preservados. Foram encontrados dois vazamentos empresariais: a Sidebar criava
sempre a rota de entregas e o serviço de entrega validava permissão, mas não a
feature `document_requests`.

O OneDrive já navegava em pastas existentes. O Google Drive não possuía
navegação equivalente e usava `drive.file`, insuficiente para um inventário
de conteúdo preexistente.

## 2. Decisões arquiteturais

- `multicloud_workspace` é independente de `cloud_sync`.
- Somente `PERSONAL` e `STUDENT` possuem a nova feature.
- `BUSINESS` mantém o mapeamento corporativo existente, sem o organizador.
- Inventário remoto não usa `documents`, `folders` ou storage interno.
- Montagem e varredura são somente leitura.
- Objeto lógico e réplica são entidades distintas.
- Reconciliação persiste um plano `DRAFT`; execução exige autorização.
- Conflitos de identidade não são resolvidos por nome.

## 3. Persistência

Migration aditiva 22:

- `remote_mounts`;
- `remote_catalog_nodes`;
- `logical_cloud_objects`;
- `cloud_replicas`;
- `multicloud_plans`;
- `multicloud_plan_actions`.

Todas as tabelas operacionais carregam escopo de organização e as relações
com contas Cloud usam chaves compostas com `organization_id`. A migração
21→22 não reexecuta a migração 21 e não altera dados documentais.

## 4. Interface

Foi incluído um botão circular ao lado da árvore de pastas, visível apenas
nos perfis compatíveis. A interface oferece:

- navegação progressiva nas pastas remotas;
- montagem com explicação de que não há cópia;
- árvore **Acervo remoto** separada das pastas GED;
- estados de varredura e erro;
- atualizar espelho;
- desmontar somente local;
- comparar, revisar e autorizar propostas.

Varredura e execução de plano usam `QThread`, mantêm referência viva e usam
o sinal nativo `finished` para cleanup.

## 5. Segurança e integridade

- conta e provider são resolvidos pela organização ativa;
- resultado assíncrono obsoleto é ignorado após troca de organização;
- nenhum token é incluído no novo catálogo;
- replicação usa temporário dentro do diretório gerenciado e limpeza em
  `finally`;
- SHA-256 é calculado no conteúdo transferido;
- item de mesmo nome no destino interrompe a operação como conflito;
- arquivos nativos Google não são tratados como bytes comuns;
- ações destrutivas permanecem modeladas, mas sem executor automático.

## 6. Compatibilidade

O desenvolvimento foi validado ainda em `0.9.0-beta.3` e posteriormente
promovido para a versão `0.9.0-beta.4` para distribuição. O Google Drive requer
`drive`; contas antigas
precisam reconectar e conceder novo consentimento para montar conteúdo
preexistente.

## 7. Validação

- `pytest`: **410 passed**;
- testes LAN executados com sockets localhost habilitados: **5 passed**;
- testes novos do acervo: **6 passed**;
- `compileall`: aprovado;
- `pip check`: nenhuma dependência quebrada;
- `git diff --check`: aprovado;
- migração 21→22 e migrações legadas: aprovadas.

## 8. Limitações deliberadas

- `MOVE_FILE`, `RENAME_FILE` e `DELETE_REPLICA` não são executados nesta
  etapa, evitando operações destrutivas prematuras.
- Uma hierarquia ausente no destino não é achatada na raiz; o arquivo não é
  proposto até existir um pai correspondente seguro.
- A verificação de identidade entre algoritmos de hash diferentes permanece
  como `CANDIDATE_MATCH`, nunca como equivalência presumida.
