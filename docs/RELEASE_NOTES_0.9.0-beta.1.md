# SmartFile 0.9.0 Beta 1

Distribuição experimental do SmartFile para avaliação em Windows x64 e Linux
amd64. Estes pacotes são **protótipos não homologados para testes**; usuários
devem relatar os problemas encontrados pelo rastreador de issues do projeto.

> **Esta é uma versão beta para avaliação. Não utilize o SmartFile como única
> cópia de documentos importantes.**

## Destaques

- Mini GED local com organizações, pastas, histórico e lixeira;
- visualizador e ferramentas de PDF;
- scanner opcional via SANE;
- conversões documentais;
- assinaturas digital e manuscrita;
- sincronização opcional com OneDrive e Google Drive;
- espelhamento remoto isolado por organização e pastas lógicas;
- backup ZIP completo restrito ao administrador do sistema;
- dados mutáveis mantidos fora de `/opt/smartfile`.

## Windows 10/11 x64

Artefatos gerados pelo GitHub Actions:

- `SmartFile-0.9.0-beta.1-Windows-x64-Setup.exe`;
- `SmartFile-0.9.0-beta.1-Windows-x64-Portable.zip`;
- arquivos `.sha256` correspondentes.

O instalador copia somente o aplicativo para `Program Files`, cria entrada de
desinstalação e oferece um atalho opcional na Área de Trabalho. A versão
portátil executa sem instalar Python, mas continua gravando dados mutáveis em
`%LOCALAPPDATA%\SmartFile` e configuração em `%APPDATA%\SmartFile`.

Confira o checksum no PowerShell:

```powershell
(Get-FileHash .\SmartFile-0.9.0-beta.1-Windows-x64-Setup.exe -Algorithm SHA256).Hash
Get-Content .\SmartFile-0.9.0-beta.1-Windows-x64-Setup.exe.sha256
```

Na desinstalação normal, banco, documentos e configuração do usuário são
preservados. O scanner exige um driver TWAIN x64 fornecido pelo fabricante; a
aplicação deve continuar funcionando quando nenhum scanner estiver disponível.
Conversões do Microsoft Office e algumas operações PDF podem depender de
programas externos instalados no Windows.

Consulte [GUIA_TESTE_WINDOWS_BETA.md](GUIA_TESTE_WINDOWS_BETA.md) antes de
distribuir o instalador. O build automatizado ainda requer homologação manual
em Windows 10 ou 11 real.

## Linux amd64

```bash
sudo apt install ./smartfile_0.9.0~beta1_amd64.deb
```

Valide o arquivo antes da instalação com:

```bash
sha256sum -c smartfile_0.9.0~beta1_amd64.deb.sha256
```

## Limitações e suporte

Esta é uma versão beta. Não a utilize como única cópia de documentos críticos.
O scanner e algumas conversões dependem de software e hardware externos. O
artefato SHA-256 detecta alterações acidentais, mas ainda não possui assinatura
de código no Windows nem assinatura GPG no Linux. A sincronização de nuvem não
substitui o backup do SQLite e do storage. OAuth inicia como `NOT_CONFIGURED`
quando o administrador não forneceu a configuração pública do provedor.

Reporte bugs pelo template **Windows beta bug**, sem anexar tokens, senhas,
certificados ou documentos confidenciais.
