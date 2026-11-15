# 0004. Perfis de decisão LGPD × LAI

- Estado: Aceito
- Data: 2026-11-15

## Contexto

A Lei de Acesso à Informação (Lei nº 12.527/2011) estabelece a publicidade como regra e o sigilo como
exceção; informações pessoais relativas à intimidade, vida privada, honra e imagem têm acesso restrito
(art. 31). A LGPD (Lei nº 13.709/2018) define dados pessoais e dados pessoais sensíveis. A restrição de
acesso deve ser motivada (Enunciado CGU nº 4/2022).

Tarjar tudo o que se parece com dado sensível prejudica a transparência: "a política de saúde mental
prevê atendimento para depressão" não contém dado pessoal. Tarjar de menos expõe pessoas: "minha filha
tem autismo" contém dado de saúde de pessoa determinada. Usos diferentes (publicação de respostas,
bases de pesquisa, área de saúde) exigem políticas diferentes.

## Decisão

A política de decisão é separada da detecção e organizada em perfis (`perfis.py`). Cada perfil
associa a cada categoria de dado uma regra: `tarjar`, `alertar` (mantido e sinalizado para revisão),
`manter` ou `vinculado`.

- A regra `vinculado` tarja frases que descrevem a situação de alguém (camada contextual) e tarja
  termos sensíveis isolados (camada semântica) somente quando a frase se refere a uma pessoa
  determinada — marcador de primeira pessoa, possessivo, papel ("a requerente") ou identificador pessoal
  na mesma frase. Sem vínculo, o termo vira alerta.
- Quatro perfis são oferecidos: `lai` (padrão), `identificadores`, `saude` e `maxima`
  ([TIPOS_DE_DADOS.md](../TIPOS_DE_DADOS.md#perfis)).
- Nas categorias identificadoras, achados de confiança moderada são tarjados por precaução (falha
  fechada); nas demais, viram alerta.
- CNPJ, URLs e nomes de instituições são mantidos no perfil `lai`; localidades e quase-identificadores
  viram alerta.
- A opção `preservar_agentes_publicos` mantém nomes acompanhados de cargo público, por decisão
  explícita do usuário.
- Todo achado carrega a base legal da categoria e a justificativa, que alimentam o relatório e a nota
  de tarjamento.

## Consequências

- O mesmo motor de detecção atende políticas diferentes, e perfis personalizados podem ser criados com
  a classe `Perfil`.
- Alertas transferem à revisão humana as decisões que dependem de contexto jurídico.
- A regra de vínculo é heurística: frases longas ou construções incomuns podem ser classificadas de
  forma diferente da esperada; o resultado aparece como alerta para revisão quando não há vínculo.

## Alternativas consideradas

- **Tarjar toda detecção.** Equivale ao perfil `maxima`; adequado a poucos casos de uso.
- **Classificador treinado para decidir a tarja.** Exigiria conjunto rotulado com decisões jurídicas e
  seria menos explicável que regras com base legal.
- **Perfil único configurável apenas por listas.** Insuficiente para expressar a regra de vínculo.
