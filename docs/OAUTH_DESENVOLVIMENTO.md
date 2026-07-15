# OAuth de nuvem — configuração administrativa

Este documento é destinado a desenvolvimento, administração e empacotamento. O
usuário final conecta a própria conta apenas pelo botão **Adicionar Conta**.

Na interface, a ação **Configurar provedor** é apresentada somente ao administrador
global (`is_superuser`). O papel `ADMIN` de uma organização não autoriza mudanças
na configuração OAuth de toda a instalação.

## Ordem de resolução

O `CloudOAuthConfigurationService` procura uma configuração válida nesta ordem:

1. recurso público empacotado;
2. variável de ambiente;
3. configuração administrativa local cifrada;
4. configuração de desenvolvimento;
5. ausente (`MISSING`).

Nunca empacote tokens, credenciais pessoais, chaves privadas ou client secret de
backend. Aplicativos desktop são clientes públicos.

## Microsoft OneDrive

1. Registre o SmartFile no Microsoft Entra.
2. Selecione os tipos de conta compatíveis com a distribuição.
3. Habilite o fluxo de cliente público.
4. Em **Autenticação → Adicionar uma plataforma**, selecione **Aplicativos móveis
   e da área de trabalho** e configure exatamente `http://localhost` como redirect
   URI para o navegador do sistema.
5. Em configurações avançadas, habilite **Permitir fluxos de cliente público**.
6. Em **Permissões de API**, adicione as permissões delegadas Microsoft Graph
   `User.Read` e `Files.ReadWrite`.
7. Copie o Application (client) ID. Não crie Client Secret para este fluxo Desktop.
8. Defina Tenant/Authority (`common`, `organizations` ou tenant autorizado).
9. Forneça `SMARTFILE_ONEDRIVE_CLIENT_ID` e, opcionalmente,
   `SMARTFILE_ONEDRIVE_TENANT`, ou use **Configurar provedor** no SmartFile.
10. Teste autenticação, renovação, desconexão e outra conta.

## Google Drive

1. Crie um projeto no Google Cloud.
2. Habilite a Google Drive API.
3. Configure a tela de consentimento.
4. Crie um OAuth Client do tipo **Desktop app**.
5. Forneça o JSON por `SMARTFILE_GOOGLE_DRIVE_CLIENT_CONFIG_FILE`, o conteúdo por
   `SMARTFILE_GOOGLE_DRIVE_CLIENT_CONFIG`, ou use a configuração administrativa.
6. Teste callback local, cancelamento, renovação e desconexão.

## Recursos empacotados e desenvolvimento

Arquivos públicos opcionais podem ser distribuídos em
`app/cloud/resources/onedrive.json` e `app/cloud/resources/google_drive.json`.
Variáveis de desenvolvimento usam os mesmos nomes com prefixo `SMARTFILE_DEV_`.

Antes de publicar o instalador, valide caminhos de recursos no Linux e Windows e
confirme que nenhum token de teste, arquivo pessoal ou segredo de backend foi incluído.

## Remoção de conta

**Remover conta/login** desvincula a organização, retorna o modo para `LOCAL` e
remove do TokenStore os tokens que não estiverem compartilhados por outro vínculo.
Quando não restar conta do provedor, o cache OAuth correspondente também é apagado.
A configuração pública do aplicativo é preservada para permitir novas conexões.
