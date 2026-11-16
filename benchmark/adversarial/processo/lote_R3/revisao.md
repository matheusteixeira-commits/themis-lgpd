# Lote R3 — revisão independente da anotação

Tema: dados sensíveis e vulnerabilidade fora do registro clínico (assistência social, conselhos
tutelares e de direitos, execução penal, medidas socioeducativas, escolas, ouvidorias, folha e
previdência de servidores). São 30 documentos, um ou dois por UF, cobrindo as 27 UFs.

* Anotação do redator: `processo/lote_R3/anotacao_redator.jsonl` (não foi alterada)
* Anotação final: `lotes/lote_R3.jsonl`, `ferramentas.py validar` → **sem problemas**

## Método

1. Li `DIRETRIZES.md` inteiro, inclusive as convenções de extensão.
2. Extraí só os textos (sem `entidades` e sem `publicos`) e anotei os 30 por conta própria, do começo
   ao fim, antes de abrir a anotação do redator.
3. Comparei as duas anotações documento a documento e decidi cada divergência pelas diretrizes. As
   alterações foram aplicadas por script, uma a uma, sobre o arquivo do redator. Depois disso,
   verifiquei por posição no texto que nenhum trecho público se sobrepõe a um dado pessoal.

Não executei o sistema nem o avaliador. Não li `sondagem.md`, `.trabalho/`, `geracao/` nem os lotes
dos outros redatores.

## Concordância (redator × final, `ferramentas.py concordancia`)

| Medida | Valor |
|---|---:|
| F1 por valor e rótulo | **0,8836** |
| F1 só por valor | 0,8836 |
| Documentos com alguma divergência (entidades ou públicos) | 29 de 30 |
| Entidades: redator → final | 559 → 566 |
| Trechos públicos: redator → final | 377 → 405 |

Os dois F1 são iguais porque **nenhuma divergência foi só de rótulo**. Todas foram de extensão, de
inclusão ou de remoção, como nos lotes A e B. Um documento (R3-001) ficou idêntico. Os outros 29
têm ao menos uma divergência de entidade.

## Alterações

| Tipo | Total | DADO_SAUDE | DADO_SENSIVEL | Demais rótulos |
|---|---:|---:|---:|---:|
| Extensão corrigida | 55 | 38 | 17 | 0 |
| Entidade incluída | 14 | 12 | 2 | 0 |
| Entidade removida | 7 | 7 | 0 | 0 |
| Rótulo corrigido | 0 | — | — | — |
| Público incluído | 29 | | | |
| Público removido | 1 | | | |

Entidades finais por rótulo: NOME_PESSOA 187, DADO_SAUDE 134, DADO_FINANCEIRO 66, DADO_SENSIVEL 54,
ID_PROCESSUAL 33, DATA_NASC 32, DOC_PROFISSIONAL 23, CONTATO 15, ENDERECO 11, QUASI_IDENTIFICADOR 7,
DOC_PESSOAL 4.

Nomes, documentos, contatos, endereços, idades, valores, números de procedimento e registros
profissionais coincidiram integralmente com a minha anotação cega. Toda divergência ficou em saúde e
em dados sensíveis, que são justamente o foco do lote.

## Regras aplicadas

**1. Verbo de ligação, de uso ou de estado fica fora** (convenção 3). Em saúde:
"tem paralisia cerebral" → "paralisia cerebral". Pelo mesmo critério:

* "faz fisioterapia…", "usa órtese…", "está grávida", "com microcefalia", "tem asma";
* "faz tratamento de câncer de mama" e "faz tratamento para HIV";
* "em tratamento antirretroviral regular", "em tratamento para tuberculose", "em uso de PrEP desde
  março";
* "faz hemodiálise…", "está na fila do transplante…", "tomo remédio para dormir";
* "é usuário de pedra…", "teve um aborto espontâneo…", "tiene diarrea…".

Também saíram artigo e advérbio iniciais: "uma tentativa de suicídio…", "a cirurgia", "ainda não
fala frases completas", "ainda não controla os esfíncteres". O verbo ficou quando ele é o próprio
conteúdo, como em "não dorme", "bebe todos os dias…", "cheirava loló…", "fumava maconha…" e "se
morde no braço".

**2. Atributos da condição e posologia integram a expressão** (convenção 3):

* estado do tratamento: "uso de crack dos 15 aos 29 anos, interrompido desde a prisão" e "uso de
  pasta-base de cocaína desde os 17, interrompido desde a prisão";
* data: "perna direita amputada em decorrência do diabetes em março" e "tratamento para dependência
  de álcool desde março";
* duração e frequência: "hormonização há três anos", "Depakene todo dia" e "cheirava loló nos fins
  de semana".

Sintomas coordenados viraram entradas separadas: "cochilou em sala" e "tonturas antes do lanche".

**3. Medida com unidade sem a palavra-chave** (convenção 1): "com idade gestacional de 31 semanas" →
"31 semanas".

**4. Dado sensível: a expressão nominal inteira, sem o verbo** (convenções 6 e 3, por analogia).
Saíram verbos de frequência ou ligação:

* "frequenta a Igreja Pentecostal Chama Viva" → "Igreja Pentecostal Chama Viva", e da mesma forma
  com a Paróquia, a igreja pentecostal da aldeia e "congrega na Igreja Evangélica Assembleia de
  Deus";
* "pertence ao povo Kaiowá" → "povo Kaiowá";
* "é ñandesy…", "é militante do MST" e "se reconhece como quilombola", alinhado ao que o redator já
  fizera em "se autodeclara parda" → "parda";
* "mantém relacionamento homoafetivo/afetivo…" e "mantém/mantinha relações sexuais…";
* "ter feito campanha para…", "desconto da mensalidade do sindicato…" e "ela já se relacionou com
  mulheres".

Ficaram dentro do valor os qualificadores nominais ou participiais que são o próprio dado, no
modelo de "filiado ao Sindicato…" e "membro da Igreja Y": "filiado ao Sindserv", "iniciada no
candomblé…", "delegada sindical do Sinpro-DF", "pastor da Igreja…" e "pré-candidata a vereadora…".
"se identifica como menina" ficou inteiro porque o verbo é o conteúdo da identidade de gênero.

**5. Agressão sofrida não é DADO_SAUDE. A lesão resultante é.** Foram removidos seis relatos de
agressão e uma qualificação jurídica que o redator rotulou como saúde:

* "quebra as coisas e a ameaça" e "violência doméstica física e psicológica";
* "ser agredida pelo companheiro";
* "foi espancado pelo padrasto";
* "apertou seu pescoço até ela quase desmaiar" e "levou três socos no rosto";
* "jogou uma panela de água quente no braço dela".

Nenhum deles é doença, diagnóstico, achado, tratamento ou exame. Ficaram anotadas as lesões ("marcas
roxas no braço esquerdo", "fratura dos ossos próprios do nariz") e foi incluída a do R3-019 ("cicatriz,
ainda avermelhada, do cotovelo ao punho").

A violência sexual continuou como DADO_SENSIVEL por se referir à vida sexual: "relações sexuais com…"
e "estupro de vulnerável".

**6. Exame pedido ou aguardado para pessoa identificada entra**, coerente com "avaliação
oftalmológica" (R3-023), que o redator já anotara. Foram incluídas "avaliação com fonoaudiólogo",
"avaliação fonoaudiológica" e "avaliação psiquiátrica".

**7. Outras inclusões de saúde (sintomas e achados):**

* R3-002: "tapa os ouvidos" e "sai correndo para o pátio", coordenados a "se morde no braço", que já
  estava anotado; "fica meio parado", efeito do remédio;
* R3-017: "qualquer dia eu acabo com tudo", ideação suicida;
* R3-023: "aperta os olhos para ler" e "se aproxima muito do caderno";
* R3-026: "muy flaquita".

**8. Instituição cujo nome revela a crença da pessoa não é público.** "Centro Espírita Caminho da
Luz" (R3-028) saiu de `publicos` e virou DADO_SENSIVEL, como "Igreja Y" em "membro da Igreja Y".
Também foi incluído "parceiro fixo" (R3-027) como DADO_SENSIVEL (vida sexual).

**9. Públicos por unidade** (convenção 9). Foram incluídos:

* cargos sem nome: "Juíza de Direito", "Juiz de Direito", "Promotora de Justiça", "Defensora
  Pública", "Defensor Público", "Orientadora Educacional" e "secretária executiva";
* órgãos e cadastros: "Ministério Público", "INSS", "SINAN", "Cadastro Único", "Banco do Brasil",
  "Caixa" e "SEE/SUGEP/DIAP";
* datas de atos: a data da audiência, as datas de visita e a data de acionamento do Conselho;
* municípios, UFs e programas: "Guarapari", "Acre", "Bolsa Família" e "Semana Municipal de
  Enfrentamento ao Feminicídio".

Foram mantidos os compostos do redator com partes que não estão na lista, como "art. 29 da Lei nº
7.210/1984" e "412 manifestações sobre saúde mental".

## Decisões mantidas do redator (registradas por serem discutíveis)

* **CRESS e CRP com sigla e região** ("CRESS 1ª Região nº 7.415", "CRP 10/04821") e matrícula só com
  o número: o padrão foi seguido de forma consistente nos 30 documentos, no modelo de "OAB/PE
  12.345".
* **Código familiar do Cadastro Único** (R3-003) e **matrícula SIAPEN de custodiada** (R3-022) como
  ID_PROCESSUAL, porque são registros sobre pessoa ou família (convenção 8), não documentos
  pessoais. A matrícula escolar (R3-002) e a FICAI (R3-006) também ficaram como ID_PROCESSUAL.
* **Números de ofício e de despacho decisório** ficaram públicos ("Ofício nº 37/2025", "Ofício nº
  412/2025-CT", "DESPACHO DECISÓRIO Nº 88/2025"), porque são atos oficiais. O número do comunicado à
  família (R3-023), dirigido a uma só estudante, ficou como ID_PROCESSUAL.
* **Chave PIX que é um telefone** (R3-007): DADO_FINANCEIRO, o rótulo mais específico.
* **Valor da excursão em aberto** (R3-023, "R$ 85,00"): DADO_FINANCEIRO como valor devido pela
  família. O auxílio-alimentação fixado para a categoria (R3-014) ficou público.
* **Licença para tratamento de saúde** (R3-010 e R3-014): DADO_SAUDE, por enunciar o motivo. As
  durações ("30 dias", "60 dias") ficaram fora.
* "síndrome de Down com cardiopatia congênita operada aos 2 anos" ficou como uma só expressão, com a
  cardiopatia lida como característica do quadro. "especial" (R3-016, sentido de deficiência) e
  "consulta no CAPS" (R3-001) ficaram por preferência pelo dado pessoal.

## Casos duvidosos

* **Atos de violência (regra 5).** É a decisão de maior impacto: 7 das 7 remoções. Se a adjudicação
  futura preferir tratar agressões como dado de saúde, elas devem voltar com a extensão do redator.
* **Nacionalidade e língua** não foram anotadas: "venezuelana" (R3-026), "fala guarani em casa"
  (R3-020), "em português e crioulo" (R3-030). Nacionalidade não é origem racial ou étnica na
  tipologia. A etnia, quando explícita ("povo Warao", "povo Kaiowá"), está anotada.
* **Situação de rua e localização vaga** não foram anotadas como endereço nem como
  quase-identificador: "morando na rua, perto da rodoviária" (R3-013) e "acampamento no norte do
  estado" (R3-029).
* **Penas e medidas** não foram anotadas: "9 anos e 4 meses" e "liberdade assistida, prazo de seis
  meses" (R3-005 e R3-008). Antecedente penal não tem rótulo na tipologia.
* **"a família não sabe da orientação sexual dele"** (R3-027) foi mantido como DADO_SENSIVEL,
  embora o dado em si já esteja em "HSH".
* **E-mails funcionais nominais** ("nome.sobrenome@…gov.br") foram mantidos como CONTATO, porque
  identificam a pessoa natural. Os e-mails de unidade ficaram públicos.
