# Themis LGPD

Anonimização de documentos públicos brasileiros, construída sobre o
[Microsoft Presidio](https://github.com/data-privacy-stack/presidio), com processamento inteiramente
local.

[![CI](https://github.com/matheusteixeira-commits/themis-lgpd/actions/workflows/ci.yml/badge.svg)](https://github.com/matheusteixeira-commits/themis-lgpd/actions/workflows/ci.yml)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)

O Themis LGPD identifica e remove dados pessoais de textos, PDFs, documentos Word, planilhas e
imagens — nomes, CPF, CNPJ (inclusive o alfanumérico), RG, CNH, PIS, título de eleitor, Cartão SUS,
telefones, e-mails, endereços (inclusive o endereçamento do Distrito Federal), dados bancários,
processos e dados pessoais sensíveis — e gera o relatório de tarjamento com a base legal de cada
tarja, para acompanhar a resposta a pedidos de acesso à informação.

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
- **Arquivos:** PDF (com tarja real), DOCX, XLSX, CSV, TXT, PNG e JPEG, com OCR local.
- **Revisão humana** na interface web; relatório e nota de tarjamento com base legal.
- **Quatro interfaces:** interface web, linha de comando, biblioteca Python e API HTTP.
- **Operação sem internet:** nenhuma telemetria, nenhum serviço externo, nenhum download automático.

## Início rápido

```bash
pip install "themis-lgpd[completo]"
python -m spacy download pt_core_news_lg
```

Requer Python 3.11 ou mais recente. Para PDFs digitalizados e imagens, instale também o Tesseract
com o idioma português ou use o RapidOCR incluído no extra `completo`. Detalhes em
[docs/INSTALACAO.md](docs/INSTALACAO.md).

**Interface web**, com revisão humana:

```bash
themis interface                                # http://127.0.0.1:8501
```

**Linha de comando:**

```bash
themis anonimizar resposta.pdf                  # gera resposta_anonimizado.pdf
themis anonimizar *.docx -o saida/ -r relatorio.xlsx
themis anonimizar planilha.xlsx --coluna-integral "Nome do servidor"
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

Referência completa: [docs/GUIA_DE_USO.md](docs/GUIA_DE_USO.md) e [docs/API.md](docs/API.md).

## Formatos

| Formato | O que é analisado | O que é removido |
|---|---|---|
| PDF | Texto horizontal e girado, campos de formulário e anotações visíveis, páginas digitalizadas e fontes sem mapeamento de texto (por OCR) | Texto sob as tarjas (páginas com tarja são rasterizadas, com camada de texto pesquisável), metadados, comentários, anexos, JavaScript, marcadores, dados de assinatura |
| DOCX | Todas as partes: corpo, tabelas, cabeçalhos, rodapés, notas, caixas de texto, gráficos, campos, textos alternativos, destinos de hiperlinks | Alterações controladas (aceitas), comentários, propriedades, miniatura, objetos incorporados, macros, partes órfãs |
| XLSX | Todas as células (inclusive a primeira linha), literais em fórmulas, nomes de abas, cabeçalhos de impressão, validações, formatação condicional, filtros, nomes definidos, gráficos | Comentários, hiperlinks, tabelas dinâmicas, vínculos externos, caches de gráficos, propriedades |
| CSV, TXT | Todo o conteúdo | — |
| PNG, JPEG | Texto reconhecido por OCR | Metadados (EXIF, GPS); a saída é um PNG novo |

Todo arquivo gerado é relido por um caminho independente; se algum valor tarjado continuar legível,
nenhum arquivo é entregue. Detalhes em [docs/SEGURANCA_E_PRIVACIDADE.md](docs/SEGURANCA_E_PRIVACIDADE.md).

## Perfis e modos de saída

| Perfil | Finalidade |
|---|---|
| `lai` (padrão) | Publicação de respostas e documentos: tarja identificadores e dados sensíveis ligados a pessoa determinada; mantém CNPJ e nomes de instituições; sinaliza localidades e quase-identificadores para revisão |
| `identificadores` | Somente o que identifica diretamente a pessoa; dados sensíveis viram alerta |
| `saude` | Como `lai`, mas tarja toda menção a condições de saúde |
| `maxima` | Tarja tudo o que for detectado, inclusive localidades, CNPJ e URLs |

| Modo | Exemplo | Natureza |
|---|---|---|
| `etiqueta` (padrão) | `[CPF]` | Remoção |
| `tarja` | `████████` | Remoção |
| `mascara` | `***.***.***-**` | Remoção |
| `pseudonimo` | `Pessoa 1`, `[CPF 2]` | Pseudonimização |
| `hmac` | `[CPF:3fa91c02be]` | Pseudonimização |

Regras por categoria e catálogo de tipos: [docs/TIPOS_DE_DADOS.md](docs/TIPOS_DE_DADOS.md).

## Resultados

| Conjunto | Métrica | Themis | Presidio puro (pt) |
|---|---|---|---|
| esic-ner (975 pedidos, CC BY 4.0) | Entidades pessoais tarjadas | **94,5%** | 53,3% |
| | Nomes / documentos pessoais tarjados | **100% / 100%** | 98,9% / 7,9% |
| | Pedidos com algum vazamento | **10,5%** | 93,3% |
| | Triagem "contém dado pessoal?" (F1) | **0,944** | 0,733 |
| | Tarja fora do gabarito (excesso) | **5,7%** | 30,8% |
| Sintético (1.000 documentos) | Identificadores tarjados | **99,6%** | 57,7% |
| | Documentos com vazamento | **3,3%** | 99,8% |
| Casos difíceis (1.000 casos) | Casos com identificador direto tarjados | **100%** | — |

"Presidio puro" é o Presidio 2.2.366 configurado para português com o modelo `pt_core_news_lg` e os
reconhecedores habilitados por padrão. No esic-ner, a maior parte do que não é tarjado são termos de
saúde em pedidos estatísticos, que o perfil `lai` sinaliza para revisão em vez de tarjar. No conjunto
sintético, todos os vazamentos ocorrem na variante com ruído de OCR simulado. Tempo médio: cerca de
20 ms por pedido em CPU comum. Metodologia e resultados por tipo:
[docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## Privacidade

- Processamento local: nenhuma telemetria, nenhum serviço externo, nenhum download automático.
- Nenhum conteúdo é gravado em disco ou em log; mensagens de erro e avisos não repetem o conteúdo.
- Relatórios publicáveis não contêm os valores originais; o relatório interno com valores exige pedido
  explícito.
- `pseudonimo`, `hmac` e o cofre de reversão são pseudonimização na terminologia da ANPD: o dado
  continua sendo pessoal.

Para relatar uma vulnerabilidade, consulte [SECURITY.md](SECURITY.md).

## Limitações

- Manuscritos, assinaturas, rostos e carimbos não são detectados; imagens dentro de DOCX e XLSX não são
  analisadas (o usuário é avisado).
- Nomes incomuns sem contexto, em texto todo em minúsculas, podem não ser detectados.
- Dados sensíveis são reconhecidos por vocabulário; sinônimos raros e nomes de medicamentos podem não
  ser reconhecidos.
- Números com letras no lugar de dígitos no primeiro caractere, comuns em OCR de baixa qualidade, podem
  não ser reconhecidos.
- Localidades isoladas são reconhecidas para as regiões administrativas do Distrito Federal.
- Páginas de PDF com tarja tornam-se imagem com camada de texto invisível; o arquivo fica maior.
- A decisão sobre o que é público ou restrito cabe à área responsável.

## Documentação

| Documento | Conteúdo |
|---|---|
| [Instalação](docs/INSTALACAO.md) | Requisitos, extras, modelo de linguagem, OCR, Docker, operação sem internet |
| [Guia de uso](docs/GUIA_DE_USO.md) | Interface web, linha de comando, biblioteca Python, boas práticas de revisão |
| [API HTTP](docs/API.md) | Rotas, autenticação, limites, erros |
| [Configuração](docs/CONFIGURACAO.md) | Variáveis de ambiente |
| [Como funciona](docs/COMO_FUNCIONA.md) | Visão geral do processo de decisão |
| [Arquitetura](docs/ARQUITETURA.md) | Fluxo de processamento, módulos, extensibilidade |
| [Segurança e privacidade](docs/SEGURANCA_E_PRIVACIDADE.md) | Modelo de ameaças, proteções por formato, riscos residuais |
| [Tipos de dados e perfis](docs/TIPOS_DE_DADOS.md) | Catálogo de tipos, base legal, regras por perfil |
| [Benchmarks](docs/BENCHMARKS.md) | Metodologia, resultados, reprodução |
| [Demonstração pública](docs/DEPLOY.md) | Implantação em servidor próprio com HTTPS |
| [Decisões de arquitetura](docs/adr/README.md) | Registros de decisão |
| [Histórico de versões](CHANGELOG.md) | Alterações por versão |

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

Ver [CONTRIBUTING.md](CONTRIBUTING.md). Ao relatar um dado que não foi tarjado, use sempre exemplo
fictício. Código de conduta: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Origem e créditos

O Themis LGPD foi desenvolvido a partir de uma solução apresentada no 1º Hackathon em Controle Social
(Participa DF) e reescrito para publicação aberta. Autores: Gilson Maciel e Matheus Teixeira.
Componentes de terceiros e respectivas licenças: [NOTICE](NOTICE). O projeto não é afiliado nem
endossado por órgão público.

Licença: [MIT](LICENSE).
