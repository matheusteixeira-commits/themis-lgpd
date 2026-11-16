# Lote R1: revisão independente da anotação

Tema do lote: forma e estrutura difíceis. São 30 documentos de 27 UFs, entre eles tabelas com colunas
intercaladas, texto em duas colunas, quebra de página no meio de nome, ruído de OCR, texto sem
pontuação, formulário com rótulos separados dos valores, CSV e letras espaçadas.

Arquivo final: `benchmark/adversarial/lotes/lote_R1.jsonl`. Os textos (`id`, `genero`, `uf` e `texto`)
são idênticos aos do redator. `ferramentas.py validar` retorna "sem problemas". Também conferi por
programa que nenhum trecho público se sobrepõe a uma ocorrência de dado pessoal.

## Como a revisão foi feita

1. Li as diretrizes por inteiro, inclusive as convenções de extensão.
2. Extraí só os textos do arquivo do redator e anotei os 30 documentos sem ver as entidades nem os
   públicos dele. Essa é a anotação cega.
3. Medi a concordância com `ferramentas.py concordancia` e decidi cada divergência pelas diretrizes.
   Em várias divergências fiquei com a versão do redator.

Não li `sondagem.md`, `.trabalho/` nem `processo/lote_R1/geracao/`, porque os scripts de geração
contêm a marcação do redator. Também não executei o sistema nem o avaliador.

## Concordância

| Comparação | Documentos com divergência | F1 por rótulo | F1 por valor |
|---|---:|---:|---:|
| Redator × anotação cega (antes da adjudicação) | 30 | 0,9741 | 0,9741 |
| Redator × anotação final | 30 | 0,9787 | 0,9787 |

Os 30 documentos aparecem como divergentes porque a ferramenta também compara os públicos. Nas
entidades, só 10 documentos divergem entre o redator e a versão final. Nenhuma divergência foi só de
rótulo, por isso os dois F1 são iguais.

| | Redator | Final |
|---|---:|---:|
| Entidades | 860 | 879 |
| Trechos públicos | 426 | 537 |

Entidades finais por rótulo:

| Rótulo | Quantidade |
|---|---:|
| NOME_PESSOA | 332 |
| DADO_FINANCEIRO | 117 |
| DOC_PESSOAL | 113 |
| DOC_PROFISSIONAL | 85 |
| ID_PROCESSUAL | 71 |
| DATA_NASC | 51 |
| DADO_SAUDE | 50 |
| ENDERECO | 24 |
| CONTATO | 21 |
| ID_VEICULO | 12 |
| DADO_SENSIVEL | 3 |

## Alterações em relação ao redator

| Tipo | Total | Por rótulo |
|---|---:|---|
| Entidade incluída | 21 | ID_PROCESSUAL 16, DADO_SAUDE 5 |
| Entidade removida | 0 | — |
| Extensão corrigida | 7 | DADO_SAUDE 4, NOME_PESSOA 2, DATA_NASC 1 |
| Rótulo corrigido | 0 | — |
| Público incluído | 139 | — |
| Público removido | 28 | 16 passaram a entidade, 8 compostos trocados por unidades, 4 sem palavra-chave |

### Entidades incluídas

- **R1-021 (ID_PROCESSUAL, 16):** os números de nota de empenho e de ordem bancária de cada diária
  (`2024NE…` e `2024OB…`). O redator os listou como públicos. Cada um registra um pagamento feito a um
  servidor identificado e permite chegar a ele no sistema financeiro. Por isso apliquei a convenção 8
  (registro sobre pessoa) e a regra "na dúvida, prefira pessoal".
- **R1-010 (DADO_SAUDE):** "EXAME TRAUMATOLÓGICO", requisitado no IML para a vítima. É exame na
  pessoa identificada e entra mesmo sem resultado (convenção 3).
- **R1-013 (DADO_SAUDE):** "prioridade amarela". É a classificação clínica de risco que a regulação
  deu à cirurgia do interessado.
- **R1-018 (DADO_SAUDE, 2):** as modalidades "PARATLETISMO" e "BASQUETE CR" (basquete em cadeira de
  rodas). Por definição, revelam a deficiência de atletas que têm nome, CPF e conta na mesma linha.
- **R1-020 (DADO_SAUDE):** "bom estado\ngeral", o estado clínico do paciente internado. É um achado
  e entra separado.

### Extensões corrigidas

- **R1-007:** "ACOMPANHAMENTO COM FONOAUDIOLOGIA DUAS VEZES POR SEMANA NO TURNO DA MANHA". O horário
  faz parte da posologia da terapia (convenção 3), como "à noite" na risperidona do R1-028.
- **R1-015:** "qua-\ndro de ansiedade, sem acompanhamento". O estado do tratamento é atributo da
  condição.
- **R1-020:** "segundo tempo cirúrgico", sem "aguardando". Usei o mesmo critério de "consulta corn
  hernatologista" no R1-001, onde o verbo também ficou fora.
- **R1-028:** "crises sensoriais com barulho intenso", sem o verbo "tem" (convenção 3).
- **R1-025:** "33 ANOS" em vez de "33". A idade escrita entra com a unidade, como "9 anos", "46 anos" e
  "vinte e sete anos" nos outros documentos.
- **R1-020 e R1-023 (NOME_PESSOA):** "FRANCISCO DE ASSIS\nMEDEIROS DANTAS" e "WANDERSON
  LUIZ\nZAMPROGNO" substituem os pares de fragmentos do redator. Nos dois casos o nome só é quebrado
  por uma quebra de linha, sem texto de outra coluna no meio. Pela convenção 2, a quebra é copiada no
  valor.

### Trechos públicos

- **Incluídos (139):**
  - cabeçalhos de órgãos e de documentos;
  - cargos sem nome;
  - artigos e normas separados por unidade;
  - datas de atos;
  - endereços e bairros de órgãos públicos;
  - siglas de órgãos expedidores (SSP/TO, SDS/PE, SSP RS, SSP AC);
  - programas (Bolsa Família, PAIF, BPC, Auxílio Natalidade);
  - municípios em contexto institucional;
  - os destinos das diárias do R1-021 (Patos, Sousa, Monteiro…), que não devem ser confundidos com
    sobrenomes.
- **Removidos (28):**
  - os 16 números de empenho e de ordem bancária, que passaram a entidade;
  - 8 compostos trocados por unidades (convenção 9), por exemplo "ART 117 DA LEI COMPLEMENTAR
    MUNICIPAL 90 DE 2012" → "ART 117" + "LEI COMPLEMENTAR MUNICIPAL 90 DE 2012";
  - 4 protocolos do R1-023 sem a palavra "Protocolo", como já estava no R1-011.

Códigos de unidade ficaram sem palavra-chave: "038712", "2495120" e "29774881".

### Decisões do redator mantidas sobre a anotação cega

- **R1-013:** "colecistectomia videolaparoscópica" e "colelitíase sintomática" ficam como entradas
  separadas. Procedimento e condição não formam uma cadeia causal. Também mantive "dois episódios de
  cólica biliar com atendimento no pronto-socorro", porque o atendimento é atributo dos episódios.
- **R1-020:** "internado" é DADO_SAUDE e "Clínica Ortopédica" é público. "acidente motociclístico"
  ficou fora: é evento, não condição, assim como a queda do R1-010 e a garrafada do R1-025.
- **R1-028:** "AEE" é público. O atendimento educacional especializado é serviço educacional, não
  tratamento de saúde, e o TEA já está anotado.
- **Públicos aceitos:**
  - "CAPS II", "CER II de Parnaíba" e "Penitenciária\nMista de Parnaíba" (R1-015);
  - o código verificador e o CRC do SEI (R1-013);
  - os lotes de vacina (R1-022);
  - "AOE"/"ASE" e "DIRETORIA DE ENSINO – REGIÃO DE SOROCABA" (R1-016);
  - "Defensora Pública" + "Núcleo Seccional de Mossoró" (R1-020);
  - "ARAGUATINS", "MUNICIPIO DE CASCAVEL" e "ES".

## Regras aplicadas

- **Nome partido por colunas de tabela ou por texto em duas colunas:** quando outro conteúdo fica
  entre as partes, cada parte é uma entrada NOME_PESSOA. Exemplos: "DE MACEDO BEZERRA", "LIMA",
  "Ivete Ro-" + "sane Dalmolin", "ARLINDO" + "ZANOTTI", "ALDEMIR" + "FONSECA JÚNIOR" (quebra de
  página). Quando só há quebra de linha ou hifenização, o valor é único e copiado com "\n" e com o
  hífen. Exemplos: "WEMERSON\nLUIZ CARDOSO PIMEN-\nTEL", "Fran-\ncisca das Chagas Carvalho Fon¬\ntenele"
  e o espaço depois de "Bor-" no endereço do R1-015.
- **Saúde partida pela coluna vizinha (R1-012):** "paralisia" e "cerebral" ficam como entradas
  separadas, mais "cadeira de rodas".
- **OCR, sem pontuação e letras espaçadas:** o valor é copiado como está. Exemplos: "Rairnunda Nonata
  Gouveia", "WELLINGT0N DA C0STA FARIAS", "17 08 1963", "M A R I L E N E   A P A R E C I D A   D E   S O
  U Z A". Uma grafia diferente do mesmo nome é outra entrada, como "Marcia R. dos Santos" e "Mar cia
  Regina dos Sant os".
- **Nomes de guerra, iniciais e apelidos:** "M. SAMPAIO", "J.A.M.", "A. Lins", "NEIDE" e "BAIANO" são
  NOME_PESSOA (convenção 2).
- **Valores recebidos ou devidos por pessoa natural (convenção 7):**
  - são DADO_FINANCEIRO, com "R$" ou "REAIS" quando presentes: vencimentos, vantagens, descontos e
    líquidos (R1-004), benefícios, bolsas, diárias, multas, pensão, renda, valor da venda do veículo
    e prejuízo;
  - totais e valores de pessoa jurídica são públicos (multa da transportadora no R1-029);
  - agência e conta são entradas separadas, sem o código do banco;
  - a chave PIX do R1-017 é DADO_FINANCEIRO.
- **ID_PROCESSUAL (convenção 8):**
  - entram número de ficha, relatório social, certidão, BO, TCO, inquérito, PAJ, prontuário,
    solicitação SISREG, AIT, vistoria, protocolo de atendimento, inscrição em seletivo, matrícula de
    estudante e "Livro 214, fls. 88" do pacto antenupcial;
  - portarias, editais e protocolos de publicação de atos ficam como públicos.
- **Licença que enuncia motivo de saúde é DADO_SAUDE (convenção 3):** "licença para tratamento de
  saúde", "Licença-saúde", "Licença-gestante", "atestado médico" e "licença por motivo de doença em
  pessoa da família". Licença-prêmio, férias, nojo e abono não entram. O CID é entrada à parte, com a
  sigla, como no exemplo das diretrizes.
- **Endereço do logradouro ao complemento (convenção 4):** localidade rural entra ("P.A. Ronca, Lote 47,
  Gleba Água Amarela"; "Povoado Caraíbas, Sítio Boa Esperança, s/n"). Bairro e município ficam fora.
  Endereço de órgão público é público.
- **Dado sensível:** "Parda", "Preta" e "frequentadora da Igreja\nAssembleia de Deus".

## Casos duvidosos

1. **Empenhos e ordens bancárias (R1-021):** marquei como ID_PROCESSUAL. Há uma leitura razoável de
   que são números de execução orçamentária, publicados em portais de transparência. Esta é a
   divergência de maior peso: 16 entidades.
2. **"PARATLETISMO" e "BASQUETE CR" (R1-018):** a deficiência é inferida da modalidade, não declarada.
   Mantive como DADO_SAUDE. O AEE do R1-028 ficou público porque não define o aluno como pessoa com
   deficiência e porque o TEA já está anotado.
3. **"prioridade amarela" (R1-013) e "EXAME TRAUMATOLÓGICO" (R1-010):** o primeiro é classificação de
   regulação. O segundo é exame requisitado, ainda não realizado.
4. **R1-020:** "bom estado geral" e "internado" entraram, "acidente motociclístico" não.
5. **Consultas e avaliações pendentes:** "consulta corn hernatologista" (R1-001) é DADO_SAUDE porque
   nomeia a especialidade. "avaliação no CER II de Parnaíba" (R1-015) não foi anotada, e a
   instituição ficou pública.
6. **Sem rótulo nas diretrizes, ficaram fora:**
   - prisão do companheiro (R1-015);
   - data de óbito (R1-023);
   - "falecido" (R1-019);
   - licença-nojo (R1-016);
   - apresentação à Seção de Justiça e Disciplina (R1-027);
   - escolaridade, estado civil, profissão e naturalidade.
7. **CEP genérico do município ("77950-000", R1-006):** anotado como ENDERECO, preferindo o pessoal.
8. **Código verificador e CRC do SEI (R1-013):** aceitos como públicos, porque autenticam o documento e
   não identificam a pessoa.
