# SmartFile 0.9.0 Beta 1

Primeira distribuição beta Linux amd64 do SmartFile para avaliação em sistemas
compatíveis baseados em Linux Mint, Ubuntu e Debian. Este pacote é um
**protótipo não oficial para testes**; usuários devem relatar os problemas
encontrados pelo rastreador de issues do projeto.

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

## Instalação

```bash
sudo apt install ./smartfile_0.9.0~beta1_amd64.deb
```

Valide o arquivo antes da instalação com:

```bash
sha256sum -c smartfile_0.9.0~beta1_amd64.deb.sha256
```

## Avisos

Esta é uma versão beta. Não a utilize como única cópia de documentos críticos.
O scanner e algumas conversões dependem de software e hardware externos. O
artefato SHA-256 detecta alterações acidentais, mas ainda não possui assinatura
GPG. A sincronização de nuvem não substitui o backup do SQLite e do storage.
Consulte `BETA_LINUX.md` para limitações e remoção.
