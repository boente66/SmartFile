# SmartFile 0.9.0-beta.9 — auditoria e correções

Esta atualização corrige falhas verificadas em permissões, publicação de arquivos,
concorrência, cancelamento e navegação entre organizações. Não há migração adicional:
o schema permanece 23.

- Importação e operações de documentos respeitam o papel na organização de destino.
- Conversão, exportação, assinatura e backup preservam saídas já existentes.
- Recepção simultânea usa temporários independentes e não invalida um arquivo já verificado.
- Importações e downloads executam fora da interface; respostas antigas não atualizam outra organização.
- A saída avisa sobre páginas não salvas. Salvar aguarda detecção e renderização.
- Diálogos de importação ganham contraste; metadados não interpretam marcação HTML.
- Documentação oficial, PDFs e capturas acompanham os pacotes Linux e Windows.

Scanner físico: homologado para captura e geração correta de PDF.
Reconhecimento automático universal do tamanho da folha: funcionalidade
experimental/assistiva, ainda não homologada para todos os formatos.
Não houve nova aquisição física nem alteração das tolerâncias do detector.

[Relatório da auditoria](AUDIT_0.9.0-beta.9.md).
Faça backup antes de atualizar. Confira os SHA-256 anexos à release.

Validação local: **620 testes aprovados** (578 da base + 42 regressões).
Compileall, pip check, sintaxe Bash e diff conferidos.
