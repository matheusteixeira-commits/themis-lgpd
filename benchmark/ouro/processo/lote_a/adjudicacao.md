# Adjudicação do lote A

Arquivo final: `ouro/ouro_a.jsonl` (60 documentos, 523 entidades, 836 trechos públicos).
Validação (`ferramentas.py validar`): **sem problemas**.

Este documento registra a concordância antes de qualquer decisão, cada decisão tomada e os casos
difíceis, conforme o passo 3 das `DIRETRIZES.md`. Nenhum código de sistema de anonimização foi lido
ou executado; apenas `benchmark/ouro/ferramentas.py`, que não importa nenhum sistema de anonimização.

## 1. Concordância antes da adjudicação

Comando: `ferramentas.py concordancia anotacao_redator.jsonl anotacao_cega.jsonl --divergencias divergencias.jsonl`

| Medida | Valor |
|---|---|
| Documentos | 60 |
| Documentos com divergência (entidades **ou** públicos) | **59** |
| … com divergência nas entidades | 23 (todos também divergem nos públicos) |
| … com divergência nos públicos | 59 (36 deles só nos públicos) |
| **F1 por rótulo** (tipo + valor) | **0,9563** |
| **F1 por valor** (só o valor) | **0,9563** |
| Entidades: redator / cega / em comum | 516 / 513 / 492 |
| Valores divergentes: só redator / só cega | 24 / 21 |
| Públicos: redator / cega / em comum (F1) | 673 / 761 / 504 (0,7029) |

O F1 por rótulo e o F1 por valor são iguais. Isso significa que **não houve nenhuma divergência só de
rótulo**: quando os anotadores marcaram o mesmo trecho, deram o mesmo rótulo. Todas as divergências
são de **extensão** (o mesmo dado delimitado de outro modo) ou de **inclusão** (dado visto por um só
anotador).

Concordância por rótulo antes da adjudicação:

| Rótulo | Redator | Cega | Comum | F1 |
|---|---:|---:|---:|---:|
| NOME_PESSOA | 172 | 172 | 172 | 1,0000 |
| DOC_PESSOAL | 53 | 53 | 53 | 1,0000 |
| DOC_PROFISSIONAL | 59 | 59 | 59 | 1,0000 |
| CONTATO | 34 | 34 | 34 | 1,0000 |
| DATA_NASC | 20 | 20 | 20 | 1,0000 |
| ID_VEICULO | 5 | 5 | 5 | 1,0000 |
| ID_PROCESSUAL | 39 | 40 | 39 | 0,9873 |
| ENDERECO | 31 | 31 | 29 | 0,9355 |
| DADO_FINANCEIRO | 30 | 25 | 25 | 0,9091 |
| QUASI_IDENTIFICADOR | 5 | 5 | 4 | 0,8000 |
| DADO_SAUDE | 57 | 58 | 44 | **0,7652** |
| DADO_SENSIVEL | 11 | 11 | 8 | **0,7273** |

Os identificadores estruturados (nomes, documentos, contatos, datas, placas) tiveram concordância
perfeita. A divergência se concentra nos rótulos descritivos: saúde, dado sensível e
quase-identificador, cuja extensão depende de julgamento, e nos valores monetários.

## 2. Decisões

| Tipo de decisão | Nº | Valores divergentes resolvidos |
|---|---:|---:|
| **Incluído**, a partir de divergência | 14 | 14 (10 vistos só pelo redator, 4 só pela cega) |
| **Incluído**, dado omitido por ambos | 2 | — |
| **Removido** (não é dado pessoal) | 0 | — |
| **Rótulo corrigido** | 0 | — |
| **Extensão corrigida** | 14 | 31 (9 a favor do redator, 4 a favor da cega, 1 nova extensão) |
| **Total de decisões sobre entidades** | **30** | **45 de 45** |
| Trecho público retirado (neutralizado) | 2 | — |

Nenhuma entidade de consenso foi removida nem teve o rótulo trocado. Revi documento a documento as
entidades em que os dois anotadores concordaram e não encontrei falso positivo.

Concordância de cada anotador com o conjunto adjudicado, para referência:

| Anotador | Precisão | Revocação | F1 |
|---|---:|---:|---:|
| Redator | 0,9903 | 0,9771 | 0,9836 |
| Cega | 0,9766 | 0,9579 | 0,9672 |

### 2.1 Tabela de decisões

| Doc | Decisão | Valor final | Descartado | Origem | Motivo |
|---|---|---|---|---|---|
| A-001 | extensão corrigida | DADO_SAUDE "adalimumabe 40 mg a cada 14 dias" | "adalimumabe 40 mg" | redator | posologia integra o tratamento prescrito; regra: expressão clínica contígua completa |
| A-002 | incluído | ID_PROCESSUAL "0081234567" | — | cega | número de documento SEI no processo da pessoa (evento com a CTC); na dúvida, pessoal |
| A-003 | extensão corrigida | ENDERECO "Rua Rio Purus, 72, Conjunto Vieiralves" | "Rua Rio Purus, 72" | redator | conjunto habitacional é complemento; endereço vai do logradouro ao complemento |
| A-005 | extensão corrigida | DADO_SAUDE "cirurgia de catarata no olho esquerdo" | "catarata no olho esquerdo" | redator | procedimento aguardado faz parte da informação de saúde (tratamento) |
| A-005 | incluído | DADO_SAUDE "diálise peritoneal" | — | cega | tratamento de pessoa identificável (única paciente do distrito), aninhado no quase-identificador |
| A-008 | incluído | DADO_FINANCEIRO "R$ 3.200,00" | — | redator | aluguel recebido por pessoa natural = renda de pessoa identificável |
| A-009 | extensão corrigida | QUASI_IDENTIFICADOR "única pediatra da unidade, afastada desde março" | "a única pediatra da unidade, afastada desde março"; "única pediatra da unidade" | nova extensão | identificador + atributo revelado (afastamento), sem artigo inicial, como nos demais quase-identificadores |
| A-011 | extensão corrigida | DADO_SAUDE "teste de alcoolemia do condutor teve resultado negativo" | "teste de alcoolemia" | redator | exame e resultado ligados à pessoa; o resultado é o dado de saúde |
| A-014 | incluído | DADO_SAUDE "auxílio por incapacidade temporária" | — | cega | benefício concedido à pessoa nomeia sua condição (incapacidade temporária) |
| A-019 | incluído | DADO_FINANCEIRO "R$ 700,00" | — | redator | bolsa mensal = renda de pessoa identificável |
| A-022 | extensão corrigida | ENDERECO "Rua CC-14, 237, Conjunto Cidadão" | "Rua CC-14, 237" | redator | conjunto habitacional é complemento (mesma regra de A-003) |
| A-023 | incluído | DADO_SAUDE "restrição ao uso intensivo da voz" | — | redator | restrição médica decorrente do diagnóstico |
| A-025 | incluído | DADO_SAUDE "licença por motivo de doença em pessoa da família" | — | redator | revela doença de familiar identificado; coerente com "licença para tratamento de saúde" (consenso) |
| A-027 | incluído | DADO_SENSIVEL "guardar o sábado como dia sagrado" | — | cega | prática religiosa ligada à pessoa |
| A-029 | extensão corrigida | DADO_SAUDE "pessoa com deficiência" | "vaga reservada a pessoa com deficiência" | cega | anotar a condição sem a palavra-chave ("vaga reservada a") |
| A-029 | extensão corrigida | DADO_SENSIVEL "candidatos negros" | "vaga reservada a candidatos negros" | cega | anotar a origem racial sem a palavra-chave ("vaga reservada a") |
| A-031 | público retirado | — | "Campus I" | — | nova lotação de vítima de violência doméstica, cujo sigilo o próprio memorando pede; neutro (nem pessoal nem público) |
| A-031 | público retirado | — | "Salvador" | — | a 2ª ocorrência ("em Salvador") revela a cidade da nova lotação sigilosa; neutro |
| A-033 | incluído | DADO_SENSIVEL "UNIÃO ESTÁVEL HOMOAFETIVA" | — | redator | ementa de parecer sobre pessoa nomeada revela orientação sexual; caixa distinta exige entrada própria |
| A-038 | extensão corrigida | DADO_SAUDE "usuária de cadeira de rodas em razão de mielomeningocele" | "usuária de cadeira de rodas"; "mielomeningocele" | redator | cadeia causal numa só expressão, como "baixa visão decorrente de retinopatia" (consenso) |
| A-046 | extensão corrigida | DADO_SAUDE "tratamento para hipertensão arterial" | "hipertensão arterial" | redator | coerente com "tratamento para dependência de álcool" (consenso em A-028) |
| A-048 | extensão corrigida | DADO_SENSIVEL "mandato classista no Sindicato dos Trabalhadores em Educação de Rondônia – SINTERO" | "mandato classista no Sindicato dos Trabalhadores em Educação de Rondônia" | redator | a sigla, se ficasse legível, revelaria o sindicato |
| A-048 | incluído (omitido por ambos) | DADO_SAUDE "licença à gestante" | — | adjudicador | gestação é dado de saúde (estado fisiológico); coerente com "licença para tratamento de saúde"; dúvida registrada |
| A-049 | extensão corrigida | DADO_SAUDE "8,1 kg" | "peso de 8,1 kg" | cega | valor sem a palavra-chave ("peso de") |
| A-049 | incluído | DADO_SAUDE "esquema de tratamento antimalárico" | — | redator | tratamento ligado à criança identificada |
| A-049 | extensão corrigida | DADO_SAUDE "anemia importante"; DADO_SAUDE "baixa aceitação alimentar" | "anemia importante e baixa aceitação alimentar" | cega | achados distintos coordenados por "e" ficam separados, como em A-022 (consenso) |
| A-049 | incluído (omitido por ambos) | DADO_SAUDE "suporte nutricional hospitalar" | — | adjudicador | tratamento indicado para a criança identificada |
| A-050 | incluído | DADO_FINANCEIRO "R$ 120,00" | — | redator | valor da hora-aula paga a pessoa natural = renda |
| A-050 | incluído | DADO_FINANCEIRO "R$ 4.800,00" | — | redator | total pago a pessoa natural = renda |
| A-054 | extensão corrigida | DADO_SAUDE "cadeirante em razao de amputacao transfemoral esquerda decorrente de complicacoes do diabetes" | "cadeirante"; "amputacao transfemoral esquerda decorrente de complicacoes do diabetes" | redator | cadeia causal numa só expressão (mesma regra de A-038) |
| A-059 | incluído | DADO_FINANCEIRO "R$ 14.860,00" | — | redator | valor do compromisso com agricultor (pessoa natural) = renda |
| A-060 | incluído | DADO_SAUDE "plena capacidade de entendimento à época dos fatos" | — | redator | resultado de exame de sanidade mental ligado à pessoa |

### 2.2 Convenções de extensão fixadas nesta adjudicação

Estas regras detalham as diretrizes e foram aplicadas igualmente a todos os documentos. Cada uma segue
o que os dois anotadores já faziam nas entidades de consenso.

1. **Saúde, cadeia causal ou associativa**: uma só expressão ("X decorrente de Y", "X em razão de Y",
   "X por Y", "X associada a Y"). Precedentes de consenso: "baixa visão decorrente de retinopatia da
   prematuridade", "fratura de fêmur decorrente de acidente de moto", "disfonia crônica por nódulos
   bilaterais em pregas vocais".
2. **Saúde, achados ou diagnósticos distintos coordenados por "e"**: entradas separadas. Precedente:
   A-022, "insuficiência renal aguda" e "diabetes mellitus tipo 2 descompensado".
3. **Tratamento**: entra a expressão que o descreve, incluindo "tratamento para …" e a posologia
   quando ela é contígua ao medicamento. Precedentes: "tratamento para dependência de álcool" e
   "tratamento oncológico".
4. **Medidas e categorias**: ficam fora as palavras-chave ("peso de", "vaga reservada a"), como já se
   faz com "CPF" e "nascida em".
5. **Endereço**: vai do logradouro ao complemento. Conjunto habitacional conta como complemento.
   Bairro, município e UF não entram (os dois anotadores fizeram assim em todos os documentos).
6. **Quase-identificador**: entra o identificador mais o atributo revelado, sem artigo inicial.
7. **Sindicato ou partido**: a sigla em aposição entra no trecho, porque, se ficasse legível,
   revelaria o dado.
8. **Valores monetários recebidos por pessoa natural** (salário, bolsa, aluguel, cachê, venda ao
   PAA, prejuízo alegado): DADO_FINANCEIRO. Valores agregados ou recebidos por pessoa jurídica
   (verbas da escola, total de diárias, lotes de pregão) são públicos.

### 2.3 Trechos públicos

Os públicos divergiram em 59 documentos (F1 0,7029), quase sempre por **granularidade**, não por
mérito. O redator usava blocos compostos ("Caruaru, 18 de agosto de 2025", "São Paulo Previdência –
SPPREV"); a cega usava unidades ("Caruaru", "18 de agosto de 2025", "SPPREV"). Tratamento aplicado:

1. união das duas listas;
2. datas de fecho ("Município, D de mês de AAAA") separadas em município e data;
3. retirada de cada composto formado só por unidades já presentes, ligadas por separadores ou
   conectivos (95 compostos retirados). Compostos com partes que não estão na lista (por exemplo
   "Rodovia BR-262, km 0, Jardim América, Cariacica/ES") foram mantidos ao lado das unidades;
4. retirada justificada de 2 trechos (A-031, ver casos difíceis);
5. verificação de conflito: nenhum trecho público coincide com valor pessoal nem se sobrepõe a
   qualquer ocorrência de valor pessoal. Também nenhum valor pessoal ocorre em contexto público no
   mesmo texto.

Resultado: 836 trechos públicos (930 na união − 95 compostos − 2 retirados + 3 unidades separadas de
datas de fecho). Os trechos que testam tarja indevida de nomes dentro de instituições
continuam no conjunto, por exemplo "Hospital Regional João Penido", "Escola Estadual Senador Petrônio
Portella", "Avenida Getúlio Vargas", "Hospital Geral de Roraima Rubens de Souza Bento" e "Casa da
Cultura Fausto Rocha Júnior". O mesmo vale para os dados de saúde agregados ("21.384 casos suspeitos
de dengue", "1.946 casos de sífilis em gestantes") e para a tese "união homoafetiva como entidade
familiar".

## 3. Casos difíceis

1. **Valores pagos por ente público a pessoa natural** (A-008 aluguel, A-019 bolsa, A-050 hora-aula e
   total, A-059 venda ao PAA). Esses valores são, ao mesmo tempo, renda de pessoa identificável e
   despesa pública sujeita a transparência ativa. Segui a diretriz ("renda… de pessoa identificável";
   na dúvida, pessoal) e a coerência com os casos de consenso: remuneração de temporário (A-035),
   salário (A-006) e até a remuneração de A-039, que o próprio texto declara pública (STF, ARE
   652.777) e que os dois anotadores marcaram. O dado continua pessoal mesmo quando a divulgação é
   obrigatória. **Sugestão:** as diretrizes deveriam dizer se esse tipo de valor deve ser medido como
   dado pessoal ou como trecho que pode ficar legível, porque a escolha muda a revocação de
   DADO_FINANCEIRO.
2. **A-048 "licença à gestante"** (omitida pelos dois). Gestação é estado fisiológico e, pela LGPD,
   dado de saúde. Os dois anotadores já haviam marcado "licença para tratamento de saúde" e "licença
   por motivo de doença em pessoa da família". Incluí, com dúvida, porque o rol de DADO_SAUDE das
   diretrizes não cita gestação.
3. **A-031, nova lotação de vítima de violência doméstica.** O memorando pede sigilo da nova lotação
   ("Campus I", "em Salvador"). Nenhum rótulo cabe, porque o nome já identifica a pessoa e o trecho
   apenas a localiza. Retirei os dois trechos dos públicos (ficam neutros) para não punir como tarja
   indevida quem os tarjar. "Salvador" saiu inteiro porque a regra conta toda ocorrência, inclusive
   a da data de fecho.
4. **A-014 "auxílio por incapacidade temporária"** (só a cega). É nome de benefício, mas, concedido a
   pessoa nomeada, enuncia a condição dela (incapacidade). Já o "Benefício de Prestação Continuada"
   (A-041) continua público: é nome de programa, não descreve condição, e o diagnóstico está anotado
   à parte.
5. **A-033 ementa em caixa alta.** "UNIÃO ESTÁVEL HOMOAFETIVA" aparece numa ementa, que costuma ser
   publicada como tese, mas num parecer sobre pessoa nomeada. A comparação diferencia maiúsculas e
   minúsculas, por isso a forma em caixa alta precisa de entrada própria.
6. **A-002 "evento 0081234567".** É número de documento SEI dentro do processo da pessoa (o
   documento é a CTC dela). Não é número de processo em sentido estrito; incluí pela regra da dúvida.
7. **A-009 quase-identificador.** Nenhuma das duas extensões ficou: adotei uma terceira, que
   inclui o atributo revelado ("afastada desde março", em contexto de licença médica) e tira o
   artigo inicial, como nos outros quatro quase-identificadores do lote.
8. **A-005 "diálise peritoneal" dentro do quase-identificador.** Mantive as duas anotações: o
   quase-identificador é rótulo de alerta, e o tratamento é dado de saúde de pessoa identificável.
9. **A-060 "plena capacidade de entendimento à época dos fatos".** É resultado de exame de sanidade
   mental, portanto "resultado ligado a pessoa", embora favorável a ela.

Considerados e **não anotados**, por não caberem em nenhum rótulo ou por serem genéricos:
- beneficiário do Bolsa Família (A-013) e do BPC (A-041): nomes de programa, que ficam públicos;
- "foi submetido a cirurgia" (A-043): evento assistencial genérico, como "internado" e "atendida",
  que nenhum anotador marcou;
- "motivo religioso" (A-027): a religião já está anotada;
- pedido de apoio a pré-candidato (A-053): a filiação partidária já está anotada;
- condição de custodiado (A-055) e de vítima de violência (A-031, A-041): o conjunto de rótulos não
  cobre dado criminal nem condição de vítima. **Sugestão:** avaliar um rótulo para isso nas
  diretrizes;
- bairros: convenção dos dois anotadores, mantida.

## 4. Pendências

- Congelamento (passo 4 das diretrizes) **não executado**: depende da aprovação desta adjudicação.
- Os resultados intermediários estão em `lote_a/divergencias.jsonl`, que registra a concordância
  antes da adjudicação.
