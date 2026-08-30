# SmartFile 0.9.0-beta.5

Versão beta voltada à experiência de entrada e à estabilidade das entregas
entre instalações SmartFile na rede local. Mantenha backup independente e
relate problemas no GitHub.

## Boas-vindas personalizadas

- após o login, o SmartFile apresenta uma notificação discreta com o primeiro
  nome da conta e a organização ativa;
- a notificação não bloqueia a interface, acompanha o redimensionamento, pode
  ser fechada e desaparece automaticamente;
- o nome é obtido exclusivamente da sessão autenticada.

## Resiliência offline em Solicitações e Entregas

- erros como “Não há rota para o host” são tratados como indisponibilidade
  temporária do dispositivo;
- entregas e comprovantes continuam na fila persistente;
- retentativas mantêm backoff exponencial e limite de oito tentativas;
- a tela informa que o dispositivo está offline e que haverá nova tentativa;
- a primeira indisponibilidade é registrada, enquanto repetições equivalentes
  deixam de poluir o log;
- falhas inesperadas continuam registrando detalhes técnicos para diagnóstico.

## Compatibilidade

- Windows 10 e Windows 11 x64;
- Linux amd64 com baseline Ubuntu 22.04/GLIBC 2.35;
- mesmo `.deb` validado em Ubuntu 22.04 e Ubuntu 24.04;
- Python 3.12, PyQt6 e SQLite nativo.

## Segurança e preservação

- nenhuma credencial ou conteúdo documental é incluído na notificação;
- nenhum traceback técnico é apresentado ao usuário;
- banco, documentos, permissões, Cloud Layer e contratos públicos foram
  preservados;
- schema permanece na versão 22.
