# SmartFile 0.9.0-beta.10

Auditoria empresarial e identidade institucional. Schema 24.

- Eventos identificam usuário SmartFile, organização, instalação existente,
  documento, origem, horário UTC e hashes quando os bytes mudam.
- Histórico contextual e consulta administrativa BUSINESS com filtros e CSV/PDF.
- Histórico consolidado protegido contra edição/apagamento comum e preservado
  após exclusão permanente do documento.
- Workers conservam o ator e a organização de origem. Corrigida a seleção de
  permissões quando a lista de associações contém mais de um usuário.
- Modo Design BUSINESS para OWNER/ADMIN, com prévia, imagens limitadas, cores
  acessíveis, dados institucionais e compartilhamento explícito pela LAN existente.
- Comprovantes institucionais mantêm protocolo, usuários, instalações e evidências;
  o comprovante de envio não declara recebimento antes de sua confirmação.
- Consultas QR por hash mostram todos os registros. Reassociação de FK nula e
  modificação posterior dos dados de revogação são bloqueadas.
- Armazenamento físico separado de quota GED, calculado em background com cancelamento;
  backup inclui a área de recebimento.
- Manual e documentação técnica atualizados, incluídos nos instaladores.

O público declarado é empresarial adulto. Os controles não certificam conformidade
jurídica. Eventos antigos sem autor comprovável permanecem LEGACY_UNKNOWN; edição
externa via OneDrive pode ter autor desconhecido. Auditoria permanece por instalação,
sem consolidação automática dos logs. A distribuição de identidade utiliza a confiança
do transporte LAN existente.

Scanner físico: homologado para captura e geração correta de PDF.
Reconhecimento automático universal do tamanho da folha: funcionalidade
experimental/assistiva, ainda não homologada para todos os formatos.

A instalação migra o banco 23 → 24. Faça backup antes de atualizar.
Verificação e limites: [relatório empresarial](AUDITORIA_EMPRESARIAL_0.9.0-beta.10.md).
