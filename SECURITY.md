# Política de segurança

## Como relatar uma vulnerabilidade

**Não abra uma issue pública.** Use o recurso
[Report a vulnerability](https://github.com/matheusteixeira-commits/themis-lgpd/security/advisories/new)
(GitHub Security Advisories) deste repositório. A avaliação inicial é respondida em até 5 dias úteis.

Inclua no relato a versão do Themis, o formato do arquivo, os passos para reproduzir e, se possível,
um arquivo de exemplo **com dados fictícios**. Nunca envie documentos reais.

## O que é considerado vulnerabilidade

- **Vazamento:** dado tarjado que continua recuperável no arquivo gerado — texto oculto, camada de
  texto do PDF, metadados, XML de DOCX ou XLSX, atributos, caches, miniaturas, partes do pacote — ou
  arquivo entregue sem que a verificação final detecte o valor remanescente.
- Execução de código, leitura de arquivos locais ou requisição de rede a partir de um documento
  enviado.
- Injeção de HTML ou script, ou requisição a terceiros, disparada pelo conteúdo de um documento na
  interface.
- Conteúdo de documento registrado em log, exibido em mensagem de erro ou incluído em aviso ou
  relatório publicável.
- Contorno dos limites da API ou da demonstração (tamanho, taxa, concorrência, autenticação).
- Negação de serviço por arquivo construído para esgotar memória ou CPU dentro dos limites
  configurados.

Dado pessoal que simplesmente **não foi detectado** em texto comum é limitação de cobertura, não
vulnerabilidade: use o modelo de issue *Dado pessoal não tarjado*, sempre com exemplo fictício.

## Garantias de projeto

- Processamento local, sem telemetria, sem serviços externos e sem download automático de modelos.
  Os reconhecedores de e-mail e URL do Presidio, que consultam a lista pública de sufixos de domínio na
  internet, não são usados.
- Nenhum conteúdo de documento é gravado em disco ou em log; mensagens de erro e avisos não repetem o
  conteúdo; a API reduz os registros de exceção ao tipo do erro.
- Remoção efetiva do conteúdo tarjado em todos os formatos e verificação independente do arquivo
  gerado: se algum valor tarjado continuar legível, nenhum arquivo é entregue (`VazamentoDetectado`).
- Arquivos que exigem OCR não são entregues sem análise quando o OCR está indisponível ou falha
  (`FalhaOCR`).
- XML de documentos Office interpretado sem DTD, sem resolução de entidades e sem acesso à rede;
  limites de tamanho descompactado, de entradas, de páginas e de pixels.
- Dependências fixadas em `requirements/producao.txt`, auditadas por `pip-audit` no CI e atualizadas pelo
  Dependabot; ações do GitHub fixadas por hash; imagem Docker sem root, com base fixada por digest e
  verificada pelo Trivy.

A descrição completa das proteções e dos riscos residuais está em
[docs/SEGURANCA_E_PRIVACIDADE.md](docs/SEGURANCA_E_PRIVACIDADE.md).

## Versões suportadas

| Versão | Suporte |
|---|---|
| 1.x | Correções de segurança na versão mais recente |
