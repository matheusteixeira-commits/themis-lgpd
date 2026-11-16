# Conjunto de referência independente — diretrizes de anotação

Conjunto de documentos fictícios, anotados de forma exaustiva, usado **somente para avaliação**:
nenhuma regra, lista ou modelo pode ser ajustado a partir dele. Mede o que o esic-ner não mede —
gêneros documentais variados (ofícios, despachos, portarias, atas, laudos, manifestações de
ouvidoria, mensagens), todas as regiões do país e a **precisão real** (o que é tarjado sem ser dado
pessoal), já que todo dado pessoal do texto está anotado.

## Processo

1. **Redação:** cada lote é escrito por um redator, que registra os dados pessoais que inseriu.
2. **Anotação cega:** um anotador que não viu a anotação do redator anota o mesmo texto.
3. **Adjudicação:** um terceiro compara as duas anotações (`ferramentas.py concordancia`), registra a
   concordância antes da adjudicação e decide cada divergência segundo estas diretrizes.
4. **Congelamento:** o arquivo final recebe resumo SHA-256 registrado em `CONGELAMENTO.json`; qualquer
   alteração posterior invalida as comparações.

Todos os dados são fictícios. Números de documentos têm dígitos verificadores válidos (gerados por
programa) para que validadores não os descartem; nomes, endereços e contatos são inventados.

## Formato (`*.jsonl`, um documento por linha)

```json
{"id": "A-001", "genero": "oficio", "uf": "PE", "texto": "…",
 "entidades": [{"tipo": "NOME_PESSOA", "valor": "Maria Aparecida Souza"}],
 "publicos": ["Secretaria de Estado da Saúde", "Lei nº 12.527/2011"]}
```

* `valor` é copiado **exatamente** do texto; toda ocorrência do valor (como palavra inteira) é
  considerada anotada. Se o mesmo trecho aparecer uma vez como dado pessoal e outra como público,
  reescreva o texto para evitar a ambiguidade.
* `publicos` lista trechos que **devem permanecer legíveis** numa resposta pública: nomes de órgãos,
  programas, normas, cargos sem nome, municípios e UFs em contexto institucional, datas e números de
  atos oficiais. Servem para medir a tarja indevida.

## Rótulos

| Rótulo | O que anotar | Exemplos |
|---|---|---|
| `NOME_PESSOA` | Nome de pessoa natural, inclusive de servidores e agentes públicos, parcial ou completo, em qualquer caixa | "Maria Aparecida Souza", "SOUZA, M. A.", "o servidor Paulo" (anotar "Paulo") |
| `DOC_PESSOAL` | CPF, RG, CNH, título de eleitor, PIS/NIS, CNS, passaporte, certidões, NB do INSS, CTPS | "CPF 529.982.247-25" → anotar "529.982.247-25" |
| `CONTATO` | Telefone, celular, e-mail pessoal | "(81) 99876-5432", "joao.silva@gmail.com" |
| `ENDERECO` | Logradouro com número e complemento, CEP, endereço rural ou de residência | "Rua das Acácias, 120, apto 302", "CEP 50030-230" |
| `DATA_NASC` | Data de nascimento e idade exata de pessoa identificável | "nascida em 12/03/1987" → "12/03/1987" |
| `DADO_SAUDE` | Doença, diagnóstico, CID, deficiência, medicamento, tratamento, exame ou resultado ligado a pessoa | "portador de esclerose múltipla", "CID F32.1", "faz uso de fluoxetina" |
| `DADO_SENSIVEL` | Origem racial ou étnica, religião, opinião política, filiação sindical, orientação sexual, vida sexual, biometria ligadas a pessoa | "filiado ao Sindicato dos …", "evangélico" |
| `DADO_FINANCEIRO` | Conta, agência, cartão, chave PIX, renda, dívida, salário de pessoa identificável | "agência 1234-5, conta 98765-0" |
| `ID_PROCESSUAL` | Número de processo, protocolo, inquérito, boletim de ocorrência ou manifestação ligado a pessoa | "processo SEI 00410.002123/2024-11" |
| `DOC_PROFISSIONAL` | Registro em conselho (OAB, CRM, CREA…), matrícula funcional, SIAPE, MASP | "OAB/PE 12.345", "matrícula 1.234.567-8" |
| `ID_VEICULO` | Placa, RENAVAM, chassi | "placa RTX-4B21" |
| `QUASI_IDENTIFICADOR` | Combinação que identifica a pessoa sem nome: cargo único, lotação específica, característica rara | "a única professora surda da Escola Estadual X" |

Regras de extensão:

* Anote o **valor** sem a palavra-chave ("529.982.247-25", não "CPF 529.982.247-25"); em endereços,
  do logradouro ao complemento; em saúde, a expressão que descreve a condição ("transtorno bipolar",
  "tratamento oncológico").
* Dado de pessoa jurídica (CNPJ, razão social, endereço de órgão público) **não** é dado pessoal:
  vai para `publicos` quando relevante.
* Nome de pessoa dentro de nome de instituição, logradouro público ou programa ("Hospital Regional Dr.
  Luiz Gonzaga", "Escola Estadual Maria Quitéria") é público; dentro de endereço residencial, faz
  parte do `ENDERECO`.
* Na dúvida entre dois rótulos de dado pessoal, escolha o mais específico; na dúvida entre pessoal e
  público, prefira pessoal e registre a dúvida na adjudicação.
