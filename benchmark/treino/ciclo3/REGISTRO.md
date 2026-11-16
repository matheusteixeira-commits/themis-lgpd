# Ciclo 3 de melhoria — registro

## Organização

O ciclo teve duas etapas.

**Lotes adversariais** (`benchmark/adversarial`, ver o `LEIAME.md` da pasta): 120 documentos oficiais
fictícios em quatro lotes (forma e estrutura, identidades e localização, dados sensíveis fora do
registro clínico, armadilhas de precisão), redigidos por quem testou o sistema só pela saída, sem ler o
código, e anotados por um revisor independente que não viu os resultados do sistema. No sistema do
ciclo 2, esses documentos tinham recall de 0,665, precisão das tarjas de 0,835 e 75% de documentos com
vazamento (`benchmark/treino/ciclo2/adversarial.json`).

**Correção**: seis frentes, cada uma num ramo isolado (`treino3/*`) a partir da integração dos lotes,
numa cópia de trabalho sem o conjunto de referência, sem a lockbox e sem as seleções:

| Frente | Área | Testes de regressão |
|---|---|---|
| Forma e estrutura | `reconhecedores/tabelas.py` (novo), normalização em `texto.py`, tipo `UNIDADE_INSTITUCIONAL` | `tests/test_treino3_forma.py` |
| Nomes | `reconhecedores/nomes.py` | `tests/test_treino3_nomes.py` |
| Saúde e dados sensíveis | `reconhecedores/sensiveis.py`, vínculo em `motor.py`, `dados/medicamentos.txt` | `tests/test_treino3_saude.py` |
| Idade, nascimento e valores | `reconhecedores/pessoais.py`, data de nascimento em `documentos.py` | `tests/test_treino3_pessoais.py` |
| Documentos e processos | `documentos.py`, `financeiro.py`, `validadores.py` | `tests/test_treino3_documentos.py` |
| Endereços, contatos, veículos e quase-identificadores | `localizacao.py`, `institucional.py`, `contatos.py`, tipos `VEICULO_OFICIAL`, `CONTATO_EMPRESA` e `ENDERECO_EMPRESA` | `tests/test_treino3_localizacao.py` |

Fontes de análise de erros: lotes adversariais e partições de ajuste do corpus oficial e do esic-ner.
As seleções só podiam ser consultadas por `benchmark/treino/portao.py` (métricas agregadas, cada
consulta registrada, no máximo cinco por frente). Portões de cada frente: suíte de testes, ruff,
sintético (recall ≥ 0,99), nacional (recall e preservação ≥ 0,99), portão das seleções, nenhum rótulo
perdendo mais de 1 ponto de recall nos lotes adversariais e no ajuste oficial, precisão e preservação
caindo no máximo 0,5 ponto, e tempo por documento até 1,2 vez o da base.

## Disciplina de dados

Consultas ao portão das seleções: 14 (13 das frentes e 1 da integração).

| Frente | Consultas | Reprovadas | Correção depois da reprovação |
|---|---:|---:|---|
| Forma e estrutura | 2 | 1 | precisão da seleção oficial −1,55 ponto: quadrícula restrita a casas em maiúsculas e tabela de pessoas exigindo identificador ou nome confirmado |
| Nomes | 1 | 0 | — |
| Saúde e dados sensíveis | 4 | 1 | recall de saúde no esic-ner −0,63 ponto: exclusões de contagem e de enunciado normativo restritas a texto sem primeira pessoa |
| Idade, nascimento e valores | 1 | 0 | — |
| Documentos e processos | 2 | 1 | recall de processos no esic-ner −0,60 ponto: descartes de números públicos restritos a documentos expedidos pelo órgão |
| Endereços, contatos, veículos e quase-identificadores | 3 | 2 | recall de saúde no esic-ner −0,63 ponto: regras de precisão mais amplas só em documento com timbre |

As reprovações levaram, em todos os casos, a regras mais restritas, nunca a ajustes para a seleção.

Os registros de execução das seis frentes (2.034 operações) foram examinados por programa: nenhum
acesso ao conjunto de referência, à lockbox, aos textos das seleções ou à pasta do portão fora da
chamada ao próprio portão; toda carga do esic-ner usou a partição de ajuste. Uma listagem de pasta do
repositório principal mostrou o nome do arquivo da partição de teste do esic-ner, sem leitura.

## Integração

Os seis ramos foram integrados em `treino/integracao`; houve conflitos só na documentação de tipos e
no catálogo (tipos novos das frentes de forma e de localização), resolvidos preservando as duas
contribuições. O sistema integrado passou na suíte inteira (1.347 testes), no ruff, no sintético
(0,9963) e no nacional (validação 0,9996, desenvolvimento 1,0, preservação 1,0) e no portão das
seleções. Tempo por documento, medido na mesma sessão com execuções alternadas: 1,15 vez o do ciclo 2
nos documentos oficiais (0,130 s → 0,149 s, três execuções de cada) e 1,13 vez no esic-ner (32 ms →
36 ms, duas de cada).

## Exemplos copiados

As linhas acrescentadas desde o início do treinamento (ciclos 1 a 3, em `src`, `tests`, `docs` e nos
scripts de `benchmark`) foram comparadas com os corpora de desenvolvimento: valores anotados que
identificam alguém (nome de duas ou mais palavras, endereço, valor com quatro ou mais dígitos) e
sequências de seis palavras idênticas a trechos dos textos. Havia 321 ocorrências, todas em comentários,
docstrings, testes e documentação, nenhuma em regra ou lista. Foram substituídas por exemplos
fictícios de redação própria que mantêm a construção ilustrada ou testada. Restaram 16 sequências,
todas nomes oficiais ("Unidade Básica de Saúde da Família", "Portaria SVS/MS nº 344/1998") ou fórmulas
administrativas ("Atesto, para os devidos fins, que", "nomeado para o cargo em comissão de"). A árvore
sintática dos módulos ficou idêntica e as métricas dos conjuntos de ajuste e de seleção não mudaram.
Nenhum teste dependia da redação exata dos corpora.

## Resultados (comparação pareada com o ciclo 2)

Intervalos de confiança de 95% por *bootstrap* pareado; McNemar sobre documentos com vazamento.

**Lotes adversariais** (desenvolvimento deste ciclo; não estimam desempenho):

| Métrica | Ciclo 2 | Ciclo 3 | IC95 da diferença |
|---|---:|---:|---|
| Recall | 0,665 | 0,964 | [+0,252; +0,351] |
| Precisão das tarjas | 0,835 | 0,987 | [+0,116; +0,192] |
| Preservação de trechos públicos | 0,888 | 0,997 | [+0,091; +0,130] |
| Documentos com vazamento | 75,0% | 34,2% | 49 deixaram de vazar, 0 passaram a vazar |

**Documentos oficiais, seleção** (47 documentos, não usados na análise de erros):

| Métrica | Ciclo 2 | Ciclo 3 | IC95 da diferença |
|---|---:|---:|---|
| Recall | 0,916 | 0,927 | [+0,001; +0,024] |
| Precisão das tarjas | 0,904 | 0,918 | [−0,001; +0,032] |
| Preservação de trechos públicos | 0,946 | 0,966 | [+0,005; +0,037] |
| Documentos com vazamento | 65,8% | 57,9% | 3 deixaram de vazar, 0 passaram a vazar (p = 0,25) |

**esic-ner, seleção** (916 pedidos): recall 0,960 → 0,961, documentos com vazamento 9,9% → 9,7%
(1 deixou de vazar, nenhum passou a vazar), tarja fora do gabarito estável (0,0765 → 0,0763).

**Documentos oficiais, ajuste**: recall 0,986 → 0,990, precisão 0,961 → 0,965, preservação 0,990 →
0,993, documentos com vazamento 18,9% → 15,0% (5 deixaram de vazar, nenhum passou a vazar).

O ganho nas seleções é bem menor que nos lotes adversariais: as classes de falha desses lotes
(tabelas, ruído de digitalização, documentos de estrangeiros, armadilhas de documentos públicos) são
raras nos documentos comuns. O que se comprova nas seleções é que as correções não pioraram nenhum
rótulo e melhoraram recall e preservação.

## Recall estrito e política de extensão

O recall estrito caiu (seleção oficial 0,903 → 0,886; esic-ner 0,895 → 0,873) porque a sigla do
conselho, o órgão emissor e a UF do RG e do registro profissional passaram a ficar legíveis
("CRM-PE [REGISTRO PROFISSIONAL]"): o número continua tarjado, e sem ele a sigla não identifica
ninguém. O recall por entidade, que exige todos os dígitos cobertos, não muda.

## Classificador treinado no sistema integrado

Ablação por rótulo (`ablacao_integrada.json`, decisão em `decisao_classificador.json`): o artefato do
ciclo 2 continua sem alteração. Sem o classificador, os documentos oficiais com vazamento passariam de
57,9% para 71,1% na seleção (5 a 0) e os pedidos do esic-ner de 9,7% para 11,0% (6 a 0, p = 0,03),
com ganho de 0,6 ponto de precisão. `DADO_SENSIVEL` segue sem efeito medido e continua ativo pelo
critério do ciclo 2. O classificador não foi retreinado com os lotes adversariais: eles já serviram
de desenvolvimento para as regras, e um novo treino exigiria outra partição de validação.

## Não resolvido

- Texto em duas colunas lido linha a linha e nome cortado por cabeçalho ou rodapé de página: juntar os
  fragmentos exige que o motor divida a tarja em trechos não contíguos.
- Fala transcrita sem termo de saúde ("subiu na laje dizendo que ia se jogar") e agressão descrita só
  pelo verbo: cobrir esses casos dependeria da redação de cada documento.
- Quase-identificador sem elemento que individualize ("professor da escola multisseriada").
- Valores, datas e identificadores em formulário em quadrícula sem rótulo.
- Na seleção oficial, os rótulos mais fracos continuam sendo dados sensíveis (0,44), quase-identificadores
  (0,56) e valores de pessoa natural (0,78).
