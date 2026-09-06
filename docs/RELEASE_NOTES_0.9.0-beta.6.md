# SmartFile 0.9.0-beta.6

Versão beta corretiva voltada à administração da Cloud Layer. Mantenha backup
independente e relate problemas no GitHub.

## Configuração administrativa da nuvem

- proprietários (`OWNER`) e administradores (`ADMIN`) podem abrir a interface
  “Configurar provedor” na organização ativa;
- a disponibilidade é igual nos perfis Pessoal, Estudante, Empresarial e
  Essencial;
- a mesma permissão é verificada no menu, no módulo Documentos e nos
  Controllers;
- editores e visualizadores continuam bloqueados.

## Segurança e preservação

- a autorização utiliza a permissão específica `cloud.configure_provider`;
- backup e privilégios globais continuam exclusivos do administrador do
  sistema;
- tokens, credenciais, armazenamento, banco e contratos públicos da Cloud
  Layer não foram alterados;
- schema permanece na versão 22.

## Compatibilidade

- Windows 10 e Windows 11 x64;
- Linux amd64 com baseline Ubuntu 22.04/GLIBC 2.35;
- mesmo `.deb` validado em Ubuntu 22.04 e Ubuntu 24.04;
- Python 3.12, PyQt6 e SQLite nativo.
