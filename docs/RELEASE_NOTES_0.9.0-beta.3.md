# SmartFile 0.9.0-beta.3

Versão beta publicada para testes e avaliação da experiência do módulo
Documentos. O armazenamento interno e os contratos entre Views,
Controllers, Services e Repositories foram preservados.

## Mapeamento seguro de pasta OneDrive

- uma pasta lógica pode adotar o `remote_id` de uma pasta OneDrive existente;
- a navegação remota é paginada e executada fora da thread da interface;
- pastas adotadas não são renomeadas, movidas ou excluídas pelo SmartFile;
- remover o mapeamento preserva integralmente o conteúdo remoto;
- mappings são vinculados à conta ativa e invalidados ao trocar a conta;
- o schema 19 registra `cloud_account_id` e a política `MANAGED`/`ADOPTED`.

## Destaques

- cabeçalho unificado para organização, perfil, nuvem e armazenamento;
- barra compacta com as ações documentais existentes;
- busca e filtros indexados recolhíveis;
- breadcrumb das pastas lógicas;
- controles para mostrar ou ocultar navegação e detalhes;
- tabela com ícones por tipo e data da última modificação;
- barra inferior com estado da seleção e sincronização;
- versão do protocolo Delivery/LAN centralizada;
- respostas seguras e estruturadas no endpoint de identidade LAN.

## Compatibilidade beta

- Windows x64: Windows 10 e Windows 11;
- Linux amd64: Ubuntu 22.04, Ubuntu 24.04 e versões posteriores compatíveis;
- distribuições derivadas de Ubuntu/Debian devem possuir bibliotecas compatíveis
  com a baseline GLIBC 2.35.

O pacote Linux é compilado no Ubuntu 22.04 e o mesmo artefato é validado em
Ubuntu 22.04 e Ubuntu 24.04. A compatibilidade com outras distribuições derivadas
deve ser confirmada durante os testes beta.

## Aviso

Esta ainda é uma versão beta. Mantenha backup independente dos documentos e
relate problemas pelo rastreador oficial do projeto.
