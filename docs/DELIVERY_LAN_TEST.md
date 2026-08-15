# SmartFile — Teste real de entrega LAN (Linux Mint ↔ Zorin OS)

## Objetivo e cuidado

Este roteiro valida a Fase 7 em duas máquinas reais da mesma rede local. A beta
usa HTTP; faça o teste somente em rede confiável e não encaminhe a porta do
roteador para a Internet.

## 1. Preparar as instalações

1. Instale a mesma versão do SmartFile nas duas máquinas.
2. Crie a organização Empresarial com o mesmo nome e os mesmos nomes de usuário
   em ambas. Ative **Solicitação de documentos**.
3. Em cada máquina, abra **Solicitações e Entregas > Configurar LAN**.
4. Defina nomes diferentes, por exemplo `Mint-Financeiro` e `Zorin-Compras`.
5. Use portas livres, por exemplo `8765` e `8766`.

Descubra o IP atual:

```bash
hostname -I
```

Confirme se a porta está em escuta depois de iniciar o SmartFile:

```bash
ss -ltn | grep 8765
```

Do outro computador, teste a conectividade:

```bash
nc -vz 192.168.0.31 8765
```

Se houver firewall UFW, libere somente a rede local adequada ao laboratório:

```bash
sudo ufw allow from 192.168.0.0/24 to any port 8765 proto tcp
```

Adapte a sub-rede e a porta ao ambiente. Remova a regra quando o laboratório
terminar, se ela não for mais necessária.

## 2. Cadastrar os peers

Em cada instalação, cadastre manualmente o UUID SmartFile, nome, IP, porta e
usuário proprietário da outra máquina. O UUID identifica; o IP apenas localiza.
Depois de DHCP ou troca de rede, atualize somente o IP/porta.

## 3. Fluxo de solicitação

1. No Mint, crie “Preciso da nota fiscal de julho” para o responsável do Zorin.
2. No Zorin, confirme a entrada da solicitação.
3. Inicie o atendimento.
4. Importe ou digitalize o documento pelo fluxo oficial do GED.
5. Vincule o documento e marque **Atendida**.
6. Use **Preparar entrega da solicitação** e envie.
7. No Mint, confira a notificação e o protocolo.
8. Visualize o documento; no Zorin, atualize e confirme `VIEWED`.
9. No Mint, use **Confirmar recebimento**.
10. No Zorin, atualize e confira `ACKNOWLEDGED` e solicitação `COMPLETED`.

## 4. Fluxo direto e ações do destinatário

No Zorin, abra a cesta sem solicitação, selecione dois documentos e envie ao
Mint. No destinatário, teste separadamente:

- **Visualizar**: abre o conteúdo recebido e registra visto;
- **Download**: cria uma cópia no diretório escolhido;
- **Adicionar ao SmartFile**: importa pelo `DocumentService` e managed storage;
- **Confirmar recebimento**: registra a confirmação no protocolo.

## 5. Destinatário offline

1. Feche o SmartFile do Zorin.
2. Envie um documento a partir do Mint.
3. Confirme que o protocolo ficou `QUEUED` e o documento original continua
   disponível.
4. Feche e reabra o SmartFile do Mint para confirmar persistência da fila.
5. Inicie novamente o Zorin.
6. Aguarde o retry ou use **Tentar novamente**.
7. Confirme `DELIVERED` somente depois da verificação SHA-256.

## 6. Diagnóstico

| Sintoma | Verificação |
|---|---|
| Conexão recusada | SmartFile remoto aberto, IP, porta e `ss -ltn` |
| Timeout | firewall, isolamento Wi-Fi/AP ou rota entre as máquinas |
| Peer inválido | UUID remoto cadastrado e organização ativa |
| Usuário não encontrado | mesmo nome de login e membro ativo nas duas instalações |
| Checksum inválido | estabilidade da rede e espaço em disco; retry após corrigir |
| Porta ocupada | escolher outra porta e reiniciar a recepção LAN |

Nunca inclua banco, credenciais, documentos reais ou dados pessoais ao relatar
um problema. Informe versão, sistema, etapas, protocolo mascarado e mensagens.
