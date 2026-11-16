# Lotes adversariais

Cento e vinte documentos oficiais fictícios, em quatro lotes, redigidos para provocar erros do sistema:
deixar dado pessoal visível ou tarjar o que deve permanecer legível. A anotação segue as diretrizes e
convenções do conjunto de referência (`benchmark/ouro/DIRETRIZES.md`).

| Lote | Tema | Documentos | Entidades | Trechos públicos | Concordância redator × final (F1) |
|---|---|---:|---:|---:|---:|
| R1 | forma e estrutura difíceis: tabelas, formulários, colunas, quebras de linha e de página, ruído de OCR, caixa alta | 30 | 879 | 537 | 0,979 |
| R2 | identidades e localização: nomes de origens diversas, documentos de estrangeiros, idades e datas atípicas, endereços rurais, de aldeia, de ocupação e de pessoas em situação de rua, quase-identificadores | 30 | 765 | 409 | 0,990 |
| R3 | dados sensíveis e vulnerabilidade fora do registro clínico: fala transcrita, relatos, ouvidoria, assistência social, execução penal, escola | 30 | 566 | 405 | 0,884 |
| R4 | armadilhas de precisão: diários oficiais, editais, contratos, leis, relatórios de gestão e boletins, densos em informação pública | 30 | 116 | 1.126 | 1,000 |

Todos os lotes cobrem as 27 UFs.

## Processo

Cada lote foi redigido em duas rodadas por um redator que testou o sistema como caixa-preta, sem ler o
código: os 15 primeiros documentos foram anotados antes da primeira execução do avaliador
(`benchmark/avaliar_ouro.py --erros`); os 15 seguintes exploram, em variantes realistas, as classes de
falha observadas, e também foram anotados antes de o sistema ser executado sobre eles. Nenhum documento
foi descartado ou reescrito depois de visto o resultado do sistema.

Um revisor independente, que não executou o sistema nem leu os resultados da sondagem, anotou cada
texto por conta própria antes de compará-lo com a anotação do redator e definiu a anotação final
(`lotes/`). A pasta `processo/` guarda, para cada lote, a anotação do redator, o relatório de sondagem
(classes de falha e métricas do sistema da época) e o relatório de revisão.

## Uso

Os lotes são de **desenvolvimento**: servem à análise de erros (`--erros` é aceito neles) e à escrita de
testes de regressão. Como foram construídos para fazer o sistema errar, não representam a distribuição
dos documentos reais: as métricas neles medem robustez em condições adversas, não o desempenho
esperado, e, depois de usados para corrigir regras, deixam de ser estimativas independentes.
