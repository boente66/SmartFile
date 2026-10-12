# Diagnóstico offline das duas capturas ADF — checkpoint antes da correção

12/10/2026. Checkpoint local `2997f10`, branch
`checkpoint/consolidation-scanner-20261012`. Sem push/release. Imagens originais
preservadas, sem terceira aquisição, internet, upload ou envio de scan a IA.

Artefatos visuais completos locais, fora do Git:
`/tmp/smartfile-adf-offline-diagnostics-20261012/index.html`.
Cada captura contém original, três previews, grayscale, denoise, Otsu, Canny,
fechamento/abertura, contornos numerados por etapa, candidatos aceitos, quad inicial,
linhas e pontos descartados, interseções antes do clamp, quad final, overlay na
origem, CSV de projeções, scanlines, JSON por borda e comparação de escalas.

**Este checkpoint de diagnóstico foi escrito antes de modificar a heurística.**
A classificação foi desabilitada por subclassificação no replay instrumental.
Não há `expected_format` no diagnóstico; A4 é usado abaixo apenas como referência
posterior para quantificar o erro já observado na homologação.

## Metrologia: conversão de pixels correta, contorno não significa folha física

2550 × 5100 px a 300 × 300 dpi = 215,9 × 431,8 mm. A área física do backend
concorda com os pixels; não há erro de conversão mm/px demonstrado. Cada pixel
original vale 0,084667 mm. O preview 500 × 1000 vale 0,4318 mm/pixel em ambos os eixos.

A fórmula de largura usa a média de TOP e BOTTOM; altura usa RIGHT e LEFT. O
problema já existe nos segmentos escolhidos, antes da classificação.

## Comparação por borda — preview 500 × 1000

| Medição | Captura 1 | Captura 2 |
|---|---:|---:|
| TOP, mm | 209,531 | 210,128 |
| RIGHT, mm | 299,845 | 298,547 |
| BOTTOM, mm | 208,992 | 205,302 |
| LEFT, mm | 307,444 | 302,769 |
| Largura média, mm | 209,262 | 207,715 |
| Altura média, mm | 303,645 | 300,658 |
| TOP, desvio do eixo | +1,961° | +0,943° |
| RIGHT, desvio do eixo | +0,330° | +1,833° |
| BOTTOM, desvio do eixo | −0,118° | −0,245° |
| LEFT, desvio do eixo | +0,244° | +0,899° |
| Candidato escolhido | #6, OTSU_OPEN | #6, OTSU_OPEN |
| Boundary publicado | INCOMPLETE | INCOMPLETE |

A altura extra é a média de duas bordas verticais desiguais: na captura 1,
LEFT acrescenta 10,444 mm e RIGHT 2,845 mm à referência 297 mm; na captura 2,
LEFT acrescenta 5,769 mm e RIGHT 1,547 mm. Isso explica os extras de 6,645 e
3,658 mm sem qualquer mudança na conversão física.

A largura da captura 2 é perdida sobretudo no BOTTOM: TOP já mede 210,128 mm,
mas BOTTOM mede 205,302 mm. A média reduz a largura para 207,715 mm. Não é uma
folha que foi corretamente medida em ambos os lados e apenas classificada errado.

Os detalhes de coordenadas originais/físicas, comprimentos visíveis, contraste,
amostras, alinhamento, extrapolação, distância à moldura e razões por borda estão
em `capture-N/edge-1000/summary.json` e `refinement.json`.

## Causa demonstrada 1 — amostragem esparsa impede refinamento real

A combinação `CHAIN_APPROX_SIMPLE` e seleção interior de 8%–92% da borda remove
os endpoints de segmentos retilíneos que podem estar representados por apenas
dois pontos. A função exige pelo menos quatro pontos e cobertura de 35% para
ajustar a linha. Quando falha, mantém a linha do polígono aproximado; o “refinamento”
não refinou aquela borda.

Na captura 1 só TOP recebeu ajuste Huber. RIGHT tem quatro pontos mas cobertura
insuficiente; BOTTOM e LEFT têm zero pontos elegíveis. Na captura 2 só RIGHT e
BOTTOM foram ajustados; TOP tem nove pontos e LEFT 16, mas cobertura insuficiente.

Experimento controlado, sem alterar produção: amostragem densa com o mesmo
threshold e morfologia muda o resultado para 208,396 × 303,910 mm na captura 1 e
208,082 × 300,598 mm na captura 2. Corrige uma fragilidade comprovada, mas **não
recupera uma A4 confiável**. Não justifica alterar tolerância/confiança.

## Causa demonstrada 2 — kernel fixo em pixels seleciona fundo em outra escala

| Preview | Kernel físico atual | Captura 1, mm | Captura 2, mm |
|---|---:|---:|---:|
| 500 × 1000 | 6,477 × 6,477 mm | 209,262 × 303,645 | 207,715 × 300,658 |
| 750 × 1500 | 4,318 × 4,318 mm | 51,097 × 123,640 | 51,240 × 128,677 |
| 1000 × 2000 | 3,238 × 3,238 mm | 51,384 × 123,603 | 51,492 × 128,676 |

Nos dois previews maiores o detector escolhe #3, OTSU_INVERSE: faixa do ADF,
não a região dominante da folha. A abertura 15 × 15 passa a ocupar menos mm e
não separa as faixas; o contorno principal fica com mais de quatro vértices e é
rejeitado pela regra de quadrilátero. Então um quadrilátero menor do fundo vence.

Mantendo a escala física da abertura (23 e 31 pixels nos previews maiores), o
contorno dominante volta a ser quadrilátero. Na captura 1 resulta aproximadamente
208,79 × 303,94 e 208,93 × 304,02; na captura 2, 207,74 × 300,49 e 207,76 × 300,75.
**Mais resolução não remove o excesso de altura.** Não se deve aumentar a resolução
padrão nem usar isso para promover A4.

## Evidência independente em resolução original: leading/trailing

Projeções/scanlines foram calculadas também diretamente nos 2550 × 5100 pixels,
com medianas locais e thresholds 80, 128, 180, 200, 230 e 250, sem formato candidato.

| Evidência em origem, threshold 200 | Captura 1 | Captura 2 |
|---|---:|---:|
| Trailing photométrico mediano, posição Y | 307,763 mm | 302,599 mm |
| Leading, ângulo dos trechos visíveis | +2,953° | +2,491° |
| Leading extrapolado em X=0 | −3,819 mm | −5,847 mm |
| Trailing, ângulo | +0,021° | −0,195° |

Entre thresholds 80–200, o trailing permanece praticamente igual. O leading
extrapolado continua negativo e inclinado. A ocorrência em origem exclui a
hipótese de que todos os 3–7 mm venham apenas de quantização do preview.

A borda luminosa de entrada e a de saída não são paralelas; tampouco combinam
consistentemente com os ângulos laterais. O sistema está ajustando uma região
fotométrica formada por folha/fundo/sombra/saída do ADF, que **não pode ser assumida
como um retângulo físico rigidamente inclinado**. O indicador `perspective_detected`
false significa só que não excedeu os limiares geométricos existentes; não prova
que as quatro linhas correspondem à folha real.

Não é possível atribuir com certeza uma linha a sombra, firmware ou material
apenas pelos valores numéricos; as imagens locais permitem revisão humana dessas
hipóteses. O que os dados demonstram é o truncamento da região visível no frame e
limites incompatíveis com uma reconstrução retangular confiável. Não se pode
fixar o leading em 0 ou recuar o trailing para 297 mm usando a informação A4.

## Conclusão antes da correção

Há duas falhas corrigíveis demonstradas no software: seleção dependente da escala
física do kernel e insuficiência de pontos para refinar linhas. Há também uma
limitação observacional persistente: a fronteira luminosa capturada não fornece
quatro bordas físicas coerentes da folha. Corrigir as duas falhas não autoriza
apagar a evidência de corte ou apresentar uma A4 aprovada.

Uma abordagem ADF de projeções 1D junto aos contornos 2D é útil para diagnosticar
continuidade e distinguir faixas de fundo. Neste material, ela confirma a
ambiguidade do leading/trailing em vez de produzir autonomamente 210 × 297 mm.
Uma medida adicional de passagem/entrada/saída, imagem com bordas completas ou
calibração independente seria necessária para resolver essa ambiguidade com
confiança; nenhuma dessas informações foi inventada nesta rodada.

A correção mínima pode tratar apenas as duas falhas demonstradas, mantendo a
análise padrão em 500 × 1000, as tolerâncias, confiança e estado PARTIAL quando
necessário. O replay e a regressão devem ser registrados separadamente abaixo.


## Coordenadas e razão geométrica por borda, antes da correção

Coordenadas físicas abaixo referem-se à **área capturada**, não a partes invisíveis da folha.

| Captura/borda | Início (x,y), mm | Fim (x,y), mm | Amostras de contraste válidas | Suporte de contraste | Razão |
|---|---|---|---:|---:|---|
| 1 / TOP | (1.311, 0.000) | (210.719, 7.169) | 17 | 0.706 | isolated_frame_contact |
| 1 / RIGHT | (210.719, 7.169) | (208.991, 307.010) | 21 | 1.000 | visible_contrast_edge |
| 1 / BOTTOM | (208.991, 307.010) | (0.000, 307.442) | 21 | 1.000 | visible_contrast_edge |
| 1 / LEFT | (0.000, 307.442) | (1.311, 0.000) | 0 | 0.000 | isolated_frame_contact |
| 2 / TOP | (4.750, 0.000) | (214.849, 3.458) | 11 | 0.000 | isolated_frame_contact |
| 2 / RIGHT | (214.849, 3.458) | (205.300, 301.853) | 21 | 0.905 | isolated_frame_contact |
| 2 / BOTTOM | (205.300, 301.853) | (0.000, 302.732) | 21 | 1.000 | visible_contrast_edge |
| 2 / LEFT | (0.000, 302.732) | (4.750, 0.000) | 14 | 0.000 | isolated_frame_contact |


## Correção mínima implementada depois de documentar a causa

Alterações de produção limitadas a `DocumentGeometryService`:

1. Usar `CHAIN_APPROX_NONE` para que o ajuste das linhas tenha suporte real no
   interior de segmentos retilíneos, sem depender de endpoints esparsos.
2. Escalar o kernel de abertura nos previews maiores, mantendo 15 pixels na
   análise padrão e em imagens menores; 23/31 nos testes de 1500/2000. A resolução
   padrão **continua 1000 pixels no maior lado**.

Não alterados: tolerância, confiança, formatos, metrologia, regra de corte,
classificação, source-image, schema 22, versão, Multicloud, LAN, recibos, QR,
Solicitações, som ou packaging. Não há regra por fabricante/modelo.

Os testes novos reproduzem exatamente os dois mecanismos: contorno retangular
esparso incapaz de corrigir vértices aproximados e faixas físicas do fundo que
reconectam em previews maiores com kernel estático. Um teste confirma que o
diagnóstico não chama o classificador de formatos.

## Replay cego após correção

| Captura | Antes 500 × 1000, mm | Depois 500 × 1000, mm | Depois 750 × 1500, mm | Depois 1000 × 2000, mm |
|---|---:|---:|---:|---:|
| 1 | 209.262 × 303.645 | 208.396 × 303.910 | 208.692 × 303.909 | 208.720 × 304.127 |
| 2 | 207.715 × 300.658 | 208.082 × 300.598 | 208.194 × 300.761 | 208.248 × 300.949 |

Em todas as escalas após correção, o candidato é #6, OTSU_OPEN, região dominante.
Antes, nas duas escalas maiores, era #3 do fundo. A discrepância de vários
milímetros não desapareceu: as duas capturas continuam **PARTIAL/CUSTOM** no
replay real de produção. Não são homologadas como A4 automática.

O replay real não passou `expected_format`, tamanho A4 ou nome do scanner.
Hashes dos dois originais conferidos antes/depois. Artefatos após correção:
`/tmp/smartfile-adf-offline-diagnostics-after-20261012/index.html`.

### Custo/benefício observado (um replay instrumental por escala)

| Captura | 500 × 1000 | 750 × 1500 | 1000 × 2000 |
|---|---:|---:|---:|
| 1 | 495.5 ms | 848.3 ms | 671.0 ms |
| 2 | 227.7 ms | 750.7 ms | 674.1 ms |

Medições locais com I/O diagnóstico e testes concorrentes; não são um benchmark isolado nem garantia de latência. Não justificam elevar a resolução padrão.

## Como reproduzir, sem scanner/rede

Na raiz do projeto (escolher pastas novas para não sobrescrever artefatos):

```bash
venv/bin/python scripts/diagnose_adf_geometry.py   --capture /tmp/smartfile-hp3700-check/source.png /tmp/smartfile-hp3700-check/measurement.json   --capture /tmp/smartfile-hp3700-second-check/source.png /tmp/smartfile-hp3700-second-check/measurement.json   --output-root /tmp/adf-diagnostic-baseline-new --pipeline baseline

venv/bin/python scripts/diagnose_adf_scanlines.py   --capture /tmp/smartfile-hp3700-check/source.png /tmp/smartfile-hp3700-check/measurement.json   --capture /tmp/smartfile-hp3700-second-check/source.png /tmp/smartfile-hp3700-second-check/measurement.json   --output-root /tmp/adf-diagnostic-baseline-new
```

Para a versão corrigida, executar o primeiro comando com `--pipeline production`
e outra pasta. O parâmetro só permite comparar a implementação do checkpoint
com a corrigida; não informa formato ou dimensão esperada.

Os scripts não instanciam ScanService, não adquirem, não abrem sockets, não enviam
imagens e não dependem de novas bibliotecas. Os gráficos numéricos são SVG local.

## Validação final

- Suíte completa: **513 passed em 402,63 s (6 min 42 s)**. Base de 506 preservada,
  sete regressões adicionais das causas; nenhuma regressão nos demais módulos.
- `compileall` de app/scripts de diagnóstico: passou.
- `pip check`: No broken requirements found.
- `git diff --check`: passou.
- Hashes dos dois originais conferidos antes/depois; artefatos reais fora do Git.
- Checkpoint local `2997f10` preserva a consolidação antes desta investigação.
  A correção mínima, scripts, teste e este relatório ficam no working tree;
  sem commit final, push, release ou terceira aquisição.
- Versão `0.9.0-beta.6` e schema 22 mantidos. Sem alteração nos demais módulos.

**A4 física automática continua não homologada.** Esta rodada demonstra e corrige
duas falhas do algoritmo, mas não fabrica as bordas físicas que os métodos
avaliados não conseguem determinar com confiança. Não se declara impossível
qualquer análise futura da imagem: demonstrou-se que os contornos/projeções
avaliados e a metrologia nominal atual não sustentam uma reconstrução física
única e confiável. A revisão visual local permite confrontar as hipóteses abaixo
antes de decidir se é necessária outra informação ou uma aquisição futura.


## Observação adicional: região de branco saturado antes do trailing

Na origem, probes em X aproximadamente 13, 73, 142 e 203 mm detectam trechos
quase uniformes, com valores >=254 durante pelo menos 25 scanlines consecutivas,
antes da transição clara/escura do ADF:

| Captura | Início desse trecho, Y em mm (quatro probes) | Transição final, Y em mm |
|---|---|---|
| 1 | 302,68; 302,94; 302,77; 301,92 | 307,59–307,76 |
| 2 | 300,40; 298,28; 297,26; 296,84 | 302,18–302,85 |

Essa região de 2–6 mm é incluída na segmentação clara e é compatível com uma
parcela importante do excesso de altura observado. **Não demonstra por si só
onde terminou o papel**: branco de papel, iluminação/saturação, sombra e preenchimento
do backend são hipóteses distintas. Usar seu início como corte automaticamente
poderia eliminar papel branco real; não foi adicionado esse corte nem escolhido
um threshold para resultar em 297 mm. A metrologia nominal coerente da área
capturada tampouco valida, sozinha, a calibração mecânica do avanço do ADF.

Os artefatos foram gerados para inspeção visual local. A investigação computacional
leu os pixels e produziu medidas/plots; nenhuma dessas imagens reais foi enviada
para análise visual de um modelo de IA.


## Decisão de fechamento — 12/10/2026

O usuário aprovou provisoriamente o scanner para esta etapa e autorizou o fechamento
com suíte completa e commit/push, sem release. Esta decisão substitui a pendência de
aprovação física para a entrega registrada no histórico acima; não altera os resultados
medidos nem aprova universalmente o detector. Não executar nova aquisição ou continuar
refinando o detector nesta rodada. Preservar `PARTIAL/REVIEW` em geometria incerta,
as correções existentes e o original, sem forçar A4.

```text
Scanner físico: homologado para captura e geração correta de PDF.
Reconhecimento automático universal do tamanho da folha:
funcionalidade experimental/assistiva, ainda não homologada para todos os formatos.
```

O reconhecimento universal será uma melhoria separada. O próximo item pendente é
QR Code funcionando sem depender obrigatoriamente de URL pública. Versão
`0.9.0-beta.6` e schema 22 permanecem inalterados. A validação de fechamento está
registrada em [REPORT.md](REPORT.md).
