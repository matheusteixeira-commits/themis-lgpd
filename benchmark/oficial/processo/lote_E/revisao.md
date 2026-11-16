# Lote E — revisão independente da anotação

Tema: assistência social, segurança pública, justiça e ouvidoria. 50 documentos, 27 UFs.

* Entrada: `textos.jsonl` e `anotacao_redator.jsonl`.
* Saída: `lote_E.jsonl`, no mesmo formato.
* Validação: `ferramentas.py validar lote_E.jsonl` retorna "sem problemas".
* Material de apoio consultado: só `DIRETRIZES.md` (lido por inteiro, com as "Convenções de extensão") e `ferramentas.py`.
* Não foi lido nada de `themis-lgpd`, de `ouro/`, dos outros lotes nem de `lote_E/geracao/`. Nenhum sistema de anonimização foi executado.

## Método

1. Os 50 textos foram lidos do começo ao fim, e os dados pessoais foram levantados antes de abrir a anotação do redator.
2. Em seguida, cada documento foi comparado com a anotação do redator.
3. Duas varreduras automáticas serviram de checagem complementar. A primeira procurou trechos numéricos, valores e sequências capitalizadas sem cobertura. A segunda procurou palavras-chave de saúde e de dado sensível sem cobertura.
4. Também foi verificada a sobreposição entre `publicos` e entidades, por posição no texto e não só por igualdade de valor. Não há nenhuma sobreposição no arquivo final.
5. As alterações foram aplicadas por script. Cada valor novo foi conferido como palavra inteira no texto.
6. As entidades de cada documento foram reordenadas pela primeira ocorrência no texto.

## Concordância entre o redator e a anotação final

Medida com `ferramentas.py concordancia anotacao_redator.jsonl lote_E.jsonl`:

| Medida | Valor |
|---|---:|
| Documentos | 50 |
| Documentos com alguma divergência (entidades ou públicos) | 21 |
| Documentos com divergência de entidades | 17 |
| F1 por rótulo | 0,9778 |
| F1 por valor | 0,9778 |
| Entidades em comum | 815 |
| Entidades só do redator | 13 |
| Entidades só da versão final | 24 |
| F1 dos trechos públicos (por documento e trecho) | 0,9882 |

O F1 por rótulo é igual ao F1 por valor porque nenhuma divergência foi só de rótulo.

### Concordância por rótulo

| Rótulo | Redator | Final | Em comum | F1 |
|---|---:|---:|---:|---:|
| NOME_PESSOA | 224 | 224 | 224 | 1,0000 |
| DADO_SAUDE | 109 | 117 | 100 | 0,8850 |
| DATA_NASC | 81 | 81 | 81 | 1,0000 |
| DADO_FINANCEIRO | 78 | 79 | 78 | 0,9936 |
| ID_PROCESSUAL | 77 | 77 | 77 | 1,0000 |
| DOC_PESSOAL | 63 | 63 | 63 | 1,0000 |
| ENDERECO | 54 | 54 | 52 | 0,9630 |
| CONTATO | 39 | 39 | 39 | 1,0000 |
| QUASI_IDENTIFICADOR | 34 | 35 | 34 | 0,9855 |
| DOC_PROFISSIONAL | 29 | 29 | 29 | 1,0000 |
| ID_VEICULO | 24 | 24 | 24 | 1,0000 |
| DADO_SENSIVEL | 16 | 17 | 14 | 0,8485 |
| **Total** | **828** | **839** | **815** | **0,9778** |
| Trechos públicos | 755 | 767 | 752 | 0,9882 |

## Alterações por tipo e rótulo

| Tipo | DADO_SAUDE | DADO_SENSIVEL | ENDERECO | DADO_FINANCEIRO | QUASI_IDENTIFICADOR | Total |
|---|---:|---:|---:|---:|---:|---:|
| Inclusão | 9 | 1 | 0 | 1 | 1 | 12 |
| Remoção (por fusão de duas entradas) | 1 | 0 | 0 | 0 | 0 | 1 |
| Extensão corrigida | 8 | 2 | 2 | 0 | 0 | 12 |
| Rótulo corrigido | 0 | 0 | 0 | 0 | 0 | 0 |

Trechos públicos: 15 incluídos e 3 removidos.

### Inclusões (12)

| Doc. | Rótulo | Valor | Fundamento |
|---|---|---|---|
| E-002 | DADO_SENSIVEL | "fio de contas e cabeça raspada no período de resguardo" | Prática religiosa da criança que revela a religião mesmo com "iniciado no candomblé" tarjado (conv. 6). |
| E-002 | DADO_SAUDE | "atendimento psicológico" | Atendimento requisitado para a criança identificada. |
| E-006 | DADO_SAUDE | "Sessões particulares de fonoaudiologia" | Terapia da criança na tabela de despesas. A outra menção já estava anotada; esta ficava exposta. |
| E-007 | DADO_FINANCEIRO | valor por extenso da multa ("um milhão, … reais") | Repete por extenso a multa à pessoa natural, já anotada em algarismos (conv. 7). |
| E-030 | DADO_SAUDE | "acompanhamneto oftalmologico" | Serviço de saúde especializado solicitado para o idoso. O erro de digitação do texto foi mantido. |
| E-030 | DADO_SAUDE | "avaliacao do risco de quedas" | Mesmo critério da linha anterior. |
| E-032 | QUASI_IDENTIFICADOR | "enfermeira da Equipe Multidisciplinar de Saúde Indígena do polo base" | Servidora identificada pela lotação. Segue o critério do redator para servidores descritos pelo cargo (E-019, E-023). |
| E-032 | DADO_SAUDE | "internada" | Internação hospitalar da criança identificada. |
| E-032 | DADO_SAUDE | "acompanhamento nutricional mensal" | Terapia coordenada, em entrada separada (conv. 3). |
| E-032 | DADO_SAUDE | "suplementação" | Mesmo critério da linha anterior. |
| E-033 | DADO_SAUDE | "dieta adaptada" | Tratamento da alergia alimentar da criança. |
| E-038 | DADO_SAUDE | "capacidade psicomotora alterada em razão da influência de álcool" | Estado de intoxicação do réu. Segue o critério do redator para sinais de embriaguez (E-034, E-038). |

### Extensões corrigidas (12)

| Doc. | Rótulo | Redator | Final | Convenção |
|---|---|---|---|---|
| E-005 | DADO_SAUDE | "faz uso abusivo de álcool" | "uso abusivo de álcool" | Verbo de uso fica fora (conv. 3), como em E-047. |
| E-010 | ENDERECO | "Travessa Iracema, 45" | "… 45, Comunidade do Trilho" | A comunidade integra o endereço, como "Grota …" (E-027) e "Ocupação …" (E-021). O bairro fica fora (conv. 4). |
| E-013 | DADO_SAUDE | "teve pico de pressão arterial" | "pico de pressão arterial" | Verbo fora (conv. 3). |
| E-016 | DADO_SAUDE | "dependente de crack" | "… desde a adolescência" | Condição com o atributo temporal forma uma só expressão (conv. 3). |
| E-019 | DADO_SAUDE | "cortes nos antebraços" + "automutilação" | "cortes nos antebraços compatíveis com automutilação" | Achado com a sua caracterização forma uma só expressão (conv. 3). É a fusão contada como remoção. |
| E-020 | DADO_SENSIVEL | "também venezuelano" | "venezuelano" | O advérbio não integra o dado (conv. 6). |
| E-023 | DADO_SAUDE | "tratamento para dependência química" | "… há dois meses" | A duração contígua integra a terapia (conv. 3). |
| E-026 | DADO_SAUDE | "afastamento médico por leptospirose" | "…, com internação" | Atributo contíguo da condição (conv. 3). |
| E-030 | ENDERECO | "Fazenda Sao Bento, Estrada da Vereda, km 18" | "…, Comunidade Vereda Grande" | A localidade rural integra o endereço. "zona rural" fica fora (conv. 4), como em E-001. |
| E-030 | DADO_SAUDE | "cegueira bilateral decorrente de glaucoma" | "…, diagnosticada em 2021" | A data do diagnóstico integra a expressão (conv. 3). |
| E-035 | DADO_SENSIVEL | "Frequenta o grupo de oração da Renovação Carismática Católica" | "grupo de oração da Renovação Carismática Católica" | Expressão nominal sem o verbo, como "membro da Igreja Y" (conv. 6). |
| E-040 | DADO_SAUDE | "epilepsia" | "epilepsia desde criança" | Atributo temporal (conv. 3), como em E-016. |

### Trechos públicos

* **E-003:** "15º D.P. – ITAIM BIBI" foi desmembrado em "15º D.P." e "ITAIM BIBI" (conv. 9). Foi incluído "Rua Joaquim Floriano", logradouro público com nome de pessoa (regra de extensão das diretrizes).
* **E-013:** foi incluído "Estado do Maranhão", em contexto institucional.
* **E-024:** "2ª COMPANHIA – CORUMBÁ" foi desmembrado em "2ª COMPANHIA" e "CORUMBÁ".
* **E-032:** foi removido "Equipe Multidisciplinar de Saúde Indígena", que passou a estar dentro do novo QUASI_IDENTIFICADOR. Segue o critério do redator de não sobrepor instituição e descrição.
* **E-044:** foi incluído "Rua Ademar Vicente Ferreira", logradouro com nome de pessoa no local do fato. O outro logradouro do cruzamento já estava listado.
* **E-050:** foram incluídos os 8 valores da tabela de partilha por porte de município. São valores agregados de órgão, públicos pela conv. 7, e completam o total que já estava listado.

## Regras aplicadas

Foram aplicadas as diretrizes e as convenções de extensão 1 a 9. Também foram confirmadas as decisões do redator listadas abaixo, por serem coerentes com as diretrizes:

* **Nomes e cargos:** apelidos são NOME_PESSOA ("Galego", "Wel da Lagoa", "Paraíba"), sem pronome de tratamento ("Seu Edmilson" → "Edmilson"). Nomes com quebra de linha foram copiados como estão no texto. Postos e cargos ao lado de nomes são públicos. Os registros de agentes (CRESS, CRP, CRF, OAB, SIAPE, MADEP, matrícula) são DOC_PROFISSIONAL, anotados só com o número.
* **ID_PROCESSUAL:** número de relatório, prontuário, ficha, inscrição, requerimento, laudo de vistoria, auto de infração, termo de apreensão ou recolhimento, sindicância, PAD, matrícula prisional, manifestação ou atendimento de ouvidoria sobre pessoa ou família. Números de ofícios e requisições, que são atos oficiais, e atos sobre coletividades (resolução, comunicado, processo SEI de resolução) são públicos.
* **DADO_FINANCEIRO:** valores recebidos, pagos ou devidos por pessoa natural, como renda, benefício, aluguel, dívida, multa, prejuízo, propina, pensão, despesas da família e valor da causa de alimentos. Valores agregados, de pessoa jurídica, de base legal e o valor da causa "para fins fiscais" são públicos.
* **DADO_SAUDE:** exame e resultado contíguos, inclusive o etilômetro negativo. Entram também os exames periciais requisitados, os sinais de intoxicação e as reformulações como "pessoa com deficiência". Rótulos de caixas de seleção de formulário não foram anotados.
* **DADO_SENSIVEL:** cor ou raça autodeclarada, etnia, religião, orientação sexual, nacionalidade e situação migratória da vítima (critério do redator, mantido). "única professora negra do corpo docente do colégio" é um só QUASI_IDENTIFICADOR.
* **QUASI_IDENTIFICADOR:** a descrição inclui o atributo revelado, sem artigo inicial. Quando a descrição contém o nome de uma instituição, essa instituição não vai para `publicos`.
* **Locais de fato e municípios:** locais de fato sem número e municípios citados só em contexto pessoal são neutros.
* **Critério novo de saúde, aplicado de forma uniforme:** entram serviços ou procedimentos de saúde nomeados por especialidade ou natureza e ligados à pessoa identificada (atendimento psicológico, avaliação neurológica, acompanhamento oftalmológico ou nutricional, suplementação, dieta, internação). Menções genéricas ficam fora, como "acompanhamento de saúde", "consultas", "acompanhamento após a alta", "equipe de saúde" e "continuidade do acompanhamento".

## Casos duvidosos

Estes casos foram mantidos como o redator decidiu ou ficaram sem anotação, com a justificativa:

1. **E-043, "R$ 400,00":** é o custo estimado do transporte que a família não consegue pagar. Não é valor recebido nem devido. Foi mantido como DADO_FINANCEIRO porque se refere à necessidade concreta da família, na mesma linha das despesas de E-006.
2. **E-020 e E-044, exames de corpo de delito requisitados e ainda não feitos:** foram mantidos como DADO_SAUDE. A requisição se refere à pessoa identificada e revela lesão.
3. **Nacionalidade e situação migratória como DADO_SENSIVEL (E-017 e E-020):** a LGPD não as lista literalmente. Foram mantidas pela regra "na dúvida, o rótulo mais específico" e pelo tratamento conjunto de "procedência nacional" na Lei nº 7.716/1989.
4. **Idioma da pessoa sem anotação:** "intérprete de crioulo haitiano" (E-017), "intérprete de guarani" (E-049) e "em kaingang" (E-032) não foram anotados. Indicam a origem só de forma indireta, e a origem ou etnia já está anotada no próprio documento.
5. **"aposentadoria por incapacidade permanente" (E-045) sem anotação:** é o nome de uma espécie de benefício. A condição de saúde que a motiva já está anotada.
6. **Rótulos de despesa em E-006 sem anotação:** "Escola com mediador", "Medicação e fraldas" e "Transporte para as terapias" não foram anotados. Só "Sessões particulares de fonoaudiologia" entrou, por nomear uma terapia.
7. **Frases de saúde em negativa ou de gestão sem anotação:** "Não faz uso de medicação psiquiátrica" (E-008), "faltas a duas consultas agendadas" (E-012) e "teve a medicação restabelecida" (E-040) não foram anotados. São negativas ou registros administrativos e não descrevem condição, exame nem terapia.
8. **QUASI_IDENTIFICADOR ao lado de pessoa já nomeada:** foi mantido como o redator decidiu. É o caso do frentista em E-005 e E-044, do farmacêutico em E-037, do monitor em E-008 e E-026 e da intérprete de Libras em E-035. A descrição continua identificando a pessoa se o nome for tarjado.
9. **"Assis Brasil" (E-017) e "Novo Progresso" (E-007) em `publicos`:** foram mantidos. São municípios, e município não é dado pessoal (conv. 4). Por isso tarjá-los seria excesso.
10. **"HIV, em terapia antirretroviral regular" (E-035):** foi mantido como uma expressão, porque o estado do tratamento é atributo da condição. A carga viral ficou em entrada separada, como exame com resultado.

## Contagem final

839 entidades:

| Rótulo | Entidades |
|---|---:|
| NOME_PESSOA | 224 |
| DADO_SAUDE | 117 |
| DATA_NASC | 81 |
| DADO_FINANCEIRO | 79 |
| ID_PROCESSUAL | 77 |
| DOC_PESSOAL | 63 |
| ENDERECO | 54 |
| CONTATO | 39 |
| QUASI_IDENTIFICADOR | 35 |
| DOC_PROFISSIONAL | 29 |
| ID_VEICULO | 24 |
| DADO_SENSIVEL | 17 |

Há também 767 trechos públicos.

Seis documentos têm só trechos públicos: E-011, E-018, E-025, E-039, E-046 e E-050.
