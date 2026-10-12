# SmartFile — consolidação Multicloud, scanner, solicitações e QR

Data: 12/10/2026. Consolidação autorizada para commit/push na main, sem publicação de release.


## Fechamento da etapa — aprovação provisória do scanner

Por decisão do usuário, a captura física e a geração segura de PDF foram aprovadas
para esta entrega. Não há nova aquisição nem refinamento adicional do detector
nesta rodada. As correções já verificadas foram preservadas; geometria incerta
continua em `PARTIAL/REVIEW`, sem forçar A4 por tolerância ou informação do usuário.

```text
Scanner físico: homologado para captura e geração correta de PDF.
Reconhecimento automático universal do tamanho da folha:
funcionalidade experimental/assistiva, ainda não homologada para todos os formatos.
```

O original permanece preservado, e as capturas físicas produziram PDF com MediaBox
210 × 297 mm. Isso não homologa o reconhecimento automático universal. A investigação
de tamanho de papel será retomada separadamente. QR Code sem dependência obrigatória
de URL pública é o próximo item pendente, fora deste fechamento.

Versão `0.9.0-beta.6` e schema **22** mantidos. O checkpoint `2997f10` preserva a
consolidação inicial; o fechamento incorpora também a correção mínima de amostragem
de contornos e escala da abertura morfológica descrita em
[ADF_OFFLINE_DIAGNOSIS.md](ADF_OFFLINE_DIAGNOSIS.md). Os resultados anteriores abaixo
são o histórico de validação; a suíte completa foi repetida para o fechamento.

## Base e auditoria

- Repositório: `boente66/SmartFile`; main atualizada com `git pull --ff-only` (`Already up to date`).
- HEAD inicial: `051dab7c24df4c50489e61f87b913c2c85fec684`.
- Versão pública mantida: `0.9.0-beta.6` (`app/version.py`).
- `CURRENT_SCHEMA_VERSION`: **22**, sem migração ou alteração do schema.
- Suíte inicial iniciada antes das modificações: **408 passaram, 5 falharam exclusivamente pelo bloqueio de sockets no sandbox**, em 319,59 s. Os 15 testes do arquivo de entregas passaram ao repetir fora do sandbox. O Python do sistema não tem PyQt6/argon2; todas as validações efetivas usam `venv/bin/python`.
- Auditados os controllers/views de montagem, provedores Google/OneDrive, workspace de captura, serviços SANE/TWAIN, composição PDF, serviços de solicitações/entregas, coordinator LAN, assinatura A1/manuscrita e specs de distribuição. Os serviços existentes foram reutilizados.

## Multicloud

A construção do diálogo emitia `browse_requested` antes de conectar o controller. Agora a ordem é construir → conectar sinais → `load_root()` → abrir. Sem sleep, processEvents, timer de correção ou retry visual.

As respostas são associadas ao diálogo, organização, conta e geração de carregamento. Troca de conta, inclusive retorno à mesma conta, fechamento ou troca de organização invalida respostas antigas. Expansões independentes não se anulam. Todos os workers ativos são mantidos até terminar; o spinner termina em sucesso, vazio, erro e fechamento.

Google Drive e OneDrive mantêm os métodos existentes que percorrem `nextPageToken`/`nextLink`. A árvore usa os metadados reais e a seleção retorna `metadata.remote_id`. Montagem e atualização do espelho continuam apenas com metadados: sem upload, download de conteúdo, criação, movimentação, exclusão remota ou importação automática para GED.

Testes: ciclo inicial, vazio/erro, respostas antigas, conta/organização, fechamento, expansões paralelas e regressão de montagem zero-copy existente. Contas reais de Google/OneDrive não foram consultadas nesta sessão.

## Scanner e Captura/PDF

`DocumentGeometryService` e `DocumentGeometryResult` formam a camada de domínio local. A análise usa preview de até 1000 pixels no maior lado: grayscale, suavização, Canny, threshold/Otsu, fechamento/abertura morfológica, contornos, quadriláteros convexos e pontuação por área e contraste de borda. A abertura separa faixas estreitas do fundo do ADF. O original permanece preservado.

O modelo mantém cantos originais/normalizados, largura/altura em pixels, dimensões físicas opcionais, fonte de medição, formato, orientação, inclinação, perspectiva, confiança, estado, possível corte, resolução analisada e tempo. Coordenadas inválidas, cruzadas ou com área insuficiente são rejeitadas.

Fontes: área física do backend corroborada pelos pixels (`DEVICE_GEOMETRY`), DPI efetivo (`SCANNER_DPI`), calibração fornecida ao serviço (`CALIBRATED`), DPI solicitado/medidas com perspectiva (`ESTIMATED`), ou `UNKNOWN`. Sem base física não há milímetros inventados. Estimativas têm `≈`; classificações usam simultaneamente tolerâncias absoluta e relativa, com exigência de confiança. A4, Carta, Legal, A5 e A3 são distintos; Ofício não recebe alias Legal; demais dimensões são Personalizado.

Orientação é calculada pela folha: Retrato, Paisagem ou indeterminada/quadrada. A orientação do conteúdo não é inferida por OCR e Paisagem não é convertida compulsoriamente para Retrato.

O worker existente `CapturePdfWorker` executa a análise, com geração, cancelamento e proteção contra resultados antigos. Troca de página não muda a página exibida por causa de um resultado antigo; remoção/limpeza/redetecção/fechamento invalidam o trabalho apropriado. Geração de scan é independente da edição manual, evitando perder uma nova captura por editar outra página. Resultados ficam cacheados no modelo da página.

Quatro alças azuis numeradas permitem ajuste livre; o controller recalcula imediatamente formato, medidas e orientação. Zoom, tamanho do widget e rotação convertem as coordenadas normalizadas. “Detectar bordas” volta à origem; “Redefinir” restaura a área original. O PDF aplica corte/deskew/perspectiva à origem, uma única vez, quando há confiança suficiente; um contorno parcial não altera silenciosamente a imagem. Falha do detector conserva o scan e o enquadramento manual.

Saída padrão: MediaBox A4 real, 210 × 297 mm, imagem proporcional e margens. Saída avançada: tamanho detectado somente com fonte e confiança suficientes, limites físicos seguros e sem corte suspeito; caso contrário A4 seguro. PDFs previamente importados mantêm suas páginas e rotação.

Testes sintéticos: retrato/paisagem A4 e Carta, A5, recibo, quadrado, inclinação, perspectiva, baixo contraste, fundos claros/escuros, folha quase completa, ausência de documento, faixas de fundo do ADF, tolerâncias, DPI inválido/ausente, pixel → mm, quadriláteros inválidos, MediaBox, fonte preservada e descarte de resultados antigos.

### SANE, TWAIN e HP 3700

SANE lê units/constraints e opções de resolution/source/tl-x/tl-y/br-x/br-y/page-width/page-height quando disponíveis. A resolução lida de volta é separada da solicitada. `ScanCapabilities` registra fontes, resolução, cor, geometria, máximos e suporte a área customizada. Não se infere formato da folha a partir das capacidades.

TWAIN moderno e legado preservam DPI e agora aplicam também cor/fonte quando suportados. A resolução efetiva vem de `TW_IMAGEINFO`/`GetImageInfo`, em vez do DPI solicitado ou de defaults do bitmap. O loop próprio do backend permite chegar ao estado de transferência. Testes com adaptadores simulados verificam DPI, cor, fonte e metadados efetivos. Referência técnica: [pytwain](https://pytwain.readthedocs.io/en/latest/twain.html).

A HP DeskJet 3700 foi encontrada na rede pelo SANE. Consulta real: ADF; Color/Gray; 75/100/200/300/600 dpi; área máxima 215,9 × 431,8 mm. Com A4 retrato inserido e confirmado pelo usuário, foi feita **uma captura real local**, a 300 dpi: 2550 × 5100 pixels, aproximadamente 26,18 s para aquisição.

O backend entregou toda a área de aquisição, inclusive o fundo do alimentador. O primeiro contorno era uma faixa do fundo; isso motivou o teste de regressão e a separação morfológica. A análise final encontrou a região principal, mas duas bordas coincidem com a captura: **PARTIAL**, confiança 0,55, possível corte, aproximadamente 209,3 × 303,6 mm, Personalizado/Retrato, medição **estimada**. O original foi preservado e a saída A4 segura foi gerada. **Esse caso não foi homologado como detecção automática A4 exata.** Não foi usado o formato informado pelo usuário para forçar a classificação.

A4 paisagem não cabe transversalmente na largura máxima de 215,9 mm desse ADF. Carta, recibo, folha menor, inclinação e deslocamento têm cobertura sintética, mas não homologação física nesta sessão. Windows/TWAIN real também requer equipamento/ambiente Windows.

### Performance observada

Captura real de 2550 × 5100, analisada em **500 × 1000**, 10 repetições locais: **353,30 ms de média**, 334,85 ms de mediana, 288,08–544,19 ms. Inicialização fria anterior: 962,26 ms. Aplicação ao estado/overlay do controller: 20 repetições, média **0,028 ms**, máximo 0,122 ms; exclui refresh do monitor e desenho posterior. A geração PDF é outra operação em background; a medição com carga concorrente foi de aproximadamente 17,16 s para o original completo de 13 MP.

São medições deste ambiente, com build/testes concorrentes, não uma garantia fixa para todo hardware. Imagem e PDFs reais ficaram somente em `/tmp/smartfile-hp3700-check`; nenhum scan foi enviado à nuvem, API, IA ou servidor de imagens. `scripts/verify_scanner_geometry.py` permite repetir a verificação local com uma folha preparada pelo usuário.

## Solicitações e Entregas

As nove abas principais foram substituídas por `QStackedWidget` e `FlowStepIndicator`: círculos desenhados, linhas, contadores, clique/teclado, foco visível e badge textual. Entrada → Atendimento → Preparação → Entrega → Finalizadas. Criadas por mim, Recebidos, Enviados, Histórico e LAN permanecem acessos secundários. A cesta aparece no preparo contextual; ações de destinatário, peer, mensagem, protocolo, retry, visualização, download, GED e comprovante continuam disponíveis.

Estados de request permanecem distintos de delivery: OPEN/IN_PROGRESS/ATTENDED/DELIVERING/COMPLETED/CANCELLED; DELIVERED de request permanece em Entrega até conclusão. A apresentação OVERDUE preserva agora o status operacional para o agrupamento. Nenhuma mudança na máquina de estados, recebimento por tamanho/SHA-256 ou promoção segura dos arquivos de delivery.

`RequestNotificationService` persiste IDs conhecidos, leitura e preferências em `app_settings`, scoped por organização e usuário, sem migração. Selecionar uma solicitação marca vista sem mudar OPEN. Snapshot inicial não toca; ID novo recebido pelo usuário toca uma única vez; refresh, atualização, filtro e reabertura não repetem. A recepção LAN emite evento pelo coordinator e há observação fora da View mesmo com workspace fechado. Badge também aparece na barra lateral. Trocar organização limpa os painéis e restaura o estado persistido do novo escopo.

Som próprio, duas notas, 0,65 s, uma execução via QSoundEffect. Animação: halo suave alternando vermelho/azul ao redor de Entrada por aproximadamente 3 s; sem modal, estrobo ou flash da tela inteira. Preferências de som/animação independentes. Sirene não é usada para atraso, prazo ou retry.

BUSINESS-only e permissões granulares existentes foram mantidos. Testes cobrem navegação, etapas, contadores, badge, leitura, refresh, IDs sucessivos, preferências independentes, persistência/reinício, isolamento, ciclo, perfis e a regressão LAN/offline/receipts.

## Parte E — QR, assinatura e Gov.br

QR opcional nas assinaturas A1 e manuscritas, com URL HTTPS configurável, página, X/Y e tamanho. Os formulários têm rolagem para que as opções e botões permaneçam acessíveis em telas menores. O usuário confirmou a solução configurável; nenhum endereço de hospedagem foi fornecido. Não há publicação automática de documentos. O QR precisa apontar para o documento final ou uma página real de verificação disponibilizada pelo usuário.

No fluxo A1, o QR é incorporado **antes** da assinatura criptográfica; o teste verifica integridade do PDF assinado, leitura exata da URL e preservação da origem. Inserir QR em PDF já assinado é recusado, preservando assinaturas anteriores. A marca manuscrita continua visual: QR ou SHA-256 não provam, sozinhos, a identidade do autor. O serviço de evidência local distingue integridade/confiança e não confirma identidade de uma marca visual.

Há acesso ao assinador oficial Gov.br e ao VALIDAR na validação. O documento pode ser assinado no portal oficial, baixado e reaberto no SmartFile. **Não foi implementado login/API de assinatura Gov.br nem instalado um conjunto novo de raízes de confiança ICP-Brasil/Gov.br.** A validação local mantém resultados UNTRUSTED/INDETERMINATE quando não há cadeia comprovada; não atribui validade jurídica automática.

O [VALIDAR oficial](https://www.gov.br/pt-br/servicos/realizar-validacao-de-assinaturas-eletronicas-validar) aceita documentos ICP-Brasil/Gov.br por arquivo, URL ou QR. A [orientação do ITI](https://validar.iti.gov.br/duvidas.html) distingue assinatura digitalizada de assinatura criptográfica. A autenticação de terceiros exige o arquivo eletrônico assinado e seu contexto de confiança, além de disponibilização real no endereço configurado.

## Packaging

- OpenCV headless já estava instalado como dependência transitiva de pdf2docx (5.0.0.93). Foi explicitado `opencv-python-headless>=4.10,<6`; sem OpenCV com GUI ou outro sistema de temas. QR reutiliza ReportLab/Pillow existentes.
- `assets/sounds/request_alert.wav` é síntese própria, com licença vinculada à licença MIT do repositório. A pasta assets já é incluída integralmente nas duas specs e pelo Inno Setup.
- Specs Linux/Windows coletam `reportlab.graphics.barcode` porque os widgets usam imports dinâmicos. Essa necessidade foi identificada por falha real no smoke do bundle e corrigida.
- Build PyInstaller Linux onedir em `/tmp/smartfile-consolidation-dist/SmartFile`, sem sobrescrever artefatos de release. Verificação do PYZ confirmou o detector de página parcial e os círculos desenhados.
- **Auditoria ABI Ubuntu 22.04 reprovada neste host Ubuntu 24.04**: libmount exige GLIBC 2.38 e libicu exige GLIBCXX 3.4.30, acima de 2.35/3.4.29. Não é uma aprovação de compatibilidade Ubuntu 22.04. O build reproduzível deve passar pelo runner Ubuntu 22.04 existente. Não foi instalado/publicado um .deb deste host.
- Windows: specs, Inno e testes de packaging verificados; execução/build nativo Windows não realizados neste Linux.

## Validação inicial da consolidação (histórico)

- `venv/bin/python -m pytest -q`: **482 passed**, 358,98 s (5 min 58 s), com sockets locais autorizados para LAN. Execuções anteriores de regressão também passaram (474 e 480 testes).
- Após os ajustes finais de navegação, rolagem e coleta do QR: **8 testes de navegação/picker** e **46 testes de assinaturas/packaging** passaram; não houve alterações posteriores nessas implementações.
- `venv/bin/python -m compileall -q app run.py scripts/verify_scanner_geometry.py`: passou.
- `venv/bin/python -m pip check`: **No broken requirements found**.
- `git diff --check`: passou.
- Banco temporário novo: schema **22**, `PRAGMA foreign_key_check` retornou `[]`. Nenhum banco real do usuário foi alterado pelos testes.
- Build Linux PyInstaller final: passou, aproximadamente 479,4 s. O PYZ foi inspecionado para confirmar código atualizado do detector parcial, círculos, navegação secundária, formulários com rolagem e módulos dinâmicos de QR.
- Binário frozen: `QT_QPA_PLATFORM=offscreen .../smartfile --smoke-test` **exit 0**, após correção do import dinâmico ReportLab. Exercita banco temporário, detector OpenCV, geração de QR e import de QtMultimedia, sem venv em runtime.
- ABI Ubuntu 22.04: **reprovada**, conforme limitação de packaging acima; build Windows e homologações físicas restantes **não executados**.
- MediaBox do PDF da captura física: **210,000 × 297,000 mm**.
- Ao término da validação inicial, HEAD ainda era a base `051dab7c24df4c50489e61f87b913c2c85fec684`; posteriormente foi criado o checkpoint `2997f10` e autorizado o fechamento com commit/push. Versão `0.9.0-beta.6` e schema 22 mantidos.
- **Nenhuma release publicada.** Não houve upload de scan ou publicação automática de documento para o QR.

## Revisão visual

Imagens de demonstração sintética, sem conteúdo do scan físico:

- [Scanner com geometria A4 e quatro alças](scanner-preview.png)
- [Solicitações com círculos, contadores e badge](requests-flow.png)


## Validação de fechamento

- Suíte completa repetida: **513 passed em 757,33 s (12 min 37 s)**, exit 0.
  A base inicial de 482 testes foi preservada, com regressões adicionais do scanner.
- `compileall` de app, run.py e scripts de homologação/diagnóstico: passou.
- `pip check`: **No broken requirements found**.
- `git diff --check`: passou.
- Commit/push autorizado na main, incorporando o checkpoint e o fechamento; a
  identificação final está no histórico Git. Sem tags ou publicação de release.
- Nenhuma aquisição física adicional. Nenhum scan real incluído no Git.
- Compatibilidade ABI Ubuntu 22.04 e build nativo Windows continuam com as
  limitações de packaging registradas acima; esta suíte não as homologa.
