# Lote R4 — armadilhas de precisão: sondagem do sistema

Lote adversarial de 30 documentos públicos fictícios (R4-001 a R4-030), densos em informação que deve
ficar legível e com poucos dados pessoais verdadeiros. Cobre as 27 UFs e os gêneros extrato de diário
oficial, edital (inclusive de leilão e de processo seletivo), aviso de licitação, extrato de contrato,
de convênio, de ata de registro de preços e de TAC, ata de sessão de licitação e de conselho, relatório
de gestão, prestação de contas, lei, decreto e decreto legislativo, nota técnica, boletim
epidemiológico e informativo, resposta a pedido de acesso à informação, comunicado à imprensa e
relatório de fiscalização de obra (227 a 497 palavras por documento).

* Anotação: `anotacao_redator.jsonl` (116 entidades, 1.083 trechos públicos), feita nos modelos de
  `geracao/` antes de cada execução do sistema; `ferramentas.py validar` → "sem problemas".
* Geração: `geracao/comum.py` (CPF, CNPJ, RENAVAM, chave de NF-e, número CNJ com dígitos verificadores;
  leitura da marcação; conferência de sobreposição entre trecho pessoal e público), `lote_r1.py`,
  `lote_r2.py`, `montar.py`.
* Avaliação: perfil `lai`; métricas em `.trabalho/metricas_R4_r1.json` e
  `.trabalho/metricas_R4_final.json`, erros em `.trabalho/erros_R4_r1.jsonl` e
  `.trabalho/erros_R4_final.jsonl`. Os 15 primeiros documentos produziram exatamente os mesmos erros
  nas duas execuções.

## Métricas agregadas

| Métrica | Rodada 1 (R4-001 a 015) | Final (R4-001 a 030) |
|---|---:|---:|
| Entidades pessoais anotadas | 61 | 116 |
| Recall de entidades | 1,000 | 0,991 |
| Recall estrito | 1,000 | 0,983 |
| Documentos com vazamento | 0,0% (0/15) | 3,3% (1/30) — IC95% 0–10% |
| Precisão das tarjas | 0,414 (IC95% 0,324–0,519) | 0,364 (IC95% 0,305–0,427) |
| Tarja fora do gabarito | 50,9% | 56,9% |
| Preservação dos trechos públicos | 0,880 (IC95% 0,851–0,912) | 0,848 (IC95% 0,820–0,875) |
| Tarjas fora do gabarito (trechos) | 92 | 210 |
| Ocorrências de trechos públicos tarjados | 78 | 188 |
| Documentos com algum trecho público tarjado | 14/15 | 29/30 |

Só na rodada 2 (R4-016 a 030): 118 tarjas fora do gabarito, 110 ocorrências de trechos públicos
tarjados (15/15 documentos) e 1 vazamento.

## Classes de falha

Contagem = trechos tarjados indevidamente (ou entidades vazadas) na execução final, separados por
rodada. Os exemplos são fictícios e curtos, escritos para ilustrar a forma, não copiados do lote.

### Vazamento

| # | Forma | R1 | R2 | Total | Exemplo fictício |
|---|---|---:|---:|---:|---|
| V1 | Condição de saúde atribuída a pessoa descrita só por quase-identificador (sem nome, documento nem marcador de primeira pessoa), com termo fora do vocabulário clínico | 0 | 1 | 1 | "o único vigia da escola do ramal Boa Fé foi levado ao hospital com suspeita de malária" — o quase-identificador é sinalizado, a doença fica legível |

### Tarja indevida

| # | Forma | R1 | R2 | Total | Exemplo fictício |
|---|---|---:|---:|---:|---|
| T1 | Nome de pessoa no nome próprio de embarcação (lancha, B/M, N/M, ferry-boat, barco de saúde, barco escolar) | 6 | 3 | 9 | "reforma do B/M Comandante Josias Arruda" |
| T2 | Nome de pessoa em equipamento, programa, honraria ou entidade fora dos padrões já reconhecidos: praça, ginásio sem título, mercado com "Seu", plenário, orquestra, coral com nome estrangeiro, conjunto habitacional, bolsa, operação policial, política citada na forma curta, entidade em caixa alta no cabeçalho | 3 | 10 | 13 | "Plenário Vereador Nestor Brambilla"; "Operação Maria Bonita"; "Bolsa Atleta Municipal Zé Tonico"; "INSTITUTO DE IDENTIFICAÇÃO DELEGADO JOSÉ FULGÊNCIO" |
| T3 | Nome de escola abreviado em caixa alta em linha de tabela | 0 | 4 | 4 | "E.M.E.F. PROF.ª ODETE MARQUES \| 1.112" |
| T4 | Logradouro público citado sem o tipo: enumeração após "ruas", rua como sujeito da oração | 0 | 7 | 7 | "calçamento das ruas Pedro Lino, Ana Rosa Queiroz e João Sátiro"; "João Sátiro tinha 70% concluído" |
| T5 | Razão social formada por sobrenomes ou iniciais; propagação do sobrenome do sócio ou de pessoa homônima à razão social | 2 | 5 | 7 | "Mendonça & Saraiva Engenharia Ltda."; "J. P. Lacerda Comércio Ltda." |
| T6 | Município, distrito ou região administrativa com forma de nome de pessoa fora dos contextos protegidos: sujeito de oração, coordenação "X e Y", caixa alta após "O PREFEITO MUNICIPAL DE", tabela sem cabeçalho "Município", célula "distrito de X", distrito isolado, último sobrenome na linha de local e data | 12 | 17 | 29 | "Pedro Afonso conta com sete equipes"; "Pedro Versiani e Crispim Jaques mantêm cloro baixo"; "O PREFEITO MUNICIPAL DE DOMINGOS MARTINS" |
| T7 | Parte de topônimo lida como dado sensível | 0 | 1 | 1 | "Municípios de Bernardino Batista e Triunfo" → "Batista" como convicção religiosa |
| T8 | Endereço de pessoa jurídica, do órgão fora do cabeçalho, de obra em rodovia ou de comunidade rural onde fica a unidade pública | 5 | 5 | 10 | "com sede na Rua Barão do Rio Branco, 450, Sala 2"; "Atendimento presencial: Rua Sete, 112, das 9h às 17h"; "UBS da comunidade Sítio Lagoa Seca"; "RO-010, km 87" |
| T9 | Placa, RENAVAM e chassi de veículo oficial (citação no singular, tabela da frota, lotes de leilão) | 11 | 9 | 20 | "o micro-ônibus escolar placa QXT4B21"; "Lote 02 \| ambulância \| FJR2C08 \| RENAVAM … \| chassi …" |
| T10 | Contato do órgão ou de empresa: celular ou WhatsApp institucional, e-mail institucional em provedor gratuito, e-mail .gov.br com nome próprio no usuário ou após o rótulo "Contato:", fixo do SIC ou da assessoria, e-mail comercial .com.br | 9 | 13 | 22 | "WhatsApp da CPL (96) 99144-0000"; "cpl.prefeitura@hotmail.com"; "premio.joanalima@municipio.sc.gov.br" |
| T11 | Número de processo, notificação, auto, laudo, ofício ou ação sobre coletividade ou pessoa jurídica (licitação, contrato, fomento, proposta de fundo, ensaio de obra, análise de água, ação civil pública entre MP e município) | 9 | 7 | 16 | "Processo SEI nº 0009.000000/2024-00 (contrato de obra)"; "Auto de Infração nº 31/2025 lavrado contra a contratada"; "Ação Civil Pública nº … (MP x Município)" |
| T12 | Sigla de conselho profissional seguida de número de ato ou de registro de pessoa jurídica | 1 | 2 | 3 | "Ofício OAB/RN nº 145/2025"; "Parecer Técnico CREA-RN nº 22/2025"; "registro de PJ no CREA-AM nº 4.218/2023" |
| T13 | Numeração de subitem ou código de classificação com forma de IP | 1 | 4 | 5 | "conforme o subitem 8.3.1.2 do Termo de Referência"; "COBRADE 1.3.2.1.4" |
| T14 | Ano ou contagem junto a palavra-chave de identificador, com propagação a todas as ocorrências | 2 | 3 | 5 | "A matrícula inicial de 2025 é de 9.418 estudantes" → "2025" tarjado também em "5 de agosto de 2025"; "1.032 partos" lido como protocolo |
| T15 | Número público lido como telefone, cartão ou conta pela forma | 3 | 1 | 4 | "Convênio nº 912345/2021" → telefone; chave de NF-e em grupos de quatro → telefone e cartão (janela que satisfaz Luhn); "símbolo CC-3" → conta corrente |
| T16 | Conta bancária de pessoa jurídica (OSC, fundo, hospital) | 2 | 4 | 6 | "conta específica da parceria: agência 0001-9, conta 12.345-6"; conta do fundo para doações |
| T17 | Termo de saúde, violência ou origem étnica em texto normativo, protocolo clínico, estatística ou nome de órgão, sem pessoa determinada | 23 | 13 | 36 | "O paciente com sinais de alarme deve receber hidratação venosa"; "A vítima de violência sexual deve ser acolhida em 72 horas"; "Diretoria de Atenção a Populações em Situação de Violência"; "214 casos de SRAG" |
| T18 | Medida técnica de engenharia ou material de obra lido como dado de saúde | 2 | 1 | 3 | "concreto com fck 35 MPa aos 28 dias"; "pedra tosca rejuntada" |
| T19 | Valor de pessoa jurídica, de ente público ou por grupo lido como valor pessoal | 1 | 5 | 6 | "aluguel social de R$ 400,00 a 37 famílias"; "multa de R$ 1.000,00 por dia ao Município"; "Rendimentos de aplicação: R$ 41.207,18"; "prejuízo ao INSS de R$ 2,3 milhões" |
| T20 | Idade de bem ou de município e "nasceu em" de programa lidos como idade ou data de nascimento | 0 | 4 | 4 | "o estádio, que tem 72 anos"; "o programa nasceu em 12/05/2019" |
| | **Total de tarjas indevidas** | **92** | **118** | **210** | |

T2 na rodada 2: 7 trechos de equipamento/honraria/operação e 3 de entidade ou política (cabeçalho em
caixa alta, forma curta "Política Nacional Aldir Blanc").

## Formas testadas sem erro

* Pessoas com nome igual a município (Iracema, Jussara, Damião, Marcelino Vieira, Afonso Cláudio,
  Amélia Rodrigues, Joaquim Távora, Fátima…), nome logo após unidade em escala, nome após prêmio,
  homenageados vivos em decreto legislativo, iniciais com idade, valor de diária, licença para
  tratamento de saúde: todos protegidos.
* Municípios como Cláudia, Santa Carmem, Miguel Pereira, Presidente Figueiredo, Rolim de Moura,
  Ministro Andreazza, Rodrigues Alves, Sena Madureira, Marechal Thaumaturgo, Iracema, Ferreira Gomes,
  Senador Pompeu, Marechal Deodoro e Governador Valadares ficaram legíveis em tabela e em texto.
* Unidades com título ("UBS Enfermeira…", "CRAS Dona…", "CMEI Tia…", "Ponte Prefeito…", "Auditório
  Vereador…", "Edifício Engenheiro…", "Paço Municipal Prefeito…"), parte dos equipamentos sem título
  ("Estádio Municipal…", "Ginásio de Esportes…", "Ginásio Coberto…", "Ponte" com nome completo), CEPAV
  com nomes de flores, leis com nome de pessoa (Maria da Penha, Berenice Piana, Paulo Gustavo).
* CNPJ, CNAE, NCM, CBO, códigos orçamentários, "Resolução CNS nº", chave PIX que é CNPJ, contagens de
  CIN, RG, CPF, boletins de ocorrência, inquéritos e TCO, valores mg/L de qualidade da água,
  medicamentos em objeto de contrato e contagem agregada de registros de violência doméstica (R4-023;
  a mesma expressão em orientação normativa, em R4-008, foi tarjada).

## Observações

* A única falha de recall (V1) envolve um termo de doença fora do vocabulário ligado a um
  quase-identificador; o quase-identificador conta como protegido no perfil `lai` por ser sinalizado.
* As maiores fontes de tarja indevida são termos de saúde e violência em texto normativo ou
  estatístico (T17), municípios e distritos com forma de nome (T6), contatos do órgão (T10) e
  identificadores de veículos oficiais (T9).
* A propagação amplia o dano: um falso positivo curto ("2025" após "matrícula", sobrenome de sócio,
  último nome de município) é tarjado em todas as ocorrências, inclusive em datas e razões sociais.
* `publicos` não é exaustivo. Algumas tarjas indevidas caíram em ocorrências sem unidade pública
  listada (município como sujeito em R4-012, R4-015, R4-019 e R4-029; "Rua Projetada 4"; "criança
  indígena" em orientação clínica) e contam só em "tarja fora do gabarito". A anotação não foi
  alterada depois da execução do sistema; nenhum documento foi descartado ou reescrito.
