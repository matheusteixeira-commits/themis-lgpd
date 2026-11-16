# Lote C (saúde e perícia): revisão independente da anotação

Arquivo final: `lote_C.jsonl` (50 documentos, mesmo formato e mesmos textos de `anotacao_redator.jsonl`).
Validação: `ferramentas.py validar lote_C.jsonl` → **sem problemas**. Uma checagem complementar por
posição no texto confirmou que nenhum trecho público se sobrepõe a uma entidade pessoal e que nenhum
valor tem dois rótulos.

## Processo e independência

1. Leitura integral de `DIRETRIZES.md`, incluindo as convenções de extensão 1 a 9.
2. Leitura dos 50 textos de `textos.jsonl` do começo ao fim. Antes de abrir a anotação do redator,
   levantei por conta própria os dados pessoais de cada documento.
3. Comparação com `anotacao_redator.jsonl`, documento a documento, e adjudicação de cada divergência.
4. Releitura final de cada texto com as entidades e os trechos públicos marcados sobre ele, para achar
   omissões que ainda restassem.

Não li `C:/Sistemas/themis-lgpd`, `themis-treino/ouro`, as pastas dos outros lotes nem a subpasta
`lote_C/geracao`. Não executei nenhum sistema de anonimização. O Python do `.venv` serviu só como
interpretador de `ferramentas.py` e de scripts auxiliares de leitura e montagem.

## Concordância entre o redator e a anotação final

Resultado de `ferramentas.py concordancia anotacao_redator.jsonl lote_C.jsonl`:

| Medida | Valor |
|---|---:|
| Documentos | 50 |
| Documentos com divergência (entidades ou públicos) | 39 |
| F1 por rótulo (tipo + valor) | **0,9126** |
| F1 por valor (sem rótulo) | **0,9135** |

| Conjunto de entidades | Quantidade |
|---|---:|
| Comuns ao redator e à anotação final | 1.018 |
| Só no redator (removidas ou com extensão alterada) | 59 (58 `DADO_SAUDE`, 1 `DOC_PESSOAL`) |
| Só na anotação final (incluídas ou com nova extensão) | 136 (133 `DADO_SAUDE`, 3 `ID_PROCESSUAL`) |
| Precisão do redator em relação à anotação final | 0,945 |
| Revocação do redator em relação à anotação final | 0,882 |

Todas as divergências estão em `DADO_SAUDE`, salvo três números de documento ou de procedimento
(ver casos duvidosos 2 e 3). Nomes, documentos pessoais e profissionais, datas de nascimento
e idades, endereços, contatos, dados sensíveis, financeiros e o quase-identificador coincidem
integralmente com a anotação do redator.

## Contagem final

| Rótulo | Redator | Final |
|---|---:|---:|
| NOME_PESSOA | 152 | 152 |
| DADO_SAUDE | 658 | 733 |
| DOC_PROFISSIONAL | 70 | 70 |
| DATA_NASC | 63 | 63 |
| ID_PROCESSUAL | 44 | 47 |
| DOC_PESSOAL | 44 | 43 |
| DADO_SENSIVEL | 15 | 15 |
| ENDERECO | 13 | 13 |
| CONTATO | 12 | 12 |
| DADO_FINANCEIRO | 5 | 5 |
| QUASI_IDENTIFICADOR | 1 | 1 |
| **Total** | **1.077** | **1.154** |
| Trechos públicos | 633 | 635 |

Há 42 documentos com dado pessoal. Os 8 documentos sem dado pessoal (C-015 a C-018 e C-035 a C-038)
ficaram sem alteração.

## Alterações por tipo e por rótulo

As contagens abaixo são de operações de adjudicação, não de entidades.

| Tipo de alteração | Total | Por rótulo |
|---|---:|---|
| Inclusão | 84 | 82 `DADO_SAUDE`, 2 `ID_PROCESSUAL` |
| Remoção | 1 | 1 `DADO_SAUDE` |
| Extensão corrigida | 46 | 46 `DADO_SAUDE`: 33 ajustes simples, 10 fusões e 3 separações |
| Rótulo corrigido | 1 | `DOC_PESSOAL` → `ID_PROCESSUAL` |
| Trechos públicos incluídos | 7 | — |
| Trechos públicos removidos | 5 | 3 passaram a dado pessoal; 2 ficaram neutros |

Alterações por documento (inc = inclusão, rem = remoção, ext = extensão, fus = fusão, sep = separação,
rot = rótulo, pub± = trecho público):

| Doc. | Alterações | Doc. | Alterações |
|---|---|---|---|
| C-001 | ext 1, inc 4, pub− 1 | C-024 | sep 1, ext 1, inc 3 |
| C-002 | ext 1 | C-025 | inc 1, ext 2, fus 1 |
| C-003 | fus 1, ext 1 | C-026 | inc 3 |
| C-004 | inc 2 | C-027 | pub+ 2 |
| C-005 | inc 4, pub− 1 | C-028 | ext 1, pub− 1 |
| C-006 | inc 4 | C-029 | fus 1, inc 2 |
| C-007 | ext 2, inc 10 | C-031 | inc 5 |
| C-008 | inc 6 | C-032 | fus 1, ext 2, inc 1 |
| C-009 | ext 2, inc 3 | C-033 | inc 2 |
| C-010 | ext 2, inc 2 | C-034 | rot 1, ext 2, fus 1, inc 5 |
| C-011 | pub+ 2 | C-039 | inc 3 |
| C-012 | ext 2, fus 1, inc 2 | C-040 | sep 2, inc 1 |
| C-013 | fus 1, inc 2 | C-042 | ext 3, rem 1, inc 5, pub+ 2 |
| C-014 | inc 2 | C-043 | ext 1, inc 1, pub− 1 |
| C-019 | ext 1 | C-044 | inc 1 |
| C-020 | ext 1 | C-045 | inc 2 |
| C-021 | pub− 1 | C-046 | ext 3, inc 1, pub+ 1 |
| C-022 | ext 1, inc 4 | C-048 | fus 1, ext 2 |
| C-023 | inc 1 | C-049 | ext 2 |
| — | — | C-050 | fus 2, inc 2 |

### Natureza das inclusões (84)

- **Relato do paciente ou do familiar entre aspas que descreve sintoma ou limitação** (14). Exemplos:
  queixa motora em C-008, sangramento gengival em C-010, visão turva em C-012, alucinação em C-024,
  dor no coto em C-026, dispneia em C-031, ideação em C-042 e desorientação em C-050. O valor entra sem
  as aspas.
- **Terapias e condutas aplicadas à pessoa** que não estavam anotadas. São condutas de fisioterapia
  (C-008, C-031), terapia fonoaudiológica (C-009), atividades terapêuticas de CAPS (C-005, C-024),
  acompanhamento especializado (C-001, C-006, C-013, C-040), terapia antirretroviral e enfaixamento das
  mamas (C-022), curativo (C-014), anestesia geral (C-033), oxigenoterapia (C-042), repouso vocal
  (C-044), manutenção periodontal (C-010) e revisão do encaixe da prótese (C-026).
- **Achados de exame e limitações funcionais**: incapacidade de marcha ou de agachamento (C-001,
  C-039), comandos de duas etapas (C-007), marcha supervisionada (C-008), comunicação (C-009, C-032),
  escadas e transferências (C-026, C-045), sonolência e nível de consciência (C-042), estabilidade
  clínica (C-024).
- **Exames e resultados**: cultura em andamento (C-004), creatinina e hemoglobina de alta (C-029),
  peso e Apgar do recém-nascido em documentos maternos (C-022, C-034), qualificadores de funções do
  corpo e de atividades e participação da avaliação do BPC (C-007, 7 linhas de tabela) e impedimento de
  longo prazo (C-007).
- **Agravo, condição ou medicamento**: agravo notificado (C-013), tipo de entrada "caso novo" (C-004),
  "Gestante" (C-012), trabalho de parto e ácido tranexâmico nas duas grafias (C-034), recusa de
  transfusão (C-014), "tratamento de saúde" (C-023), leito de saúde mental (C-042).
- **Licença, benefício ou incapacidade que enuncia motivo de saúde**: licença para tratamento da
  própria saúde e incapacidade para o cargo (C-006), benefício por incapacidade temporária (B31) (C-001),
  aposentadoria por incapacidade permanente (C-025), incapacidade total para a atividade habitual
  (C-039), supervisão contínua de terceiros (C-050).
- **ID_PROCESSUAL**: número de ofício da Defensoria sobre o usuário (C-005) e número de requisição do
  Conselho Tutelar sobre a adolescente (C-043). Os dois saíram de `publicos`.

### Remoção (1)

- C-042, "sem sintomas psicoticos": negação. A regra adotada pelo próprio redator não anota negações;
  em C-006 a mesma expressão só entra como parte da descrição do CID.

## Regras aplicadas na adjudicação

1. **Palavra-chave fora do valor** (conv. 1): em sinais vitais e medidas, a sigla ou o nome da medida
   sai do valor. "PA de 150 x 100 mmHg" passa a "150 x 100 mmHg"; o mesmo vale para FC, SatO2 e
   saturação (C-012, C-020, C-034, C-042, C-046). "idade gestacional de X" passa a "X" e "peso ao nascer
   de X" passa a "X" (C-012, C-049). Também saíram "quadro de" (C-002), "diagnóstico de" (C-007),
   "Lesões:" (C-048) e "iniciou" (C-022). Em exame laboratorial, o nome do exame continua no valor,
   porque exame e resultado formam uma expressão.
2. **Exame e resultado contíguos** formam uma só expressão (conv. 3): passaram a incluir o nome do exame
   a videofluoroscopia (C-009), a tonometria (C-019) e a triagem auditiva neonatal (C-032).
3. **Condição com seus atributos** é uma só expressão (conv. 3). Entram no valor o estado do tratamento,
   a duração, as datas e a cadeia causal. Exemplos: diabetes "sem adesão regular ao tratamento"
   (C-003), HAS "sem controle, não toma a medicação direito" (C-046), tremor como "efeito colateral dos
   medicamentos" (C-024), incapacidade "em razão de neoplasia maligna" (C-025), histerectomia "por
   atonia uterina refratária" (C-034), "câncer de tireoide tratado em 2010" (C-028), duração da dor
   (C-001), data da última crise (C-007), decanulação (C-009), conclusão de tratamento (C-010, C-025).
4. **Posologia contígua integra o medicamento** (conv. 3): duração do antibiótico (C-003) e esquema da
   PQT-U (C-048).
5. **CID com descrição**, regra única aplicada em todo o lote e coerente com a regra declarada pelo
   redator. Código colado à descrição forma uma só expressão, na forma "F33.2 – descrição" ou
   "descrição (código)". Isso juntou em uma entrada o que estava separado em C-012, C-013, C-029,
   C-032, C-048 e C-050. Código separado da descrição pela palavra "CID" ou isolado em lista com ";"
   fica em entrada própria. Isso separou C-024 e C-040, onde o redator havia incluído "CID-10" e
   "CID-11" dentro do valor.
6. **Achados coordenados** ("com X, Y e Z" após uma condição) continuam como entradas separadas, como o
   redator fez em C-008 e C-009 (conv. 3, achados e sintomas coordenados).
7. **Negações** não são anotadas. **Resultado normal de exame nomeado** feito na pessoa é anotado, como
   VDRL, G6PD, teste do pezinho e campo visual. **Achado normal genérico do exame físico ou psíquico** não
   é anotado: "bom estado geral", "vígil, orientada", "ligamentos estáveis", "pupilas isocóricas",
   "afebril".
8. **Licença ou benefício que enuncia motivo de saúde** é `DADO_SAUDE` (conv. 3). Por analogia com a
   licença, o mesmo vale para o benefício por incapacidade temporária (B31) e para a aposentadoria por
   incapacidade permanente. A simples duração de afastamento ou de licença continua fora.
9. **Número de procedimento ou documento sobre pessoa** é `ID_PROCESSUAL` (conv. 8). Isso inclui o
   ofício e a requisição que tratam de uma pessoa determinada e o número da Declaração de Óbito.
10. **Trechos públicos por unidade** (conv. 9). Incluí município e data de assinatura que faltavam
    (C-011, C-027, C-046) e as siglas SINAN e SAMU (C-042). Retirei de `publicos` destinos genéricos de
    encaminhamento da própria pessoa ("ambulatório de cirurgia bucomaxilofacial" em C-021) e a
    especialidade solicitada para ela ("Cirurgia de Cabeça e Pescoço" em C-028), porque revelam
    necessidade de saúde da pessoa e não devem ser tratados como trecho que obrigatoriamente fica
    legível. Esses dois trechos ficaram neutros, nem públicos nem anotados. Foram mantidas as armadilhas
    do redator: nomes de pessoa em nomes de instituição, termos sensíveis em uso genérico (C-036,
    C-037), doenças e sorotipos em boletins, empregador pessoa jurídica (C-041), endereços de unidades
    públicas e valores de edital.

## Casos duvidosos registrados

1. **Benefício B31 e aposentadoria por incapacidade** (C-001, C-025). O redator listava "Benefício por
   incapacidade temporária" como público. Passou a `DADO_SAUDE` por analogia com a licença que enuncia
   motivo de saúde (conv. 3) e pela regra "na dúvida entre pessoal e público, prefira pessoal". O
   "Benefício de Prestação Continuada" (C-007) ficou público, porque o nome do programa não enuncia
   condição.
2. **Ofício (C-005) e requisição do Conselho Tutelar (C-043)**. O redator tratava os dois como número
   de ato oficial público. Passaram a `ID_PROCESSUAL` porque tratam de uma pessoa determinada. A conv. 8
   reserva o tratamento público a documentos sobre coletividade.
3. **Declaração de Óbito (C-034)**: `DOC_PESSOAL` → `ID_PROCESSUAL`. A DO não é certidão de registro
   civil; é um registro sobre a pessoa, o que a conv. 8 enquadra como `ID_PROCESSUAL`. É o único caso de
   divergência só de rótulo.
4. **Qualificadores da avaliação do BPC (C-007)**. Anotei as linhas de funções do corpo e as de
   atividades e participação (vida doméstica, relações interpessoais, vida comunitária). Não anotei os
   fatores ambientais (produtos e tecnologia, habitabilidade, apoio, atitudes, serviços), que descrevem
   barreiras do ambiente e não a saúde da pessoa.
5. **Relatos entre aspas** passaram a `DADO_SAUDE` quando descrevem sintoma ou limitação. Não entraram
   os relatos sem conteúdo de saúde: "fica em paz" (C-024), "a casa ficou mais calma" (C-043), a
   justificativa de faltas (C-034) e o alarme do processador (C-032). Em C-028 ficou a forma do
   redator, com as aspas, porque o valor inclui o atributo temporal.
6. **Títulos de ficha ou relatório que nomeiam o agravo** ("TUBERCULOSE", "VIOLÊNCIA
   INTERPESSOAL/AUTOPROVOCADA", "CASO DE HANSENÍASE EM MENOR DE 15 ANOS", "ACIDENTE DE TRABALHO") não
   foram anotados nem listados como públicos. São nome de formulário; o agravo da pessoa está anotado
   no corpo do documento.
7. **C-021**. "namorado" não foi anotado como `DADO_SENSIVEL`: a orientação sexual já está anotada no
   campo próprio, e anotar a palavra dependeria de inferência. Tipo e meio de agressão ("física",
   "força corporal/espancamento") continuam `DADO_SAUDE`, como agravo notificado; a outra leitura
   possível é não anotá-los. "homem cisgênero" e a motivação "homofobia/…" continuam `DADO_SENSIVEL`.
8. **Encaminhamentos a serviços** ("ambulatório de pé diabético", "reabilitação cardiovascular",
   "infectologia pediátrica", "ambulatório de seguimento do prematuro") não foram anotados. A condição
   que motiva o encaminhamento já está anotada. Unidades com nome próprio de instituição continuam
   públicas.
9. **Datas clínicas** (DUM, internação, alta, óbito, início da doença ou da incapacidade) não são
   anotadas isoladamente, como fez o redator. Entram só quando fazem parte da expressão de saúde, como
   data do diagnóstico, do procedimento ou do exame.
10. **Dados do recém-nascido em documento materno** (C-022, C-034). Peso e Apgar foram anotados porque o
    recém-nascido é identificável como filho da paciente.
11. **Curatela e curadora** (C-024, C-050) não foram anotadas: são situação jurídica, não dado de
    saúde. As limitações que a fundamentam estão anotadas.
12. **"Bolsa Família"** (C-007, C-026) ficou neutro, nem público nem anotado. O valor recebido é
    `DADO_FINANCEIRO` e o tipo de benefício fica fora (conv. 7).
13. **Achados coordenados versus expressão única**. Mantive a separação do redator em listas introduzidas
    por "com", como disfagia com seus sinais (C-009) e hemiparesia com espasticidade (C-008). A outra
    leitura possível da conv. 3 juntaria tudo como atributos de uma única condição.

## Avaliação da anotação do redator

A anotação do redator é exaustiva e correta nos identificadores diretos. Os rótulos que não são
`DADO_SAUDE` coincidem integralmente com a anotação final, salvo os três números de procedimento ou
documento discutidos acima. As armadilhas de `publicos` estão bem construídas e sem sobreposição.

As omissões estão concentradas em `DADO_SAUDE`: relatos entre aspas, condutas terapêuticas descritas
em lista e achados funcionais. As correções de extensão vêm da aplicação desigual das convenções 1
(palavra-chave) e 3 (atributos, exame com resultado, CID com descrição). Quase todas as alterações
ampliam a cobertura: só uma entidade foi removida.
