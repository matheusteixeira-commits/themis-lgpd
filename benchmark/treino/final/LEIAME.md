# Avaliação final do treinamento

Medições do conjunto de referência (`benchmark/ouro`) e da partição de teste do esic-ner (lockbox),
os dois conjuntos que nunca foram usados para examinar erros nem para escolher entre alternativas.

| Pasta | Commit | Conteúdo |
|---|---|---|
| `eef0f77/` | `eef0f77` | Avaliação ao fim do terceiro ciclo, com as decisões de regra e do classificador já fechadas |
| `.` | versão publicada | A mesma avaliação depois de duas correções decididas fora destes conjuntos (verificação final de PDFs e sobrenome com palavra de instituição), e as demais medições da versão publicada |

As métricas do conjunto de referência e da lockbox são idênticas nas duas pastas
(`comparacao_ouro_eef0f77.json`, `comparacao_lockbox_eef0f77.json`), assim como as das seleções, do
ajuste e dos lotes adversariais em relação ao ciclo 3 (`comparacao_*_ciclo3.json`).

Comparações pareadas da versão publicada:

- `comparacao_ouro_linha_de_base.json`, `comparacao_ouro_ciclo1.json`, `comparacao_ouro_ciclo2.json`:
  conjunto de referência contra a linha de base e contra o fim de cada ciclo;
- `comparacao_lockbox_linha_de_base.json`: partição de teste do esic-ner contra a medição anterior ao
  treinamento.

Cada uso da partição de teste está em `benchmark/treino/registro_lockbox.jsonl`, com o motivo e o
commit. Os arquivos `*_docs.jsonl` guardam só contagens por documento e o resumo SHA-256 de cada texto.
