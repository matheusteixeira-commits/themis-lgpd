# Lote R3 — sondagem adversarial

Tema: dados de saúde, dados sensíveis e dados financeiros de pessoa natural **fora do registro
clínico** (fala transcrita, relatos, e-mails, despachos, atas, ouvidoria, assistência social,
educação especial, sistema prisional, conselho tutelar, socioeducação), ao lado de menções públicas e
agregadas sobre os mesmos temas. Sistema avaliado como caixa-preta: `benchmark/avaliar_ouro.py`
(perfil `lai`), sem leitura de código.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `anotacao_redator.jsonl` | 30 documentos (R3-001 a R3-030), anotação do redator |
| `geracao/dados.py` | gerador de nomes por combinação e de números com dígito verificador (CPF, NIS, CNS, CNJ, NUP, título); sementes 3301 (rodada 1) e 3302 (rodada 2) |
| `geracao/pool_r1.json`, `geracao/pool_r2.json` | saídas do gerador usadas nos textos |
| `geracao/fontes_r1.txt`, `geracao/fontes_r2.txt` | textos com marcação inline (`[[RÓTULO\|valor]]`, `{{público}}`), versão final |
| `geracao/fontes_r1_pre_sondagem.txt`, `geracao/fontes_r2_pre_sondagem.txt` | estado das fontes no momento de cada execução do sistema |
| `geracao/montar.py` | monta o JSONL e confere: toda ocorrência de valor pessoal está marcada; público não se sobrepõe a pessoal; um rótulo por valor; 150–700 palavras |
| `geracao/classificar_erros.py` | atribui cada erro do avaliador a uma classe (tabela explícita por valor) |

Métricas e erros: `.trabalho/metricas_R3_r1.json`, `.trabalho/erros_R3_r1.jsonl` (rodada 1, anotação
corrigida), `.trabalho/metricas_R3_r1_antes_correcao.json`, `.trabalho/metricas_R3_r2_somente.json`,
`.trabalho/metricas_R3_final.json`, `.trabalho/erros_R3_final.jsonl`, `.trabalho/classes_R3_*.json`.

## Composição

* 30 documentos, 8.975 palavras (181 a 447 por documento), 27 UFs (BA, GO e SC com dois documentos).
* Gêneros: manifestação de ouvidoria com resposta (4), e-mail funcional (4), ata de conselho de
  direitos ou de política pública (4), despacho (3), relatório de visita domiciliar (2), parecer ou
  estudo social (2), relatório de execução penal (2), comunicação da escola (2), termo de audiência
  (2), relatório de medida socioeducativa (2), relatório de conselho tutelar (2), estudo de caso de
  educação especial (1).
* 559 entidades: NOME_PESSOA 187, DADO_SAUDE 129, DADO_FINANCEIRO 66, DADO_SENSIVEL 52, ID_PROCESSUAL 33,
  DATA_NASC 32, DOC_PROFISSIONAL 23, CONTATO 15, ENDERECO 11, QUASI_IDENTIFICADOR 7, DOC_PESSOAL 4.
  377 trechos públicos.

## Processo e integridade

1. Rodada 1 escrita, anotada e validada (`ferramentas.py validar`: "sem problemas") antes de qualquer
   execução do sistema. SHA-256 do arquivo no momento da execução: `7e74af9b3ba68e6ccb2b5e3f56a8e876f4c36471978254887c55408bccb5e16c`.
2. Rodada 2 escrita a partir das classes da rodada 1, anotada e validada antes da execução
   (SHA-256 dos 30 documentos no momento da execução: `c47a9e10e9a719f9ee0b142750efff0069db5856197cbea9020b4d01c12d45aa`).
3. Nenhum documento foi descartado ou reescrito depois da saída do sistema. Correções posteriores,
   todas por omissão de anotação segundo as diretrizes (segunda menção de condição já anotada ou exame
   realizado na pessoa identificada), sem retirar nenhuma entidade:
   * R3-007 `órtese` (segunda menção do dispositivo da criança); R3-009 `amputação` e `avaliação de
     prótese` (mesma pessoa); R3-010 `dependente com deficiência` (no corpo refere-se ao filho
     identificado; a anotação por valor cobre também a linha de assunto); R3-012 `internação` (da
     adolescente identificada) — DADO_SAUDE;
   * R3-024 `exame de corpo de delito` (exame realizado na vítima, convenção 3) — DADO_SAUDE; `sapatão`
     (insulto que atribui orientação sexual à vítima) — DADO_SENSIVEL; R3-029 `violência
     autoprovocada` (tipo da notificação do adolescente identificado) — DADO_SAUDE.
   SHA-256 final: `b1867d0044f23657f7a8fb465077137a1bd3f3d8d599df8302812edc042a0c0d`.
4. Decisões de rótulo sem previsão expressa nas diretrizes (para a adjudicação): violência física ou
   psicológica sofrida por pessoa identificada → DADO_SAUDE (agravo de notificação compulsória);
   violência sexual e vida sexual → DADO_SENSIVEL; nome de instituição pública mantido como público
   mesmo ao lado de frase de saúde da pessoa; linha "Assunto:" e nome legal de benefício ("benefício
   assistencial à pessoa com deficiência") não anotados quando o mesmo trecho não aparece como dado
   da pessoa no corpo.

## Métricas agregadas

| Métrica | Rodada 1 (R3-001–015) | Rodada 2 isolada (R3-016–030) | Lote final (30) |
|---|---:|---:|---:|
| Documentos com vazamento | 1,000 (15/15) | 1,000 (15/15) | 1,000 (30/30) |
| Recall de entidades | 0,7351 | 0,6537 | 0,6977 (IC95 0,659–0,738) |
| Recall estrito | 0,7219 | 0,6420 | 0,6852 |
| Precisão das tarjas | 0,9307 | 0,9069 | 0,9205 (IC95 0,892–0,948) |
| Preservação dos públicos | 0,9556 | 0,9213 | 0,9404 (IC95 0,907–0,968) |
| Tarja fora do gabarito | 0,1132 | 0,1767 | 0,1413 |

Rodada 1 antes das correções de anotação: recall 0,7407, precisão 0,9124, preservação 0,9556,
vazamento 15/15.

Recall por rótulo (rodada 1 → final): DADO_SENSIVEL 0,18 → 0,21; DADO_SAUDE 0,45 → 0,41;
QUASI_IDENTIFICADOR 0,25 → 0,43; DATA_NASC 0,80 → 0,66; DADO_FINANCEIRO 0,74 → 0,67; ENDERECO
0,86 → 0,82; ID_PROCESSUAL 0,82 → 0,85; NOME_PESSOA 0,95 → 0,96; CONTATO, DOC_PESSOAL e
DOC_PROFISSIONAL 1,00 nas duas rodadas.

## Classes de falha — vazamentos

Contagem de entidades não protegidas (ocorrências na rodada 1 / no lote final; documentos afetados
no lote final). Exemplos fictícios, escritos para esta nota.

| Classe | Forma do texto | R1 | Final | Docs | Exemplo fictício |
|---|---|---:|---:|---:|---|
| V6 | Dado sensível não clínico em terceira pessoa ou perífrase: pertença religiosa por prática ("congrega", "frequenta", "fio de contas", "ogã", "mãe pequena", "ñandesy"), etnia por pertença ("pertence ao povo…"), orientação e vida sexual por relação ("mantém relacionamento com…", "HSH", "trabalhadora sexual"), filiação por função ("delegada sindical", "candidato à diretoria do sindicato"), opinião política por atuação ("fez campanha para…", "militante do…") | 18 | 41 | 24 | "o avô é cambono do terreiro da Rua Sete" |
| V1 | Saúde mental, sintoma ou comportamento descrito em linguagem leiga ou em fala transcrita (insônia, alucinação, automutilação, ideação suicida, recusa alimentar) | 12 | 24 | 10 | "diz que vê vultos no quintal e não come há dias" |
| V7 | Valor de pessoa natural por extenso, em salário mínimo após verbo de ganho ou em fração ("três quartos", "um e meio"), ou após expressão de gasto, credor pessoa jurídica, parcela, pecúlio ou remuneração de preso | 10 | 22 | 16 | "tira uns mil e quinhentos na roça" |
| V5 | Condição, gestação, deficiência ou exame nomeado sem verbo de atribuição reconhecido, inclusive marca comercial de medicamento e sigla de exame | 11 | 19 | 15 | "toma Tegretol desde pequeno" |
| V3 | Tratamento ou cuidado descrito pelo serviço ou pelo evento (CAPS, ambulatório, comunidade terapêutica, observação hospitalar, hemodiálise, fila de transplante, PrEP) | 5 | 15 | 12 | "segue no CAPS i a cada quinze dias" |
| V8 | Idade em aposto a prenome isolado, por extenso ou entre parênteses | 4 | 11 | 11 | "Taís, de 17 anos, compareceu" |
| V2 | Uso de substância por verbo, gíria ou perífrase | 3 | 9 | 7 | "vive na pinga desde o desemprego" |
| V4 | Violência relatada por verbo de ação ou classificada pelo técnico, sem "vítima de" | 5 | 9 | 6 | "o ex-marido a empurrou da escada" |
| V9 | Prenome que é nome de município ou está fora da lista de prenomes (parcialmente tarjado ou só sinalizado) | 5 | 8 | 6 | "a filha Marília faltou" |
| V10 | Número de relatório, parecer, ficha ou comunicado sobre pessoa com sigla de instrumento não prevista (FICAI, PIA, CTC) ou número curto | 3 | 5 | 4 | "PLANO DE ATENDIMENTO Nº 33/2025-CRE" |
| V12 | Quase-identificador por função, lotação ou turno sem a palavra "único" | 3 | 4 | 3 | "o vigia da noite da escola do assentamento" |
| V11 | Endereço regional ou rural sem logradouro típico | 1 | 2 | 2 | "Folha 28, Quadra 5, Lote 3" |
| **Total** | | **80** | **169** | | |

Observações por classe:

* V6 é a classe dominante: recall de DADO_SENSIVEL de 0,21 no lote. Parte dos termos isolados foi
  protegida (gay, mulher trans, travesti, homem trans, parda, preta, muçulmana, Testemunha de Jeová,
  sapatão); outros ficaram só sinalizados (adventista, lésbica, negra, estupro de vulnerável). A falha
  está na **perífrase** e na **terceira pessoa** sem marcador na frase — atas, despachos e e-mails não
  têm campos de identificação que tornem o documento "centrado em pessoa".
* V1 e V5: o vocabulário clínico explícito é bem coberto (HIV, sífilis, síndrome de Down, idade
  gestacional, diabetes, insulina, até relato em espanhol), mas não as descrições leigas de sintomas,
  as marcas comerciais (três das quatro marcas usadas vazaram; só Ritalina foi protegida) e condições comuns fora de registro clínico
  ("tem paralisia cerebral", "tem asma", "está grávida" escaparam em frases com papel de pessoa).
* V7: vazam todos os sete valores **por extenso** (inclusive em espanhol), o salário mínimo após
  verbo de ganho ("eu ganho um salário mínimo") e em fração ("três quartos", "um salário e meio"), e
  valores em reais com âncora de gasto ("gastar cerca de", "gasta em média"), de credor pessoa
  jurídica ("com a concessionária"), de parcela, de pecúlio e de remuneração de preso. As formas
  abreviadas ("R$ 1,3 mil") e "pensão de um salário mínimo" foram protegidas.
* V8: a idade é protegida após papel ("a requerente, de 41 anos") e falha após prenome isolado,
  inclusive prenomes comuns.
* V9: dos dezesseis prenomes que também são municípios, onze foram protegidos (inclusive com pronome
  de tratamento, como "Dra. Cristina"); vazaram Marília, Mercedes e Vitória, e Guaraci e Ubiratã
  ficaram apenas sinalizados. "Kemilly" e "Ryan" no início de nome completo deixaram o prenome visível.

## Classes de falha — tarjas indevidas

Trechos da lista de públicos tarjados (ocorrências no arquivo de erros, rodada 1 / final):

| Classe | Forma do texto | R1 | Final | Docs | Exemplo fictício |
|---|---|---:|---:|---:|---|
| T1 | Estatística agregada com termo de violência, saúde, gestação ou deficiência | 6 | 9 | 6 | "foram 52 notificações de violência sexual em 2025" |
| T4 | E-mail institucional de setor em cabeçalho de mensagem (De/Para/Cc) — todas as ocorrências testadas foram tarjadas | 2 | 8 | 4 | "Para: Coordenação <coord.cras@prefeitura.gov.br>" |
| T3 | Nome de pessoa ou termo sensível dentro de nome de programa, serviço ou evento | 1 | 3 | 3 | "Comitê Estadual LGBTQIA+", "Núcleo de Hepatites/Aids" |
| T2 | Município em caixa alta com forma de nome de pessoa "Prenome + de/da + Nome", lido como nome (a grafia em caixa normal ficou legível) | 1 | 2 | 2 | "CONSELHO TUTELAR DE APARECIDA DO NORTE" |
| T5 | Número de precedente judicial público lido como protocolo pessoal | 0 | 1 | 1 | "nos termos do RE nº 999.111/SP" |
| T6 | Valor médio ou agregado lido como valor pessoal, apesar de "valor médio" | 0 | 1 | 1 | "pensões com valor médio de R$ 1.870,00" |
| **Total** | | **10** | **24** | | |

Tarjas fora do gabarito que não atingem trecho público (rodada 1 / final: 10 / 15), sem contar as
que coincidem com públicos acima:

* T7a — termo genérico de saúde, gênero ou raça em frase normativa, rótulo ou classificação ("o uso
  do nome social é assegurado…", "acolhimento de pessoas trans", "situação de vulnerabilidade",
  rótulo "Cor/raça declarada", nome legal de benefício, linha de assunto): 5 / 7;
* T7b — expressões comuns sem conteúdo pessoal marcadas como saúde ("Faz três semanas", "Em
  entrevista", "roda de conversa", "al médico", "e que perdeu", fala sobre comportamento escolar):
  4 / 6;
* T7c — homônimo: "internação" no sentido de medida socioeducativa tratada como internação
  hospitalar: 0 / 1;
* T7d — município de residência ("mora em Planaltina de Goiás") tarjado como endereço: 1 / 1.

Formas que **não** provocaram tarja indevida e podem ser retiradas de sondagens futuras: municípios em
caixa alta com nome de pessoa diferente de prenome comum (João Pessoa, Teófilo Otoni, Presidente
Kennedy, Marechal Deodoro, Senador Guiomard, Paulo Afonso), "Patrulha Maria da Penha", "Lei Berenice
Piana", estação e escolas com nome de pessoa, valor normativo de categoria ("auxílio-alimentação …
fixado para toda a categoria"), "três quartos do salário mínimo" em citação da LEP.

## Leitura

Todos os 30 documentos vazaram ao menos uma entidade. A fragilidade concentra-se onde o dado não
tem forma própria: sensíveis não clínicos e saúde descritos por perífrase em documentos sem campos de
identificação, valores por extenso, idades e nomes curtos. Identificadores com formato (CPF, NIS, CNS,
telefone, e-mail pessoal, registro profissional, processo CNJ) tiveram recall 1,00. Do lado da
precisão, o erro é sistemático em duas formas: e-mail de setor em cabeçalho e estatística agregada que
contém termo de violência, gestação ou deficiência.

Limitações: anotação apenas do redator (sem anotação cega nem adjudicação); classes atribuídas por
tabela explícita em `geracao/classificar_erros.py`; contagens são de entidades por valor, como no
arquivo de erros do avaliador.

## Reprodução

```
cd C:/Sistemas/themis-treino/c3-adversarial
PY=C:/Sistemas/themis-lgpd/.venv/Scripts/python.exe
$PY benchmark/adversarial/processo/lote_R3/geracao/montar.py benchmark/adversarial/processo/lote_R3/anotacao_redator.jsonl \
    benchmark/adversarial/processo/lote_R3/geracao/fontes_r1.txt benchmark/adversarial/processo/lote_R3/geracao/fontes_r2.txt
$PY benchmark/ouro/ferramentas.py validar benchmark/adversarial/processo/lote_R3/anotacao_redator.jsonl
PYTHONPATH=src PYTHONIOENCODING=utf-8 $PY benchmark/avaliar_ouro.py benchmark/adversarial/processo/lote_R3/anotacao_redator.jsonl \
    --erros .trabalho/erros_R3_final.jsonl --json .trabalho/metricas_R3_final.json
$PY benchmark/adversarial/processo/lote_R3/geracao/classificar_erros.py .trabalho/erros_R3_final.jsonl
```
