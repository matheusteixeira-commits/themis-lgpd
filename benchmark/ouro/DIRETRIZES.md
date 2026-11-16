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

## Convenções de extensão

Fixadas na adjudicação dos lotes A e B a partir do que os anotadores já faziam nas entidades de
consenso; valem para todo conjunto anotado segundo estas diretrizes.

1. **Palavras-chave e qualificadores ficam fora** do valor: "CPF", "nascida em", "peso de", "vaga
   reservada a", "mensais", "renda estimada de", "dívida de". Medidas com unidade entram sem a
   palavra-chave ("38 semanas", "150 x 100 mmHg"); escalas clínicas mantêm o nome ("Glasgow 13").
2. **Nome de pessoa** entra sem pronome de tratamento ("dona Joana" → "Joana"). Iniciais e nomes
   parciais de pessoa identificável também são `NOME_PESSOA`. Quando o mesmo nome aparece em duas
   grafias (caixa alta e normal), cada grafia é uma entrada; quebra de linha dentro do valor é
   copiada como está no texto.
3. **Saúde:** uma condição com seus atributos (medida, lateralidade, características, data do
   diagnóstico, estado do tratamento) ou uma cadeia causal ("X decorrente de Y") é uma só expressão;
   achados, sintomas, medicamentos, terapias e exames coordenados são entradas separadas, salvo
   quando um núcleo comum governa a lista ("testagem para HIV, sífilis e hepatites"). Exame e
   resultado contíguos formam uma expressão; exame realizado na pessoa identificada entra mesmo
   sem resultado. Posologia contígua (dose, frequência, duração) integra o medicamento ou a terapia.
   Verbo de ligação ou de uso fica fora ("é diabética" → "diabética"), salvo quando é o próprio
   conteúdo ("não deambula"). Licença que enuncia motivo de saúde é `DADO_SAUDE`; a simples duração
   de um afastamento não é.
4. **Endereço** vai do logradouro ao complemento; conjunto habitacional, quadra, lote e casa contam
   como complemento; localidade rural ou aldeia que integra o endereço entra. Bairro, município, UF,
   tipo de área ("zona rural") e território ficam fora.
5. **Quase-identificador:** o identificador mais o atributo revelado, sem artigo inicial.
6. **Dado sensível:** a expressão inteira ("indígena da etnia X", "membro da Igreja Y"); sigla de
   sindicato ou partido em aposição entra, porque revelaria o dado.
7. **Valores monetários recebidos ou devidos por pessoa natural** (salário, benefício, bolsa,
   aluguel, cachê, renda, dívida, prejuízo alegado) são `DADO_FINANCEIRO`. Valores agregados ou de
   pessoa jurídica (contratos com empresas, verbas de órgão, totais de programas) são públicos.
   Agência e conta são entradas separadas, sem as palavras "agência" e "conta"; o nome do banco fica
   fora.
8. **Número de procedimento, relatório ou registro sobre pessoa ou família** (relatório social,
   laudo, prontuário, ficha de matrícula, sindicância, auto de infração) é `ID_PROCESSUAL`; atas,
   notas técnicas e comunicados sobre uma coletividade são públicos.
9. **Trechos públicos** são listados por unidade ("Caruaru" e "18 de agosto de 2025", não "Caruaru,
   18 de agosto de 2025"); compostos só entram quando têm partes que não estão na lista.

## Conjunto congelado

| Arquivo | Documentos | Entidades | Trechos públicos | Concordância antes da adjudicação (F1) |
|---|---:|---:|---:|---:|
| `ouro_a.jsonl` | 60 | 523 | 836 | 0,956 |
| `ouro_b.jsonl` | 60 | 783 | 565 | 0,861 |

Os dois lotes cobrem as 27 UFs e doze gêneros documentais; o lote B concentra laudos, prontuários
e documentos de saúde. Resumos SHA-256 em `CONGELAMENTO.json`. A pasta `processo/` guarda, por lote,
as anotações independentes do redator e da anotação cega e o relatório de adjudicação, de modo que a
concordância pode ser recalculada (`ferramentas.py concordancia`). Toda divergência foi de extensão
ou de inclusão; nenhuma foi só de rótulo.
