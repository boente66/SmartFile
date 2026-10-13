# SmartFile 0.9.0-beta.7 — QR de validação e consolidação

Esta beta adiciona uma camada de verificação de integridade documental e consolida
Multicloud, Solicitações e Entregas, notificações e captura/PDF.

## QR sem URL pública obrigatória

- QR local e código digitável identificam um registro na organização ativa.
- O PDF final é preservado como original registrado; SHA-256 é calculado depois
  da assinatura, sem inserir o hash no próprio QR.
- A central “Validar documento por QR/código” aceita URI, token, código ou arquivo,
  compara os bytes e permite abrir/baixar o original registrado.
- QR copiado continua apontando ao original associado; uma cópia alterada retorna
  divergência de hash. Divergência não é automaticamente classificada como fraude.
- A1/PAdES é verificado separadamente da integridade e da confiança da cadeia.
  Assinatura manuscrita permanece visual.
- Revogação preserva os bytes e o histórico. Exclusão do GED preserva o registro
  e seu artefato canônico. Backup inclui artefatos e comprovantes.
- Base HTTPS opcional prepara o QR web futuro, sem publicar documentos. Sem serviço
  externo, a câmera de um celular não consulta automaticamente a instalação local.

## Consolidação

- Montagem Multicloud com carregamento inicial e descarte de respostas antigas.
- Novo fluxo de Solicitações e Entregas, contadores e alertas de recebimento.
- Captura física, preservação do original e saída segura em PDF A4 homologadas.
- Reconhecimento automático universal de tamanho de papel permanece experimental/
  assistivo, ainda não homologado para todos os formatos; estados PARTIAL/REVIEW
  são mantidos quando a geometria não é confiável.

## Banco e atualização

Schema **23**, com migração 22 → 23 e retenção de registros de validação. Faça backup
administrativo antes de atualizar. Uma instalação antiga com schema 22 não abre um
banco já migrado para 23; restauração deve utilizar backup anterior compatível.

Instaladores previstos: Linux amd64 (.deb), Windows x64 Setup e Portable.
Os artefatos publicados são produzidos pelos respectivos runners nativos e têm
checksums. Nenhum documento, scan ou credencial é incluído nos instaladores.

## Limites de confiança

O QR é um localizador, não uma prova de autenticidade por aparência. Hash confirma
bytes, não identidade ou validade jurídica automática. O domínio de validação
impede sobrescrita pela aplicação e confere o original antes de disponibilizá-lo;
comprometimento simultâneo do banco e do sistema de arquivos por um administrador
local continua fora dessa garantia. Serviço web público, hosting e publicação
explícita de documentos ficam para uma etapa futura.
