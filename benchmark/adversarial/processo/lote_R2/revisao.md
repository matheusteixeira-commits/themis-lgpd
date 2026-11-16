# Lote R2 — revisão independente da anotação (identidades e localização)

* **Entrada:** `processo/lote_R2/anotacao_redator.jsonl` (30 documentos, 769 entidades, 394 trechos públicos).
* **Saída:** `lotes/lote_R2.jsonl` (30 documentos, 765 entidades, 409 trechos públicos).
* **Validação:** `ferramentas.py validar lotes/lote_R2.jsonl` → `sem problemas`. Conferido à parte: os textos,
  `id`, `genero` e `uf` ficaram idênticos aos do redator, e nenhum trecho público se sobrepõe a uma ocorrência
  de dado pessoal.
* **Método:** revisão cega. Cada texto foi lido do começo ao fim e anotado antes de abrir a anotação do redator
  daquele documento. O sistema e o avaliador não foram executados. `sondagem.md`, `.trabalho/` e os lotes dos
  outros redatores não foram lidos. Depois da comparação, uma varredura listou, por documento, todo número e
  toda palavra com inicial maiúscula sem cobertura de entidade ou de trecho público. Ela não revelou dado pessoal
  omitido.

## Concordância (redator × final)

| Medida | Valor |
|---|---:|
| Documentos | 30 |
| Documentos com alguma divergência (entidades ou públicos) | 18 |
| Documentos com divergência em entidades | 5 |
| F1 por rótulo | 0,9896 |
| F1 por valor (sem rótulo) | 0,9896 |

As 759 entidades em comum coincidem também no rótulo. Toda divergência de entidade é de **extensão em
`DADO_SAUDE`**. Não houve inclusão, exclusão nem troca de rótulo.

## Alterações

### Por tipo

| Tipo | Quantidade |
|---|---:|
| Entidades incluídas | 0 |
| Entidades removidas | 0 |
| Extensão corrigida | 6 entidades finais (substituem 10 entradas do redator) |
| Rótulo corrigido | 0 |
| Trechos públicos incluídos | 20 |
| Trechos públicos removidos | 5 |

### Por rótulo

| Rótulo | Redator | Final | Alteração |
|---|---:|---:|---|
| NOME_PESSOA | 250 | 250 | — |
| DATA_NASC | 101 | 101 | — |
| DOC_PESSOAL | 85 | 85 | — |
| ID_PROCESSUAL | 44 | 44 | — |
| ENDERECO | 48 | 48 | — |
| CONTATO | 29 | 29 | — |
| DADO_FINANCEIRO | 28 | 28 | — |
| DADO_SENSIVEL | 24 | 24 | — |
| QUASI_IDENTIFICADOR | 28 | 28 | — |
| DOC_PROFISSIONAL | 17 | 17 | — |
| ID_VEICULO | 4 | 4 | — |
| DADO_SAUDE | 111 | 107 | 6 extensões corrigidas (4 fusões de duas entradas, 2 ampliações) |
| **Total** | **769** | **765** | |

### Extensões corrigidas (todas `DADO_SAUDE`, convenção 3)

| Doc. | Redator | Final | Fundamento |
|---|---|---|---|
| R2-015 | "tuberculose pulmonar" | "tuberculose pulmonar em 12/08/2025" | data do diagnóstico integra a condição |
| R2-015 | "tratamento diretamente observado (TDO)" + "esquema RHZE, 4 comprimidos ao dia" | uma expressão só | terapia única ("TDO com esquema…"), com posologia contígua; não é coordenação. "TDO" segue como entrada própria para a menção posterior |
| R2-016 | "grávida de 24 semanas" | "…, sem nenhuma consulta desde a saída do Chile" | estado do acompanhamento integra a condição (mesmo critério do redator em "tuberculose, com tratamento interrompido…" e "hipertensão, sem medicação") |
| R2-020 | "HIV positivo, em TARV irregular" + "sem retirar a medicação há cerca de três meses" | uma expressão só | condição com estado do tratamento, contígua |
| R2-023 | "úlcera infectada no hálux direito" + "amputação do hálux direito" | "…, que evoluiu para amputação do hálux direito" | cadeia causal é uma só expressão |
| R2-026 | "TEA nível 1 de suporte" + "laudo de neuropediatra de 2023" | "…, conforme laudo de neuropediatra de 2023" | origem e data do diagnóstico integram a condição |

### Trechos públicos

* **Incluídos (20):** cargos de assinatura sem nome que faltavam para manter a coerência com os demais documentos
  ("Enfermeira", "Médico", "Enfermeiro", "Médica", "Psicóloga", "Escrivã", "assistente social", "Técnica de
  referência"). Datas de atos oficiais: registro de BO, data da ronda e da manifestação, a data por extenso dos
  termos lavrados ("três dias do mês de novembro de 2025", "onze dias de novembro de 2025"), o período do registro
  semanal e o marco legal "22 de dezembro de 2015". Órgãos: "Registro Civil da Paróquia San Simón", "Registro Civil
  do Município Antonio Díaz", "Governo Federal" e "SUS".
* **Removidos (5):** "Avenida Rio Branco" e "Rua Coronel Gurgel" (R2-019, cruzamento onde as crianças pediam
  dinheiro e a mãe vende artesanato), "Varadouro" e "Praça Vidal de Negreiros" (R2-020, pontos de pernoite atual
  e anterior), "Praça Sete" (R2-028, ponto diário de venda de pessoa em situação de rua já nomeada). São locais
  de rotina de pessoas identificadas. Não chegam a ser endereço, mas também não devem ser cobrados como "legíveis".
  Ficaram neutros: nem pessoais, nem públicos.

## Regras aplicadas (confirmadas na anotação final)

* **Nomes:** apelidos ("Paraná", "Professor", "Galego", "Tico", "Batchan", "Formiguinha", "Ceará", "Bahia",
  "Doutor", "Paulo"), nome social e nome de registro, grafias alternativas de nomes estrangeiros (ordem
  sobrenome-nome, hífen, caixa alta, hangul) e iniciais são `NOME_PESSOA`. Os pronomes de tratamento ficam
  fora ("Dona Flor" → "Flor", "Tia Bendita" → "Bendita"), assim como o artigo de alcunhas em espanhol ("el
  Gocho" → "Gocho"). Servidores e agentes públicos também são anotados.
* **Datas e idades:** formatos não usuais (romano, ISO, ponto, francês, espanhol, por extenso, "64a") e o ano de
  nascimento isolado ("1992", "1961") são `DATA_NASC`. "Aparenta mais de 70 anos" não é idade exata e não foi
  anotado.
* **Endereço:** endereços descritivos (aldeia, povoado, ocupação, acampamento, palafita, ponto de referência) vão
  do logradouro ou localidade ao último complemento. Coordenadas geográficas, lotes de assentamento (inclusive os
  dos confrontantes) e locais de pernoite de pessoas em situação de rua também são `ENDERECO`. Bairro, município,
  "sector"/"barrio", terra indígena e região ficam fora.
* **Quase-identificador:** o identificador mais o atributo, sem artigo ("única professora da escola da
  comunidade", "mototaxista que faz a linha da fronteira no turno da manhã"), inclusive para terceiros sem nome
  (servidores identificáveis por posto e turno).
* **Sensível:** etnia, povo, cor/raça autodeclarada, religião, identidade de gênero e união homoafetiva, cada um
  na expressão inteira.
* **Financeiro:** renda, benefício (inclusive "um salário mínimo" de BPC, aposentadoria ou seguro-defeso),
  pensão alimentícia ("30% do salário mínimo"), prejuízo alegado, valor devido à autarquia, agência e conta em
  entradas separadas.
* **ID_PROCESSUAL:** número do próprio relatório, ficha, parecer ou laudo sobre pessoa ou família; RA e matrícula
  escolar; código familiar do CadÚnico; registro SIASI; códigos SIPRA, CAR e SNCR de imóvel de pessoa natural;
  protocolo de refúgio.

## Casos duvidosos (decididos, sem alteração)

1. **Nacionalidade, naturalidade e língua** ("venezuelana", "síria", "língua pomerana", "aimará", "natural de
   Londrina"): nenhum rótulo as cobre e elas não identificam isoladamente, por isso não foram anotadas. Os
   municípios de naturalidade que o redator listou como públicos ("Domingos Martins", "Juazeiro do Norte", "Porto
   Seguro") foram mantidos, porque a convenção 4 deixa o município fora do dado pessoal.
2. **R2-028, venda de colares na Praça Sete:** não é única, e a pessoa já está nomeada. Não foi anotada como
   quase-identificador, só retirada dos públicos. Em R2-007 a mesma estrutura ("guardador de carros em frente ao
   Mercado de São José nas manhãs de sábado") é quase-identificador, porque ali a pessoa não tem nome civil.
3. **Extensões de quase-identificador mantidas como o redator fez:** R2-013 "única vendedora chinesa do box
   1.214", com "Feira dos Importados" legível; R2-015 "cacique da Aldeia Morro do Boi", sem a oração "que divide a
   casa com o paciente"; R2-002 "única parteira tradicional da comunidade", sem "avó materna".
4. **Exame de corpo de delito requisitado** (R2-003 e R2-014): não foi anotado, porque ainda não foi realizado e
   é providência de rotina.
5. **Saúde, extensões aceitas:** R2-023 "dieta proposta pela nutricionista" (sem "não segue"); R2-025 "tratamento
   de hanseníase com PQT" (sem "concluiu em 2024"); variantes de pré-natal ("início do pré-natal", "pré-natal
   iniciado", "pré-natal") mantidas como escritas. Também foram aceitos "alta hospitalar", "material ampliado",
   "glicosímetro" e "controle glicêmico", que revelam condição ou tratamento.
6. **Endereço de estabelecimento** (R2-024, "Pastelaria Sabor Oriental, Avenida Presidente Kennedy, 2.415, loja
   B"): mantido como público, por ser dado de pessoa jurídica e local do fato. O endereço residencial da vítima é
   `ENDERECO`.
7. **Abrigo público** (R2-001): "Abrigo Rondon 3" fica público e "unidade habitacional 214 do setor C" é `ENDERECO`.
8. **Rótulos aceitos entre alternativas pessoais:** SIASI, RA e protocolo de refúgio como `ID_PROCESSUAL` (em vez
   de `DOC_PESSOAL`); RGP como `DOC_PROFISSIONAL`; CIPTEA como `DOC_PESSOAL`; sufixos de órgão emissor ("SSP/MS",
   "LP", "SC") fora do valor do documento.
