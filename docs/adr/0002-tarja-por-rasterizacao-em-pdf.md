# 0002. Tarja por rasterização das páginas de PDF

- Estado: Aceito
- Data: 2026-11-15

## Contexto

Em PDF, desenhar um retângulo preto sobre o texto não o remove: o texto continua no fluxo de conteúdo
e pode ser selecionado, copiado ou extraído. Falhas desse tipo expõem dados de documentos publicados
com frequência. Remover o texto diretamente do fluxo de conteúdo exige reescrever operadores de texto,
lidar com codificações de fontes, kerning, texto em formulários XObject e caracteres que compartilham
glifos — e qualquer erro deixa fragmentos recuperáveis.

As bibliotecas que oferecem remoção de texto no fluxo de conteúdo com maturidade têm licença AGPL
(PyMuPDF), incompatível com a licença MIT do projeto.

## Decisão

Páginas que contêm ao menos uma tarja são rasterizadas:

1. a página é renderizada a 200 dpi com o pypdfium2 (PDFium);
2. as tarjas são aplicadas sobre os pixels (e o rótulo, quando cabe);
3. uma página nova é gerada com a imagem e uma camada de texto invisível (modo de renderização 3)
   recriada apenas com as palavras não tarjadas, para preservar busca, seleção e acessibilidade;
4. páginas sem tarja são copiadas sem alteração;
5. o documento é reescrito por inteiro com o pikepdf e saneado (metadados, anotações, anexos,
   JavaScript, marcadores, estrutura de tags, dados de assinatura).

Antes da extração, campos de formulário e anotações visíveis são incorporados ao conteúdo da página,
para que sejam analisados e, se for o caso, tarjados na imagem.

## Consequências

- O conteúdo tarjado deixa de existir no arquivo; não há texto, glifo ou objeto a recuperar.
- As páginas com tarja ficam maiores e perdem a qualidade vetorial; o texto girado dessas páginas não
  é recriado na camada invisível.
- A verificação final relê o arquivo com dois extratores independentes
  ([ADR 0006](0006-verificacao-final-e-falha-fechada.md)).
- Todas as bibliotecas usadas (pdfplumber, pypdfium2, Pillow, ReportLab, pikepdf) têm licença
  compatível com MIT.

## Alternativas consideradas

- **Retângulo sobre o texto.** Descartado: não remove o conteúdo.
- **Remoção de operadores de texto no fluxo de conteúdo.** Complexa e sujeita a fragmentos
  remanescentes; as implementações maduras têm licença AGPL.
- **Rasterizar o documento inteiro.** Desnecessário para páginas sem tarja e prejudica a qualidade e a
  acessibilidade de todo o documento.
- **Conversão para imagem sem camada de texto.** Perde busca e acessibilidade, requisitos de
  publicação em transparência.
