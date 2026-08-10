# SmartFile 0.9.0-beta.2

Versão beta publicada em 7 de agosto de 2026 para avaliação técnica.

## Principais alterações

- perfis de recursos separados das funcionalidades efetivamente ativadas em cada organização;
- padrão Empresarial conservador: controle de acesso e auditoria ativos, integrações externas opcionais;
- transporte corporativo NAS, LAN ou HTTPS independente da Cloud Layer e do OAuth;
- validação de permissão, perfil, organização ativa e destino antes de configurar transporte;
- solicitações documentais opcionais com responsável limitado a membro ativo da organização;
- prazos ativados de forma independente das solicitações;
- migração incremental do banco para a versão 15, preservando configurações em uso;
- aviso não bloqueante de novidades exibido uma vez por versão instalada.

### Incremento de transporte NAS

- fila corporativa persistente e independente da Cloud Layer;
- cópia NAS real em background, por chunks e com progresso baseado em bytes;
- arquivo temporário, conclusão atômica e validação SHA-256;
- retry limitado e recuperação quando o NAS volta a ficar disponível;
- exclusão NAS somente após exclusão definitiva no SmartFile;
- teste administrativo de conexão e auditoria de sucesso ou falha;
- snapshots imutáveis de destino para preservar retries e DELETEs após troca de NAS;
- reconciliation conservadora para jobs históricos sem destino comprovável;
- Credential Vault via keyring do sistema operacional, sem segredo no SQLite;
- migration 17, sem alteração do número público `0.9.0-beta.2`.

## Segurança e compatibilidade

Credenciais não podem ser incluídas na URL do transporte. `credential_ref`
aponta para o cofre do sistema operacional e o banco não armazena username ou
senha. Rotação cria nova referência e preserva a anterior enquanto houver job ou
arquivo remoto dependente. O NAS funciona como filesystem previamente
montado ou compartilhamento UNC acessível pelo sistema operacional. O SmartFile
não monta o compartilhamento. LAN e HTTPS não fingem transferência: seus
conectores físicos permanecem para uma etapa futura.

A Cloud Layer para OneDrive e Google Drive continua separada e não foi
substituída pelo transporte corporativo.

## Artefatos beta

- `smartfile_0.9.0~beta2_amd64.deb`;
- `SmartFile-0.9.0-beta.2-Windows-x64-Setup.exe`;
- `SmartFile-0.9.0-beta.2-Windows-x64-Portable.zip`;
- arquivos `.sha256` correspondentes.

Esta versão ainda é beta. Faça backup independente e relate falhas pelo GitHub,
informando sistema operacional, versão e passos para reprodução, sem anexar
documentos, tokens, senhas ou outros dados sensíveis.
