# 0007. Propagação de valores tarjados no documento

- Estado: Aceito
- Data: 2026-11-15

## Contexto

Reconhecedores identificam muitos dados somente onde há contexto: o CPF após a palavra "CPF", o nome
após "Requerente:" ou "meu nome é". O mesmo valor costuma reaparecer sem contexto — na assinatura, no
rodapé, em outra célula da planilha, em outra página. Se apenas a ocorrência com contexto for tarjada,
a outra expõe o dado e anula a tarja.

Em arquivos, o texto é analisado em partes (páginas, parágrafos, células), o que agrava o problema: a
parte com contexto e a parte sem contexto são analisadas separadamente.

## Decisão

Depois da decisão por perfil, `Anonimizador._propagar` procura as demais ocorrências dos valores
tarjados (`propagacao.py`) e as tarja com o motivo "Mesmo dado já tarjado em outro ponto do
documento":

- são propagados valores das categorias identificadoras com pelo menos quatro letras e dígitos;
- a busca usa uma representação compacta (apenas letras e dígitos, sem acentos, em minúsculas), de modo
  que `529.982.247-25` e `52998224725`, ou `Maria  Souza` e `MARIA SOUZA`, sejam o mesmo valor; cada
  ocorrência precisa começar e terminar em limite de palavra no original;
- partes de nomes (quatro letras ou mais, iniciadas por maiúscula, que não sejam conectores, palavras
  comuns ou prenomes ambíguos) são propagadas isoladamente: "Sra. Fagundes" após "Ana Beatriz
  Fagundes";
- não são propagadas ocorrências já tarjadas, protegidas pela lista de permissão, mantidas por decisão
  explícita, ou contidas em nomes de lugares e organizações não tarjados;
- nomes de pessoa não são propagados para dentro de nomes de lugares, instituições e normas
  ("São Paulo", "Rua Paulo Freire", "Lei Maria da Penha"), pela mesma regra usada no reconhecimento de
  nomes (`nomes.contexto_nao_pessoal`).

Com `mesmo_documento=True`, a propagação abrange todas as partes do lote. Todos os formatos de arquivo
usam esse modo. Sem ele, a propagação ocorre dentro de cada texto.

A verificação final aplica as mesmas regras de proteção, para que uma ocorrência preservada de
propósito não seja acusada como vazamento ([ADR 0006](0006-verificacao-final-e-falha-fechada.md)).

## Consequências

- Um dado identificado em qualquer parte do documento é tarjado em todas.
- Palavras comuns que coincidem com valores tarjados podem ser tarjadas (por exemplo, um sobrenome que
  também é substantivo, quando o valor tarjado é apenas esse sobrenome). As partes isoladas de nomes só
  são propagadas quando iniciadas por maiúscula, o que reduz esses casos.
- O custo da busca é linear no tamanho do documento.

## Alternativas consideradas

- **Analisar o documento inteiro como um único texto.** Melhora o contexto, mas não resolve
  ocorrências distantes do contexto e dificulta o mapeamento de posições em formatos estruturados.
- **Propagar apenas valores completos.** Não cobre referências parciais a nomes.
- **Comparação exata, sem representação compacta.** Não cobre variações de pontuação e espaçamento.
