# SmartFile 0.9.0-beta.8 — recorte e instaladores atualizados

Atualização da beta.7: páginas digitalizadas e imagens importadas mostram o
recorte confiável na prévia antes de salvar. O mesmo enquadramento é aplicado ao
PDF e à importação no GED, sem a margem artificial de 8 mm.

- Mostrar documento recortado inicia marcado. Desmarque para ajustar as alças
  sobre o original e marque novamente para conferir o resultado.
- Salvar, extrair, dividir e adicionar ao GED aguardam o fim da detecção.
- PARTIAL/REVIEW e possível corte automático preservam a área original para
  revisão; Redefinir restaura o enquadramento original.
- Formato do papel de saída permanece separado do recorte. A proporção é
  preservada, sem esticar a imagem para preencher a folha.
- Manual, documentação técnica e capturas ilustrativas acompanham os instaladores
  Linux amd64 (.deb), Windows x64 Setup e Portable.

QR local, Multicloud, Solicitações e Entregas e notificações permanecem disponíveis.
Schema **23** permanece inalterado. Faça backup antes de atualizar e mantenha
cópias independentes dos documentos. Quem vem da beta.7 não tem nova migração.

Scanner físico: homologado para captura e geração correta de PDF.
Reconhecimento automático universal do tamanho da folha: funcionalidade
experimental/assistiva, ainda não homologada para todos os formatos.
Nenhuma nova aquisição física ou alteração no detector universal nesta rodada.

A release usa uma versão nova para que o SmartFile reconheça a atualização.
Confira os arquivos SHA-256 anexos antes de instalar. Os pacotes Debian têm
versão interna 0.9.0~beta8; o nome público usa 0.9.0.beta8.

[Manual e documentação oficial](https://github.com/boente66/SmartFile/blob/main/docs/README.md).
