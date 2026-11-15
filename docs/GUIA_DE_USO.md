# Guia de uso

O Themis LGPD pode ser usado por quatro interfaces, todas com o mesmo motor:

| Interface | Indicada para | Comando |
|---|---|---|
| Interface web | Revisão humana de documentos individuais | `themis interface` |
| Linha de comando | Lotes de arquivos e automação | `themis anonimizar` |
| Biblioteca Python | Integração em sistemas Python | `from themis_lgpd import Anonimizador` |
| API HTTP | Integração com sistemas em outras linguagens | `themis api` ([API.md](API.md)) |

Antes de usar, consulte [INSTALACAO.md](INSTALACAO.md). Os perfis e tipos de dado estão descritos em
[TIPOS_DE_DADOS.md](TIPOS_DE_DADOS.md).

## Interface web

```bash
themis interface                 # http://127.0.0.1:8501
themis interface --porta 8600
```

A interface é iniciada sem telemetria, com proteção XSRF e sem exibição de detalhes de erro. Por
padrão, escuta somente em `127.0.0.1`; use `--endereco 0.0.0.0` apenas atrás de um proxy com HTTPS.

### Configuração (barra lateral)

- **Perfil:** define o que é tarjado e o que vira alerta.
- **Como substituir:** modo de saída (etiqueta, tarja, máscara, pseudônimo ou HMAC).
- **Manter nomes de agentes públicos em exercício da função:** equivale a
  `preservar_agentes_publicos`.
- **Listas de permissão e bloqueio:** termos que nunca são tarjados e termos sempre tarjados, um por
  linha.

### Texto

1. Cole o texto e acione **1 · Analisar**.
2. **2 · Revise:** o texto original é exibido com realce — vermelho para o que será tarjado, amarelo
   para alertas. Passe o cursor sobre um trecho para ver o tipo e a base legal. Na tabela, marque ou
   desmarque a coluna *Tarjar* de cada achado; em *Tarjar também*, informe trechos adicionais, um por
   linha.
3. Acione **3 · Gerar versão anonimizada** para obter o resultado, que pode ser baixado em TXT.

### Arquivo

1. Envie um arquivo PDF, DOCX, XLSX, CSV, TXT, PNG ou JPEG e acione **Anonimizar arquivo**.
2. Confira os contadores de trechos tarjados e de alertas, os avisos (conteúdo removido, convertido ou
   não analisado) e a pré-visualização da primeira página (PDF) ou da imagem.
3. Baixe o arquivo anonimizado.
4. Para corrigir excessos, desmarque na tabela de revisão os trechos que não devem ser tarjados e acione
   **Anonimizar arquivo** novamente; esses trechos passam a integrar a lista de permissão da sessão.
   Para tarjar algo a mais, use a lista *Sempre tarjar* da barra lateral.

### Relatórios

Para texto e arquivos, a interface oferece:

| Relatório | Conteúdo | Pode ser publicado |
|---|---|---|
| Relatório de tarjamento (XLSX) | Resumo, fundamentação por categoria e lista de itens com base legal, justificativa e contexto já anonimizado | Sim |
| Relatório (JSON) | O mesmo conteúdo em JSON | Sim |
| Nota de tarjamento (TXT) | Texto pronto para acompanhar a resposta ao pedido de acesso | Sim |
| Relatório interno (CSV) | Inclui os valores originais; exige confirmação | **Não**: contém dados pessoais |

O relatório interno não está disponível na demonstração pública.

### Privacidade da interface

O conteúdo é processado em memória e descartado ao fim da sessão. Nada é gravado em disco, registrado
em log ou enviado a terceiros. O conteúdo dos documentos é exibido com escape de HTML, de modo que
nenhum documento consegue executar código ou carregar recursos externos no navegador.

## Linha de comando

```
themis [--versao] <comando> [opções]
```

| Comando | Descrição |
|---|---|
| `anonimizar` | Anonimiza arquivos e pastas (PDF, DOCX, XLSX, CSV, TXT, PNG, JPEG) ou a entrada padrão (`-`) |
| `analisar` | Lista, em JSON, o que seria tarjado em um texto |
| `perfis` | Lista os perfis e os modos de saída |
| `interface` | Inicia a interface web local |
| `api` | Inicia a API HTTP local |
| `reverter` | Reverte um texto pseudonimizado com o cofre e a senha |

### `themis anonimizar`

```
themis anonimizar ENTRADA [ENTRADA ...] [opções]
```

| Opção | Descrição |
|---|---|
| `ENTRADA` | Arquivos e pastas, ou `-` para ler texto da entrada padrão (UTF-8 ou Windows-1252) e escrever o resultado na saída padrão; a entrada padrão também passa pela verificação final |
| `-o`, `--saida` | Arquivo ou pasta de saída. Com várias entradas ou com pastas, é sempre uma pasta, com a mesma árvore das entradas: `a/despacho.pdf` e `b/despacho.pdf` geram `saida/a/…` e `saida/b/…`. Padrão: `<nome>_anonimizado.<ext>` ao lado da entrada |
| `-R`, `--recursivo` | Inclui as subpastas das pastas indicadas (sem a opção, só o primeiro nível). Arquivos ocultos e saídas anteriores (`*_anonimizado.*`) são ignorados |
| `-j N`, `--trabalhos N` | Processa N arquivos em paralelo; cada processo carrega o modelo de linguagem (cerca de 1 GB de memória por processo) |
| `--manifesto ARQ.jsonl` | Manifesto de cadeia de custódia (ver abaixo) |
| `--retomar` | Pula os arquivos já concluídos, com o mesmo conteúdo e a mesma configuração, segundo o manifesto; exige `--manifesto` |
| `-r`, `--relatorio` | Gera relatório consolidado do lote, que identifica o arquivo de cada item: `.json`, `.csv`, `.xlsx`, ou `.txt`/`.md` para a nota de tarjamento |
| `--coluna-integral CABEÇALHO` | Em planilhas, tarja a coluna inteira com esse cabeçalho (repetível) |
| `--sem-ocr` | Não usa OCR. Em PDFs, as páginas que o exigiriam são listadas em aviso como não analisadas; imagens continuam exigindo OCR e são recusadas |
| `--cofre ARQ\|PASTA` | Para arquivos `.txt`, grava um cofre cifrado que permite reverter a substituição: um arquivo, para uma entrada, ou uma pasta com um `.cofre` por documento (senha em `THEMIS_SENHA_COFRE` ou solicitada no terminal; mínimo de 12 caracteres) |
| `--limite-mb N` | Tamanho máximo de arquivo, em MB (padrão: 50) |
| `--config ARQ` | Configuração do órgão (`themis.toml`, ver [CONFIGURACAO.md](CONFIGURACAO.md#configuração-do-órgão-themistoml)); padrão: variável `THEMIS_CONFIG`, se definida. As opções da linha de comando prevalecem sobre o arquivo, e as listas são somadas |
| `--perfil` | `lai` (padrão), `identificadores`, `saude`, `ouvidoria`, `educacao`, `maxima` ou um perfil do `themis.toml` |
| `--modo` | `etiqueta` (padrão), `tarja`, `mascara`, `pseudonimo` ou `hmac` (chave em `THEMIS_CHAVE_HMAC`) |
| `--permitir TERMO` | Termo que nunca é tarjado (repetível) |
| `--permitir-arquivo ARQ` | Arquivo com termos permitidos, um por linha (linhas iniciadas por `#` são ignoradas) |
| `--bloquear TERMO` | Termo sempre tarjado (repetível) |
| `--bloquear-arquivo ARQ` | Arquivo com termos a tarjar, um por linha |
| `--preservar-agentes-publicos` | Não tarja nomes acompanhados de cargo público (valide com a área jurídica) |
| `--sem-ner` | Não usa o modelo de linguagem (menor cobertura de nomes) |
| `--modelo NOME` | Modelo spaCy (padrão: `pt_core_news_lg`) |
| `--incluir-valores` | Inclui os valores originais no relatório (**contém dados pessoais**) |

Para cada arquivo, a CLI informa o destino, a quantidade de trechos tarjados e de alertas e os avisos.
A CLI se recusa a sobrescrever o arquivo de entrada. Um arquivo cujo conteúdo não corresponde à
extensão (um `.pdf` que é texto, por exemplo) é recusado.

Códigos de saída — o do lote é o de maior gravidade entre os arquivos:

| Código | Significado |
|---|---|
| 0 | Todos os arquivos foram processados |
| 1 | Algum arquivo foi recusado (formato, limites, OCR indisponível ou com falha) ou reprovado na verificação final, ou houve erro de uso (configuração inválida, entrada inexistente) |
| 2 | Erro interno em algum arquivo; somente o tipo do erro é exibido |
| 130 | Interrompido pelo usuário (Ctrl+C); os arquivos concluídos ficam registrados no manifesto |

Os demais arquivos do lote continuam sendo processados quando um deles falha.

**Manifesto de cadeia de custódia.** Com `--manifesto custodia.jsonl`, cada arquivo concluído gera uma
linha JSON, gravada no disco assim que o arquivo termina, com: caminho relativo, SHA-256 e tamanho da
entrada e da saída, formato, perfil, modo, versão do Themis, identificador da configuração (resumo de
tudo o que influi no resultado, inclusive o `themis.toml`), quantidade de tarjas por tipo, alertas,
avisos, situação (`ok`, `rejeitado`, `erro`), início e duração. O manifesto não contém nenhum trecho
dos documentos nem os termos das listas de permissão e de bloqueio, e permite comprovar depois qual
versão de qual arquivo foi publicada, com que configuração. Um lote interrompido continua de onde
parou com `--retomar`: arquivos alterados, ou processados com outra configuração, são refeitos.

Exemplos:

```bash
themis anonimizar resposta.pdf
themis anonimizar *.docx -o saida/ -r relatorio.xlsx
themis anonimizar processos/ -R -o publicacao/ --manifesto custodia.jsonl -j 4 -r relatorio.xlsx
themis anonimizar processos/ -R -o publicacao/ --manifesto custodia.jsonl --retomar
themis anonimizar manifestacoes/ -o publicacao/ --config ouvidoria.toml
themis anonimizar planilha.xlsx --coluna-integral "Nome do servidor" --coluna-integral "Lotação"
themis anonimizar pedido.txt --perfil maxima --modo pseudonimo
themis anonimizar despacho.pdf --permitir-arquivo instituicoes.txt --bloquear "Operação Aurora"
echo "Eu, Maria Souza, CPF 529.982.247-25" | themis anonimizar -
```

### `themis analisar`

```
themis analisar ENTRADA [opções do motor]
```

Lê um arquivo de texto UTF-8 (ou `-` para a entrada padrão) e imprime as entidades em JSON, com tipo,
posição, ação, confiança, camada, origem, base legal e motivo. Aceita as mesmas opções de motor de
`anonimizar` (`--perfil`, `--modo`, `--permitir`, `--bloquear`, `--preservar-agentes-publicos`,
`--sem-ner`, `--modelo`) e `--incluir-valores` para incluir os trechos originais.

```bash
themis analisar pedido.txt --perfil identificadores
```

### `themis perfis`

Lista os perfis, com título e descrição, e os modos de saída.

### `themis interface`

| Opção | Padrão | Descrição |
|---|---|---|
| `--porta` | 8501 | Porta |
| `--endereco` | 127.0.0.1 | Endereço; `0.0.0.0` somente atrás de proxy com HTTPS |
| `--config` | `THEMIS_CONFIG` | Configuração do órgão; perfis próprios aparecem na barra lateral |

### `themis api`

| Opção | Padrão | Descrição |
|---|---|---|
| `--porta` | 8000 | Porta |
| `--endereco` | 127.0.0.1 | Endereço |
| `--config` | `THEMIS_CONFIG` | Configuração do órgão; um arquivo inválido impede o início do serviço |
| `--processos N` | 1 | Processos de análise em paralelo, num único processo HTTP (as tarefas assíncronas continuam consultáveis em qualquer requisição); cerca de 1 GB de memória por processo |

### `themis reverter`

```
themis reverter TEXTO_ANONIMIZADO COFRE
```

Reconstitui o texto original a partir do texto anonimizado e do cofre criado com `--cofre`. A senha é
lida de `THEMIS_SENHA_COFRE` ou solicitada no terminal. A reversão falha se o texto tiver sido editado
após a anonimização ou se a senha estiver incorreta.

```bash
THEMIS_SENHA_COFRE="senha com pelo menos 12 caracteres" \
  themis anonimizar pedido.txt --modo pseudonimo --cofre pedido.cofre
themis reverter pedido_anonimizado.txt pedido.cofre
```

O cofre é pseudonimização reversível: guarde-o, e a senha, separados do documento publicado.

## Biblioteca Python

### Texto

```python
from themis_lgpd import Anonimizador

anon = Anonimizador(perfil="lai", modo="etiqueta")
r = anon.anonimizar("Eu, Maria Aparecida Souza, CPF 529.982.247-25, moro na QNM 12 Conjunto B Casa 4.")
print(r.texto)
# Eu, [NOME], CPF [CPF], moro na [ENDEREÇO].

for e in r.tarjadas:
    print(e.tipo, e.inicio, e.fim, e.base_legal)
for e in r.alertas:
    print("revisar:", e.rotulo, e.motivo)
```

Para um único texto, há o atalho `themis_lgpd.anonimizar(texto, perfil="lai", modo="etiqueta")`. Para
vários textos, reutilize o mesmo `Anonimizador`: o modelo de linguagem é carregado uma vez por
processo, mas a configuração da instância é refeita a cada criação.

### Parâmetros do `Anonimizador`

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `perfil` | `"lai"` | Nome do perfil ou instância de `Perfil` |
| `modo` | `"etiqueta"` | Modo de substituição |
| `permitir` | `()` | Termos que nunca são tarjados |
| `bloquear` | `()` | Termos sempre tarjados |
| `usar_ner` | `True` | Usa o modelo de linguagem para nomes |
| `modelo_spacy` | `"pt_core_news_lg"` | Pacote do modelo spaCy |
| `preservar_agentes_publicos` | `False` | Mantém nomes acompanhados de cargo público |
| `chave_hmac` | `None` | Chave do modo `hmac`; sem chave, uma chave aleatória é gerada por instância |
| `reconhecedores_extras` | `()` | `EntityRecognizer` do Presidio ou objetos com `detectar(texto)` |

### Modos de saída

| Modo | Exemplo de saída para `CPF 529.982.247-25` |
|---|---|
| `etiqueta` | `CPF [CPF]` |
| `tarja` | `CPF ████████` |
| `mascara` | `CPF ***.***.***-**` |
| `pseudonimo` | `CPF [CPF 1]`; nomes viram `Pessoa 1`, `Pessoa 2`… |
| `hmac` | `CPF [CPF:e355434cc4]` (depende da chave) |

No modo `pseudonimo`, a mesma pessoa recebe o mesmo pseudônimo em todo o lote, inclusive quando citada
de forma parcial:

```python
Anonimizador(modo="pseudonimo").anonimizar(
    "Maria Souza encaminhou o pedido. A Sra. Souza e João Pereira assinaram."
).texto
# 'Pessoa 1 encaminhou o pedido. A Sra. Pessoa 1 e Pessoa 2 assinaram.'
```

### Lotes e documentos com várias partes

`anonimizar_lote(textos)` processa vários textos de uma vez. Com `mesmo_documento=True`, os textos são
tratados como partes de um único documento (páginas, parágrafos, células): um valor tarjado em uma parte
é tarjado em todas.

```python
partes = ["Requerente: Ana Beatriz Fagundes", "Assinado: Fagundes"]
[r.texto for r in anon.anonimizar_lote(partes, mesmo_documento=True)]
# ['Requerente: [NOME]', 'Assinado: [NOME]']
[r.texto for r in anon.anonimizar_lote(partes)]
# ['Requerente: [NOME]', 'Assinado: Fagundes']
```

O parâmetro `consistente` (padrão `True`) mantém os mesmos pseudônimos em todo o lote.

### Revisão programática

`analisar` devolve as entidades sem alterar o texto. A ação de cada uma pode ser alterada antes da
anonimização:

```python
texto = "Fulano da Silva, CPF 529.982.247-25"
entidades = anon.analisar(texto)
for e in entidades:
    if e.tipo == "NOME":
        e.acao = "alertar"          # manter visível, mas registrar no relatório
anon.anonimizar(texto, entidades).texto
# 'Fulano da Silva, CPF [CPF]'
```

### Arquivos

```python
from pathlib import Path
from themis_lgpd import Anonimizador
from themis_lgpd.formatos import ArquivoInvalido, FalhaOCR, VazamentoDetectado, anonimizar_arquivo

entrada = Path("despacho.pdf")
try:
    resultado = anonimizar_arquivo(entrada.read_bytes(), entrada.name, Anonimizador())
except (ArquivoInvalido, FalhaOCR, VazamentoDetectado) as erro:
    print("Arquivo não gerado:", erro)
else:
    Path(resultado.nome).write_bytes(resultado.dados)
    for aviso in resultado.avisos:
        print("aviso:", aviso)
```

| Parâmetro de `anonimizar_arquivo` | Padrão | Descrição |
|---|---|---|
| `dados` | obrigatório | Conteúdo do arquivo |
| `nome` | `""` | Nome original (distingue CSV de texto e nomeia a saída) |
| `anonimizador` | perfil `lai` | `Anonimizador` configurado |
| `limite_bytes` | 50 MB | Tamanho máximo |
| `limite_paginas` | 500 | Páginas de PDF |
| `ocr` | `True` | Permite OCR |
| `colunas` | `None` | Planilhas: restringe o processamento a estas colunas (pelo cabeçalho) |
| `colunas_integrais` | `None` | Planilhas: colunas a tarjar por inteiro |
| `verificar` | `True` | Verificação final do arquivo gerado; desligar apenas em medições de desempenho |

Exceções:

| Exceção | Situação |
|---|---|
| `ArquivoInvalido` | Arquivo vazio, corrompido, protegido por senha, de formato não suportado ou acima dos limites |
| `FalhaOCR` | O arquivo exige OCR e nenhum mecanismo está disponível, ou o OCR falhou |
| `VazamentoDetectado` | A verificação final encontrou valor tarjado no arquivo gerado; nenhum arquivo é devolvido |

`ResultadoArquivo` contém `dados`, `formato`, `nome`, `mime`, `resultados` (um `Resultado` por trecho
de texto), `entidades` (todas as entidades) e `avisos`.

### Relatórios

```python
from themis_lgpd import relatorio

resultados = resultado.resultados                      # ou uma lista de Resultado
Path("relatorio.xlsx").write_bytes(relatorio.para_xlsx(resultados))
Path("relatorio.json").write_text(relatorio.para_json(resultados), encoding="utf-8")
Path("nota.txt").write_text(relatorio.nota_de_tarjamento(resultados, "o despacho"), encoding="utf-8")
```

`para_json`, `para_csv` e `para_xlsx` aceitam `incluir_valores=True` para o relatório interno, que
contém dados pessoais.

### Cofre de reversão

```python
from themis_lgpd import Anonimizador
from themis_lgpd.cofre import criar_cofre, reverter

r = Anonimizador(modo="pseudonimo").anonimizar("Maria Souza, CPF 529.982.247-25")
cofre = criar_cofre(r, "senha com pelo menos 12 caracteres")     # bytes; guarde separado
reverter(r.texto, cofre, "senha com pelo menos 12 caracteres")
# 'Maria Souza, CPF 529.982.247-25'
```

O cofre guarda, cifrado com a senha (scrypt e Fernet), o mapa entre cada substituto e o valor original.

### Serialização

`Resultado.para_dict()` e `Entidade.para_dict()` produzem dicionários sem dados pessoais. Os parâmetros
`incluir_valores` e `incluir_original` acrescentam os valores e o texto original e devem ser usados
apenas em contextos internos.

## Boas práticas de revisão

1. **Escolha o perfil pela finalidade.** `lai` para publicação de respostas e documentos; `maxima`
   quando a legibilidade importa menos que a proteção; `identificadores` para bases de dados e
   pesquisa.
2. **Leia todos os avisos.** Eles indicam conteúdo que não foi analisado (imagens, páginas sem OCR) ou
   que foi removido (anexos, comentários, objetos incorporados).
3. **Revise os alertas.** Termos sensíveis sem vínculo claro, localidades e quase-identificadores
   permanecem no texto e dependem de decisão humana.
4. **Confira imagens e assinaturas.** Fotos, carimbos, assinaturas digitalizadas e manuscritos não são
   detectados.
5. **Avalie quase-identificadores em conjunto.** Cargo, lotação, datas e circunstâncias podem
   identificar a pessoa mesmo sem nome.
6. **Use as listas.** A lista de permissão evita tarjas indevidas recorrentes (nomes de unidades,
   programas públicos); a de bloqueio garante a tarja de termos específicos do caso.
7. **Publique o relatório de tarjamento.** A restrição de acesso deve ser motivada (Enunciado CGU
   nº 4/2022); o relatório e a nota de tarjamento trazem a base legal de cada tarja.
8. **Nunca publique o relatório interno**, o cofre ou a chave HMAC.
