# SmartFile — Manual do Usuário

**Versão do manual:** 1.4

**Aplicação:** SmartFile — Mini GED Local

**Plataformas:** Linux e Windows

## 1. Apresentação

O SmartFile é um gerenciador local de documentos com organizações independentes,
pastas lógicas, pesquisa, favoritos, histórico, Scanner, conversão, ferramentas de
PDF, visualização interna, assinatura e sincronização opcional em nuvem.

O arquivo original importado é mantido no armazenamento interno gerenciado pelo
SmartFile. Pastas exibidas no módulo Documentos são lógicas e não precisam
corresponder a diretórios físicos do computador.

## 2. Iniciando a aplicação

Com o ambiente e as dependências instalados, execute na pasta do projeto:

```bash
python run.py
```

Quando utilizado o ambiente virtual incluído no projeto:

```bash
venv/bin/python run.py
```

Na primeira execução, o SmartFile abre o cadastro inicial. Nas execuções seguintes,
abre a tela de login. A janela principal não é disponibilizada sem autenticação.

## 3. Primeiro acesso

O cadastro utiliza um wizard de quatro etapas:

1. Em **Dados pessoais**, informe nome, username, contatos, senha e avatar opcional.
2. Em **Organização**, escolha nome, descrição, ícone, cor, modelo de pastas e plano de armazenamento.
3. Em **Resumo**, confira os dados, as pastas previstas e o papel `OWNER`.
4. Selecione **Finalizar** e, após a conclusão, **Entrar no SmartFile**.

É possível voltar às etapas anteriores sem persistir dados parciais.

O primeiro usuário recebe o papel de proprietário (`OWNER`) da organização padrão
e torna-se o administrador global da instalação. Administradores de uma organização
não recebem automaticamente permissão para alterar a configuração OAuth global.
Os modelos Pessoal, Estudante e Empresarial servem somente para criar as pastas
iniciais; eles não são níveis de acesso.

O modelo de pastas e o plano de armazenamento são conceitos separados. O SmartFile
oferece planos lógicos de **10 GB**, **20 GB** e **60 GB**. A sugestão inicial é
Pessoal 10 GB, Estudante 20 GB e Empresarial 60 GB, mas o plano pode ser escolhido
independentemente do modelo.

### Modelos disponíveis

| Modelo | Pastas iniciais |
|---|---|
| Pessoal | Documentos pessoais, Contas, Garantias, Saúde, Imposto de Renda e Comprovantes |
| Estudante | Disciplinas, Trabalhos, Projetos, TCC, Certificados e Livros e materiais |
| Empresarial | Financeiro, Fiscal, Recursos Humanos, Contratos, Clientes, Fornecedores, Administrativo e Projetos |
| Começar vazio | Não cria pastas automaticamente |

## 4. Login e conta

É possível entrar usando o nome de usuário ou o e-mail cadastrado.

1. Informe o usuário ou e-mail.
2. Informe a senha.
3. Selecione **Entrar**.

Após cinco tentativas inválidas consecutivas, a conta é bloqueada temporariamente
por segurança. O SmartFile não cria contas ou senhas padrão.

No menu da conta é possível:

- trocar a organização ativa;
- alterar a senha;
- excluir a própria conta;
- encerrar a sessão.

Ao sair, a sessão atual é revogada e o SmartFile retorna à tela de login.

### Excluir a própria conta

Selecione **Excluir minha conta**, informe a senha atual e digite `EXCLUIR`. A
operação revoga todas as sessões, remove os vínculos ativos e anonimiza username,
e-mail, telefone, avatar e senha. Documentos e registros de auditoria são
preservados. Se o usuário for o único `OWNER` de uma organização que ainda possui
outros membros, deverá transferir a propriedade antes da exclusão.

Quando a conta for o único membro de uma organização conectada à nuvem, o vínculo
OAuth local, os tokens e a conta local do provedor também serão removidos. Essa
ação não apaga os documentos armazenados no SmartFile.

## 5. Organizações e pastas

Cada organização mantém documentos, pastas, favoritos, recentes e histórico
independentes. Para visualizar dados de outra organização, é necessário trocá-la
explicitamente no seletor ou no menu da conta.

No módulo Documentos, o usuário pode:

- criar e editar organizações;
- criar pastas e subpastas;
- renomear e mover pastas;
- selecionar uma pasta para filtrar os documentos;
- mover itens para a lixeira.

### Gerenciar organizações

No menu da conta, selecione **Gerenciar organizações** para consultar quantidades
de documentos, pastas e membros, provedor de nuvem, status e atividade. Conforme
as permissões, é possível criar, editar, abrir, duplicar a estrutura ou arquivar.

Arquivar é uma operação lógica: documentos e arquivos físicos são preservados. A
confirmação exige digitar exatamente o nome da organização. A única organização
ativa do usuário e organizações com sincronização em andamento não podem ser
arquivadas.

### Usuários e permissões

Usuários autorizados podem adicionar contas locais existentes, criar uma conta
temporária, alterar papéis, desativar vínculos, remover membros e transferir a
propriedade. A organização deve manter pelo menos um `OWNER`. A transferência é
uma ação separada e exige a senha atual do proprietário.

Ao criar uma organização, pode-se escolher novamente um modelo de pastas. Essa
escolha não altera as permissões do usuário.

## 6. Documentos

### Importar

1. Abra o módulo **Documentos**.
2. Selecione **Importar** ou **Adicionar documento**.
3. Escolha um arquivo regular do computador.
4. Selecione a organização e a pasta lógica de destino, quando solicitado.
5. Confirme a importação.

O SmartFile calcula o checksum SHA-256, cria um nome interno seguro e registra o
documento no SQLite. O arquivo de origem não deve ser editado diretamente dentro
do storage gerenciado.

### Pesquisar e filtrar

Utilize o campo de busca para pesquisar por nome, categoria ou etiqueta. Também é
possível consultar favoritos, documentos recentes, pastas e lixeira.

### Favoritos

Selecione um documento e use a ação **Favorito**. O documento permanece na mesma
pasta e passa a ser exibido também na seção de favoritos.

### Lixeira

A exclusão normal move o documento para a lixeira. Ela não deve ser confundida com
remoção permanente. Confirme sempre a organização e o documento selecionados antes
de excluir.

Clique com o botão direito sobre um documento para abrir o menu contextual. Na lista
normal estão disponíveis **Copiar**, **Colar** e **Mover para lixeira**. Na Lixeira,
o menu oferece **Copiar**, **Colar**, **Restaurar**, **Excluir definitivamente** e
**Esvaziar lixeira**. Exclusões definitivas removem também o arquivo gerenciado e
não podem ser desfeitas.

### Armazenamento da organização

O painel **Armazenamento** mostra plano, uso, reserva, espaço disponível, percentual
e estado. Os valores são exibidos em GB; internamente o SmartFile controla os
valores em bytes.

- até 79%: normal;
- de 80% a 89%: atenção;
- de 90% a 99%: crítico;
- 100%: bloqueado.

Antes de criar um arquivo gerenciado, o SmartFile reserva o espaço necessário. A
reserva evita que duas importações simultâneas ultrapassem a cota. A lixeira continua
consumindo armazenamento; o espaço só é liberado depois da exclusão permanente do
arquivo. Use **Gerenciar armazenamento** para abrir a lixeira, recalcular o uso ou
consultar os maiores arquivos, alterar o plano, iniciar a sincronização ou ver erros
da nuvem. Um plano menor não pode ser aplicado quando o uso e as reservas atuais
ultrapassarem o novo limite.

## 7. Visualizador de PDF

A ação **Visualizar** abre o leitor interno. A ação **PDF Tools** abre o manipulador
estrutural; são módulos diferentes.

No visualizador é possível:

- navegar entre páginas;
- usar miniaturas;
- aumentar ou reduzir o zoom;
- ajustar à largura ou à página;
- girar a visualização sem alterar o arquivo;
- pesquisar texto com `Ctrl+F`;
- consultar informações do PDF;
- imprimir;
- entrar em tela cheia com `F11`;
- consultar assinaturas detectadas.

Atalhos principais:

| Atalho | Ação |
|---|---|
| `PageUp` / `PageDown` | Página anterior ou seguinte |
| `Home` / `End` | Primeira ou última página |
| `Ctrl++` / `Ctrl+-` | Aumentar ou reduzir zoom |
| `Ctrl+0` | Restaurar zoom |
| `Ctrl+F` | Pesquisar texto |
| `F11` | Tela cheia |
| `Esc` | Fechar pesquisa ou sair da tela cheia |

PDFs digitalizados sem camada de texto não podem ser pesquisados nesta fase. O
visualizador não executa OCR automaticamente.

## 8. PDF Tools

O módulo PDF Tools é destinado à manipulação estrutural. Ele permite:

- adicionar PDFs;
- remover páginas;
- alterar a ordem;
- girar páginas permanentemente;
- extrair páginas;
- dividir documentos;
- mesclar PDFs;
- salvar um novo PDF.

Revise a seleção de páginas antes de aplicar alterações. Sempre que possível,
salve o resultado como um novo arquivo para preservar o original.

## 9. Scanner

1. Abra **Scanner**.
2. Selecione o dispositivo disponível.
3. Escolha perfil, fonte do papel e resolução.
4. Coloque o documento na mesa ou no alimentador selecionado.
5. Selecione **Digitalizar**.
6. Revise as páginas.
7. Use **Digitalizar e adicionar mais** quando necessário.
8. Para exportar, selecione **Salvar documento**.
9. Para cadastrar diretamente, selecione **Adicionar ao GED**.
10. Escolha organização e pasta, preencha título, categoria, descrição, etiquetas,
    data e observações, e confirme.

As setas na lista permitem reordenar as páginas antes da geração do PDF. Ao adicionar
ao GED, o SmartFile cria um PDF temporário, verifica e reserva a cota, copia o arquivo
para o storage interno, persiste os metadados com origem `SCANNER`, registra o
histórico e enfileira a nuvem vinculada. O temporário é removido ao final.

As opções disponíveis dependem do driver SANE no Linux ou TWAIN no Windows e das
capacidades do equipamento. A mensagem “alimentador sem documentos” indica que a
fonte ADF foi escolhida, mas não há papel no alimentador; coloque as folhas ou
troque a fonte para mesa/Flatbed.

## 10. Assinaturas

### Assinatura digital

A assinatura digital utiliza certificado A1 `.pfx` ou `.p12` e produz uma assinatura
criptográfica real no PDF.

1. Abra o PDF no visualizador.
2. Selecione **Assinar digitalmente**.
3. Escolha o certificado A1.
4. Informe a senha do certificado.
5. Defina assinatura visível ou invisível.
6. Para assinatura visível, escolha página e posição.
7. Informe motivo e localização, se necessário.
8. Escolha um novo arquivo de saída.
9. Confirme a assinatura.

O original é preservado. A senha e a chave privada não são armazenadas. O suporte
inicial é PAdES-B-B; não se deve considerar implementado certificado A3 ou PAdES-LT/LTA.

### Assinatura manuscrita eletrônica

A assinatura manuscrita insere uma representação visual no documento. Ela não é
equivalente a uma assinatura digital baseada em certificado e não oferece, sozinha,
prova criptográfica de integridade.

## 11. Nuvem

O armazenamento interno permanece como fonte principal. OneDrive e Google Drive
são provedores opcionais de sincronização e são acessados somente pela Cloud Layer.

No módulo Documentos, a organização pode trabalhar como:

- Local;
- OneDrive;
- Google Drive.

Quando não há internet, os documentos locais continuam disponíveis e as operações
podem permanecer na fila. A sincronização é retomada quando houver conexão e uma
conta corretamente configurada.

Para adicionar uma conta, selecione **Adicionar Conta → Microsoft OneDrive** ou
**Adicionar Conta → Google Drive**. O SmartFile abre a página oficial de autorização
no navegador. O provedor só é ativado depois que a autorização for concluída. O
usuário comum nunca precisa informar Client ID, Tenant, segredo ou arquivo JSON.

Se a integração ainda não tiver sido preparada, a tela mostrará **Integração não
configurada pelo administrador**. A configuração pública do aplicativo pertence ao
administrador ou ao empacotamento do SmartFile e não deve ser confundida com a conta
OneDrive/Google Drive escolhida pelo usuário.

Somente o administrador global da instalação visualiza **Configurar provedor**.
Essa ação serve exclusivamente para fornecer a configuração OAuth pública do
aplicativo SmartFile; ela não efetua login e não recebe tokens de usuários.

- **OneDrive:** registrar o SmartFile no Microsoft Entra, configurar aplicativo
  público em **Aplicativos móveis e da área de trabalho**, cadastrar exatamente o
  redirect URI `http://localhost`, habilitar fluxos de cliente público e adicionar
  as permissões delegadas `User.Read` e `Files.ReadWrite`. Depois, informar o
  Application (client) ID e o tenant. Não é necessário Client Secret.
- **Google Drive:** criar um projeto no Google Cloud, habilitar a Drive API, criar
  um cliente OAuth do tipo Desktop e selecionar o JSON disponibilizado pelo Google.

Use **Remover conta/login** para desvincular a organização. O SmartFile volta ao
modo local, apaga os tokens locais e preserva os documentos internos.

As configurações são criptografadas no diretório de dados. A autenticação é executada
pelas APIs Python `msal` e `google-auth-oauthlib`, usando navegador do sistema e
callback local. Tokens não são exibidos na interface; o SQLite contém somente uma
referência ao cofre do sistema ou ao cofre local cifrado.

Nunca informe tokens manualmente em telas que não sejam destinadas à configuração
da conta. Tokens não são exibidos pela interface.

## 12. Casos de uso

### UC-01 — Criar o primeiro usuário

**Ator principal:** primeiro usuário do SmartFile.

**Pré-condição:** não existir usuário cadastrado no banco local.

**Gatilho:** iniciar a aplicação.

**Fluxo principal:**

1. O SmartFile identifica que o banco não possui usuários.
2. O sistema apresenta o cadastro inicial.
3. O usuário informa seus dados pessoais.
4. O usuário personaliza a organização e escolhe um modelo de pastas.
5. O sistema apresenta o resumo antes da confirmação.
6. O sistema valida username, e-mail, senha, avatar e organização.
7. O sistema cria o usuário e protege a senha com Argon2id.
8. O sistema cria ou atualiza a organização padrão.
9. O sistema vincula o usuário como `OWNER`.
10. O sistema cria as pastas lógicas do modelo selecionado.
11. O sistema cria uma sessão autenticada.
12. A conclusão é apresentada e a janela principal é liberada.

**Fluxos alternativos:**

- Se o username ou e-mail já estiver em uso, o cadastro é recusado.
- Se a senha não cumprir a política, o sistema informa a validação necessária.
- Se alguma gravação falhar, toda a operação é revertida.

**Resultado:** usuário autenticado, organização ativa e estrutura inicial persistida.

### UC-02 — Entrar no SmartFile

**Ator principal:** usuário cadastrado.

**Pré-condição:** usuário ativo e vinculado a pelo menos uma organização.

**Fluxo principal:**

1. O usuário informa username ou e-mail e senha.
2. O sistema valida as credenciais.
3. O sistema carrega as organizações vinculadas.
4. O sistema cria a sessão e registra o último acesso.
5. O sistema abre a organização ativa na janela principal.

**Fluxos alternativos:**

- Credenciais inválidas: o sistema exibe “Usuário ou senha inválidos”.
- Usuário inativo: o acesso é negado.
- Conta temporariamente bloqueada: o usuário deve aguardar o período informado.

**Resultado:** sessão autenticada e acesso somente às organizações vinculadas.

### UC-03 — Criar uma conta local adicional

**Ator principal:** novo usuário local.

**Pré-condição:** cadastro local habilitado.

**Fluxo principal:**

1. Na tela de login, o usuário seleciona **Criar conta**.
2. Informa seus dados e escolhe um modelo.
3. O sistema cria uma nova organização independente.
4. O sistema vincula o novo usuário como `OWNER`.
5. O sistema cria as pastas e inicia a sessão.

**Resultado:** nova conta sem acesso automático à organização de outros usuários.

### UC-04 — Importar e organizar um documento

**Ator principal:** usuário com permissão de importação.

**Pré-condições:** sessão autenticada e organização ativa.

**Fluxo principal:**

1. O usuário abre Documentos e escolhe uma pasta lógica.
2. Seleciona **Importar**.
3. Escolhe um arquivo válido.
4. O SmartFile valida o caminho e calcula o checksum.
5. O SmartFile valida a cota e reserva o tamanho necessário.
6. O arquivo é copiado para o storage interno com identificador seguro.
7. Os metadados são persistidos no SQLite e a reserva é convertida em uso.
8. A operação é registrada no histórico.
9. Se houver nuvem configurada, um trabalho de upload é colocado na fila.

**Fluxos alternativos:**

- Arquivo inválido ou inexistente: a importação é cancelada.
- Checksum duplicado: o sistema impede ou informa a duplicidade.
- Sem internet: o documento permanece local e o upload fica pendente.
- Cota insuficiente: nenhuma cópia ou registro parcial é mantido.
- Disco local insuficiente: a mensagem diferencia espaço físico de cota lógica.

**Resultado:** documento disponível na organização e pasta selecionadas.

### UC-05 — Localizar e visualizar um PDF

**Ator principal:** usuário autenticado.

**Fluxo principal:**

1. O usuário pesquisa por nome, categoria ou etiqueta.
2. Seleciona o documento encontrado.
3. Aciona **Visualizar**.
4. O sistema valida e abre o PDF no leitor interno.
5. O usuário navega, aplica zoom ou pesquisa texto.

**Fluxos alternativos:**

- PDF protegido: o visualizador solicita ou informa a necessidade de senha.
- PDF inválido: é apresentada uma mensagem amigável.
- Documento sem texto: a pesquisa informa que não há camada pesquisável.

**Resultado:** documento consultado sem alteração estrutural do arquivo.

### UC-06 — Digitalizar um documento

**Ator principal:** usuário com scanner configurado.

**Pré-condição:** dispositivo reconhecido pelo backend SANE ou TWAIN.

**Fluxo principal:**

1. O usuário seleciona dispositivo, fonte e resolução.
2. Aciona **Digitalizar**.
3. O backend SANE ou TWAIN executa a captura.
4. O sistema apresenta a página no preview.
5. O usuário adiciona outras páginas ou conclui a sessão.
6. O usuário reordena ou remove páginas, se necessário.
7. O documento é exportado ou adicionado diretamente ao GED.

**Fluxo alternativo:** se o alimentador estiver vazio, o sistema orienta colocar
papel ou selecionar a mesa do scanner.

**Resultado:** PDF digitalizado exportado ou cadastrado no GED sem uma segunda importação.

### UC-07 — Manipular um PDF

**Ator principal:** usuário autenticado.

**Fluxo principal:**

1. O usuário abre o documento em **PDF Tools**.
2. Seleciona páginas.
3. Executa adicionar, remover, mover, girar, extrair, dividir ou mesclar.
4. Revisa o preview.
5. Seleciona **Aplicar e salvar**.
6. O sistema gera o arquivo resultante.

**Resultado:** novo PDF com as alterações estruturais solicitadas.

### UC-08 — Assinar digitalmente um PDF

**Ator principal:** titular de certificado A1 válido.

**Pré-condições:** PDF válido e certificado `.pfx` ou `.p12` disponível.

**Fluxo principal:**

1. O usuário abre o PDF no visualizador.
2. Inicia a assinatura digital.
3. Seleciona certificado, saída e aparência.
4. Informa a senha do certificado.
5. O serviço valida a solicitação e assina o PDF em background.
6. O sistema grava atomicamente um novo PDF.
7. O usuário pode importar o resultado no GED.

**Fluxos alternativos:**

- Senha do certificado incorreta: nenhuma saída parcial permanece.
- Certificado inválido ou expirado: a operação é recusada.
- Saída igual ao original: o sistema impede a sobrescrita.

**Resultado:** novo PDF assinado, com o original preservado.

### UC-09 — Sincronizar uma organização

**Ator principal:** usuário com conta de nuvem configurada.

**Pré-condição:** organização configurada com OneDrive ou Google Drive.

**Fluxo principal:**

1. O usuário importa ou altera um documento local.
2. A Cloud Layer cria um trabalho na fila.
3. O Worker seleciona o provider configurado.
4. O arquivo é enviado e seus metadados remotos são registrados.
5. O documento passa para o estado sincronizado.

**Fluxos alternativos:**

- Sem conexão: o trabalho permanece pendente.
- Token expirado: o provider tenta atualizar a autenticação.
- Falha remota: o estado de erro e a mensagem técnica são registrados sem expor tokens.

**Resultado:** cópia remota associada ao documento local da organização.

### UC-10 — Trocar de organização

**Ator principal:** usuário vinculado a mais de uma organização.

**Fluxo principal:**

1. O usuário abre o menu da conta ou seletor de organização.
2. Escolhe outra organização vinculada.
3. O sistema valida o membership.
4. Documentos, pastas, favoritos, recentes e histórico são atualizados.

**Fluxo alternativo:** uma organização sem vínculo ativo não pode ser selecionada.

**Resultado:** apenas os dados da nova organização ativa são apresentados.

### UC-11 — Controlar a cota de armazenamento

**Ator principal:** usuário da organização.

**Fluxo principal:**

1. O usuário inicia uma importação, cópia, digitalização ou incorporação de resultado.
2. O sistema calcula o tamanho e verifica cota e espaço livre local.
3. O sistema persiste uma reserva temporária.
4. Após arquivo e registro serem validados, a reserva é convertida em uso.
5. O painel atualiza o percentual e o estado textual.

**Fluxos alternativos:**

- Se a cota for insuficiente, o sistema informa uso, limite e tamanho solicitado.
- Se a criação falhar, a reserva e arquivos parciais são removidos.
- Mover para a lixeira não libera espaço; excluir definitivamente libera.
- Se a nuvem estiver cheia, o documento local é preservado e a sincronização recebe erro.

**Resultado:** uso coerente por organização sem ultrapassagem por operações simultâneas.

## 13. Boas práticas

- Use uma senha exclusiva para o SmartFile.
- Não compartilhe a senha do certificado digital.
- Não altere manualmente arquivos dentro do storage interno.
- Revise a organização ativa antes de importar documentos.
- Use a lixeira antes de considerar uma exclusão permanente.
- Preserve o PDF original ao usar ferramentas ou assinaturas.
- Mantenha backups do banco e do storage em conjunto.
- Não desligue o computador durante gravações ou atualizações do banco.

## 14. Solução de problemas

| Situação | Orientação |
|---|---|
| Usuário ou senha inválidos | Verifique o identificador, o teclado e a senha cadastrada |
| Conta temporariamente bloqueada | Aguarde 15 minutos antes de tentar novamente |
| Scanner sem documentos | Coloque papel no ADF ou selecione Flatbed/Mesa |
| PDF não abre | Confirme se o arquivo é PDF válido e se exige senha |
| Pesquisa não encontra texto | O documento pode ser apenas imagem, sem camada de texto |
| Documento não sincroniza | Verifique conexão, conta ativa e estado da fila |
| Limite de armazenamento atingido | Esvazie a lixeira, altere o plano ou remova definitivamente arquivos desnecessários |
| Disco local sem espaço | Libere espaço no disco; esta situação é diferente da cota da organização |
| Certificado não carrega | Confirme o arquivo A1, a validade e a senha |

## 15. Limitações conhecidas

Nesta versão não estão incluídos:

- recuperação de senha por e-mail;
- login Google ou Microsoft como autenticação do SmartFile;
- autenticação em dois fatores;
- certificado A3;
- OCR automático no visualizador;
- colaboração simultânea;
- resolução automática de conflitos de nuvem;
- perfis PAdES-LT ou PAdES-LTA;
- alteração obrigatória automática da senha temporária no primeiro login; o estado
  já é registrado, mas o bloqueio guiado será concluído em fase futura.

## 16. Encerramento

Para encerrar a sessão, utilize **Conta → Sair**. O logout revoga a sessão atual e
retorna à tela de login. Depois disso, a aplicação pode ser fechada normalmente.

## 17. Instalação da versão beta no Linux

Em sistemas amd64 compatíveis com Linux Mint, Ubuntu ou Debian, instale o pacote
baixado usando o APT:

```bash
sudo apt install ./smartfile_0.9.0~beta1_amd64.deb
```

O SmartFile pode ser aberto pelo menu de aplicativos ou pelo comando
`smartfile`. Scanner, conversões e integração com o cofre de credenciais podem
depender de componentes opcionais do sistema; consulte `BETA_LINUX.md`.

Para remover somente o aplicativo:

```bash
sudo apt remove smartfile
```

A remoção do pacote preserva documentos, banco, tokens protegidos, configurações
e backups do usuário. A exclusão total desses dados é uma operação manual e
irreversível, descrita no guia da versão beta.

## 18. Backup administrativo ZIP

Somente o administrador do sistema visualiza a opção **Conta → Criar backup
ZIP**. Antes de qualquer operação, o SmartFile pergunta se o administrador
deseja realmente iniciar o backup. Se a resposta for negativa, nenhum arquivo é
criado e nenhuma pasta é solicitada.

O backup completo inclui:

- snapshot consistente do banco SQLite;
- documentos do storage interno de todas as organizações;
- avatares locais;
- manifesto com versão, tamanho e SHA-256 de cada arquivo.

Tokens, credenciais OAuth, configuração privada de provedores, logs, cache,
temporários e backups anteriores não são incluídos. A geração ocorre em segundo
plano e produz um arquivo `.zip` por escrita atômica, evitando manter saída
parcial em caso de falha.

O arquivo ZIP deve ser guardado em local seguro. Embora credenciais externas
sejam excluídas, o backup contém documentos e dados cadastrais sensíveis. A
restauração automática será implementada separadamente, com validação integral
do manifesto e confirmação administrativa específica.
