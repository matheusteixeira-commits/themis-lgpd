# Lote F — revisão independente da anotação

Tema: expediente administrativo e documentos públicos. 50 documentos, 27 UFs.

- Anotação do redator: `anotacao_redator.jsonl`, com 332 entradas pessoais e 1.028 trechos públicos.
- Anotação final: `lote_F.jsonl`, com 331 entradas pessoais e 1.032 trechos públicos.
- Validação (`ferramentas.py validar lote_F.jsonl`): **sem problemas**.
- SHA-256 de `lote_F.jsonl` na data da revisão: `ca0810a76f1102eaea8ec008dca37fdeebf35981f13ec252d37725ecaba208e5`.

## Método

1. Leitura integral de `DIRETRIZES.md`, inclusive das "Convenções de extensão" 1 a 9.
2. Leitura de cada texto do começo ao fim, a partir de `textos.jsonl`, com levantamento próprio dos dados pessoais antes de abrir a anotação do redator.
3. Comparação item a item com `anotacao_redator.jsonl`, documento por documento.
4. Verificações automáticas sobre a anotação final:
   - ocorrências múltiplas de cada valor anotado, conferidas no contexto;
   - sobreposição, por posição no texto, entre trecho público e dado pessoal: nenhuma;
   - públicos compostos de outras unidades já listadas: nenhum restante;
   - entradas duplicadas: nenhuma;
   - sequências em maiúscula inicial e números do texto que não estão cobertos por nenhuma anotação: conferidos um a um, sem nome ou documento pessoal omitido.

Os textos não foram alterados: o campo `texto` de `lote_F.jsonl` é idêntico ao de `textos.jsonl`. Não consultei a pasta `geracao/`, outros lotes, o conjunto congelado nem o código do sistema, e não executei nenhum anonimizador.

## Concordância entre o redator e a anotação final

Medida com `ferramentas.py concordancia anotacao_redator.jsonl lote_F.jsonl`:

| Medida | Valor |
|---|---:|
| Documentos | 50 |
| Documentos com divergência | 9 |
| F1 por rótulo | 0,9834 |
| F1 por valor | 0,9834 |

As 663 entradas somadas nas duas anotações (332 + 331) incluem 326 em comum. Há 6 entradas só no redator e 5 só na anotação final.

- Seis documentos divergem em entidades: F-002, F-005, F-022, F-029, F-042 e F-048.
- Três divergem apenas em públicos: F-023, F-030 e F-041.

O F1 por rótulo é igual ao F1 por valor, porque nenhuma divergência foi só de rótulo. Todas são de extensão ou de inclusão.

## Alterações

### Por tipo

| Tipo | Qtd. | Documentos |
|---|---:|---|
| Entrada incluída | 2 | F-005, F-029 |
| Entrada removida | 3 | F-042 (passou a público); F-002 e F-022 (absorvidas em fusão) |
| Extensão corrigida | 3 | F-002, F-022, F-048 |
| Rótulo corrigido | 0 | — |
| Público incluído | 6 | F-002, F-023 (3), F-041, F-042 |
| Público removido | 2 | F-002, F-030 |

### Por rótulo

| Rótulo | Redator | Incl. | Rem. | Ext. | Final |
|---|---:|---:|---:|---:|---:|
| NOME_PESSOA | 151 | 0 | 0 | 0 | 151 |
| DOC_PROFISSIONAL | 46 | 0 | 0 | 0 | 46 |
| ID_PROCESSUAL | 40 | 0 | 1 | 0 | 39 |
| DOC_PESSOAL | 36 | 0 | 0 | 0 | 36 |
| DADO_FINANCEIRO | 26 | 0 | 1 | 1 | 25 |
| CONTATO | 10 | 0 | 0 | 0 | 10 |
| DADO_SAUDE | 8 | 2 | 1 | 1 | 9 |
| ENDERECO | 6 | 0 | 0 | 0 | 6 |
| DATA_NASC | 4 | 0 | 0 | 0 | 4 |
| ID_VEICULO | 3 | 0 | 0 | 0 | 3 |
| DADO_SENSIVEL | 1 | 0 | 0 | 0 | 1 |
| QUASI_IDENTIFICADOR | 1 | 0 | 0 | 1 | 1 |
| **Total** | **332** | **2** | **3** | **3** | **331** |

### Detalhe

- **F-002, extensão de DADO_FINANCEIRO.** O redator anotou o valor em algarismos e o valor por extenso como duas entradas. A anotação final usa uma só: "R$ 18.500,00 (dezoito mil e quinhentos reais)". O extenso entre parênteses repete o próprio valor: não é palavra-chave nem qualificador (convenção 1). A fusão também alinha o lote à idade de F-027, que o redator já anotou como uma expressão única ("61 (sessenta e um) anos").
- **F-002, público.** "art. 74, inciso II, da Lei nº 14.133/2021" foi trocado pela unidade "Lei nº 14.133/2021" (convenção 9).
- **F-005, DADO_SAUDE incluído.** A ementa cita o diagnóstico do dependente da interessada em caixa alta. Essa grafia não estava coberta pela entrada em minúsculas do relatório, e cada grafia é uma entrada. A expressão "Política Nacional de Proteção dos Direitos da Pessoa com Transtorno do Espectro Autista", em caixa mista, segue pública e não coincide com o valor anotado.
- **F-022, extensão de QUASI_IDENTIFICADOR.** As duas entradas do redator (a função única e a licença de saúde) viraram uma só: "unico vigia noturno da unidade, em licenca para tratamento de saude". A convenção 5 manda anotar "o identificador mais o atributo revelado, sem artigo inicial", e o exemplo das diretrizes ("única professora surda…") põe o dado de saúde dentro do quase-identificador. A entrada DADO_SAUDE separada foi absorvida.
- **F-029, DADO_SAUDE incluído.** A internação em unidade coronariana do pai do recorrente é tratamento ligado a pessoa identificada. Pela convenção 3, terapias coordenadas com o diagnóstico entram como entradas separadas.
- **F-042, ID_PROCESSUAL passou a público.** O número do processo de Reurb-S se refere ao núcleo urbano informal, e não ao requerente nem à sua família. Pela convenção 8, procedimento sobre uma coletividade é público. O número do pedido de acesso, que é do requerente, continua ID_PROCESSUAL.
- **F-048, extensão de DADO_SAUDE.** O valor passou a "carbamazepina de uso contínuo": pela convenção 3, a posologia contígua (frequência ou duração) integra o medicamento.
- **F-030, público removido.** "Diretora da Superintendência Regional de Ensino de Teófilo Otoni" é composto, e as duas partes já estão listadas como unidades (convenção 9).
- **F-023, públicos incluídos.** "Língua Wapichana", "Língua Macuxi" e "Língua Taurepang" são componentes curriculares. Entraram como armadilha: aparecem ao lado de nomes de candidatos com o mesmo etnônimo, sem sobreposição com os nomes anotados.
- **F-041, público incluído.** "Tema 531" é uma tese de tribunal superior.

## Regras aplicadas

- **Nomes.** Entram sem pronome de tratamento e sem cargo. Nomes parciais e iniciais de pessoa identificável são entradas próprias (as iniciais dos filhos em F-005 e F-039). Cada grafia é uma entrada, e a quebra de linha dentro do nome é copiada como está (F-013, F-050). Nome dentro de instituição, programa, lei, prêmio, logradouro público ou embarcação é público.
- **Documentos.** Entram sem a palavra-chave. CPF mascarado em qualquer padrão é DOC_PESSOAL. O RG entra sem o órgão emissor. O registro RENACH (F-036) é DOC_PESSOAL, como identificador do condutor e rótulo mais específico.
- **Registros profissionais.** Conselho e UF adjacentes integram o valor ("OAB/BA …", "CREA-GO …/D", "CRC-MG …", "CAU A…"). De matrícula, SIAPE e MASP entra só o número.
- **Valores (convenção 7).** Valor recebido ou devido por pessoa natural é DADO_FINANCEIRO: cachê, honorários, benefício, abono, ajuda de custo, diárias pagas, auxílio de pesquisa, renda familiar e débito de ISS. Agência e conta são entradas separadas, e o nome do banco fica fora. Contratos com empresas, glosas a empresas, totais de programas, valores unitários de prêmio por categoria e valores de diária fixados em decreto são públicos.
- **Procedimentos (convenção 8).** Processo, protocolo, recurso, auto de infração, sindicância, laudo, certidão ou inscrição sobre uma pessoa é ID_PROCESSUAL. Isso inclui os processos de contratação ou outorga a pessoa natural (F-002, F-021, F-028, F-035). Processos de contratação de empresas, certidão de pessoa jurídica (F-040) e procedimento coletivo (Reurb-S em F-042) são públicos.
- **Endereços (convenção 4).** O valor vai do logradouro ao complemento, com quadra, lote e casa. A localidade rural entra ("Sítio … , s/n"). Bairro, setor, comunidade urbana e município ficam fora. Endereço de órgão público ou de empresa é público. O endereço profissional de pessoa natural (F-028) é ENDERECO.
- **Idade (DATA_NASC).** A idade entra com a unidade e, quando houver, com o número por extenso.
- **Saúde (convenção 3).** Cada diagnóstico entra com seus atributos (nível de suporte, estágio). Terapias e acompanhamentos com a frequência entram como entradas próprias. Medicamento entra com a posologia contígua.
- **Veículos.** Placas de frota oficial e de empresa contratada são públicas. A placa da van particular do condutor (F-034) e a placa e o RENAVAM do recorrente (F-029) são ID_VEICULO.
- **Públicos.** São listados por unidade, sem sobreposição com valores pessoais. As armadilhas do redator foram preservadas:
  - municípios e distritos com nome de pessoa;
  - "Avenida Padre Cícero" ao lado de "Cícero Romão…", "Teófilo Otoni" ao lado de "Ottoni" e "Governador Valadares" ao lado de "Valadares";
  - leis e programas com nome de pessoa;
  - "Júlio de Castilhos" como município (F-035) e dentro de endereço residencial (F-021).

## Casos duvidosos e decisões

1. **"dependente com deficiência" no assunto de F-005 não foi anotado.** A expressão é a categoria legal do pedido e aparece idêntica no parágrafo normativo sobre o estatuto. Se fosse anotada, a ocorrência genérica também contaria como pessoal. O diagnóstico específico está anotado no relato e na ementa. A mesma lógica vale para "motivo de saúde de dependente" no assunto de F-039, onde o diagnóstico também está anotado.
2. **QUASI_IDENTIFICADOR de F-022 em um só trecho.** A outra leitura possível, que separa a função única e a licença de saúde, deixa o quase-identificador sem o atributo revelado, contra o texto da convenção 5. O trecho único mantém o dado de saúde coberto.
3. **Valor por extenso (F-002).** Decidi por uma expressão única, por coerência com a idade de F-027. Não há outro valor pessoal com extenso no lote.
4. **Números de inscrição e cadastro sobre pessoa ficaram como ID_PROCESSUAL** (convenção 8): inscrição imobiliária (F-026), inscrição municipal de autônomo (F-049), inscrição de candidato (F-023, F-036) e cadastro de agente cultural (F-021). Nenhum rótulo é mais específico.
5. **Representação de sindicato em F-013 ficou como DADO_SENSIVEL.** A representação do segmento de trabalhadores pelo sindicato revela filiação sindical. As associações de moradores, de aposentados e de agentes comunitários e a APAE não foram marcadas: não revelam dado sensível do representante.
6. **Sobrenomes que são etnônimos não foram marcados como DADO_SENSIVEL.** São Kaxinawá, Wapichana, Macuxi, Taurepang, Ingarikó, Guajajara, Kayapó, Pataxó, Baniwa, Tupari e Kaiowá. Nenhum texto afirma a origem étnica da pessoa, e a convenção 6 pede a expressão que revela o dado ("indígena da etnia X"). Em F-023, deduzir a etnia da língua ensinada seria inferência.
7. **Celulares em F-038 e F-050 ficaram como CONTATO.** São informados para contato direto com servidora ou servidor, e nada indica que sejam linhas institucionais. Os telefones fixos e os e-mails de órgão são públicos.
8. **Datas sobre uma pessoa não foram anotadas,** porque não são rótulo de dado pessoal: períodos de licença e férias, início de benefício, períodos de exercício e data de aprovação em exame. As datas de pedido de acesso que o redator listou como públicas (F-003, F-033) e a data do exame em F-036 foram mantidas: devem ficar legíveis numa resposta pública.
9. **Itens não anotados por falta de rótulo ou de conteúdo:**
   - o modelo do veículo em F-029 (o rótulo cobre placa, RENAVAM e chassi);
   - "quadro clínico" e "relatório de atendimento hospitalar" em F-029, que não descrevem condição;
   - o número de documento interno do SEI em F-043;
   - funções sem atributo revelado, como o nutricionista responsável técnico da contratada em F-019 e o médico diretor clínico em F-003.
10. **Confirmado: 15 documentos sem dado pessoal.** São F-004, 007, 011, 012, 014, 019, 024, 025, 031, 032, 037, 040, 044, 045 e 046.
