# API HTTP

A API HTTP expõe a anonimização de textos e arquivos para integração com outros sistemas
(sistemas de ouvidoria, e-SIC, fluxos de publicação). É implementada com FastAPI em
`src/themis_lgpd/api/app.py` e não armazena nenhum conteúdo.

## Execução

```bash
pip install "themis-lgpd[api,arquivos]"
python -m spacy download pt_core_news_lg
themis api                                   # http://127.0.0.1:8000
themis api --endereco 0.0.0.0 --porta 8000   # somente atrás de proxy com HTTPS
```

Com Docker:

```bash
docker run --rm -p 127.0.0.1:8000:8000 themis-lgpd api --endereco 0.0.0.0 --porta 8000
```

A documentação interativa (OpenAPI) fica em `/docs` e o esquema em `/openapi.json`, exceto quando
`THEMIS_DOCS=false` ou `THEMIS_DEMO=true`. A configuração é feita por variáveis de ambiente
([CONFIGURACAO.md](CONFIGURACAO.md)).

## Autenticação

Quando `THEMIS_CHAVES_API` está definida (chaves separadas por vírgula), as rotas `POST` exigem o
cabeçalho `X-API-Key` com uma das chaves; a comparação é feita em tempo constante. Sem a variável, a
API não exige chave — configuração adequada apenas para uso local.

```bash
# No servidor: chaves longas e aleatórias, separadas por vírgula.
export THEMIS_CHAVES_API="$(openssl rand -hex 32),$(openssl rand -hex 32)"

# No cliente: a chave fica em variável de ambiente, nunca no comando nem no histórico do shell.
curl -H "X-API-Key: ${THEMIS_CHAVE}" ...
```

## Rotas

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| `GET` | `/saude` | não | Estado do serviço, versão, OCR, processos, modo de demonstração e uso de configuração do órgão |
| `GET` | `/v1/perfis` | não | Perfis (do Themis e do órgão), perfil padrão e modos de saída |
| `GET` | `/v1/tipos` | não | Tipos de dado (inclusive os do órgão), categorias, etiquetas e base legal |
| `POST` | `/v1/anonimizar` | sim¹ | Anonimiza um texto |
| `POST` | `/v1/analisar` | sim¹ | Lista o que seria tarjado, sem alterar o texto |
| `POST` | `/v1/arquivos/anonimizar` | sim¹ | Anonimiza um arquivo e devolve o arquivo gerado (ou, em JSON, o arquivo e o relatório) |
| `POST` | `/v1/tarefas` | sim¹ | Agenda a anonimização de um arquivo e responde de imediato (202) |
| `GET` | `/v1/tarefas/{id}` | sim² | Situação da tarefa |
| `GET` | `/v1/tarefas/{id}/resultado` | sim² | Baixa o resultado e o apaga da memória |
| `DELETE` | `/v1/tarefas/{id}` | sim² | Apaga a tarefa e o resultado |

¹ Somente quando `THEMIS_CHAVES_API` está definida.
² Com a mesma chave que criou a tarefa; para outra chave, a tarefa não existe (404).

A especificação OpenAPI de cada versão está versionada em [openapi.json](openapi.json) (gerada por
`scripts/gerar_openapi.py`; um teste falha se a API mudar sem que o arquivo seja atualizado), o que
permite gerar clientes para sistemas como o SEI ou portais de transparência.

### `GET /saude`

```json
{"status": "ok", "versao": "1.0.0", "ocr": true, "demo": false}
```

### `GET /v1/perfis`

```json
{
  "perfis": [{"nome": "lai", "titulo": "Transparência (LAI)", "descricao": "..."}, "..."],
  "modos": {"etiqueta": "Etiqueta do tipo de dado — ex.: [CPF], [NOME]. Padrão.", "...": "..."}
}
```

### `GET /v1/tipos`

```json
[
  {"tipo": "NOME", "nome": "Nome de pessoa", "categoria": "PESSOA", "etiqueta": "[NOME]",
   "base_legal": "LGPD, art. 5º, I; LAI, art. 31, § 1º, I"},
  {"tipo": "CPF", "nome": "CPF", "categoria": "DOCUMENTO", "etiqueta": "[CPF]",
   "base_legal": "LGPD, art. 5º, I; LAI, art. 31, § 1º, I"}
]
```

### `POST /v1/anonimizar`

Corpo (JSON):

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `texto` | string | obrigatório | Texto a anonimizar; de 1 a `THEMIS_MAX_CARACTERES` caracteres |
| `perfil` | string | do órgão (`lai`) | `lai`, `identificadores`, `saude`, `ouvidoria`, `educacao`, `maxima` ou um perfil do `themis.toml` |
| `modo` | string | do órgão (`etiqueta`) | `etiqueta`, `tarja`, `mascara`, `pseudonimo` ou `hmac` (indisponível na demonstração) |
| `permitir` | lista de strings | `[]` | Termos que nunca são tarjados (até 200 termos de até 200 caracteres), somados aos do `themis.toml` |
| `bloquear` | lista de strings | `[]` | Termos sempre tarjados (mesmos limites), somados aos do `themis.toml` |
| `preservar_agentes_publicos` | booleano | do órgão (`false`) | Mantém nomes acompanhados de cargo público |
| `incluir_valores` | booleano | `false` | Inclui o valor original de cada entidade na resposta |

No modo `hmac`, a API usa uma chave aleatória por requisição: os códigos não se repetem entre
requisições. Para códigos estáveis, use a biblioteca ou a CLI com chave definida.

Exemplo:

```bash
curl -s http://127.0.0.1:8000/v1/anonimizar \
  -H "Content-Type: application/json" \
  -d '{"texto": "Eu, Ana Lima, CPF 529.982.247-25, moro em Taguatinga.", "perfil": "lai"}'
```

Resposta (resumida):

```json
{
  "texto_anonimizado": "Eu, [NOME], CPF [CPF], moro em [ENDEREÇO].",
  "perfil": "lai",
  "modo": "etiqueta",
  "estatisticas": {
    "tarjadas": 3, "alertas": 0,
    "por_tipo": {"NOME": 1, "CPF": 1, "ENDERECO": 1},
    "por_categoria": {"PESSOA": 1, "DOCUMENTO": 1, "LOCALIZACAO": 1},
    "caracteres_original": 53, "caracteres_saida": 42
  },
  "entidades": [
    {
      "inicio": 4, "fim": 12, "tipo": "NOME", "rotulo": "Nome de pessoa", "categoria": "PESSOA",
      "acao": "tarjar", "score": 0.85, "camada": "contextual", "validado_por_digito": null,
      "origem": "nomes:gatilho", "base_legal": "LGPD, art. 5º, I; LAI, art. 31, § 1º, I",
      "motivo": "", "inicio_saida": 4, "fim_saida": 10
    }
  ],
  "avisos": [],
  "nota_de_tarjamento": "NOTA DE TARJAMENTO — o texto\n\nForam tarjados 3 trecho(s)..."
}
```

Campos de cada entidade:

| Campo | Descrição |
|---|---|
| `inicio`, `fim` | Posição no texto original (fim exclusivo) |
| `inicio_saida`, `fim_saida` | Posição do substituto no texto anonimizado (somente entidades tarjadas) |
| `tipo`, `rotulo`, `categoria` | Tipo de dado, nome legível e categoria ([TIPOS_DE_DADOS.md](TIPOS_DE_DADOS.md)) |
| `acao` | `tarjar` ou `alertar` (mantido no texto e sinalizado para revisão) |
| `score` | Confiança, entre 0 e 1 |
| `camada` | `estrutural`, `contextual`, `semantica` ou `ner` |
| `validado_por_digito` | `true`/`false` quando o dígito verificador foi conferido; `null` quando não se aplica |
| `origem` | Reconhecedor e, quando houver, a palavra de contexto que reforçou a confiança |
| `base_legal`, `motivo` | Fundamento legal da categoria e justificativa específica da decisão |
| `valor` | Trecho original; somente com `incluir_valores=true` |

O texto original nunca é devolvido.

### `POST /v1/analisar`

Mesmo corpo de `/v1/anonimizar`. Devolve as entidades sem aplicar substituições:

```json
{"entidades": [{"inicio": 0, "fim": 8, "tipo": "NOME", "acao": "tarjar", "...": "..."}]}
```

### `POST /v1/arquivos/anonimizar`

Requisição `multipart/form-data`:

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `arquivo` | arquivo | obrigatório | Qualquer formato suportado (PDF, DOCX, XLSX, PPTX, ODT, ODS, CSV, TXT, HTML, EML, PNG, JPEG, TIFF, ZIP; DOC, XLS, PPT e RTF com o LibreOffice no servidor), até `THEMIS_MAX_MB` |
| `perfil` | texto | do órgão (`lai`) | Perfil |
| `modo` | texto | do órgão (`etiqueta`) | Modo de saída |
| `permitir`, `bloquear` | texto (repetível) | — | Termos nunca ou sempre tarjados, somados aos do `themis.toml` |
| `preservar_agentes_publicos` | booleano | do órgão | Mantém nomes acompanhados de cargo público |
| `coluna_integral` | texto (repetível) | — | Em planilhas, coluna (pelo cabeçalho) tarjada por inteiro |
| `ocr` | booleano | `true` | Permite OCR em páginas digitalizadas e imagens |
| `pdfa` | booleano | `false` | Em PDFs, gera PDF/A-2b para arquivamento |
| `resposta` | texto | `arquivo` | `arquivo` devolve o arquivo gerado; `json` devolve o arquivo em base64 com o relatório de tarjamento (resumo, itens sem valores originais) e a nota de tarjamento |

```bash
curl -s http://127.0.0.1:8000/v1/arquivos/anonimizar \
  -F "arquivo=@despacho.pdf" -F "perfil=lai" -F "permitir=Hospital Regional de Taguatinga" \
  -o despacho_anonimizado.pdf -D cabecalhos.txt
```

A resposta é o arquivo gerado, com os cabeçalhos:

| Cabeçalho | Conteúdo |
|---|---|
| `Content-Type` | Tipo MIME do arquivo gerado (PNG e JPEG são devolvidos em PNG; formatos antigos do Office, no formato aberto) |
| `Content-Disposition` | `attachment; filename*=UTF-8''<nome>_anonimizado.<ext>` |
| `X-Themis-Tarjados` | Quantidade de trechos tarjados |
| `X-Themis-Para-Revisar` | Quantidade de alertas para revisão |
| `X-Themis-Avisos` | Avisos ao usuário, separados por ` \| ` e codificados para URL (até 4.000 caracteres) |

Os avisos informam conteúdo removido, convertido ou não analisado (anexos, comentários, imagens não
analisadas, páginas rasterizadas) e nunca repetem conteúdo do documento. O arquivo gerado passa pela
verificação final descrita em [SEGURANCA_E_PRIVACIDADE.md](SEGURANCA_E_PRIVACIDADE.md#verificação-final).

### Tarefas assíncronas: `POST /v1/tarefas`

Documentos longos — um PDF digitalizado de dezenas de páginas, que exige OCR — podem exceder o tempo
de uma requisição (`THEMIS_TIMEOUT_S`). A rota `/v1/tarefas` recebe os mesmos campos de
`/v1/arquivos/anonimizar`, responde imediatamente com HTTP 202 e processa o arquivo em segundo plano,
com o limite `THEMIS_TAREFA_TIMEOUT_S`:

```bash
curl -s http://127.0.0.1:8000/v1/tarefas -H "X-API-Key: ${THEMIS_CHAVE}" -F "arquivo=@processo.pdf"
# {"id": "k3J…", "situacao": "na_fila", "consulta": "/v1/tarefas/k3J…",
#  "resultado": "/v1/tarefas/k3J…/resultado", "expira_apos_conclusao_s": 900}

curl -s http://127.0.0.1:8000/v1/tarefas/k3J… -H "X-API-Key: ${THEMIS_CHAVE}"
# {"id": "k3J…", "situacao": "concluida", "nome": "processo_anonimizado.pdf", "tarjados": 41, …}

curl -s http://127.0.0.1:8000/v1/tarefas/k3J…/resultado -H "X-API-Key: ${THEMIS_CHAVE}" -o processo_anonimizado.pdf
```

A situação é `na_fila`, `processando`, `concluida` ou `falhou` (com `mensagem`, que nunca repete
conteúdo do documento). O identificador é aleatório (192 bits) e a tarefa só é visível para a chave de
API que a criou. Nada é gravado em disco: o arquivo enviado e o resultado ficam em memória, e o
resultado é apagado após o download, após `DELETE /v1/tarefas/{id}` ou `THEMIS_TAREFA_TTL_S` segundos
depois da conclusão. No máximo `THEMIS_MAX_TAREFAS` tarefas são mantidas; além disso, a rota responde
503 com `Retry-After`.

## Erros

Todas as respostas de erro têm o formato `{"erro": "<mensagem>"}`; erros de validação acrescentam a
lista `detalhes`.

| Código | Situação | Corpo |
|---|---|---|
| 401 | Chave de API ausente ou inválida | `{"erro": "Chave de API ausente ou inválida."}` |
| 413 | Corpo maior que `THEMIS_MAX_MB` (verificado pelo cabeçalho `Content-Length`) | `{"erro": "Requisição maior que N MB."}` |
| 413 | Arquivo maior que `THEMIS_MAX_MB` | `{"erro": "Arquivo maior que N MB."}` |
| 422 | Parâmetros inválidos (perfil ou modo inexistente, texto vazio ou longo demais), em qualquer rota | `{"erro": "Requisição inválida.", "detalhes": [{"campo": "body.perfil", "erro": "..."}]}` |
| 422 | Arquivo inválido, corrompido, protegido por senha, de formato não suportado ou acima dos limites | `{"erro": "<mensagem>"}` |
| 429 | Limite de requisições por IP por minuto excedido; cabeçalho `Retry-After: 60` | `{"erro": "Muitas requisições. Tente novamente em instantes."}` |
| 500 | A verificação final encontrou valor tarjado no arquivo gerado; nenhum arquivo é devolvido | `{"erro": "N trecho(s) tarjado(s) ainda ..."}` |
| 500 | Erro interno | `{"erro": "Erro interno ao processar."}` |
| 503 | Concorrência máxima atingida por mais de 15 segundos, ou processamento acima de `THEMIS_TIMEOUT_S` | `{"erro": "Servidor ocupado. Tente novamente."}` ou `{"erro": "Tempo de processamento excedido."}` |
| 503 | O arquivo exige OCR (PDF digitalizado, imagem ou texto em contornos) e nenhum mecanismo está instalado, ou o OCR falhou | `{"erro": "<mensagem>"}` |

Após o tempo limite, o cliente recebe 503, mas a vaga de concorrência só é liberada quando a análise
termina de fato: o número de análises em execução nunca excede `THEMIS_CONCORRENCIA`.

Erros de validação nunca devolvem o valor recebido, e nenhuma mensagem contém trechos do texto ou do
arquivo enviado.

## Limites

| Limite | Padrão | Demonstração (`THEMIS_DEMO=true`) | Variável |
|---|---|---|---|
| Tamanho de texto | 500.000 caracteres | 20.000 | `THEMIS_MAX_CARACTERES` |
| Tamanho de arquivo e de corpo | 50 MB | 5 MB | `THEMIS_MAX_MB` |
| Páginas de PDF | 500 | 10 | `THEMIS_MAX_PAGINAS` |
| Requisições `POST` por IP por minuto | 120 | 10 | `THEMIS_LIMITE_REQ_MINUTO` |
| Processamentos simultâneos | 2 | 2 | `THEMIS_CONCORRENCIA` |
| Tempo máximo por requisição | 300 s | 60 s | `THEMIS_TIMEOUT_S` |

O controle de taxa é mantido em memória, por processo. Atrás de um proxy reverso, defina
`THEMIS_CONFIAR_PROXY=true` para que o IP seja lido de `X-Forwarded-For`; não habilite a opção sem
proxy, pois o cabeçalho pode ser forjado pelo cliente.

## Garantias de privacidade

- Nenhum texto ou arquivo é gravado em disco ou em log; o processamento ocorre em memória.
- Respostas com `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` e `Content-Security-Policy` restritiva
  (exceto em `/docs`).
- CORS desativado por padrão; com `THEMIS_CORS_ORIGENS`, somente as origens listadas, sem credenciais,
  com os métodos `GET` e `POST` e os cabeçalhos `Content-Type` e `X-API-Key`.
- Exceções inesperadas são registradas apenas pelo tipo, sem mensagem; o cliente recebe mensagem
  genérica. Os registros de exceção do Uvicorn passam pelo mesmo filtro e também são reduzidos ao
  tipo do erro, sem rastreamento.
- `themis api` inicia o Uvicorn sem log de acesso e sem o cabeçalho `Server`.

## Implantação

Para expor a API publicamente, use um proxy reverso com HTTPS, defina `THEMIS_CHAVES_API` e
`THEMIS_CONFIAR_PROXY=true`, e restrinja `THEMIS_CORS_ORIGENS` às origens necessárias. Ver
[DEPLOY.md](DEPLOY.md#api).
