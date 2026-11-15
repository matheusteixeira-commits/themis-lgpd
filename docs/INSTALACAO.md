# Instalação

## Requisitos

| Componente | Requisito |
|---|---|
| Python | 3.11, 3.12 ou 3.13 (o Presidio exige 3.11 ou mais recente) |
| Memória | 2 GB livres para o modelo de linguagem; 4 GB recomendados para PDFs grandes e OCR |
| Disco | Cerca de 1,5 GB (dependências e modelo `pt_core_news_lg`) |
| Sistema | Linux, Windows ou macOS |
| OCR (opcional) | Tesseract com o idioma `por`, ou RapidOCR (instalado pelo extra `ocr`) |

## Pacote portátil para Windows

Para computadores sem Python e sem permissão de administrador — a situação comum em órgãos
públicos —, há um pacote portátil: uma pasta com o Python incorporável oficial, as dependências, o
modelo de linguagem e o Themis, que funciona a partir de qualquer local (disco, pen drive, pasta de
rede) e não altera nada no Windows.

1. Baixe `themis-lgpd-<versão>-windows-x64.zip` (artefato do workflow "Pacote portátil para Windows"
   ou anexo da versão publicada) e extraia-o.
2. Dê dois cliques em `Iniciar Themis.bat`: o navegador abre a interface em `http://127.0.0.1:8501`.
3. Para a linha de comando, use `themis.bat` na mesma pasta (`themis.bat anonimizar documento.pdf`).

O OCR usa o RapidOCR incluído; nenhum outro programa precisa ser instalado. O pacote é montado por
`scripts/empacotar_windows.py`, que confere o Python incorporável pelo resumo publicado pelo
python.org, e verificado a cada alteração no CI por `scripts/verificar_pacote_windows.py`, que o
executa sem nenhum Python no `PATH` e anonimiza os exemplos fictícios de `exemplos/`.

## Instalação com pip

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install "themis-lgpd[completo]"
python -m spacy download pt_core_news_lg
```

O modelo de linguagem é baixado uma única vez (cerca de 570 MB). O Themis nunca o baixa
automaticamente: sem o modelo, a criação de um `Anonimizador` falha com uma mensagem que indica o
comando acima.

### Extras

O pacote base contém apenas o motor de texto. Os recursos adicionais são instalados por extras:

| Extra | Conteúdo | Necessário para |
|---|---|---|
| `arquivos` | pdfplumber, pdfminer.six, pypdfium2, pikepdf, ReportLab, Pillow, python-docx, openpyxl, OpenCV (headless) | PDF, DOCX, XLSX e imagens; detecção de QR codes |
| `ocr` | RapidOCR e ONNX Runtime (modelo multilíngue incluído no pacote) | OCR sem instalar o Tesseract |
| `api` | FastAPI, Starlette, Uvicorn, python-multipart | `themis api` |
| `ui` | Streamlit, pandas | `themis interface` |
| `ml` | presidio-analyzer com GLiNER (PyTorch) | Reconhecedor neural opcional |
| `completo` | `arquivos`, `ocr`, `api` e `ui` | Uso geral |
| `dev` | `completo`, pytest, pytest-cov, httpx, ruff, Faker, pip-audit, bandit | Desenvolvimento |

Exemplos:

```bash
pip install themis-lgpd                       # somente texto (biblioteca e CLI para texto)
pip install "themis-lgpd[arquivos,ocr]"       # arquivos com OCR, sem interface
pip install "themis-lgpd[completo,ml]"        # tudo, inclusive GLiNER
```

### Modelo de linguagem

O modelo `pt_core_news_lg` (Explosion AI) é distribuído sob a licença CC BY-SA 4.0. Ele não faz parte
do repositório; é instalado separadamente e incluído na imagem Docker sob a mesma licença. Outro modelo
spaCy em português pode ser usado com `--modelo` (CLI), `modelo_spacy=` (biblioteca) ou
`THEMIS_MODELO_SPACY` (API e interface).

Para instalar o modelo a partir de um arquivo, por exemplo em máquinas sem acesso à internet:

```bash
pip install pt_core_news_lg-3.8.0-py3-none-any.whl
```

O arquivo está disponível nas versões publicadas do repositório `explosion/spacy-models`. A imagem
Docker confere o hash SHA-256 do arquivo durante a construção.

Sem o modelo, é possível operar com `usar_ner=False` (CLI `--sem-ner`), com cobertura reduzida de
nomes: permanecem a lista de nomes brasileiros e os gatilhos de contexto.

### OCR

O OCR é usado em PDFs digitalizados, em páginas com imagens grandes ou com fontes sem mapeamento de
texto, e em imagens PNG e JPEG. O Themis usa o Tesseract quando ele está instalado com o idioma `por`
(melhor qualidade para português) e, na falta dele, o RapidOCR.

| Sistema | Instalação do Tesseract |
|---|---|
| Debian, Ubuntu | `sudo apt install tesseract-ocr tesseract-ocr-por` |
| Fedora | `sudo dnf install tesseract tesseract-langpack-por` |
| macOS (Homebrew) | `brew install tesseract tesseract-lang` |
| Windows | Instalador do projeto Tesseract (UB Mannheim), marcando o idioma português, e o executável no `PATH` |

Sem nenhum mecanismo de OCR, imagens não podem ser processadas e PDFs que exigem OCR são recusados
(exceção `FalhaOCR`), a menos que o OCR seja desativado explicitamente (CLI `--sem-ocr`); nesse caso, as páginas que
exigiriam OCR são listadas em aviso como não analisadas.

## Instalação com Docker

A imagem inclui o modelo de linguagem e o Tesseract com português e executa sem acesso à internet.

```bash
git clone https://github.com/matheusteixeira-commits/themis-lgpd.git
cd themis-lgpd
docker build -t themis-lgpd .

# Interface web em http://127.0.0.1:8501
docker run --rm -p 127.0.0.1:8501:8501 themis-lgpd

# API em http://127.0.0.1:8000
docker run --rm -p 127.0.0.1:8000:8000 themis-lgpd api --endereco 0.0.0.0 --porta 8000

# CLI sobre arquivos de uma pasta local
docker run --rm -v "$PWD/documentos:/dados" -w /dados themis-lgpd anonimizar despacho.pdf
```

A imagem executa como usuário sem privilégios (UID 10001) e pode ser executada com sistema de
arquivos somente leitura (`--read-only --tmpfs /tmp`). Para a pasta montada receber os arquivos
gerados, ela deve permitir escrita ao UID 10001.

Para a demonstração pública com HTTPS, consulte [DEPLOY.md](DEPLOY.md).

A imagem usa o Tesseract para OCR e não inclui o RapidOCR. A verificação de saúde (`themis saude`)
vale tanto para a interface quanto para a API.

### Imagem publicada e verificação de autenticidade

As versões publicadas ficam no GitHub Container Registry, assinadas com cosign (sem chave, pela
identidade do workflow de publicação) e com atestado de proveniência SLSA. Antes de usar a imagem em
produção, confira as duas coisas:

```bash
IMAGEM=ghcr.io/matheusteixeira-commits/themis-lgpd:1.1.0
cosign verify "$IMAGEM"   --certificate-identity-regexp '^https://github.com/matheusteixeira-commits/themis-lgpd/\.github/workflows/release\.yml@refs/tags/v'   --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify "oci://$IMAGEM" --repo matheusteixeira-commits/themis-lgpd
```

Os pacotes do PyPI têm atestado equivalente (`gh attestation verify themis_lgpd-1.1.0-py3-none-any.whl
--repo matheusteixeira-commits/themis-lgpd`), e cada versão traz o SBOM (CycloneDX) das dependências.

## Instalação para desenvolvimento

```bash
git clone https://github.com/matheusteixeira-commits/themis-lgpd.git
cd themis-lgpd
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download pt_core_news_lg
pytest
```

Ver [CONTRIBUTING.md](../CONTRIBUTING.md).

## Verificação da instalação

```bash
themis --versao
themis perfis
echo "Eu, Maria Souza, CPF 529.982.247-25" | themis anonimizar -
```

Saída esperada do último comando:

```
Eu, [NOME], CPF [CPF]
```

Para conferir o OCR:

```bash
python -c "from themis_lgpd.formatos.ocr import ocr_disponivel; print(ocr_disponivel())"
```

## Operação sem internet

Depois de instalado, o Themis não faz nenhuma requisição de rede:

- o modelo spaCy é carregado do disco e nunca baixado automaticamente;
- os reconhecedores do Presidio que consultam listas públicas de domínios na internet não são usados;
- a interface é iniciada com a telemetria do Streamlit desativada;
- o teste `tests/test_offline.py` bloqueia o acesso à rede, recria o motor de análise e anonimiza um
  texto com nome, e-mail e URLs, confirmando que nenhuma conexão é tentada.

A única exceção é o reconhecedor GLiNER opcional (extra `ml`), que baixa o modelo do Hugging Face na
primeira execução quando é explicitamente ativado. Para uso em ambiente isolado, baixe o modelo
previamente e informe o caminho local em `reconhecedor_gliner(modelo=...)`.

Para instalar em máquina sem internet, gere os pacotes em uma máquina com acesso e copie-os:

```bash
pip download "themis-lgpd[completo]" -d pacotes/
# copie pacotes/ e o arquivo do modelo pt_core_news_lg para a máquina isolada
pip install --no-index --find-links pacotes/ "themis-lgpd[completo]"
pip install pt_core_news_lg-3.8.0-py3-none-any.whl
```

## Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `RuntimeError` mencionando `pt_core_news_lg` | Modelo de linguagem não instalado | `python -m spacy download pt_core_news_lg` |
| "Suporte a PDF requer: pip install 'themis-lgpd[arquivos]'" | Extra `arquivos` ausente | `pip install "themis-lgpd[arquivos]"` |
| Imagens recusadas por falta de OCR | Nenhum mecanismo de OCR | Instale o Tesseract com `por` ou o extra `ocr` |
| PDF recusado por exigir OCR | Páginas digitalizadas sem OCR disponível | Instale o OCR, ou use `--sem-ocr` e revise manualmente as páginas listadas |
| `themis: command not found` | Ambiente virtual não ativado | Ative o ambiente ou use `python -m themis_lgpd.cli` |
| Primeira análise lenta | Carregamento do modelo (uma vez por processo) | Reutilize o mesmo processo ou `Anonimizador` |
