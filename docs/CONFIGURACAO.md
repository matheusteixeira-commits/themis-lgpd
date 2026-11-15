# Configuração

A API e a interface web são configuradas por variáveis de ambiente com o prefixo `THEMIS_`, lidas em
`src/themis_lgpd/config.py` quando o processo é iniciado. Os valores padrão são os seguros para uso
local. A biblioteca Python não lê variáveis de ambiente: recebe a configuração pelos parâmetros do
`Anonimizador` e de `anonimizar_arquivo`.

## Variáveis da API e da interface

| Variável | Padrão | Padrão com `THEMIS_DEMO=true` | Efeito |
|---|---|---|---|
| `THEMIS_DEMO` | `false` | — | Modo de demonstração pública: reduz os limites, exibe a faixa "não envie documentos reais", desativa o modo `hmac`, o relatório com valores e a documentação interativa da API |
| `THEMIS_MAX_CARACTERES` | `500000` | `20000` | Tamanho máximo do texto por requisição (API e campo de texto da interface) |
| `THEMIS_MAX_MB` | `50` | `5` | Tamanho máximo de arquivo e de corpo de requisição, em MB; também define o limite de envio do Streamlit |
| `THEMIS_MAX_PAGINAS` | `500` | `10` | Número máximo de páginas de PDF |
| `THEMIS_LIMITE_REQ_MINUTO` | `120` | `10` | Requisições `POST` por minuto por endereço IP na API |
| `THEMIS_CONCORRENCIA` | `2` | `2` | Processamentos simultâneos na API; os excedentes aguardam até 15 segundos e recebem 503 |
| `THEMIS_TIMEOUT_S` | `300` | `60` | Tempo máximo de processamento por requisição na API, em segundos |
| `THEMIS_CHAVES_API` | vazio | vazio | Chaves aceitas no cabeçalho `X-API-Key`, separadas por vírgula. Vazio: API sem autenticação |
| `THEMIS_CORS_ORIGENS` | vazio | vazio | Origens autorizadas a chamar a API pelo navegador, separadas por vírgula. Vazio: CORS desativado |
| `THEMIS_DOCS` | `true` | `false` | Publica a documentação interativa (`/docs` e `/openapi.json`) |
| `THEMIS_CONFIAR_PROXY` | `false` | `false` | Usa o primeiro endereço de `X-Forwarded-For` como IP do cliente. Habilite somente atrás de proxy reverso confiável |
| `THEMIS_USAR_NER` | `true` | `true` | Usa o modelo de linguagem no reconhecimento de nomes |
| `THEMIS_MODELO_SPACY` | `pt_core_news_lg` | `pt_core_news_lg` | Pacote do modelo spaCy |

Valores booleanos aceitam `1`, `true`, `sim`, `yes` e `on` (sem distinção de caixa) como verdadeiro;
qualquer outro valor é falso. Valores numéricos inválidos são substituídos pelo padrão.

Os limites efetivamente aplicados por cada interface:

| Limite | API | Interface |
|---|---|---|
| `THEMIS_MAX_CARACTERES` | Validação do campo `texto` | Campo de texto |
| `THEMIS_MAX_MB` | Corpo e arquivo (413) | Envio de arquivo |
| `THEMIS_MAX_PAGINAS` | Arquivos PDF | Arquivos PDF |
| `THEMIS_LIMITE_REQ_MINUTO`, `THEMIS_CONCORRENCIA`, `THEMIS_TIMEOUT_S` | Sim | Não¹ |

¹ Na interface, o limite de uso é de 40 análises por sessão por hora no modo de demonstração e 10.000
fora dele. O limite por IP da demonstração pública é aplicado pelo proxy ([DEPLOY.md](DEPLOY.md)).

## Variáveis da linha de comando

| Variável | Uso |
|---|---|
| `THEMIS_CHAVE_HMAC` | Chave do modo `hmac` em `themis anonimizar --modo hmac` e `themis analisar --modo hmac`. Sem ela, uma chave aleatória é gerada a cada execução e os códigos não se repetem entre execuções |
| `THEMIS_SENHA_COFRE` | Senha do cofre em `themis anonimizar --cofre` e `themis reverter`. Sem ela, a senha é solicitada no terminal |

Não grave a chave HMAC nem a senha do cofre em arquivos versionados ou em histórico do shell.

## Configuração da interface (Streamlit)

O comando `themis interface` inicia o Streamlit com as opções abaixo, que não dependem de arquivo de
configuração:

| Opção | Valor | Motivo |
|---|---|---|
| `browser.gatherUsageStats` | `false` | Sem telemetria |
| `server.enableXsrfProtection` | `true` | Proteção contra falsificação de requisições |
| `server.enableCORS` | `true` | Política de origem do Streamlit ativa |
| `client.showErrorDetails` | `none` | Erros nunca exibem trechos de documentos |
| `client.toolbarMode` | `minimal` | Menu reduzido |
| `server.fileWatcherType` | `none` | Sem observação de arquivos |
| `server.maxUploadSize` | `THEMIS_MAX_MB` | Limite de envio |

O arquivo `.streamlit/config.toml` do repositório aplica as mesmas opções quando a interface é iniciada
com `streamlit run` a partir da raiz do repositório.

## Configuração da demonstração pública

O arquivo `deploy/.env.exemplo` contém as variáveis da composição Docker:

| Variável | Descrição |
|---|---|
| `DOMINIO` | Domínio público, usado pelo Caddy para emitir o certificado TLS |
| `EMAIL_ACME` | E-mail de contato para a autoridade certificadora (Let's Encrypt) |
| `THEMIS_DEMO`, `THEMIS_MAX_MB`, `THEMIS_MAX_PAGINAS`, `THEMIS_MAX_CARACTERES` | Repassadas ao contêiner da aplicação |

Ver [DEPLOY.md](DEPLOY.md).

## Exemplos

Uso local com autenticação:

```bash
export THEMIS_CHAVES_API="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
themis api
```

API atrás de proxy, aceitando chamadas de um portal:

```bash
export THEMIS_CHAVES_API="..."
export THEMIS_CONFIAR_PROXY=true
export THEMIS_CORS_ORIGENS="https://portal.exemplo.gov.br"
export THEMIS_DOCS=false
themis api --endereco 0.0.0.0
```

Contêiner com limites próprios:

```bash
docker run --rm -p 127.0.0.1:8501:8501 \
  -e THEMIS_MAX_MB=20 -e THEMIS_MAX_PAGINAS=100 \
  --read-only --tmpfs /tmp themis-lgpd
```
