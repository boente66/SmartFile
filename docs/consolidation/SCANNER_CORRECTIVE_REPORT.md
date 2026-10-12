# Fechamento corretivo — geometria nas bordas da aquisição

Data: 12/10/2026. Escopo limitado ao scanner; QR offline fica para uma tarefa
posterior. Sem acesso à internet e sem nova aquisição física nesta preparação.

## Base preservada

- HEAD: `051dab7c24df4c50489e61f87b913c2c85fec684`, main, working tree da rodada anterior preservado.
- Versão `0.9.0-beta.6`; schema 22; nenhum commit ou push.
- Base anterior: 482 testes passando. Antes das alterações corretivas, os 51
  testes de geometria existentes passaram.
- Não alterados nesta rodada: Multicloud, Solicitações/Entregas, preferências,
  som/animação, QR, packaging, assinaturas, banco ou versão.

## Causa e correção

A regra anterior tratava qualquer canto junto ao limite da imagem como corte,
reduzindo todos esses casos a confiança 0,55/PARTIAL. Isso não distingue uma
borda inteira alinhada ao limite da aquisição de um canto truncado/oblíquo.

A detecção agora refina as linhas do contorno com ajuste robusto, evitando usar
pontos da moldura como evidência de uma borda inclinada. Uma interseção fora da
captura fica registrada como possível corte, e os pontos do overlay permanecem
sempre dentro da imagem.

Uma ou duas bordas coincidentes só recebem `DETECTED/COINCIDENT` quando todas
as evidências são consistentes:

- todos os contatos pertencem a lados inteiros alinhados à mesma borda da captura;
- pelo menos dois lados da folha permanecem visíveis, com contraste coerente
  em pelo menos 80% das amostras válidas por lado
  (21 posições independentes, com pelo menos 15 válidas);
- não há extrapolação da borda visível para fora da captura nem perspectiva suspeita;
- há medição física confiável e correspondência inequívoca com um padrão dentro
  da tolerância já existente, simultaneamente absoluta/relativa;
- se DPI efetivo e área física estiverem disponíveis, ambos concordam dentro
  de 1,2%, independentemente do formato candidato;
- a confiança inicial, derivada do contraste/área, já é suficiente.

O número de confiança **não recebe floor, boost ou multiplicador** para promover
um resultado. Falta de evidência, contato isolado de um canto, dimensões incompatíveis,
DPI solicitado/ausente, conflito entre metrologias ou corte real preservam PARTIAL,
medidas estimadas/desconhecidas e fallback seguro. Nenhum tamanho é corrigido para
210 × 297 por receber o nome A4.

A separação morfológica de faixas estreitas do ADF permanece na análise reduzida.
Orientação, deskew, perspectiva, tolerâncias gerais, transformações não destrutivas
no PDF e cálculo manual pelos cantos mantêm suas regras anteriores.

Campos adicionados apenas ao resultado de domínio: `boundary_status` e
`boundary_evidence`, para diagnosticar COMPLETE/COINCIDENT/INCOMPLETE. Sem schema.

## Regressões específicas

Novo arquivo `tests/test_document_geometry_capture_edges.py`:

- A4 e Carta no limite superior, lateral e com duas bordas coincidentes;
- Carta encostada nos dois limites laterais, com topo/base visíveis;
- A4 com faixas estreitas do fundo de ADF;
- recibo estreito interno e recibo no limite, sem conversão para padrão;
- página realmente cortada, inclusive borda inclinada atravessando a captura;
- folha que continua além da altura adquirida;
- Personalizado 205 × 290, 209,3 × 303,6, 220 × 310 e 215 × 420;
- ausência de medição confiável, DPI/área contraditórios e Paisagem;
- confiança não elevada por coincidência de borda e origem preservada.

`tests/test_scanner_geometry_verification_script.py` verifica replay sem rede,
formato esperado sem influência no detector, milímetros desconhecidos quando
faltam metadados e recusa de sobrescrever a origem/pasta anterior.

## Captura física anterior: replay, não nova homologação

O replay é exclusivamente local, usando a captura e seus metadados já disponíveis.
A imagem não foi mostrada a serviço de IA nem enviada para fora do computador.

A captura anterior **continua PARTIAL**, aproximadamente 209,26 × 303,64 mm,
confiança 0,55, Personalizado/Retrato, fonte estimada. A nova evidência registra
borda visível que extrapola a captura, canto truncado/inclinado e ausência de
correspondência física inequívoca com A4. Esses dados não permitem assumir
297 mm sem forçar o resultado ou introduzir uma calibração não demonstrada.

Isso não aprova o caso antigo como A4. O segundo teste usa uma folha inteira,
alinhada às guias, e precisa demonstrar a geometria fisicamente consistente.
A saída segura do replay preserva o original e tem MediaBox 210 × 297 mm.

## Script e roteiro para o único segundo teste

`verify_scanner_geometry.py` agora suporta captura ou replay offline, com
original, hash, medidas/evidências e avaliação automática PASS/REVIEW. O formato
esperado é avaliado depois da detecção e nunca passado ao detector. Cada execução
exige pasta nova.

[Preparação e comando do segundo teste](SCANNER_SECOND_HOMOLOGATION.md).

## Validação

- Suíte completa: **506 passed em 403,97 s (6 min 43 s)**; base de 482 preservada,
  com 24 regressões adicionais. Os testes de LAN usaram somente loopback local,
  fora da restrição de sockets do sandbox; sem consulta à internet.
- `venv/bin/python -m compileall -q app scripts/verify_scanner_geometry.py`: passou.
- `venv/bin/python -m pip check`: No broken requirements found.
- `git diff --check`: passou.
- Versão `0.9.0-beta.6`, schema 22 e HEAD inicial mantidos; sem commit/push/release.
- Replay antigo: homologation REVIEW; original preservado; PDF A4 real verificado.

**Segunda homologação física pendente.** A correção está preparada e testada,
mas não se declara a detecção física A4 aprovada antes da única nova aquisição
combinada e da avaliação de seu resultado. QR offline permanece adiado.


## Segunda homologação física — resultado real

Após o usuário confirmar “pronto”, foi executada **uma única aquisição**
no dispositivo local previamente identificado, 300 dpi, Color, ADF. Sem internet,
upload, nova tentativa automática, commit ou push.

- Aquisição: 27,34 s; imagem original 2550 × 5100 px.
- DPI efetivo reportado: 300 × 300; área física da aquisição: 215,9 × 431,8 mm.
- A consulta preliminar de capabilities retornou perfil vazio/UNKNOWN; a aquisição
  retornou DPI e área física. Essa limitação da consulta não foi ocultada.
- Detector: preview 500 × 1000, 3370,12 ms nesta execução fria.
- Resultado: **PARTIAL / INCOMPLETE**, confiança **0,55**; **CUSTOM**, Retrato;
  aproximadamente **207,71 × 300,66 mm**, fonte **ESTIMATED**.
- Evidências: canto truncado/inclinado, lados visíveis insuficientes, ausência de
  correspondência física inequívoca com padrão, fronteira visível instável.
- Homologação: **REVIEW — não aprovada como detecção automática A4**.
- PDF: MediaBox **210 × 297 mm**, saída segura e proporcional.
- Original e SHA-256 conferidos após a geração do PDF.

Artefatos reais, somente locais: `/tmp/smartfile-hp3700-second-check/source.png`,
`a4.pdf` e `measurement.json`. Não se alterou nem reaproveitou como saída a pasta
original da primeira homologação.

**O objetivo de aprovação física continua pendente.** Os testes sintéticos e
as regras de coincidência passaram, mas isso não substitui este resultado real.
Não foi ampliada a tolerância, aumentada a confiança ou substituída a medição
pela informação de que a folha inserida é A4. Não haverá nova aquisição sem
combiná-la com o usuário. Antes de propor outro teste físico, a investigação pode
continuar offline com estas duas capturas e seus metadados, preservando os originais.
