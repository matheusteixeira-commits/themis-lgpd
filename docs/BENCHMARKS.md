# Benchmarks

O Themis é avaliado em sete conjuntos, todos reproduzíveis a partir do repositório. Os números
abaixo foram medidos com a versão 1.0.0 e com a versão em desenvolvimento (coluna "Versão atual"),
perfil `lai` salvo indicação em contrário, em CPU comum, sem GPU. A detecção da versão atual foi
melhorada em ciclos de treinamento orientados por medição, descritos em
[Treinamento das regras](#treinamento-das-regras).

## Conjuntos

| Conjunto | Origem | Tamanho | O que mede |
|---|---|---|---|
| **esic-ner** | [EliMC/esic-ner](https://huggingface.co/datasets/EliMC/esic-ner), licença CC BY 4.0. Pedidos de acesso à informação sintéticos anotados com entidades | 975 pedidos (teste) e 4.473 (treino) | Cobertura por tipo de entidade, vazamento por documento, triagem e excesso de tarja em texto realista |
| **Sintético** | `benchmark/sintetico.py`: pedidos fictícios gerados com Faker (pt_BR) e documentos com dígitos verificadores válidos (e CPFs inválidos) | 1.000 documentos, semente 7 | Cobertura de todos os identificadores brasileiros em formatações difíceis |
| **Nacional** | `benchmark/nacional.py`: pedidos fictícios das 27 UFs, com municípios reais (IBGE), endereços urbanos, rurais e de rodovias e identificadores de abrangência nacional; e textos de interesse público sem dado pessoal | 1.080 documentos por conjunto e 270 textos públicos, semente 7 | Cobertura fora do Distrito Federal, por tipo e por região, e excesso de tarja em texto público |
| **Casos difíceis** | `tests/data/casos_dificeis_participa.jsonl`: casos sintéticos do 1º Hackathon em Controle Social (Participa DF) | 1.000 casos | Regressão: identificadores diretos e casos sem dado pessoal |
| **Conjunto de referência** | `benchmark/ouro`: documentos oficiais fictícios (ofícios, despachos, portarias, atas, laudos, manifestações de ouvidoria, mensagens) de todas as regiões, com anotação dupla cega e adjudicação ([diretrizes](../benchmark/ouro/DIRETRIZES.md)); congelado por SHA-256 | 120 documentos, 1.306 dados pessoais e 1.401 trechos públicos anotados | Recall, **precisão real** e preservação de trechos públicos em documentos oficiais; só avaliação |
| **Documentos oficiais** | `benchmark/oficial`: documentos oficiais fictícios em quatro lotes temáticos, anotados pelas mesmas diretrizes ([LEIAME](../benchmark/oficial/LEIAME.md)) | 200 documentos (ajuste 153, seleção 47) | Desenvolvimento: análise de erros no ajuste, escolha entre alternativas na seleção |
| **Lotes adversariais** | `benchmark/adversarial`: documentos oficiais fictícios redigidos para provocar erros (tabelas, ruído de digitalização, identidades e endereços atípicos, dados sensíveis fora do registro clínico, documentos públicos densos), com revisão independente ([LEIAME](../benchmark/adversarial/LEIAME.md)) | 120 documentos | Desenvolvimento: robustez em condições adversas |

O conjunto esic-ner é baixado sob demanda na primeira execução e guardado em `benchmark/.cache/`; não
é redistribuído. A partição de **treino** é dividida, pelo SHA-256 do texto, em **ajuste** (3.557
pedidos, análise de erros) e **seleção** (916, só métricas agregadas); a de **teste** é a *lockbox*,
reservada aos números publicados: `--particao lockbox` exige um motivo e cada uso fica registrado em
`benchmark/treino/registro_lockbox.jsonl`. O esic-ner é dominado por pedidos do Distrito Federal, por
isso não mede, sozinho, a cobertura nacional.

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
| Tarja fora do gabarito | Fração dos caracteres tarjados que não pertencem a nenhuma entidade anotada. No esic-ner é um indicador aproximado de excesso de tarja, porque o gabarito não anota todo dado pessoal |
| Precisão das tarjas | Nos conjuntos de documentos oficiais, em que todo dado pessoal está anotado: fração das tarjas que atingem algum dado pessoal |
| Preservação de trechos públicos | Nos conjuntos de documentos oficiais: fração dos trechos anotados como públicos (órgãos, normas, programas, datas e locais de expedição) que ficaram intactos |
| Não tarjadas: sinalizadas × não detectadas | Entidades que ficaram visíveis, divididas entre as detectadas e apenas sinalizadas para revisão (o perfil manda revisar, e o revisor as vê destacadas) e as não detectadas (nenhum aviso: dependem só da atenção humana) |
| Textos públicos preservados | No conjunto nacional, fração dos termos de interesse público que permanecem e fração dos textos públicos sem nenhuma tarja |
| Tempo por documento | Tempo médio de análise, excluída a carga do modelo |

No esic-ner, as entidades `ORG_JURIDICA` e `DOC_EMPRESA` (pessoas jurídicas) não são consideradas
pessoais.

## Resultados

### Documentos oficiais — conjunto de referência

`python benchmark/avaliar_ouro.py`; resultados em `benchmark/treino/final/ouro.json`. A linha de base é
a versão anterior ao treinamento (com as melhorias de cobertura nacional e de formatos), medida antes
do primeiro ciclo; cada coluna seguinte é o sistema integrado ao fim de um ciclo. Os erros deste
conjunto nunca foram examinados.

| Métrica | Linha de base | Ciclo 1 | Ciclo 2 | **Versão atual** |
|---|---|---|---|---|
| Dados pessoais tarjados (recall) | 64,7% | 68,8% | 91,9% | **93,6%** |
| Recall estrito | 63,1% | 67,3% | 90,3% | **90,8%** |
| Precisão das tarjas | 85,5% | 84,2% | 92,9% | **93,5%** |
| Trechos públicos preservados | 88,9% | 88,4% | 95,4% | **96,5%** |
| Documentos com vazamento | 93,3% | 88,5% | 53,8% | **50,0%** |
| Tarja fora do gabarito | 19,8% | 20,1% | 18,4% | **17,8%** |

Comparação pareada da versão atual com a linha de base (mesmos 120 documentos; intervalo de confiança
de 95% por *bootstrap*): recall +28,9 pontos [+24,6; +32,9], precisão +8,0 [+5,8; +10,5],
preservação +7,5 [+5,9; +9,1]; 45 documentos deixaram de vazar e nenhum passou a vazar (McNemar,
p < 0,001). Contra o ciclo 2, o último ciclo acrescentou recall +1,8 ponto [+1,0; +2,6] e preservação
+1,1 [+0,3; +1,8], com 4 documentos que deixaram de vazar e nenhum que passou a vazar.

Por rótulo (linha de base → versão atual): nomes 86,2% → **98,9%**; registro profissional 86,3% →
**99,0%**; documento pessoal 89,0% → **96,1%**; data de nascimento 36,4% → **95,5%**; valores de
pessoa natural 38,3% → **91,7%**; endereço 85,5% → **91,9%**; processos e registros sobre pessoa
80,3% → **92,1%**; saúde 21,7% → **88,5%**; dados sensíveis 14,8% → **59,3%**; quase-identificadores
0,0% → **53,8%**; contato 100,0% → 99,0%; veículo 100,0%.

Metade dos documentos ainda tem algum dado visível: os documentos deste conjunto têm, em média, 11
dados pessoais, e basta um para contar como vazamento. Os rótulos mais fracos — dados
sensíveis descritos por perífrase, quase-identificadores e saúde em linguagem leiga — são também os que
mais dependem de interpretação; ver [Limitações](#limitações-da-avaliação).

### esic-ner — partição de teste (números publicados)

`python benchmark/esic_ner.py --particao lockbox --lockbox MOTIVO`; resultados em
`benchmark/resultado_esic_ner.json`. A coluna "Antes do treinamento" é a medição registrada antes do
primeiro ciclo; a "Versão atual", a avaliação final ao término do treinamento, repetida com resultado
idêntico na versão publicada (ver [Treinamento das regras](#treinamento-das-regras)).

| Métrica | Themis 1.0.0 | Antes do treinamento | **Versão atual** |
|---|---|---|---|
| Entidades pessoais tarjadas | 94,2% | 94,6% | **95,1%** |
| Recall estrito | 91,8% | 92,0% | 91,8% |
| Pedidos com algum vazamento | 11,3% | 10,3% | **9,9%** |
| Triagem: precisão / recall / F1 | 0,948 / 0,941 / 0,944 | 0,948 / 0,943 / 0,946 | **0,963** / **0,949** / **0,956** |
| Tarja fora do gabarito | 5,7% | 5,7% | **5,3%** |
| Não tarjadas: sinalizadas / não detectadas | 22 / 61 | 22 / 55 | 24 / **47** |
| Tempo por pedido | 15 a 22 ms | 17 a 20 ms | 30 ms |

Na comparação pareada com a medição anterior ao treinamento, a diferença no recall é de +0,4 ponto
[0,0; +0,9]; 4 pedidos deixaram de vazar e 2 passaram a vazar (um dado de saúde e um nome; McNemar,
p = 0,69). Nos pedidos do e-SIC, em que o sistema já acertava quase todos os identificadores, o
treinamento não trouxe ganho de recall estatisticamente significativo; o ganho está na triagem e no
excesso de tarja. O recall estrito caiu porque a sigla do conselho, o órgão emissor e a UF passaram a
ficar legíveis ao lado do número tarjado ("CRM-PE [REGISTRO PROFISSIONAL]").

Por rótulo (antes do treinamento → versão atual):

| Rótulo | Entidades | Tarjadas | Estrito |
|---|---|---|---|
| `NOME_PESSOA` | 377 | 100,0% → 99,7% | 100,0% → 99,7% |
| `DATA_NASC` | 268 | 100,0% | 100,0% |
| `DOC_PESSOAL` | 76 | 100,0% | 100,0% → 97,4% |
| `CONTATO` | 48 | 100,0% | 100,0% |
| `DADO_FINANCEIRO` | 19 | 100,0% | 100,0% |
| `ID_VEICULO` | 14 | 100,0% | 100,0% |
| `DOC_PROFISSIONAL` | 32 | 96,9% | 56,3% → 15,6% |
| `ENDERECO` | 52 | 94,2% | 69,2% → **78,9%** |
| `ID_PROCESSUAL` | 444 | 93,0% → **93,5%** | 92,1% → **93,5%** |
| `DADO_SAUDE` | 86 | 65,1% → **67,4%** | 65,1% → **67,4%** |
| `QUASI_IDENTIFICADOR` | 20 | 40,0% → **55,0%** (sinalizados) | 0,0% |

### esic-ner — partição de treino (desenvolvimento)

Os 4.473 pedidos de treino (partições de ajuste e de seleção) foram usados para encontrar falhas,
escrever regras e treinar o classificador; por isso os ganhos aqui são muito maiores que no teste e não
devem ser lidos como estimativa de desempenho.

| Métrica | Themis 1.0.0 | Antes do treinamento | Versão atual |
|---|---|---|---|
| Entidades pessoais tarjadas | 90,3% | 91,8% | **97,1%** |
| Recall estrito | 85,0% | 86,9% | **87,2%** |
| Pedidos com algum vazamento | 21,6% | 17,0% | **7,2%** |
| Triagem: F1 | 0,962 | 0,962 | **0,972** |
| Tarja fora do gabarito | 6,5% | 7,0% | 7,2% |
| Não tarjadas: sinalizadas / não detectadas | 97 / 798 | 170 / 591 | 178 / **86** |
| `DADO_SAUDE` (810 entidades) | 45,6% | 56,3% | **75,8%** |
| `DOC_PROFISSIONAL` (470) — estrito | 71,3% | 83,4% | 21,5% |
| `ENDERECO` (678) — tarjados / estrito | 94,8% / 61,7% | 96,5% / 64,6% | **98,8%** / **73,9%** |

A tarja fora do gabarito vem principalmente de nomes de propriedades rurais ("Fazenda Boa Vista",
"Sítio Recanto Feliz") citados por requerentes, que o gabarito não anota. A queda do recall estrito de
registros profissionais vem da sigla do conselho e da UF, que passaram a ficar legíveis ao lado do
número tarjado.

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
| Tempo por documento | — | 19 a 21 ms (11 ms antes do treinamento) |

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
| Documentos com vazamento | 3,1% | 3,1% |
| Tempo por documento | 23 ms | 23 ms |

Por tipo (perfil `lai`):

| Tipo | Tarjados | Tipo | Tarjados |
|---|---|---|---|
| `NOME` | 100,0% | `CONTA_BANCARIA` | 99,7% |
| `EMAIL` | 100,0% | `PIS` | 99,7% |
| `TELEFONE` | 100,0% | `ENDERECO` | 100,0% |
| `CEP` | 100,0% | `PROCESSO_JUDICIAL` | 100,0% |
| `IP` | 100,0% | `CPF` | 99,5% |
| `MATRICULA` | 100,0% | `CNH` | 99,4% |
| `DATA_NASCIMENTO` | 100,0% | `CARTAO` | 98,7% |
| `PROCESSO_ADMINISTRATIVO` | 100,0% | `CNS` | 98,1% |
| `RG` | 99,7% | `TITULO_ELEITOR` | 97,9% |
| | | `PLACA` | 97,6% |

Todos os 31 documentos com vazamento pertencem à variante com ruído de OCR. Nos demais 858
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

## Treinamento das regras

Entre a linha de base e a versão atual, a detecção foi melhorada em três ciclos, com as regras de
escolha e de avaliação fixadas antes do primeiro.

**Separação dos dados.** Cada conjunto tem um papel único:

| Papel | Conjuntos | Uso permitido |
|---|---|---|
| Ajuste | esic-ner (3.557 pedidos), documentos oficiais (153), lotes adversariais (120) | Examinar erros documento a documento (`--erros`) e treinar o classificador |
| Seleção | esic-ner (916), documentos oficiais (47) | Escolher entre alternativas, só por métricas agregadas |
| Avaliação | conjunto de referência (120), partição de teste do esic-ner (975) | Medir; nunca examinar erros |

As partições de ajuste e de seleção são atribuídas pelo SHA-256 do texto normalizado
(`benchmark/treino/particoes.py`, `benchmark/oficial/particionar.py`). Os avaliadores recusam `--erros`
fora do ajuste, e a partição de teste do esic-ner exige um motivo e registra cada uso. No terceiro
ciclo, as seleções passaram a ser consultadas só por `benchmark/treino/portao.py`, que devolve métricas
agregadas, compara com o ciclo anterior pelas tolerâncias do ciclo e registra cada consulta.

**Ciclos.** Em cada ciclo, frentes de trabalho independentes — nomes; saúde e dados sensíveis; idade,
nascimento e valores; documentos e processos; endereços, contatos, veículos e quase-identificadores;
forma e estrutura do texto; classificador treinado — trabalharam em ramos separados, em cópias do
repositório das quais o conjunto de referência e a partição de teste foram removidos. Uma mudança só
era integrada se cumprisse as travas: suíte de testes e `ruff`; sintético e nacional ≥ 99%; nas
seleções, nenhum rótulo perdendo recall além da tolerância (0,5 ponto no esic-ner, 1 ponto nos
documentos oficiais) e precisão e preservação estáveis; tempo por documento limitado em relação ao
ciclo anterior. O primeiro ciclo trabalhou sobre o esic-ner; o segundo, sobre o corpus de documentos
oficiais, com o classificador retreinado; o terceiro corrigiu as classes de falha encontradas pelos
lotes adversariais, escritos por quem testou o sistema apenas pela saída.

**Critérios de decisão.** As versões são comparadas nos mesmos documentos
(`benchmark/treino/comparar_execucoes.py`): intervalo de confiança de 95% por *bootstrap* pareado
(2.000 reamostragens, semente fixa) e teste exato de McNemar sobre os documentos com vazamento. Um
rótulo de proteção do classificador só é desativado quando a ablação no sistema integrado mostra dano
medido (`ablacao_integrada.json` de cada ciclo).

**Verificações.** Os registros de execução de cada ciclo foram examinados por programa à procura de
acesso ao conjunto de referência, à partição de teste ou aos textos das seleções; os achados e as
medidas tomadas estão em `benchmark/treino/ciclo2/REGISTRO.md` e `benchmark/treino/ciclo3/REGISTRO.md`.
As linhas acrescentadas ao código foram comparadas com os corpora de desenvolvimento, à procura de
valores anotados e de sequências de seis palavras copiadas (sinal de regra escrita para um documento,
e não para uma classe de documentos); as ocorrências, todas em exemplos de comentários e testes, foram
substituídas por exemplos fictícios.

Resultados nas partições de seleção (não usadas na análise de erros):

| Seleção | Métrica | Linha de base | Ciclo 1 | Ciclo 2 | Versão atual |
|---|---|---|---|---|---|
| Documentos oficiais (47) | Recall | 46,3% | 48,9% | 91,6% | **92,7%** |
| | Precisão das tarjas | 79,6% | 77,9% | 90,4% | **91,8%** |
| | Trechos públicos preservados | 87,9% | 87,1% | 94,6% | **96,6%** |
| | Documentos com vazamento | 97,4% | 97,4% | 65,8% | **57,9%** |
| esic-ner (916) | Recall | 92,3% | 95,8% | 96,0% | **96,1%** |
| | Pedidos com vazamento | 17,0% | 10,3% | 9,9% | **9,7%** |
| | Recall de dados de saúde | 53,1% | 65,6% | 67,5% | **68,1%** |
| | Recall de quase-identificadores | 41,3% | 90,5% | 90,5% | **92,1%** |

Nos lotes adversariais, que foram material de desenvolvimento do terceiro ciclo, o recall passou de
66,5% para 96,4% e a precisão das tarjas de 83,5% para 98,7%; esses números medem a correção das
falhas encontradas, não o desempenho esperado. Registros, métricas por documento (só contagens) e
comparações de cada etapa estão em `benchmark/treino/` (`linha_de_base`, `ciclo1`, `ciclo2`, `ciclo3`,
`final`).

**Avaliação final.** O conjunto de referência e a partição de teste foram avaliados ao fim do terceiro
ciclo (`benchmark/treino/final/eef0f77`). Depois disso, os benchmarks de desempenho e nacional revelaram
dois defeitos, corrigidos antes da publicação: a verificação final recusava PDFs em que um termo de
saúde tarjado numa página aparecia, sem relação com a pessoa, em outra; e um sobrenome com palavra de
nome de instituição ("Casa Grande", "da Ponte") deixava de ser reconhecido. As correções foram decididas
fora dos conjuntos de avaliação. A versão publicada foi medida de novo em todos os conjuntos, com o uso
da partição de teste registrado, e as métricas do conjunto de referência, da partição de teste e das
seleções ficaram idênticas (`benchmark/treino/final`).

## Desempenho

`python benchmark/desempenho.py --json benchmark/resultado_desempenho.json`: análise de textos
fictícios de 10, 50 e 100 mil caracteres e anonimização de PDFs de texto com 10 e 50 páginas (uma
tarja por página), no mesmo computador (CPU comum, Windows, Python 3.11).

| Medida | Themis 1.0.0 | Antes do treinamento | Versão atual |
|---|---|---|---|
| Texto de 10 mil caracteres | 0,42 s (41,8 ms por mil caracteres) | 0,36 s (36,5 ms) | 0,69 s (68,5 ms) |
| Texto de 50 mil caracteres | 3,67 s (73,4 ms por mil) | 2,03 s (40,6 ms) | 3,78 s (75,6 ms) |
| Texto de 100 mil caracteres | 11,34 s (113,4 ms por mil) | 4,74 s (47,4 ms) | 8,01 s (80,1 ms) |
| PDF de 50 páginas | 23,6 s (0,47 s por página) | 15,9 s (0,32 s por página) | 18,0 s (0,36 s por página) |
| PDF de 50 páginas: tamanho gerado | 8.560 KB (143 vezes o original) | 4.990 KB (83 vezes) | 5.935 KB (99 vezes) |

As regras de contexto e o classificador acrescentados no treinamento quase dobraram o tempo de análise
de texto (de 36,5 para 68,5 ms por mil caracteres); o crescimento com o tamanho do texto continua quase
linear. Na anonimização de PDF, em que a composição das páginas pesa mais que a análise, o aumento foi
de 13% por página.

Na versão 1.0.0, o tempo por mil caracteres quase triplicava de 10 para 100 mil caracteres: o custo
era quadrático. Duas causas, encontradas por perfilamento: o reforço de confiança por contexto do
Presidio localizava o token de cada achado percorrendo o documento desde o início, e o filtro de
nomes remontava o texto do documento (`doc.text`) a cada entidade. A versão atual localiza o token
por busca binária (mesmo resultado, verificado em teste) e lê o texto uma vez. O crescimento passa a
ser quase linear; `tests/test_desempenho.py` falha se cinco vezes mais texto custar mais de 7,5 vezes
mais tempo.

No PDF, as páginas com tarja passaram a ser gravadas em escala de cinza quando não têm cor (um terço
dos dados, sem perdas) e em JPEG quando a página é fotográfica — digitalizações —, e a composição e a
compressão das páginas rodam em paralelo. As páginas sem tarja continuam copiadas sem alteração. As
detecções não mudaram: os resultados do esic-ner, do sintético e do nacional são idênticos antes e
depois dessas otimizações.

## Comparação com o Presidio puro

`benchmark/comparar.py` mede, com os mesmos dados e as mesmas métricas, o Presidio 2.2.366 configurado
para português com o modelo `pt_core_news_lg` e os reconhecedores que ele habilita por padrão
(entidades do spaCy, e-mail, telefone, cartão, IP, IBAN, URL, data, criptomoeda, MAC, UUID), tarjando
tudo o que detecta. É o resultado obtido ao configurar o Presidio para português sem reconhecedores
brasileiros.

| Métrica | Presidio puro (pt) | Themis (versão atual) |
|---|---|---|
| esic-ner: entidades pessoais tarjadas | 53,3% | **95,1%** |
| esic-ner: nomes tarjados | 98,9% | **99,7%** |
| esic-ner: documentos pessoais tarjados | 7,9% | **100,0%** |
| esic-ner: datas de nascimento tarjadas | 100,0% | 100,0% |
| esic-ner: pedidos com algum vazamento | 93,3% | **9,9%** |
| esic-ner: triagem (F1) | 0,733 | **0,956** |
| esic-ner: triagem (precisão) | 0,583 | **0,963** |
| esic-ner: tarja fora do gabarito | 30,8% | **5,3%** |
| esic-ner: tempo por pedido | 19 ms | 30 ms |
| sintético: identificadores tarjados | 57,7% | **99,6%** |
| sintético: documentos com vazamento | 99,8% | **3,1%** |

A tabela gerada automaticamente, com os dados completos por rótulo, está em
[benchmark/COMPARACAO.md](../benchmark/COMPARACAO.md) e [benchmark/COMPARACAO.json](../benchmark/COMPARACAO.json).

## Como reproduzir

A partir da raiz do repositório, com o ambiente de desenvolvimento instalado
([INSTALACAO.md](INSTALACAO.md#instalação-para-desenvolvimento)):

```bash
# esic-ner (baixa o conjunto na primeira execução)
python benchmark/esic_ner.py                                   # seleção (padrão)
python benchmark/esic_ner.py --particao ajuste --erros 20      # exemplos de vazamento, só no ajuste
python benchmark/esic_ner.py --particao train --json benchmark/resultado_esic_ner_train.json
python benchmark/esic_ner.py --particao lockbox --lockbox "MOTIVO" --json benchmark/resultado_esic_ner.json

# Conjunto de referência, documentos oficiais e lotes adversariais
python benchmark/avaliar_ouro.py --json ouro.json
python benchmark/avaliar_ouro.py benchmark/oficial/selecao.jsonl
python benchmark/avaliar_ouro.py benchmark/adversarial/lotes/*.jsonl

# Comparação pareada entre duas execuções (arquivos de --detalhes)
python benchmark/treino/comparar_execucoes.py base.jsonl candidata.jsonl

# Nacional (27 UFs) e textos públicos
python benchmark/nacional.py --n 1080 --semente 7 --conjunto desenvolvimento \
    --json benchmark/resultado_nacional_desenvolvimento.json
python benchmark/nacional.py --n 1080 --semente 7 --conjunto validacao \
    --json benchmark/resultado_nacional_validacao.json

# Sintético
python benchmark/sintetico.py --n 1000 --semente 7 --perfil lai
python benchmark/sintetico.py --n 1000 --semente 7 --perfil maxima

# Comparação com o Presidio puro (gera benchmark/COMPARACAO.md e .json; usa a partição de teste)
python benchmark/comparar.py --lockbox "MOTIVO"
python benchmark/comparar.py --lockbox "MOTIVO" --outro-src ../outra-versao/src --outro-rotulo "Themis anterior"

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

E avalia o conjunto de referência com `benchmark/avaliar_ouro.py --recall-minimo 0.93
--precisao-minima 0.925 --preservacao-minima 0.955`, cerca de um ponto abaixo dos números da versão
atual (93,6%, 93,5% e 96,5%): falha se uma mudança reduzir o recall, a precisão das tarjas ou a
preservação de trechos públicos em documentos oficiais. A trava só lê as métricas agregadas.

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
- O conjunto de referência, o corpus de documentos oficiais e os lotes adversariais são documentos
  fictícios escritos por processos semelhantes (redação com registro dos dados inseridos e revisão
  independente). O conjunto de referência nunca foi usado para ajustar regras, mas partilha estilo
  com o material de desenvolvimento; documentos reais de órgãos públicos podem ter estruturas e
  redações que nenhum dos três representa. A partição de teste do esic-ner, de outra origem, é o
  contraponto, e nela o ganho do treinamento foi pequeno.
- No segundo ciclo, a decisão de manter ativo o rótulo `DADO_SENSIVEL` do classificador foi revista
  depois de uma medição no conjunto de referência (`benchmark/treino/ciclo2/REGISTRO.md`); por isso,
  o resultado desse rótulo no conjunto de referência não é uma estimativa inteiramente independente.
- A partição de teste do esic-ner foi usada no desenvolvimento das versões anteriores ao treinamento,
  inclusive para examinar erros. Ela mede sem viés o efeito do treinamento (antes × depois), mas o
  nível absoluto pode ser otimista.
- O tempo de análise cresceu a cada ciclo de treinamento (de 1,13 a 1,15 vez por ciclo, mais o
  classificador): quase o dobro do tempo de antes do treinamento em textos longos.
