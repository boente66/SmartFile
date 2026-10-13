# Entrega e instaladores SmartFile

Preferência definida pelo usuário em 13/10/2026: toda modificação entregue deve
ser acompanhada dos instaladores atualizados, inclusive mudanças de documentação.

1. Consolidar fontes, manuais, PDFs e versão antes de gerar os pacotes.
2. Usar versão pública superior à última publicada, permitindo detecção de
   atualização pelo aplicativo e ordenação correta pelo Debian.
3. Executar checks apropriados e validar os builds nativos de Linux e Windows.
4. Publicar .deb amd64, Setup e Portable x64 produzidos do mesmo commit funcional,
   com SHA-256 e notas que identifiquem a origem e as verificações.
5. Conferir os assets publicados antes de anunciar o fechamento. Não sobrescrever
   instaladores históricos com bytes de outra implementação usando a mesma versão.

Os bundles incluem docs e assets para leitura offline, com os PDFs ilustrados.
Documentação posterior que apenas registra os hashes e resultados da publicação
não muda os bytes já validados; deve identificar o commit usado nos instaladores.
