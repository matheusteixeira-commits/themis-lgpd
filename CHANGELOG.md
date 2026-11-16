# Histórico de versões

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota
[versionamento semântico](https://semver.org/lang/pt-BR/).

## Não publicado

### Segurança — vazamentos fechados

- Metadados de imagens incorporadas (EXIF com GPS e autor, XMP, comentários, miniaturas e vídeo
  anexado ao fim de fotos de celular) removidos sem recompressão em DOCX, XLSX e nas imagens JPEG e
  JPEG 2000 de páginas de PDF sem tarja; a verificação final falha se algum metadado permanecer.
- QR codes localizados e decodificados em imagens, em imagens incorporadas e em páginas de PDF
  (inclusive desenhados como vetores, como em GRU e boletos): BR Code do PIX sempre tarjado; demais
  QR codes tarjados quando o conteúdo tem dado pessoal; QR codes não decodificáveis tarjados.
- Imagens rasterizadas dentro de DOCX e XLSX analisadas por OCR e tarjadas nos pixels, no mesmo lote
  do documento (um nome tarjado no texto é tarjado também na imagem).
- Texto de imagens vetoriais EMF e WMF (tabelas coladas do Excel) analisado e mascarado no próprio
  arquivo, inclusive registros EMF+; texto e atributos de SVG analisados.
- PDF: textos alternativos de conteúdo marcado (`/ActualText`, `/Alt`, `/E`) removidos e nomes de
  camadas neutralizados em páginas sem tarja; a verificação passa a ler o conteúdo bruto de todas as
  páginas e a reler por OCR e QR code as páginas cujas tarjas dependem dos pixels.
- DOCX: nomes internos de arquivos de mídia neutralizados; identificadores de sessão de edição
  (`rsid`, `paraId`, `docId`) removidos.
- HTML, XML, RTF e mensagens de e-mail deixam de ser tratados como texto simples (o conteúdo
  codificado escapava à análise): HTML, e-mail e RTF passam a ter tratamento próprio (ver *formatos
  usados pelos órgãos*); XML e imagens GIF, BMP e WebP são recusados com orientação.
- Detecção: "meu RG é o …", número do registro em conselhos com região ("CRN-3 88421"), registros
  profissionais em minúsculas, "sob o nº", e itens seguintes de enumerações ("as CDAs X e Y", "os CPFs
  X, Y e Z").
- Nomes em CAIXA ALTA deixam de ser cortados na primeira palavra fora das listas ("BENEDITA FERREIRA
  LINS" tinha "LINS" exposto): a palavra desconhecida integra o nome quando fica entre palavras de nome
  ou o encerra antes de pontuação, minúscula ou palavra gramatical, e nunca quando é verbo, cargo ou
  substantivo comum.
- RENAVAM com dígito verificador inválido ao lado da palavra-chave passa a ser tarjado: a palavra-chave
  exigida pela própria regra conta como contexto.
- PDF com rotação declarada (`/Rotate` 90, 180 ou 270): as tarjas eram desenhadas na página sem
  rotação, fora da posição do texto, que continuava legível na imagem gerada (a verificação textual não
  o via, pois a camada de texto era recriada sem ele). Texto, OCR, QR codes e tarjas passam a usar as
  coordenadas da página exibida, a página gerada sai na orientação de exibição e o texto de cabeça para
  baixo é lido na ordem correta; teste de regressão nas quatro rotações, com releitura por OCR.

### Adicionado — classificador treinado de dados de saúde

- Classificador de trechos (componente `spancat` do spaCy) treinado sobre a partição de ajuste do
  EliMC/esic-ner (`benchmark/treino/treinar_spancat.py`) e acoplado ao pipeline do `pt_core_news_lg`
  com o mesmo vocabulário e os mesmos vetores (artefato de 6,8 MB em `dados/modelos/sensivel`).
  Reconhece condições descritas com palavras próprias ("dores fortes no joelho", "falta de ar"), que
  continuam sujeitas à regra de vínculo do perfil. Desligável com `THEMIS_MODELO_SENSIVEL=0`.
- O rótulo de quase-identificadores do mesmo classificador fica desativado: na ablação do sistema
  integrado (`benchmark/treino/ciclo1/ablacao_integrada.json`) ele não acrescentou acertos às regras
  e sinalizava frases de expediente.

### Alterado — classificador retreinado com documentos oficiais

- O classificador de trechos passa a ser treinado também com a partição de ajuste do corpus de
  documentos oficiais fictícios (`benchmark/oficial`) e com textos-modelo em inglês sem nada anotado,
  e ganha os rótulos `DADO_SENSIVEL` (tipo inferido do vocabulário do trecho) e `NOME_PESSOA`; o de
  quase-identificadores continua desativado. Na seleção do corpus oficial, com as regras do ciclo
  anterior, o recall de dados de saúde passa de 0,128 para 0,280, o de nomes de 0,852 para 0,966 e o
  de dados sensíveis de 0 para 0,222, com a precisão das tarjas e a preservação de trechos públicos
  estáveis; no esic-ner, nenhum rótulo perde recall.
- Trechos que o classificador marcaria como saúde mas são só idade ou duração ("≥ 18 anos", "30 dias")
  são descartados.
- Nomes propostos pelo classificador que integram o nome de instituição, logradouro, norma, honraria ou
  município são descartados.
- `benchmark/treino/ablacao_spancat.py` avalia uma grade de épocas e limiares no sistema completo, nas
  duas seleções, verifica os portões e grava a configuração escolhida no artefato.
- Ablação no sistema integrado do ciclo 2 (`benchmark/treino/ciclo2/ablacao_integrada.json`): sem o
  classificador, os documentos oficiais com vazamento passariam de 65,8% para 76,3% na seleção. Um
  rótulo de proteção só é desativado quando causa dano medido; `DADO_SENSIVEL`, sem efeito mensurável
  nas seleções e sem dano, continua ativo.

### Alterado — detecção treinada em documentos oficiais

Três ciclos de melhoria orientados por medição (método em `docs/BENCHMARKS.md`, seção *Treinamento
das regras*). No conjunto de referência de 120 documentos oficiais fictícios, que nunca serviu ao
ajuste, o recall passa de 64,7% para 93,6%, a precisão das tarjas de 85,5% para 93,5%, a preservação de
trechos públicos de 88,9% para 96,5% e os documentos com algum vazamento de 93,3% para 50,0% (45
deixaram de vazar, nenhum passou a vazar). Na partição de teste do esic-ner, o recall passa de 94,6%
para 95,1% e a precisão da triagem de 0,948 para 0,963.

- A idade ligada a uma pessoa passa a ser tarjada (tipo `IDADE`), inclusive por extenso, em aposto e
  entre parênteses; a data de nascimento é reconhecida também por extenso, com mês em algarismos
  romanos, com o ano primeiro e em documentos de outros países.
- Valores recebidos ou devidos por pessoa natural — salário, benefício, renda, pensão, dívida,
  prejuízo — passam a ser tarjados (tipo `VALOR_PESSOAL`, categoria `ECONOMICO`; alerta no perfil
  `identificadores`). Valores de contratos, de órgãos e totais de programas continuam legíveis.
- Dados do próprio órgão e de empresas — telefone e e-mail de setor, endereço da sede, placa, RENAVAM
  e chassi da frota oficial, contato e endereço de fornecedor, nome de unidade em tabela — ficam
  legíveis e sinalizados para revisão (categoria `INSTITUCIONAL`; tarjados no perfil `maxima`). As
  regras mais amplas valem só em documento expedido pelo órgão, com timbre nas primeiras linhas.
- Saúde e dados sensíveis fora do registro clínico: linguagem leiga, fala transcrita, uso de
  substâncias, tratamento descrito pelo serviço (CAPS, fila de transplante), deficiência e gestação
  sem verbo de atribuição, violência classificada no caso e dados sensíveis em terceira pessoa ou por
  perífrase; enunciados normativos, estatísticas e nomes de órgãos com esses termos continuam
  legíveis.
- Tabelas, formulários e documentos digitalizados (`reconhecedores/tabelas.py`): cada coluna é
  tipificada pelo cabeçalho em tabelas separadas por barra, tabulação, ponto e vírgula ou espaços
  alinhados, em grade e em formulário; a normalização reúne palavras hifenizadas em caixa alta,
  números partidos, letras em quadrícula e rótulos colados ao valor, e corrige trocas comuns de OCR
  em nomes e rótulos.
- Nomes em formas atípicas: invertidos ("SOBRENOME, prenome"), com partículas estrangeiras, do Leste
  Asiático com o sobrenome à frente, apelidos, iniciais de crianças e testemunhas, nome de guerra após
  posto e nome em célula de tabela. Nome de pessoa dentro de nome de embarcação, programa, honraria,
  entidade, empresa, logradouro ou município fica legível.
- Documentos de estrangeiros (RNE, RNM, cédulas de identidade e passaportes de outros países, codice
  fiscale e identidade chinesa com dígito de controle), assentos de registro civil por livro e folha,
  carteiras sem formato nacional (CIPTEA, RGP) e números de parecer, ficha e prontuário de sistemas
  setoriais.
- Endereços de aldeias, povoados, comunidades ribeirinhas, acampamentos, ocupações, assentamentos e
  abrigos, com a referência descritiva ("casa de taipa depois da capela"), ponto de pernoite de
  pessoa em situação de rua, endereço estrangeiro, linha colonial com quilômetro e coordenadas.
- Quase-identificadores por função, lugar, turno ou cargo comunitário, e "único" com qualificador de
  língua, origem ou família.
- Registros em conselho e documentos de identidade: o número continua tarjado; a sigla do conselho, o
  órgão emissor e a UF ficam legíveis ("CRM-PE [REGISTRO PROFISSIONAL]").
- Menos tarja indevida em documentos públicos: processos, autos e laudos sobre coletividade ou pessoa
  jurídica, numeração de itens e de classificação com forma de IP, protocolos do diário oficial e
  códigos verificadores do SEI, contas bancárias de pessoa jurídica, notas de empenho e ordens
  bancárias.

### Adicionado — avaliação com separação de dados

- Conjunto de referência independente (`benchmark/ouro`): 120 documentos oficiais fictícios de todas
  as regiões, com anotação dupla cega, adjudicação e congelamento por SHA-256, e avaliador
  (`benchmark/avaliar_ouro.py`) de recall, precisão real das tarjas e preservação de trechos
  públicos, com intervalos de confiança.
- Corpus de desenvolvimento de 200 documentos oficiais fictícios (`benchmark/oficial`) e 120
  documentos adversariais (`benchmark/adversarial`), anotados pelas mesmas diretrizes.
- Partições de ajuste, seleção e *lockbox*: `--erros` só nas partições de ajuste; a partição de teste
  do esic-ner exige `--lockbox MOTIVO` e registra cada uso, também em `benchmark/comparar.py`;
  consulta às seleções por métricas agregadas (`benchmark/treino/portao.py`).
- Comparação pareada de duas execuções (`benchmark/treino/comparar_execucoes.py`): *bootstrap*
  pareado e teste de McNemar.
- Trava de regressão no CI: o conjunto de referência precisa manter recall ≥ 93%, precisão das tarjas
  ≥ 92,5% e preservação ≥ 95,5%.

### Adicionado — cobertura nacional

- Endereços de todo o país: abreviações (Av., Trav., Pça., Lgo., Rod., Estr.), número com milhar,
  ruas numeradas ou com letra ("Rua 15", "Rua B-15, Quadra 30"), endereço sem número após expressão
  de residência, propriedades rurais (sítio, fazenda, chácara, granja, estância), localidades coletivas
  com residência (povoado, assentamento, aldeia, comunidade, ramal, loteamento), linha e lote
  (Rondônia), rodovias federais e estaduais das 27 UFs com quilômetro, e bairro antes de "Cidade/UF".
- Municípios: os 5.570 municípios do IBGE (`dados/municipios.txt`, gerado por
  `scripts/gerar_municipios.py`) reconhecidos como "Cidade/UF" (com conferência da UF), "município de
  Cidade" e após expressão de residência, inclusive em minúsculas ("moro em campinas"). Municípios
  homônimos de palavras comuns ou de estados só são sinalizados com contexto.
- Identificadores: número de benefício do INSS, chassi (VIN), recibo do CAR, prontuário, DNV, AIH e
  cartão de vacina, RA e matrícula escolar, inscrição imobiliária (IPTU), Inscrição Estadual abreviada,
  MASP, ID e registro funcional, RNTRC, CADASTUR, MTB, DRT, CRB, termo de certidão, RG com a palavra-chave
  depois do número, RENAVAM com a grafia "renavan".
- Processos: NUP de 21 dígitos, SEI de Minas Gerais, Pernambuco, Bahia e Rio de Janeiro, PROA (RS),
  eProtocolo (PR), SGPe (SC) e "Proc. Adm.".
- Saúde: seleção de medicamentos da DCB e da Portaria SVS/MS nº 344/1998 (`dados/medicamentos.txt`),
  com sal e dose ("cloridrato de metformina 500mg") e classes pelo sufixo (-mabe, -tinibe, -prazol,
  -statina…); uso de medicamento ("faço uso de fluoxetina") na camada contextual; doenças, condições,
  procedimentos, exames e especialidades ausentes; códigos da CID-11, "C.I.D." e listas de códigos.
- Prenomes mais frequentes por sexo, década e UF no Censo 2010 (`dados/prenomes_ibge.txt`, gerado
  por `scripts/gerar_prenomes_ibge.py` a partir da API de Nomes do IBGE).
- Benchmark nacional (`benchmark/nacional.py`): 27 UFs, conjuntos de desenvolvimento e de validação e
  textos de interesse público que não podem ser tarjados; trava no CI. Recall na validação: 64,5% na
  versão 1.0.0, 100% agora; textos públicos sem tarja: 98,1% → 100%.
- `benchmark/esic_ner.py` separa as entidades não tarjadas em sinalizadas para revisão e não
  detectadas; partição de treino para desenvolvimento (`--split train`).

### Adicionado — operação em escala e por órgão

- Lotes na CLI: pastas (`-R` para subpastas), árvore de pastas preservada na saída (arquivos de mesmo
  nome em pastas diferentes não colidem mais), processamento paralelo (`-j N`), cofre por documento e
  código de saída igual à maior gravidade do lote (um erro interno não é mais rebaixado por um arquivo
  recusado depois).
- Manifesto de cadeia de custódia (`--manifesto`, JSON Lines gravado arquivo a arquivo): SHA-256 e
  tamanho de entrada e saída, formato, perfil, modo, versão, identificador da configuração, tarjas por
  tipo, alertas, avisos, situação e duração, sem nenhum conteúdo; retomada de lotes interrompidos
  (`--retomar`).
- Relatório consolidado de lote identifica o arquivo de origem de cada item.
- Configuração por órgão (`themis.toml`, `--config` ou `THEMIS_CONFIG`) para CLI, API e interface:
  perfil e modo padrão, listas, cargos, tipos e reconhecedores próprios (expressão regular, contexto e
  validador de dígito, registrados no Presidio) e perfis derivados; erros indicam seção e campo e
  impedem a execução. Exemplo comentado em `exemplos/orgao.toml`.
- Perfis `ouvidoria` (identidade do manifestante, Lei nº 13.460/2017, art. 10, § 7º) e `educacao`
  (estudantes, LGPD art. 14 e ECA art. 17).
- Agentes públicos: lista de cargos ampliada (reitor, defensor público, promotor de justiça, delegado,
  pregoeiro, fiscal e gestor de contrato, ordenador de despesa…) e decisão aplicada a todas as
  ocorrências do mesmo nome no documento.
- API: rota de arquivos com listas, agentes públicos, colunas integrais, OCR e resposta em JSON com o
  relatório de tarjamento; tarefas assíncronas (`POST /v1/tarefas`, consulta, download e exclusão),
  com resultado só em memória, visível apenas para a chave que o criou e apagado após o download ou a
  expiração; processos de análise em paralelo (`themis api --processos N`, `THEMIS_PROCESSOS`);
  especificação OpenAPI versionada em `docs/openapi.json`, com teste de sincronia.
- `benchmark/desempenho.py`: tempo de análise de textos longos e de anonimização de PDFs, e tamanho
  dos PDFs gerados.

### Adicionado — distribuição e confiança

- Versão em fonte única (`src/themis_lgpd/_versao.py`, lida pelo `pyproject.toml`); metadados
  completos (endereços de documentação e histórico, sistemas operacionais) e README com links
  absolutos, para exibição correta no PyPI; `twine check --strict` no CI.
- Workflow de publicação por tag (`release.yml`): roda e sdist com SBOM CycloneDX e atestado de
  proveniência SLSA, PyPI por publicação confiável, imagem no GHCR com SBOM SPDX, assinatura cosign
  sem chave e atestado de proveniência; ensaio completo, sem publicar, em pull requests.
  Roteiro em `docs/PUBLICACAO.md`.
- CodeQL (`security-extended`) e OpenSSF Scorecard; testes também em Windows e macOS e com
  exatamente as versões de `requirements/producao.txt`.
- `themis saude`: verificação de saúde da API e da interface, usada pelo HEALTHCHECK da imagem (antes,
  fixo na porta da interface); serviço de API na composição Docker (perfil `api`); imagem sem o
  RapidOCR (OCR pelo Tesseract). O CI sobe o contêiner no modo API, espera o estado `healthy` e
  anonimiza um texto por ele.
- Pacote portátil para Windows (`scripts/empacotar_windows.py`): Python incorporável oficial,
  dependências, modelo e Themis numa pasta que funciona sem instalação e sem administrador, com
  `Iniciar Themis.bat` (interface) e `themis.bat` (linha de comando); montado e verificado no CI sem Python no
  `PATH`, anonimizando os exemplos fictícios de `exemplos/`.

### Adicionado — PDF acessível, pesquisável e de arquivamento

- Camada de texto das páginas tarjadas com fonte Unicode incorporada (antes, caracteres fora do
  Windows-1252, como "≥", viravam "?") e o rótulo de cada tarja ("[CPF]") como texto alternativo
  (`/ActualText`), lido por leitores de tela no lugar do conteúdo removido.
- Páginas digitalizadas sem tarja recebem a camada de texto do OCR já realizado, sobreposta à imagem
  original: o documento inteiro fica pesquisável.
- Idioma declarado (`/Lang pt-BR`); marcadores (sumário) recriados com os títulos anonimizados e links
  para a web mantidos quando o endereço não contém dado pessoal (antes, ambos eram removidos).
- `--pdfa` (CLI), `pdfa` (API e biblioteca): PDF/A-2b, com todas as páginas em imagem e camada de
  texto, perfil sRGB, metadados apenas com a identificação PDF/A e versão 1.7; validado no CI pelo
  veraPDF com PDFs de fontes não incorporadas, página digitalizada, cor CMYK e o exemplo fictício.

### Adicionado — formatos usados pelos órgãos

- ODT e ODS (formato aberto do e-PING): texto com conteúdo misto, cabeçalhos e rodapés, células,
  fórmulas e valores (a célula tarjada perde também o valor numérico e a fórmula), objetos incorporados
  e imagens; alterações controladas aceitas; comentários, metadados, miniatura, configurações e macros
  removidos; `mimetype` gravado primeiro e sem compressão.
- HTML (documentos do SEI): entidades decodificadas, texto em fluxo único, atributos com texto,
  endereços de links e imagens em `data:` analisados; scripts, eventos, quadros e metadados removidos.
- Mensagens de e-mail (EML): assunto, correspondentes, corpo em texto e HTML (base64 e
  *quoted-printable*) e anexos, cada um pelo próprio formato e com o nome analisado; endereços trocados
  por endereço reservado; rotas de entrega, identificadores e DKIM descartados.
- ZIP de processo: cada arquivo pelo próprio formato, nomes de pastas e arquivos analisados (com os
  valores tarjados nos documentos propagados para eles e nomes em página de código 850 decodificados),
  arquivos não suportados removidos e manifesto `manifesto_anonimizacao.json` com SHA-256 de entrada e
  de saída, situação e contagem por tipo; proteção contra *zip slip*, arquivos de sistema e ligações
  simbólicas removidos; até três níveis de ZIP aninhado.
- TIFF de uma ou várias páginas (digitalizadoras): OCR de todas as páginas no mesmo lote e TIFF novo
  com as mesmas páginas, resolução e profundidade de cor (1 bit com CCITT G4), sem etiquetas de
  metadados.
- PPTX (também `.pptm`, `.potx`, `.ppsx`): slides, inclusive ocultos, anotações do orador, mestres,
  gráficos, textos alternativos e imagens analisados; comentários e autores (inclusive os modernos),
  histórico de coautoria, marcas de suplementos, áudios e vídeos e macros removidos.
- DOC, XLS, PPT e RTF convertidos pelo LibreOffice, quando instalado, para DOCX, XLSX ou PPTX e
  anonimizados como tal (perfil temporário, sem interface, tempo máximo); `.doc` que é na verdade RTF
  ou HTML identificado pelo conteúdo; sem o LibreOffice, recusa com orientação. Testado no CI com o
  LibreOffice instalado.
- A CLI em lote, a interface e a API aceitam todos os formatos novos.

### Adicionado — interface de revisão

- Vários arquivos por envio (até 50; 10 na demonstração): processados como um ZIP, com download único,
  manifesto e tabela da situação de cada arquivo.
- Pré-visualização de todas as páginas de PDFs, imagens e TIFF, uma por vez.
- Tarja manual por região (assinaturas manuscritas, fotos, carimbos), arrastando o mouse sobre a
  página (`streamlit-image-coordinates`, MIT) ou informando as coordenadas em porcentagem, com as
  regiões contornadas antes de aplicar. O núcleo (`formatos/regioes.py`) também está na CLI
  (`--regiao 1:10,70,45,85`), na API (campo `regiao`) e na biblioteca (`regioes=`); a verificação
  final confirma que nenhuma palavra do PDF gerado está dentro de uma região.
- Marcações acessíveis: a ação de cada trecho tem símbolo e sublinhado próprios, além da cor, e a ação,
  o tipo e a base legal são lidos pelos leitores de tela junto com o trecho; legenda em texto.

### Desempenho

- Análise de textos longos quase linear: 100 mil caracteres em 8,0 s (1.0.0: 11,3 s). O reforço de
  confiança por contexto do Presidio localiza o token de cada achado por busca binária, e o filtro de
  nomes lê o texto do documento uma vez, em vez de remontá-lo a cada entidade. As regras de contexto e
  o classificador acrescentados no treinamento quase dobraram o tempo de análise em relação à versão
  anterior a ele (4,7 s).
- PDF: páginas tarjadas gravadas em escala de cinza quando não têm cor e em JPEG quando fotográficas,
  com composição em paralelo — 0,36 s por página (1.0.0: 0,47 s) e arquivos 31% menores.

### Corrigido

- A verificação final recusava o arquivo inteiro quando um termo de saúde, dado sensível ou valor de
  pessoa natural tarjado num trecho aparecia, sem relação com a pessoa, em outro (o pedido do
  requerente e uma nota técnica sobre o programa, no mesmo PDF). Esses valores não se propagam; a
  ocorrência deixada visível pela análise passa a ser reconhecida pelo contexto, e uma tarja que não
  chegou ao arquivo continua sendo acusada.
- Sobrenome com palavra de nome de instituição ("Augusto Casa Grande", "Rafaela da Ponte") deixava o
  nome inteiro legível: depois de um prenome conhecido, a palavra só indica instituição quando seguida
  de preposição ("Casa de Cultura").
- A verificação final de PDFs, DOCX e XLSX deixava de entregar documentos válidos quando um sobrenome
  tarjado ("Rocha") aparecia como palavra comum em minúsculas ("rocha") em outro trecho; ela passa a
  seguir a regra da propagação.
- Relatórios CSV e XLSX exibiam um apóstrofo nas células vazias.
- Arquivo com extensão de formato binário e conteúdo de texto (um `.pdf` renomeado) era processado
  como texto e gerava saída com outra extensão; passa a ser recusado.
- Sigla de documento antes do número ("Pedido de acesso - CPF 529.982.247-25") era capturada como
  prefixo de protocolo e tarjada como `[PROTOCOLO] [CPF]`; siglas de documentos deixam de compor
  números de protocolo.
- `themis analisar` e `themis reverter` exibiam o rastreamento do Python para arquivo inexistente,
  texto fora de UTF-8 ou senha incorreta; passam a exibir mensagem e a sair com código 1.

### Alterado

- OCR pelo pacote `rapidocr` (modelo multilíngue PP-OCRv6, com acentuação do português, incluído no
  pacote e sem acesso à rede) no lugar de `rapidocr-onnxruntime`, que não tem versão para Python 3.13.
  Palavras coladas pelo OCR são separadas antes da análise.
- Imagens: orientação EXIF aplicada antes do OCR e PNG gravado sem perfil de cor.
- `Anonimizador.analisar_lote` e `anonimizar_lote` aceitam valores tarjados em etapa anterior do mesmo
  arquivo (`externos`), entidades definidas para parte dos textos (`definidas`) e continuidade da
  numeração de pseudônimos (`continuar`).
- Menos tarja indevida em texto público: municípios com nome de pessoa após designação institucional
  ("Prefeitura de Dom Eliseu", "Secretaria de Obras de Dom Expedito Lopes"), homenageados com título em
  nomes de rua ("Rua Professora Maria Clara"), órgãos fazendários ("Secretaria de Estado de Fazenda do
  Distrito Federal") e naturalidade ("natural do Paraná") deixam de ser tarjados.
- Um alerta só é descartado quando contido em outro: a frase de um quase-identificador continua
  sinalizada inteira mesmo que contenha um município com alerta próprio.

## 1.0.0 — 2026-11-15

Primeira versão pública, reescrita a partir da solução apresentada no 1º Hackathon em Controle Social
(Participa DF).

### Adicionado

**Motor**

- Construção sobre o Microsoft Presidio 2.2.366: detecção pelo `AnalyzerEngine` (registro de
  reconhecedores, `SpacyNlpEngine`, `LemmaContextAwareEnhancer`, explicação das decisões) e substituição
  pelo `AnonymizerEngine`. Reconhecedores brasileiros escritos como `EntityRecognizer` do Presidio e
  reutilizáveis em qualquer instalação dele; reconhecedores predefinidos do Presidio para telefone
  (região BR), IP, cartão, IBAN e criptomoedas.
- Documentos com dígito verificador: CPF, CNPJ (inclusive alfanumérico), PIS/NIS, título de eleitor,
  Cartão SUS, CNH, processo judicial (padrão CNJ) e cartão de pagamento. Também RG, passaporte, CTPS,
  certidão, matrícula, registros profissionais, data de nascimento, conta bancária, PIX, placa,
  RENAVAM, processos administrativos e protocolos.
- Nomes de pessoas por modelo de linguagem, lista de nomes brasileiros e gatilhos de contexto, em
  minúsculas e caixa alta.
- Dados sensíveis, situações de violência e dados de crianças, com tarja condicionada ao vínculo com
  pessoa determinada.
- Normalização com mapa de posições: caracteres invisíveis, homóglifos, hifenização de fim de linha e
  ruído de OCR em números; o documento só muda nos trechos tarjados.
- Perfis `lai`, `identificadores`, `saude` e `maxima`; modos `etiqueta`, `tarja`, `mascara`, `pseudonimo`
  e `hmac`; cofre cifrado para reverter a pseudonimização; listas de permissão e de bloqueio; opção para
  manter nomes de agentes públicos no exercício da função.
- Falha fechada para identificadores: achados de confiança moderada em categorias identificadoras são
  tarjados por precaução, em vez de sinalizados.
- Propagação no documento: cada valor tarjado é procurado em todas as partes do documento (páginas,
  parágrafos, células), inclusive com pontuação diferente e por partes de nomes ("Sra. Fagundes"), e
  tarjado em todas as ocorrências. Nomes de pessoa não são propagados para dentro de nomes de lugares
  e instituições ("São Paulo", "Rua Paulo Freire").
- Prioridade por tipo e expansão até o limite do token nas sobreposições, sem fragmentos visíveis.

**Arquivos**

- PDF com tarja real: páginas com tarja rasterizadas com camada de texto invisível; reescrita e
  saneamento (metadados do documento e de todos os objetos, anotações, anexos, formulários, JavaScript,
  marcadores, estrutura de tags, dados de validação de assinatura).
- PDF: incorporação de campos de formulário e anotações visíveis antes da extração, para que sejam
  analisados; leitura de texto girado (90° e −90°) no sentido correto, com tarja contínua por coluna;
  OCR em páginas com fontes sem mapeamento Unicode.
- DOCX tratado no nível do pacote: análise de todas as partes XML (corpo, tabelas, cabeçalhos, rodapés,
  notas, caixas de texto, equações, gráficos, SmartArt), de instruções de campo, de atributos de texto
  livre e de destinos de hiperlinks; texto dividido entre trechos de formatação analisado como fluxo
  contínuo; análise de qualquer texto em elementos não previstos; remoção de alterações controladas,
  comentários, propriedades, miniatura, dados XML personalizados, variáveis, modelo anexado, mala
  direta, marcas inteligentes, assinaturas, objetos incorporados, blocos importados, macros, referências
  a arquivos locais e partes órfãs; recusa de DTD, entradas duplicadas ou criptografadas e formato OOXML
  Strict.
- XLSX além das células: primeira linha sempre analisada, literais em fórmulas, nomes de abas (com
  atualização de referências), cabeçalhos de impressão, validações de dados, formatação condicional,
  filtros, nomes definidos, gráficos e desenhos; caches de gráficos, comentários, hiperlinks, tabelas
  dinâmicas, vínculos externos e macros removidos. Valores das colunas tarjadas por inteiro são
  propagados para as demais células, e a numeração de pseudônimos é única em toda a planilha.
- PDF: páginas sem camada de texto e com texto convertido em contornos vetoriais passam por OCR.
- CSV com a primeira linha analisada; TXT em UTF-8 ou Windows-1252; imagens PNG e JPEG por OCR,
  regravadas em PNG sem metadados.
- OCR local por Tesseract (imagem enviada pela entrada padrão, sem arquivo temporário) ou RapidOCR.
- Verificação final independente em todos os formatos: o arquivo gerado é relido (no PDF, por dois
  extratores e pela inspeção de todos os objetos) e comparado com os valores tarjados, com limite de
  palavra, tolerância a separadores e desconsideração de trechos mantidos intencionalmente. Se algum
  valor continuar legível, a operação falha com `VazamentoDetectado` e nenhum arquivo é entregue.
- `FalhaOCR`: arquivos que exigem OCR são recusados quando nenhum mecanismo está disponível ou quando
  o OCR falha, em vez de entregues sem análise; somente com o OCR desativado explicitamente o PDF é
  gerado, com aviso das páginas não analisadas.
- Avisos ao usuário sobre conteúdo removido, convertido ou não analisado, sem repetir conteúdo do
  documento.

**Interfaces**

- Interface web com revisão humana, realce dos achados e relatórios.
- Linha de comando (`themis`) com processamento em lote, relatório consolidado e cofre de reversão;
  a entrada padrão também passa pela verificação final; erros inesperados exibem apenas o tipo e saem
  com código 2.
- API HTTP com limites de corpo, taxa, concorrência e tempo, chave de API opcional e respostas sem eco
  do conteúdo, todas no formato `{"erro": ...}`; registros de exceção do servidor reduzidos ao tipo do
  erro.
- Relatório de tarjamento (JSON, CSV, XLSX) e nota de tarjamento com base legal, sem os valores
  originais; relatório interno com valores somente sob pedido explícito.

**Qualidade e distribuição**

- Benchmarks reproduzíveis: esic-ner (EliMC, CC BY 4.0), conjunto sintético com todos os
  identificadores e comparação com o Presidio puro (`benchmark/comparar.py`).
- Reconhecedor GLiNER opcional, pelo `GLiNERRecognizer` do Presidio.
- Imagem Docker sem root, com modelo de linguagem e Tesseract, para uso sem internet; composição para
  demonstração pública com Caddy.
- Integração contínua com testes em Python 3.11 a 3.13, ruff, bandit, pip-audit, gitleaks, Trivy e trava
  de regressão no benchmark sintético.
- Documentação: instalação, guia de uso, API, configuração, arquitetura, segurança e privacidade,
  tipos de dados, benchmarks e registros de decisão de arquitetura.

### Corrigido em relação à versão do hackathon

- Nomes de pessoas não eram anonimizados; PIS, CNH, título de eleitor, Cartão SUS, placa e processos
  não eram detectados; o mascaramento parcial deixava dígitos visíveis.
- Relatórios exportavam o texto original e os valores detectados; o processamento em lote truncava o
  texto.
- Injeção de HTML na interface; telemetria do Streamlit ativada; proteção XSRF desativada; CORS aberto;
  credenciais padrão; contêiner executado como root; dependências com vulnerabilidades conhecidas.

### Limitações conhecidas

- No conjunto sintético, 99,6% dos identificadores são tarjados; todos os casos não tarjados estão na
  variante com ruído de OCR simulado, quando o primeiro caractere de um número ou de uma placa é
  substituído por letra. Ver [docs/BENCHMARKS.md](docs/BENCHMARKS.md).
- Imagens dentro de DOCX e XLSX, manuscritos, assinaturas e rostos não são analisados.
