# Corpus de desenvolvimento de documentos oficiais

Duzentos documentos oficiais fictícios, em quatro lotes temáticos, anotados segundo as mesmas
diretrizes e convenções do conjunto de referência (`benchmark/ouro/DIRETRIZES.md`):

| Lote | Tema | Documentos | Entidades | Concordância redator × final (F1) |
|---|---|---:|---:|---:|
| C | saúde e perícia | 50 | 1.154 | 0,913 |
| D | gestão de pessoas e processo disciplinar | 50 | 666 | 0,996 |
| E | assistência social, segurança pública, justiça e ouvidoria | 50 | 839 | 0,978 |
| F | expediente administrativo e documentos públicos | 50 | 331 | 0,983 |

Cada lote foi redigido e anotado por um redator e revisado por inteiro por um revisor, que levantou
os dados pessoais de cada texto antes de comparar com a anotação do redator. A pasta `processo/`
guarda a anotação do redator e o relatório de revisão de cada lote. Nenhum dos dois leu o código do
sistema nem o conjunto de referência.

Diferentemente do conjunto de referência, este corpus é de **desenvolvimento**: `particionar.py`
o divide, pela mesma regra do esic-ner, em `ajuste.jsonl` (análise de erros com
`benchmark/avaliar_ouro.py --erros` e treinamento) e `selecao.jsonl` (só métricas agregadas).
