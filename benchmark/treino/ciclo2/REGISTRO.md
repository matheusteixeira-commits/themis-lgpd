# Ciclo 2 de melhoria — registro

## Organização

Seis frentes de trabalho, cada uma com uma área de código própria e um ramo isolado (`treino2/*`), numa
cópia de trabalho da qual o conjunto de referência (`benchmark/ouro`) foi removido:

| Frente | Área | Testes de regressão |
|---|---|---|
| Nomes | `reconhecedores/nomes.py` | `tests/test_treino2_nomes.py` |
| Saúde e dados sensíveis | `reconhecedores/sensiveis.py` (exceto quase-identificadores), vínculo em `motor.py` | `tests/test_treino2_saude.py` |
| Idade, nascimento e valores | `reconhecedores/pessoais.py` (novo), data de nascimento em `documentos.py`, tipos `IDADE` e `VALOR_PESSOAL` | `tests/test_treino2_pessoais.py` |
| Processos e documentos | `reconhecedores/documentos.py`, processos em `financeiro.py` | `tests/test_treino2_processos.py` |
| Endereços, contatos, veículos e quase-identificadores | `localizacao.py`, `institucional.py` (novo), veículos em `financeiro.py`, quase-identificadores em `sensiveis.py` | `tests/test_treino2_localizacao.py` |
| Classificador treinado | `aprendido.py`, treino e artefato | `tests/test_treino2_modelo.py` |

Fontes de análise de erros: partições de ajuste do esic-ner e do corpus de documentos oficiais
(`benchmark/avaliar_ouro.py --erros`). Escolha entre alternativas: partições de seleção, por métricas
agregadas. Cada frente cumpriu os portões antes de entregar: suíte de testes, ruff, benchmark sintético
(recall ≥ 0,99), benchmark nacional (recall e preservação ≥ 0,99), esic-ner seleção (nenhum rótulo perde
mais de 0,5 ponto; tarja fora do gabarito sobe no máximo 0,5 ponto), documentos oficiais seleção
(precisão e preservação caem no máximo 0,5 ponto; nenhum rótulo perde mais de 1 ponto) e tempo por
documento até 1,3 vez o do ciclo anterior.

## Disciplina de dados

Os registros de execução das seis frentes (1.688 operações) foram examinados por programa:

- nenhum acesso ao conjunto de referência, à lockbox ou à partição `test` do esic-ner;
- duas tentativas de ler o texto da seleção oficial (conferir números de exemplo contra o corpus e
  inspecionar um documento) foram bloqueadas antes da execução;
- a frente de saúde comparou resultados da seleção oficial documento a documento (identificador e
  contagens por rótulo, sem o texto), além do permitido. No conjunto de referência, que nenhuma frente
  viu, o recall de saúde ficou em 0,872, contra 0,885 na seleção: sem indício de inflação relevante.

Medida adotada para o ciclo seguinte: a seleção oficial sai das cópias de trabalho e passa a ser
consultada só por `benchmark/treino/portao.py`, que devolve métricas agregadas e registra cada consulta.

## Integração

Os seis ramos foram integrados em `treino/integracao`; os conflitos (perfis com as categorias novas
`ECONOMICO` e `INSTITUCIONAL`, documentação) foram resolvidos preservando as duas contribuições. O
sistema integrado passou na suíte inteira, no ruff, no sintético (0,9963) e no nacional (1,0 e 0,9996,
preservação 1,0). Tempo por documento, medido na mesma sessão com execuções alternadas: 1,13 vez o do
ciclo 1 no esic-ner e 1,15 vez nos documentos oficiais.

## Classificador treinado no sistema integrado

A ablação por rótulo (`ablacao_integrada.json`, decisão em `decisao_classificador.json`) manteve
DADO_SAUDE (0,8) e NOME_PESSOA (0,98): sem o classificador, os documentos oficiais com vazamento
passariam de 65,8% para 76,3% na seleção. O limiar contextual de saúde reprovou no portão do esic-ner.

DADO_SENSIVEL não alterou nenhuma métrica das seleções e chegou a ser desativado. A medição no conjunto
de referência mostrou a perda de 2 das 27 entidades de dados sensíveis, o que revelou a falha do
critério, não dos dados: a seleção oficial tem só 9 entidades desse rótulo, e a ausência de efeito ali
não tem poder estatístico. O critério passou a ser o mesmo que desativou o rótulo de
quase-identificadores no ciclo 1: um rótulo de proteção só é desativado quando causa dano medido. Por
esse critério DADO_SENSIVEL continua ativo. Como a revisão foi motivada pela medição no conjunto de
referência, o resultado desse rótulo no conjunto de referência deixa de ser uma estimativa
inteiramente independente; a lockbox do esic-ner continua intacta.
