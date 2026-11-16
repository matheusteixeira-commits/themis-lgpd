# Adjudicação do lote B

Arquivo final: `ouro/ouro_b.jsonl` (60 documentos, 783 entidades, 565 trechos públicos).
Validação (`ferramentas.py validar`): **sem problemas**.

Este documento registra a concordância antes de qualquer decisão, cada decisão tomada e os casos
difíceis, conforme o passo 3 das `DIRETRIZES.md`. Nenhum código de sistema de anonimização foi lido
ou executado. Só executei `benchmark/ouro/ferramentas.py` (`concordancia` e `validar`), sem ler o
código dele. As decisões seguem as diretrizes e as convenções fixadas na adjudicação do lote A
(`lote_a/adjudicacao.md`, seção 2.2), para que os dois lotes sejam medidos pelo mesmo critério.

## 1. Concordância antes da adjudicação

Comando: `ferramentas.py concordancia anotacao_redator.jsonl anotacao_cega.jsonl --divergencias divergencias.jsonl`

| Medida | Valor |
|---|---|
| Documentos | 60 |
| Documentos com divergência (entidades **ou** públicos) | **58** |
| … com divergência nas entidades | 45 (42 deles também divergem nos públicos) |
| … com divergência nos públicos | 55 (13 deles só nos públicos) |
| **F1 por rótulo** (tipo + valor) | **0,8614** |
| **F1 por valor** (só o valor) | **0,8614** |
| Entidades: redator / cega / em comum | 698 / 767 / 631 |
| Valores divergentes: só redator / só cega | 67 / 136 |
| Públicos: redator / cega / em comum (F1) | 463 / 465 / 347 (0,7478) |

O F1 por rótulo é igual ao F1 por valor. Isso significa que **não houve nenhuma divergência só de
rótulo**: quando os dois anotadores marcaram o mesmo trecho, deram o mesmo rótulo. Todas as
divergências são de **extensão** (o mesmo dado delimitado de outro modo) ou de **inclusão** (dado
visto por um só anotador).

Concordância por rótulo antes da adjudicação:

| Rótulo | Redator | Cega | Comum | F1 |
|---|---:|---:|---:|---:|
| DATA_NASC | 46 | 46 | 46 | 1,0000 |
| CONTATO | 62 | 62 | 62 | 1,0000 |
| DOC_PESSOAL | 74 | 74 | 74 | 1,0000 |
| DOC_PROFISSIONAL | 36 | 36 | 36 | 1,0000 |
| ID_VEICULO | 5 | 5 | 5 | 1,0000 |
| NOME_PESSOA | 189 | 189 | 188 | 0,9947 |
| ID_PROCESSUAL | 34 | 36 | 34 | 0,9714 |
| ENDERECO | 31 | 31 | 27 | 0,8710 |
| DADO_SAUDE | 171 | 238 | 138 | **0,6748** |
| DADO_SENSIVEL | 13 | 15 | 9 | **0,6429** |
| DADO_FINANCEIRO | 30 | 27 | 12 | **0,4211** |
| QUASI_IDENTIFICADOR | 7 | 8 | 0 | **0,0000** |

A concordância é bem menor que a do lote A (0,9563). Os identificadores estruturados (documentos,
contatos, datas de nascimento, placas) voltaram a ter concordância perfeita, e os nomes divergiram em
um único caso ("dona Eliete" × "Eliete"). As causas da queda são quatro, todas sistemáticas:

1. **Granularidade em saúde.** O redator juntava achados coordenados ("febre alta e neutropenia",
   "losartana, metformina e AAS"), e a cega os separava. A cega também marcou 238 itens de saúde,
   67 a mais que o redator: exames, escalas, internações e itens do plano terapêutico.
2. **Qualificadores em valores.** O redator incluía "mensais", "por mês", "uns", "renda estimada de".
   A cega incluía "agência … conta …" nas contas bancárias.
3. **Artigo inicial nos quase-identificadores.** O redator começava 6 dos 7 com "o"/"a"; a cega, não.
   Daí o F1 de 0 nesse rótulo, embora os dois tenham marcado as mesmas pessoas.
4. **Bairro, zona rural e território** no fim dos endereços (4 casos).

## 2. Decisões

| Tipo de decisão | Nº de decisões | Entidades no ouro | Valores divergentes resolvidos |
|---|---:|---:|---:|
| **Incluído**, a partir de divergência | 53 | 54 | 53 (todos vistos só pela cega; 6 com extensão ajustada às convenções) |
| **Incluído**, dado omitido por ambos | 12 | 15 | — |
| **Removido** (não é dado pessoal ou não cabe em rótulo) | 2 | — | 2 (1 do redator, 1 da cega) |
| **Rótulo corrigido** | 0 | — | — |
| **Extensão corrigida** | 62 | — | 148 (66 do redator, 82 da cega): 37 decisões a favor da cega, 21 a favor do redator, 4 com nova extensão |
| **Total de decisões sobre entidades** | **129** | | **203 de 203** |
| Trecho público retirado (fica neutro) | 3 | | |
| Trecho público normalizado | 1 | | ("Município: Parintins" → "Parintins") |

Nenhuma entidade de consenso foi removida, teve o rótulo trocado ou a extensão alterada. Revi
documento a documento as 631 entidades em que os dois anotadores concordaram e não encontrei falso
positivo nem rótulo errado. Em dois casos, uma entidade nova contém a de consenso (B-010, posologia
do benznidazol; B-060, radiografia de punho). Nesses casos, o valor de consenso continua no ouro
porque cobre outra ocorrência no texto.

Composição do ouro: 631 entidades de consenso, mais 126 valores divergentes mantidos como estavam
(25 do redator e 101 da cega), mais 4 novas extensões, mais 7 inclusões com extensão ajustada, mais
15 omitidas por ambos, o que dá **783**.

Entidades finais por rótulo:

| Rótulo | Ouro B |
|---|---:|
| DADO_SAUDE | 251 |
| NOME_PESSOA | 189 |
| DOC_PESSOAL | 74 |
| CONTATO | 62 |
| DATA_NASC | 46 |
| ID_PROCESSUAL | 36 |
| DOC_PROFISSIONAL | 36 |
| ENDERECO | 31 |
| DADO_FINANCEIRO | 30 |
| DADO_SENSIVEL | 15 |
| QUASI_IDENTIFICADOR | 8 |
| ID_VEICULO | 5 |
| **Total** | **783** |

Concordância de cada anotador com o conjunto adjudicado, para referência:

| Anotador | Precisão | Revocação | F1 |
|---|---:|---:|---:|
| Redator | 0,9398 | 0,8378 | 0,8859 |
| Cega | 0,9544 | 0,9349 | 0,9445 |

Diferente do lote A, aqui a anotação cega ficou mais próxima do ouro. A revocação do redator caiu
sobretudo em DADO_SAUDE (100 itens do ouro que ele não marcou nessa forma). A maior parte vem da
separação de achados coordenados, e o restante são itens que só a cega viu.

### 2.1 Tabela de decisões

| Doc | Decisão | Valor final | Descartado | Origem | Motivo |
|---|---|---|---|---|---|
| B-001 | extensão corrigida | DADO_SAUDE "diabética"; DADO_SAUDE "hipertensa" | DADO_SAUDE "diabética e hipertensa" | cega | diagnósticos distintos coordenados por "e" ficam separados (conv. 2) |
| B-001 | extensão corrigida | DADO_SAUDE "cirurgia de retirada da vesícula" | DADO_SAUDE "retirada da vesícula" | cega | o procedimento aguardado integra o dado (precedente A-005, "cirurgia de catarata…") |
| B-001 | incluído | DADO_SAUDE "crises de dor" | — | cega | sintoma da manifestante identificada |
| B-003 | extensão corrigida | DADO_SAUDE "risperidona 0,5 mg à noite" | DADO_SAUDE "risperidona 0,5 mg" | redator | posologia contígua ao medicamento (conv. 3) |
| B-003 | extensão corrigida | DADO_SAUDE "terapia ocupacional"; DADO_SAUDE "fonoaudiologia"; DADO_SAUDE "intervenção comportamental" | DADO_SAUDE "terapia ocupacional, fonoaudiologia e intervenção comportamental" | cega | terapias distintas sem núcleo comum ficam separadas (conv. 2 estendida; igual a B-039) |
| B-003 | incluído | DADO_SAUDE "suporte nível 2" | — | cega | grau de suporte do TEA (precedente A-026, "nível 2 de suporte") |
| B-004 | extensão corrigida | DADO_SAUDE "microcefalia associada à síndrome congênita do Zika" | DADO_SAUDE "microcefalia"; DADO_SAUDE "síndrome congênita do Zika" | redator | cadeia associativa numa só expressão (conv. 1; precedente A-041) |
| B-004 | incluído | DADO_SAUDE "deficiência" | — | cega | "registro da deficiência de Pedro Henrique": condição da criança |
| B-004 | extensão corrigida | DADO_FINANCEIRO "R$ 400,00" | DADO_FINANCEIRO "R$ 400,00 mensais" | cega | valor sem qualificador (conv. 4) |
| B-004 | incluído | ID_PROCESSUAL "087/2025" | — | cega | número do relatório social da família (como a ficha de matrícula em B-005, consenso); título que o contém saiu dos públicos |
| B-005 | extensão corrigida | DADO_SAUDE "alergia grave a amendoim"; DADO_SAUDE "anafilaxia" | DADO_SAUDE "alergia grave a amendoim (já teve anafilaxia)" | cega | alergia e episódio de anafilaxia são achados distintos; valor sem parênteses |
| B-006 | extensão corrigida | DADO_FINANCEIRO "4471" | DADO_FINANCEIRO "Itaú final 4471" | cega | valor sem palavra-chave; o nome do banco é de pessoa jurídica |
| B-009 | extensão corrigida | QUASI_IDENTIFICADOR "assessor do vereador que preside a Comissão de Saúde da Câmara" | QUASI_IDENTIFICADOR "vereador que preside a Comissão de Saúde da Câmara" | redator | a pessoa implicada é o assessor; relação com titular de cargo único (precedente A-020) |
| B-010 | extensão corrigida | DADO_SAUDE "febre há 12 dias"; DADO_SAUDE "edema facial e de membros inferiores"; DADO_SAUDE "dispneia aos esforços" | DADO_SAUDE "febre há 12 dias, edema facial e de membros inferiores e dispneia aos esforços" | cega | achados distintos (conv. 2) |
| B-010 | extensão corrigida | DADO_SAUDE "benznidazol 100 mg de 8/8 h até completar 60 dias" | — | redator | posologia completa na 2ª ocorrência (conv. 3); "benznidazol" (consenso) segue cobrindo a 1ª |
| B-010 | incluído | DADO_SAUDE "transmissão oral por consumo de açaí não pasteurizado" | — | cega | via de infecção da doença da paciente |
| B-010 | incluído | DADO_SAUDE "hemograma"; DADO_SAUDE "enzimas hepáticas" | DADO_SAUDE "hemograma e enzimas hepáticas" | cega | exames prescritos à paciente; separados por não terem núcleo comum (conv. 2 estendida) |
| B-010 | incluído (omitido por ambos) | DADO_SAUDE "regressão do edema" | — | adjudicador | evolução clínica específica, coerente com as evoluções de B-039 |
| B-011 | incluído | DADO_SAUDE "muito confuso à noite" | DADO_SAUDE "fica muito confuso à noite" | cega | sintoma do paciente; sem o verbo de ligação, como "diabética" em B-001 |
| B-011 | incluído (omitido por ambos) | DADO_SAUDE "agitado" | — | adjudicador | sintoma do mesmo quadro ("quando ele ficava agitado") |
| B-012 | removido | — | DADO_SAUDE "Plano Educacional Individualizado" | redator | nome de instrumento pedagógico, não descreve condição; o diagnóstico (TDAH) já está anotado (precedente A-041, BPC); fica neutro |
| B-013 | extensão corrigida | DADO_SAUDE "tratamento para depressão" | DADO_SAUDE "está em tratamento para depressão no CAPSi" | cega | expressão do tratamento (conv. 3); CAPSi é serviço público e fica em públicos |
| B-013 | extensão corrigida | QUASI_IDENTIFICADOR "única aluna da turma que é mãe" | QUASI_IDENTIFICADOR "a única aluna da turma que é mãe" | cega | sem artigo inicial (conv. 6) |
| B-015 | extensão corrigida | DADO_SAUDE "hematoma periorbital à esquerda"; DADO_SAUDE "escoriações no antebraço direito" | DADO_SAUDE "hematoma periorbital à esquerda e escoriações no antebraço direito" | cega | lesões distintas (conv. 2) |
| B-015 | incluído (omitido por ambos) | DADO_SAUDE "alcoolizado" | — | adjudicador | estado de intoxicação do autor identificado; coerente com "hálito etílico" (B-060 consenso, A-028); dúvida registrada |
| B-016 | extensão corrigida | DADO_SENSIVEL "indígena da etnia Huni Kuin" | DADO_SENSIVEL "Huni Kuin" | cega | origem étnica completa (precedentes A-027 e A-049) |
| B-016 | extensão corrigida | ENDERECO "Aldeia Nova Fortaleza, casa 9" | ENDERECO "Aldeia Nova Fortaleza, casa 9, Terra Indígena Kaxinawá do Rio Jordão" | redator | endereço vai do logradouro ao complemento; a terra indígena é território, como o município (conv. 5) |
| B-016 | extensão corrigida | DADO_SAUDE "tosse produtiva há mais de três semanas"; DADO_SAUDE "febre vespertina"; DADO_SAUDE "perda de 6 kg" | DADO_SAUDE "tosse produtiva há mais de três semanas, febre vespertina e perda de 6 kg" | cega | achados distintos (conv. 2) |
| B-016 | extensão corrigida | DADO_SAUDE "teste rápido molecular detectável para Mycobacterium tuberculosis, sensível à rifampicina" | DADO_SAUDE "teste rápido molecular detectável para Mycobacterium tuberculosis"; DADO_SAUDE "sensível à rifampicina" | redator | um só exame com o seu resultado (precedente A-011; consenso "Pesquisa de Trypanosoma cruzi positiva…") |
| B-016 | incluído | DADO_SAUDE "tratamento diretamente observado" | — | cega | modalidade de tratamento do paciente |
| B-016 | incluído | DADO_SAUDE "radiografia de tórax" | — | cega | exame da esposa identificada |
| B-018 | extensão corrigida | DADO_SAUDE "fita para o aparelho de glicemia" | DADO_SAUDE "aparelho de glicemia" | cega | insumo de tratamento completo |
| B-019 | extensão corrigida | DADO_FINANCEIRO "R$ 700" | DADO_FINANCEIRO "uns R$ 700 por mês" | cega | valor sem qualificador (conv. 4) |
| B-019 | extensão corrigida | DADO_FINANCEIRO "5311-2"; DADO_FINANCEIRO "89145-2" | DADO_FINANCEIRO "agência 5311-2, conta corrente 89145-2" | redator | agência e conta como números separados, sem palavra-chave (padrão do ouro A) |
| B-019 | incluído | DADO_SAUDE "auxílio-doença" | — | cega | benefício que enuncia a condição da pessoa (precedente A-014) |
| B-020 | incluído | ID_PROCESSUAL "213/2025" | — | cega | número do relatório técnico sobre o idoso (como B-004); título que o contém saiu dos públicos |
| B-020 | extensão corrigida | DADO_FINANCEIRO "R$ 18.400,00" | DADO_FINANCEIRO "três empréstimos consignados que somam R$ 18.400,00"; DADO_FINANCEIRO "três empréstimos consignados" | cega | valor sem palavras-chave (conv. 4 e 8); "empréstimos consignados" descreve o dado |
| B-022 | extensão corrigida | DADO_SAUDE "humor deprimido persistente"; DADO_SAUDE "anedonia"; DADO_SAUDE "insônia terminal"; DADO_SAUDE "prejuízo importante de concentração" | DADO_SAUDE "humor deprimido persistente, anedonia, insônia terminal e prejuízo importante de concentração" | cega | sintomas distintos (conv. 2) |
| B-022 | extensão corrigida | DADO_SAUDE "quetiapina 50 mg à noite" | DADO_SAUDE "quetiapina 50 mg" | redator | posologia contígua (conv. 3) |
| B-022 | incluído | DADO_SAUDE "psicoterapia semanal" | — | cega | tratamento (precedente A-023, "acompanhamento fonoaudiológico semanal") |
| B-022 | incluído (omitido por ambos) | DADO_SAUDE "licença para tratamento de saúde" | — | adjudicador | licença que enuncia motivo de saúde (precedente A-025) |
| B-023 | extensão corrigida | ENDERECO "Passarela Liberdade, casa 31" | ENDERECO "Passarela Liberdade, casa 31, área de ressaca" | redator | "área de ressaca" é tipo de área, como "zona rural" (conv. 5) |
| B-023 | extensão corrigida | DADO_SAUDE "baixa visão no olho esquerdo, sequela de acidente de trabalho" | DADO_SAUDE "baixa visão no olho esquerdo"; DADO_SAUDE "sequela de acidente de trabalho" | redator | cadeia causal numa só expressão (conv. 1) |
| B-025 | extensão corrigida | QUASI_IDENTIFICADOR "cunhado do presidente da Câmara Municipal" | QUASI_IDENTIFICADOR "o cunhado do presidente da Câmara Municipal" | cega | sem artigo inicial (conv. 6) |
| B-025 | incluído | QUASI_IDENTIFICADOR "chefe de gabinete" | — | cega | cargo único na secretaria, ocupado por pessoa implicada na denúncia (assina o ponto da servidora) |
| B-026 | extensão corrigida | DADO_SAUDE "hepatite C diagnosticada em 2023, sem tratamento" | DADO_SAUDE "hepatite C" | redator | condição com os seus atributos (data do diagnóstico e ausência de tratamento), como "uso abusivo… há 12 anos" (consenso) |
| B-026 | incluído | DADO_SAUDE "acolhimento noturno por 10 dias" | — | cega | item do projeto terapêutico |
| B-026 | incluído | DADO_SAUDE "consulta psiquiátrica" | — | cega | tratamento psiquiátrico (precedente A-045) |
| B-026 | incluído | DADO_SAUDE "testagem rápida para HIV, sífilis e hepatites" | — | cega | exames do usuário; núcleo comum, uma só expressão |
| B-026 | incluído | DADO_SAUDE "grupo terapêutico" | — | cega | item do projeto terapêutico |
| B-027 | extensão corrigida | ENDERECO "Sítio Lagoa do Mato, s/n" | ENDERECO "Sítio Lagoa do Mato, s/n, zona rural" | cega | "zona rural" fica fora, como em B-004 (consenso) (conv. 5) |
| B-027 | extensão corrigida | DADO_FINANCEIRO "R$ 870,00" | DADO_FINANCEIRO "R$ 870,00 mensais" | cega | valor sem qualificador (conv. 4) |
| B-027 | incluído | DADO_SAUDE "não deambula" | — | cega | limitação funcional |
| B-027 | incluído | DADO_SAUDE "depende de terceiros para alimentação, higiene e locomoção" | — | cega | limitação funcional |
| B-029 | extensão corrigida | DADO_SAUDE "duas bengalas" | DADO_SAUDE "uso duas bengalas" | redator | sem o verbo, como "cadeira de rodas adaptada" (B-027 consenso) |
| B-030 | extensão corrigida | DADO_FINANCEIRO "350 reais" | DADO_FINANCEIRO "uns 350 reais por mes" | cega | valor sem qualificador (conv. 4) |
| B-030 | incluído (omitido por ambos) | DADO_SAUDE "nao posso pegar peso" | — | adjudicador | restrição médica decorrente da cirurgia cardíaca (precedente A-023) |
| B-031 | extensão corrigida | DADO_SAUDE "equimose arroxeada em região orbitária esquerda, medindo 4 x 3 cm" | DADO_SAUDE "equimose arroxeada em região orbitária esquerda" | redator | a medida integra a descrição da lesão, como "escoriação linear de 6 cm…" (consenso) e A-046 |
| B-031 | extensão corrigida | DADO_SAUDE "edema traumático no lábio superior"; DADO_SAUDE "ferida contusa suturada com três pontos" | DADO_SAUDE "edema traumático no lábio superior, com ferida contusa suturada com três pontos" | cega | lesões distintas (conv. 2) |
| B-031 | incluído | DADO_SAUDE "radiografia de tórax" | — | cega | exame da examinada |
| B-033 | incluído (omitido por ambos) | DADO_SAUDE "acompanhamento com a psiquiatra" | — | adjudicador | tratamento psiquiátrico do aluno (precedente A-045, "acompanhamento psiquiátrico") |
| B-034 | extensão corrigida | ENDERECO "Rua 1.034, Qd. 112, Lt. 08" | ENDERECO "Rua 1.034, Qd. 112, Lt. 08, Setor Pedro Ludovico" | cega | bairro fica fora (conv. 5) |
| B-036 | extensão corrigida | QUASI_IDENTIFICADOR "rapaz que fica na farmácia da UBS no turno da tarde" | QUASI_IDENTIFICADOR "o rapaz que fica na farmácia da UBS no turno da tarde" | cega | sem artigo inicial (conv. 6) |
| B-036 | extensão corrigida | NOME_PESSOA "Eliete" | NOME_PESSOA "dona Eliete" | cega | nome sem o tratamento, como "o servidor Paulo" → "Paulo" (diretrizes) |
| B-037 | extensão corrigida | DADO_SAUDE "tratamento com penicilina benzatina 7.200.000 UI, em três doses semanais" | DADO_SAUDE "penicilina benzatina 7.200.000 UI" | redator | expressão do tratamento com posologia (conv. 3) |
| B-037 | incluído | DADO_SAUDE "parto vaginal anterior sem intercorrências" | — | cega | antecedente obstétrico |
| B-037 | incluído | DADO_SAUDE "12/05/2025" | — | cega | data da última menstruação (DUM) |
| B-037 | incluído | DADO_SAUDE "16/02/2026" | — | cega | data provável do parto (DPP) |
| B-037 | incluído | DADO_SAUDE "hepatites B e C não reagentes" | — | cega | resultado de exame, coerente com "HIV não reagente" (consenso) |
| B-037 | incluído | DADO_SAUDE "Parceiro tratado" | — | cega | revela tratamento de sífilis do parceiro identificado |
| B-037 | incluído | DADO_SAUDE "VDRL de controle mensal" | — | cega | exame de seguimento da gestante |
| B-037 | incluído | DADO_SAUDE "pré-natal de alto risco" | — | cega | revela gestação de alto risco |
| B-039 | extensão corrigida | DADO_SAUDE "losartana"; DADO_SAUDE "metformina"; DADO_SAUDE "AAS" | DADO_SAUDE "losartana, metformina e AAS" | cega | medicamentos distintos (conv. 2 estendida) |
| B-039 | incluído | DADO_SAUDE "internação de 16 dias" | — | cega | internação do paciente, coerente com "duas internações anteriores…" (B-026 consenso) |
| B-039 | incluído | DADO_SAUDE "marcha com auxílio de bengala e base alargada" | — | cega | achado da avaliação |
| B-039 | incluído | DADO_SAUDE "alto risco de quedas" | — | cega | interpretação da escala de Berg |
| B-039 | incluído | DADO_SAUDE "dependência parcial para vestir-se e para o banho" | — | cega | limitação funcional |
| B-039 | incluído | DADO_SAUDE "Berg de 41/56" | — | cega | resultado de escala clínica |
| B-039 | incluído | DADO_SAUDE "fisioterapia duas vezes por semana por mais 90 dias" | DADO_SAUDE "fisioterapia duas vezes por semana" | cega | tratamento; a duração contígua entra (conv. 3) |
| B-039 | incluído | DADO_SAUDE "terapia ocupacional" | — | cega | tratamento |
| B-039 | incluído | DADO_SAUDE "fonoaudiologia" | — | cega | tratamento |
| B-039 | incluído (omitido por ambos) | DADO_SAUDE "ganho de amplitude de movimento no ombro direito"; DADO_SAUDE "melhora do controle de tronco"; DADO_SAUDE "marcha domiciliar sem bengala em curtas distâncias" | — | adjudicador | achados da evolução, do mesmo tipo dos da avaliação inicial que a cega anotou |
| B-040 | extensão corrigida | DADO_FINANCEIRO "4091-6"; DADO_FINANCEIRO "35.829-0" | DADO_FINANCEIRO "agência 4091-6, conta 35.829-0" | redator | números separados, sem palavra-chave (padrão do ouro A) |
| B-040 | extensão corrigida | DADO_FINANCEIRO "0001"; DADO_FINANCEIRO "8817245-3" | DADO_FINANCEIRO "agência 0001, conta 8817245-3" | redator | números separados, sem palavra-chave (padrão do ouro A) |
| B-041 | extensão corrigida | QUASI_IDENTIFICADOR "estudante transferido de Cambé em setembro" | QUASI_IDENTIFICADOR "o estudante transferido de Cambé em setembro" | cega | sem artigo inicial (conv. 6) |
| B-043 | extensão corrigida | DADO_SAUDE "sessões de radioterapia três vezes por semana" | DADO_SAUDE "sessões de radioterapia"; DADO_SAUDE "radioterapia três vezes por semana" | nova extensão | tratamento com a frequência contígua (conv. 3); união das duas extensões |
| B-043 | extensão corrigida | DADO_FINANCEIRO "R$ 1.300,00" | DADO_FINANCEIRO "R$ 1.300,00 mensais" | cega | valor sem qualificador (conv. 4) |
| B-043 | extensão corrigida | DADO_FINANCEIRO "R$ 23.000,00" | DADO_FINANCEIRO "dívida de R$ 23.000,00 em financiamento do Pronaf" | redator | valor sem palavras-chave (conv. 4); Pronaf é programa público |
| B-043 | extensão corrigida | DADO_SENSIVEL "filiada ao Sindicato dos Trabalhadores e Trabalhadoras Rurais do município" | DADO_SENSIVEL "filiada ao Sindicato dos Trabalhadores e Trabalhadoras Rurais" | cega | designação completa do sindicato (conv. 7) |
| B-044 | incluído | DADO_SAUDE "cadeira de rodas" | DADO_SAUDE "usa cadeira de rodas" | cega | sem o verbo, como em B-027 (consenso) e B-029 |
| B-045 | extensão corrigida | DADO_SAUDE "68 dB na orelha direita"; DADO_SAUDE "72 dB na orelha esquerda" | DADO_SAUDE "média dos limiares em 500, 1.000, 2.000 e 3.000 Hz de 68 dB na orelha direita e de 72 dB na orelha esquerda" | cega | medidas sem a descrição do método (conv. 4) e separadas por orelha (conv. 2) |
| B-045 | incluído | DADO_SAUDE "audiometria tonal liminar" | — | cega | exame da candidata |
| B-045 | incluído | DADO_SAUDE "leitura labial" | — | cega | modo de comunicação decorrente da deficiência |
| B-045 | incluído | DADO_SAUDE "deficiência auditiva" | — | cega | condição da candidata (precedente A-019) |
| B-045 | incluído (omitido por ambos) | DADO_SAUDE "pessoa com deficiência" | — | adjudicador | condição em que a candidata concorre (precedente A-029) |
| B-046 | extensão corrigida | DADO_SAUDE "quimioterapia para câncer de mama metastático" | DADO_SAUDE "quimioterapia"; DADO_SAUDE "câncer de mama metastático" | redator | "tratamento para X" numa só expressão (conv. 3) |
| B-046 | extensão corrigida | DADO_SAUDE "febre alta"; DADO_SAUDE "neutropenia" | DADO_SAUDE "febre alta e neutropenia" | cega | achados distintos (conv. 2) |
| B-047 | extensão corrigida | DADO_SAUDE "38 semanas e 4 dias" | DADO_SAUDE "IG de 38 semanas e 4 dias" | redator | medida sem palavra-chave (conv. 4), como "24 semanas" (B-037 consenso) |
| B-047 | extensão corrigida | DADO_SAUDE "nifedipino 20 mg de 12/12 h" | DADO_SAUDE "PA controlada com nifedipino 20 mg de 12/12 h"; DADO_SAUDE "nifedipino 20 mg" | nova extensão | medicamento com posologia (conv. 3), sem a frase de estado |
| B-047 | incluído | DADO_SAUDE "160 x 110 mmHg" | DADO_SAUDE "PA 160 x 110 mmHg" | cega | medida sem palavra-chave (conv. 4) |
| B-047 | incluído | DADO_SAUDE "indução do trabalho de parto" | — | cega | procedimento |
| B-047 | incluído | DADO_SAUDE "falha de indução" | — | cega | indicação clínica da cesariana |
| B-047 | incluído | DADO_SAUDE "Coombs indireto negativo" | — | cega | resultado de exame nomeado |
| B-047 | incluído | DADO_SAUDE "2.890 g" | DADO_SAUDE "peso 2.890 g" | cega | peso do recém-nascido sem palavra-chave (conv. 4) |
| B-047 | incluído | DADO_SAUDE "Apgar 8/9" | — | cega | escala clínica mantém o nome, como "escala de equilíbrio de Berg de 32/56" (consenso) |
| B-048 | extensão corrigida | DADO_SENSIVEL "indígena da etnia Warao" | DADO_SENSIVEL "Warao" | cega | origem étnica completa (precedente A-049) |
| B-048 | extensão corrigida | DADO_FINANCEIRO "R$ 300,00" | DADO_FINANCEIRO "ganho médio de R$ 300,00 por mês" | cega | valor sem qualificador (conv. 4) |
| B-048 | incluído (omitido por ambos) | DADO_SAUDE "acompanhamento nutricional" | — | adjudicador | tratamento da criança desnutrida (precedente A-049, "suporte nutricional hospitalar") |
| B-049 | incluído | DADO_SAUDE "internação de cinco dias" | — | cega | internação da aluna |
| B-050 | incluído | DADO_SAUDE "acompanhamento psicológico" | — | cega | tratamento (precedente A-045) |
| B-051 | extensão corrigida | QUASI_IDENTIFICADOR "único aluno cadeirante do 3º ano C" | QUASI_IDENTIFICADOR "o único aluno cadeirante do 3º ano C" | cega | sem artigo inicial (conv. 6) |
| B-052 | extensão corrigida | DADO_FINANCEIRO "6050-X"; DADO_FINANCEIRO "1876099-6" | DADO_FINANCEIRO "agência 6050-X, conta 1876099-6" | redator | números separados, sem palavra-chave (padrão do ouro A) |
| B-052 | incluído (omitido por ambos) | DADO_SAUDE "licença-maternidade"; DADO_SAUDE "Licença-maternidade" | — | adjudicador | licença ligada à gestação (precedente A-048, "licença à gestante"); a caixa alta do assunto exige entrada própria |
| B-055 | extensão corrigida | DADO_SAUDE "lesão por pressão estágio 3 em região sacral, medindo 5 x 4 cm, com tecido de granulação e pouco exsudato" | DADO_SAUDE "lesão por pressão estágio 3 em região sacral" | redator | uma só lesão com medida e características (coerente com B-031) |
| B-055 | extensão corrigida | DADO_SAUDE "curativo com hidrogel e placa de alginato de cálcio a cada 48 horas" | DADO_SAUDE "hidrogel e placa de alginato de cálcio"; DADO_SAUDE "curativo com hidrogel e placa de alginato de cálcio" | nova extensão | expressão do tratamento com a frequência contígua (conv. 3) |
| B-055 | incluído | DADO_SAUDE "Restrito ao leito há oito meses" | — | cega | limitação funcional |
| B-055 | incluído | DADO_SAUDE "colchão pneumático" | — | cega | dispositivo terapêutico |
| B-055 | incluído | DADO_SAUDE "dieta enteral" | — | cega | tratamento nutricional |
| B-055 | incluído (omitido por ambos) | DADO_SAUDE "mudança de decúbito a cada duas horas" | — | adjudicador | prescrição de cuidado do mesmo plano (curativo, colchão) |
| B-056 | extensão corrigida | DADO_SENSIVEL "terreiro de candomblé" | DADO_SENSIVEL "candomblé" | cega | prática religiosa da pessoa, como "mãe de santo" (consenso) |
| B-056 | incluído | DADO_SENSIVEL "filhos de santo" | — | cega | revela a religião de Rafael e Tainá |
| B-057 | removido | — | DADO_SAUDE "afastamento de 90 dias" | cega | duração de afastamento não descreve condição (precedentes A-023 e A-043); a cirurgia e o CID já estão anotados |
| B-057 | incluído (omitido por ambos) | DADO_SAUDE "licença para tratamento de saúde" | — | adjudicador | precedente A-025 |
| B-058 | extensão corrigida | QUASI_IDENTIFICADOR "coordenadora de enfermagem do plantão noturno de quarta-feira" | QUASI_IDENTIFICADOR "a coordenadora de enfermagem do plantão noturno de quarta-feira" | cega | sem artigo inicial (conv. 6) |
| B-058 | incluído | DADO_SENSIVEL "participei da paralisação de maio" | — | cega | atividade sindical da denunciante (greve), ao lado da filiação já anotada |
| B-059 | extensão corrigida | DADO_FINANCEIRO "R$ 300,00" | DADO_FINANCEIRO "renda estimada de R$ 300,00 por mês" | cega | valor sem qualificador (conv. 4) |
| B-060 | extensão corrigida | DADO_SAUDE "tomografia de crânio sem lesões intracranianas agudas" | DADO_SAUDE "sem lesões intracranianas agudas" | cega | exame e resultado numa só expressão (precedente A-011) |
| B-060 | extensão corrigida | DADO_SAUDE "radiografia de punho com fratura de rádio distal esquerdo" | DADO_SAUDE "fratura de rádio distal esquerdo" | nova extensão | exame e resultado com lateralidade, como a tomografia na mesma frase; "fratura de rádio distal" (consenso) segue cobrindo a hipótese diagnóstica |
| B-060 | incluído | DADO_SAUDE "Glasgow 14" | — | cega | escala clínica |

### 2.2 Convenções aplicadas

As oito convenções do lote A (`lote_a/adjudicacao.md`, 2.2) valem aqui sem mudança. As regras abaixo
as detalham para os casos que apareceram neste lote. Cada uma segue o que os anotadores já faziam nas
entidades de consenso, e todas foram aplicadas igualmente aos 60 documentos.

1. **Itens coordenados** (achados, sintomas, medicamentos, terapias, exames) vão em entradas
   separadas. Isso estende a conv. 2 do lote A. A exceção é quando um núcleo comum governa a lista,
   como em "testagem rápida para HIV, sífilis e hepatites", "hepatites B e C não reagentes" e
   "suplementação de ferro e vitamina A" (consenso). O precedente A-026, "terapias de ABA,
   fonoaudiologia e terapia ocupacional", também tem núcleo comum ("terapias de") e fica coerente
   com a regra.
2. **Uma só lesão ou condição com os seus atributos** é uma expressão. Os atributos são medida,
   lateralidade, características, data do diagnóstico e estado do tratamento. Exemplos: "equimose …
   medindo 4 x 3 cm", "lesão por pressão … com tecido de granulação e pouco exsudato" e "hepatite C
   diagnosticada em 2023, sem tratamento". Os precedentes de consenso são "escoriação linear de 6 cm
   na face anterior do antebraço direito" e "uso abusivo de crack e álcool há 12 anos". Lesões
   distintas ficam separadas.
3. **Exame e resultado** formam uma só expressão quando são contíguos, como em "tomografia de crânio
   sem lesões intracranianas agudas" e "teste rápido molecular … sensível à rifampicina" (precedente
   A-011). Um exame nomeado e realizado na pessoa identificada entra mesmo sozinho, como
   "radiografia de tórax" e "audiometria tonal liminar".
4. **Posologia** inclui dose, frequência e duração quando são contíguas ao medicamento ou à terapia,
   como em "nifedipino 20 mg de 12/12 h" e "fisioterapia duas vezes por semana por mais 90 dias".
   Isso aplica a conv. 3 do lote A.
5. **Verbo de ligação ou de uso** fica fora: "diabética", "muito confuso à noite", "duas bengalas",
   "cadeira de rodas". O precedente de consenso é "cadeira de rodas adaptada" (B-027). O verbo só
   entra quando é o próprio conteúdo, como em "não deambula" e "depende de terceiros para …".
6. **Medidas com unidade** ficam sem a palavra-chave, como em "38 semanas e 4 dias", "160 x 110
   mmHg", "2.890 g" e "68 dB na orelha direita". Isso aplica a conv. 4 do lote A. Já as
   **escalas clínicas** mantêm o nome ("Glasgow 14", "Apgar 8/9", "Berg de 41/56"), como no consenso
   "escala de equilíbrio de Berg de 32/56".
7. **Valores monetários** entram sem qualificadores ("mensais", "uns", "por mês", "renda estimada
   de", "dívida de", "empréstimos consignados que somam"). Agência e conta entram como números
   separados, sem "agência" e "conta", que é o padrão do ouro A. O nome do banco fica fora, porque é
   de pessoa jurídica.
8. **Nome de pessoa** entra sem pronome de tratamento ("Eliete", não "dona Eliete"), como no exemplo
   das diretrizes ("o servidor Paulo" → "Paulo").
9. **Número de relatório ou registro sobre pessoa ou família** é ID_PROCESSUAL. Isso vale para
   relatório social, relatório técnico, ficha de matrícula, laudo e prontuário. Atas, notas técnicas
   e comunicados sobre uma coletividade continuam públicos ("ATA Nº 18/2025", "NOTA TÉCNICA Nº
   14/2025", "COMUNICADO Nº 32/2025").
10. **Licenças que enunciam motivo de saúde** são DADO_SAUDE ("licença para tratamento de saúde",
    "licença-maternidade"), como em A-025 e A-048. A **duração de afastamento** não é, porque não
    descreve condição (A-023 e A-043).
11. **Origem étnica** entra por inteiro, como "indígena da etnia X" (A-027, A-049).
12. **Endereço** vai do logradouro ao complemento (conv. 5 do lote A). Ficam fora o bairro, o tipo de
    área ("zona rural", "área de ressaca") e o território ("Terra Indígena Kaxinawá do Rio Jordão",
    que fica em públicos).

### 2.3 Trechos públicos

Os públicos divergiram em 55 documentos (F1 0,7478). Como no lote A, a divergência é quase toda de
**granularidade**: o redator listava unidades ("Lei nº 11.340/2006", "Lei Maria da Penha") e a cega,
compostos ("Lei nº 11.340/2006 (Lei Maria da Penha)"), ou o contrário. Apliquei o mesmo tratamento do
lote A:

1. união das duas listas (581 trechos);
2. 32 datas de fecho ("Município, D de mês de AAAA") separadas em município e data;
3. retirada de 45 compostos formados só por unidades já presentes, ligadas por separadores ("—",
   "/", parênteses, vírgula) ou conectivos ("da", "de", "do"…). Compostos com partes que não estão na
   lista ficaram ao lado das unidades, por exemplo "Estação Faria Lima da Linha 4-Amarela do metrô",
   "art. 16 da Lei nº 13.460/2017" e "Diário Oficial do Município nº 1.832, de 3 de março de 2025";
4. retirada justificada de 3 trechos e normalização de 1:
   - B-004 "RELATÓRIO SOCIAL DE VISITA DOMICILIAR Nº 087/2025" e B-020 "RELATÓRIO TÉCNICO Nº 213/2025"
     contêm números de relatório que passaram a ID_PROCESSUAL;
   - B-037 "teste do pezinho" é exame ligado à gestante e ao recém-nascido e fica neutro;
   - B-036 "Município: Parintins" virou "Parintins";
5. verificação de conflito: nenhum trecho público coincide com um valor pessoal nem se sobrepõe a
   qualquer ocorrência dele. Também verifiquei que todo público ocorre no texto.

Resultado: **565** trechos públicos (581 − 45 − 3 + 32). Os trechos que testam tarja indevida de
nomes dentro de instituições continuam no conjunto, por exemplo "Hospital Geral Roberto Santos",
"EMEF Vereador Antônio Giúdice", "Escola Estadual Professora Esther da Silva Virgolino", "Hospital
Regional Dr. Abelardo Santos", "Unidade de Acolhimento Zilda Arns", "Centro de Referência de Combate
ao Racismo e à Intolerância Religiosa Nelson Mandela" e "Avenida Bezerra de Menezes". O mesmo vale
para os documentos só com dados agregados (B-008, B-014, B-021, B-028, B-035, B-038, B-042, B-053),
que medem a precisão sem nenhuma entidade pessoal. Também continuam no conjunto o telefone e os
e-mails institucionais ("(34) 3218-2300", "matriculas@educacao.rn.gov.br").

## 3. Casos difíceis

1. **B-025 "chefe de gabinete"** (só a cega). As diretrizes mandam deixar públicos os "cargos sem
   nome" e tratar o "cargo único" como quase-identificador. Aqui o cargo é único na Secretaria
   Municipal de Saúde de Gurupi, e quem o ocupa é acusada de assinar o ponto de outra servidora.
   Incluí como QUASI_IDENTIFICADOR, pela regra da dúvida. **Sugestão:** as diretrizes deveriam dizer
   que um cargo sem nome passa a quase-identificador quando o texto atribui uma conduta a quem o ocupa.
2. **B-009, extensão do quase-identificador.** A cega marcou só "vereador que preside a Comissão de
   Saúde da Câmara". O redator marcou "assessor do vereador que preside…". Fiquei com a do redator:
   a pessoa implicada é o assessor, identificável pela relação com o titular de um cargo único, como
   em A-020 ("engenheiro fiscal do contrato que é irmão do Prefeito de Jucurutu"). A extensão
   escolhida contém a da cega.
3. **B-058 "participei da paralisação de maio"** (só a cega). Participar de greve é atividade
   sindical e não está literalmente no rol "filiação sindical". Incluí como DADO_SENSIVEL, ao lado da
   filiação já anotada, pela regra da dúvida.
4. **B-015 "alcoolizado"** (omitido pelos dois). É o estado de intoxicação do autor identificado.
   Incluí por coerência com "hálito etílico" (B-060, consenso; A-028), com dúvida, porque também
   pode ser lido como circunstância do crime.
5. **B-037, datas da gestação.** DUM ("12/05/2025") e DPP ("16/02/2026") são datas, mas datas
   clínicas da gestante. Incluí como DADO_SAUDE, coerente com a idade gestacional "24 semanas"
   (consenso). Pelo mesmo motivo, "teste do pezinho" saiu dos públicos.
6. **B-004 e B-020, números de relatório** (só a cega). O redator tinha posto os títulos com número
   em públicos. Como a ficha de matrícula de B-005 foi marcada como ID_PROCESSUAL por consenso, e A-002
   seguiu a mesma linha, os números passaram a ID_PROCESSUAL e os títulos saíram dos públicos.
7. **Afastamento e licença** (B-022, B-057). A cega marcou "afastamento de 90 dias" em B-057.
   Removi, porque a duração não descreve condição e o lote A não anotou afastamentos (A-023, A-043).
   Pelo mesmo motivo não incluí "afastamento de suas atividades laborais por 60 (sessenta) dias"
   (B-022). Já "licença para tratamento de saúde" (B-022, B-057) e "licença-maternidade" (B-052),
   omitidas pelos dois, entraram pelos precedentes A-025 e A-048. **Sugestão:** as diretrizes
   deveriam dizer expressamente se licenças e afastamentos médicos contam como DADO_SAUDE.
8. **B-012 "Plano Educacional Individualizado"** (só o redator). É nome de instrumento pedagógico e
   não descreve condição; o diagnóstico (TDAH) já está anotado. Removi e deixei o trecho neutro,
   como o lote A fez com o BPC (A-041). O "Atendimento Educacional Especializado" continua público,
   como no consenso de B-032.
9. **Resultados normais ou negativos.** Ficaram anotados quando o exame trata de um agente nomeado
   ("HIV não reagente", consenso; "hepatites B e C não reagentes"; "Coombs indireto negativo") ou
   quando forma uma só expressão com o exame ("tomografia de crânio sem lesões intracranianas
   agudas"). Ficaram **neutros** quando aparecem separados do exame e não revelam condição: "sem
   alterações" (B-016), "sem sinais de fratura" (B-031), "sem disfunção ventricular" (B-010) e "sem
   sinais de infecção" (B-055). **Sugestão:** fixar a regra nas diretrizes.
10. **B-020 "três empréstimos consignados"** (só a cega). Pela conv. 8 do lote A, entra o valor
    ("R$ 18.400,00"), e a descrição da dívida é palavra-chave. Apliquei o mesmo em B-043 ("dívida de …
    em financiamento do Pronaf" → "R$ 23.000,00"; Pronaf é público).
11. **B-052, caixa alta.** "Licença-maternidade" aparece com maiúscula nos assuntos dos e-mails e com
    minúscula no corpo. Como a comparação diferencia maiúsculas e minúsculas, cada forma tem entrada
    própria (o mesmo foi feito em A-033).
12. **B-019 "auxílio-doença"** (só a cega). É o nome antigo do benefício que o lote A tratou como
    saúde ("auxílio por incapacidade temporária", A-014), e por isso foi incluído.
13. **B-039, evolução clínica** (omitida pelos dois). A cega marcou os achados da avaliação inicial
    e o "Berg de 41/56" da evolução, mas não os demais achados da evolução. Incluí "ganho de amplitude
    de movimento no ombro direito", "melhora do controle de tronco" e "marcha domiciliar sem bengala
    em curtas distâncias" para que o documento ficasse coerente. Pelo mesmo motivo incluí "regressão
    do edema" (B-010).

Considerados e **não anotados** (ficam neutros, nem pessoais nem públicos):
- passos genéricos de cuidado: "analgesia", "observação neurológica por seis horas" e "retorno ao
  ambulatório de ortopedia" (B-060); "avaliação clínica" (B-026); "acompanhamento domiciliar"
  (B-043); "aleitamento materno exclusivo" e "revisão do puerpério" (B-047); "repouso" (B-052);
  "adesão irregular" (B-059);
- exames sem resultado e sem pessoa identificada, ou de rotina: "prova tuberculínica" (contatos não
  nomeados) e "baciloscopia do 2º mês" (B-016); "exame de corpo de delito" (B-015, procedimento
  pericial); "Ecocardiograma" (B-010, cujo achado já está anotado); "seguimento da criança exposta"
  (B-037, porque a sífilis materna já está anotada);
- nacionalidade e naturalidade ("venezuelano", B-024; "procedente de Tucupita, Venezuela", B-048;
  "natural de Santa Maria/RS", B-059): nenhum rótulo cobre. **Sugestão:** avaliar se a condição de
  migrante deve entrar em DADO_SENSIVEL ou em QUASI_IDENTIFICADOR;
- situação de rua ou sem domicílio fixo (B-026, B-059), estado civil, ocupação, escolaridade e
  desempenho escolar (B-013, B-041): sem rótulo;
- condição de vítima (B-015, B-031, B-033, B-050): o conjunto de rótulos não a cobre, como já se
  registrou no lote A;
- bairros, municípios e datas de internação, de alta e dos fatos: convenção dos dois anotadores,
  mantida.

## 4. Pendências

- O congelamento (passo 4 das diretrizes) **não foi executado**, porque depende da aprovação desta
  adjudicação.
- A concordância antes da adjudicação está registrada em `lote_b/divergencias.jsonl`.
- Sugestões para a próxima revisão das diretrizes (casos 1, 7 e 9 e a nacionalidade):
  quase-identificador por cargo com conduta atribuída, licenças e afastamentos, resultados normais
  e condição de migrante.
