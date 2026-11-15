# Benchmarks

O Themis é avaliado em quatro conjuntos, todos reproduzíveis a partir do repositório. Os números
abaixo foram medidos com a versão 1.0.0 e com a versão em desenvolvimento (coluna "Versão atual"),
perfil `lai` salvo indicação em contrário, em CPU comum, sem GPU.

## Conjuntos

| Conjunto | Origem | Tamanho | O que mede |
|---|---|---|---|
| **esic-ner** | [EliMC/esic-ner](https://huggingface.co/datasets/EliMC/esic-ner), licença CC BY 4.0. Pedidos de acesso à informação sintéticos anotados com entidades | 975 pedidos (teste) e 4.473 (treino) | Cobertura por tipo de entidade, vazamento por documento, triagem e excesso de tarja em texto realista |
| **Sintético** | `benchmark/sintetico.py`: pedidos fictícios gerados com Faker (pt_BR) e documentos com dígitos verificadores válidos (e CPFs inválidos) | 1.000 documentos, semente 7 | Cobertura de todos os identificadores brasileiros em formatações difíceis |
| **Nacional** | `benchmark/nacional.py`: pedidos fictícios das 27 UFs, com municípios reais (IBGE), endereços urbanos, rurais e de rodovias e identificadores de abrangência nacional; e textos de interesse público sem dado pessoal | 1.080 documentos por conjunto e 270 textos públicos, semente 7 | Cobertura fora do Distrito Federal, por tipo e por região, e excesso de tarja em texto público |
| **Casos difíceis** | `tests/data/casos_dificeis_participa.jsonl`: casos sintéticos do 1º Hackathon em Controle Social (Participa DF) | 1.000 casos | Regressão: identificadores diretos e casos sem dado pessoal |

O conjunto esic-ner é baixado sob demanda na primeira execução e guardado em `benchmark/.cache/`; não
é redistribuído. A partição de **treino** é usada para desenvolver regras; a de **teste** fica reservada
para os números publicados. O esic-ner é dominado por pedidos do Distrito Federal, por isso não mede,
sozinho, a cobertura nacional.

O conjunto nacional tem duas variantes de documentos pessoais. A de **desenvolvimento** usa o modelo
"Eu, Fulano, residente em …" e serviu para escrever as regras; a de **validação** usa outras redações
(formulário "Endereço:", terceira pessoa, pedido de correspondência), outros nomes de logradouros e
propriedades e outros rótulos dos identificadores, e não foi usada para ajustar regras. Um valor
conta como vazado se o seu núcleo (nome do logradouro ou da propriedade, número do identificador)
aparecer na saída. Os **textos públicos** (prefeituras, obras em rodovias, assentamentos e comunidades
em notícias, ruas sem número, "Fazenda Pública", hospitais regionais) não podem receber nenhuma tarja.

No conjunto sintético, cada documento contém nome, CPF, telefone, e-mail e de três a sete
identificadores adicionais, em uma de cinco variantes: texto normal, todo em minúsculas (15%), todo em
caixa alta (10%), com ruído de OCR nos números (10%: cada "0", "1" e "5" trocado por "O", "l" ou "S" com
probabilidade de 25%) e com quebras de linha (10%). Vinte por cento dos CPFs têm dígito verificador
inválido e devem ser tarjados pela presença da palavra "CPF".

## Métricas

| Métrica | Definição |
|---|---|
| Entidades tarjadas (recall) | Fração das entidades pessoais anotadas totalmente cobertas pela tarja. Para valores com dígitos, todos os dígitos precisam estar cobertos; palavras-chave dentro do valor anotado ("SIAPE 1984235") podem ficar visíveis. No perfil `lai`, quase-identificadores contam como cobertos quando sinalizados para revisão |
| Recall estrito | Como o anterior, mas toda letra e todo dígito do valor anotado precisam estar cobertos |
| Documentos com vazamento | Fração dos documentos com dado pessoal em que ao menos uma entidade escapou |
| Triagem | Classificação "contém dado pessoal?" por documento: precisão, recall e F1 |
| Tarja fora do gabarito | Fração dos caracteres tarjados que não pertencem a nenhuma entidade anotada. É um indicador aproximado de excesso de tarja: o gabarito não anota todo dado pessoal |
| Não tarjadas: sinalizadas × não detectadas | Entidades que ficaram visíveis, divididas entre as detectadas e apenas sinalizadas para revisão (o perfil manda revisar, e o revisor as vê destacadas) e as não detectadas (nenhum aviso: dependem só da atenção humana) |
| Textos públicos preservados | No conjunto nacional, fração dos termos de interesse público que permanecem e fração dos textos públicos sem nenhuma tarja |
| Tempo por documento | Tempo médio de análise, excluída a carga do modelo |

No esic-ner, as entidades `ORG_JURIDICA` e `DOC_EMPRESA` (pessoas jurídicas) não são consideradas
pessoais.

## Resultados

### esic-ner — partição de teste (números publicados)

| Métrica | Themis 1.0.0 | Versão atual |
|---|---|---|
| Entidades pessoais tarjadas | 94,2% | **94,6%** |
| Recall estrito | 91,8% | **92,4%** |
| Pedidos com algum vazamento | 11,3% | **10,3%** |
| Triagem: precisão / recall / F1 | 0,948 / 0,941 / 0,944 | 0,948 / **0,943** / **0,945** |
| Tarja fora do gabarito | 5,7% | 5,7% |
| Não tarjadas: sinalizadas / não detectadas | 22 / 61 | 22 / **55** |
| Tempo por pedido | 15 a 22 ms | 17 a 20 ms |

A versão atual corrige o separador "é o" ("meu RG é o …"), o número de registro em conselhos com
região ("CRN-3 88421"), registros profissionais em minúsculas e itens de enumerações ("as CDAs X e
Y"), e amplia a cobertura para todo o país (ver [Nacional](#nacional)) e para medicamentos,
procedimentos e códigos da CID-11. Os números são gerados por `benchmark/esic_ner.py` e gravados em
`benchmark/resultado_esic_ner.json`.

Por rótulo:

| Rótulo | Entidades | Tarjadas (1.0.0 → atual) | Estrito (1.0.0 → atual) |
|---|---|---|---|
| `NOME_PESSOA` | 377 | 100,0% | 100,0% |
| `DATA_NASC` | 268 | 100,0% | 100,0% |
| `DOC_PESSOAL` | 76 | 100,0% | 100,0% |
| `CONTATO` | 48 | 100,0% | 100,0% |
| `DADO_FINANCEIRO` | 19 | 100,0% | 100,0% |
| `ID_VEICULO` | 14 | 100,0% | 100,0% |
| `DOC_PROFISSIONAL` | 32 | 96,9% | 68,8% → **75,0%** |
| `ENDERECO` | 52 | 94,2% | 65,4% → **69,2%** |
| `ID_PROCESSUAL` | 444 | 92,1% → **93,0%** | 91,2% → **92,1%** |
| `DADO_SAUDE` | 86 | 64,0% → **65,1%** | 64,0% → **65,1%** |
| `QUASI_IDENTIFICADOR` | 20 | 35,0% → **40,0%** (sinalizados) | 0,0% |

### esic-ner — partição de treino (desenvolvimento)

Os 4.473 pedidos de treino foram usados para encontrar falhas e escrever regras; por isso os ganhos
aqui são maiores que no teste e não devem ser lidos como estimativa de desempenho.

| Métrica | Themis 1.0.0 | Versão atual |
|---|---|---|
| Entidades pessoais tarjadas | 90,3% | **91,8%** |
| Recall estrito | 85,0% | **86,9%** |
| Pedidos com algum vazamento | 21,6% | **17,0%** |
| Triagem: F1 | 0,962 | 0,962 |
| Tarja fora do gabarito | 6,5% | 7,0% |
| Não tarjadas: sinalizadas / não detectadas | 97 / 798 | 170 / **591** |
| `DADO_SAUDE` (810 entidades) | 45,6% | **56,3%** |
| `DOC_PROFISSIONAL` (470) — estrito | 71,3% | **83,4%** |
| `ENDERECO` (678) — tarjados / estrito | 94,8% / 61,7% | **96,5%** / **64,6%** |

O aumento da tarja fora do gabarito no treino (6,5% → 7,0%) vem principalmente de nomes de
propriedades rurais ("Fazenda Boa Vista", "Sítio Recanto Feliz") citados por requerentes que o
gabarito não anota; na partição de teste, o indicador não se alterou.

Leitura dos resultados:

- **Dados de saúde (65,1% no teste).** Parte das anotações está em pedidos estatísticos ("quantos
  casos de depressão foram registrados…", "estoque de insulina glargina na rede"), que o perfil `lai`
  deliberadamente não tarja: sem vínculo com pessoa determinada, o termo vira alerta
  ([ADR 0004](adr/0004-perfis-lgpd-e-lai.md)). A separação entre entidades sinalizadas e não
  detectadas mostra o efeito: no treino, as não detectadas de saúde caíram de 344 para 184, e as
  sinalizadas subiram de 97 para 170.
- **Identificadores processuais (93,0%).** Parte das anotações corresponde a números de editais, notas
  fiscais e contratos, que são informação pública.
- **Recall estrito de endereços e registros profissionais.** A diferença para o recall comum vem de
  palavras-chave e componentes que ficam fora da tarja ("OAB/DF", nome da cidade), mantendo o número
  e o logradouro tarjados.
- **Tarja fora do gabarito.** Em boa parte, relatos de violência e de assédio que o perfil `lai` tarja
  e que o gabarito não anota.

Para referência, o BR-Access-NER (BERTimbau), desenvolvido no mesmo hackathon, reporta F1 de 0,9048 na
triagem desse conjunto; as metodologias de avaliação podem não ser idênticas.

### Nacional

`python benchmark/nacional.py --n 1080 --semente 7 --conjunto <conjunto>`; resultados em
`benchmark/resultado_nacional_desenvolvimento.json` e `benchmark/resultado_nacional_validacao.json`.

| Métrica | Themis 1.0.0 | Versão atual |
|---|---|---|
| Validação: endereços e identificadores tarjados | 64,5% | **100,0%** |
| Validação: documentos com vazamento | 94,6% | **0,0%** |
| Desenvolvimento: endereços e identificadores tarjados | 54,0% | **100,0%** |
| Desenvolvimento: documentos com vazamento | 97,4% | **0,0%** |
| Textos públicos: termos preservados | 98,6% | **100,0%** |
| Textos públicos: sem nenhuma tarja | 98,1% | **100,0%** |
| Tempo por documento | — | 11 ms |

Por tipo, na versão 1.0.0 (desenvolvimento / validação): endereço rural 0,0% / 37,4%; endereço
numerado ("Rua 15", "Rua B-15, Quadra 30") 51,2% / 47,4%; rodovia estadual 41,0% / 100,0%; endereço
urbano com abreviação 64,8% / 100,0%; benefício do INSS 40,8% / 66,2%; chassi 0,0% / 0,0%;
prontuário 0,0% / 0,0%; recibo do CAR 5,6% (só desenvolvimento); matrícula funcional estadual
(MASP, ID funcional) 7,5% (só desenvolvimento); registro em conselho com região 0,0% / 0,0%. Na
versão atual, todos os tipos e as cinco regiões ficam em 100,0% nos dois conjuntos. Por região, a
versão 1.0.0 variava de 51,9% (Norte) a 56,0% (Sul) no desenvolvimento.

Na versão 1.0.0, os textos públicos com tarja indevida eram municípios com nome de pessoa ("Secretaria
de Obras de Dom Eliseu", "Distrito Industrial de Vitória do Jari") e homenageados em nomes de rua
("Rua Professora Maria Clara"); a versão atual os reconhece como lugares.

**O que este conjunto não prova.** Os documentos são gerados por modelos escritos pelos autores, que
também escreveram as regras; o conjunto de validação usa redações diferentes e não foi usado no
ajuste, mas não substitui documentos reais. O resultado de 100% significa que os formatos
representados são tratados, não que toda variação real de endereço ou identificador o seja.

### Sintético

| Métrica | Perfil `lai` | Perfil `maxima` |
|---|---|---|
| Identificadores tarjados | **99,6%** | **99,6%** |
| Documentos com vazamento | 3,3% | 3,3% |
| Tempo por documento | 14 a 16 ms | 19 ms |

Por tipo (perfil `lai`):

| Tipo | Tarjados | Tipo | Tarjados |
|---|---|---|---|
| `NOME` | 100,0% | `CONTA_BANCARIA` | 99,7% |
| `EMAIL` | 100,0% | `PIS` | 99,7% |
| `TELEFONE` | 100,0% | `ENDERECO` | 99,7% |
| `CEP` | 100,0% | `PROCESSO_JUDICIAL` | 99,7% |
| `IP` | 100,0% | `CPF` | 99,5% |
| `MATRICULA` | 100,0% | `CNH` | 99,4% |
| `DATA_NASCIMENTO` | 100,0% | `CARTAO` | 98,7% |
| `PROCESSO_ADMINISTRATIVO` | 100,0% | `CNS` | 98,1% |
| `RG` | 99,7% | `TITULO_ELEITOR` | 97,9% |
| | | `PLACA` | 97,6% |

Todos os 33 documentos com vazamento pertencem à variante com ruído de OCR. Nos demais 858
documentos (texto normal, minúsculas, caixa alta e quebras de linha), nenhum identificador vazou. As
falhas ocorrem quando o ruído substitui o primeiro caractere de um número (`S713 4436 2542`,
`l39.042.934-27`, `O0516431328`) ou atinge placas de veículo (`PAVlF63`, `OVMOG14`): nesses casos, a
correção de OCR da normalização não reconstitui o número e os dígitos verificadores não conferem. Ver
[Limitações](#limitações-da-avaliação).

### Casos difíceis

| Verificação | Resultado |
|---|---|
| Casos com identificador direto (330) com ao menos uma tarja, perfil `lai` | 330 (100%) |
| Casos sem dado pessoal (10) sem nenhuma tarja, perfil `lai` | 10 (100%) |
| Casos com dado pessoal (990) com ao menos uma tarja, perfil `maxima` | 801 (80,9%) |
| Casos com dado pessoal (990) com tarja ou alerta, perfil `lai` | 801 (80,9%) |

Os casos com dado pessoal incluem categorias de intimidade, saúde, dados sensíveis e casos-limite, em
que a decisão depende de contexto. As três primeiras verificações são executadas pela suíte de testes
(`tests/test_cli_e_regressao.py`).

## Comparação com o Presidio puro

`benchmark/comparar.py` mede, com os mesmos dados e as mesmas métricas, o Presidio 2.2.366 configurado
para português com o modelo `pt_core_news_lg` e os reconhecedores que ele habilita por padrão
(entidades do spaCy, e-mail, telefone, cartão, IP, IBAN, URL, data, criptomoeda, MAC, UUID), tarjando
tudo o que detecta. É o resultado obtido ao configurar o Presidio para português sem reconhecedores
brasileiros.

| Métrica | Presidio puro (pt) | Themis 1.0.0 |
|---|---|---|
| esic-ner: entidades pessoais tarjadas | 53,3% | **94,5%** |
| esic-ner: nomes tarjados | 98,9% | **100,0%** |
| esic-ner: documentos pessoais tarjados | 7,9% | **100,0%** |
| esic-ner: datas de nascimento tarjadas | 100,0% | 100,0% |
| esic-ner: pedidos com algum vazamento | 93,3% | **10,5%** |
| esic-ner: triagem (F1) | 0,733 | **0,944** |
| esic-ner: triagem (precisão) | 0,583 | **0,948** |
| esic-ner: tarja fora do gabarito | 30,8% | **5,7%** |
| sintético: identificadores tarjados | 57,7% | **99,6%** |
| sintético: documentos com vazamento | 99,8% | **3,3%** |

A tabela gerada automaticamente, com os dados completos por rótulo, está em
[benchmark/COMPARACAO.md](../benchmark/COMPARACAO.md) e [benchmark/COMPARACAO.json](../benchmark/COMPARACAO.json).

## Como reproduzir

A partir da raiz do repositório, com o ambiente de desenvolvimento instalado
([INSTALACAO.md](INSTALACAO.md#instalação-para-desenvolvimento)):

```bash
# esic-ner (baixa o conjunto na primeira execução)
python benchmark/esic_ner.py --json benchmark/resultado_esic_ner.json
python benchmark/esic_ner.py --perfil maxima
python benchmark/esic_ner.py --erros 20          # mostra 20 exemplos de vazamento
python benchmark/esic_ner.py --split train --json benchmark/resultado_esic_ner_train.json

# Nacional (27 UFs) e textos públicos
python benchmark/nacional.py --n 1080 --semente 7 --conjunto desenvolvimento \
    --json benchmark/resultado_nacional_desenvolvimento.json
python benchmark/nacional.py --n 1080 --semente 7 --conjunto validacao \
    --json benchmark/resultado_nacional_validacao.json

# Sintético
python benchmark/sintetico.py --n 1000 --semente 7 --perfil lai
python benchmark/sintetico.py --n 1000 --semente 7 --perfil maxima

# Comparação com o Presidio puro (gera benchmark/COMPARACAO.md e .json)
python benchmark/comparar.py
python benchmark/comparar.py --outro-src ../outra-versao/src --outro-rotulo "Themis anterior"

# Casos difíceis
pytest tests/test_cli_e_regressao.py -k casos_dificeis
```

O tempo por documento varia com o equipamento; as demais métricas são determinísticas para a mesma
versão do Themis, do Presidio e do modelo de linguagem.

## Integração contínua

O CI executa `python benchmark/sintetico.py --n 400 --minimo 0.99` (semente 2026) em cada alteração e
falha se o recall ficar abaixo de 99%. Na versão 1.0.0, esse conjunto resulta em 99,6% de
identificadores tarjados e 3,0% de documentos com vazamento.

Executa também o benchmark nacional (540 documentos de cada conjunto) com
`--minimo 0.99 --preservacao-minima 0.99`: falha se o recall cair abaixo de 99% ou se mais de 1% dos
termos de interesse público passar a ser tarjado. Com o código da versão 1.0.0, essa trava falha.

## Limitações da avaliação

- O esic-ner e o conjunto sintético são compostos de textos sintéticos. Documentos reais têm estruturas
  mais variadas (tabelas, cabeçalhos, digitalizações), não representadas nestes números.
- As métricas avaliam o texto. A anonimização de arquivos (PDF, DOCX, XLSX, imagens) é coberta por
  testes de regressão específicos, não por estes benchmarks.
- O ruído de OCR do conjunto sintético é simulado por troca de caracteres; o OCR real produz também
  quebras, fusões e omissões. O resultado de 99,6% decorre das falhas nessa variante: identificadores
  cujo primeiro caractere foi trocado por letra e placas com letras no lugar de dígitos não são
  reconhecidos. Documentos digitalizados de baixa qualidade exigem revisão humana atenta.
- O gabarito do esic-ner não anota todo dado pessoal; a tarja fora do gabarito é, por isso, um limite
  superior aproximado do excesso de tarja.
- A comparação com o BR-Access-NER usa o número publicado pelos autores, não uma execução própria.
