# Comparação

esic-ner (teste, 975 pedidos) e benchmark sintético (1000 documentos, semente 7); perfil LAI do Themis. Gerado por `benchmark/comparar.py`.

| Métrica | Presidio puro (pt) | Themis 1.1.0.dev0 (sobre o Presidio) |
|---|---|---|
| esic-ner: entidades pessoais tarjadas | 53.3% | 95.1% |
| esic-ner: nomes tarjados | 98.9% | 99.7% |
| esic-ner: documentos pessoais tarjados | 7.9% | 100.0% |
| esic-ner: datas de nascimento tarjadas | 100.0% | 100.0% |
| esic-ner: pedidos com algum vazamento | 93.3% | 9.9% |
| esic-ner: F1 de triagem | 0.733 | 0.956 |
| esic-ner: tarja fora do gabarito (excesso) | 30.8% | 5.3% |
| esic-ner: ms por pedido | 19 | 30 |
| sintético: identificadores tarjados | 57.7% | 99.6% |
| sintético: documentos com vazamento | 99.8% | 3.1% |
