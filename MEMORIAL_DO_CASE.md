# Memorial do Case — Análise de Anomalias de Faturamento

*Documento de estudo para a apresentação. Reúne a anatomia da base, o enunciado, a reconstrução do cenário de negócio, o passo a passo da análise, os resultados, os achados de qualidade de dado e um banco de perguntas prováveis com respostas.*

**Arquivo analisado:** `Case_Processo_Seletivo.xlsx` · **Script:** `analise_anomalias.py` · **Saída bruta:** `saida_execucao.txt` · **Resultado:** `resultado_analise.xlsx`

---

## Sumário executivo — o que dizer nos primeiros 30 segundos

> A operação trata **163.811 anomalias de faturamento** em 6 meses, com **6,23% fora do SLA** de 2 dias. O volume é dominado pelo tratamento massivo (81%), mas o **esforço humano é 94% manual** — é ali que está o custo e é ali que a automação paga. Mais: **53% de todas as quebras de SLA vêm de um único código, a MANUAL01**, concentrada em um único colaborador. Não é um problema difuso de capacidade; é um gargalo endereçável.

---

# 1. Anatomia da planilha

## 1.1 Visão geral do arquivo

A pasta de trabalho tem **três abas**, com papéis bem distintos:

| Aba | Dimensões | O que é | Papel na análise |
|---|---|---|---|
| `Expectativa` | 21 linhas úteis (B2:K22) | O **enunciado do desafio**. Texto corrido, sem tabela. | Define o que entregar e como seremos avaliados. Não contém dado. |
| `Base de Dados` | **163.811 linhas × 8 colunas** | O **fato**: um registro por anomalia tratada. | É a base analítica. Tudo é calculado sobre ela. |
| `Premissas e Informações` | 46 linhas × 9 colunas, em **três blocos lado a lado** | Os **parâmetros**: tempo médio por anomalia, SLA, saturação e o dicionário de dados. | Fornece as constantes do cálculo e a tabela do merge. |

**Ponto de atenção estrutural:** a aba `Premissas e Informações` não é uma tabela simples. Ela tem três blocos horizontais com títulos em células mescladas (`B1:C2`, `E1:F2`, `H1:I2`), e a tabela de Tempo Médio **começa na linha 3**, não na linha 1. Ler essa aba com `header=0` produz lixo. No script, a tabela é localizada **dinamicamente** pela busca do par de rótulos `Anomalia` / `Tempo` — se a planilha mudar de layout, o código encontra ou falha alto, mas não calcula errado em silêncio.

## 1.2 Aba `Base de Dados` — o fato

**Granularidade — o que é uma linha:** uma linha é **uma anomalia (retenção) aplicada a um documento de faturamento, e o seu tratamento**. Não é um documento, e não é um dia de trabalho.

Isso importa porque `Documento` **não é chave única**: há 112.282 documentos distintos para 163.811 linhas — em média **1,46 anomalia por documento**, com casos de até **19 anomalias no mesmo documento**. Um mesmo documento pode ser retido por várias regras diferentes e cada retenção precisa ser tratada individualmente. A chave real da linha é a combinação `Documento` + `Anomalia` + `Data da Anomalia`, e essa combinação **não tem duplicatas** (verificado).

**Período coberto:** anomalias geradas entre **06/01/2026 e 30/06/2026** (6 meses); tratamentos registrados até **05/08/2026** — a cauda de tratamento passa do fim do período de geração, o que é esperado e é justamente onde moram os atrasos.

**As 8 colunas, com o nome exato:**

| Coluna (nome exato) | Tipo | Nulos | Distintos | Exemplos | Papel na análise |
|---|---|---|---|---|---|
| `Documento` | int64 | 0 | 112.282 | 217750304505, 217500032003, 216650101500 | Identificador do documento de faturamento retido. Não é chave única: um documento pode acumular várias anomalias. |
| `Anomalia` | str | 0 | 32 | ZFML_X_MF, ZCDFNPARC, ZC113DIFNG | Código da retenção aplicada. Chave do merge com a tabela de Tempo Médio. |
| `Data da Anomalia` | str | 0 | 120 | 2026-02-21, 2026-02-20, 2026-04-23 | Data em que a anomalia esteve presente no contrato. Início da contagem do SLA. |
| `Data de Tratamento` | str | 0 | 119 | 2026-02-21, 2026-04-23, 2026-06-30 | Data em que a anomalia foi tratada e liberada. Fim da contagem do SLA. |
| `Tipo de Tratamento` | str | 0 | 2 | Com correção, Sem Correção | Se houve intervenção de correção ou apenas liberação da retenção. |
| `Tipo de Liberação` | str | 0 | 2 | MASSIVO, MANUAL | Se o tratamento foi feito de forma manual (um a um) ou massiva (em lote). |
| `Origem` | str | 0 | 3 | Backoffice, Clientes Telemedidos, Campo | Sistema, processo ou regra que gerou a retenção. |
| `Colaborador(a)` | str | 0 | 8 | NAYARA, JESSICA, ALFREDO | Quem analisou e concluiu o tratamento. Chave do cálculo de saturação. |

**Distribuição das colunas categóricas:**

| Coluna | Valores | Distribuição |
|---|---|---|
| `Tipo de Tratamento` | 2 | Sem Correção 50.0% · Com correção 50.0% |
| `Tipo de Liberação` | 2 | MASSIVO 80.9% · MANUAL 19.1% |
| `Origem` | 3 | Backoffice 68.7% · Campo 25.3% · Clientes Telemedidos 6.0% |
| `Colaborador(a)` | 8 | ANA 38.6% · ALFREDO 22.4% · JOSE 15.5% · MARTA 7.2% · NAYARA 4.5% · CARLA 4.4% · JESSICA 3.9% · ANDREA 3.4% |

**Qualidade formal:** zero nulos em todas as 8 colunas, zero linhas duplicadas, todas as datas em formato ISO `AAAA-MM-DD` e 100% conversíveis. A base é *formalmente* limpa — o que não quer dizer que seja *logicamente* consistente (ver seção 6).

**Volume por mês de geração:**

| Mês | Anomalias geradas | % do total |
|---|---|---|
| 2026-01 | 15.953 | 9.7 |
| 2026-02 | 28.313 | 17.3 |
| 2026-03 | 45.554 | 27.8 |
| 2026-04 | 16.737 | 10.2 |
| 2026-05 | 28.853 | 17.6 |
| 2026-06 | 28.401 | 17.3 |

Março concentra 27,8% das anomalias do semestre — quase o triplo de janeiro. **Fato observado**; a causa não está na base.

**Um detalhe de calendário que muda o cálculo:** há **5.342 tratamentos registrados em sábados e nenhum em domingos**. A operação, portanto, roda seis dias por semana. Esse fato é a base da decisão sobre "dias corridos vs úteis" (seção 4).

## 1.3 Aba `Premissas e Informações` — os parâmetros

### Bloco 1 (B1:C46) — Tempo Médio de Tratamento das Anomalias

Tabela de **43 anomalias** com o tempo médio de tratamento de cada uma. As células estão formatadas como hora (`00:06:10`), o que no contexto significa **6 minutos e 10 segundos** — não 6 horas. Os valores vão de **33 segundos a 6min10s**.

| Anomalia | Tempo (mm:ss) | Segundos | Chamados na base | Consta na base? |
|---|---|---|---|---|
| ZFML_X_MF | 06:10 | 370 | 58 | sim |
| MANUAL02 | 06:03 | 363 | 28 | sim |
| ZCDEVEXC | 06:01 | 361 | 99 | sim |
| MANUAL03 | 04:14 | 254 | 3476 | sim |
| MANUAL04 | 04:14 | 254 | 26 | sim |
| ZCLTAPDEF | 04:14 | 254 | 23428 | sim |
| ZCLTAPTL33 | 04:14 | 254 | 1244 | sim |
| ZCDFNPARC | 03:18 | 198 | 44208 | sim |
| ZCLAJ_SP47 | 02:03 | 123 | 202 | sim |
| MANUAL00 | 01:55 | 115 | 2325 | sim |
| MANUAL01 | 01:55 | 115 | 27214 | sim |
| MANUAL05 | 01:55 | 115 | 3913 | sim |
| MANUAL07 | 01:55 | 115 | 2 | sim |
| MANUAL08 | 01:55 | 115 | 40 | sim |
| MANUAL09 | 01:55 | 115 | 1 | sim |
| OSB-Amount | 01:55 | 115 | 1069 | sim |
| ZC113DIFNG | 01:55 | 115 | 16702 | sim |
| ZC113MULEQ | 01:55 | 115 | 2 | sim |
| ZCAJALTO | 01:55 | 115 | 37635 | sim |
| ZCCL<15 | 01:55 | 115 | 0 | **não** |
| ZCCL<27 | 01:55 | 115 | 63 | sim |
| ZCCOVID19 | 01:55 | 115 | 0 | **não** |
| ZCDFLRCPI | 01:55 | 115 | 0 | **não** |
| ZCIMPNEG | 01:55 | 115 | 0 | **não** |
| ZCLBXIRREG | 01:55 | 115 | 2 | sim |
| ZCLE_48_56 | 01:55 | 115 | 1 | sim |
| ZCLN_34_42 | 01:55 | 115 | 45 | sim |
| ZCOSB | 01:55 | 115 | 0 | **não** |
| ZCOSB_OLT | 01:55 | 115 | 0 | **não** |
| ZCSAZONAL | 01:55 | 115 | 4 | sim |
| ZCSDABER | 01:55 | 115 | 7 | sim |
| ZCSDEMI | 01:55 | 115 | 0 | **não** |
| ZFDC_CDC11 | 01:55 | 115 | 19 | sim |
| ZFDJUDVL | 01:55 | 115 | 0 | **não** |
| ZFINCONS | 01:55 | 115 | 0 | **não** |
| ZFOSB | 01:55 | 115 | 0 | **não** |
| ZFOSB_SRTC | 01:55 | 115 | 0 | **não** |
| ZFVALALTO | 01:55 | 115 | 204 | sim |
| ZCIMPALTO | 01:53 | 113 | 1535 | sim |
| ZCFPMBAI | 01:45 | 105 | 22 | sim |
| ZCLAJ_SP42 | 00:44 | 44 | 105 | sim |
| ZCLAJ_SP56 | 00:44 | 44 | 110 | sim |
| MANUAL06 | 00:33 | 33 | 22 | sim |

**Três leituras críticas dessa tabela — decore estas:**

1. **29 das 43 anomalias têm exatamente o mesmo tempo: `01:55`.** Isso não é coincidência estatística; é um **valor padrão de preenchimento**. Só 14 anomalias têm tempo genuinamente medido. Felizmente, as anomalias de maior volume (`ZCDFNPARC`, `ZCLTAPDEF`) estão entre as que têm valor próprio — mas isso limita a precisão de qualquer número de horas.
2. **O valor `04:14` se repete 4 vezes** (`ZCLTAPDEF`, `MANUAL03`, `MANUAL04`, `ZCLTAPTL33`) e `00:44` se repete 2 vezes — outro sinal de agrupamento/estimativa, não de medição individual.
3. **11 anomalias cadastradas não aparecem na base** do período. O cadastro é mais amplo que a janela analisada. Não afeta os cálculos, mas é preciso saber responder por isso.

### Bloco 2 (E1:F4) — SLA e Saturação

| Parâmetro | Valor literal na planilha |
|---|---|
| Prazo esperado para tratamento das anomalias | **2 dias** |
| Saturação esperada do colaborador(a) por dia | **7 horas** |

São as duas constantes do case. Note que "2 dias" **não é qualificado** — não diz corridos nem úteis, nem se é `<=` ou `<`. Essa ambiguidade é deliberada e é onde o case separa os candidatos (seção 4.3).

### Bloco 3 (H1:I9) — Dados Complementares (dicionário oficial)

| Campo | Definição oficial (texto literal da planilha) |
|---|---|
| Anomalia | Tipo de retenção aplicada para impedir a emissão de faturamento com potencial inconsistência. |
| Data da Anomalia | Data em que a anomalia esteve presente no contrato |
| Data de Tratamento | Data em que a anomalia foi tratada e liberada para prosseguimento do processo de faturamento. |
| Tipo de Tratamento | Indica se houve necessidade de intervenção operacional para correção da inconsistência ou apenas liberação da retenção sem ajustes |
| Tipo de Liberação | Indicação se o tratamento foi dispensado de forma manual ou massiva. |
| Origem | Sistema, processo ou regra responsável pela geração da retenção de faturamento. |
| Colaborador(a) | Usuário responsável pela análise e conclusão do tratamento da anomalia. |

O dicionário documenta **7 campos**, mas a base tem **8 colunas** — `Documento` não é descrito. É a diferença entre o que a área considerou "campo de negócio" e a chave técnica que veio junto.

## 1.4 Aba `Expectativa` — o enunciado

Não contém dado nem layout de saída: é **texto do desafio**, transcrito integralmente na seção 2. Quem espera encontrar ali o formato da resposta perde tempo; quem não a lê com atenção entrega metade do que foi pedido.

---

# 2. O que foi solicitado

## 2.1 Transcrição fiel da aba `Expectativa`

> **Desafio**
>
> Com base na base de dados disponibilizados, o candidato deverá:
>
> 1. Desenvolver um dashboard gerencial contendo os principais indicadores de desempenho (KPIs) que auxiliem a gestão no monitoramento da operação e na tomada de decisão.
> 2. Realizar uma análise crítica dos dados, identificando padrões, tendências, desvios, oportunidades de melhoria e possíveis riscos observados.
> 3. Apresentar recomendações objetivas, fundamentadas nos dados analisados, indicando ações que poderiam contribuir para melhoria dos resultados do negócio.
> 4. Demonstrar o racional analítico utilizado, justificando a escolha dos indicadores, visualizações e conclusões apresentadas.
>
> **Apresentação**
>
> Tempo máximo para apresentação: 10 minutos.
>
> O candidato deverá apresentar:
> - Os KPIs selecionados e sua relevância para o negócio;
> - Os principais insights identificados;
> - As conclusões obtidas a partir dos dados;
> - As recomendações propostas para a gestão.
>
> **Observação:** Será valorizada a capacidade de traduzir dados em informações acionáveis para o negócio, indo além da simples construção de gráficos e indicadores. O foco da avaliação está em: 1. Produzir insights relevantes; 2. Qualidade das recomendações apresentadas; 3. Qualidade na apresentação dos dados.

## 2.2 Destrinchando: o que é entregável, o que é critério, o que é implícito

| Categoria | O que é | Onde aparece |
|---|---|---|
| **Entregável explícito** | Dashboard gerencial de KPIs | Item 1 |
| **Entregável explícito** | Análise crítica: padrões, tendências, desvios, oportunidades, riscos | Item 2 |
| **Entregável explícito** | Recomendações objetivas e fundamentadas | Item 3 |
| **Entregável explícito** | Racional analítico: justificar indicador, visualização e conclusão | Item 4 |
| **Restrição** | 10 minutos de apresentação | Bloco "Apresentação" |
| **Critério de avaliação** | Insights relevantes (peso 1) | Observação |
| **Critério de avaliação** | Qualidade das recomendações (peso 2) | Observação |
| **Critério de avaliação** | Qualidade na apresentação dos dados (peso 3) | Observação |
| **Critério implícito** | "Ir além da simples construção de gráficos" — gráfico bonito sem conclusão não pontua | Observação |
| **Implícito** | Tratar as ambiguidades das premissas (SLA sem qualificador, massivo vs manual) e **defender a escolha** | Estrutura da planilha |
| **Implícito** | Detectar e reportar problemas de qualidade do dado | Item 2, "desvios" e "riscos" |

**A leitura estratégica:** os quatro itens do desafio são **meio**; os três critérios da observação são **fim**. O texto diz explicitamente que gráfico não é o ponto — "indo além da simples construção de gráficos e indicadores". Uma apresentação que gasta 8 dos 10 minutos mostrando visualizações e 2 tirando conclusões está invertida.

## 2.3 O que o pedido técnico cobria, e o que a Expectativa cobra além

O pedido de análise que originou o script cobria cinco itens objetivos:

| # | Requisito técnico | Status |
|---|---|---|
| 1 | Dias entre anomalia e tratamento + flag `Dentro do SLA` (2 dias) | Entregue |
| 2 | Merge da base com os Tempos Médios das Premissas | Entregue, com auditoria de cobertura |
| 3 | Horas por `Colaborador(a)` por dia + flag `Estourou Saturação` (7h) | Entregue, com tratamento do massivo |
| 4 | Taxas gerais: % fora do SLA, % manual vs massivo, top 3 ofensoras | Entregue, com dois rankings de tempo |
| 5 | Código limpo, documentado em português, estatísticas impressas | Entregue |

**A Expectativa cobra quatro coisas que esse pedido não menciona:**

1. **Dashboard gerencial** — artefato visual, não saída de terminal. *Ainda não construído.*
2. **Análise crítica de padrões, tendências e riscos** — a dimensão temporal e comparativa, além das taxas agregadas. *Parcialmente coberta* (ver seções 5 e 6).
3. **Recomendações objetivas para a gestão** — o "e daí?" de cada número. *Coberta neste documento, seção 5.4.*
4. **Racional analítico justificado** — por que *este* KPI e não outro. *É exatamente o que este memorial documenta.*

**Consequência prática:** o script resolve a camada analítica e a defesa metodológica. Faltam, para o case ficar completo, o **dashboard** e o **roteiro de 10 minutos**.

---

# 3. A situação que o case simula

*Esta seção reconstrói a empresa por trás dos dados. Cada afirmação vem marcada: **[FATO]** quando está diretamente observável na planilha, **[INFERÊNCIA]** quando é leitura plausível a partir da evidência. Na banca, apresente as inferências como hipóteses — "a base sugere que..." —, nunca como certezas.*

## 3.1 O processo de negócio

**[FATO]** O dicionário da planilha define anomalia como "tipo de retenção aplicada para impedir a emissão de faturamento com potencial inconsistência", e `Tipo de Tratamento` como a indicação de "se houve necessidade de intervenção operacional para correção da inconsistência ou apenas liberação da retenção sem ajustes".

Isso descreve, na íntegra, um **processo de bloqueio de faturamento**:

1. O sistema de cobrança prepara um documento de faturamento.
2. Regras automáticas de validação inspecionam o documento. Se algo parece errado — valor fora de padrão, leitura de consumo implausível, contrato em situação especial —, uma **retenção (anomalia)** é aplicada e o documento **não é faturado**.
3. Um analista recebe a fila de retenções, investiga cada caso e decide: corrige a inconsistência (**Com correção**) ou conclui que o documento está correto e apenas libera a retenção (**Sem Correção**).
4. Liberado, o documento segue para faturamento.

**[FATO]** A divisão entre corrigir e apenas liberar é praticamente 50/50 (49,98% / 50,02%).

**[INFERÊNCIA — e é uma das mais fortes do case]** Metade das retenções não tinha erro nenhum. São **falsos positivos das regras de validação**: o sistema barrou um documento correto e um humano gastou tempo para dizer "está tudo certo, pode passar". Cada ponto percentual de falso positivo é trabalho puro sem valor agregado. Isso é material de recomendação: calibrar as regras que mais geram "Sem Correção" reduz a fila sem tocar em uma linha de processo.

## 3.2 Que empresa é essa

**[INFERÊNCIA]** Uma **concessionária de utilidade pública** — muito provavelmente **energia elétrica**, possivelmente água ou gás. A evidência:

- **[FATO]** A `Origem` **"Clientes Telemedidos"** (9.890 chamados) é vocabulário direto de medição remota de consumo — telemetria de medidores.
- **[FATO]** A `Origem` **"Campo"** (41.402 chamados, 25,3%) indica equipes de leitura/serviço em campo alimentando o processo.
- **[FATO]** Códigos de anomalia como `ZCSAZONAL` (sazonalidade de consumo), `ZCCL<27` e `ZCCL<15` (limiares de consumo), `ZCIMPALTO` / `ZCIMPNEG` (impostos alto/negativo), `ZCDEVEXC` (devolução de excedente), `ZCCOVID19`.
- **[FATO]** O volume — 163 mil retenções em 6 meses sobre 112 mil documentos — é escala de faturamento de massa, não de B2B.

**[INFERÊNCIA]** O sistema de origem é **SAP** (ou um ERP de padrão semelhante). O prefixo `Z` é a convenção SAP para objetos customizados pelo cliente, e todos os 32 códigos técnicos seguem `ZC*` ou `ZF*`. Em uma banca, isso se diz assim: *"o padrão de nomenclatura sugere objetos customizados de um ERP, provavelmente SAP IS-U"* — e não como afirmação categórica.

## 3.3 O que os códigos de anomalia sugerem

**[FATO]** Os 32 códigos presentes na base caem em três famílias claras:

| Família | Exemplos | **[INFERÊNCIA]** do que trata |
|---|---|---|
| **`ZC*`** — 19 códigos | `ZCDFNPARC`, `ZCAJALTO`, `ZCLTAPDEF`, `ZC113DIFNG`, `ZCIMPALTO`, `ZCSAZONAL` | Regras de **consistência de cobrança/consumo**: parcelamento, ajuste de valor alto, diferença de faturamento, imposto, sazonalidade. É o miolo das validações de conta. |
| **`ZF*`** — 3 códigos | `ZFML_X_MF`, `ZFVALALTO`, `ZFDC_CDC11` | **[INFERÊNCIA]** `F` de faturamento/financeiro: valor alto, divergência entre documentos. Baixo volume, tempo unitário alto. |
| **`MANUAL00`–`MANUAL09`** — 10 códigos | `MANUAL01`, `MANUAL03`, `MANUAL05` | **Retenções aplicadas por decisão humana**, não por regra automática. Alguém segurou o documento deliberadamente. |
| Fora de padrão | `OSB-Amount` | **[FATO]** Único código com hífen e letras minúsculas — nomenclatura de outro sistema. **[INFERÊNCIA]** integração com uma ferramenta distinta (OSB = *Oracle Service Bus* ou "*outstanding balance*"). |

**[FATO]** As anomalias `MANUAL*` somam **37.047 chamados (22,6% do volume)** e concentram **53,4% de todas as quebras de SLA** — praticamente todas na `MANUAL01`.

**[INFERÊNCIA]** Retenção manual é, por natureza, uma fila sem dono automático: ninguém a criou por regra, então ninguém a monitora por regra. É consistente com o padrão de atraso observado (seção 6.2).

## 3.4 Manual vs massivo — o que significa na operação

**[FATO]** `Tipo de Liberação` tem dois valores: `MANUAL` (31.319 chamados, 19,1%) e `MASSIVO` (132.492, 80,9%). Agrupando por colaborador + dia + anomalia, existem **2.277 lotes massivos**, com mediana de 7 chamados e **máximo de 10.600 chamados em um único lote**.

**[INFERÊNCIA]** A leitura operacional é direta:

- **Manual** = o analista abre o caso, investiga, decide e libera. **Um a um.** Custa o tempo médio cheio da anomalia.
- **Massivo** = o analista identifica um padrão ("todos estes 10.600 documentos foram retidos pela mesma regra pelo mesmo motivo, e todos estão corretos") e libera **o lote inteiro em uma execução**. Custa aproximadamente o mesmo tempo de um caso — não 10.600 vezes.

Essa distinção é o coração técnico do case. É ela que torna a conta de saturação defensável ou absurda (seção 4.4).

## 3.5 A equipe

| Colaborador(a) | Dias Trabalhados | Chamados Tratados | Horas Totais | Horas/Dia (média) | Horas/Dia (máximo) | Dias com Estouro | % Fora do SLA | % Manual | Origem predominante |
|---|---|---|---|---|---|---|---|---|---|
| ANA | 90 | 63.278 | 517.41 | 5.75 | 91.03 | 12 | 2.0 | 17.0 | Backoffice |
| ALFREDO | 90 | 36.725 | 210.83 | 2.34 | 17.39 | 6 | 16.86 | 9.3 | Backoffice |
| JOSE | 89 | 25.436 | 187.65 | 2.11 | 28.49 | 8 | 3.43 | 19.2 | Campo |
| NAYARA | 111 | 7.313 | 176.55 | 1.59 | 7.18 | 1 | 6.17 | 39.6 | Backoffice |
| CARLA | 107 | 7.261 | 159.0 | 1.49 | 5.32 | 0 | 4.24 | 36.5 | Backoffice |
| MARTA | 69 | 11.799 | 150.06 | 2.17 | 30.4 | 2 | 5.38 | 21.9 | Backoffice |
| JESSICA | 107 | 6.388 | 132.06 | 1.23 | 4.5 | 0 | 6.4 | 32.3 | Backoffice |
| ANDREA | 34 | 5.611 | 110.7 | 3.26 | 20.17 | 4 | 0.57 | 36.1 | Backoffice |

**[FATO]** São 8 pessoas, com distribuição de carga muito desigual: **ANA sozinha trata 38,6% do volume**; as três menores somam menos de 12%.

**[INFERÊNCIA]** A base sugere **especialização por origem, não por volume**:

- **ANA** e **JOSE** são os únicos com volume relevante de `Campo` (18.870 e 19.859) — provavelmente a dupla que cuida da fila gerada por serviço em campo.
- **ALFREDO** é o **único** que trata `Clientes Telemedidos` (todos os 9.890) — dono exclusivo da fila de telemetria.
- **ANDREA** aparece em apenas **34 dias** dos ~120 do período, contra 111 de NAYARA. **[INFERÊNCIA]** entrada tardia, saída, férias, ou alocação parcial em outra frente.
- Quem tem **maior % de tratamento manual** (NAYARA 39,6%, CARLA 36,5%, ANDREA 36,1%) tem **menor volume total**. Quem opera em massa (ALFREDO 90,7% massivo, ANA 83,0%) carrega o volume. **[INFERÊNCIA]** dois perfis de trabalho coexistem na mesma equipe: o "resolvedor de casos" e o "operador de lote".

## 3.6 O que SLA de 2 dias e saturação de 7h revelam sobre a gestão

**[FATO]** As duas premissas estão escritas na planilha: prazo de 2 dias, saturação de 7 horas/dia.

**[INFERÊNCIA]** Elas dizem bastante sobre como a área é gerida:

- **SLA de 2 dias sobre retenção de faturamento** significa que **o dinheiro está parado enquanto a anomalia existe**. Documento retido é receita não faturada. Um SLA curto e explícito indica que alguém já mediu o custo financeiro do atraso — provavelmente em impacto de fluxo de caixa ou em indicador regulatório de prazo de faturamento.
- **Saturação de 7 horas em uma jornada de 8** é um **parâmetro de capacidade produtiva**: reserva-se ~1 hora para reunião, pausa e trabalho não medido. Uma área que define isso já pensa em dimensionamento de equipe, não só em execução.
- A existência de uma **tabela de tempo médio por tipo de anomalia** mostra que a gestão quer **converter fila em horas** — ou seja, responder "quantas pessoas eu preciso para esse volume?".

**[INFERÊNCIA] A dor de negócio que motiva o pedido**, portanto, é uma destas três (ou a combinação):

1. **"Estou perdendo prazo e não sei onde."** Alguém reportou atraso de faturamento e a gestão precisa localizar o gargalo.
2. **"Preciso justificar quadro de pessoal."** Com tempo médio × volume, dá para dizer quantas pessoas o volume exige — para pedir mais gente ou para provar que dá para fazer com menos.
3. **"Quero saber o que automatizar primeiro."** Com 163 mil retenções e metade sem erro real, a pergunta é onde a automação tem maior retorno.

**A boa notícia para a apresentação:** os dados respondem às três. E respondem com um único achado central — o desequilíbrio entre volume e esforço (seção 5.2).

---

# 4. O que fizemos e como

Todo o processamento está em `analise_anomalias.py` (~940 linhas, comentado em português). O fluxo é orquestrado em `main()` e segue sete etapas.

## 4.1 Etapa 0 — Inspecionar antes de calcular

**O que foi feito:** antes de qualquer análise, o script lê a planilha e imprime a estrutura real: abas encontradas, nomes de coluna com `repr()` (para expor espaço extra, acento e quebra de linha invisíveis), dtypes, contagem de nulos e cardinalidade de cada coluna.

**Por quê:** nome de coluna inventado é a forma mais rápida de produzir um número errado com aparência correta. `repr()` mostra `'Colaborador(a)'` e revelaria `'Colaborador(a) '` com espaço no fim — uma diferença invisível a olho nu que quebra qualquer `groupby`.

**Como no código:** `inspecionar_planilha()`. A função valida a lista `COLUNAS_OBRIGATORIAS` e **levanta exceção** se qualquer uma faltar. Falhar alto é melhor que calcular errado.

**Resultado:** as 8 colunas conferem com o nome exato, zero nulos, zero problemas de conversão.

## 4.2 Etapa 0b — Extrair a tabela de Tempo Médio

**O que foi feito:** localizar a tabela dentro da aba de Premissas e converter a coluna `Tempo` para segundos.

**Por quê:** a tabela não começa na linha 1 (são três blocos lado a lado com títulos mesclados), e as células estão formatadas como `datetime.time`, não como número.

**Como no código:** `extrair_tempos_medios()` varre a aba procurando o par de rótulos `Anomalia` / `Tempo` adjacentes e ancora a leitura ali — em vez de assumir posição fixa. A conversão fica em `tempo_para_segundos()`, que aceita `datetime.time`, `Timedelta`, string `HH:MM:SS` e serial numérico do Excel.

**Resultado:** 43 anomalias, de 33s a 370s, mediana 115s. Zero chaves duplicadas — verificado explicitamente, porque chave duplicada no lado direito de um merge **multiplica linhas** e infla todos os totais silenciosamente.

## 4.3 Etapa 1 — Tempo de tratamento e flag `Dentro do SLA`

**O que foi feito:** converter as datas, calcular `Dias para Tratamento` e criar a flag booleana `Dentro do SLA`.

**Como no código:** `preparar_e_calcular_sla()`.

### Decisão [D1] — dias corridos, não úteis

| Alternativa | % fora do SLA | Avaliação |
|---|---|---|
| **Dias corridos (ADOTADO)** | **6,23%** | Leitura literal da premissa |
| Dias úteis seg–sáb | 3,12% | Afrouxa o indicador pela metade |

**Justificativa:** a planilha diz apenas "2 dias", sem qualificar. E o dado mostra **5.342 tratamentos aos sábados e zero aos domingos** — a operação **não** segue calendário útil seg–sex. Adotar dias úteis padrão perdoaria automaticamente todo atraso que atravessa fim de semana, num processo que trabalha aos sábados. Dias corridos é a leitura conservadora e defensável.

**Transparência:** o script calcula **também** `Dias Úteis (Seg-Sáb)` como coluna de sensibilidade (função `dias_uteis_seg_sab()`, com `weekmask="1111110"`) e imprime os dois cenários. Nada foi escondido.

### Decisão [D2] — SLA é `<= 2`, não `< 2`

| Alternativa | % fora do SLA | Diferença |
|---|---|---|
| **`atraso <= 2` (ADOTADO)** | **6,23%** | — |
| `atraso < 2` | 10,51% | **+4,28 pontos** |

**Justificativa:** "prazo esperado para tratamento: 2 dias" descreve um **teto**. Tratar em 2 dias **cumpre** o acordo. Ler como `< 2` transformaria o prazo em 1 dia e reprovaria quem fez exatamente o combinado. A escolha vale 4,28 pontos percentuais — quase dobra o indicador —, por isso está documentada e a alternativa é impressa junto.

### Decisão [D3] — anomalias sem tratamento não somem do denominador

**Regra implementada:** registro sem `Data de Tratamento` permanece na base, é envelhecido contra a **data máxima observada na base** (não contra "hoje", que tornaria o resultado irreprodutível) e conta como fora do SLA se já ultrapassou o prazo.

**Por quê:** excluir o não tratado do denominador é a maneira clássica de fabricar um SLA bonito — some justamente o caso pior. O código trata isso mesmo tendo encontrado **zero ocorrências** nesta base. A robustez está lá e o número zero é reportado explicitamente.

### Decisão [D7] — registros com data invertida

**Regra implementada:** 537 registros têm tratamento **anterior** à anomalia. Recebem `Registro Inconsistente = True`, ficam com `Dentro do SLA` **nulo** e saem do denominador do SLA — com a contagem reportada na saída.

**Por quê:** são impossíveis no fluxo do processo. Tratá-los como "dentro do SLA" (atraso negativo ≤ 2) premiaria um erro de dado com um indicador melhor. Descartá-los em silêncio esconderia um problema de qualidade que a gestão precisa conhecer. Sinalizar e excluir do cálculo, reportando, é a única saída honesta. Detalhes na seção 6.1.

## 4.4 Etapa 2 — Merge com os Tempos Médios

**O que foi feito:** juntar a base à tabela de tempos pela chave `Anomalia`, **auditando a cobertura**.

**Como no código:** `merge_tempos_medios()`, apoiada em `normalizar_chave()`.

**A defesa contra o erro clássico:** divergência de grafia entre as duas abas (acento, espaço extra, caixa) faria o merge falhar silenciosamente e deixar `NaN` no tempo médio — que depois viraria zero hora em algum `sum()`. `normalizar_chave()` remove acentos (normalização NFKD), colapsa espaços internos, corta espaços das bordas e uniformiza a caixa antes de casar.

**Três validações explícitas, todas na saída:**

| Validação | Como | Resultado |
|---|---|---|
| O merge não multiplicou linhas | `validate="many_to_one"` + comparação de contagem antes/depois com `AssertionError` | 163.811 → 163.811 |
| Nenhuma anomalia ficou sem tempo | Contagem de `Tempo Médio (s)` nulo após o merge | **0 linhas** |
| Cadastro mais amplo que a base | Diferença de conjuntos nos dois sentidos | 11 anomalias cadastradas sem uso, listadas nominalmente |

**Por que isso vale nota:** dizer "o merge funcionou" não é evidência. Imprimir a contagem de não casados — **mesmo quando é zero** — é. Se a resposta fosse 4.000 linhas sem tempo, o número apareceria em vez de virar hora zero no relatório.

## 4.5 Etapa 3 — Esforço por chamado e saturação

**O que foi feito:** converter cada chamado em horas e agregar por colaborador e dia, com a flag `Estourou Saturação` (> 7h).

**Como no código:** `calcular_esforco()` e `resumo_saturacao()`.

### Decisão [D4] — o rateio do tratamento massivo (a decisão mais importante do case)

**O problema:** um tratamento massivo resolve um lote inteiro em uma execução. Se atribuirmos o tempo médio **cheio** a cada chamado do lote, um lote de 10.600 documentos custaria 10.600 × 1min55s = **339 horas** — em um dia, para uma pessoa.

**A regra implementada:**

- `MANUAL` → tempo médio **cheio** por chamado (cada um foi tratado individualmente).
- `MASSIVO` → tempo médio contado **uma vez por lote**, rateado igualmente entre os chamados do lote. O total por lote fica correto e cada linha continua auditável.
- Lote = `Colaborador(a)` + `Data de Tratamento` + `Anomalia` + `Tipo de Liberação` — mesma pessoa, mesmo dia, mesma anomalia, mesma execução.

**O custo da alternativa — o número que fecha a discussão:**

| Métrica | Cenário adotado (rateado) | Cenário ingênuo (tempo cheio) | Fator |
|---|---|---|---|
| Esforço total do semestre | **1.644,3 h** | 7.347,5 h | **4,5×** |
| Dias-colaborador acima de 7h | **33 de 698 (4,7%)** | 157 de 698 (**22,5%**) | 4,8× |

**Por que o cenário ingênuo é indefensável:** ele afirmaria que a equipe trabalhou 7.347 horas em 6 meses — o equivalente a 8,8 pessoas em tempo integral só nessa fila — e que 1 em cada 4,4 dias de trabalho estourou a jornada. Ele também produziria uma média de **29,8 h/dia para ANA**, um número fisicamente impossível que qualquer avaliador identifica em 5 segundos.

**Transparência:** o script calcula **os dois** e mantém ambos na base exportada (`Horas Atribuídas` e `Horas (Cenário Ingênuo)`), imprimindo a comparação. A decisão é declarada, não escondida.

## 4.6 Etapa 4 — Taxas gerais e top 3 ofensoras

**Como no código:** `taxas_gerais()` e `top_anomalias()`.

### Decisão [D5] — "maior tempo gasto" tem duas leituras, e as duas foram entregues

O requisito pedia as "top 3 anomalias mais ofensoras (maior volume e maior tempo gasto)". "Maior tempo gasto" é ambíguo:

- **Tempo total agregado** → onde a operação queima horas. Responde: *o que automatizar primeiro?*
- **Tempo médio unitário** → qual anomalia é individualmente cara. Responde: *qual procedimento simplificar?*

São rankings **sem interseção** nesta base. Entregar só um é entregar metade da resposta; entregar os dois e explicar a diferença é o que demonstra maturidade analítica.

## 4.7 Etapas 5 e 6 — Exportação e painel

`exportar()` grava `resultado_analise.xlsx` com 9 abas: a ficha de premissas e decisões (para o resultado não depender do script), a base enriquecida com 163.811 linhas e 22 colunas, e sete abas de resumo. `painel_final()` imprime o resumo executivo.

Detalhe deliberado: a base exportada traz de volta, em cada linha de chamado, as `Horas do Colaborador no Dia` e a flag `Estourou Saturação`. Assim a aba é **autossuficiente** — dá para filtrar e conferir qualquer número sem reexecutar nada.

---

# 5. Os resultados e o que significam

## 5.1 Painel principal

| Indicador | Valor | Leitura de negócio |
|---|---|---|
| Chamados analisados | 163.811 | 6 meses de operação |
| Documentos distintos | 112.282 | 1,46 retenção por documento |
| **% fora do SLA** | **6,23%** (10.166) | ~93,8% dentro do prazo — o processo, no agregado, funciona |
| Tratados no mesmo dia | **80,73%** | A maioria esmagadora é resolvida na hora |
| Tempo médio / p90 / máximo | 0,41 dia / 2 dias / **120 dias** | Média e p90 ótimos; a cauda é longuíssima |
| Esforço total estimado | **1.644 h** | ~2 pessoas em tempo integral (1,97 FTE) |
| Dias-colaborador acima de 7h | 33 de 698 (4,7%) | Saturação **não** é o problema sistêmico |

**A leitura que sustenta a apresentação:** o processo **não tem um problema de capacidade** — tem 4,7% de dias saturados e p90 exatamente no limite do SLA. O que ele tem é uma **cauda concentrada**: 6,23% dos casos escapam, e eles não estão espalhados.

## 5.2 O contraste 19/81 contra 94/6 — o achado central

| Tipo de Liberação | Chamados | % dos Chamados | Horas Atribuídas | % do Esforço |
|---|---|---|---|---|
| MASSIVO | 132.492 | 80.88 | 103.71 | 6.31 |
| MANUAL | 31.319 | 19.12 | 1540.54 | 93.69 |

**Leia esta tabela duas vezes.** O tratamento massivo responde por **80,88% do volume** e apenas **6,31% do esforço humano**. O manual é o inverso quase perfeito: **19,12% do volume, 93,69% do esforço**.

**O que isso significa em uma frase:** *quatro em cada cinco anomalias já são resolvidas de forma essencialmente gratuita; praticamente todo o custo humano da operação está concentrado no quinto restante.*

**Por que é o insight mais valioso do case:**

1. **Redireciona a pergunta.** A pergunta natural da gestão é "como reduzir as 163 mil anomalias?". A resposta certa é: reduzir volume massivo não economiza quase nada. **um chamado manual custa em média 63× mais esforço que um massivo** (2,95 min contra 0,047 min). Migrar volume de manual para massivo vale muito mais que reduzir volume total.
2. **Dá alvo à automação.** Não se automatiza "a fila". Automatiza-se a fila manual — e, dentro dela, as anomalias que aparecem no ranking de horas.
3. **Explica a saturação.** Os picos de carga não vêm de volume alto; vêm de volume alto **classificado como manual** (seção 6.2).

## 5.3 Ranking de anomalias — os três recortes

| Anomalia | Chamados | % do Volume | Horas Totais | % do Esforço | Tempo Médio Unitário (min) | % Fora do SLA | Dias Médios p/ Tratamento |
|---|---|---|---|---|---|---|---|
| ZCDFNPARC | 44.208 | 26.99 | 219.34 | 13.34 | 3.3 | 2.21 | 0.14 |
| ZCAJALTO | 37.635 | 22.97 | 287.56 | 17.49 | 1.92 | 0.61 | 0.28 |
| MANUAL01 | 27.214 | 16.61 | 10.67 | 0.65 | 1.92 | 19.93 | 0.78 |
| ZCLTAPDEF | 23.428 | 14.3 | 542.57 | 33.0 | 4.23 | 5.22 | 0.46 |
| ZC113DIFNG | 16.702 | 10.2 | 14.41 | 0.88 | 1.92 | 7.25 | 0.57 |
| MANUAL05 | 3.913 | 2.39 | 125.0 | 7.6 | 1.92 | 14.69 | 1.04 |
| MANUAL03 | 3.476 | 2.12 | 231.14 | 14.06 | 4.23 | 4.89 | 0.4 |
| MANUAL00 | 2.325 | 1.42 | 4.66 | 0.28 | 1.92 | 2.88 | 0.24 |
| ZCIMPALTO | 1.535 | 0.94 | 48.02 | 2.92 | 1.88 | 4.43 | 0.44 |
| ZCLTAPTL33 | 1.244 | 0.76 | 87.35 | 5.31 | 4.23 | 3.86 | 0.27 |
| OSB-Amount | 1.069 | 0.65 | 34.15 | 2.08 | 1.92 | 0.65 | 0.41 |
| ZFVALALTO | 204 | 0.12 | 5.59 | 0.34 | 1.92 | 30.39 | 2.09 |

*(12 primeiras de 32; ranking completo na aba `Ranking Anomalias` do resultado.)*

**A) Top 3 por volume:** `ZCDFNPARC` (44.208 · 27,0%), `ZCAJALTO` (37.635 · 23,0%), `MANUAL01` (27.214 · 16,6%).

**B) Top 3 por tempo total:** `ZCLTAPDEF` (542,6 h · **33,0% de todo o esforço**), `ZCAJALTO` (287,6 h · 17,5%), `MANUAL03` (231,1 h · 14,1%).

**C) Top 3 por tempo médio unitário:** `ZFML_X_MF` (6,17 min), `MANUAL02` (6,05 min), `ZCDEVEXC` (6,02 min).

**As três leituras que os rankings entregam:**

- **`ZCLTAPDEF` é a maior consumidora de horas da operação** (33% do esforço) sendo apenas a **4ª em volume** (14,3%). Combina volume alto, tempo unitário alto (4,23 min) e **30,9% de tratamento manual — e esses 30,9% respondem por 510 das suas 542,6 horas**. É a primeira candidata a automação.
- **`ZCDFNPARC` lidera o volume mas custa 13,3% do esforço** — já é tratada majoritariamente em massa. Reduzi-la traria pouco retorno de capacidade.
- **O ranking C é uma armadilha de priorização.** `ZFML_X_MF` é a mais cara por ocorrência (6,17 min), mas tem **58 chamados no semestre** — 4,9 horas no total. Otimizá-la é irrelevante. É exatamente por isso que os dois rankings precisam ser apresentados juntos: **o ranking unitário sem o volume ao lado leva a decisão errada.**

## 5.4 Onde o SLA quebra — e a recomendação que sai daí

| Anomalia | Chamados fora do SLA | % de todas as quebras | % do volume da anomalia |
|---|---|---|---|
| MANUAL01 | 5.425 | 53.4 | 19.9 |
| ZCLTAPDEF | 1.223 | 12.0 | 5.2 |
| ZC113DIFNG | 1.211 | 11.9 | 7.3 |
| ZCDFNPARC | 976 | 9.6 | 2.2 |
| MANUAL05 | 575 | 5.7 | 14.7 |
| ZCAJALTO | 231 | 2.3 | 0.6 |

**O achado mais acionável do case:** `MANUAL01`, com 16,6% do volume, responde por **53,4% de todas as quebras de SLA**. Sua taxa de falha interna é de **19,93%**, contra 2,21% da maior anomalia em volume.

E há mais: **5.355 das 5.425 quebras de `MANUAL01` estão com um único colaborador (ALFREDO)** — o que também explica por que ele aparece com 16,86% de chamados fora do prazo contra 2,00% de ANA. **Não é desempenho individual: é a fila que caiu no colo dele.**

**As quatro recomendações que os dados sustentam:**

1. **Atacar `MANUAL01` primeiro.** Metade das quebras de SLA está em um código. Resolver essa fila corta o indicador geral de 6,23% para ~3,0% — sem tocar em nada mais.
2. **Automatizar `ZCLTAPDEF`.** Um terço de todo o esforço humano do semestre. Maior retorno de capacidade por unidade de trabalho.
3. **Calibrar as regras que mais geram "Sem Correção".** Metade das retenções não tinha erro. Cada falso positivo eliminado é fila que nunca se forma.
4. **Redistribuir a fila `MANUAL01`, não cobrar o ALFREDO.** A concentração é estrutural, não individual — e o dado mostra isso com clareza.

---

# 6. As anomalias nos dados

*Apresente esta seção como **achado de qualidade de dado**, não como desculpa. Encontrar e reportar isso é competência; deixar passar é o erro.*

## 6.1 Achado 1 — 537 registros com tratamento anterior à anomalia

**O fato:** 537 linhas (0,33% da base) têm `Data de Tratamento` **anterior** à `Data da Anomalia`. A distribuição é reveladora:

| Atraso | Ocorrências | Padrão |
|---|---|---|
| −2 dias | **536** | Concentradas: anomalia em **27/04/2026**, tratamento em **25/04/2026** |
| −14 dias | 1 | Caso isolado |

**Por que não é ruído aleatório:** 536 dos 537 casos compartilham exatamente o mesmo par de datas, mas se espalham por **múltiplas anomalias, colaboradores e origens**. Erro de digitação individual não produz esse padrão.

**Hipóteses de causa, em ordem de plausibilidade:**

1. **Erro de carga/ETL em um lote específico.** Um job processou o dia 27/04 com carimbo de data errado, ou houve inversão de campos na extração.
2. **Reprocessamento retroativo.** A anomalia foi *reaplicada* em 27/04 sobre um documento cujo tratamento de 25/04 já constava — o registro guardaria a data da reincidência, não da ocorrência original.
3. **Fusos ou tipos de data diferentes** entre os sistemas de origem da anomalia e do tratamento.

**O que perguntar à área:**

- "O que aconteceu na carga do dia 27/04/2026? Houve reprocessamento ou correção retroativa?"
- "A `Data da Anomalia` é a data da **primeira** ocorrência ou a da **última reincidência**?"
- "É possível que uma anomalia seja reaplicada a um documento já tratado? Se sim, como o registro reflete isso?"

**O que fizemos:** sinalizamos (`Registro Inconsistente`), excluímos do denominador do SLA e reportamos a contagem. Como são 0,33% da base, o impacto no indicador é desprezível — mas a decisão está documentada e é reversível.

## 6.2 Achado 2 — 12 dias-colaborador com carga fisicamente impossível

**O fato:** mesmo **depois** do rateio correto do massivo, 12 pares (colaborador, dia) ultrapassam 24 horas de trabalho.

| Colaborador(a) | Data | Chamados Tratados | Horas Trabalhadas | % da Capacidade Diária |
|---|---|---|---|---|
| ANA | 25/05/2026 | 8.225 | 91.0 | 1300.4 |
| ANA | 19/02/2026 | 3.910 | 41.7 | 596.3 |
| ANA | 20/03/2026 | 3.078 | 40.8 | 582.4 |
| ANA | 29/05/2026 | 1.785 | 35.5 | 506.8 |
| ANA | 27/02/2026 | 4.189 | 31.9 | 455.6 |
| ANA | 18/06/2026 | 2.119 | 30.8 | 440.6 |
| MARTA | 30/04/2026 | 1.695 | 30.4 | 434.3 |
| ANA | 30/03/2026 | 2.532 | 29.7 | 424.7 |

O pico: **ANA, 25/05/2026 — 91,03 horas**, ou 1.300% da capacidade diária.

**A causa, isolada no dado:** naquele dia, ANA tem 8.225 chamados. Destes, **2.047 estão marcados como `MANUAL`** e sozinhos respondem por **90,8 das 91,0 horas**. Os 6.178 massivos custam 0,2 hora. Ou seja: **o problema não é volume, é classificação.**

**Hipóteses de causa:**

1. **Erro de classificação do `Tipo de Liberação` (mais provável).** Trabalho feito em lote foi registrado como `MANUAL`. Duas mil investigações individuais em um dia é implausível — seriam 12 segundos por caso, sem pausa, o dia inteiro.
2. **O tempo médio não vale para tratamento em série.** Mesmo genuinamente "manual", tratar 2.047 casos idênticos em sequência não custa o tempo unitário cheio de cada um — há ganho de repetição que o modelo linear não captura.
3. **Registro em nome de fila, não de pessoa.** O campo `Colaborador(a)` pode identificar o **dono da fila** que executou a liberação, não quem gastou as horas.

**O que perguntar à área:**

- "Quando um analista libera vários documentos em uma mesma ação, isso é registrado como MASSIVO ou pode sair como MANUAL?"
- "O tempo médio da tabela de premissas foi medido em tratamento individual ou inclui casos em série?"
- "`Colaborador(a)` é quem executou ou o responsável pela fila?"

**Por que isso não invalida a análise:** afeta **12 de 698** pares colaborador-dia (1,7%) e **437,9 de 1.644 horas**. A direção de todos os achados — 94% do esforço no manual, `MANUAL01` como gargalo de SLA, `ZCLTAPDEF` como maior consumidora — **se mantém em qualquer das três hipóteses**, porque todas concentram ainda mais o esforço no lado manual. O que muda é a magnitude absoluta das horas, não o ranking nem a conclusão.

## 6.3 Achado 3 — o tempo médio é majoritariamente um valor padrão

**O fato:** **29 das 43 anomalias** da tabela de premissas têm exatamente `00:01:55`. Outras 4 compartilham `00:04:14` e 2 compartilham `00:00:44`. Apenas ~11 valores são genuinamente distintos.

**A leitura:** a tabela não é o resultado de uma cronoanálise por tipo de anomalia. É uma estimativa com um valor de preenchimento para o que não foi medido.

**Impacto real, e por que é menor do que parece:** as anomalias de maior volume e maior esforço — `ZCDFNPARC` (3,30 min), `ZCLTAPDEF` (4,23 min), `ZCAJALTO` (1,92 min) — estão entre as que têm valor próprio ou dominam o volume. As 29 com valor padrão somam pouco do esforço total. Ainda assim, **todo número em horas deste case é uma estimativa derivada de um parâmetro estimado**, e deve ser apresentado como tal.

**O que perguntar à área:** "Como o tempo médio de cada anomalia foi levantado? O `01:55` é medido ou é um padrão para o que não foi cronometrado?"

---

# 7. Perguntas prováveis da banca

**1. Por que dias corridos e não dias úteis?**

Porque a premissa diz apenas "2 dias", sem qualificar, e porque a operação **trabalha aos sábados** — há 5.342 tratamentos em sábados e nenhum em domingos na base. Usar calendário útil seg–sex perdoaria automaticamente todo atraso que atravessa o fim de semana, em um processo que não para no sábado. Calculei os dois: corridos dão 6,23% fora do SLA, úteis seg–sáb dão 3,12%. Adotei o mais conservador e deixei o outro visível na saída.

**2. E se o SLA de 2 dias for `< 2` e não `<= 2`?**

O indicador vai de 6,23% para 10,51% — 4,28 pontos. Adotei `<= 2` porque "prazo esperado: 2 dias" descreve um teto: quem entrega em 2 dias cumpriu o combinado; ler como `< 2` transformaria o prazo em 1 dia. Mas é uma convenção, não um fato, e o número alternativo está impresso na saída do script. Se a área confirmar a outra leitura, é uma constante para trocar.

**3. Por que você rateou o tratamento massivo? Não está subestimando o trabalho?**

Ao contrário — o cenário sem rateio **superestima** em 4,5×. Um tratamento massivo resolve o lote em uma execução; o maior lote da base tem 10.600 documentos. Atribuir o tempo cheio a cada um faria esse único lote custar 339 horas em um dia. O total do semestre iria de 1.644 para 7.347 horas, e a média de ANA seria de 29,8 h/dia. Mantive os dois cenários lado a lado na base exportada, justamente para que a premissa possa ser contestada e recalculada.

**4. Esse pico de 91 horas em um dia não invalida sua conta?**

Ele invalida a leitura literal daquele dia, não a análise. São 12 dias de 698 (1,7%) e 437 de 1.644 horas. E é um achado, não um erro meu: naquele dia, 2.047 chamados estão marcados como `MANUAL` e respondem por 90,8 das 91 horas. Ou a classificação do `Tipo de Liberação` está errada nesses lotes, ou o tempo médio não vale para tratamento em série. Nas três hipóteses que levantei, a conclusão da análise não muda — todas concentram ainda mais o esforço no lado manual. O que muda é a magnitude, e é por isso que a apresento como estimativa e trago a pergunta para a área.

**5. E se o tempo médio da tabela de premissas estiver errado?**

Provavelmente está impreciso, e eu sei disso: **29 das 43 anomalias têm exatamente `01:55`**, o que é claramente um valor padrão de preenchimento, não medição. Duas defesas: primeiro, as anomalias de maior volume e esforço estão entre as que têm valor próprio; segundo, e mais importante, **os rankings são robustos a escala**. Se todos os tempos estiverem 30% errados para cima, `ZCLTAPDEF` continua sendo um terço do esforço e o manual continua sendo 94% do custo. As conclusões dependem da proporção, não do valor absoluto.

**6. Por que você excluiu os 537 registros invertidos? Não está limpando o dado a seu favor?**

Excluí do **denominador do SLA**, não da base — eles continuam lá, marcados com `Registro Inconsistente`, e a contagem é impressa. E a exclusão me prejudica, não me favorece: se os tratasse como atraso negativo, eles entrariam como "dentro do SLA" e **melhorariam** meu indicador. Tratamento anterior à anomalia é impossível no fluxo do processo, e premiar um erro de dado com um indicador melhor seria pior que reportá-lo.

**7. Como você garante que o merge com os tempos médios está correto?**

Três validações explícitas na saída. Normalizei as chaves antes de casar — sem acento, sem espaço extra, caixa uniforme — porque divergência de grafia é o erro clássico. Usei `validate="many_to_one"` e comparei a contagem de linhas antes e depois, com `AssertionError` se mudasse: 163.811 → 163.811. E contei as linhas sem tempo médio após o merge: **zero**. Também reportei as 11 anomalias cadastradas nas premissas que não aparecem na base. O ponto não é que deu certo; é que o script mostra o número mesmo quando é zero.

**8. Seu SLA de 6,23% é bom ou ruim?**

Isoladamente não sei dizer — não há meta declarada na planilha, e é a primeira coisa que eu perguntaria à gestão. O que os dados dizem é mais útil: 80,7% são resolvidos no mesmo dia e o p90 está exatamente em 2 dias, ou seja, o processo está calibrado no limite do prazo. E o problema **não é difuso**: 53,4% de todas as quebras vêm de um único código. Um indicador agregado de 6,23% esconde que metade da dor está em um lugar só.

**9. Você olhou desempenho individual? ALFREDO tem 16,86% fora do SLA contra 2,00% de ANA.**

Olhei, e é justamente por isso que **não** apresento como desempenho individual. 5.355 das 6.192 quebras dele são de uma única anomalia, a `MANUAL01`, cuja fila está concentrada nele. Ele também é o único que trata `Clientes Telemedidos`. A diferença é de **composição de carteira**, não de produtividade. A recomendação que sai daí é redistribuir a fila `MANUAL01`, não cobrar a pessoa. Concluir o contrário seria um erro de análise com consequência real para alguém.

**10. Qual é a única recomendação que você faria se pudesse fazer só uma?**

Atacar a `MANUAL01`. É 16,6% do volume e 53,4% de todas as quebras de SLA, com taxa de falha interna de 19,93% contra 2,21% da maior anomalia em volume. Resolver essa fila sozinha levaria o indicador geral de 6,23% para aproximadamente 3,0%. É o maior retorno por unidade de esforço em toda a base.

**11. O que você faria com mais tempo?**

Quatro coisas, em ordem. **Um:** validar com a área as três perguntas de qualidade de dado — os 537 invertidos, a classificação manual/massivo nos dias de pico e a origem do tempo médio `01:55`. **Dois:** análise temporal — o volume de março é quase o triplo de janeiro e eu não sei por quê; se for sazonalidade, muda o dimensionamento da equipe. **Três:** cruzar `Tipo de Tratamento` com a anomalia para ranquear as regras por taxa de falso positivo, e propor calibragem das que mais geram "Sem Correção" — metade das retenções não tinha erro nenhum. **Quatro:** o dashboard gerencial com esses KPIs e uma simulação de capacidade: dado o volume projetado, quantas pessoas a fila exige.

**12. Por que você entregou dois rankings de "tempo gasto"?**

Porque "maior tempo gasto" é ambíguo e as duas leituras levam a decisões diferentes. Por tempo **total**, `ZCLTAPDEF` lidera com 33% de todo o esforço — é o alvo de automação. Por tempo **médio unitário**, lidera `ZFML_X_MF` com 6,17 min por caso — mas ela tem 58 chamados no semestre, 4,9 horas no total. Otimizá-la seria irrelevante. Entregar só o ranking unitário levaria a priorizar a anomalia errada, e é exatamente por isso que os dois precisam aparecer juntos.

---

## Apêndice — mapa dos arquivos

| Arquivo | Conteúdo |
|---|---|
| `Case_Processo_Seletivo.xlsx` | Cópia intocada da planilha original |
| `analise_anomalias.py` | Script da análise, ~940 linhas, comentado em português; decisões [D1]–[D7] no cabeçalho |
| `saida_execucao.txt` | Saída real da execução, do log de inspeção ao painel final |
| `resultado_analise.xlsx` | 9 abas: Premissas e Decisões · Base Enriquecida (163.811 × 22) · Saturação por Dia · Resumo Colaborador · Manual vs Massivo · Ranking Anomalias · Top3 Volume · Top3 Horas Totais · Top3 Tempo Unitário |
| `MEMORIAL_DO_CASE.md` / `.pdf` | Este documento |
