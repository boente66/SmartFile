# OAuth de nuvem — configuração administrativa

Este documento é destinado a desenvolvimento, administração e empacotamento. O
usuário final conecta a própria conta apenas pelo botão **Adicionar Conta**.

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
4. Configure redirect URI para aplicativo desktop/loopback.
5. Copie o Application (client) ID.
6. Defina Tenant/Authority (`common`, `organizations` ou tenant autorizado).
7. Forneça `SMARTFILE_ONEDRIVE_CLIENT_ID` e, opcionalmente,
   `SMARTFILE_ONEDRIVE_TENANT`, ou use a configuração administrativa avançada.
8. Teste autenticação, renovação, desconexão e outra conta.

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
