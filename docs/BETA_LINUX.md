# SmartFile 0.9.0 Beta 1 — Linux amd64

Esta distribuição é destinada a avaliação. Não utilize o SmartFile como a única
cópia de documentos críticos. Mantenha backups independentes do banco e do
storage.

## Compatibilidade inicial

- Linux Mint baseado em Ubuntu 24.04;
- Ubuntu 24.04 LTS;
- Debian e derivados amd64 com bibliotecas compatíveis.

A compatibilidade só é considerada confirmada quando o pacote é instalado e
testado em cada ambiente limpo. Um smoke test local não substitui essa etapa.

## Instalação e remoção

```bash
sudo apt install ./smartfile_0.9.0~beta1_amd64.deb
smartfile
sudo apt remove smartfile
```

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
não impedem a abertura do SmartFile são recomendações:

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
- o fluxo `docx2pdf` não oferece suporte Linux nativo; conversões DOCX devem ser
  validadas com LibreOffice antes de serem consideradas suportadas no pacote;
- scanner com hardware depende do dispositivo, driver e permissões locais;
- assinatura digital requer certificado de teste/usuário e dependências válidas;
- OAuth não inclui Client IDs, segredos, tokens ou configurações pessoais;
- pacote possui SHA-256, não assinatura criptográfica GPG;
- A3, PAdES-LT/LTA, OCR e atualização automática não são declarados como
  suportados por esta beta.

## Build reproduzível do projeto

Em Linux amd64 com Python 3.12, `dpkg-deb` e `desktop-file-validate`:

```bash
chmod +x scripts/build_linux_deb.sh
./scripts/build_linux_deb.sh
```

O script cria um ambiente isolado em `build/linux/venv`, instala
`requirements.txt` e `requirements-build.txt`, executa testes, compila o bundle,
monta a árvore Debian, executa smoke tests isolados e grava o pacote e o checksum
em `release/`. Ele não usa `sudo` e não acessa os dados reais do usuário.

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

## Relato de bugs

Abra uma issue no repositório informando distribuição, versão, arquitetura,
etapas para reproduzir e mensagens exibidas. Remova documentos, e-mails, tokens,
Client IDs, segredos e outros dados pessoais antes de anexar logs ou imagens.
