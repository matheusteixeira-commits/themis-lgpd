# Configuração

Há dois níveis de configuração:

* **do órgão** — perfis, listas, cargos, tipos e reconhecedores próprios —, num arquivo `themis.toml`
  aplicado igualmente pela CLI, pela API e pela interface;
* **do serviço** — limites, autenticação, processos —, por variáveis de ambiente com o prefixo
  `THEMIS_`, lidas em `src/themis_lgpd/config.py` quando a API ou a interface é iniciada.

Os valores padrão são os seguros para uso local. A biblioteca Python não lê variáveis de ambiente:
recebe a configuração pelos parâmetros do `Anonimizador` e de `anonimizar_arquivo` (ou por
`themis_lgpd.configuracao.carregar(caminho).argumentos()`).

## Configuração do órgão (`themis.toml`)

O arquivo é indicado com `--config` na CLI ou na variável `THEMIS_CONFIG` (CLI, API e interface). O
exemplo comentado [exemplos/orgao.toml](../exemplos/orgao.toml) mostra todas as seções:

| Seção | Conteúdo |
|---|---|
| `[padrao]` | `perfil`, `modo`, `preservar_agentes_publicos`, `usar_ner`, `ocr` usados quando a chamada não indica outros |
| `[listas]` | `permitir` e `bloquear` (listas de termos) e `permitir_arquivo`/`bloquear_arquivo` (arquivos de texto, um termo por linha, com caminho relativo ao `themis.toml`) |
| `[agentes_publicos]` | `cargos`: cargos do órgão somados aos que o Themis reconhece ("superintendente regional de ensino") |
| `[[tipos]]` | Tipos de dado próprios: `codigo`, `nome`, `categoria`, `etiqueta`, `prioridade` |
| `[[reconhecedores]]` | Regras próprias: `nome`, `tipo`, `regex` (com `grupo` nomeado para delimitar o dado), `score`, `contexto`, `contexto_obrigatorio`, `janela`, `validador` (`cpf`, `cnpj`, `pis`, `titulo_eleitor`, `cns`, `cnh`, `renavam`, `processo_cnj`, `luhn`, `ano_plausivel`), `score_invalido`, `ignorar_caixa` |
| `[perfis.<nome>]` | Perfis derivados de um perfil do Themis (`base`), com `regras` por categoria (`tarjar`, `alertar`, `manter`, `vinculado`), `score_minimo`, `score_alerta` e `tarjar_sensivel_sempre` |

Os reconhecedores próprios entram no registro do Presidio como os reconhecedores do Themis e seguem a
mesma política de decisão, propagação e verificação final. Um erro no arquivo — campo desconhecido,
expressão regular inválida ou que aceite texto vazio, tipo ou categoria inexistente, perfil sem base —
interrompe a execução com a indicação da seção e do campo: uma regra de proteção ignorada em silêncio
seria um vazamento. A API e a interface não iniciam com um arquivo inválido.

Na CLI, as opções informadas na linha de comando prevalecem sobre o `[padrao]`, e as listas de
permissão e de bloqueio são somadas às do arquivo. O manifesto de lote registra um resumo da
configuração efetiva: um lote retomado com outro `themis.toml` refaz os arquivos.

## Perfis

| Perfil | Finalidade |
|---|---|
| `lai` (padrão) | Publicação de respostas e documentos: tarja identificadores e dados sensíveis ligados a pessoas; cidades, CNPJ e termos genéricos viram alerta |
| `identificadores` | Somente o que identifica diretamente a pessoa; dados sensíveis viram alerta (bases de dados, pesquisa) |
| `saude` | Como `lai`, mas tarja qualquer menção a doenças, tratamentos e condições de saúde |
| `ouvidoria` | Manifestações de ouvidoria: preserva a identidade do manifestante (Lei nº 13.460/2017, art. 10, § 7º) tarjando também cidade, lotação, função e turno e demais quase-identificadores |
| `educacao` | Documentos escolares: RA, matrícula, dados de crianças e adolescentes (LGPD, art. 14; ECA, art. 17), turma, série e saúde de estudantes sempre tarjados |
| `maxima` | Tarja tudo o que for detectado, inclusive cidades, CNPJ e URLs |

A regra de cada perfil por categoria está em [TIPOS_DE_DADOS.md](TIPOS_DE_DADOS.md).

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
| `THEMIS_CONFIG` | vazio | vazio | Arquivo `themis.toml` da configuração do órgão |
| `THEMIS_PROCESSOS` | `1` | `1` | Processos de análise da API (`themis api --processos`); com mais de um, cada análise roda num processo de trabalho, com o próprio modelo (cerca de 1 GB por processo). A concorrência passa a ser o maior entre este valor e `THEMIS_CONCORRENCIA` |
| `THEMIS_MAX_TAREFAS` | `20` | `2` | Tarefas assíncronas (`/v1/tarefas`) mantidas em memória ao mesmo tempo, incluídas as concluídas ainda não baixadas; acima disso, 503 |
| `THEMIS_TAREFA_TTL_S` | `900` | `900` | Tempo, em segundos, em que o resultado de uma tarefa concluída aguarda o download antes de ser apagado da memória |
| `THEMIS_TAREFA_TIMEOUT_S` | `3600` | `300` | Tempo máximo de processamento de uma tarefa assíncrona, em segundos |
| `THEMIS_SOFFICE` | vazio | vazio | Executável do LibreOffice usado para converter `.doc`, `.xls`, `.ppt` e `.rtf` (também na CLI). Vazio: procura no `PATH` e nos locais de instalação padrão |

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

## Classificador de dados sensíveis

Além das regras, a detecção usa um classificador de trechos treinado (componente `spancat` do spaCy, em
`src/themis_lgpd/dados/modelos/sensivel`), acrescentado ao pipeline do `pt_core_news_lg` com o mesmo
vocabulário e os mesmos vetores. Ele foi treinado com pedidos de acesso à informação (EliMC/esic-ner), com
um corpus de documentos oficiais fictícios de produção própria (laudos, prontuários, relatórios sociais,
portarias, processos disciplinares) e com textos-modelo em inglês e texto de preenchimento, sem nada
anotado, para que não reaja a mestres de apresentações e cabeçalhos de planilhas. Cada rótulo tem limiar
próprio, definido pela ablação no sistema completo e registrado em `meta.json`:

| Rótulo | Achado | Tratamento no perfil LAI |
|---|---|---|
| `DADO_SAUDE` | `SAUDE` (camada semântica) | Regra de vínculo: tarjado em frase que se refere a uma pessoa, sinalizado nos demais casos |
| `DADO_SENSIVEL` | `ORIGEM_RACIAL`, `RELIGIAO`, `OPINIAO_POLITICA`, `FILIACAO_SINDICAL`, `VIDA_SEXUAL` ou `GENETICO_BIOMETRICO`, conforme o vocabulário do trecho; sem indicação da categoria, nenhum achado | Regra de vínculo |
| `NOME_PESSOA` | `NOME` (nomes em caixa alta, em tabelas, em assinaturas, iniciais) | Tarjado. Nomes de homenageados em instituições, logradouros, normas e honrarias e nomes de municípios são descartados |
| `QUASI_IDENTIFICADOR` | `QUASE_IDENTIFICADOR` | Desativado: sinalizava frases de expediente e funções descritas em abstrato; as regras cobrem os quase-identificadores |

Um rótulo sem limiar em `meta.json` não produz achados (`rotulos_desativados` registra o motivo). O campo
`limiares_contextuais` permite tarjar dados de saúde de alta probabilidade sem a regra de vínculo; fica
vazio por padrão, pois tarjava termos de saúde de interesse público em pedidos de acesso à informação.

| Variável | Padrão | Efeito |
|---|---|---|
| `THEMIS_MODELO_SENSIVEL` | definido no artefato (ligado) | `0` desliga e `1` liga o classificador na CLI, na API, na interface e na biblioteca. Lida quando o modelo de linguagem é carregado |

Sem o modelo de linguagem (`THEMIS_USAR_NER=false`) o classificador não é usado. O treino é reproduzido
por `benchmark/treino/treinar_spancat.py`; a ablação no sistema completo, a escolha da época e dos limiares
e a gravação da decisão no artefato, por `benchmark/treino/ablacao_spancat.py`.

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
