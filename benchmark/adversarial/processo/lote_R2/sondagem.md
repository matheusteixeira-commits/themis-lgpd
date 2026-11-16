# Lote R2 — sondagem: identidades e localização

Lote adversarial de 30 documentos fictícios (R2-001 a R2-030) escritos para fazer o Themis LGPD
(perfil `lai`) deixar dado pessoal visível ou tarjar trecho que deveria ficar legível. O sistema foi
tratado como caixa-preta: só foram observados os erros apontados por `benchmark/avaliar_ouro.py`.

## 1. Composição e método

- **Arquivo:** `anotacao_redator.jsonl` (campos `id`, `genero`, `uf`, `texto`, `entidades`, `publicos`),
  gerado por `geracao/montar.py` a partir de `geracao/r1.py` (rodada 1) e `geracao/r2.py` (rodada 2).
  `geracao/numeros.py` produz os números com semente fixa e dígito verificador válido quando o documento
  tem um (CPF com região fiscal da UF, CNS definitivo e provisório, NIS, título de eleitor, NUP, processo
  CNJ, matrícula de certidão, identidade chinesa GB 11643, codice fiscale). RNM, passaportes, cédulas
  estrangeiras, DPRNM e RG da maioria das UFs não têm algoritmo público: só formato plausível.
- **Cobertura:** 27 UFs (SP, RR e MS com dois documentos) e 10 gêneros com 3 documentos cada: registro de
  atendimento a migrante, relatório de saúde indígena, boletim/registro de ocorrência, cadastro
  socioassistencial (ficha do CadÚnico, visita domiciliar, prontuário SUAS), ficha escolar, relatório do
  conselho tutelar, relatório de abordagem social, regularização fundiária (Incra, Titula Brasil, TAUS da
  SPU), manifestação de ouvidoria e termo de declaração/depoimento. Textos de 272 a 407 palavras.
- **Origens dos nomes:** indígenas (Tikuna, Guarani Kaiowá, Krahô, Xavante, Pataxó, Warao, Pemón),
  ciganos Calon e Rom, haitianos, venezuelanos, bolivianos, sírios, chineses e taiwaneses, coreanos,
  japoneses/nikkeis, alemães/pomeranos e italianos, além de nomes brasileiros que coincidem com palavras,
  virtudes, flores ou municípios, nome social, apelidos e iniciais.
- **Anotação:** exaustiva, segundo `DIRETRIZES.md` e as convenções de extensão, gravada **antes** de cada
  execução do sistema. `ferramentas.py validar` → **sem problemas** nas duas rodadas. A conferência própria
  do redator (`geracao/base.py`) verifica ainda 150–700 palavras, valor com dois rótulos e sobreposição
  entre ocorrência de trecho público e de entidade (a única ocorrência, a sigla "EMSI" dentro do número do
  relatório R2-002, foi corrigida no texto antes da primeira execução).
- **Integridade:** nenhum documento foi descartado ou reescrito depois da saída do sistema e nenhuma
  anotação foi alterada depois das execuções. Os 15 documentos da rodada 1 produzem os mesmos erros na
  execução final (determinismo conferido).

| Rótulo | Entidades | | Rótulo | Entidades |
|---|---:|---|---|---:|
| NOME_PESSOA | 250 | | ID_PROCESSUAL | 44 |
| DADO_SAUDE | 111 | | CONTATO | 29 |
| DATA_NASC | 101 | | DADO_FINANCEIRO | 28 |
| DOC_PESSOAL | 85 | | QUASI_IDENTIFICADOR | 28 |
| ENDERECO | 48 | | DADO_SENSIVEL | 24 |
| DOC_PROFISSIONAL | 17 | | ID_VEICULO | 4 |

Total: 769 entidades (400 na rodada 1, 369 na rodada 2) e 394 trechos públicos (183 + 211).

## 2. Métricas agregadas

`avaliar_ouro.py`, perfil `lai`. "Rodada 2" é o subconjunto R2-016 a R2-030 avaliado à parte
(`.trabalho/metricas_R2_r2.json`); "Final" são os 30 documentos (`.trabalho/metricas_R2_final.json`).

| Métrica | Rodada 1 (15) | Rodada 2 (15) | Final (30) | IC 95% final |
|---|---:|---:|---:|---|
| Entidades tarjadas (recall) | 0,7925 | 0,6152 | 0,7074 | 0,659–0,751 |
| Recall estrito | 0,7725 | 0,5772 | 0,6788 | 0,629–0,724 |
| Precisão das tarjas | 0,9600 | 0,9515 | 0,9563 | 0,940–0,972 |
| Trechos públicos preservados | 0,9851 | 0,9578 | 0,9703 | 0,955–0,984 |
| Documentos com vazamento | 1,00 | 1,00 | 1,00 | 1,00–1,00 |
| Tarja fora do gabarito | 0,1326 | 0,1447 | 0,1376 | 0,076–0,197 |
| Não tarjadas: sinalizadas / não detectadas | 3 / 80 | 8 / 134 | 11 / 214 | — |

Recall por rótulo:

| Rótulo | Rodada 1 | Rodada 2 | Final |
|---|---:|---:|---:|
| ENDERECO | 0,391 | 0,280 | 0,333 |
| QUASI_IDENTIFICADOR | 0,250 | 0,500 | 0,393 |
| DADO_SENSIVEL | 0,583 | 0,500 | 0,542 |
| DADO_FINANCEIRO | 0,750 | 0,500 | 0,607 |
| DADO_SAUDE | 0,768 | 0,600 | 0,685 |
| DATA_NASC | 0,846 | 0,571 | 0,713 |
| DOC_PESSOAL | 0,792 | 0,622 | 0,718 |
| ID_VEICULO | 1,000 | 0,500 | 0,750 |
| NOME_PESSOA | 0,870 | 0,689 | 0,784 |
| ID_PROCESSUAL | 0,870 | 0,714 | 0,796 |
| DOC_PROFISSIONAL | 1,000 | 0,857 | 0,941 |
| CONTATO | 0,947 | 1,000 | 0,966 |

A rodada 2, dirigida às classes da rodada 1, baixou o recall de 0,79 para 0,62 e a preservação de
0,985 para 0,958 no próprio subconjunto. Todos os 30 documentos vazaram ao menos uma entidade.

## 3. Classes de falha — vazamentos (225 entidades não protegidas no lote final)

Contagem = entidades não protegidas na execução final (r1/r2 = documentos 1–15 / 16–30). Os exemplos são
novos, curtos e fictícios; mostram a forma, não reproduzem os documentos. Classificação reproduzível em
`.trabalho/classificar_R2.py` (saída em `.trabalho/classes_R2.json`).

### Nomes (54)

| Classe | Total (r1/r2) | Forma que provoca o erro | Exemplo fictício |
|---|---:|---|---|
| N1 | 10 (2/8) | Nome em CAIXA ALTA fora das listas de prenomes (estrangeiro ou indígena), com partículas (DEL, DE LOS, VON DER, DE', AL) ou prenome raro; a mesma pessoa em caixa mista costuma ser detectada | `Nome: DAYANA DEL ROSARIO QUINTERO PAZ` |
| N2 | 12 (5/7) | Nome do Leste Asiático com sobrenome primeiro em caixa alta e prenome hifenizado ou romanizado; inclui o sobrenome isolado ("Sr. Kim") | `Requerente: HAN Ji-woo (nome adotado: Júlia Han)` |
| N3 | 8 (2/6) | Prenome que é substantivo comum ou virtude, em caixa alta ou isolado | `CONSOLAÇÃO DAS NEVES FORMOSA – responsável familiar`; `Dona Consolação informou…` |
| N4 | 13 (5/8) | Apelido de palavra única (profissão, título, gentílico, UF, termo afetivo ou estrangeiro), mesmo após "conhecido como" | `conhecido na feira como "Sargento"`; `la Cruceña` |
| N5 | 6 (2/4) | Iniciais de duas letras de criança ou testemunha (as de três ou quatro letras foram tarjadas) | `a criança E.F., 5 anos` |
| N6 | 5 (1/4) | Prenome estrangeiro ou indígena isolado, ou sobrenome que é topônimo (UF, país) | `a neta Svetlana`; `Raimundo Pará Xingu` |

### Documentos e números (36)

| Classe | Total (r1/r2) | Forma | Exemplo fictício |
|---|---:|---|---|
| D1 | 16 (6/10) | Documento de identidade ou viagem estrangeiro: cédula com prefixo V-, CI boliviana com sigla do departamento, NIF haitiano, carta d'identità, codice fiscale, identidade chinesa de 18 dígitos, DPRNM e passaporte com gentílico entre a palavra-chave e o número | `cédula V-19.552.731`; `passaporte sírio nº N0045…` |
| D2 | 7 (4/3) | Assento de registro civil por número + livro/folha/tomo/folio (certidão antiga, RANI, partida de nacimiento, acte de naissance) | `RANI nº 3.902, livro B-7, fls. 61` |
| D3 | 2 (0/2) | Carteira ou registro nacional sem padrão conhecido (CIPTEA, Registro Geral da Pesca) | `CIPTEA nº 2025-MG-0012345` |
| P1 | 5 (1/4) | Número "NNN/AAAA" de parecer, ficha, nota ou relatório individual, sem "protocolo" ou "processo" | `Parecer Social nº 47/2025` |
| P2 | 4 (2/2) | Registro em sistema setorial (SIASI, R.A.) com formato numérico genérico | `Nº SIASI 5.402.118` |
| V1 | 1 (0/1) | Placa estrangeira | `placa boliviana 3401-ZXP` |
| C1 | 1 (1/0) | Identificador de aplicativo de mensagem sem "@" | `WeChat: wei_bh88` |

### Endereços e localização (32 de 48 endereços)

| Classe | Total (r1/r2) | Forma | Exemplo fictício |
|---|---:|---|---|
| E1 | 8 (4/4) | Aldeia, povoado, linha, sítio/córrego ou comunidade ribeirinha com referência descritiva e sem logradouro numerado | `Aldeia Água Funda, terceira casa depois do poço artesiano` |
| E2 | 5 (2/3) | Ponto de pernoite de pessoa em situação de rua (praça, viaduto, calçada de igreja) | `pernoita sob a marquise do mercado, lado da peixaria` |
| E3 | 3 (2/1) | Acampamento, ocupação ou terreno, com barraca ou beco | `Ocupação Nova Conquista, beco 2, barraco 9` |
| E4 | 4 (1/3) | Endereço estrangeiro (calle, carrera, rue, esquina) | `Calle 7 con Avenida Bolívar, casa 15` |
| E5 | 7 (4/3) | Lote de assentamento ou unidade de abrigo citados sem a vicinal ou o logradouro | `ocupa o lote 23 desde 2015` |
| E6 | 4 (1/3) | Logradouro urbano numerado cujo nome é topônimo, data ou sobrenome, com complemento atípico (fundos, quarto, sobreloja, edifício) | `Rua Treze de Maio, 77, quarto 4` |
| E7 | 1 (0/1) | Coordenadas geográficas da residência | `coordenadas 1°12'05" S, 48°30'44" W` |

### Datas de nascimento e idades (29)

| Classe | Total (r1/r2) | Forma | Exemplo fictício |
|---|---:|---|---|
| A1 | 19 (7/12) | Idade "N anos" separada do nome por nacionalidade, ocupação, parentesco, parênteses ou data; "2 anos e meio" | `Lourdes, paraguaia, costureira, 36 anos` |
| A2 | 4 (0/4) | Idade por extenso | `o neto, de doze anos` |
| A3 | 6 (1/5) | Data de nascimento atípica: mês em algarismo romano, ano isolado, AAAA.MM.DD, por extenso completo, em espanhol, após "nato a … il" | `DN 03/VII/2012`; `nacida el 4 de mayo de 2001` |

### Dados sensíveis, saúde, finanças e quase-identificadores (74)

| Classe | Total (r1/r2) | Forma | Exemplo fictício |
|---|---:|---|---|
| S1 | 6 (2/4); 2 sinalizadas | Pertencimento étnico ou cigano fora do vocabulário ("família cigana", "etnia Rom kalderash", "povo Warao", "família quilombola Kalunga") | `a família se declara cigana calon` |
| S2 | 3 (2/1); 1 sinalizada | Identidade de gênero ("mulher transexual", "pessoa não binária"; "mulher trans" só sinalizada) | `pessoa não binária, 22 anos` |
| S3 | 2 (1/1); 2 sinalizadas | Religião como prática ou pertença a comunidade | `muçulmano praticante` |
| H1 | 29 (10/19); 5 sinalizadas | Termo coloquial, dispositivo ou ato assistencial ligado à pessoa: bombinha, nebulizador, glicosímetro, alta hospitalar, pré-natal, avaliação ou laudo, curativo, sintoma | `usa nebulizador em casa` |
| H2 | 4 (2/2); 1 sinalizada | Sigla clínica (TDO, PQT) ou condição seguida do estado do tratamento | `hanseníase, com PQT concluída` |
| H3 | 2 (1/1) | Lesão descrita em registro policial | `escoriação no joelho direito, suturada` |
| F1 | 7 (2/5) | Renda, benefício ou diária em campo de cadastro ou relato | `Bolsa Família: R$ 800,00` |
| F2 | 4 (1/3) | Percentual de salário mínimo, moeda estrangeira, preço de titulação, dinheiro levado | `US$ 1.500,00 subtraídos do cofre` |
| Q1 | 11 (4/7) | Quase-identificador por função + lugar + turno/dia ou cargo único, sem "único" | `o porteiro da noite do abrigo` |
| Q2 | 6 (5/1) | "único/única" + função + grupo ou lugar | `a única intérprete de árabe do hospital` |

Dos 28 quase-identificadores, 11 foram protegidos (3 na rodada 1, 8 na rodada 2), todos em formas próximas
das documentadas: função + turno ("enfermeira chefe do plantão noturno", "vigilante noturno do museu"),
"única/único" + função + local curto ("única professora da escola da comunidade") e descrição física com
marca distintiva. Os 17 restantes ficaram **sem sinalização**: "único/única" seguido de qualificador
étnico, linguístico ou de grupo ("única operadora haitiana do turno…", "única falante de warao entre…"),
cargo comunitário (cacique, aidamo, presidente de associação) e função ligada a rota, ponto ou dia da
semana ("mototaxista que faz a linha…", "cambista … nas manhãs de sexta-feira").

## 4. Classes de falha — tarjas indevidas (29 tarjas; 13 em trechos públicos)

| Classe | Total (r1/r2) | Forma | Exemplo fictício |
|---|---:|---|---|
| T1 | 6 (3/3) | Nome de pessoa ou de santo dentro de nome de instituição ou de município: prenome de invocação religiosa, unidade em caixa alta, município ou região administrativa com nome de pessoa fora da linha de local e data | `CRAS São Judas Tadeu`; `natural de Getúlio Vargas` |
| T2 | 5 (3/2) | Data de registro do próprio ato tarjada como documento | `Data do registro: 02/09/2025` |
| T3 | 5 (2/3) | A expressão "nome social" tarjada como vida sexual, inclusive em orientação genérica | `orientado sobre o uso do nome social` |
| T4 | 2 (1/1) | Sigla de equipe ou de cargo | `a EMSI do polo`; `quando o AIS está em área` |
| T5 | 2 (0/2) | Endereço de pessoa jurídica ou território coletivo tarjado como endereço pessoal | `Mercearia Boa Sorte, Rua do Comércio, 120, loja 3`; `Território Quilombola X` |
| T6 | 9 (6/3) | Relato policial, rótulo de campo, providência ou topônimo tarjados como saúde, violência ou dado de menor | `requisitado exame de corpo de delito`; `nascido em Homs` |

T1 a T5 atingiram trechos listados em `publicos`, exceto "Vicente Pires", "Antonio Díaz", as datas de
registro e o "nome social" da rodada 1, que não estavam na lista. T6 só entra em "tarja fora do gabarito": esses trechos não
foram anotados nem listados como públicos.

## 5. Observações

- **Acertos relevantes do sistema:** CPF, CNS, NIS, título, NUP, processo CNJ e certidão de 32 dígitos
  foram sempre tarjados; telefones estrangeiros (+58, +509, +591, +39) e e-mails também; "née le 12 mars
  1994" foi reconhecida. Foram preservados nomes de instituições e leis com nome de pessoa (Lei Maria da
  Penha, Lei Henry Borel, Lei Menino Bernardo, Lei Berenice Piana, Lei Romeo Mion, Maternidade Dona
  Evangelina Rosa, Hospital Odilon Behrens, Centro POP Miguilim, Hospital Estadual Adão Pereira Nunes) e
  municípios com nome de pessoa em contexto institucional (João Pessoa, Teotônio Vilela, Duque de Caxias,
  Ministro Andreazza, José de Freitas).
- **Padrão geral dos vazamentos:** o sistema depende de palavra-chave brasileira ou de formato nacional.
  Quando o identificador vem com palavra estrangeira (cédula, passeport, codice fiscale), com gentílico
  entre a palavra e o número, ou com referência descritiva em vez de logradouro numerado, a detecção cai.
  Em nomes, a caixa alta sem prenome das listas e a ordem sobrenome-prenome são as formas mais frágeis.
- **Decisões de anotação que a adjudicação pode rever:** valores sem palavra-chave, inclusive matrícula e
  registro profissional (só o número); "material ampliado", "alta hospitalar", "curativo", "TDO" e
  "dieta proposta pela nutricionista" como DADO_SAUDE; "exame de corpo de delito" **não** anotado, porque
  só foi requisitado; quase-identificador anotado também quando a pessoa tem apelido; endereço da
  pastelaria (pessoa jurídica) listado como público em R2-024; terra indígena e sítio Kalunga fora do
  ENDERECO e listados como públicos; nacionalidade não anotada.
- **Arquivos de trabalho:** `.trabalho/metricas_R2_r1.json`, `.trabalho/erros_R2_r1.jsonl`,
  `.trabalho/metricas_R2_final.json`, `.trabalho/erros_R2_final.jsonl`, `.trabalho/metricas_R2_r2.json`
  (subconjunto da rodada 2), `.trabalho/classificar_R2.py` e `.trabalho/classes_R2.json`.
