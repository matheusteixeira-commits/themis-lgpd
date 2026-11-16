# Lote D — revisão independente da anotação

Tema: gestão de pessoas e processo disciplinar. 50 documentos (D-001 a D-050), 44 com dados pessoais e 6 sem
(D-045 a D-050). A revisão define a anotação final, gravada em `lote_D.jsonl` (mesmo formato de
`anotacao_redator.jsonl`).

## Procedimento

1. Leitura integral de `DIRETRIZES.md`, inclusive as "Convenções de extensão" (1 a 9).
2. Leitura dos 50 textos de `textos.jsonl`, do começo ao fim, com registro próprio de cada dado pessoal antes de
   abrir a anotação do redator.
3. Comparação, documento por documento, com `anotacao_redator.jsonl`, seguida de duas verificações automáticas:
   (a) números e palavras iniciadas por maiúscula que não estão cobertos por entidade nem por trecho público;
   (b) valores curtos ou repetidos, sobreposição entre entidades e sobreposição entre entidade e trecho público.
   Nenhum caso pendente apareceu nessas verificações.
4. Correções aplicadas sobre a anotação do redator. Validação e concordância medidas com `ferramentas.py`.

Fontes consultadas: apenas `DIRETRIZES.md`, `ferramentas.py`, `textos.jsonl` e `anotacao_redator.jsonl`. Não foram lidos
o código do sistema, o conjunto de referência, as pastas de outros lotes nem os programas de geração
(`lote_D/geracao/`), e nenhum sistema de anonimização foi executado.

## Concordância entre o redator e a anotação final

`python ferramentas.py concordancia anotacao_redator.jsonl lote_D.jsonl`

| Medida | Valor |
|---|---:|
| Documentos | 50 |
| Documentos com divergência (entidades ou públicos) | 7 |
| F1 por rótulo | 0,9962 |
| F1 por valor | 0,9962 |

Os dois F1 são iguais porque nenhuma divergência foi só de rótulo. As divergências são três inclusões, uma
correção de extensão e ajustes em `publicos`.

## Contagens

| Rótulo | Redator | Final | Diferença |
|---|---:|---:|---:|
| NOME_PESSOA | 235 | 235 | 0 |
| DOC_PROFISSIONAL | 114 | 114 | 0 |
| ID_PROCESSUAL | 72 | 73 | +1 |
| DADO_FINANCEIRO | 70 | 70 | 0 |
| DADO_SAUDE | 56 | 57 | +1 |
| DOC_PESSOAL | 53 | 53 | 0 |
| DATA_NASC | 27 | 27 | 0 |
| ENDERECO | 13 | 13 | 0 |
| DADO_SENSIVEL | 9 | 10 | +1 |
| CONTATO | 7 | 7 | 0 |
| ID_VEICULO | 5 | 5 | 0 |
| QUASI_IDENTIFICADOR | 2 | 2 | 0 |
| **Total de entidades** | **663** | **666** | **+3** |
| Trechos públicos | 870 | 873 | +3 |

### Alterações por tipo e por rótulo

| Tipo | Quantidade | Rótulos |
|---|---:|---|
| Entidade incluída | 3 | ID_PROCESSUAL 1, DADO_SAUDE 1, DADO_SENSIVEL 1 |
| Entidade removida | 0 | — |
| Extensão corrigida | 1 | DADO_SAUDE 1 |
| Rótulo corrigido | 0 | — |
| Trecho público incluído | 8 | — |
| Trecho público removido | 5 | — |

## Alterações, documento por documento

| Doc. | Alteração | Regra |
|---|---|---|
| D-009 | Incluído ID_PROCESSUAL "7.341/2025 – JMO/GESP" (número do parecer médico-pericial da Junta Médica Oficial) e retirado de `publicos` o trecho "PARECER MÉDICO-PERICIAL Nº 7.341/2025 – JMO/GESP". | Conv. 8: o parecer da junta é laudo sobre a pessoa periciada. Aplica também a regra do próprio redator (dúvida 4), que trata como ID_PROCESSUAL os laudos de D-023, D-032, D-037 e D-043. A extensão segue o padrão "017/2025 – CPPAD/SESPA" (D-014). |
| D-009 | Público "Gerência de Saúde e Prevenção – Junta Médica Oficial" dividido em "Gerência de Saúde e Prevenção" e "Junta Médica Oficial". | Conv. 9: um trecho público por unidade. |
| D-018 | Público "COMISSÃO ORGANIZADORA DO CONCURSO PÚBLICO – EDITAL Nº 01/2024" dividido nas duas unidades. | Conv. 9. |
| D-024 | Incluído DADO_SENSIVEL "mensalidade sindical", da frase em que a requerente pede a exclusão do desconto de mensalidade sindical. | Conv. 6 e rótulo DADO_SENSIVEL (filiação sindical ligada à pessoa). O desconto na folha da requerente revela a filiação, como a rubrica "Mensalidade sindical – SINTE/SC" da tabela, que o redator já anotou. Como a comparação diferencia maiúsculas de minúsculas, o valor da tabela não cobre esta ocorrência. |
| D-030 | DADO_SAUDE "transtorno de ansiedade generalizada" estendido para "tratamento de transtorno de ansiedade generalizada". | Conv. 3: o estado do tratamento faz parte da expressão. Uniformiza com D-021 ("tratamento de hemodiálise…") e D-023 ("tratamento de leucemia linfoblástica aguda"). |
| D-034 | Público "CONCURSO PÚBLICO – EDITAL Nº 001/2025" dividido em "CONCURSO PÚBLICO" e "EDITAL Nº 001/2025". | Conv. 9. |
| D-037 | "Programa de Atenção à Saúde Mental do Servidor" passa de público a DADO_SAUDE. | O trecho registra o encaminhamento do servidor identificado ao programa para acompanhamento, ou seja, é tratamento ligado à pessoa. É o mesmo critério que levou o redator a incluir "Centro de Atenção Psicossocial – CAPS" no dado de saúde do mesmo documento, e o próprio ato manda publicar o extrato sem os dados de saúde. Na dúvida entre pessoal e público, prevaleceu o pessoal. |
| D-038 | Incluídos os públicos "BANPARA" e "CAIXA". | Conv. 7: o nome do banco fica fora da entidade e é público, como nos demais documentos do lote. |

## Regras aplicadas (resumo)

* **Palavras-chave fora do valor (conv. 1):** CPF, RG, CRM-UF, OAB/UF, COREN-UF, MASP, SIAPE, "matrícula", "CEP",
  "agência", "conta", "nascida em", "Dr./Dra.". Os sufixos que fazem parte do número ficam no valor: "-ENF"/"-TE" do COREN,
  "/01" do vínculo, "A" da matrícula do Amazonas, "/3" do RF.
* **Nomes (conv. 2):** cada grafia é uma entrada: prenome isolado ("Samir", "Miriam", "Jamile"), formas abreviadas
  ("Ana P. S. Torres", "SUELEN A. F. DA COSTA"), iniciais ("M. E. S. C."), forma invertida ("CARVALHO, Rosilene B."),
  apelido ("Wandinho"), variantes com erro (JOSIVALDO/JOSEVALDO, BENEDETTI/BENEDETE) e quebras de linha copiadas com `\n`.
  Etnônimos usados como sobrenome são NOME_PESSOA, não DADO_SENSIVEL.
* **Saúde (conv. 3):** uma condição com seus atributos é uma só expressão ("hérnia de disco lombar L4-L5 com
  radiculopatia à esquerda"). O CID é entrada separada da condição. Sintomas e medicamentos coordenados são entradas
  separadas, e a posologia integra o medicamento. A lista de restrições governada por um único núcleo é uma expressão
  (D-043). A licença que enuncia motivo de saúde é DADO_SAUDE ("licença para tratamento de saúde", "LTS",
  "LICENÇA POR MOTIVO DE DOENÇA EM PESSOA DA FAMÍLIA"). A duração do afastamento não é anotada.
* **Endereço (conv. 4):** do logradouro ao complemento, com quadra, lote, casa, bloco e conjunto habitacional. Ficam
  fora o bairro e o município. O CEP é anotado sem a palavra "CEP". Imóvel rural ou lote do declarante é ENDERECO.
  Endereço de órgão público é público.
* **Quase-identificador (conv. 5):** sem artigo inicial ("única professora surda lotada na Escola Municipal…").
* **Dado sensível (conv. 6):** a expressão inteira, com a sigla do sindicato ou do partido em aposição.
* **Valores (conv. 7):** valores recebidos ou devidos por pessoa natural, inclusive com a forma por extenso
  contígua, o percentual de pensão alimentícia e os valores patrimoniais sem "R$", são DADO_FINANCEIRO. São públicos o
  faturamento de pessoa jurídica (D-013), o prejuízo agregado ao erário (D-030) e as remunerações e taxas de edital
  (D-046, D-049).
* **Procedimentos (conv. 8):** são ID_PROCESSUAL os processos sobre ato de pessoa determinada, os PAD, as
  sindicâncias, as ações judiciais, os laudos, os protocolos de ouvidoria, o boletim de ocorrência, a CAT e os números de
  inscrição em concurso (registro sobre a pessoa). São públicos os processos do certame ou de coletividade (D-001,
  D-046), o relatório de auditoria geral (D-027) e os números de atos oficiais (portaria, despacho, decisão,
  resolução, termo de posse, título de nomeação).
* **Públicos (conv. 9):** um trecho por unidade, sem sobreposição com valor pessoal. As armadilhas do redator ficam
  mantidas: "60 (sessenta) anos" (D-018, D-049), "80 anos" (D-050), "transtorno do espectro autista", "pessoas com
  deficiência" e "Classificação Internacional de Doenças" (D-045, D-046), além dos nomes de pessoa dentro de nome de
  hospital, escola, logradouro público, palácio e lei.

## Dúvidas do redator: decisão

As dez decisões apontadas pelo redator foram verificadas no texto e mantidas, com duas ressalvas. A primeira é o
D-009: a regra de laudo da dúvida 4 não tinha sido aplicada ao parecer médico-pericial. A segunda é o D-037, em que o
programa de saúde mental passou a dado de saúde pelo mesmo critério usado para o CAPS. Em particular, foram
confirmadas:

* a anotação de "pessoa com deficiência" após "vaga reservada a" (D-001);
* a expressão única para cada condição de D-017, D-034 e D-043;
* a inclusão do verbo em "necessita de assistência permanente…" (D-033), porque o verbo é o próprio conteúdo;
* a menção genérica à licença por doença em pessoa da família, em D-014, sem rótulo;
* os rótulos dos dados sensíveis, inclusive a filiação passada (D-024) e a autodeclaração racial (D-034);
* o rótulo QUASI_IDENTIFICADOR em D-016 e D-031, com "surdez" anotada à parte;
* todas as armadilhas públicas.

## Casos duvidosos registrados

1. **Pareceres administrativos sobre uma só pessoa** (D-005, parecer de aposentadoria; D-028, parecer conclusivo de
   estágio probatório). Foram mantidos públicos como número de ato. Só o parecer médico-pericial (D-009) passou a
   ID_PROCESSUAL, por ser laudo. Se a adjudicação geral entender "relatório sobre pessoa" de forma ampla, esses dois
   números também passam a ID_PROCESSUAL.
2. **Atestado ou laudo de aptidão física e mental apresentado na posse** (D-019, D-042). Ficaram sem rótulo e fora de
   `publicos`. É uma exigência legal de toda posse e não revela nada específico da pessoa. Pela letra da conv. 3
   ("exame realizado na pessoa identificada entra mesmo sem resultado"), seria DADO_SAUDE.
3. **Títulos de seção de D-034** ("pessoas negras", "pessoas com deficiência"). Ficaram neutros: sem rótulo e fora de
   `publicos`. A autodeclaração e a condição de cada candidato estão anotadas.
4. **D-024, "mensalidade sindical"** (incluída) e **D-037, programa de saúde mental** (incluído). As duas inclusões
   seguiram a regra "na dúvida, prefira pessoal".
5. **D-036, "lotação em município sede de serviço de alta complexidade"**. É uma recomendação pericial decorrente da
   doença. Ficou sem rótulo, porque o dado de saúde ("tratamento oncológico") está anotado ao lado. Não se confunde com
   as restrições funcionais de D-009 e D-043, que descrevem limitações da pessoa.
6. **D-009, nexo causal "relacionado a evento ocorrido em serviço"**. Ficou fora da expressão de saúde, porque o CID
   separa a condição do nexo e o evento não é dado de saúde em si.
7. **D-013, "acompanhamento psiquiátrico" sem a data de início ("em março de 2023")**. Mantida a extensão do redator.
8. **Municípios de endereço residencial listados como públicos** (Natal, Rio de Janeiro, Salvador, Maceió, Macapá,
   BELEM). O mesmo nome aparece no fecho do ato, em contexto institucional, e a conv. 4 deixa o município fora do
   ENDERECO. A lista foi mantida.
9. **D-027, "Gerente Regional de Araguaína"**. Cargo único da servidora acusada, mantido público como cargo sem nome.
   Com o nome tarjado, o cargo identifica a pessoa e poderia ser um alerta de QUASI_IDENTIFICADOR.
10. **D-001 × D-041**. O processo de nomeação dos aprovados no certame (D-001) ficou público, e o processo das licenças
    de três servidores nomeados (D-041) ficou como ID_PROCESSUAL, conforme a regra do redator (certame ou coletividade
    × ato de pessoas determinadas).

## Validação

* `python ferramentas.py validar lote_D/lote_D.jsonl` → `sem problemas`.
* `python ferramentas.py validar lote_D/anotacao_redator.jsonl` → `sem problemas`.
* O texto de cada documento do arquivo final é idêntico ao de `textos.jsonl`.
