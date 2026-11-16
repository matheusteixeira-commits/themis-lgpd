# Lote R1 — sondagem adversarial: forma e estrutura difíceis

Sistema sondado como caixa-preta: Themis LGPD, perfil `lai`, avaliado por `benchmark/avaliar_ouro.py`.
Só foram usados os erros que o avaliador aponta nos documentos deste lote.

## Lote

| Item | Valor |
|---|---|
| Documentos | 30 (R1-001 a R1-015 na rodada 1; R1-016 a R1-030 na rodada 2) |
| UFs | 27, uma por documento e três repetidas (BA, GO, PR) |
| Gêneros | 24: atas, listas de presença, escalas, folhas de pagamento, de frequência e de bolsas, relações de beneficiários e de diárias, fichas cadastrais e de matrícula, requerimentos, ofícios, certidão, BO, termo de declaração, TCO, portaria, diário oficial, despacho SEI, edital de resultado, de proclamas e de notificação, registro de vacinação, relatório social |
| Tamanho | 152 a 497 palavras |
| Entidades anotadas (valor distinto por documento) | 860: NOME_PESSOA 334, DADO_FINANCEIRO 117, DOC_PESSOAL 113, DOC_PROFISSIONAL 85, ID_PROCESSUAL 55, DATA_NASC 51, DADO_SAUDE 45, ENDERECO 24, CONTATO 21, ID_VEICULO 12, DADO_SENSIVEL 3 |
| Trechos públicos | 426 (211 na rodada 1) |

Arquivos:

- `anotacao_redator.jsonl`: os 30 documentos com entidades e públicos;
- `geracao/`: programas de geração (`docs_br.py` gera os números com dígito verificador; `marcacao.py` é a
  marcação inline `⟦RÓTULO|valor⟧` com as verificações de coerência; `rodada1.py`, `rodada2.py`;
  `gerar.py` monta o JSONL).

Para refazer o arquivo: `python benchmark/adversarial/processo/lote_R1/geracao/gerar.py`. Os 15 primeiros
registros saem idênticos aos avaliados na rodada 1.

Todos os documentos foram anotados antes de qualquer execução do sistema. `ferramentas.py validar`
devolve "sem problemas". Depois da saída do sistema, a anotação mudou uma única vez e o texto não
mudou: em R1-020, "internado", que descreve a internação do paciente identificado, foi anotado como
DADO_SAUDE. É uma omissão pelas diretrizes (tratamento ligado a pessoa) e segue a mesma regra já
aplicada em R1-030 ("internação de 12 dias em UTI neonatal"). Nenhum documento foi descartado nem
reescrito.

## Métricas agregadas

| Métrica | Rodada 1 (R1-001 a 015) | Só rodada 2 (R1-016 a 030) | Final (30 documentos) |
|---|---:|---:|---:|
| Recall de entidades | 0,650 | 0,481 | **0,569** |
| Recall estrito | 0,641 | 0,476 | 0,562 |
| Precisão das tarjas | 0,924 | 0,870 | 0,899 |
| Preservação dos públicos | 0,897 | 0,804 | 0,853 |
| Documentos com vazamento | 0,933 (14/15) | 1,000 (15/15) | 0,967 (29/30) |
| Tarja fora do gabarito | 0,125 | 0,216 | 0,167 |

Recall por rótulo:

| Rótulo | Rodada 1 | Final |
|---|---:|---:|
| NOME_PESSOA | 0,867 | 0,751 |
| DOC_PESSOAL | 0,982 | 0,912 |
| DOC_PROFISSIONAL | 0,362 | 0,318 |
| DADO_FINANCEIRO | 0,063 | 0,086 |
| DATA_NASC | 0,313 | 0,255 |
| ID_PROCESSUAL | 0,375 | 0,291 |
| DADO_SAUDE | 0,609 | 0,444 |
| ENDERECO | 0,750 | 0,750 |
| CONTATO | 0,909 | 0,857 |
| ID_VEICULO | 0,500 | 0,833 |
| DADO_SENSIVEL | 1,000 | 1,000 |

Métricas brutas: `.trabalho/metricas_R1_r1.json`, `.trabalho/metricas_R1_r2.json` e
`.trabalho/metricas_R1_final.json`. Erros: `.trabalho/erros_R1_r1.jsonl` e
`.trabalho/erros_R1_final.jsonl`.

## Classes de falha

Cada erro do avaliador recebe uma única classe, conforme a forma do texto que o provoca. A
classificação é feita por `.trabalho/classificar_R1.py`. Nos vazamentos, a unidade é o valor distinto
por documento, a mesma das métricas. Na tarja indevida, a unidade é cada tarja fora do gabarito, mais
o trecho público atingido pela extensão de uma tarja sobre dado pessoal vizinho. Os exemplos abaixo
são fictícios e curtos e não reproduzem trechos do lote.

### Vazamentos (dado pessoal legível)

| Classe | Forma do texto | R1 | Final | Docs | Exemplo fictício |
|---|---|---:|---:|---:|---|
| V1 | Valor em coluna de tabela, CSV ou formulário, com o rótulo só no cabeçalho ou num bloco separado dos valores: matrícula, COREN, RG, inscrição, data de nascimento, agência/conta, salário, bolsa, diária, multa, RENAVAM | 103 | 199 | 13 | `MATR.  NOME ... LÍQUIDO` / `004410  ROSA M. TELES  ...  2.310,55` |
| V2 | Valor monetário de pessoa natural em texto corrido, sem gatilho de salário ou renda (pensão, prejuízo, benefício, renda per capita) | 4 | 6 | 4 | `pensão mensal de R$ 1.180,00`; `PREJUIZO DE 900 REAIS` |
| V3 | Nome em forma tabular: invertido (SOBRENOME, prenome ou iniciais), fragmento na linha de continuação da célula, só sobrenome (nome de guerra) | 13 | 57 | 8 | `PINHEIRO, A. L.`; linha `      FONTES BARRETO`; `SD PM 100.000-0 BRAGANÇA` |
| V4 | Valor partido por quebra de linha ou de página: hifenização em caixa alta, `¬` ou `- ` no fim da linha, quebra após o hífen de número, nome cortado por rodapé e cabeçalho da página seguinte | 9 | 11 | 3 | `JOSÉ CARLOS PE-⏎REIRA`; `NIS 100.00000.00-⏎0`; `Fon¬⏎seca` |
| V5 | Ruído de digitalização: OCR (rn↔m, l↔1, O↔0, espaço dentro de palavra), campos em quadrícula com caracteres espaçados, rótulo colado ao valor sem espaço | 3 | 18 | 4 | `Rairnundo`; `C0STA`; `Ma ria`; `N O M E   J O A N A`; `Aluno(a):JOANA LIMA` |
| V6 | Data, idade ou número sem pontuação, com espaço no lugar da barra ou por extenso; CID sem ponto | 5 | 13 | 4 | `NASC 05 11 1972`; `nascida aos três dias do mês de maio de mil novecentos e setenta`; `PROC N 1234 2023`; `CID 10 F32 1` |
| V7 | Nome completo em lista ou depois de rótulo, sem gatilho reconhecido (prenome raro, caixa alta) | 4 | 9 | 7 | `Interessado(a): GILDENOR PAIXÃO VERAS` |
| V8 | Identificador com rótulo abreviado ou incomum, ou só com posto ou sigla antes | 4 | 27 | 6 | `MATR 30551`; `PROTOC 2023/004411`; `Nº FICHA: 0212/2023`; `PAJ nº 2023/0001-01` |
| V9 | Endereço em forma atípica: sem pontuação e abreviado, ou rural do Sul (`Linha …, km`) | 2 | 2 | 2 | `END R PADRE ANCHIETA 77 AP 12`; `Linha Santa Lúcia, s/n, km 12` |
| V10 | Expressão de saúde abreviada, em código de tabela ou fora do vocabulário | 5 | 21 | 12 | `PcD (def. visual)`; `Licença-saúde 03 a 05/06`; `TRÍPLICE VIRAL D2`; `ESCORIAÇÕES NO BRAÇO` |
| V11 | Duas colunas lidas linha a linha: o nome, o termo de saúde ou a idade fica dividido por texto da outra coluna | 4 | 8 | 2 | `…a vereadora Ana Lú-   [texto da coluna 2]⏎[texto da coluna 1]   cia Ferraz…` |
| **Total** | | **156** | **371** | | |

### Tarja indevida (trecho público tarjado ou tarja fora do gabarito)

| Classe | Forma do texto | R1 | Final | Exemplo fictício |
|---|---|---:|---:|---|
| T1 | Endereço, CEP e telefone institucionais no timbre ou no rodapé, repetidos a cada página. A tarja de endereço avança sobre o município e a UF do órgão | 9 | 30 | `Rua do Comércio, 100 – Centro – Cidade/UF – CEP 00000-000 – (00) 3000-0000` |
| T2 | Nome de instituição que contém nome de pessoa, inteiro ou partido em célula ou coluna | 7 | 11 | `EEF PROFESSORA MARIA` / `LUÍZA CORDEIRO` (célula partida) |
| T3 | Número de publicação, ato ou verificação tomado por protocolo ou por dado: protocolo do DOE, código CRC/verificador do SEI, número de indicação legislativa sem a palavra que o precede, nota de empenho e ordem bancária | 4 | 9 | `Protocolo 1290000`; `código CRC= 4AB9F201`; `2024NE00123` |
| T4 | Palavra comum, abreviatura, topônimo ou cabeçalho tomado por nome: `Enfª`, `Filho`, `V. Sa.`, município homônimo de sobrenome em tabela, bairro com nome de pessoa, cabeçalho de CSV | 5 | 11 | `Sousa 07/05 a 09/05` (destino de diária); `ORD;NOME DO` |
| T5 | Sigla de UF ou de órgão, ou município, colada a dado pessoal e tarjada por extensão | 5 | 7 | `RG 0.000.000 SDS/PE`; `COREN-AM 000.000`; `…AP. 10 – CIDADE/UF` |
| T6 | Dado de pessoa jurídica (placa de veículo de empresa) e tarja de saúde estendida além da expressão | 1 | 2 | `hipertensão em acompanhamento⟦ na UBS do P.A.⟧` |
| **Total** | | **31** | **70** | |

## Leitura

1. A falha dominante é estrutural: em tabela, CSV e formulário, o valor fica longe da palavra-chave
   (V1, 54% dos vazamentos finais). Formatos com dígito verificador resistem: CPF e CNS foram
   protegidos mesmo sem pontuação, partidos após o hífen ou entre grupos de dígitos. Já matrícula,
   registro profissional, RG de SP, inscrição, data de nascimento, agência/conta e valores ficam
   expostos quando o rótulo está só no cabeçalho da coluna. DADO_FINANCEIRO tem recall de 0,086:
   só foram tarjados os 10 valores com contexto explícito na mesma frase ou no mesmo campo (renda,
   "Ag.:"/"C/C:", transferência por PIX, Bolsa Família). Nenhum valor em coluna foi tarjado.
2. Nomes em forma de lista quase não são reconhecidos quando aparecem invertidos ("SOBRENOME,
   prenome"), como fragmento de célula ou como sobrenome isolado (nome de guerra). A propagação não
   alcança essas formas: em R1-003, "SALDANHA, K. R." ficou legível na página 2, embora o nome
   completo tenha sido tarjado na página 1 (V3, 57).
3. A reunião de palavras hifenizadas funciona em nomes com caixa mista ("Mar-⏎ques", "Lu-⏎ísa").
   Falha em 3 de 4 nomes em caixa alta, com `¬`, com hífen seguido de espaço, em números
   quebrados após o hífen (NIS, telefone, placa) e em nome cortado por rodapé e cabeçalho de
   página (V4). Já o CPF quebrado após o hífen e o CNS quebrado entre grupos foram protegidos.
4. O ruído de digitalização só é normalizado quando há troca de letras dentro de números. Não são
   normalizados: espaço dentro de nome, algarismo no lugar de letra em nome, campos em quadrícula
   e rótulos colados (V5). Na ficha em quadrícula (R1-030), os oito campos em quadrícula vazaram;
   o NIS foi apenas sinalizado.
5. Datas e idades por extenso ou sem barras não são reconhecidas como data de nascimento (V6). No
   edital de proclamas (R1-019), as cinco datas e idades por extenso vazaram.
6. Na tarja indevida, os casos mais frequentes são o endereço institucional no timbre e no rodapé
   (T1), que leva junto município e UF a cada página, e o nome de escola com nome de pessoa partido
   em células (T2). Na rodada 2, a precisão caiu para 0,870 e a preservação dos públicos para 0,804.

## Observações de método

- Quebras de linha dentro do valor foram copiadas como estão no texto (convenção 2). Fragmentos
  separados por texto de outra coluna ou por cabeçalho e rodapé são entradas separadas.
- O endereço, o CEP e o telefone de órgão público entram em `publicos` (dado de pessoa jurídica,
  conforme as diretrizes). A placa e a multa de pessoa jurídica (R1-029) também são públicas.
- Valores de diárias, bolsas, multas, salários, pensões e prejuízos de pessoa natural são
  DADO_FINANCEIRO (convenção 7). Totais da unidade ou do edital são públicos.
- O CPF parcialmente mascarado das publicações oficiais (`***.000.000-**`) foi anotado como
  DOC_PESSOAL. A matrícula acadêmica, a inscrição em seleção, o AIT, o número de vistoria e a
  referência a livro e folha de pacto antenupcial foram anotados como ID_PROCESSUAL (convenção 8).
