# Themis LGPD

Anonimização de documentos públicos brasileiros, construída sobre o
[Microsoft Presidio](https://github.com/data-privacy-stack/presidio), com processamento inteiramente
local.

[![CI](https://github.com/matheusteixeira-commits/themis-lgpd/actions/workflows/ci.yml/badge.svg)](https://github.com/matheusteixeira-commits/themis-lgpd/actions/workflows/ci.yml)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)

O Themis LGPD identifica e remove dados pessoais de textos, PDFs, documentos Word, planilhas e
imagens — nomes, CPF, CNPJ (inclusive o alfanumérico), RG, CNH, PIS, título de eleitor, Cartão SUS,
benefício do INSS, RENAVAM, chassi, CAR, telefones, e-mails, endereços de todo o país (urbanos, rurais,
rodovias das 27 UFs e o endereçamento do Distrito Federal), municípios, dados bancários, processos dos
sistemas federais e estaduais e dados pessoais sensíveis — e gera o relatório de tarjamento com a base
legal de cada tarja, para acompanhar a resposta a pedidos de acesso à informação.

O Presidio fornece o motor de análise (registro de reconhecedores, motor spaCy, reforço de confiança
por contexto, explicação das decisões) e o motor de substituição. O Themis acrescenta reconhecedores
para dados brasileiros, escritos como reconhecedores do Presidio; normalização do texto com mapa de
posições; política de decisão que equilibra LGPD e LAI; remoção efetiva do conteúdo tarjado em
arquivos; e verificação independente de cada arquivo gerado.

> **Ferramenta de apoio.** O Themis reduz o trabalho e o risco do tarjamento, mas não substitui a
> revisão humana antes da publicação.

## Recursos

- **Documentos brasileiros com dígito verificador:** CPF, CNPJ alfanumérico, PIS/NIS, título de
  eleitor, Cartão SUS, CNH, processo judicial (padrão CNJ) e cartões de pagamento; além de RG,
  passaporte, CTPS, matrícula, registros profissionais, data de nascimento, contas, PIX, placas,
  RENAVAM, processos administrativos e protocolos.
- **Nomes de pessoas** por três mecanismos complementares: modelo de linguagem `pt_core_news_lg`,
  lista de nomes brasileiros (funciona em minúsculas e caixa alta) e gatilhos de contexto.
- **Dados sensíveis** (saúde, religião, opinião política, filiação sindical, vida sexual, dados
  genéticos, origem racial), situações de violência e dados de crianças, com tarja condicionada ao
  vínculo com pessoa determinada.
- **Robustez:** caracteres invisíveis, homóglifos, hifenização, números quebrados entre linhas e ruído
  de OCR.
- **Falha fechada:** identificadores com confiança moderada são tarjados; arquivos que não passam na
  verificação final não são entregues.
- **Propagação:** um dado identificado em qualquer ponto do documento é tarjado em todas as
  ocorrências.
- **Arquivos:** PDF (com tarja real), DOCX, XLSX, PPTX, ODT, ODS, HTML (documentos do SEI), e-mail
  (EML, com anexos), CSV, TXT, PNG, JPEG e TIFF multipágina, com OCR local; ZIP de processo (cada
  arquivo pelo seu formato, nomes analisados, manifesto); DOC, XLS, PPT e RTF com o LibreOffice; PDF gerado
  pesquisável e acessível (rótulos das tarjas para leitores de tela, idioma declarado) e, opcionalmente,
  em PDF/A-2b para arquivamento, validado pelo veraPDF.
- **Revisão humana** na interface web; relatório e nota de tarjamento com base legal.
- **Quatro interfaces:** interface web, linha de comando, biblioteca Python e API HTTP (com tarefas
  assíncronas para documentos longos e especificação OpenAPI versionada).
- **Lotes com cadeia de custódia:** pastas inteiras, em paralelo, com a árvore preservada, manifesto
  com SHA-256 de entrada e saída de cada arquivo e retomada de lotes interrompidos.
- **Configuração por órgão:** um `themis.toml` com perfis, listas, cargos e reconhecedores próprios,
  aplicado igualmente pela linha de comando, pela API e pela interface.
- **Operação sem internet:** nenhuma telemetria, nenhum serviço externo, nenhum download automático.

## Início rápido

```bash
pip install "themis-lgpd[completo]"
python -m spacy download pt_core_news_lg
```

Requer Python 3.11 ou mais recente. Sem Python e sem permissão de administrador, use o
[pacote portátil para Windows](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/INSTALACAO.md#pacote-portátil-para-windows).
Para PDFs digitalizados e imagens, instale também o Tesseract com o idioma português ou use o
RapidOCR incluído no extra `completo`. Detalhes em
[docs/INSTALACAO.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/INSTALACAO.md).

**Interface web**, com revisão humana:

```bash
themis interface                                # http://127.0.0.1:8501
```

**Linha de comando:**

```bash
themis anonimizar resposta.pdf                  # gera resposta_anonimizado.pdf
themis anonimizar *.docx -o saida/ -r relatorio.xlsx
themis anonimizar planilha.xlsx --coluna-integral "Nome do servidor"
themis anonimizar processos/ -R -o publicacao/ --manifesto custodia.jsonl -j 4 --config orgao.toml
echo "Eu, Maria Souza, CPF 529.982.247-25" | themis anonimizar -
```

**Python:**

```python
from themis_lgpd import Anonimizador

anon = Anonimizador(perfil="lai")
r = anon.anonimizar("Eu, Maria Aparecida Souza, CPF 529.982.247-25, moro na QNM 12 Conjunto B Casa 4.")
print(r.texto)   # Eu, [NOME], CPF [CPF], moro na [ENDEREÇO].
```

```python
from themis_lgpd.formatos import anonimizar_arquivo

resultado = anonimizar_arquivo(open("despacho.pdf", "rb").read(), "despacho.pdf", anon)
open(resultado.nome, "wb").write(resultado.dados)
```

**API HTTP:**

```bash
themis api                                      # http://127.0.0.1:8000/docs
curl -s http://127.0.0.1:8000/v1/anonimizar -H "Content-Type: application/json" \
     -d '{"texto": "Ana Lima, CPF 529.982.247-25", "perfil": "lai"}'
```

**Docker**, com modelo de linguagem e OCR incluídos:

```bash
docker build -t themis-lgpd .
docker run --rm -p 127.0.0.1:8501:8501 themis-lgpd
```

Referência completa: [docs/GUIA_DE_USO.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/GUIA_DE_USO.md) e [docs/API.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/API.md).

## Formatos

| Formato | O que é analisado | O que é removido |
|---|---|---|
| PDF | Texto horizontal e girado, campos de formulário e anotações visíveis, páginas digitalizadas e fontes sem mapeamento de texto (por OCR) | Texto sob as tarjas (páginas com tarja são rasterizadas, com camada de texto pesquisável), metadados, comentários, anexos, JavaScript, marcadores, dados de assinatura |
| DOCX | Todas as partes: corpo, tabelas, cabeçalhos, rodapés, notas, caixas de texto, gráficos, campos, textos alternativos, destinos de hiperlinks | Alterações controladas (aceitas), comentários, propriedades, miniatura, objetos incorporados, macros, partes órfãs |
| XLSX | Todas as células (inclusive a primeira linha), literais em fórmulas, nomes de abas, cabeçalhos de impressão, validações, formatação condicional, filtros, nomes definidos, gráficos | Comentários, hiperlinks, tabelas dinâmicas, vínculos externos, caches de gráficos, propriedades |
| PPTX | Slides (inclusive ocultos), anotações do orador, mestres e layouts, tabelas, gráficos, textos alternativos, hiperlinks, imagens | Comentários e autores, histórico de coautoria, propriedades, marcas de suplementos, áudios e vídeos, objetos incorporados, macros |
| ODT, ODS | Parágrafos (inclusive conteúdo misto), cabeçalhos e rodapés, células, fórmulas e valores, objetos incorporados, atributos de texto livre, imagens | Alterações controladas (aceitas), comentários, metadados, miniatura, configurações, macros, objetos binários |
| HTML | Texto da página (entidades decodificadas), atributos com texto (`title`, `alt`, formulários), endereços de links, imagens em `data:` | Scripts, eventos, quadros e objetos incorporados, comentários, metadados |
| EML | Assunto, nomes dos correspondentes, corpo em texto e HTML, nomes e conteúdo dos anexos (cada um pelo seu formato) | Endereços de e-mail (trocados por endereço reservado), rotas de entrega, identificadores, DKIM, cabeçalhos `X-…` |
| ZIP | Cada arquivo pelo seu formato; nomes de pastas e de arquivos | Arquivos não suportados ou protegidos (registrados no manifesto), arquivos de sistema, comentário e datas |
| DOC, XLS, PPT, RTF | Convertidos para DOCX, XLSX ou PPTX pelo LibreOffice (quando instalado) e tratados como tal | O mesmo do formato de destino |
| CSV, TXT | Todo o conteúdo | — |
| PNG, JPEG, TIFF | Texto reconhecido por OCR, QR codes | Metadados (EXIF, GPS, XMP, etiquetas TIFF); PNG e JPEG saem em PNG, TIFF em TIFF com as mesmas páginas |

Todo arquivo gerado é relido por um caminho independente; se algum valor tarjado continuar legível,
nenhum arquivo é entregue. Detalhes em [docs/SEGURANCA_E_PRIVACIDADE.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/SEGURANCA_E_PRIVACIDADE.md).

## Perfis e modos de saída

| Perfil | Finalidade |
|---|---|
| `lai` (padrão) | Publicação de respostas e documentos: tarja identificadores e dados sensíveis ligados a pessoa determinada; mantém CNPJ e nomes de instituições; sinaliza localidades e quase-identificadores para revisão |
| `identificadores` | Somente o que identifica diretamente a pessoa; dados sensíveis viram alerta |
| `saude` | Como `lai`, mas tarja toda menção a condições de saúde |
| `ouvidoria` | Manifestações de ouvidoria: preserva a identidade do manifestante (Lei nº 13.460/2017, art. 10, § 7º), tarjando também cidade, lotação, função e turno |
| `educacao` | Documentos escolares: RA, matrícula, turma, série e dados de crianças e adolescentes sempre tarjados |
| `maxima` | Tarja tudo o que for detectado, inclusive localidades, CNPJ e URLs |

| Modo | Exemplo | Natureza |
|---|---|---|
| `etiqueta` (padrão) | `[CPF]` | Remoção |
| `tarja` | `████████` | Remoção |
| `mascara` | `***.***.***-**` | Remoção |
| `pseudonimo` | `Pessoa 1`, `[CPF 2]` | Pseudonimização |
| `hmac` | `[CPF:3fa91c02be]` | Pseudonimização |

Regras por categoria e catálogo de tipos: [docs/TIPOS_DE_DADOS.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/TIPOS_DE_DADOS.md).

## Resultados

| Conjunto | Métrica | Themis | Presidio puro (pt) |
|---|---|---|---|
| esic-ner (975 pedidos, CC BY 4.0) | Entidades pessoais tarjadas | **94,6%** | 53,3% |
| | Nomes / documentos pessoais tarjados | **100% / 100%** | 98,9% / 7,9% |
| | Pedidos com algum vazamento | **10,3%** | 93,3% |
| | Triagem "contém dado pessoal?" (F1) | **0,946** | 0,733 |
| | Tarja fora do gabarito (excesso) | **5,7%** | 30,8% |
| Sintético (1.000 documentos) | Identificadores tarjados | **99,6%** | 57,7% |
| | Documentos com vazamento | **3,3%** | 99,8% |
| Nacional (1.080 documentos, 27 UFs) | Endereços e identificadores tarjados (validação) | **100%** | — |
| | Textos públicos sem nenhuma tarja | **100%** | — |
| Casos difíceis (1.000 casos) | Casos com identificador direto tarjados | **100%** | — |

"Presidio puro" é o Presidio 2.2.366 configurado para português com o modelo `pt_core_news_lg` e os
reconhecedores habilitados por padrão. No esic-ner, a maior parte do que não é tarjado são termos de
saúde em pedidos estatísticos, que o perfil `lai` sinaliza para revisão em vez de tarjar. No conjunto
sintético, todos os vazamentos ocorrem na variante com ruído de OCR simulado. O conjunto nacional,
gerado pelos autores, mede endereços e identificadores das 27 UFs e, em textos de interesse público,
a ausência de tarja indevida; a versão 1.0.0 tarjava 64,5% desses dados. Tempo médio: cerca de
20 ms por pedido em CPU comum. Metodologia e resultados por tipo:
[docs/BENCHMARKS.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/BENCHMARKS.md).

## Privacidade

- Processamento local: nenhuma telemetria, nenhum serviço externo, nenhum download automático.
- Nenhum conteúdo é gravado em disco ou em log; mensagens de erro e avisos não repetem o conteúdo.
- Relatórios publicáveis não contêm os valores originais; o relatório interno com valores exige pedido
  explícito.
- `pseudonimo`, `hmac` e o cofre de reversão são pseudonimização na terminologia da ANPD: o dado
  continua sendo pessoal.

Para relatar uma vulnerabilidade, consulte [SECURITY.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/SECURITY.md).

## Limitações

- Manuscritos, assinaturas, rostos e carimbos não são detectados.
- Nomes incomuns sem contexto, em texto todo em minúsculas, podem não ser detectados.
- Dados sensíveis são reconhecidos por vocabulário; sinônimos raros e medicamentos fora da seleção da
  DCB incluída no pacote podem não ser reconhecidos.
- Números com letras no lugar de dígitos no primeiro caractere, comuns em OCR de baixa qualidade, podem
  não ser reconhecidos.
- Bairros e distritos citados isoladamente, sem logradouro nem expressão de residência, não são
  reconhecidos; municípios homônimos de palavras comuns ("Natal", "Bonito") só são sinalizados com a UF
  ou a designação "município de".
- Páginas de PDF com tarja tornam-se imagem com camada de texto invisível; o arquivo fica maior.
- A decisão sobre o que é público ou restrito cabe à área responsável.

## Documentação

| Documento | Conteúdo |
|---|---|
| [Instalação](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/INSTALACAO.md) | Requisitos, extras, modelo de linguagem, OCR, Docker, operação sem internet |
| [Guia de uso](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/GUIA_DE_USO.md) | Interface web, linha de comando, biblioteca Python, boas práticas de revisão |
| [API HTTP](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/API.md) | Rotas, autenticação, limites, erros |
| [Configuração](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/CONFIGURACAO.md) | Variáveis de ambiente |
| [Como funciona](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/COMO_FUNCIONA.md) | Visão geral do processo de decisão |
| [Arquitetura](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/ARQUITETURA.md) | Fluxo de processamento, módulos, extensibilidade |
| [Segurança e privacidade](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/SEGURANCA_E_PRIVACIDADE.md) | Modelo de ameaças, proteções por formato, riscos residuais |
| [Tipos de dados e perfis](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/TIPOS_DE_DADOS.md) | Catálogo de tipos, base legal, regras por perfil |
| [Benchmarks](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/BENCHMARKS.md) | Metodologia, resultados, reprodução |
| [Demonstração pública](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/DEPLOY.md) | Implantação em servidor próprio com HTTPS |
| [Publicação de versões](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/PUBLICACAO.md) | PyPI, GHCR, assinatura, SBOM e proveniência |
| [Decisões de arquitetura](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/docs/adr/README.md) | Registros de decisão |
| [Histórico de versões](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/CHANGELOG.md) | Alterações por versão |

## Uso com o Presidio

Os reconhecedores brasileiros podem ser registrados em qualquer `AnalyzerEngine` do Presidio:

```python
from themis_lgpd.integracoes.presidio import reconhecedores_brasileiros

for reconhecedor in reconhecedores_brasileiros(com_modelo=False):
    engine.registry.add_recognizer(reconhecedor)
```

No sentido inverso, qualquer reconhecedor do Presidio pode ser somado ao Themis com
`Anonimizador(reconhecedores_extras=[...])`, inclusive o GLiNER (`themis_lgpd.integracoes.gliner`).

## Contribuição

Ver [CONTRIBUTING.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/CONTRIBUTING.md). Ao relatar um dado que não foi tarjado, use sempre exemplo
fictício. Código de conduta: [CODE_OF_CONDUCT.md](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/CODE_OF_CONDUCT.md).

## Origem e créditos

O Themis LGPD foi desenvolvido a partir de uma solução apresentada no 1º Hackathon em Controle Social
(Participa DF) e reescrito para publicação aberta. Autores: Gilson Maciel e Matheus Teixeira.
Componentes de terceiros e respectivas licenças: [NOTICE](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/NOTICE). O projeto não é afiliado nem
endossado por órgão público.

Licença: [MIT](https://github.com/matheusteixeira-commits/themis-lgpd/blob/main/LICENSE).
