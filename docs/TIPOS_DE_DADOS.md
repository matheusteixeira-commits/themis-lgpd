# Tipos de dados e perfis

Este documento descreve os tipos de dado reconhecidos, as categorias com a respectiva base legal e
as regras de cada perfil. A fonte de verdade é o código: `src/themis_lgpd/catalogo.py` (tipos e
categorias), `src/themis_lgpd/perfis.py` (perfis) e `src/themis_lgpd/reconhecedores/`
(reconhecedores). A lista pode ser obtida em tempo de execução com `GET /v1/tipos` na API.

Todos os exemplos deste documento são fictícios.

## Categorias e base legal

| Categoria | Nome | Base legal | Identificadora¹ |
|---|---|---|---|
| `PESSOA` | Nome de pessoa natural | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | sim |
| `DOCUMENTO` | Documento de identificação | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | sim |
| `DADO_PESSOAL` | Dado pessoal | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | sim |
| `CONTATO` | Contato pessoal | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | sim |
| `LOCALIZACAO` | Endereço | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | sim |
| `FINANCEIRO` | Dado financeiro | LGPD, art. 5º, I; LAI, art. 31, § 1º, I; LC 105/2001 | sim |
| `ECONOMICO` | Situação econômica de pessoa natural | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | não |
| `VEICULO` | Identificação de veículo | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | sim |
| `PROCESSO` | Número de processo ou protocolo | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | sim |
| `SENSIVEL` | Dado pessoal sensível | LGPD, art. 5º, II, e art. 11; LAI, art. 31 | não |
| `INTIMIDADE` | Intimidade e vida privada | LAI, art. 31, caput e § 1º, I; CF, art. 5º, X | não |
| `MENOR` | Dado de criança ou adolescente | LGPD, art. 14; ECA, arts. 17 e 143 | não |
| `EMPRESA` | Identificação de pessoa jurídica | LAI, art. 22 (quando houver sigilo legal) | não |
| `LOCALIDADE` | Localidade | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | não |
| `URL` | Endereço de internet | LAI, art. 31 (quando pessoal) | não |
| `INSTITUCIONAL` | Dado de órgão ou entidade | LAI, art. 8º, § 1º, I; LGPD, art. 5º, I (a contrario) | não |
| `QUASE_IDENTIFICADOR` | Quase-identificador | LGPD, art. 5º, I; LAI, art. 31, § 1º, I | não |
| `MANUAL` | Tarja manual | Decisão do revisor | sim |

¹ Categorias em `perfis.CATEGORIAS_IDENTIFICADORAS`: identificam a pessoa por si sós. Nelas, um achado
de confiança moderada é tarjado por precaução (ver [Falha fechada](#falha-fechada-para-identificadores))
e os valores tarjados são propagados para todo o documento.

## Tipos de dado

A coluna **Prioridade** decide qual entidade prevalece quando duas se sobrepõem (maior prevalece). A
coluna **Validação** indica o que é conferido além do formato.

### Pessoa e documentos

| Código | Nome | Etiqueta | Prioridade | Validação | Exemplo fictício |
|---|---|---|---|---|---|
| `NOME` | Nome de pessoa | `[NOME]` | 75 | Modelo de linguagem, lista de nomes ou gatilho de contexto | Maria Aparecida Souza |
| `CPF` | CPF | `[CPF]` | 100 | Módulo 11; formato pontuado ou contexto dispensam a validação; CPF parcialmente mascarado com dígitos visíveis | 529.982.247-25; `***.982.247-**`; 529.XXX.XXX-25 |
| `RG` | RG / Carteira de identidade | `[RG]` | 95 | Contexto obrigatório ("RG", "identidade", "CIN"); inclui órgão emissor e UF | RG 1.234.567 SSP/DF |
| `CNH` | CNH | `[CNH]` | 95 | Dígitos verificadores; contexto obrigatório | CNH 39825979149 |
| `PIS` | PIS/PASEP/NIS/NIT | `[PIS]` | 95 | Módulo 11; sem pontuação característica, exige contexto | 190.74833.78-3 |
| `TITULO_ELEITOR` | Título de eleitor | `[TÍTULO DE ELEITOR]` | 95 | Dígitos verificadores com código da UF | 8762 3286 2410 |
| `CNS` | Cartão Nacional de Saúde (SUS) | `[CARTÃO SUS]` | 95 | Módulo 11 (definitivo e provisório); grupos separados por espaço ou ponto | 112 9040 4796 6691 |
| `PASSAPORTE` | Passaporte | `[PASSAPORTE]` | 90 | Contexto obrigatório | passaporte AB123456 |
| `CTPS` | Carteira de trabalho | `[CTPS]` | 90 | Contexto obrigatório; inclui série e UF | CTPS 1234567 série 0012/DF |
| `CERTIDAO` | Matrícula de certidão civil | `[CERTIDÃO]` | 90 | Formato de 32 dígitos (Provimento CNJ nº 3/2009); termo com livro e folha | termo 4521, livro A-32, folha 118 |
| `MATRICULA` | Matrícula funcional | `[MATRÍCULA]` | 85 | Contexto obrigatório ("matrícula", "Matr.", "SIAPE", "MASP", "ID funcional", "nº funcional", "registro funcional"; "RF" só no formato do registro funcional), com o vínculo ("/01"); coluna de tabela com esse cabeçalho | MASP 1234567-8; Id. funcional 1234567/01; RF 123.456.7/1 |
| `REGISTRO_PROFISSIONAL` | Registro profissional (OAB, CRM, RNTRC, CADASTUR…) e RQE | `[REGISTRO PROFISSIONAL]` | 85 | Sigla do conselho com a UF ou a região ("6ª Região"), inclusive em minúsculas; coluna de tabela com a sigla no cabeçalho | OAB/DF 12.345; CRN-3 88421; CRESS 6ª Região nº 1.234; RQE 4.321 |
| `BENEFICIO` | Benefício previdenciário ou social (NB do INSS) | `[BENEFÍCIO]` | 90 | Contexto obrigatório ("NB", "benefício"), inclusive no cabeçalho da coluna de uma tabela | NB 123.456.789-0 |
| `REGISTRO_SAUDE` | Prontuário, DNV, AIH ou cartão de vacina | `[REGISTRO DE SAÚDE]` | 85 | Contexto obrigatório; o prontuário pode trazer a sigla do serviço ("Prontuário CER:", "Prontuário SIGLA nº") e o número, a sigla da unidade | prontuário nº 2891163; Prontuário: ABC-0123/2024 |
| `MATRICULA_ESCOLAR` | Matrícula escolar ou RA | `[MATRÍCULA ESCOLAR]` | 85 | Contexto obrigatório ("RA", "registro acadêmico", "matrícula do aluno") | RA 123456789-X |
| `INSCRICAO_IMOVEL` | Inscrição imobiliária (IPTU, CCM) | `[INSCRIÇÃO]` | 80 | Contexto obrigatório | inscrição imobiliária 01.23.456.0789.001 |
| `DOCUMENTO` | Número de documento | `[DOCUMENTO]` | 80 | Contexto obrigatório; coluna de tabela com cabeçalho de inscrição, protocolo ou requerimento | Documento do cliente: 1234567-8 |
| `DATA_NASCIMENTO` | Data de nascimento | `[DATA DE NASCIMENTO]` | 85 | Contexto ("nascido em", "data de nascimento", "DN", e em documentos de estrangeiros "nacida el", "nato a … il", "née le") ou coluna "Nascimento" de tabela; formatos numérico (também com espaços no lugar das barras e com o ano primeiro), ISO, com mês em algarismos romanos ou abreviado, por extenso (também em espanhol, italiano e francês), de registro civil e toda por extenso; o ano isolado ou presumido. "Nasceu em" com sujeito que é programa, projeto ou entidade não é data de nascimento | nascida em 12/03/1985; 1º de março de 1985; DN 03/XI/2015; nascido aos onze dias do mês de julho de mil novecentos e oitenta |
| `IDADE` | Idade de pessoa | `[IDADE]` | 80 | Contexto que liga a idade a uma pessoa identificável (ver [Idade e valores de pessoa natural](#idade-e-valores-de-pessoa-natural)) | Idade: 52 anos; Fulano, 33 anos, CPF…; o filho, de 6 anos |

### Contato, localização e finanças

| Código | Nome | Etiqueta | Prioridade | Validação | Exemplo fictício |
|---|---|---|---|---|---|
| `EMAIL` | E-mail | `[E-MAIL]` | 90 | Formato; inclui formas ofuscadas | maria.souza@exemplo.com.br; joao arroba gmail ponto com; joao [arroba] gmail [ponto] com; joao @ gmail . com |
| `TELEFONE` | Telefone | `[TELEFONE]` | 85 | Padrões próprios e biblioteca phonenumbers (região BR) | (61) 99876-5432 |
| `PERFIL_REDE_SOCIAL` | Perfil em rede social | `[PERFIL]` | 85 | `@usuario` com contexto ou URL de rede social | @maria.souza |
| `IP` | Endereço IP | `[IP]` | 80 | Reconhecedor do Presidio | 203.0.113.45 |
| `ENDERECO` | Endereço | `[ENDEREÇO]` | 70 | Logradouro (inclusive abreviado, numerado, com ordem — "2ª Travessa" — e passarela) e componentes (inclusive barraco e "casa sem número"), com o ponto de referência que o completa ("ao lado da capela…"); propriedades e localidades rurais, ocupações e favelas; rodovias das 27 UFs; endereçamento do DF; município ou região de residência. Linha de tabela ("Rua X \| 9") não forma endereço | Rua B-15, Quadra 30, Lote 10; Sítio Boa Esperança; PE-060, km 10; QNM 12 Conjunto B Casa 4 |
| `CAR` | Recibo do Cadastro Ambiental Rural | `[CAR]` | 90 | Formato (UF, código IBGE do município e 32 caracteres hexadecimais) | MT-5107925-1A2B.3C4D.… |
| `CEP` | CEP | `[CEP]` | 80 | Formato com hífen ou após "CEP" | 72215-120 |
| `CONTA_BANCARIA` | Agência/conta bancária | `[CONTA BANCÁRIA]` | 85 | Contexto bancário; IBAN pelo Presidio | agência 1234, conta 56789-0 |
| `CARTAO` | Cartão de pagamento | `[CARTÃO]` | 90 | Algoritmo de Luhn | 4111 1111 1111 1111 |
| `CHAVE_PIX` | Chave PIX | `[CHAVE PIX]` | 90 | Contexto ("pix", "chave") | chave pix 61998765432 |
| `CARTEIRA_CRIPTO` | Carteira de criptomoeda | `[CARTEIRA CRIPTO]` | 85 | Reconhecedor do Presidio | |
| `VALOR_PESSOAL` | Valor recebido ou devido por pessoa natural | `[VALOR]` | 70 | Contexto que liga o valor a uma pessoa (ver [Idade e valores de pessoa natural](#idade-e-valores-de-pessoa-natural)) | aposentadoria de R$ 1.600,00; dívida de R$ 412,00 |

### Veículos e processos

| Código | Nome | Etiqueta | Prioridade | Validação | Exemplo fictício |
|---|---|---|---|---|---|
| `PLACA` | Placa de veículo | `[PLACA]` | 85 | Padrão Mercosul; padrão antigo com contexto | ABC1D23 |
| `RENAVAM` | RENAVAM | `[RENAVAM]` | 90 | Contexto obrigatório ("RENAVAM", "renavan"); o dígito verificador eleva a confiança | RENAVAM 72510273464 |
| `CHASSI` | Chassi (VIN) | `[CHASSI]` | 90 | Com "chassi", qualquer fabricante; sem a palavra, prefixo 9 (fabricantes no Brasil) com letras e dígitos | 9BWZZZ377VT004251 |
| `PROCESSO_JUDICIAL` | Processo judicial (CNJ) | `[PROCESSO JUDICIAL]` | 85 | Módulo 97 (Resolução CNJ nº 65/2008); formato pontuado dispensa a validação | 4686958-42.2023.8.07.6678 |
| `PROCESSO_ADMINISTRATIVO` | Processo administrativo (SEI/NUP) | `[PROCESSO]` | 80 | Ano plausível; formatos federais e estaduais (NUP-21, SEI-MG, SEI-PE, SEI-BA, RJ); contexto para formatos livres (PROA, eProtocolo, SGPe, sigla do sistema ou do órgão antes do número). Não se aplica a avisos de licitação, atas de pregão, termos de referência e extratos de contrato sem pessoa natural | 00410-00012345/2024-11; 1500.01.0012345/2024-12; Processo SIGLA: ABC-2024/01234 |
| `PROTOCOLO` | Protocolo e número de documento sobre pessoa | `[PROTOCOLO]` | 75 | Contexto ("protocolo", "ocorrência", "boletim"); laudo, parecer médico ou psicossocial, relatório social ou de atendimento, investigação, declaração de óbito, CAT, procedimento, sindicância, mandado, auto e termo lavrados contra o autuado, ficha e guia individuais, com qualificativos e sigla da unidade; registros policiais pela sigla (BO, REDS, RAI, TCO). Relatórios de auditoria, fiscalização e gestão, laudos de imóveis e obras, códigos de tabelas públicas (IBGE, CNAE, CBO) e boletins que são publicações ficam legíveis | protocolo nº 2024123456; Relatório Social nº 733/2026; Laudo nº 4410/2025-PTC |

### Pessoa jurídica, localidades e outros

| Código | Nome | Etiqueta | Prioridade | Observação |
|---|---|---|---|---|
| `CNPJ` | CNPJ | `[CNPJ]` | 90 | Módulo 11, inclusive o CNPJ alfanumérico (IN RFB nº 2.229/2024), como GM.Y1U.F3A/0001-01 |
| `LOCALIDADE` | Cidade ou região administrativa | `[LOCALIDADE]` | 30 | Os 5.570 municípios do IBGE ("Cidade/UF" com conferência da UF, "município de Cidade", menção isolada não ambígua) e as regiões administrativas do DF; "moro em campinas" e "resido em Taguatinga" são classificados como `ENDERECO` |
| `URL` | Endereço de internet | `[URL]` | 20 | |
| `CONTATO_INSTITUCIONAL` | Telefone ou e-mail de órgão ou setor | `[CONTATO INSTITUCIONAL]` | 20 | Ver [Contatos, endereços e veículos do órgão](#contatos-endereços-e-veículos-do-órgão) |
| `ENDERECO_INSTITUCIONAL` | Endereço de sede ou unidade de órgão | `[ENDEREÇO INSTITUCIONAL]` | 20 | "na sede da Secretaria, situada na Rua…"; cabeçalho do documento |
| `PLACA_OFICIAL` | Placa de veículo da frota oficial | `[PLACA OFICIAL]` | 20 | "veículos oficiais de placas …"; tabela de unidades e placas em documento sobre a frota |
| `QUASE_IDENTIFICADOR` | Quase-identificador | `[QUASE-IDENTIFICADOR]` | 15 | Função, local e turno ("atendente do guichê 4 na tarde de ontem"); função ou condição precedida de "único" ("única professora surda da escola", "o único apenado da galeria que atua como monitor"); aposto que descreve a pessoa ("o escrivão do plantão, um senhor grisalho de bigode"); descrição física com marca distintiva ("o mais alto, com tatuagem no pescoço") |
| `NUMERO_NAO_IDENTIFICADO` | Número longo não identificado | `[NÚMERO]` | 10 | Reservado; não é produzido pelos reconhecedores padrão |
| `MANUAL` | Trecho tarjado manualmente | `[TARJADO]` | 110 | Lista de bloqueio e tarjas manuais da revisão |

### Dados sensíveis, intimidade e menores

| Código | Nome | Etiqueta | Categoria | Exemplos de achado |
|---|---|---|---|---|
| `SAUDE` | Dado de saúde | `[DADO DE SAÚDE]` | `SENSIVEL` | CID F32.1, F41.1 e G40; C.I.D. 6A70.1; "Diagnósticos de alta: E11.5; M86.1"; "diagnosticado com depressão"; "asma"; "faço uso de fluoxetina 20mg"; "creatinina de 1,6 mg/dL"; "PA 150 x 95 mmHg"; "Glasgow 13"; "licença para tratamento de saúde" |
| `RELIGIAO` | Convicção religiosa | `[CONVICÇÃO RELIGIOSA]` | `SENSIVEL` | "sou católico"; "membro da Igreja …"; "filha de santo do Terreiro …" |
| `OPINIAO_POLITICA` | Opinião política | `[OPINIÃO POLÍTICA]` | `SENSIVEL` | "filiado ao Partido … (sigla) e membro de seu diretório municipal" |
| `FILIACAO_SINDICAL` | Filiação sindical ou associativa | `[FILIAÇÃO]` | `SENSIVEL` | "sou sindicalizado"; "mensalidade sindical"; "desfiliado do Sindicato … (sigla)" |
| `VIDA_SEXUAL` | Vida sexual / orientação sexual | `[VIDA SEXUAL]` | `SENSIVEL` | "relacionamento homoafetivo"; "homem cisgênero" |
| `GENETICO_BIOMETRICO` | Dado genético ou biométrico | `[DADO BIOMÉTRICO]` | `SENSIVEL` | exame de DNA, impressão digital |
| `ORIGEM_RACIAL` | Origem racial ou étnica | `[ORIGEM RACIAL]` | `SENSIVEL` | "Raça/cor: parda"; "indígena da etnia …"; "remanescente de quilombo" |
| `VIOLENCIA` | Situação de violência ou risco | `[SITUAÇÃO DE VIOLÊNCIA]` | `INTIMIDADE` | "vítima de violência doméstica"; "medida protetiva" (com vínculo) |
| `DADO_DE_MENOR` | Dado de criança ou adolescente | `[DADO DE MENOR]` | `MENOR` | "meu filho de 9 anos"; "medida socioeducativa" |

Os dados de saúde são reconhecidos por códigos da CID-10 e da CID-11 (inclusive listas), frases de
diagnóstico e tratamento, um vocabulário de cerca de 500 expressões — doenças e condições por
aparelho, deficiências, transtornos, alergias, sintomas, procedimentos, exames, imunização, gestação,
dependência química, dispositivos e especialidades —, uma seleção de cerca de 290 medicamentos da DCB
e da Portaria SVS/MS nº 344/1998 (`dados/medicamentos.txt`), além das classes identificadas pelo
sufixo (-mabe, -tinibe, -prazol…). O trecho tarjado inclui os qualificadores que também revelam a
condição: gravidade, tipo, localização anatômica e sigla entre parênteses ("carcinoma basocelular",
"artrose no quadril", "esclerose lateral amiotrófica (ELA)"). Expressões que atribuem a condição a
alguém ("estou com suspeita de…", "sofri uma fratura…"), registros clínicos ("laudo de…",
"prontuário referente à…") e campos de formulário ("Condição clínica: …") são contextuais.
As demais categorias sensíveis usam vocabulário próprio.

O tipo de violência só é contextual com o enquadramento que o atribui a alguém ("vítima de", "sofreu",
"medo de"); citado sem enquadramento ("denúncias de assédio moral"), assim como "situação de risco" ou
"de vulnerabilidade", é termo isolado e depende de vínculo. "Conselho tutelar" e "acolhimento
institucional" também dependem de vínculo, e faixas e limites de idade ("crianças de 6 meses a menores
de 9 anos", "menores de 15 anos") não são dado de menor.

#### Registro clínico e documento centrado em pessoa

Num documento centrado numa pessoa identificada — campos de identificação no início de linha
("Paciente:", "Periciando:", "Usuário:", "Requerente:", "Data de nascimento:", "Prontuário:", "CPF:"),
seção de identificação ou fórmula de atestação ("Atesto, para os devidos fins, que a Sra. …") —, o dado
sensível se refere a essa pessoa, e o termo isolado é tarjado sem marcador na frase (motivo "Dado
sensível em documento centrado em pessoa identificada"), salvo quando a frase, fora de registro clínico,
trata de grupo ou estatística. Boletins, notas técnicas, editais e comunicados não têm esses campos e
seguem a regra da frase.

O documento centrado é **registro clínico ou pericial** quando o título indica o gênero (laudo, atestado,
prontuário, sumário de alta, parecer de junta médica, ficha de notificação, receituário,
encaminhamento, avaliação biopsicossocial…), quando há ao menos duas seções do registro ("HISTÓRICO",
"EXAME FÍSICO", "DIAGNÓSTICO", "CONDUTA"…) ou quando o texto tem muitos achados de saúde. Nele:

- são reconhecidas também as formas próprias do registro: analito com resultado ("creatinina de 1,6
  mg/dL", "anti-HCV reagente"), sinal vital e medida, escala clínica ("ECOG 2", "Child-Pugh C"),
  posologia ("400 mg EV de 12/12 h"), fórmula obstétrica e idade gestacional, achados do exame físico e
  psíquico, nome de exame, termos pelo sufixo (-algia, -ectomia, -plastia…) e o valor de campos clínicos
  ("Natureza:", "Tipo de violência:", "Evolução:", "Marcha:");
- o trecho tarjado vai até a fronteira da frase (ponto final, ponto e vírgula, quebra de linha, célula),
  sem atravessar nome de instituição, programa ou norma, conectivo normativo ("conforme a Política…"),
  município ou nome próprio; o rótulo da linha ("Diagnóstico:") fica legível, salvo quando nomeia exame;
- as linhas do corpo de tabela de exames, prescrição ou achados ("EXAME | RESULTADO | REFERÊNCIA") são
  tarjadas inteiras, com o cabeçalho legível.

Fora do registro clínico, o trecho de saúde tarjado inclui os atributos da condição: tempo ("há 14
anos", "desde 2021"), estado do tratamento (", em tratamento desde…"), frequência ("três vezes por
semana"), causa ("em razão de paralisia cerebral") e a célula de tabela. Numa tabela com uma pessoa por
linha (coluna "Nome", "Candidato"), o dado sensível da célula se refere à pessoa da linha.

Não são vinculados a pessoa, e viram alerta, o termo sensível dentro de nome de instituição, programa,
norma ou serviço ("Departamento de Controle da Hanseníase", "Vara de Violência Doméstica",
"ambulatório de pé diabético"), em título do documento (salvo título que enuncia o motivo de uma licença),
na linha de assinatura do profissional, em rótulo de campo ("Internação:", "Nome social:"), em
classificação do caso no cabeçalho ("Assunto:", "Natureza:"), negado ou hipotético ("nega alergias",
"em caso de febre", "Possui deficiência? não"), em quesito padrão não respondido com "sim", o termo de
cor ou etnia que integra nome próprio ou qualifica serviço ("Terra Indígena …", "saúde indígena") e o
trecho em maiúsculas do classificador treinado sem termo do léxico.

O classificador de trechos treinado (ver [Configuração](CONFIGURACAO.md#classificador-de-dados-sensíveis))
complementa essas regras com condições descritas em linguagem clínica ou com palavras próprias, achados de
exame, medicamentos com posologia e descrições de origem étnica, religião, filiação ou orientação sexual;
o tipo do dado sensível é inferido do vocabulário do trecho. Os achados seguem a mesma regra de vínculo.

### Nomes de pessoas

Três reconhecedores se complementam:

| Reconhecedor | Funcionamento | Funciona em minúsculas e caixa alta |
|---|---|---|
| `BR_Nomes_Modelo` | Entidades `PER` (e `MISC`/`LOC` iniciadas por prenome conhecido) do modelo `pt_core_news_lg`, divididas na quebra de linha, no travessão e na barra vertical (o cargo da linha de baixo não entra no nome) e filtradas: títulos e cargos iniciais, letras isoladas, algarismos romanos, palavras comuns e administrativas, siglas, nomes de instituições, empresas, normas e lugares | não |
| `BR_Nomes_Lista` | Sequências iniciadas por um dos cerca de 700 prenomes brasileiros das listas (inclusive os mais frequentes por sexo, década e UF no Censo 2010 do IBGE), seguidos de sobrenomes, conectores ou iniciais ("Graziela B. Assunção"); em CAIXA ALTA, até três palavras fora das listas entre nomes ou no fim do nome; o nome continua na linha seguinte quando a linha termina em conector, quando a seguinte começa por "Filho", "Neto" ou "Júnior" ou quando a célula da tabela foi partida | sim |
| `BR_Nomes_Gatilho` | Nome após gatilho de contexto ("meu nome é", "requerente:", "Atenciosamente,", "sou a…"), rótulo de campo ("Membro:", "Periciada:", "Contribuinte:"), papel ou ato de pessoal ("a servidora FULANA", "conduzido por", "Exonerar"); nome antes de identificador, idade ou cargo ("FULANO, matrícula", "FULANO – Membro"); linha só com o nome sobre a linha do cargo, na assinatura; célula de tabela com o nome em linha que traz CPF ou matrícula; iniciais de pessoa ("K.C.P.", "M. E. S."); apelidos ("vulgo “Fulano”"). Nesses contextos, nomes de imigrantes e indígenas fora das listas são aceitos em CAIXA ALTA | sim |

Nomes que integram nomes de lugares, instituições, empresas ou normas não são tratados como pessoa:
"São Paulo", "Escola Paulo Freire", "Lei Maria da Penha", "Unidade Básica de Saúde Doutor Fulano",
"EE Professora Fulana", "Penitenciária Estadual Fulano de Tal", "Panificadora Fulano Ltda.". O mesmo
vale para municípios com nome de pessoa citados como lugar: na linha de local e data ("Teotônio
Vilela, 12 de maio de 2025"), com a UF, após "em" ou rótulo ("Município: …"), após unidade
administrativa ("Superintendência Regional de Ensino de …") e em enumerações ou colunas de municípios.

O classificador de trechos treinado também propõe nomes (`BR_Sensivel_Aprendido`, origem
`aprendido:nome_pessoa`), em especial em caixa alta, em tabelas, em assinaturas e por iniciais. Aplica
o mesmo critério de lugares, instituições e normas, descarta o nome que encerra o nome próprio de uma
unidade ou honraria ("Unidade Básica de Saúde Dr. …", "Prêmio … Fulano de Tal") e o que é, por inteiro,
nome de município, e retira pronomes de tratamento do início.

## Perfis

| Categoria | `lai` (padrão) | `identificadores` | `saude` | `ouvidoria` | `educacao` | `maxima` |
|---|---|---|---|---|---|---|
| `PESSOA`, `DOCUMENTO`, `DADO_PESSOAL`, `CONTATO`, `LOCALIZACAO`, `FINANCEIRO`, `VEICULO`, `PROCESSO`, `MANUAL` | tarjar | tarjar | tarjar | tarjar | tarjar | tarjar |
| `SENSIVEL` | vinculado | alertar | vinculado² | vinculado | vinculado³ | tarjar |
| `INTIMIDADE` | vinculado | alertar | vinculado | vinculado | vinculado | tarjar |
| `MENOR` | vinculado | alertar | vinculado | tarjar | tarjar | tarjar |
| `ECONOMICO` | tarjar | alertar | tarjar | tarjar | tarjar | tarjar |
| `EMPRESA` | manter | manter | manter | alertar | manter | tarjar |
| `LOCALIDADE` | alertar | manter | alertar | tarjar | alertar | tarjar |
| `URL` | manter | manter | manter | tarjar | manter | tarjar |
| `INSTITUCIONAL` | alertar | alertar | alertar | alertar | alertar | tarjar |
| `QUASE_IDENTIFICADOR` | alertar | alertar | alertar | tarjar | tarjar | tarjar |
| Confiança mínima para aplicar a regra (`score_minimo`) | 0,6 | 0,6 | 0,6 | 0,5 | 0,6 | 0,4 |
| Confiança mínima para considerar o achado (`score_alerta`) | 0,4 | 0,4 | 0,4 | 0,4 | 0,4 | 0,3 |

² No perfil `saude`, os tipos `SAUDE` e `GENETICO_BIOMETRICO` são tarjados sempre, mesmo sem vínculo.
³ No perfil `educacao`, o tipo `SAUDE` é tarjado sempre, mesmo sem vínculo.

O perfil `ouvidoria` atende à preservação da identidade do manifestante (Lei nº 13.460/2017, art. 10,
§ 7º): além dos identificadores, tarja a cidade, a lotação, a função e o turno, que, combinados,
permitiriam reconhecer quem se manifestou. O perfil `educacao` protege estudantes (LGPD, art. 14; ECA,
art. 17): RA, matrícula, turma, série e dados de crianças e adolescentes são sempre tarjados.
Perfis próprios do órgão são derivados destes no `themis.toml` ([CONFIGURACAO.md](CONFIGURACAO.md)).

### Contatos, endereços e veículos do órgão

Telefone e e-mail de setor, endereço de sede ou de unidade de atendimento e placa da frota oficial não
são dados pessoais: a LAI manda divulgá-los (art. 8º, § 1º, I). Depois de todos os reconhecedores, o
contexto do documento inteiro reclassifica esses achados para a categoria `INSTITUCIONAL`, que o perfil
LAI mantém legível e sinaliza para revisão:

- **contato do órgão:** número de serviço (0800, 4004); telefone fixo ou e-mail de domínio público
  (`.gov.br`, `.jus.br`, `.mp.br`, `.leg.br`, `.def.br`, `.edu.br`, `.org.br`) sem nome de pessoa,
  quando o contexto é de canal de atendimento ("Dúvidas…", "Informações:", "telefone institucional",
  "Telefone da unidade:", "à disposição para esclarecimentos", "poderão ser esclarecidas pelo telefone"),
  quando a linha começa pelo nome de um órgão ou unidade ("Núcleo de Endemias – (69) 3216-7742"), no
  cabeçalho do documento ou na mesma frase de outro contato do órgão ("pelo telefone … ou pelo e-mail
  setor@orgao.gov.br");
- **endereço do órgão:** no cabeçalho do documento (bloco de linhas curtas separado do corpo), após o
  rótulo "Endereço da unidade:" ou o edifício-sede ("Palácio…", "Centro Administrativo…") ou introduzido
  pela sede ou pela unidade ("na sede da Corregedoria, na Rua…", "a Diretoria de Atenção Primária,
  situada na Avenida…", "na UBS Vila Nova, na Rua…") numa frase que anuncia o serviço — horário de
  atendimento, hora do ato ou providência ("poderão ser retirados", "deverá ser protocolada"); num
  pedido, a mesma construção costuma descrever o lugar que a pessoa frequenta. O CEP do mesmo endereço
  acompanha a classificação, e o nome de pessoa dentro dele é o nome do logradouro;
- **placa oficial:** enumeração após "veículos oficiais de placas…" ou "viaturas de placas…" e linhas de
  tabela que associam unidades do órgão a placas, em documento sobre a frota.

Na dúvida, o achado continua pessoal e tarjado: celular nunca é institucional; e-mail de provedor de uso
pessoal, de empresa (`.com.br`) ou com nome de pessoa (prenome, iniciais coladas ao sobrenome) também
não; vínculo pessoal próximo ("meu telefone", "telefone da genitora", "residente na", campo de
qualificação como "Nome:" e "Endereço:" na linha anterior) prevalece sobre a menção ao órgão. O mesmo
número ou e-mail recebe a mesma classificação em todo o documento. A placa de viatura citada no singular
continua tarjada, porque em relatos costuma identificar o servidor que a conduzia.

Códigos de natureza de despesa ("natureza de despesa 3.3.90.39"), que têm a forma de endereço IP, são
descartados quando o contexto é orçamentário.

### Regras

- **tarjar:** o trecho é substituído.
- **alertar:** o trecho permanece no texto e é listado para revisão humana.
- **manter:** o trecho é ignorado.
- **vinculado:** frases que descrevem a situação de alguém (camada contextual, como
  "diagnosticado com…" ou "vítima de violência doméstica") são tarjadas; termos isolados (camada
  semântica, como "asma" ou "católico") são tarjados somente quando a frase se refere a uma pessoa
  determinada e, caso contrário, viram alerta.

A frase se refere a uma pessoa determinada quando contém marcador de primeira pessoa ("eu", "minha",
"tenho", "sofri"), possessivo ou papel ("a requerente", "o paciente", "minha filha"), ou um
identificador pessoal já detectado (nome, documento, contato, processo). Assim, "a política de saúde
mental prevê atendimento para depressão" permanece legível, enquanto "minha filha tem autismo" é
tarjado. A regra evita tarjar conteúdo de interesse público, em atenção ao princípio da máxima
divulgação da LAI. Ver [ADR 0004](adr/0004-perfis-lgpd-e-lai.md).

Para dados de saúde, o vínculo também é procurado na frase anterior e na seguinte, pois os pedidos
costumam nomear a condição numa frase e dizer de quem é na outra ("Solicito o fornecimento de insulina
glargina. Minha filha tem diabetes tipo 1."). Essa extensão não se aplica quando a frase do termo trata
de grupo ou estatística ("o número de casos de dengue", "a campanha de vacinação", "pacientes com
diabetes"), e fórmulas de contato na frase vizinha ("meu e-mail é…") não contam como vínculo. Um termo
de saúde já tarjado no texto é tarjado também nas demais ocorrências, que revelariam a mesma condição.

### Idade e valores de pessoa natural

Idade e valor monetário só são dado pessoal quando se referem a uma pessoa identificável; os mesmos
números em normas, editais, estatísticas e contratos com empresas são informação pública. Por isso os
tipos `IDADE` e `VALOR_PESSOAL` dependem do contexto (`src/themis_lgpd/reconhecedores/pessoais.py`).

**Idade** é tarjada no campo de formulário ("Idade: 52 anos", "Idade: 47 a", "Idade referida: 58
anos"), em aposto ao nome, às iniciais, ao prenome isolado ou ao papel da pessoa ("Fulano, 33 anos,
CPF…", "P.R.S., 8 anos;", "a genitora, de 29 anos", "a neta, Íris, de 7 anos", "um sobrinho de 12
anos"), inclusive com nacionalidade, ocupação, parentesco ou documento entre o nome e a idade ("Fulana,
peruana, doceira, 41 anos", "Fulano, CPF…, de 58 anos"), com verbo ("hoje com 3 anos", "contava 20
anos", "tem 9 anos"), em "62 (sessenta e dois) anos de idade", por extenso ("de doze anos", "vinte e
seis anos"), ao lado da data de nascimento ("10/10/2010 (15 anos)", "03/XI/2015 (10 anos)"), entre
parênteses depois do nome de criança ou adolescente ("a criança Fulana de Tal (8)") e na coluna
"Idade" de tabelas de pessoas. Permanecem legíveis faixas e requisitos ("de 6 a 14 anos", "idade
mínima de 18 anos", "a partir de 60 anos", "18 anos ou mais"), durações ("há 10 anos", "pena de 6 anos",
"36 anos de contribuição", "prazo de 2 anos", "dois anos para concluir"), grupos ("pessoas com 60
anos"), a idade em que algo ocorreu ("aos 14 anos"), a antiguidade de bens, lugares, entidades e
programas ("a ponte, que tem 80 anos", "120 anos de emancipação") e disposições normativas sem pessoa
identificada ("o servidor com 75 anos de idade será aposentado").

**Valores recebidos, pagos ou devidos por pessoa natural** — remuneração, salário, proventos, renda,
benefício, pensão, bolsa, aluguel, dívida, parcela, desconto em folha, multa, fiança, indenização,
prejuízo alegado, bem subtraído ou avaliado, pecúlio do preso — recebem `VALOR_PESSOAL`, na categoria
`ECONOMICO`, em reais ou em moeda estrangeira ("US$ 1.300,00"), com a moeda por extenso ("800 reais",
"duzentos e dez reais"), em milhar por extenso no relato ("chega a seis mil"), em salários mínimos,
inteiros ou em fração ("pensão de um salário mínimo", "um quarto do salário mínimo", "dois salários e
meio"), ou como percentual dos rendimentos ou do salário mínimo ("pensão alimentícia de 30% dos
rendimentos líquidos"). Decide a expressão mais próxima antes do valor, na mesma frase (a quebra de
linha no meio da frase não a interrompe; as expressões entre parênteses só decidem na falta de outra):

- expressão de valor público (contrato, licitação, proposta, orçamento, dotação, repasse, receita de
  convênio, rendimento de aplicação financeira, empresa, erário, tabela, valor estimado ou global, valor
  fixado, taxa, valor da causa) mantém o valor legível, assim como limites e faixas ("até R$ 660,00", "de
  R$ 1.000,00 a R$ 10.000,00", "limitada a R$ 50.000,00"), médias sem pessoa designada na frase ("valor
  médio de R$ 1.640,00"), valores por grupo ("a renda média das famílias", "R$ 600,00 por família", "pago
  a 52 famílias") e dívidas, multas e prejuízos do próprio ente ou de autarquia ("o débito do Município",
  "prejuízo ao INSS");
- expressão de vínculo pessoal (renda, remuneração, dívida, multa…) tarja o valor, salvo em oração
  normativa ("fica fixado o subsídio do cargo em…", "o servidor fará jus a diárias de…") ou atribuída a
  pessoa jurídica que não seja só a credora ("multa… devida pela contratada", mas "dívida de R$ 515,00
  com a concessionária" é da pessoa), quando a frase não identifica uma pessoa (CPF, iniciais,
  tratamento, primeira pessoa); a oração normativa de um caso concreto ("a pensão fixada em…", quando a
  frase cita o requerido, a genitora ou o réu) continua pessoal; em documento que só identifica pessoas
  jurídicas (com CNPJ e sem CPF), a multa sem pessoa designada na frase fica legível;
- expressão de vínculo fraco (benefício, auxílio, bolsa, recebeu, recebendo, pagou, gasta, ganha, tira,
  rende, vive com) tarja o valor quando a frase designa uma pessoa ("a requerente", "a família", "seu
  benefício", "ela", "Dona Fulana", frase que começa por prenome ou por verbo de relato com o sujeito
  oculto: "Gastou em média…").

Também são tarjados os valores das tabelas de pessoas (com coluna de nome, parentesco, CPF, matrícula
ou rubrica de contracheque), todos os valores de declarações de bens (Lei nº 8.429/1992, art. 13), os
valores sem contexto decisivo em extratos de contrato ou termo de outorga cuja contraparte é pessoa
física (identificada por CPF), em frases com CPF e sem CNPJ e na seção de renda ("RENDA FAMILIAR",
"Renda e despesas") de ficha cadastral, prontuário ou estudo social sobre pessoa ou família identificada
(com CPF, NIS ou código familiar), o dinheiro levado ou guardado ("R$ 950,00 em dinheiro") e as
repetições, no mesmo documento, de um valor já reconhecido como pessoal. Agência, conta, cartão e chave
PIX continuam nos tipos da categoria `FINANCEIRO`. Os valores de `VALOR_PESSOAL` não são propagados para
outros trechos do documento, pois a mesma quantia pode ter outro sentido em outra frase.

No perfil `identificadores`, `ECONOMICO` vira alerta; nos demais, é tarjado. Para manter legíveis as
remunerações de agentes públicos publicadas em transparência ativa, use um perfil personalizado com
`"ECONOMICO": "alertar"`.

### Falha fechada para identificadores

Nas categorias identificadoras com regra `tarjar`, um achado com confiança entre `score_alerta` e
`score_minimo` é tarjado por precaução, com o motivo "Identificador com confiança moderada — tarjado
por precaução". Nas demais categorias, o mesmo achado vira alerta. Expor um CPF ou telefone é
irreversível; uma tarja a mais é corrigível na revisão.

Também por esse princípio, números com formato de documento acompanhados da palavra correspondente
("CPF 123.456.789-00") são tarjados mesmo com dígito verificador inválido: erros de digitação continuam
identificando a pessoa.

### Agentes públicos

Com a opção `preservar_agentes_publicos` (CLI `--preservar-agentes-publicos`; caixa de seleção na
interface), nomes precedidos ou seguidos de cargo público ("Secretária de Estado de Saúde, Fulana";
"Fulano, diretor-geral") recebem `manter`, com o motivo "Agente público no exercício da função
(transparência ativa)". A aplicação dessa opção deve ser validada pela área jurídica.

### Listas de permissão e de bloqueio

- **Permitir:** termos que nunca são tarjados, comparados sem distinção de caixa e acentos e com
  limite de palavra. Ocorrências contidas em um termo permitido recebem `manter`.
- **Bloquear:** termos sempre tarjados, em qualquer ocorrência, com o tipo `MANUAL`.

### Perfil personalizado

```python
from themis_lgpd import Anonimizador, Perfil, PERFIS

perfil = Perfil("ouvidoria", "Ouvidoria", "LAI com tarja de localidades",
                {**PERFIS["lai"].regras, "LOCALIDADE": "tarjar"})
anon = Anonimizador(perfil)
```

Categorias ausentes das regras recebem `alertar`.

## Informações mantidas de propósito

Em atenção à LAI, permanecem legíveis no perfil `lai`: números de leis, editais, contratos, notas
fiscais, empenhos e termos de parceria; nomes de instituições; CNPJ; expressões genéricas de estado
emocional ("estou chateada com a demora"); termos sensíveis sem vínculo com pessoa determinada (como
alerta); idades em normas, requisitos, faixas e estatísticas; valores de contratos com empresas,
orçamentos, repasses, totais de programas e valores fixados em norma.
