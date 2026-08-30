# SmartFile 0.9.0-beta.4

Versão beta destinada à validação dos perfis exclusivos e do novo Acervo
Remoto Multicloud. Mantenha backup independente e relate problemas no GitHub.

## Acervo remoto multicloud

- perfis Pessoal e Estudante podem montar pastas existentes do OneDrive e
  Google Drive como espelhos lógicos;
- a montagem consulta somente metadados e não importa arquivos para o GED;
- o catálogo remoto não consome a cota de armazenamento local;
- arquivos podem possuir múltiplas réplicas sem serem duplicados visualmente;
- nome igual é apenas candidato, nunca prova automática de identidade;
- diferenças permanecem como divergência para decisão do usuário;
- a comparação cria um plano e nenhuma escrita ocorre sem autorização;
- desmontar remove somente o espelho local e preserva o provedor.

## Perfis empresariais

- Solicitações, prazos, entregas e protocolos são exclusivos do perfil
  Empresarial na interface, nas rotas, nos controllers e nos services;
- perfis Pessoal, Estudante e Essencial não exibem o conceito empresarial.

## Persistência e segurança

- schema 22 aditivo, sem perda de documentos ou mapeamentos existentes;
- todas as estruturas multicloud são isoladas por organização e conta;
- tokens continuam fora do SQLite;
- replicação autorizada usa temporário, SHA-256 e limpeza garantida;
- conflitos não são sobrescritos silenciosamente;
- ações destrutivas permanecem sem executor automático nesta versão.

## Atenção para Google Drive

Ler pastas preexistentes requer o escopo Google Drive completo. Quem já
conectou uma conta Google deve reconectá-la e conceder o novo consentimento
antes de montar o acervo remoto.

## Compatibilidade

- Windows 10 e Windows 11 x64;
- Linux amd64 com baseline Ubuntu 22.04/GLIBC 2.35;
- mesmo pacote `.deb` validado em Ubuntu 22.04 e Ubuntu 24.04;
- Python 3.12, PyQt6 e SQLite nativo.

## Validação de código

- 410 testes automatizados aprovados antes da publicação;
- `compileall`, `pip check` e `git diff --check` aprovados.
