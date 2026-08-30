# Guia de teste — SmartFile Windows 0.9.0 Beta 5

## Aviso

**Esta é uma versão beta para avaliação. Não utilize o SmartFile como única
cópia de documentos importantes.**

O instalador é produzido automaticamente em um runner Windows do GitHub
Actions. Isso não substitui homologação manual em Windows 10 ou 11 real.

O instalador x64 declara como baseline Windows 10 versão 1809
(`10.0.17763`) e também aceita Windows 11. Versões anteriores são bloqueadas
pelo instalador para evitar uma instalação aparentemente bem-sucedida em um
sistema sem suporte.

## Preparação

1. No GitHub, abra **Actions > Windows beta package**.
2. Selecione a execução desejada e baixe o artefato
   `SmartFile-0.9.0-beta.5-Windows-x64`.
3. Extraia o ZIP do artefato do Actions.
4. Compare o SHA-256 do instalador ou do ZIP portátil:

```powershell
(Get-FileHash .\SmartFile-0.9.0-beta.5-Windows-x64-Setup.exe -Algorithm SHA256).Hash
Get-Content .\SmartFile-0.9.0-beta.5-Windows-x64-Setup.exe.sha256
```

Os dois valores devem ser iguais. Interrompa o teste se forem diferentes.

## Roteiro do instalador

1. Execute `SmartFile-0.9.0-beta.5-Windows-x64-Setup.exe`.
2. Confirme que o instalador identifica a versão como beta.
3. Mantenha o diretório padrão em `C:\Program Files\SmartFile`.
4. Escolha se deseja o atalho opcional na Área de Trabalho.
5. Conclua a instalação sem executar o aplicativo como administrador.
6. Inicie o SmartFile pelo Menu Iniciar.
7. Crie o primeiro usuário e uma organização de teste.
8. Saia e teste o login novamente.
9. Guarde um código de recuperação, saia e teste **Esqueci minha senha**.
10. Confirme que o código utilizado não pode ser reutilizado.
11. Importe uma cópia descartável de um documento.
12. Abra o PDF Viewer e teste navegação, zoom e retorno a Documentos.
13. Abra o mesmo PDF em PDF Tools e salve uma cópia.
14. Teste assinatura manuscrita em uma cópia.
15. Teste assinatura digital somente com certificado de teste.
16. Se houver scanner com driver TWAIN x64, teste detecção e captura.
17. Sem scanner, confirme que o módulo informa a indisponibilidade sem fechar o
    restante do aplicativo.
18. Teste logout, fechamento e nova abertura.
19. Desinstale em **Configurações > Aplicativos instalados**.
20. Confirme que os dados permanecem em `%LOCALAPPDATA%\SmartFile` e a
    configuração em `%APPDATA%\SmartFile`.

## Roteiro da versão portátil

1. Extraia `SmartFile-0.9.0-beta.5-Windows-x64-Portable.zip` em uma pasta comum.
2. Execute `SmartFile.exe` sem instalar Python.
3. Repita login, importação e abertura após reiniciar o aplicativo.
4. Confirme que banco, storage e logs não foram criados dentro da pasta
   portátil.

## Nuvem e dependências externas

- OneDrive e Google Drive podem aparecer como `NOT_CONFIGURED` até que um
  administrador informe a configuração OAuth pública do aplicativo.
- Nunca use credenciais OAuth pessoais em um build distribuído.
- Scanner requer driver TWAIN x64 do fabricante.
- Conversões do Microsoft Office podem exigir o Office instalado.
- Poppler ou LibreOffice podem ser necessários em fluxos específicos.

## Como reportar

Abra uma issue usando o formulário **Windows beta bug**. Informe versão do
Windows, arquitetura, instalação ou portátil, etapas de reprodução e mensagens
visíveis. Anexe somente logs sanitizados e screenshots sem dados pessoais.

Nunca envie tokens, senhas, PINs, certificados, chaves privadas ou documentos
confidenciais.
