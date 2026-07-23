# SmartFile

O SmartFile é uma aplicação desktop multiplataforma para gestão local de
documentos. O projeto reúne Mini GED, organizações, pastas lógicas, scanner,
conversão de arquivos, visualização e manipulação de PDFs, assinaturas e
sincronização opcional com provedores de nuvem.

> **Versão beta para avaliação. Não utilize o SmartFile como única cópia de
> documentos importantes.**

O armazenamento interno continua sendo a fonte principal dos documentos. A
nuvem é uma camada opcional de sincronização e não substitui backups
independentes.

## Funcionalidades principais

- cadastro local, login e perfis administrativos;
- organizações independentes e pastas lógicas;
- importação, pesquisa, filtros, favoritos, recentes, histórico e lixeira;
- armazenamento interno gerenciado com SQLite e checksums SHA-256;
- visualizador interno de PDF com navegação, zoom, miniaturas e pesquisa;
- PDF Tools para operações estruturais;
- assinatura digital e assinatura manuscrita;
- scanner SANE no Linux e TWAIN no Windows;
- conversão de documentos;
- backup completo em ZIP para administradores;
- sincronização opcional com Microsoft OneDrive ou Google Drive.

## Camada de Nuvem

A Cloud Layer mantém os módulos do SmartFile desacoplados das APIs externas:

```text
Documentos / Scanner
        │
        ▼
Storage interno + SQLite
        │
        ▼
Cloud Queue
        │
        ▼
Cloud Layer
   ┌────┴─────┐
   ▼          ▼
OneDrive  Google Drive
```

Nenhum módulo documental acessa diretamente o Microsoft Graph ou o Google
Drive. Uploads, downloads, renomeações, movimentações, exclusões e consultas de
alterações passam pelo contrato comum da Cloud Layer.

### Funcionamento por organização

- cada organização escolhe entre `Local`, `OneDrive` ou `Google Drive`;
- somente uma conta de nuvem fica ativa por organização;
- documentos, pastas, fila, cursor remoto e pasta raiz são isolados por
  organização;
- trocar a organização ativa não troca nem expõe a conta de outra organização;
- o SmartFile mantém na nuvem uma pasta `SmartFile` e uma raiz própria para cada
  organização sincronizada.

### Funcionamento offline

O documento é salvo primeiro no storage interno e no SQLite. Se não houver
internet, a operação permanece na fila e o arquivo continua disponível
localmente. Quando a conexão retorna, o worker tenta processar a pendência sem
bloquear a interface.

Estados documentais utilizados:

- `LOCAL_ONLY`;
- `PENDING_UPLOAD`;
- `UPLOADING`;
- `SYNCED`;
- `PENDING_DOWNLOAD`;
- `CONFLICT`;
- `SYNC_ERROR`;
- `REMOTE_DELETED`;
- `LOCAL_DELETED`.

### Autenticação e segurança

- autenticação OAuth pelo navegador do sistema;
- Microsoft por MSAL e Microsoft Graph;
- Google por `google-auth-oauthlib` e Google Drive API;
- tokens preferencialmente armazenados no keyring do sistema;
- fallback local cifrado quando o keyring não estiver disponível;
- tokens e refresh tokens não são gravados no SQLite nem exibidos na interface;
- senhas, tokens e credenciais não devem aparecer em logs;
- remover uma conta apaga o vínculo e os tokens locais que não estejam sendo
  usados por outra organização;
- nenhuma credencial OAuth pessoal é incluída nos instaladores.

### Configuração OAuth administrativa

A opção **Configurar provedor** é exclusiva do administrador global do
SmartFile. Ela configura o aplicativo OAuth; cada usuário conecta depois sua
própria conta pelo botão **Adicionar Conta**.

Para o OneDrive:

1. registrar um aplicativo Desktop no Microsoft Entra;
2. configurar o redirect URI `http://localhost`;
3. habilitar fluxo de cliente público;
4. conceder permissões delegadas `User.Read` e `Files.ReadWrite`;
5. informar o Client ID e o tenant ao SmartFile.

Para o Google Drive:

1. criar um projeto no Google Cloud;
2. habilitar a Google Drive API;
3. configurar a tela de consentimento;
4. criar um cliente OAuth do tipo **Aplicativo para computador**;
5. fornecer o JSON do cliente na configuração administrativa.

Consulte [OAuth de nuvem — configuração administrativa](docs/OAUTH_DESENVOLVIMENTO.md)
e o [relatório formal da Cloud Layer](docs/RELATORIO_FORMAL_IMPLEMENTACAO_CLOUD_LAYER.md).

### Limitações da nuvem

- sincronização não equivale a backup;
- não há colaboração em tempo real;
- não há compartilhamento ou permissões remotas;
- conflitos não são resolvidos automaticamente;
- contas, consentimento, políticas corporativas, proxy e MFA dependem da
  configuração externa de cada ambiente;
- a homologação completa deve ser feita com contas de teste, nunca com
  documentos ou certificados pessoais.

## Tecnologias

- Python 3.12;
- PyQt6;
- SQLite nativo;
- PyMuPDF, pypdf, pyHanko, reportlab e Pillow;
- python-docx, openpyxl, pandas e LibreOffice quando disponível;
- MSAL e Google OAuth;
- keyring;
- SANE no Linux e TWAIN no Windows;
- PyInstaller e Inno Setup para distribuição.

## Executar pelo código-fonte

Crie um ambiente virtual, instale as dependências e execute:

```bash
python -m pip install -r requirements.txt
python run.py
```

No Linux, o scanner pode exigir `libsane` e ferramentas SANE do sistema. No
Windows, instale o driver TWAIN x64 fornecido pelo fabricante do scanner.

## Pacote Linux beta

O pacote Linux amd64 é destinado a testes em sistemas compatíveis baseados em
Linux Mint, Ubuntu e Debian:

```bash
sudo apt install ./smartfile_0.9.0~beta1_amd64.deb
```

A remoção normal preserva banco, documentos, configurações e backups do
usuário. Consulte [SmartFile Beta Linux](docs/BETA_LINUX.md).

## Pacote Windows experimental

O GitHub Actions gera:

- `SmartFile-0.9.0-beta.1-Windows-x64-Setup.exe`;
- `SmartFile-0.9.0-beta.1-Windows-x64-Portable.zip`;
- checksums SHA-256 dos dois arquivos.

O instalador é construído em um runner oficial Windows com PyInstaller onedir e
Inno Setup. Nenhuma release final é publicada automaticamente.

Abra [Windows beta package](https://github.com/boente66/SmartFile/actions/workflows/build-windows.yml)
para executar ou baixar um build temporário. Antes da distribuição, siga o
[Guia de teste Windows Beta](docs/GUIA_TESTE_WINDOWS_BETA.md).

## Estrutura do projeto

```text
SmartFile/
├── app/
│   ├── cloud/
│   ├── controllers/
│   ├── database/
│   ├── entities/
│   ├── repositories/
│   ├── services/
│   ├── views/
│   └── workers/
├── assets/
├── docs/
├── packaging/
├── scripts/
├── tests/
├── requirements.txt
├── requirements-windows.txt
└── run.py
```

## Testes

```bash
python -m compileall -q app tests run.py
python -m pytest -q
python -m pip check
git diff --check
```

Builds do instalador não substituem testes manuais em Windows ou Linux reais,
especialmente para scanner, assinatura digital, conversores externos e OAuth.

## Roadmap

- estabilização e homologação dos pacotes beta;
- assinatura de código dos instaladores;
- validação ampliada com contas de nuvem de teste;
- tratamento assistido de conflitos;
- sincronização incremental e versionamento remoto;
- preparação de uma versão candidata à 1.0.

## Contribuição

1. Faça um fork do repositório.
2. Crie uma branch para a alteração.
3. Implemente e execute os testes.
4. Abra um pull request descrevendo impacto e validações.

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) e
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Licença

O SmartFile é distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
