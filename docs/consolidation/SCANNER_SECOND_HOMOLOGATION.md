# Segundo teste físico — uma única folha A4 retrato

Esta rodada testa apenas o enquadramento documental. Sem internet, upload, OCR,
QR novo, alteração de versão/schema, commit ou push. A comunicação necessária
para adquirir a imagem é somente com o scanner na rede local.

## Preparação

1. Colocar **uma única folha A4 retrato**, inteira, no ADF da HP DeskJet 3700.
2. Alinhar a folha às guias do alimentador, reta, sem dobra ou folha sobreposta.
3. Manter scanner/impressora e computador na mesma rede local.
4. Confirmar no chat: **“A4 retrato pronto para o segundo teste”**.

Nenhuma digitalização nova será executada antes dessa confirmação. O detector
não recebe nome/modelo do scanner nem o formato que o usuário informou.

## Comando de aquisição, após a confirmação

Na raiz do projeto, com o venv existente:

```bash
venv/bin/python scripts/verify_scanner_geometry.py \
  --device 'airscan:e0:HP DeskJet 3700 series [38EF08]' \
  --dpi 300 \
  --source ADF \
  --output-directory /tmp/smartfile-hp3700-second-check \
  --expected-size A4 \
  --expected-orientation PORTRAIT
```

O identificador acima é o dispositivo encontrado na homologação anterior,
passado como argumento. Não existe código específico por modelo no detector.
Se o identificador local mudar, substituir somente `--device` pelo identificador
real disponível, sem adaptar a geometria ao nome do equipamento.

A pasta de saída precisa ser nova: o script recusa sobrescrever uma pasta
existente. Não repetir automaticamente uma aquisição em caso de revisão/falha.
A folha deve ser reinserida apenas se houver um novo teste expressamente combinado.

`--expected-size` e `--expected-orientation` são usados **após a detecção**,
exclusivamente na avaliação de homologação. Não são parâmetros do detector e
não calibram/snapam os cantos ou milímetros para A4.

## Artefatos exclusivamente locais

- `source.png`: original completo, sem cortar/redimensionar o arquivo fonte;
- `a4.pdf`: saída documental A4 real, proporcional, derivada do original;
- `measurement.json`: capacidades, DPI efetivo/solicitado, área física da
  aquisição, geometria, fonte de medida, evidência de borda, confiança, tempos,
  hash SHA-256 da origem e MediaBox.

Nenhum scan é enviado a API, serviço de IA, nuvem ou servidor de imagens.
O diagnóstico pode ser discutido por seus números, sem compartilhar a imagem.

## Critério de aprovação do único teste

Esperado no `measurement.json`:

```text
geometry.standard_size: A4
geometry.orientation: PORTRAIT
geometry.detection_status: DETECTED
geometry.possible_clipping: false
geometry.confidence: >= 0.8, sem aumento por coincidência de bordas
geometry.boundary_status: COMPLETE ou COINCIDENT
geometry.measurement_source: DEVICE_GEOMETRY / SCANNER_DPI / CALIBRATED
geometry.physical_width_mm: aproximadamente 210
geometry.physical_height_mm: aproximadamente 297
homologation.status: PASS
pdf_media_box_mm: aproximadamente [210, 297]
```

As medidas detectadas devem corresponder ao padrão dentro da tolerância já
existente: erro absoluto máximo de 2,5 mm **e** relativo máximo de 1,2% em cada
lado confiável. Não se amplia essa tolerância para alcançar aprovação.

`REVIEW`/`PARTIAL` preserva o original e mantém A4 seguro como saída, mas
**não aprova** a detecção física. Não ajustar manualmente os cantos para marcar
essa homologação como automática. Não declarar encerramento/commit/push antes
de registrar o resultado e a aprovação do segundo teste.

## Replay opcional, sem scanner e sem rede

A captura anterior continua intocada. Para reanalisar somente seus arquivos:

```bash
venv/bin/python scripts/verify_scanner_geometry.py \
  --replay-image /tmp/smartfile-hp3700-check/source.png \
  --metadata /tmp/smartfile-hp3700-check/measurement.json \
  --output-directory /tmp/smartfile-scanner-corrective-replay-new \
  --expected-size A4 \
  --expected-orientation PORTRAIT
```

Sem `--metadata`, o replay não usa o DPI solicitado na linha de comando para
inventar dimensões físicas. Alterar o formato esperado muda apenas a avaliação
PASS/REVIEW, nunca o resultado da geometria.


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
