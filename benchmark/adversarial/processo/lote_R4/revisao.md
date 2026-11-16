# Lote R4 — revisão independente (armadilhas de precisão)

Arquivo final: `benchmark/adversarial/lotes/lote_R4.jsonl` (30 documentos, 116 entidades, 1.126 trechos públicos).
Base: `processo/lote_R4/anotacao_redator.jsonl` (30 documentos, 116 entidades, 1.083 trechos públicos).

## Método

1. Leitura integral de `benchmark/ouro/DIRETRIZES.md`, inclusive as convenções de extensão.
2. Os 30 textos foram extraídos sem as anotações e lidos do começo ao fim. A anotação própria de
   entidades foi registrada antes de abrir a anotação do redator.
3. Só depois disso as duas anotações foram comparadas, documento por documento. Em seguida os `publicos`
   do redator foram revistos: unidade, sobreposição com dado pessoal e armadilhas sem registro.
4. Não foram lidos `sondagem.md`, `.trabalho/` nem os scripts de `processo/lote_R4/geracao/`. O
   sistema e o avaliador não foram executados.

## Concordância (redator × final)

`ferramentas.py concordancia anotacao_redator.jsonl lotes/lote_R4.jsonl`

| Medida | Valor |
|---|---:|
| Documentos | 30 |
| Documentos com divergência | 20 (todas só em `publicos`) |
| F1 por rótulo | 1,0 |
| F1 por valor | 1,0 |

A anotação cega de entidades coincidiu com a do redator nas 116 entidades, com o mesmo valor e o mesmo
rótulo. Isso vale também para as decisões de extensão: número de conselho sem a sigla, "licença para
tratamento de saúde", "suspeita de malária" e o quase-identificador do R4-016. Validação:
`ferramentas.py validar` → "sem problemas". Não há sobreposição entre ocorrências de trechos públicos
e de dados pessoais, o que foi conferido por posição no texto.

## Alterações

| Tipo | Quantidade |
|---|---:|
| Entidades incluídas | 0 |
| Entidades removidas | 0 |
| Extensão corrigida | 0 |
| Rótulo corrigido | 0 |
| Trechos públicos incluídos | 53 |
| Trechos públicos removidos ou substituídos | 10 |

Nenhuma alteração atingiu entidades, por isso a contagem por rótulo de dado pessoal é zero em todos.
Entidades finais por rótulo: NOME_PESSOA 84, DOC_PROFISSIONAL 16, DOC_PESSOAL 4, ID_PROCESSUAL 3,
CONTATO 2, DADO_FINANCEIRO 2, DADO_SAUDE 2, DATA_NASC 2, QUASI_IDENTIFICADOR 1.

### Trechos públicos removidos ou substituídos (10)

- **Compostos desfeitos em unidades (convenção 9):** "Teresina/PI" → "Teresina" (R4-001);
  "Palmares/PE" → "Palmares" (R4-020); "Sousa/PB" → "Sousa" (R4-024; Sousa também é sobrenome);
  "SAMU 192 – Base Jardim Todos os Santos" → "SAMU 192" e "Base Jardim Todos os Santos" (R4-013);
  "art. 74, II, da Lei nº 14.133/2021" → "Lei nº 14.133/2021" (R4-011).
- **Composto redundante removido:** "Cajazeiras/PB" (R4-024), porque "Cajazeiras" já está na lista.
- **Nome de embarcação sem o substantivo comum que indica o tipo:** "lancha-ambulância Enfermeira
  Doralice Paixão" → "Enfermeira Doralice Paixão" (R4-002); "ferry-boat Comandante Ivo Barreto" →
  "Comandante Ivo Barreto" (R4-010); "balsa Comandante Aldemir Lopes" e "barco de saúde Enfermeira
  Zuleide Bezerra" → nomes sem o tipo (R4-016). Isso segue o que o próprio redator fez no R4-027
  ("Professor Ednaldo Picanço"). Os prefixos "B/M" e "N/M" foram mantidos porque fazem parte da
  designação da embarcação.

### Trechos públicos incluídos (53)

- **Municípios com forma de nome de pessoa que só estavam listados em caixa alta ou dentro de um
  composto:** "Domingos Martins" (R4-012), "Carlos Barbosa" (R4-019), "Pedro Afonso" (R4-015),
  "Rafael Fernandes" e "José da Penha" (R4-029). Também entraram municípios citados e não listados:
  "Plácido de Castro" e "Manoel Urbano" (R4-016).
- **Idades e datas que não são de pessoa (armadilha de DATA_NASC):** "18 anos" e "60 anos" (R4-015),
  "18 anos" (R4-017) e "17 anos" (R4-030), todas como requisito ou faixa etária geral. Somam-se às que
  o redator já listara: "104 anos", "72 anos", "66 anos", "31 anos" e "12/05/2019".
- **Cargos sem nome e funções:** "FISCAL DO CONTRATO" e "sócio-administrador" (R4-001); "enfermeira
  epidemiologista" e "técnico em vigilância" (R4-004); "diretor-geral da ARCON" (R4-010);
  "Coordenador Municipal de Proteção e Defesa Civil" (R4-012); "contadora da Secretaria", "diretor
  do hospital" e "Secretária" (R4-014); "Tenente-Coronel BM" (R4-016); "delegado regional"
  (R4-023); "Pregoeiro" e "Presidente do Consórcio" (R4-024); "Contador" e "Diretor-presidente"
  (R4-028); "Prefeito" e "Prefeita" (R4-029).
- **Órgãos, programas e datas:** "ESTADO DO PIAUÍ" (R4-001); "Coordenadoria Regional de Vigilância em
  Saúde" (R4-004); "ARCON" e "Ouvidoria da ARCON" (R4-010); "2 de setembro de 2025" em caixa normal
  (R4-012); "Comissão Organizadora" (R4-015); "JUCESP" (R4-017); "Prêmio Jovem Talento Musical 2025"
  (R4-019); "Carteira de Identidade Nacional", "CIN", "Receita Federal" e "Instituto Médico Legal"
  (R4-026); "Comissão de Contratação" (R4-027).
- **Saúde sem pessoa identificável:** "cirurgias eletivas de catarata e de hérnia" (R4-014, fila
  agregada de 87 pacientes) e "quimioterapia" (R4-028, produção agregada e prazo legal).

## Regras aplicadas (confirmadas na anotação do redator)

- Nomes de pessoa dentro de nomes de instituição, logradouro público, programa, prêmio, lei, operação
  ou embarcação são públicos. Exemplos: "Lei Maria da Penha", "Operação Maria Bonita", "CEPAV
  Margarida", as ruas do R4-018 citadas sozinhas e "INSTITUTO DE IDENTIFICAÇÃO CIVIL DELEGADO
  RAIMUNDO FERRAZ".
- Dados de pessoa jurídica são públicos: razão social com nome ou iniciais ("J. R. Oliveira Comércio…"),
  CNPJ, endereço de empresa ou órgão, contas bancárias da parceria, do fundo ou do convênio (R4-011,
  R4-016 e R4-028) e a chave PIX que é o CNPJ do fundo.
- Placas, RENAVAM e chassi de veículos oficiais ou da frota municipal são públicos (R4-001, R4-004,
  R4-006, R4-013, R4-017, R4-023, R4-025 e R4-026).
- Contatos institucionais em Gmail ou Hotmail, WhatsApp institucional e e-mails de empresa são públicos.
  O celular do leiloeiro, pessoa natural, é CONTATO (R4-017).
- O registro em conselho, a matrícula funcional, o MASP e a matrícula na JUCESP são DOC_PROFISSIONAL, só
  com o número, sem a sigla nem "nº" (convenção 1).
- Valores recebidos ou devidos por pessoa identificada são DADO_FINANCEIRO: diárias de R$ 450,00 (R4-020)
  e ressarcimento de R$ 195,23 (R4-013). Valores fixados em norma (diária de R$ 180,00), valores por
  beneficiário sem identificação (bolsas, auxílios, aluguel social, Bolsa Reciclagem), multas a
  empresas e totais de programa são públicos.
- O protocolo ou pedido LAI ligado ao requerente é ID_PROCESSUAL (R4-005 e R4-022). Também o é o auto
  de infração ligado ao servidor condutor (R4-013). Notificações, autos, laudos de ensaio, inquérito
  civil e ação civil pública contra empresas ou municípios são públicos.
- Iniciais e idade de presos: "J. C. S. A." e "M. L. F." são NOME_PESSOA; "41 anos" e "36 anos" são
  DATA_NASC (R4-023).

## Casos duvidosos (mantidos como estão)

1. **R4-030, "R$ 5.000,00":** é o valor do Prêmio Mestre Antônio Pimenta, e os dois contemplados são
   nomeados na frase seguinte. Ficou público como parâmetro do programa ("dez prêmios de"), porque o
   texto não o atribui a uma pessoa determinada. Uma leitura estrita da convenção 7 o faria
   DADO_FINANCEIRO. Os valores do prêmio no R4-007 são da edição de 2025 e não se ligam à premiada de
   2024.
2. **ART (R4-001 e R4-018):** ficou pública como registro de responsabilidade técnica da obra ou do
   contrato, e não como procedimento sobre a pessoa. O número de CREA do profissional ficou pessoal.
3. **R4-004, "O óbito de Vera":** Vera é município. O registro de um único óbito por dengue, com a
   semana epidemiológica, foi tratado como dado epidemiológico agregado, sem quase-identificador.
4. **R4-023, "que trabalhava em um cartório da região":** não foi anotado como QUASI_IDENTIFICADOR,
   porque o atributo não é único (três municípios). As iniciais e a idade já estão anotadas.
5. **R4-020, licença médica:** "licença para tratamento de saúde" é DADO_SAUDE, porque enuncia o motivo.
   "60 dias" não foi anotado, pois é a simples duração (convenção 3), nem listado como público, por
   ser contíguo ao dado de saúde.
6. **R4-011, "Genésio do Acordeon":** é nome artístico de pessoa natural e ficou NOME_PESSOA. O cachê
   de R$ 85.000,00 é pago à empresa e é público.
7. **R4-016:** o quase-identificador "único professor da escola da comunidade Pupunha" e o dado de saúde
   "suspeita de malária" ficaram como entradas separadas. Por isso "Pupunha" não foi listado como
   público.
8. **Citações de norma com data** ("Lei nº 12.608, de 10 de abril de 2012") e o período "1º de janeiro
   a 30 de junho de 2025" foram mantidos como uma unidade, por designarem um único ato ou período.
