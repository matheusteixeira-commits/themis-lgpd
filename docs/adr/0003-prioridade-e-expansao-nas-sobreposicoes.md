# 0003. Prioridade por tipo e expansão até o limite do token

- Estado: Aceito
- Data: 2026-11-15

## Contexto

Reconhecedores diferentes produzem trechos sobrepostos: um padrão de telefone pode casar no meio do
número de uma CNH; um nome pode conter parte de um endereço. Na versão do hackathon, a substituição
independente de cada trecho deixava fragmentos visíveis, como `CNH 0[TELEFONE]` e
`SUS 898 00[TELEFONE]`: o dado era tarjado apenas em parte.

A união pura dos trechos também é inadequada: o relatório perderia a informação de qual tipo de dado
foi tarjado e com qual base legal.

## Decisão

Na consolidação das entidades de cada texto:

1. **Expansão até o limite do token.** Toda entidade tarjada cujo início ou fim cai no meio de uma
   palavra ou número é estendida até a borda. Números ligados por `.`, `-` ou `/` são um único token.
   A extensão só ocorre se o corte cair no meio do token, para não engolir palavras vizinhas.
2. **Prioridade por tipo.** Cada tipo tem prioridade (`catalogo.TIPOS`): CPF 100, RG/CNH/PIS 95,
   documentos e contatos de 80 a 90, nome 75, endereço 70, dados sensíveis 60, localidade 30. Na
   substituição, cada caractere pertence à entidade de maior prioridade que o cobre; trechos
   remanescentes de entidades de menor prioridade são aparados para não começar nem terminar em
   pontuação.
3. **Cobertura monotônica.** A consolidação remove do relatório entidades contidas em outra de
   prioridade igual ou maior, mas nunca reduz a área tarjada.
4. Entidades do mesmo tipo que se sobrepõem ou se tocam são fundidas.

## Consequências

- Nenhum fragmento do mesmo dado fica ao lado da tarja.
- O relatório indica o tipo de maior prioridade para cada trecho tarjado.
- Em casos raros, a expansão tarja um pouco além do necessário (por exemplo, um código colado a um
  número); a decisão privilegia a proteção.

## Alternativas consideradas

- **Substituição independente de cada trecho.** Deixa fragmentos visíveis.
- **Fusão de todos os trechos sobrepostos em uma tarja genérica.** Perde o tipo e a base legal de cada
  tarja.
- **Desempate por confiança.** Um reconhecedor genérico com confiança alta prevaleceria sobre um
  documento validado por dígito verificador.
