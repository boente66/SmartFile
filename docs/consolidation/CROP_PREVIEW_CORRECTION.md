# Correção de prévia e recorte — 13/10/2026

Escopo: páginas digitalizadas e imagens importadas em Captura e PDF. Correção
posterior aos instaladores publicados da beta.7; versão e schema não alterados.

A prévia removia geometry dos snapshots para exibir alças sobre a imagem original.
Assim, o recorte detectado não aparecia antes de salvar. A composição ainda
acrescentava margem de 8 mm, inclusive após o recorte confiável.

A opção Mostrar documento recortado inicia marcada. Prévia e materialização
utilizam a mesma condição: DETECTED/MANUAL, confiança >= 0,8, sem indicação de
corte automático. PARTIAL e NOT_DETECTED preservam a área original. Ajuste manual
é decisão explícita do usuário, sem promover o resultado automático a DETECTED.
Desmarcar a opção mostra o original e permite editar as alças; não desativa o
recorte da saída. Redefinir restaura a imagem original no preview e na saída.

Salvar, extrair, dividir e adicionar ao GED aguardam a detecção, inclusive por
chamadas de atalho. Resultados de geometria atualizam o estado dirty e solicitam
nova renderização. O recorte aplicado não recebe margem artificial de 8 mm;
espaço decorrente da proporção diferente do papel de saída é mantido, sem
esticar ou cortar conteúdo para preencher A4.

O original permanece intacto. Não houve aquisição física nem alteração no
reconhecimento de formatos, tolerâncias, medida física, Multicloud ou QR. O
fluxo de PDF nativo permanece preservado. O problema informado pelo usuário foi
confirmado como página digitalizada/imagem, não PDF aberto.

Regressões verificam imagem com fundo excedente, correspondência do recorte
na prévia/saída e ausência de margem artificial, preservação do original,
PARTIAL mesmo com confiança elevada, possível corte, alternância de prévia,
redefinição e bloqueio de salvamento durante detecção.

Validação focada: 86 testes aprovados em 17,52 s. Compilação dos arquivos alterados
e git diff --check aprovados. Suíte completa: **578 passed em 447,52 s (7 min 27 s)**, exit 0.
A primeira execução no sandbox ficou parada no teste de inicialização com LAN;
foi encerrada e repetida integralmente com a rede local disponível, sem alterar
testes, timeouts funcionais ou executar aquisição física.
