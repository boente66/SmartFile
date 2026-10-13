# Auditoria SmartFile 0.9.0-beta.9

Data: 13/10/2026. Schema 23. Escopo: arquitetura, experiência de uso,
permissões, integridade de arquivos, concorrência e casos de uso documentados.
Método: leitura dos fluxos da aplicação, inspeção de fronteiras entre camadas,
execução da suíte existente e regressões para falhas reproduzíveis.

## Casos de uso vistoriados

| Caso | Fluxo e evidência automatizada principal |
| --- | --- |
| UC-01 | Primeiro usuário: `test_auth`, `test_auth_ui`, `test_application_layer` |
| UC-02 | Login, logout e sessão: `test_auth`, `test_auth_ui` |
| UC-02A | Recuperação com código: `test_auth`, `test_corporate_transport` |
| UC-03 | Conta adicional e administração: `test_administration`, `test_auth` |
| UC-04 | Importação, organização e exclusão: `test_document_service`, `test_document_storage`, `test_audit_regressions` |
| UC-04A | Conversão e cancelamento: `test_convert_flow`, `test_image_service`, `test_audit_regressions` |
| UC-05 | Pesquisa e visualização: `test_pdf_viewer`, `test_pdf_preview_service`, `test_document_context_actions` |
| UC-06 | Digitalização, geometria e original preservado: `test_scan_service`, `test_capture_pdf`, `test_document_geometry_capture_edges` |
| UC-07 | Manipulação de PDF: `test_pdf_tools`, `test_capture_pdf` |
| UC-08 | Assinatura A1, marca manuscrita e verificação: `test_pdf_signature`, `test_handwritten_signature`, `test_signature_verification` |
| UC-09 | Sincronização por organização/provedor: `test_multicloud_workspace`, `test_cloud_layer`, `test_document_integrity_and_cloud_isolation` |
| UC-09A | Reorganização de pastas: `test_cloud_folder_mapping`, `test_remote_mount_lifecycle` |
| UC-09B | Mapeamento OneDrive: `test_cloud_folder_mapping`, `test_cloud_oauth_security` |
| UC-10 | Troca de organização e isolamento: `test_organizations`, `test_business_feature_policy`, `test_audit_regressions` |
| UC-11 | Cota e reserva de armazenamento: `test_storage_quota`, `test_document_storage` |
| UC-11A | Capacidade da nuvem: `test_cloud_storage_quota`, `test_cloud_python_auth` |
| UC-12 | Explorador lógico e destino de importação: `test_scanner_ged`, `test_delivery_document_picker`, `test_audit_regressions` |
| UC-13 | Transporte empresarial e credenciais: `test_corporate_transport`, `test_transport_reconciliation_and_credentials` |
| UC-14 | Solicitação, prazo, entrega e notificações: `test_document_delivery`, `test_delivery_protocol`, `test_request_notifications` |
| Complementares | QR local/canônico/revogação: `test_document_validation`; backup/restauração: `test_backup`; LAN: `test_lan_discovery`; atualizações: `test_application_update`; distribuição: `test_linux_packaging`, `test_windows_packaging` |

Os nomes acima correspondem a módulos em `tests/`. A vistoria cobre os fluxos
implementados e suas falhas observadas; não constitui garantia de ausência de
qualquer defeito em todas as combinações de hardware e serviços externos.

## Problemas encontrados e correções

| Prioridade | Problema reproduzível | Correção e verificação |
| --- | --- | --- |
| Alta | Papel da organização ativa podia autorizar importação em destino com papel inferior; serviços dependiam de bloqueios visuais | Permissão verificada no serviço e na associação ao destino; testes de VIEWER e destino distinto |
| Alta | Exportação/backup/assinatura/conversão podiam substituir destino existente; cancelamento removia arquivos de nome semelhante | Temporário privado, publicação sem sobrescrita e limpeza somente de arquivos próprios; colisão, link pendente e cancelamento testados |
| Alta | Download de entrega precisava conferir organização, destinatário e integridade antes da leitura | Validação prévia de contexto, caminho, tamanho e SHA-256; regressões de acesso cruzado |
| Alta | Recepção concorrente do mesmo item compartilhava temporário; falha podia invalidar item verificado | Temporários únicos e atualização condicional do estado; teste intercalado de transferência válida/inválida nos dois sentidos |
| Alta | Janela após obtenção da conexão permitia operação juntar-se à transação de outra thread | Leitura e transações serializadas; testes determinísticos da janela com escrita e leitura |
| Média | Resultado tardio do viewer, mapeamento remoto ou importação atualizava outro contexto | Identificação de worker, documento e organização; interrupção e descarte de callbacks antigos |
| Média | Importação/download de arquivos bloqueavam a interface | Worker reutilizável, progresso e cancelamento cooperativo; destinos capturados antes da execução |
| Média | Falha de recorte podia gerar PDF com fundo inteiro sem informar | Falha explícita, original preservado e nenhuma saída publicada; salvar aguarda geometria e renderização |
| Média | Views importavam serviços, constantes e lógica de negócio | Catálogos/modelos puros, dados preparados nos controllers e teste de fronteira via AST |
| Média | Saída/logout sem aviso descartava páginas não salvas | Confirmação no fechamento, logout e exclusão da própria conta; rejeitar mantém o fluxo aberto |
| Média | Assinatura de arquivo gerenciado sugeria saída no armazenamento interno | Destino externo sugerido e validação dos diretórios gerenciados |
| Baixa | Diálogo de importação herdava texto claro sobre fundo claro; erro de imagem de assinatura escapava | Tema local legível, erro visível, verificação de formato/tamanho antes de decodificação Qt |
| Baixa | Metadados interpretavam marcação e preferências malformadas interrompiam notificações | Texto simples e recuperação segura de preferências inválidas |

As classes de serviço mantêm uso compatível sem sessão para integrações locais
confiáveis; a composição da aplicação autenticada injeta SessionContext. Isso não
é um controle de segurança contra o administrador do computador.

## Validação

- Base anterior: 578 testes aprovados.
- Novas regressões da auditoria: 42 testes aprovados, incluindo concorrência,
  integridade, permissões, arquitetura, cancelamento e legibilidade.
- Verificação focada ampliada: 152 testes aprovados antes do fechamento.
- Suíte completa local: **620 testes aprovados** em 371,75 segundos.
- Compileall, pip check, validação Bash e git diff --check aprovados.
- Resultado dos checks nativos: registrado nas notas da release,
  com links para os runs e identificação do commit dos instaladores.

## Limites e continuidade

Scanner físico: homologado para captura e geração correta de PDF.
Reconhecimento automático universal do tamanho da folha: funcionalidade
experimental/assistiva, ainda não homologada para todos os formatos.

Não houve nova aquisição física, ajuste de tolerância ou tentativa de forçar A4.
PARTIAL/REVIEW permanecem quando a evidência não permite enquadramento confiável.
Um ajuste manual é identificado como manual, sem elevar confiança automática.

OAuth real de cada provedor, servidores SMTP externos, certificados pessoais,
Word/LibreOffice e novos equipamentos exigem homologação no ambiente correspondente.
Os testes usam fixtures/adaptadores quando essas dependências não estão disponíveis.
Cancelamento é cooperativo; biblioteca externa pode terminar uma chamada antes de
responder à interrupção. LAN continua destinada a instalações autorizadas em rede
local confiável; esta rodada não adiciona um novo protocolo de transporte.

Os instaladores incluem manual, documentação técnica, relatório e capturas.
Os artefatos históricos permanecem preservados. Hashes e origem do novo build são
publicados com a beta.9.
