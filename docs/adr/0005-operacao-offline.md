# 0005. Operação sem acesso à internet

- Estado: Aceito
- Data: 2026-11-15

## Contexto

Os documentos processados contêm dados pessoais, muitas vezes sensíveis, sob responsabilidade de
órgãos públicos. Enviar esse conteúdo a serviços externos, ou mesmo permitir que a ferramenta faça
requisições de rede durante o processamento, cria risco de vazamento, exige avaliação de operadores
de dados e impede o uso em redes isoladas.

Componentes comuns fazem requisições de rede sem que isso seja evidente: o Streamlit envia
estatísticas de uso por padrão; os reconhecedores de e-mail e URL do Presidio usam a biblioteca
tldextract, que consulta a lista pública de sufixos de domínio; o spaCy pode baixar modelos sob
demanda.

## Decisão

Depois de instalado, o Themis não faz nenhuma requisição de rede:

- o modelo spaCy é carregado do disco e nunca baixado automaticamente; a ausência do modelo gera erro
  com a instrução de instalação;
- os reconhecedores de e-mail e URL do Presidio não são registrados; o Themis tem reconhecedores
  próprios para esses tipos, sem consulta externa;
- a interface é iniciada com `gatherUsageStats=false` e sem recursos externos (fontes, imagens,
  scripts);
- o OCR é local (Tesseract ou RapidOCR);
- a imagem Docker inclui o modelo de linguagem e o Tesseract;
- o teste `tests/test_offline.py` bloqueia o acesso à rede e confirma que nenhuma conexão é tentada
  durante a carga do motor e a anonimização.

O reconhecedor GLiNER é a única exceção: opcional, ativado explicitamente e dependente do download do
modelo na primeira execução.

## Consequências

- O Themis pode ser usado em redes isoladas e sem avaliação de terceiros no tratamento de dados.
- A instalação exige um passo explícito para o modelo de linguagem.
- A detecção de domínios de e-mail e URL não usa a lista pública de sufixos; o reconhecimento é feito
  por padrões próprios.

## Alternativas consideradas

- **Serviços de nuvem de detecção de dados pessoais.** Descartados pelo envio de conteúdo a terceiros
  e por cobertura limitada de documentos brasileiros.
- **Download automático do modelo na primeira execução.** Conveniente, mas abre uma conexão de rede
  implícita e falha em redes isoladas.
- **Lista de sufixos de domínio embutida.** Possível evolução, sem necessidade atual.
