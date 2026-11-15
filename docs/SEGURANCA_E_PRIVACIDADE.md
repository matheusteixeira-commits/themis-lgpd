# Segurança e privacidade

Este documento descreve o modelo de ameaças do Themis LGPD, as proteções implementadas em cada
formato de arquivo, a verificação final e os riscos residuais. Para relatar uma vulnerabilidade,
siga a [política de segurança](../SECURITY.md).

## Princípios

1. **Processamento local.** Nenhum conteúdo sai da máquina. Não há telemetria, chamada a serviços
   externos nem download automático de modelos (ver [ADR 0005](adr/0005-operacao-offline.md)).
2. **Remoção efetiva.** O que é tarjado deixa de existir no arquivo gerado; não é apenas encoberto
   (ver [ADR 0002](adr/0002-tarja-por-rasterizacao-em-pdf.md)).
3. **Falha fechada.** Diante de dúvida sobre um identificador, o Themis tarja; diante de dúvida sobre o
   arquivo gerado, não o entrega (ver [ADR 0006](adr/0006-verificacao-final-e-falha-fechada.md)).
4. **Nenhum registro de conteúdo.** Mensagens de erro, avisos, logs e relatórios publicáveis não
   contêm trechos dos documentos.
5. **Revisão humana.** A ferramenta apoia a decisão sobre o que tarjar; não a substitui.

## Modelo de ameaças

| Ameaça | Exemplo | Mitigação |
|---|---|---|
| Dado não detectado no texto | Nome sem contexto em minúsculas | Reconhecedores complementares (lista, gatilhos, modelo), falha fechada para identificadores, propagação no documento, revisão humana |
| Dado detectado em um ponto e exposto em outro | CPF citado no corpo e repetido no rodapé sem a palavra "CPF" | Propagação de valores tarjados para todo o documento |
| Fragmento ao lado da tarja | `CNH 0[TELEFONE]` | Expansão até o limite do token e prioridade por caractere |
| Conteúdo oculto no arquivo | Texto sob tarja desenhada, metadados, comentários, alterações controladas, partes órfãs do pacote | Rasterização, saneamento e reconstrução dos arquivos |
| Conteúdo fora do fluxo de texto | Texto girado, campos de formulário, texto alternativo de imagens, nomes de abas, fórmulas | Extração específica por formato e análise de todo texto encontrado |
| Evasão por formatação | Caracteres invisíveis, homóglifos, hifenização, ruído de OCR | Normalização com mapa de posições |
| Arquivo malicioso | Bomba de compressão, XML com entidades externas, PDF malformado | Limites de tamanho, páginas, pixels e entradas; XML sem DTD e sem rede; exceções tratadas sem eco |
| Exposição por mensagens e logs | Exceção de biblioteca que cita o texto | Mensagens próprias sem conteúdo; registro apenas do tipo da exceção |
| Abuso de instância pública | Esgotamento de CPU, varredura | Limites de corpo, taxa, concorrência e tempo; proxy com limite por IP |
| Injeção na interface | HTML ou Markdown vindo de um documento | Renderização com escape de todo o conteúdo; CSP sem domínios externos |

Fora do escopo: comprometimento do sistema operacional ou do ambiente Python em que o Themis executa,
e conteúdo que não é texto (rostos, assinaturas manuscritas, imagens dentro de documentos Office).

## Proteções por formato

### PDF

| Etapa | Proteção |
|---|---|
| Incorporação de anotações | Campos de formulário preenchidos, carimbos de assinatura e caixas de texto livre visíveis são incorporados ao conteúdo da página antes da extração (`flatten_annotations` do pikepdf) e analisados como texto comum. Comentários e campos ocultos não são incorporados e são removidos depois. |
| Texto girado | Caracteres não horizontais são agrupados por coluna e lidos no sentido indicado pela matriz de cada caractere (90° ou −90°), como as notas de margem de documentos assinados digitalmente. As tarjas são contínuas por coluna. |
| Fontes sem mapeamento Unicode | Quando mais de 10% dos caracteres da página não podem ser decodificados (`(cid:N)`, caractere de substituição, área de uso privado), a página passa por OCR. |
| Páginas digitalizadas e texto em contornos | Páginas com imagens ocupando mais de 15% da área, com imagens e menos de 25 caracteres de texto, ou sem camada de texto e com 40 curvas vetoriais ou mais (texto convertido em contornos), passam por OCR. Se o OCR for necessário e nenhum mecanismo estiver instalado, ou se o OCR falhar, o processamento é interrompido com `FalhaOCR`: tratar a falha como "página sem texto" entregaria o conteúdo sem tarja. Somente com o OCR desativado explicitamente (`--sem-ocr`, `ocr=False`) o PDF é gerado sem analisar essas páginas, que são listadas em aviso. Páginas em que o OCR não reconhece texto (manuscritos, baixa resolução) também são listadas. |
| Tarja | Páginas com tarja são renderizadas a 200 dpi; as tarjas são aplicadas nos pixels e uma camada de texto invisível é recriada somente com as palavras não tarjadas, preservando busca e acessibilidade. Texto girado não é recriado na camada invisível. |
| QR codes | Páginas com imagens ou com muitos retângulos e curvas (QR codes desenhados como vetores, comuns em GRU e boletos) são renderizadas e examinadas; o tratamento segue a política descrita em [Imagens incorporadas, QR codes e metarquivos](#imagens-incorporadas-qr-codes-e-metarquivos). |
| Saneamento | O arquivo é reescrito por inteiro, sem atualizações incrementais. São removidos: dicionário de informações, metadados XMP (inclusive os de imagens e outros objetos), metadados gravados dentro das imagens JPEG e JPEG 2000 (EXIF, GPS, XMP, comentários), nomes e anexos, ações de abertura, formulários, marcadores, estrutura de tags, textos alternativos de conteúdo marcado (`/ActualText`, `/Alt`, `/E`), dados de validação de assinaturas (`/DSS`), camadas opcionais (com nomes de camada neutralizados), anotações remanescentes, miniaturas e dados privados de aplicativos. |
| Verificação | O arquivo gerado é relido por dois extratores independentes (pdfplumber e PDFium); as cadeias de caracteres de todos os objetos, os fluxos de metadados e anexos e o conteúdo bruto de todas as páginas e formulários são inspecionados; as imagens são conferidas quanto a metadados. Páginas cujas tarjas foram posicionadas pelos pixels (OCR ou QR code) são renderizadas novamente e relidas por OCR e pela busca de QR codes. Um fluxo ilegível também interrompe a operação. |

Avisos emitidos: anexos removidos, formulários incorporados, páginas convertidas em imagem, páginas
analisadas por OCR por causa das fontes, páginas não analisadas por OCR desativado, páginas em que o
OCR não reconheceu texto e páginas com imagens pequenas não analisadas (assinaturas digitalizadas,
fotos, carimbos).

O Tesseract recebe a imagem da página pela entrada padrão e devolve o resultado pela saída padrão:
nenhum arquivo temporário com o conteúdo do documento é gravado em disco.

### DOCX

O pacote é tratado no nível do XML, parte por parte.

**Analisado e tarjado:**

- texto de todas as partes: corpo, tabelas, caixas de texto, cabeçalhos e rodapés, notas de rodapé e
  de fim, equações, gráficos (títulos, rótulos e valores em cache), SmartArt e formas;
- texto dividido entre trechos de formatação ("Mar" + "ia") e separado por tabulação ou quebra de
  linha, analisado como fluxo contínuo;
- instruções de campo (`HYPERLINK "mailto:..."`) e campos simples;
- atributos de texto livre: texto alternativo, título e nome de imagens e formas, dicas de hiperlinks,
  rótulos e itens de controles de conteúdo e de campos de formulário, texto de WordArt;
- destinos de hiperlinks externos (o destino vira `#` quando contém dado tarjado);
- qualquer outro texto presente em qualquer elemento de qualquer parte XML;
- imagens rasterizadas, imagens vetoriais EMF/WMF e SVG (ver
  [Imagens incorporadas, QR codes e metarquivos](#imagens-incorporadas-qr-codes-e-metarquivos)).

**Removido:**

- alterações controladas, que são aceitas: o texto excluído é descartado e os nomes dos revisores
  desaparecem;
- comentários e a lista de autores;
- propriedades do documento (autor, empresa, gerente, título, assunto, palavras-chave, propriedades
  personalizadas), mantidas somente as datas de criação e modificação, e a miniatura da primeira página;
- dados XML personalizados e vínculos de dados de controles de conteúdo, variáveis do documento,
  modelo anexado, configuração de mala direta, propriedades de marcas inteligentes;
- assinaturas digitais;
- objetos incorporados (planilhas de gráficos, objetos OLE, controles ActiveX), blocos de conteúdo
  importado (`altChunk`), glossário, macros e configurações de impressora;
- referências a arquivos locais (caminhos que costumam conter o nome do usuário ou do servidor);
- partes do pacote não referenciadas por nenhum relacionamento;
- identificadores de sessão de edição (`rsid`, `paraId`, `docId`), que permitiriam correlacionar o
  documento anonimizado com a versão original;
- nomes originais dos arquivos de mídia (renomeados para `midia1.png`, `midia2.emf`…) e nomes internos
  de imagens e formas.

**Recusado:** pacotes com entradas duplicadas ou criptografadas, XML com declaração de DTD, documentos
no formato OOXML Strict e arquivos acima dos limites de tamanho descompactado (300 MB) ou de número de
entradas (10.000). Documentos protegidos por senha e formatos antigos (`.doc`) são recusados.

Documentos `.docm` e `.dotx` são gravados como `.docx` comum.

### XLSX

**Analisado e tarjado:**

- todas as células, inclusive a primeira linha (nem toda planilha tem cabeçalho);
- colunas cujo cabeçalho indica dado pessoal ("Nome", "CPF", "E-mail", "Endereço" etc.) são tarjadas
  por inteiro;
- literais de texto em fórmulas (`="Maria Souza"`), inclusive em fórmulas matriciais;
- nomes de abas, com atualização das referências em fórmulas, validações, formatação condicional,
  nomes definidos e gráficos;
- cabeçalhos e rodapés de impressão;
- mensagens e listas de validação de dados;
- regras de formatação condicional (fórmulas e texto);
- critérios de filtros automáticos, inclusive de tabelas;
- nomes definidos;
- texto de gráficos e desenhos;
- imagens (OCR e QR codes), com os valores tarjados nas células propagados para elas.

**Removido:** comentários, hiperlinks, tabelas dinâmicas (o cache guarda cópia dos dados originais),
vínculos com outras pastas de trabalho, macros, propriedades do documento e caches de dados dos
gráficos (o Excel os recalcula a partir das células ao abrir). Os nomes das colunas de tabelas são
mantidos iguais às células de cabeçalho.

### CSV

Todas as células são analisadas, inclusive a primeira linha. O delimitador original é preservado e a
saída é gravada em UTF-8 com BOM.

### TXT

O texto é decodificado como UTF-8 (com ou sem BOM) ou, na falha, como Windows-1252, com aviso; a saída
é sempre UTF-8.

### Imagens (PNG e JPEG)

O texto é reconhecido por OCR local e as regiões tarjadas são cobertas nos pixels, com margem de
4 pixels; a orientação registrada no EXIF é aplicada antes do OCR. Imagens só são processadas com o
OCR ativado; sem mecanismo de OCR instalado, ou com falha na execução do OCR, o processamento é
interrompido com `FalhaOCR`. A imagem é gravada como PNG novo: nenhum metadado do original (EXIF, GPS,
perfil de cor, miniatura) é copiado. Após a tarja, a imagem gerada passa por novo OCR e nova busca de
QR codes. O limite de descompressão do Pillow é fixado em 60 milhões de pixels, como proteção contra
imagens construídas para esgotar a memória.

### Imagens incorporadas, QR codes e metarquivos

**Metadados de imagens.** Fotos coladas em documentos carregam metadados invisíveis na revisão:
coordenadas GPS, autor, modelo do aparelho, miniatura da imagem original e, em fotos de celular, vídeo
anexado ao fim do arquivo. Em DOCX, XLSX e nas páginas de PDF, esses dados são removidos sem
recompressão (`formatos/midia.py`): JPEG mantém só os segmentos de decodificação (o perfil de cor ICC
e o segmento Adobe são preservados); PNG, GIF, WebP e TIFF perdem blocos de texto, EXIF e XMP; JPEG
2000 mantém só cabeçalho e fluxo codificado. A verificação final falha se alguma imagem do arquivo
gerado ainda tiver metadados.

**Texto de imagens rasterizadas em DOCX e XLSX.** Imagens com o menor lado a partir de 48 pixels
passam por OCR e pela busca de QR codes; o texto entra no mesmo lote de análise do documento, de modo
que um nome tarjado no corpo é tarjado também na imagem. As regiões são tarjadas nos pixels e a imagem
é regravada no formato original, sem metadados, e relida por OCR. Sem OCR instalado, o processamento é
interrompido com `FalhaOCR`, exceto com o OCR desativado explicitamente.

**QR codes** (`formatos/qr.py`). O BR Code do PIX (nome do recebedor e chave, que pode ser CPF, e-mail
ou telefone) é sempre tarjado; o conteúdo dos demais QR codes é analisado como texto do documento e o
código é tarjado se contiver dado a tarjar; QR codes localizados, mas não decodificáveis, são tarjados.

**Metarquivos EMF e WMF** (`formatos/metarquivo.py`). Tabelas e diagramas colados como imagem no Word
guardam o texto legível dentro do arquivo. O texto dos registros GDI e EMF+ é extraído, analisado com
o documento e mascarado no próprio arquivo (`█` em UTF-16, `X` em texto de 8 bits), sem alterar a
estrutura. Texto gravado apenas como índices de glifos não pode ser lido e é informado em aviso.

**SVG.** Texto, título, descrição e atributos de texto livre (rótulos de editores, nome do arquivo de
origem) são analisados como as demais partes XML.

### Formatos recusados

HTML, XML, RTF, mensagens de e-mail, mensagens do Outlook (`.msg`), TIFF, GIF, BMP e WebP avulsos são
recusados com orientação de conversão. Nesses formatos o conteúdo pode estar codificado (entidades
como `&#46;`, escapes como `\'e3`, corpo em base64) e não pode ser tratado como texto simples sem
deixar dados fora da análise.

## Verificação final

Todo formato relê o arquivo gerado por um caminho diferente do usado na anonimização e confirma que
nenhum valor tarjado continua legível (`formatos/verificacao.py`). As regras de comparação são:

| Regra | Motivo |
|---|---|
| Caixa e acentos ignorados | `MARIA` e `Mária` são o mesmo valor |
| Até três caracteres não alfanuméricos tolerados entre dois caracteres do valor | Quebras de linha, hifenização, espaçamento entre letras, texto dividido entre elementos XML |
| Valor deve começar e terminar em limite de palavra | "Costa" tarjado não é confundido com "acostamento" |
| Números com oito dígitos ou mais também são procurados apenas pelos dígitos | O mesmo CPF escrito com outra pontuação |
| Trechos mantidos intencionalmente são desconsiderados | Lista de permissão, regra `manter`, nomes de lugares e organizações não tarjados |
| Ocorrência só é desconsiderada quando inteiramente contida em trecho protegido | Permitir "Maria" não esconde "Maria Souza" |
| Nomes de pessoa dentro de nomes de lugares e instituições são desconsiderados | Mesma regra da propagação ("Paulo" em "São Paulo") |
| Valores com menos de cinco letras e dígitos não são verificados | Coincidências com palavras comuns; continuam tarjados normalmente |

Se algum valor continuar legível, a operação levanta `VazamentoDetectado` e nenhum arquivo é
entregue. A mensagem informa apenas a quantidade de trechos, nunca os valores. Na API, a resposta é
HTTP 500; na CLI, o arquivo é ignorado e o código de saída é 1. A verificação também se aplica ao texto
lido da entrada padrão (`themis anonimizar -`).

O parâmetro `verificar=False` de `anonimizar_arquivo` desliga a verificação e existe apenas para
medições de desempenho.

## Mensagens, avisos e registros

- `ArquivoInvalido`, `FalhaOCR` e `VazamentoDetectado` têm mensagens próprias, que nunca incluem
  conteúdo do arquivo.
- Avisos identificam colunas pela letra e abas pelo título já anonimizado; nunca repetem textos do
  documento.
- A CLI exibe apenas o tipo de exceções inesperadas e sai com código 2; a API registra apenas o tipo
  da exceção e responde com mensagem genérica; a interface exibe "Não foi possível processar o
  arquivo".
- Na API, os registros de exceção do servidor ASGI (Uvicorn) também são reduzidos ao tipo do erro, sem
  mensagem nem rastreamento, por um filtro de log aplicado aos registradores `uvicorn`, `uvicorn.error`
  e `gunicorn.error`.
- Os registros de depuração do Presidio são limitados ao nível WARNING, para que uma aplicação
  hospedeira configurada em DEBUG não registre informações sobre documentos.
- A API iniciada por `themis api` não registra log de acesso (`access_log=False`), e o proxy da
  demonstração não grava log de acesso.

## Relatórios

- **Relatório de tarjamento** (JSON, CSV, XLSX) e **nota de tarjamento** (texto): tipo de dado,
  categoria, base legal, justificativa, confiança e um trecho do texto *já anonimizado* em volta de cada
  tarja. Não contêm os valores originais e podem acompanhar a resposta a um pedido de acesso.
- **Relatório interno com valores**: somente com `--incluir-valores` (CLI) ou confirmação explícita na
  interface; marcado com "CONTÉM DADOS PESSOAIS ORIGINAIS". Desativado na demonstração pública.
- Relatórios CSV e XLSX neutralizam fórmulas (`=`, `+`, `-`, `@` no início da célula).

## Interface e API

**Interface (Streamlit):** todo o conteúdo dos documentos é exibido com escape de HTML; telemetria
desativada (`gatherUsageStats=false`); proteção XSRF ativa; detalhes de erro ocultos; observação de
arquivos desativada. Na demonstração pública, o limite é de 40 análises por sessão por hora, o modo
`hmac` e o relatório com valores ficam indisponíveis e uma faixa orienta a não enviar documentos reais.

**API (FastAPI):** limite de corpo (413), limite de requisições por IP por minuto (429), concorrência e
tempo máximos (503; após o tempo limite, a vaga só é liberada quando a análise termina de fato, de
modo que o número de análises em execução nunca excede o configurado), OCR indisponível (503), chave
de API opcional com comparação em tempo constante (401), CORS fechado por
padrão e sem credenciais, cabeçalhos `Cache-Control: no-store`, `X-Content-Type-Options`,
`Referrer-Policy`, `X-Frame-Options` e CSP; erros de validação sem eco da entrada; documentação
interativa desativável. Detalhes em [API.md](API.md).

**Demonstração pública:** contêiner sem root, sem capabilities, com sistema de arquivos somente
leitura e temporários em memória; proxy Caddy com HTTPS, HSTS, limite de corpo, limite por IP, CSP sem
domínios externos e sem log de acesso. Ver [DEPLOY.md](DEPLOY.md).

## Cadeia de suprimentos

- Dependências de produção fixadas em `requirements/producao.txt`, auditadas por `pip-audit` no CI e
  atualizadas pelo Dependabot.
- Ações do GitHub fixadas por hash de commit.
- Imagem Docker com base fixada por digest, modelo spaCy verificado por hash SHA-256 e varredura pelo
  Trivy.
- Varredura de segredos no histórico (gitleaks) e análise estática (bandit, ruff).
- Nenhuma dependência do núcleo tem licença incompatível com a MIT (por exemplo, PyMuPDF, de licença
  AGPL, não é usado).

## Anonimização e pseudonimização

Na terminologia da LGPD e da ANPD, **anonimização** torna o titular não identificável por meios
razoáveis; **pseudonimização** substitui o dado por um código, mas mantém a possibilidade de
reidentificação com informação adicional guardada separadamente. Dado pseudonimizado continua sendo
dado pessoal.

| Modo ou recurso | Natureza |
|---|---|
| `etiqueta` (`[CPF]`), `tarja` (`████████`), `mascara` (`***.***.***-**`) | Remoção do dado |
| `pseudonimo` (`Pessoa 1`, `[CPF 2]`) | Pseudonimização: a correspondência entre menções é preservada |
| `hmac` (`[CPF:3fa9…]`) | Pseudonimização: quem tem a chave pode confirmar um valor |
| Cofre de reversão (`--cofre`) | Pseudonimização reversível com senha |

A remoção do dado não garante, sozinha, a anonimização do documento: a combinação de
quase-identificadores (cargo, local de trabalho, datas, circunstâncias) pode permitir a
reidentificação. Por isso o perfil `lai` sinaliza quase-identificadores para revisão.

## Riscos residuais e limitações

- **Cobertura de detecção.** Nomes incomuns sem contexto, em texto todo em minúsculas, podem não ser
  detectados. Dados sensíveis são reconhecidos por vocabulário (cerca de 150 condições de saúde e
  termos de religião, política, sindicatos, vida sexual, origem racial, violência); sinônimos raros e
  nomes de medicamentos podem não ser reconhecidos.
- **Localidades.** O reconhecimento de localidades isoladas cobre as regiões administrativas do
  Distrito Federal; cidades de outras unidades da federação não são sinalizadas como localidade.
- **Imagens em documentos Office.** Imagens com o menor lado abaixo de 48 pixels não passam por OCR;
  texto em imagens vetoriais gravado só como índices de glifos não pode ser lido (o usuário é avisado).
- **Conteúdo visual.** Manuscritos, assinaturas, rostos, carimbos e texto em imagens pequenas não são
  detectados. A qualidade do OCR depende da digitalização.
- **Texto em contornos.** Páginas de PDF sem camada de texto e com 40 curvas vetoriais ou mais
  (texto convertido em contornos) passam por OCR. Texto em contornos com menos curvas que esse
  limite, em uma página que também tem camada de texto, não é analisado.
- **Formatos com perda.** Páginas de PDF com tarja tornam-se imagem com camada de texto invisível; o
  arquivo fica maior e o texto girado dessas páginas não é pesquisável. Objetos incorporados em DOCX e
  caches de gráficos em XLSX são removidos.
- **Verificação.** Valores com menos de cinco letras e dígitos não são verificados; a verificação de
  imagens depende do OCR.
- **Decisão jurídica.** A classificação de uma informação como pública ou restrita cabe à área
  responsável. O Themis não decide sobre sigilo legal, segredo de justiça ou informações classificadas.

A revisão humana antes da publicação é obrigatória.
