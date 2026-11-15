# 0006. Verificação final do arquivo e falha fechada

- Estado: Aceito
- Data: 2026-11-15

## Contexto

A anonimização de arquivos envolve muitas etapas — extração, análise, gravação nas posições de
origem, reconstrução, saneamento — e cada formato tem lugares onde o texto pode sobreviver: camadas de
texto, metadados, atributos XML, caches de gráficos, partes órfãs do pacote. Um erro em qualquer etapa
produziria um arquivo que parece anonimizado, mas não está. Para o usuário, esse é o pior resultado
possível, pois o arquivo seria publicado com confiança.

Na detecção, a mesma assimetria vale: expor um identificador é irreversível, enquanto uma tarja a mais
é corrigível na revisão.

## Decisão

**Verificação independente.** Depois de gerar o arquivo, cada formato extrai todo o conteúdo textual
do resultado por um caminho diferente do usado na anonimização (`formatos/verificacao.py`):

| Formato | Conteúdo verificado |
|---|---|
| PDF | Texto extraído por pdfplumber e por PDFium; cadeias de caracteres de todos os objetos; fluxos de metadados e anexos |
| DOCX, XLSX | Texto e valores de atributos de todas as partes XML, VML e de relacionamento |
| CSV, TXT | Texto gerado |
| Imagem | Novo OCR da imagem gerada |

A comparação ignora caixa e acentos, tolera separadores entre caracteres, exige limite de palavra,
procura números longos apenas pelos dígitos e desconsidera trechos mantidos intencionalmente
([SEGURANCA_E_PRIVACIDADE.md](../SEGURANCA_E_PRIVACIDADE.md#verificação-final)).

**Falha fechada.** Se qualquer valor tarjado continuar legível, a operação levanta
`VazamentoDetectado` e nenhum arquivo é entregue. O mesmo princípio se aplica a:

- identificadores com confiança moderada, que são tarjados em vez de sinalizados;
- números com formato de documento e palavra-chave, tarjados mesmo com dígito verificador inválido;
- arquivos que exigem OCR quando o OCR está indisponível ou falha (`FalhaOCR`), em vez de tratar as
  páginas como vazias;
- fluxos de metadados que não podem ser lidos na verificação;
- documentos com estrutura que não pode ser processada com segurança (DTD, entradas duplicadas,
  formato OOXML Strict), recusados com `ArquivoInvalido`.

## Consequências

- Um defeito em qualquer etapa resulta em erro, não em vazamento silencioso.
- A verificação acrescenta tempo de processamento, sobretudo em PDFs (segunda extração) e imagens
  (segundo OCR).
- Valores com menos de cinco letras e dígitos não são verificados, para evitar falsos positivos com
  palavras comuns; continuam sendo tarjados.
- Falsos positivos da verificação impedem a entrega do arquivo; as regras de limite de palavra e de
  trechos protegidos existem para reduzi-los, e são as mesmas da propagação
  ([ADR 0007](0007-propagacao-no-documento.md)).

## Alternativas consideradas

- **Confiar na construção do arquivo.** Não detecta defeitos nem conteúdo em lugares não previstos.
- **Verificação apenas com o mesmo extrator usado na anonimização.** Repetiria as mesmas falhas de
  extração.
- **Remover automaticamente o valor encontrado na verificação e entregar o arquivo.** A presença do
  valor indica defeito em uma etapa anterior; corrigi-lo silenciosamente esconderia o defeito.
