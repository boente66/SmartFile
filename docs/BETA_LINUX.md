# SmartFile 0.9.0 Beta 3 — Linux amd64

Esta distribuição é um **protótipo beta não oficial**, destinado exclusivamente
a avaliação e testes. Não utilize o SmartFile como a única cópia de documentos
críticos. Mantenha backups independentes do banco e do storage e relate todos os
erros, comportamentos inesperados ou incompatibilidades encontrados.

## Compatibilidade inicial

- Linux Mint com base Ubuntu 22.04 ou 24.04;
- Zorin OS com base Ubuntu 22.04 ou 24.04;
- Ubuntu 22.04 LTS;
- Ubuntu 24.04 LTS;
- Debian e derivados amd64 com bibliotecas compatíveis.

O pacote é compilado uma única vez no runner Ubuntu 22.04, com baseline máxima
`GLIBC_2.35` e `GLIBCXX_3.4.29`. Esse mesmo arquivo, sem recompilação, é instalado
e iniciado nos runners Ubuntu 22.04 e Ubuntu 24.04. Distribuições baseadas em
Ubuntu 20.04 ou anteriores não fazem parte da compatibilidade declarada.

A compatibilidade com uma família de distribuição depende da base Ubuntu, não
apenas do nome ou da versão visual do sistema. Hardware, drivers de scanner e
ambiente gráfico ainda devem ser testados no equipamento do usuário.

## Download oficial da beta

Utilize a página permanente da
[Release 0.9.0 Beta 3](https://github.com/boente66/SmartFile/releases/tag/v0.9.0-beta.3).
O instalador Linux e seu arquivo SHA-256 ficam na seção **Assets**. O link de
GitHub Actions é temporário, pode exigir login e entrega um ZIP; ele não é o
canal de distribuição do instalador.

[Download direto do SmartFile Linux amd64](https://github.com/boente66/SmartFile/releases/download/v0.9.0-beta.3/smartfile_0.9.0.beta3_amd64.deb)

O arquivo baixado deve se chamar `smartfile_0.9.0.beta3_amd64.deb`. Um download
que seja HTML ou ZIP não é um pacote Debian e deve ser descartado.

## Instalação gráfica

1. Baixe o arquivo `.deb` em **Assets** na página da Release.
2. Abra a pasta de Downloads.
3. Dê um clique duplo no arquivo `.deb`.
4. Selecione **Instalar** no instalador de aplicativos e informe a senha do
   administrador quando solicitada.
5. Procure por **SmartFile** no menu de aplicativos.

## Instalação pelo terminal

```bash
cd ~/Downloads
sha256sum -c smartfile_0.9.0.beta3_amd64.deb.sha256
file smartfile_0.9.0.beta3_amd64.deb
dpkg-deb --info smartfile_0.9.0.beta3_amd64.deb
sudo apt install ./smartfile_0.9.0.beta3_amd64.deb
smartfile
sudo apt remove smartfile
```

O resultado do SHA-256 deve ser `OK`, e `file` deve identificar `Debian binary
package`. O pacote produzido localmente pelo script do projeto usa o nome
`smartfile_0.9.0~beta3_amd64.deb`; o GitHub normaliza o caractere `~` no nome do
asset, mas a versão interna do pacote continua sendo `0.9.0~beta3`.

O launcher instalado fica em `/usr/share/applications/smartfile.desktop`, o
comando em `/usr/bin/smartfile` e o bundle em `/opt/smartfile`. O aplicativo não
depende de virtualenv, `PYTHONPATH`, diretório do projeto ou diretório corrente.

A remoção ou atualização substitui apenas arquivos em `/opt/smartfile` e a
integração do menu. Não remove documentos, banco, contas, configurações, tokens
protegidos nem backups.

Os dados ficam, por padrão, em `~/.local/share/SmartFile`. Para uma remoção total,
feche o aplicativo, faça um backup e remova manualmente os diretórios abaixo
somente se tiver certeza de que não precisa mais dos dados:

```text
~/.local/share/SmartFile
~/.config/SmartFile
~/.cache/SmartFile
```

## Dependências

As bibliotecas básicas do desktop são declaradas em `Depends`. Integrações que
não impedem a abertura do SmartFile são opcionais. Somente o cofre do desktop
permanece recomendado; scanner, Poppler e LibreOffice são sugestões e não são
instalados automaticamente pelo APT:

- `libsecret-1-0`: armazenamento de credenciais pelo keyring do desktop;
- `sane-utils` e `libsane1`: scanners SANE;
- `poppler-utils`: fluxos de imagem que usam utilitários Poppler;
- `libreoffice`: conversões de documentos compatíveis no Linux.

TIFF é processado pelo Pillow. O plugin TIFF do Qt não integra o bundle Linux
porque a wheel atual referencia a biblioteca obsoleta `libtiff.so.5`; isso evita
uma dependência quebrada sem remover as conversões TIFF do SmartFile.

Sem scanner ou SANE, o módulo deve informar a indisponibilidade sem impedir os
demais recursos. Impressão depende da configuração de impressão do sistema.

## Limitações conhecidas

- somente arquitetura amd64 nesta receita;
- conversões DOCX para PDF/JPG utilizam o LibreOffice em modo headless e exibem
  orientação clara quando o programa não estiver instalado;
- scanner com hardware depende do dispositivo, driver e permissões locais;
- assinatura digital requer certificado de teste/usuário e dependências válidas;
- OAuth não inclui Client IDs, segredos, tokens ou configurações pessoais;
- pacote possui SHA-256, não assinatura criptográfica GPG;
- A3, PAdES-LT/LTA, OCR e atualização automática não são declarados como
  suportados por esta beta.

## Diagnóstico de instalação

- `Unable to locate package` ou arquivo inexistente: entre na pasta Downloads e
  mantenha o prefixo `./` no comando do APT.
- `not a Debian format archive`: apague o arquivo; o navegador salvou HTML/ZIP
  ou o download foi interrompido. Baixe novamente pela Release.
- `user is not in the sudoers file`: a conta atual não possui autorização para
  instalar programas; utilize uma conta administradora.
- arquitetura incompatível: `dpkg --print-architecture` deve retornar `amd64`.
- dependência indisponível: execute `sudo apt update` e repita a instalação.

Ao relatar uma falha, informe a distribuição, sua versão, arquitetura, saída
de `dpkg-deb --info` e mensagem completa do APT. Não envie senhas, tokens ou
documentos pessoais.

## Build reproduzível do projeto

Em Linux amd64 com Python 3.12, `dpkg-deb`, `desktop-file-validate` e
`appstreamcli`:

```bash
chmod +x scripts/build_linux_deb.sh
./scripts/build_linux_deb.sh
```

O script cria um ambiente isolado em `build/linux/venv`, instala
`requirements.txt` e `requirements-build.txt`, executa testes, compila o bundle,
monta a árvore Debian, executa smoke tests isolados e grava o pacote e o checksum
em `release/`. Ele não usa `sudo` e não acessa os dados reais do usuário. O
workflow oficial executa etapas em runners limpos 22.04 e 24.04, usando o mesmo
`.deb`: instala de verdade, valida o comando, o launcher, o AppStream, reinstala
e remove o pacote confirmando a preservação dos dados do usuário. A auditoria
`scripts/audit_linux_abi.sh` registra todos os ELF e bloqueia o build se a maior
versão requerida ultrapassar a baseline declarada.

Para reutilizar um ambiente já preparado:

```bash
SMARTFILE_BUILD_PYTHON="$PWD/venv/bin/python" \
SMARTFILE_SKIP_INSTALL=1 ./scripts/build_linux_deb.sh
```

Durante diagnóstico local, um bundle já gerado pode ser remontado com
`SMARTFILE_REUSE_BUNDLE=1 SMARTFILE_SKIP_TESTS=1`. Essas opções não são usadas no
workflow oficial e não substituem uma execução integral antes da publicação.

Instale `lintian` no host de build para obter a análise adicional. Ausência dessa
ferramenta é reportada e deve constar no relatório de validação.
O relatório é sempre preservado em `build/linux/lintian.log`. Bundles PyInstaller
incluem binários de terceiros e podem gerar apontamentos de empacotamento Debian;
esses apontamentos são documentados, enquanto formato, dependências, instalação
real e startup são tratados como bloqueios obrigatórios pelo CI.

## Relato de bugs

Abra uma issue no repositório informando distribuição, versão, arquitetura,
etapas para reproduzir e mensagens exibidas. Remova documentos, e-mails, tokens,
Client IDs, segredos e outros dados pessoais antes de anexar logs ou imagens.
