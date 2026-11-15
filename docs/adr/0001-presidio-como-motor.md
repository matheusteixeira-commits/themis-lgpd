# 0001. Microsoft Presidio como motor de análise e de substituição

- Estado: Aceito
- Data: 2026-11-15

## Contexto

O Themis precisa de um motor de detecção de dados pessoais com registro de reconhecedores,
integração com modelo de linguagem, reforço de confiança por palavras de contexto, remoção de
duplicatas e explicação das decisões, além de um mecanismo de substituição que aceite operadores
diferentes por tipo de dado.

O Microsoft Presidio (licença MIT) oferece esses componentes e é amplamente adotado, mas não possui
reconhecedores para documentos brasileiros. Na configuração para português, com os reconhecedores
genéricos que liga por padrão, o Presidio tarja 53,3% das entidades pessoais do conjunto esic-ner e
7,9% dos documentos pessoais ([BENCHMARKS.md](../BENCHMARKS.md)).

Um motor próprio exigiria reimplementar e sustentar funcionalidades já maduras no Presidio, sem
benefício para os usuários.

## Decisão

O Themis é construído sobre o Presidio:

- a detecção usa o `AnalyzerEngine`, com `SpacyNlpEngine` (modelo `pt_core_news_lg`),
  `RecognizerRegistry` em português e `LemmaContextAwareEnhancer`;
- os reconhecedores brasileiros são escritos como `EntityRecognizer` do Presidio (por meio do
  adaptador `ReconhecedorThemis`) e podem ser registrados em qualquer instalação do Presidio;
- reconhecedores predefinidos do Presidio são reaproveitados onde são adequados (telefone com a
  biblioteca phonenumbers, IP, cartão de crédito, IBAN, carteiras de criptomoeda), reconfigurados para
  os tipos do Themis;
- o `SpacyRecognizer` padrão é substituído por um reconhecedor que lê as mesmas entidades do
  `SpacyNlpEngine` e aplica filtros para nomes brasileiros;
- a substituição usa o `AnonymizerEngine`, com operadores `replace` e `custom`;
- o que é específico do Themis — normalização com mapa de posições, política de decisão por perfil,
  propagação, resolução de sobreposições, formatos de arquivo e verificação — fica em camadas próprias
  em volta do Presidio.

## Consequências

- O Themis herda a evolução do Presidio (novos reconhecedores, motores de linguagem, GLiNER) e pode
  incorporar reconhecedores do Presidio por `reconhecedores_extras`.
- Os reconhecedores brasileiros beneficiam também quem já usa o Presidio
  (`themis_lgpd.integracoes.presidio`).
- O projeto depende das versões 2.2.x do Presidio (`>=2.2.366,<2.3`) e, por consequência, de Python
  3.11 ou mais recente.
- Comportamentos do Presidio precisaram de adaptação: os reconhecedores ad hoc recebem apenas as
  entidades do registro, por isso o adaptador filtra pelas entidades que ele próprio declara; o reforço
  por contexto é desativado para resultados em que o reconhecedor do Themis já considerou o contexto.
- O resultado de cada etapa é comparável com o Presidio puro (`benchmark/comparar.py`).

## Alternativas consideradas

- **Motor próprio.** Descartado: duplicaria funcionalidades maduras, sem ganho de qualidade.
- **Modelos de linguagem ajustados (BERTimbau e similares) como motor principal.** Exigem GPU ou CPU
  elevada, não validam dígitos verificadores e são menos previsíveis para identificadores
  estruturados. Permanecem possíveis como reconhecedores adicionais (GLiNER, opcional).
- **Serviços de nuvem.** Incompatíveis com o requisito de processamento local
  ([ADR 0005](0005-operacao-offline.md)).
