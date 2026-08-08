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

## Segurança e compatibilidade

Credenciais não podem ser incluídas na URL do transporte. O campo reservado
`credential_ref` prepara integração futura com um cofre seguro, sem armazenar
segredos na configuração do destino. Nenhum conector NAS/LAN/HTTPS foi simulado:
a configuração valida e persiste o destino, enquanto a transferência efetiva
depende de um contrato técnico posterior.

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
