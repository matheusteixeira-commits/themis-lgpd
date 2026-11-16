# Como contribuir

Contribuições são bem-vindas: correções de vazamentos e de tarjas indevidas, novos reconhecedores,
suporte a formatos, documentação e benchmarks. Este documento descreve o ambiente de desenvolvimento,
os critérios de aceitação e a política de dados de teste.

## Dados de teste: somente fictícios

Issues, testes, exemplos, benchmarks e mensagens de commit usam **somente dados fictícios**. Nunca
inclua documentos reais, nomes de pessoas reais ou números de documentos reais.

- Gere documentos com dígito verificador válido com `themis_lgpd.validadores`: `gerar_cpf`,
  `gerar_cnpj` (inclusive `alfanumerico=True`), `gerar_pis`, `gerar_titulo`, `gerar_cns`, `gerar_cnh`,
  `gerar_renavam`, `gerar_processo_cnj` e `gerar_cartao`.
- Para nomes, use o Faker (`Faker("pt_BR")`) ou combinações evidentemente fictícias.
- Ao relatar um dado que não foi tarjado em documento real, reproduza o caso trocando nomes e números
  e mantendo o formato e o contexto.

Vulnerabilidades (dado tarjado recuperável no arquivo gerado, execução de código a partir de um
documento) seguem a [política de segurança](SECURITY.md) e não devem ser relatadas em issues públicas.

## Ambiente

```bash
git clone https://github.com/matheusteixeira-commits/themis-lgpd.git
cd themis-lgpd
python -m venv .venv
source .venv/bin/activate                     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m spacy download pt_core_news_lg
```

Para os testes de OCR, instale o Tesseract com o idioma `por` (ver [docs/INSTALACAO.md](docs/INSTALACAO.md)).

## Verificações

As mesmas verificações são executadas na integração contínua:

```bash
pytest                                                 # testes
pytest --cov --cov-report=term-missing:skip-covered    # testes com cobertura
ruff check src tests benchmark scripts                 # estilo e erros comuns
bandit -q -r src -c pyproject.toml                     # análise de segurança
python benchmark/sintetico.py --n 400 --minimo 0.99    # trava de regressão
pip-audit -r requirements/producao.txt                 # vulnerabilidades em dependências
```

Os testes marcados como `lento` (OCR, PDFs grandes) podem ser excluídos durante o desenvolvimento com
`pytest -m "not lento"`.

Benchmarks completos ([docs/BENCHMARKS.md](docs/BENCHMARKS.md)):

```bash
python benchmark/esic_ner.py                     # partição de seleção do esic-ner
python benchmark/avaliar_ouro.py                  # conjunto de referência (só métricas agregadas)
python benchmark/sintetico.py --n 1000 --semente 7
```

A partição de teste do esic-ner é reservada à avaliação de cada versão publicada
(`esic_ner.py --particao lockbox --lockbox MOTIVO` e `comparar.py --lockbox MOTIVO`); cada uso fica
registrado em `benchmark/treino/registro_lockbox.jsonl`.

## Organização do código

O Themis é construído sobre o Microsoft Presidio. Antes de escrever uma regra nova, verifique se o
Presidio já tem um reconhecedor que possa ser configurado para o caso. A arquitetura está descrita em
[docs/ARQUITETURA.md](docs/ARQUITETURA.md).

| Objetivo | Arquivo |
|---|---|
| Registrar ou configurar reconhecedores no Presidio; palavras de contexto | `src/themis_lgpd/analisador.py` |
| Reconhecer um novo documento | `src/themis_lgpd/reconhecedores/documentos.py` e, para o dígito verificador, `validadores.py` |
| Ajustar contatos, endereços, dados financeiros, veículos ou processos | `reconhecedores/contatos.py`, `localizacao.py`, `financeiro.py` |
| Ajustar o reconhecimento de nomes | `reconhecedores/nomes.py` e `scripts/gerar_listas_nomes.py` |
| Ajustar dados sensíveis | `reconhecedores/sensiveis.py` |
| Incluir um tipo de dado (etiqueta, categoria, prioridade, base legal) | `catalogo.py` |
| Alterar o que cada perfil tarja | `perfis.py` |
| Alterar a decisão, a propagação ou a consolidação | `motor.py`, `propagacao.py` |
| Suportar ou corrigir um formato de arquivo | `formatos/` |
| Alterar a verificação final | `formatos/verificacao.py` |

### Adicionar um reconhecedor

1. Escreva os padrões como `Padrao` (`reconhecedores/base.py`), com:
   - a expressão regular, usando `ANTES_NUM` e `DEPOIS_NUM` nos limites de números;
   - a confiança;
   - o `validador` de dígito verificador, quando houver, e `score_invalido` para o caso de dígito
     inválido com contexto (falha fechada);
   - as palavras de `contexto` e, quando o formato sozinho for ambíguo, `contexto_obrigatorio=True`;
   - a `camada` (`estrutural`, `contextual` ou `semantica`) e um `nome` que identifique a regra.
2. Se o tipo for novo, inclua-o em `catalogo.TIPOS`, com categoria, etiqueta e prioridade.
3. Registre o grupo de padrões em `reconhecedores_brasileiros()` (`analisador.py`).
4. Acrescente casos positivos em `tests/test_vazamentos.py` e casos que não devem ser tarjados em
   `test_nao_tarja_informacao_publica`.
5. Se houver gerador de documentos, inclua o tipo no conjunto sintético (`benchmark/sintetico.py`).

## Critérios para aceitar uma mudança

1. Todo vazamento corrigido ganha um caso de regressão: em `tests/test_vazamentos.py` para texto e em
   `tests/test_vazamento_arquivos.py` para arquivos.
2. Toda tarja indevida corrigida ganha um caso em `test_nao_tarja_informacao_publica`.
3. O recall do benchmark sintético não pode cair; mudanças que afetem a detecção informam no pull
   request os resultados da seleção do esic-ner e do conjunto de referência (`python
   benchmark/esic_ner.py` e `python benchmark/avaliar_ouro.py`). Exemplos de erro só podem ser
   examinados nas partições de ajuste (`--erros`).
4. Nenhuma mensagem de erro, aviso ou registro de log pode conter conteúdo do documento processado.
5. Nenhuma funcionalidade pode fazer requisições de rede durante o processamento.
6. Nenhuma dependência do núcleo pode ter licença incompatível com a MIT (por exemplo, AGPL).
7. `ruff` e `bandit` sem pendências.
8. Código, comentários, mensagens e documentação em português, no estilo dos módulos existentes: docstrings
   no formato Google (`Args`, `Returns`, `Raises`) e comentários que expliquem o motivo das decisões.

## Pull requests

- Uma mudança por pull request, com descrição do problema e da solução.
- Preencha a lista de verificação do modelo de pull request.
- Atualize a documentação e o [CHANGELOG.md](CHANGELOG.md) quando a mudança for perceptível ao usuário.

## Conduta

Este projeto adota o [Código de Conduta](CODE_OF_CONDUCT.md).
