# Acervo remoto e espelho lógico multicloud

Disponível somente nos perfis **Pessoal** e **Estudante**. A capacidade é
controlada pela feature `multicloud_workspace`; ela não reutiliza
`cloud_sync` como chave de interface.

## Garantias de domínio

- Montar consulta e persiste metadados. Não baixa, importa, cria, move,
  renomeia nem exclui conteúdo remoto.
- O catálogo remoto é separado de `documents`, `folders` e do storage interno.
- Desmontar apaga somente o espelho local e nunca chama `provider.delete()`.
- Nome igual não comprova identidade. Hash igual produz `VERIFIED_MATCH`;
  ausência de hash produz `CANDIDATE_MATCH`; hash ou tamanho divergente
  produz `DIVERGED`.
- A comparação cria um plano `DRAFT`. Nenhuma escrita ocorre antes da
  seleção e autorização explícita do usuário.
- A replicação usa arquivo temporário, SHA-256, destino exato e limpeza em
  `finally`. Um nome já existente vira conflito; não se presume identidade.
- Conta, montagem, catálogo, objeto lógico, réplica e plano carregam
  `organization_id` e são consultados sempre nesse escopo.

## Google Drive

Ler pastas já existentes exige o escopo `drive`, pois `drive.file` permite
somente arquivos criados ou abertos pelo aplicativo. Instalações que já
conectaram Google Drive devem reconectar a conta e conceder o novo escopo
antes de montar um acervo. Tokens continuam fora do SQLite.

## Limites desta etapa

- Ações destrutivas (`MOVE_FILE`, `RENAME_FILE`, `DELETE_REPLICA`) são
  modeladas, mas não são executadas automaticamente.
- Arquivos dentro de uma pasta inexistente no destino não são achatados na
  raiz. A criação hierárquica segura pode ser planejada em etapa futura.
- Arquivos nativos do Google (Docs, Sheets e Slides) exigem exportação
  específica; não são replicados como se fossem bytes comuns.

## Fluxo de teste manual

1. Entre em uma organização Pessoal ou Estudante.
2. Conecte OneDrive e/ou Google Drive.
3. Ao lado de **Pastas**, clique no botão circular de nuvem.
4. Escolha a conta, navegue e selecione uma pasta existente.
5. Confirme que a montagem não criou conteúdo no provedor.
6. Monte uma segunda pasta com o mesmo identificador de coleção para
   compará-las.
7. Use **Comparar e planejar**, revise cada proposta e autorize apenas se
   desejar criar a réplica indicada.
8. Use **Desmontar** e confirme que os arquivos remotos permanecem intactos.
