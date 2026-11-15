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
export THEMIS_CHAVES_API="chave-longa-e-aleatoria-1,chave-longa-e-aleatoria-2"
curl -H "X-API-Key: chave-longa-e-aleatoria-1" ...
```

## Rotas

| Método | Rota | Autenticação | Descrição |
|---|---|---|---|
| `GET` | `/saude` | não | Estado do serviço, versão, disponibilidade de OCR e modo de demonstração |
| `GET` | `/v1/perfis` | não | Perfis e modos de saída disponíveis |
| `GET` | `/v1/tipos` | não | Tipos de dado, categorias, etiquetas e base legal |
| `POST` | `/v1/anonimizar` | sim¹ | Anonimiza um texto |
| `POST` | `/v1/analisar` | sim¹ | Lista o que seria tarjado, sem alterar o texto |
| `POST` | `/v1/arquivos/anonimizar` | sim¹ | Anonimiza um arquivo e devolve o arquivo gerado |

¹ Somente quando `THEMIS_CHAVES_API` está definida.

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
| `perfil` | string | `lai` | `lai`, `identificadores`, `saude` ou `maxima` |
| `modo` | string | `etiqueta` | `etiqueta`, `tarja`, `mascara`, `pseudonimo` ou `hmac` (indisponível na demonstração) |
| `permitir` | lista de strings | `[]` | Termos que nunca são tarjados (até 200 termos de até 200 caracteres) |
| `bloquear` | lista de strings | `[]` | Termos sempre tarjados (mesmos limites) |
| `preservar_agentes_publicos` | booleano | `false` | Mantém nomes acompanhados de cargo público |
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
| `arquivo` | arquivo | obrigatório | PDF, DOCX, XLSX, CSV, TXT, PNG ou JPEG, até `THEMIS_MAX_MB` |
| `perfil` | texto | `lai` | Perfil |
| `modo` | texto | `etiqueta` | Modo de saída |

```bash
curl -s http://127.0.0.1:8000/v1/arquivos/anonimizar \
  -F "arquivo=@despacho.pdf" -F "perfil=lai" \
  -o despacho_anonimizado.pdf -D cabecalhos.txt
```

A resposta é o arquivo gerado, com os cabeçalhos:

| Cabeçalho | Conteúdo |
|---|---|
| `Content-Type` | Tipo MIME do arquivo gerado (imagens são devolvidas em PNG) |
| `Content-Disposition` | `attachment; filename*=UTF-8''<nome>_anonimizado.<ext>` |
| `X-Themis-Tarjados` | Quantidade de trechos tarjados |
| `X-Themis-Para-Revisar` | Quantidade de alertas para revisão |
| `X-Themis-Avisos` | Avisos ao usuário, separados por ` \| ` e codificados para URL (até 4.000 caracteres) |

Os avisos informam conteúdo removido, convertido ou não analisado (anexos, comentários, imagens não
analisadas, páginas rasterizadas) e nunca repetem conteúdo do documento. O arquivo gerado passa pela
verificação final descrita em [SEGURANCA_E_PRIVACIDADE.md](SEGURANCA_E_PRIVACIDADE.md#verificação-final).

Pela API de arquivos não é possível informar listas de permissão e bloqueio nem colunas a tarjar por
inteiro; para esses casos, use a CLI ou a biblioteca.

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
