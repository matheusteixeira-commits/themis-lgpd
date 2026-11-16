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
| `CPF` | CPF | `[CPF]` | 100 | Módulo 11; formato pontuado ou contexto dispensam a validação | 529.982.247-25 |
| `RG` | RG / Carteira de identidade | `[RG]` | 95 | Contexto obrigatório ("RG", "identidade", "CIN"); inclui órgão emissor e UF | RG 1.234.567 SSP/DF |
| `CNH` | CNH | `[CNH]` | 95 | Dígitos verificadores; contexto obrigatório | CNH 39825979149 |
| `PIS` | PIS/PASEP/NIS/NIT | `[PIS]` | 95 | Módulo 11; sem pontuação característica, exige contexto | 190.74833.78-3 |
| `TITULO_ELEITOR` | Título de eleitor | `[TÍTULO DE ELEITOR]` | 95 | Dígitos verificadores com código da UF | 8762 3286 2410 |
| `CNS` | Cartão Nacional de Saúde (SUS) | `[CARTÃO SUS]` | 95 | Módulo 11 (definitivo e provisório) | 112 9040 4796 6691 |
| `PASSAPORTE` | Passaporte | `[PASSAPORTE]` | 90 | Contexto obrigatório | passaporte AB123456 |
| `CTPS` | Carteira de trabalho | `[CTPS]` | 90 | Contexto obrigatório; inclui série e UF | CTPS 1234567 série 0012/DF |
| `CERTIDAO` | Matrícula de certidão civil | `[CERTIDÃO]` | 90 | Formato de 32 dígitos (Provimento CNJ nº 3/2009); termo com livro e folha | termo 4521, livro A-32, folha 118 |
| `MATRICULA` | Matrícula funcional | `[MATRÍCULA]` | 85 | Contexto obrigatório ("matrícula", "SIAPE", "MASP", "ID funcional", "registro funcional") | MASP 1234567-8 |
| `REGISTRO_PROFISSIONAL` | Registro profissional (OAB, CRM, RNTRC, CADASTUR…) | `[REGISTRO PROFISSIONAL]` | 85 | Sigla do conselho, com ou sem região, inclusive em minúsculas | OAB/DF 12.345; CRN-3 88421 |
| `BENEFICIO` | Benefício previdenciário ou social (NB do INSS) | `[BENEFÍCIO]` | 90 | Contexto obrigatório ("NB", "benefício") | NB 123.456.789-0 |
| `REGISTRO_SAUDE` | Prontuário, DNV, AIH ou cartão de vacina | `[REGISTRO DE SAÚDE]` | 85 | Contexto obrigatório | prontuário nº 2891163 |
| `MATRICULA_ESCOLAR` | Matrícula escolar ou RA | `[MATRÍCULA ESCOLAR]` | 85 | Contexto obrigatório ("RA", "registro acadêmico", "matrícula do aluno") | RA 123456789-X |
| `INSCRICAO_IMOVEL` | Inscrição imobiliária (IPTU, CCM) | `[INSCRIÇÃO]` | 80 | Contexto obrigatório | inscrição imobiliária 01.23.456.0789.001 |
| `DOCUMENTO` | Número de documento | `[DOCUMENTO]` | 80 | Contexto obrigatório | Documento do cliente: 1234567-8 |
| `DATA_NASCIMENTO` | Data de nascimento | `[DATA DE NASCIMENTO]` | 85 | Contexto ("nascido em", "data de nascimento", "DN") ou coluna "Nascimento" de tabela; formatos numérico, ISO, por extenso, com mês abreviado e de registro civil | nascida em 12/03/1985; 1º de março de 1985 |
| `IDADE` | Idade de pessoa | `[IDADE]` | 80 | Contexto que liga a idade a uma pessoa identificável (ver [Idade e valores de pessoa natural](#idade-e-valores-de-pessoa-natural)) | Idade: 52 anos; Fulano, 33 anos, CPF…; o filho, de 6 anos |

### Contato, localização e finanças

| Código | Nome | Etiqueta | Prioridade | Validação | Exemplo fictício |
|---|---|---|---|---|---|
| `EMAIL` | E-mail | `[E-MAIL]` | 90 | Formato; inclui formas ofuscadas | maria.souza@exemplo.com.br; joao arroba gmail ponto com; joao [arroba] gmail [ponto] com; joao @ gmail . com |
| `TELEFONE` | Telefone | `[TELEFONE]` | 85 | Padrões próprios e biblioteca phonenumbers (região BR) | (61) 99876-5432 |
| `PERFIL_REDE_SOCIAL` | Perfil em rede social | `[PERFIL]` | 85 | `@usuario` com contexto ou URL de rede social | @maria.souza |
| `IP` | Endereço IP | `[IP]` | 80 | Reconhecedor do Presidio | 203.0.113.45 |
| `ENDERECO` | Endereço | `[ENDEREÇO]` | 70 | Logradouro (inclusive abreviado e numerado) e componentes; propriedades e localidades rurais; rodovias das 27 UFs; endereçamento do DF; município ou região de residência | Rua B-15, Quadra 30, Lote 10; Sítio Boa Esperança; PE-060, km 10; QNM 12 Conjunto B Casa 4 |
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
| `PROCESSO_ADMINISTRATIVO` | Processo administrativo (SEI/NUP) | `[PROCESSO]` | 80 | Ano plausível; formatos federais e estaduais (NUP-21, SEI-MG, SEI-PE, SEI-BA, RJ); contexto para formatos livres (PROA, eProtocolo, SGPe) | 00410-00012345/2024-11; 1500.01.0012345/2024-12 |
| `PROTOCOLO` | Protocolo | `[PROTOCOLO]` | 75 | Contexto ("protocolo", "ocorrência", "boletim") | protocolo nº 2024123456 |

### Pessoa jurídica, localidades e outros

| Código | Nome | Etiqueta | Prioridade | Observação |
|---|---|---|---|---|
| `CNPJ` | CNPJ | `[CNPJ]` | 90 | Módulo 11, inclusive o CNPJ alfanumérico (IN RFB nº 2.229/2024), como GM.Y1U.F3A/0001-01 |
| `LOCALIDADE` | Cidade ou região administrativa | `[LOCALIDADE]` | 30 | Os 5.570 municípios do IBGE ("Cidade/UF" com conferência da UF, "município de Cidade", menção isolada não ambígua) e as regiões administrativas do DF; "moro em campinas" e "resido em Taguatinga" são classificados como `ENDERECO` |
| `URL` | Endereço de internet | `[URL]` | 20 | |
| `QUASE_IDENTIFICADOR` | Quase-identificador | `[QUASE-IDENTIFICADOR]` | 15 | Função, local e turno ("atendente do guichê 4 na tarde de ontem") |
| `NUMERO_NAO_IDENTIFICADO` | Número longo não identificado | `[NÚMERO]` | 10 | Reservado; não é produzido pelos reconhecedores padrão |
| `MANUAL` | Trecho tarjado manualmente | `[TARJADO]` | 110 | Lista de bloqueio e tarjas manuais da revisão |

### Dados sensíveis, intimidade e menores

| Código | Nome | Etiqueta | Categoria | Exemplos de achado |
|---|---|---|---|---|
| `SAUDE` | Dado de saúde | `[DADO DE SAÚDE]` | `SENSIVEL` | CID F32.1, F41.1 e G40; C.I.D. 6A70.1; "diagnosticado com depressão"; "asma"; "faço uso de fluoxetina 20mg"; "laqueadura" |
| `RELIGIAO` | Convicção religiosa | `[CONVICÇÃO RELIGIOSA]` | `SENSIVEL` | "sou católico" |
| `OPINIAO_POLITICA` | Opinião política | `[OPINIÃO POLÍTICA]` | `SENSIVEL` | filiação partidária |
| `FILIACAO_SINDICAL` | Filiação sindical ou associativa | `[FILIAÇÃO]` | `SENSIVEL` | "sou sindicalizado" |
| `VIDA_SEXUAL` | Vida sexual / orientação sexual | `[VIDA SEXUAL]` | `SENSIVEL` | |
| `GENETICO_BIOMETRICO` | Dado genético ou biométrico | `[DADO BIOMÉTRICO]` | `SENSIVEL` | exame de DNA, impressão digital |
| `ORIGEM_RACIAL` | Origem racial ou étnica | `[ORIGEM RACIAL]` | `SENSIVEL` | |
| `VIOLENCIA` | Situação de violência ou risco | `[SITUAÇÃO DE VIOLÊNCIA]` | `INTIMIDADE` | "vítima de violência doméstica"; "medida protetiva" |
| `DADO_DE_MENOR` | Dado de criança ou adolescente | `[DADO DE MENOR]` | `MENOR` | "meu filho de 9 anos" |

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

### Nomes de pessoas

Três reconhecedores se complementam:

| Reconhecedor | Funcionamento | Funciona em minúsculas e caixa alta |
|---|---|---|
| `BR_Nomes_Modelo` | Entidades `PER` (e `MISC`/`LOC` iniciadas por prenome conhecido) do modelo `pt_core_news_lg`, filtradas: títulos, letras isoladas, algarismos romanos, palavras comuns, nomes de instituições, normas e lugares | não |
| `BR_Nomes_Lista` | Sequências iniciadas por um dos cerca de 700 prenomes brasileiros das listas (inclusive os mais frequentes por sexo, década e UF no Censo 2010 do IBGE), seguidos de sobrenomes ou conectores; em CAIXA ALTA, palavras fora das listas entre nomes ou no fim do nome | sim |
| `BR_Nomes_Gatilho` | Nome após gatilho de contexto ("meu nome é", "requerente:", "Atenciosamente,", "sou a…") | sim |

Nomes que integram nomes de lugares, instituições ou normas ("São Paulo", "Escola Paulo Freire",
"Lei Maria da Penha") não são tratados como pessoa.

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

**Idade** é tarjada no campo de formulário ("Idade: 52 anos", "Idade: 47 a"), em aposto ao nome, às
iniciais ou ao papel da pessoa ("Fulano, 33 anos, CPF…", "P.R.S., 8 anos;", "a genitora, de 29 anos",
"um sobrinho de 12 anos"), com verbo ("hoje com 3 anos", "contava 20 anos", "tem 9 anos"), em "62
(sessenta e dois) anos de idade", ao lado da data de nascimento ("10/10/2010 (15 anos)") e na coluna
"Idade" de tabelas de pessoas. Permanecem legíveis faixas e requisitos ("de 6 a 14 anos", "idade
mínima de 18 anos", "a partir de 60 anos", "18 anos ou mais"), durações ("há 10 anos", "pena de 6 anos",
"36 anos de contribuição", "prazo de 2 anos"), grupos ("pessoas com 60 anos"), a idade em que algo
ocorreu ("aos 14 anos") e disposições normativas sem pessoa identificada ("o servidor com 75 anos de
idade será aposentado").

**Valores recebidos, pagos ou devidos por pessoa natural** — remuneração, salário, proventos, renda,
benefício, pensão, bolsa, aluguel, dívida, parcela, desconto em folha, multa, fiança, indenização,
prejuízo alegado, bem subtraído ou avaliado — recebem `VALOR_PESSOAL`, na categoria `ECONOMICO`, em
reais, em salários mínimos ("pensão de um salário mínimo") ou como percentual dos rendimentos ("pensão
alimentícia de 30% dos rendimentos líquidos"). Decide a expressão mais próxima antes do valor, na mesma
frase:

- expressão de valor público (contrato, licitação, proposta, orçamento, dotação, repasse, empresa,
  erário, tabela, valor estimado ou global, valor fixado, taxa, valor da causa) mantém o valor legível,
  assim como limites e faixas ("até R$ 660,00", "de R$ 1.000,00 a R$ 10.000,00"), médias e valores por
  grupo ("a renda média das famílias", "R$ 600,00 por família") e dívidas do próprio ente ("o débito do
  Município");
- expressão de vínculo pessoal (renda, remuneração, dívida, multa…) tarja o valor, salvo em oração
  normativa ("fica fixado o subsídio do cargo em…", "o servidor fará jus a diárias de…") ou atribuída a
  pessoa jurídica, quando a frase não identifica uma pessoa (CPF, iniciais, tratamento, primeira
  pessoa);
- expressão de vínculo fraco (benefício, auxílio, bolsa, recebeu, pagou) tarja o valor quando a frase
  designa uma pessoa ("a requerente", "a família", "seu benefício").

Também são tarjados os valores das tabelas de pessoas (com coluna de nome, parentesco, CPF, matrícula
ou rubrica de contracheque), todos os valores de declarações de bens (Lei nº 8.429/1992, art. 13), os
valores sem contexto decisivo em extratos de contrato ou termo de outorga cuja contraparte é pessoa
física (identificada por CPF) e em frases com CPF e sem CNPJ, e as repetições, no mesmo documento, de um
valor já reconhecido como pessoal. Agência, conta, cartão e chave PIX continuam nos tipos da categoria
`FINANCEIRO`. Os valores de `VALOR_PESSOAL` não são propagados para outros trechos do documento, pois a
mesma quantia pode ter outro sentido em outra frase.

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
