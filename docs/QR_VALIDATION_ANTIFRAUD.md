# Validação documental por QR — SmartFile

## 1. Visão geral e modelo de confiança

O QR é somente um localizador. Localização, integridade dos bytes, originalidade
no registro SmartFile e identidade/assinatura são resultados separados. Nenhum
booleano genérico transforma essas evidências em autenticidade ou validade jurídica.

## 2. Threat model

| Ameaça | Tratamento |
|---|---|
| T1 PDF alterado/reexportado | SHA-256 diverge, ainda que a aparência seja igual |
| T2 QR copiado para outro documento | Resolve o original associado ao token; comparar a cópia revela divergência |
| T3 QR removido | Registro continua; bytes alterados divergem |
| T4 QR falso | Registro não encontrado nesta instalação/fonte; não inferir fraude |
| T5 Token adivinhado | CSPRNG de 256 bits; nenhuma listagem pública |
| T6 Artefato substituído | Hash e tamanho conferidos antes de abrir/exportar |
| T7 Artefato excluído | ARTIFACT_MISSING, ações de original bloqueadas |
| T8 Banco adulterado | Triggers bloqueiam alterações pela aplicação; administrador que controla DB e FS está fora da garantia |
| T9 Acesso cross-org | Escopo e permissões no service e queries por organização |
| T10 Revogação ignorada | Estado administrativo exibido separadamente da integridade |
| T11 Reassinatura | Nova versão/registro; nenhum QR retroativo em PDF assinado |
| T12 Marca visual confundida com digital | VISUAL_HANDWRITTEN e NOT_APPLICABLE explícitos |

## 3. QR, token e código

Token `SFV1-` + `secrets.token_urlsafe(32)` (256 bits), sem IDs ou informação embutida.
Código humano separado de 16 caracteres aleatórios não ambíguos, prefixo SFV,
normalizável por espaços/hífens e case. Ambos têm unique constraint e retry de colisão.
Token é case-sensitive. O parser dedicado rejeita versões desconhecidas.

## 4. Artefato canônico

`CanonicalValidationArtifact` representa os bytes finais. `CanonicalArtifactService`
fica em área gerenciada própria por organização, fora do storage editável do GED.
Referências relativas são internas, não API nem conteúdo do QR. Sem update/delete
na API canônica, sem regenerar, reexportar ou reconstruir PDFs para validar.

## 5. SHA-256 e autorreferência

Hash em streaming de 1 MiB, lowercase hex, dos bytes preservados após assinatura.
QR só contém token: inserir hash final no próprio documento criaria autorreferência.
Hash não identifica pessoa e não autentica por aparência.

## 6. A1/PAdES

PENDING → token/QR → PDF preparado → pyHanko A1/PAdES → bytes finais → artifact →
SHA-256/tamanho → ACTIVE. Nada altera o PDF após assinatura. Verificação usa o serviço
criptográfico existente e apresenta VALID/INVALID/INDETERMINATE separadamente de
TRUSTED/UNTRUSTED/INDETERMINATE. A avaliação é do original registrado; uma cópia
HASH_MISMATCH não herda a assinatura do original. Sem novas raízes CA ou API Gov.br.

## 7. Manuscrita e documentos sem assinatura

Manuscrita é visual, tipo VISUAL_HANDWRITTEN, identidade criptográfica NOT_APPLICABLE.
QR não a transforma em assinatura digital. A arquitetura permite registro explícito
de PDF sem assinatura com NONE; esse registro confirma apenas referência/integridade.

## 8. QR copiado

A contém T1, B recebe visualmente T1. T1 continua resolvendo A. A tela chama a
referência de “Original registrado associado a este QR”. Fornecer B resulta em
HASH_MISMATCH. Nome, texto ou aparência de B não substituem comparação dos bytes.

## 9. QR removido

Editar/remover QR muda os bytes, sem apagar registro/artefato. Código ou token
manual ainda localiza o registro; arquivo modificado diverge.

## 10. QR falso ou ilegível

Registro inexistente: “Registro não encontrado nesta instalação/fonte de validação.”
Ausência local não prova fraude. Leitura automática de imagem usa OpenCV já instalado;
falha de leitura oferece código/token manual. Não há câmera de celular integrada.

## 11. Original registrado e versões

Cada finalização gera novo token e storage_ref. T1 continua ligado a A1 e T2 a A2.
Nome lógico/protocolo/tipo/data são snapshots mínimos; não dependem de documento GED
continuar existindo. Um registro pode ser encontrado por hash, token, URI/URL ou código.
Hash não é unique: o mesmo PDF pode ter registros legítimos distintos. Busca por hash
retorna o mais recente no escopo; token/código identifica precisamente uma versão.

## 12. Abrir e baixar

Abrir usa o PDF Viewer existente em contexto de original somente leitura. Caminho
canônico não é exibido. Baixar copia bytes e verifica SHA-256/tamanho exportados.
Nenhuma importação automática ao GED e nenhum renderer PDF no caminho de exportação.
Destino existente é recusado. Original ausente/corrompido não é disponibilizado.

## 13. Revogação

ACTIVE → REVOKED com data, usuário e motivo. PDF permanece igual. Integridade pode
ser MATCH e status REVOKED simultaneamente. Histórico ainda pode ser aberto/exportado
com autorização. Revogação não reescreve PDF nem altera assinatura criptográfica.

## 14. Retenção e backup

Schema 23: document_id, delivery_id e receipt_id opcionais usam SET NULL, nunca
cascade de validação. Exclusão permanente do GED remove apenas seu storage; registro,
artefato e auditoria própria permanecem. Triggers impedem delete do registro e update
de metadados canônicos finalizados. Backup administrativo inclui validation_artifacts
e delivery_receipts, além das áreas existentes. Não há purge automático de evidências.
Artefatos retidos consomem espaço adicional; a contabilidade de quota do GED não
foi ampliada para esse domínio histórico. Restauração completa precisa desses diretórios e do snapshot SQLite, mantendo layout
relativo; integração de interface de restauração não foi criada nesta tarefa.

## 15. Privacidade

Nenhum PDF, scan ou credencial é publicado. QR/DTO público mínimo não têm IDs internos,
paths, usuários, OAuth, segredos, hash final ou dados pessoais. Metadados mínimos ficam
no banco local; o próprio documento pode ser confidencial. Logs de auditoria usam ID
interno de registro, sem token completo/conteúdo. Tokens não são credenciais administrativas.

## 16. Organização e permissões

Services exigem organização ativa e validation.create/view/export/revoke/configure.
OWNER possui wildcard; ADMIN validation.*; EDITOR create/view/export; VIEWER view/export.
Comprovantes respeitam delivery.acknowledge já existente. Os fluxos gerais não são
limitados a BUSINESS; regras do módulo de entregas permanecem. Contexto None é uso
interno/testes sem sessão, não endpoint público e não deve ser exposto remotamente.

## 17. Modo local

Sem base URL: `smartfile:verify:v1:<token>`. Funciona na instalação que possui o
registro, dentro da organização autorizada, sem internet. Uma instalação diferente
pode não ter o registro. Não há sincronização automática do banco/artifact para terceiros.

## 18. Futuro modo web

Base opcional HTTPS por organização gera `{base}/verify/{token}`, com snapshot da
base usada. Alterar a base afeta somente novos QR, nunca reescreve artefatos antigos.
Modo de localização WEB não significa publicação: publication_mode fica LOCAL_ONLY,
publication_status NOT_PUBLISHED. Não há serviço público nesta versão. Não há localhost,
domínio fictício, compartilhamento automático OneDrive/Google ou exposição de NAS/LAN.

Um celular externo exigirá hosting HTTPS real, lookup mínimo por token, política
explícita de publicação/autorização, proteção/rate limiting (sobretudo human code),
TLS, auditoria de acesso e streaming autorizado. Endpoint futuro conceitual:
`GET /verify/<token>/document`, application/pdf, inline/attachment e eventual range.
A URI local não instala automaticamente um handler de sistema nem abre o desktop
através de câmera de celular. DeliveryHttpServer permanece restrito a entregas LAN.

## 19. Limitações

Não há garantia contra administrador comprometido que altera simultaneamente banco,
software e arquivos. Sem HMAC/CA improvisada. O original é imutável pela API do domínio,
não um storage WORM certificado. Igualdade byte a byte é estrita: reexportar um PDF
visualmente igual pode divergir. Divergência não determina intenção fraudulenta.
Não implementados: servidor/hosting/upload público, OCR, diff visual/semântico,
blockchain, identidade facial, login Gov.br ou reconhecimento de papel.

## 20. Escrita segura, falhas e segurança

Temporário exclusivo → cópia streaming → flush/fsync → hash/tamanho → promoção
atômica create-if-absent → fsync de diretório quando disponível → confirmação dos
bytes → transação ACTIVE. Windows usa hardlink NTFS e fallback rename sem overwrite;
directory fsync não disponível nesse sistema. Referência aceita somente org/token.pdf,
symlinks/componentes externos recusados. Temporário tem modo 0600 em Unix.

Falhas deixam FAILED ou PENDING recuperável, nunca aprovação positiva. Crash após
promoção e antes do DB pode deixar artefato órfão, retido; não é ativado por inferência.
`recover_pending` autorizado converte PENDING com pelo menos 24 h em FAILED, sem
remover arquivos. Auditoria registra criação, ativação, verificação, divergência,
exportação, abertura, corrupção e revogação sem conteúdo. Workers e geração impedem
respostas antigas de substituir resultados depois de mudança de arquivo/org/fechamento.

Consulte [auditoria prévia e fechamento](qr-validation/AUDIT.md) e
[notas beta.7](RELEASE_NOTES_0.9.0-beta.7.md).
