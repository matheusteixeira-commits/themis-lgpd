# Themis LGPD — imagem para uso local, servidor do órgão ou demonstração pública (atrás do proxy em deploy/).
# Roda 100% offline depois de construída: o modelo de linguagem e o OCR vêm dentro da imagem.
FROM python:3.11-slim-bookworm@sha256:a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# OCR em português pelo Tesseract (Apache-2.0). O RapidOCR, alternativa para quem não pode instalar o
# Tesseract, não entra na imagem: o ONNX Runtime e os modelos somariam centenas de megabytes sem ganho.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements/producao.txt /tmp/producao.txt
RUN grep -vE '^(rapidocr|onnxruntime)==' /tmp/producao.txt > /tmp/imagem.txt \
 && pip install -r /tmp/imagem.txt \
 && pip install "pt_core_news_lg @ https://github.com/explosion/spacy-models/releases/download/pt_core_news_lg-3.8.0/pt_core_news_lg-3.8.0-py3-none-any.whl#sha256=2561c9a72a938d37141e9694e1a36d25061a44ce7e4f3bad2d3fa3bb836191af"

COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src
RUN pip install --no-deps . && rm -rf /app/src /tmp/producao.txt /tmp/imagem.txt

# Usuário sem privilégios; o sistema de arquivos pode (e deve) ser montado como somente leitura.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin themis
USER 10001

EXPOSE 8501 8000
# Vale para a interface (porta 8501) e para a API (porta 8000): "themis saude" consulta as duas.
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 CMD ["themis", "saude"]

# Interface web. Para a API: docker run ... themis-lgpd api --endereco 0.0.0.0
ENTRYPOINT ["themis"]
CMD ["interface", "--endereco", "0.0.0.0", "--porta", "8501"]
