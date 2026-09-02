# Relatório de auditoria independente — case de anomalias

**Escopo.** Auditoria adversarial dos números do case. A análise foi refeita do zero
(`auditoria_independente.py`, saída em `saida_auditoria_independente.txt`) lendo apenas
`Case_Processo_Seletivo.xlsx`, **antes** de qualquer contato com `analise_core.py`,
`analise_anomalias.py`, `app.py`, `resultado_analise.xlsx`, `numeros.json` ou
`DOCUMENTO_ANALISE.docx`. Só depois os artefatos existentes foram abertos e confrontados.
Nada da análise existente foi alterado.

**Método de verificação.** Além do confronto entre as duas implementações, os 70+ campos de
`numeros.json` foram recalculados um a um com aritmética independente (script de conferência
em `/tmp/.../verif.py`), sem importar `analise_core`. O `.xlsx` de saída, o `.docx` e o
dashboard foram checados quanto a somas, denominadores e concordância entre si.

---

## 1. Tabela de confronto

Convenções da auditoria independente: dias corridos, fora do SLA = `dias > 2`, invertidos
mantidos no denominador, **sem** rateio do massivo. As da análise existente estão em `[D1]`–`[D7]`.

| # | Número | Auditoria independente | Análise existente | Status |
|---|---|---|---|---|
| 1 | Linhas da base | 163.811 | 163.811 | **Igual** |
| 2 | Documentos distintos | 112.282 | 112.282 | **Igual** |
| 3 | Anomalias distintas | 32 | 32 | **Igual** |
| 4 | Colaboradores | 8 | 8 | **Igual** |
| 5 | Linhas duplicadas | 0 | 0 | **Igual** |
| 6 | Registros com data invertida | 537 (536 × −2 dias, 1 × −14) | 537 (mesma distribuição) | **Igual** |
| 7 | Chamados fora do SLA (contagem) | 10.166 | 10.166 | **Igual** |
| 8 | **% fora do SLA** | 6,2059% (den. 163.811) | 6,2263% (den. 163.274) | **Convenção** `[D7]` |
| 9 | % fora, critério `< 2 dias` | 10,4773% / 10,5118% s/ invertidos | 10,5118% | **Igual** |
| 10 | % fora, dias úteis seg–sáb | — | 3,1199% | **Igual** (recalculado: 3,1199%) |
| 11 | Mesmo dia | 80,73% (den. total) | 80,9915% (den. avaliáveis) | **Convenção** `[D7]` |
| 12 | Média de dias | 0,4081 (todos) | 0,4161 (consistentes) | **Convenção** `[D7]` |
| 13 | Percentil 90 | 2 dias | 2 dias | **Igual** |
| 14 | Máximo de dias | 120 | 120 | **Igual** |
| 15 | Merge: linhas antes → depois | 163.811 → 163.811 | 163.811 → 163.811 | **Igual** |
| 16 | Linhas sem tempo após merge | 0 | 0 | **Igual** |
| 17 | Tempos cadastrados / não usados | 43 / 11 | 43 / 11 | **Igual** |
| 18 | Chaves duplicadas na tabela de tempos | 0 | 0 | **Igual** |
| 19 | Volume MANUAL / MASSIVO | 31.319 (19,119%) / 132.492 (80,881%) | idênticos | **Igual** |
| 20 | **Esforço total** | 7.347,52 h | 1.644,26 h | **Convenção** `[D4]` |
| 21 | **% do esforço MANUAL** | 20,97% | 93,69% | **Convenção** `[D4]` |
| 22 | Lotes massivos | 2.277 (mediana 7, máx. 10.600) | 2.277 (mediana 7, máx. 10.600) | **Igual** |
| 23 | Pares (colaborador, dia) | 697 | 697 | **Igual** |
| 24 | **Dias-colaborador > 7 h** | 157 (22,53%) | 33 (4,73%); 157 no cenário ingênuo | **Convenção** `[D4]` |
| 25 | **Top 3 por volume** | ZCDFNPARC, ZCAJALTO, MANUAL01 | idêntico | **Igual** |
| 26 | **Top 3 por tempo gasto** | ZCDFNPARC, ZCLTAPDEF, ZCAJALTO | ZCLTAPDEF, ZCAJALTO, MANUAL03 | **Convenção** `[D4]` |
| 27 | Top 3 por tempo unitário | ZFML_X_MF, MANUAL02, ZCDEVEXC | idêntico | **Igual** |
| 28 | MANUAL01 — volume | 27.214 (16,613%) | 27.214 (16,613%) | **Igual** |
| 29 | MANUAL01 — % de todas as quebras | 53,3642% | 53,3642% | **Igual** |
| 30 | MANUAL01 — % das próprias ocorrências | 19,9346% | 19,9346% | **Igual** |
| 31 | MANUAL01 — concentração em ALFREDO | 98,71% das quebras / 94,19% do volume | 98,71% (das quebras) | **Igual** |
| 32 | Ranking de quebras (5 primeiras) | 5.425 / 1.223 / 1.211 / 976 / 575 | idêntico | **Igual** |
| 33 | Impacto de zerar MANUAL01 | 6,2263% → 2,9037% (−3,3226 p.p.) | idêntico | **Igual** |
| 34 | Pico de carga | ANA 25/05, 8.225 chamados | ANA 25/05, 91,03 h | **Igual** (mesmo par) |
| 35 | Dias > 24 h | — | 12 pares, 1,72%, 437,88 h manuais | **Igual** (recalculado) |
| 36 | Tratamentos aos sábados / domingos | 5.342 / 0 | 5.342 / 0 | **Igual** |
| 37 | **Com correção / Sem correção** | **49,978% / 50,022%** | **0,0% / 50,022%** | **DIVERGENTE — erro** |

Nenhum outro campo de `numeros.json` divergiu. Quatro suspeitas iniciais foram descartadas
após identificar a definição usada: `sabados` (5.342 é sobre a base inteira, correto),
`pico_seg_por_caso` (é 7 h ÷ 2.047 casos manuais = 12,31 s, correto para a frase que sustenta),
`alvo_fte` (parte de `alvo_h_manual` = 509,98 h, coerente com o texto) e
`cenarios["< 2"]` (`< 2` implementado como `>= 2` para "fora", equivalente em inteiros).

---

## 2. Divergências e causa raiz

### 2.1 ERRO DE FATO — `com_correcao = 0,0%` (crítico, bloqueia o envio)

`numeros.json` traz `"com_correcao": 0.0`. O valor correto é **49,9778%**
(81.869 de 163.811). O `.docx` imprime isso na íntegra:

> *"A divisão entre corrigir e apenas liberar ficou em **0,0% contra 50,0%** no semestre.
> Metade das retenções, portanto, não tinha erro nenhum a corrigir."*
> — `DOCUMENTO_ANALISE.docx`, seção 2

A frase é autocontraditória: se metade não tinha erro, a outra metade tinha — e os dois
percentuais somam 50,0%, não 100%.

**Causa raiz.** Não é erro de conta nem de filtro: o campo **nunca foi calculado**.
`app.py:306` computa apenas `PCT_SEM_CORRECAO`; não existe contraparte para "Com correção"
em lugar nenhum do código. E `numeros.json` **não é gerado por nenhum script do repositório**
— não há um único `json.dump` no projeto —, apesar de `gerar_documento.js:4` afirmar que
*"os números não são digitados: vêm de numeros.json, produzido pelo mesmo núcleo"*. O arquivo
é mantido à mão, o campo ficou no default `0.0` e o gerador imprimiu sem validação.

**Correção.** `"com_correcao": 49.97771822405089`. A frase seguinte permanece válida.

**Risco sistêmico associado.** Enquanto `numeros.json` for editado manualmente, qualquer
número do `.docx` pode divergir do núcleo sem que nada acuse. Recomenda-se emitir o JSON a
partir de `analise_core.analisar()` e adicionar uma asserção de que percentuais
complementares somam 100%.

### 2.2 AFIRMAÇÃO NÃO SUSTENTADA — a evidência do §3.1 contradiz os dados

> *"comparando semana a semana, o percentual fora do prazo sobe e desce em momentos que não
> coincidem com as semanas de maior volume"* — `DOCUMENTO_ANALISE.docx`, seção 3.1

Recálculo independente:

| Agregação | Correlação volume × % fora | Período de maior volume | É também o pior em % fora? |
|---|---|---|---|
| Mensal | Pearson **+0,73** | 2026-03 (45.554) | **Sim** — 16,22%, o maior do semestre |
| Semanal | Pearson −0,20 / Spearman −0,45 | 2026-03-09 (17.780) | 3º pior (39,2%) |

As duas semanas com % fora acima dela têm **313 e 188 chamados** — ruído, não sinal. No nível
mensal, pico de volume e pico de atraso são **o mesmo mês**.

**A conclusão está certa; a evidência citada, não.** O atraso realmente vem de fila travada,
e a prova está disponível na própria base: **72,7% de todas as quebras do semestre (7.390 de
10.166) estão em março**, e **5.341 das 7.390 quebras de março são MANUAL01 tratadas por
ALFREDO**. Trocar a frase pela concentração temporal fortalece o argumento em vez de o expor.

### 2.3 Diferenças de convenção — todas declaradas, nenhuma é erro

| Convenção | Efeito medido | Declarada? | Onde |
|---|---|---|---|
| `[D4]` rateio do massivo | Esforço 7.347,5 h → 1.644,3 h (4,47×); MANUAL vai de 20,97% para **93,69%** do esforço; estouros de 157 para 33; muda o **top 3 por tempo** | **Sim, exemplarmente** | `.docx` §6.2 (com os dois cenários lado a lado), aba *Premissas e Decisões* do `.xlsx`, `[D4]` em `analise_core.py`, colunas `Horas Atribuídas` e `Horas (Cenário Ingênuo)` na base exportada |
| `[D7]` invertidos fora do denominador | % fora 6,2059% → 6,2263% | **Sim** | `.docx` §4.1 e §6.2, `[D7]`, coluna `Registro Inconsistente` |
| `[D2]` `<= 2` e não `< 2` | 6,23% vs 10,51% | **Sim** | `.docx` §6.2, com o cenário alternativo publicado |
| `[D1]` dias corridos | 6,23% vs 3,12% em dias úteis | **Sim** | `.docx` §6.2, coluna `Dias Úteis (Seg-Sáb)` |
| `[D5]` "maior tempo" ambíguo | Três rankings entregues | **Sim** | `.docx` §3.5, três abas no `.xlsx` |

`[D4]` é a de maior consequência e merece destaque: **o achado-manchete do case
("19% do volume, 94% do esforço") é inteiramente dirigido por essa convenção.** Sem rateio,
o contraste desaparece (19,1% do volume, 21,0% do esforço). A análise não esconde isso —
publica o fator 4,47×, o cenário ingênuo e as duas colunas na base. É uma escolha defensável e
declarada. Mas quem apresentar precisa saber que a manchete é uma consequência da premissa,
não uma leitura direta do dado; se o avaliador rejeitar o rateio, o achado inverte de sinal.

---

## 3. Aderência ao enunciado

### 3.1 Aba *Expectativa* (o enunciado real do case)

| Item pedido | Entregue | Onde |
|---|---|---|
| 1. Dashboard gerencial com KPIs | **Sim** | `app.py` — cartões de topo (`app.py:290-320`) e aba *Diagnóstico* (§1.1 a §1.4) |
| 2. Análise crítica: padrões, tendências, desvios, riscos | **Sim** | `.docx` §3 e §4; app, abas *Diagnóstico* e *Achados de qualidade de dado* (3 achados) |
| 3. Recomendações objetivas e fundamentadas | **Sim** | `.docx` §5 (4 frentes, 2 com impacto quantificado); app, aba *Recomendações* |
| 4. Racional analítico justificado | **Sim** | `.docx` §6; app, aba *Racional* (por que estes KPIs, decisões, validações) |
| Apresentação em 10 min | Não aplicável a esta auditoria | — |

### 3.2 Os quatro cálculos solicitados nesta auditoria

| Item | Entregue pela análise existente | Onde |
|---|---|---|
| 1. Dias entre datas + flag de SLA (2 dias) | **Sim** | `preparar_e_calcular_sla()`; colunas `Dias para Tratamento`, `Dentro do SLA`, `Fora do SLA` |
| 2. Merge com Tempos Médios das Premissas | **Sim**, com `validate="many_to_one"` e asserção de contagem | `merge_tempos_medios()`; colunas `Tempo Médio (s)`/`(min)` |
| 3. Horas por colaborador por dia + flag > 7 h | **Sim** | `resumo_saturacao()`; aba *Saturação por Dia*; colunas `Horas do Colaborador no Dia`, `Estourou Saturação` |
| 4. % fora do SLA, manual × massivo, top 3 por volume e por tempo | **Sim** | `distribuicao_liberacao()`, `ranking_anomalias()`; abas *Manual vs Massivo*, *Top3 Volume*, *Top3 Horas Totais*, *Top3 Tempo Unitário* |

Nenhum item pedido ficou de fora.

---

## 4. Integridade

### 4.1 Checagens que passaram

| Verificação | Resultado |
|---|---|
| Soma das partes = total (dentro + fora do SLA) | 153.108 + 10.166 = 163.274 avaliáveis; + 537 nulos = 163.811 |
| % Manual + % Massivo (volume) | 100,000000% |
| % Manual + % Massivo (esforço) | 100,000000% |
| Ranking de anomalias: soma de chamados | 163.811 (32 linhas, todas as anomalias) |
| Ranking de anomalias: soma de horas | 1.644,2553 h = total |
| Soma das quebras por anomalia | 10.166 = total fora do SLA |
| Saturação: soma de horas / de chamados | 1.644,2553 h / 163.811 |
| Resumo por colaborador: soma de horas / chamados / dias | 1.644,2553 h / 163.811 / 697 pares |
| Merge: contagem de linhas preservada | 163.811 → 163.811, 0 sem tempo, 0 chave duplicada |
| Base Enriquecida: linhas e duplicatas | 163.811 linhas, 0 duplicatas integrais |
| `dados/base.parquet` × aba *Base de Dados* | Conteúdo e dtypes **idênticos** — o cache não desvia o app |
| `Horas do Colaborador no Dia` × groupby | Idêntico ao `transform("sum")` recalculado |
| `.docx` × `.xlsx` × `numeros.json` × app | **Concordam** em todos os números conferidos, **exceto** o item 2.1 |

Não há dupla contagem em groupby, inflação de linhas no merge, percentual sobre base errada
nem empate de ranking resolvido arbitrariamente (verifiquei as três fronteiras de top 3:
27.214 vs 23.428 no volume; 231,14 h vs 219,34 h no tempo; 6,02 vs 4,23 min no unitário —
nenhuma é empate; o empate quádruplo em 4,23 min fica fora do corte).

### 4.2 Fragilidades — não são erros, mas devem ser corrigidas ou ditas

1. **Série semanal sem piso de denominador.** `serie_temporal()` não filtra semanas de baixo
   volume. Duas semanas com 313 e 188 chamados aparecem com 66,1% e 39,4% fora do SLA e
   dominam visualmente o gráfico do app. Adicionar um piso (ex.: n ≥ 500) ou plotar a contagem
   junto do percentual.
2. **Denominadores mistos para o mesmo indicador.** O headline e o corte por *Origem*
   (`distribuicao_por`) usam avaliáveis (163.274); os cortes por *Anomalia*
   (`ranking_anomalias`) e por *Colaborador* (`perfil_colaborador`) usam o volume total. A
   diferença é ≤ 0,01 p.p., mas as duas convenções convivem na mesma frase do §3.2
   ("19,9% das próprias ocorrências, contra 2,2% da anomalia de maior volume"). Unificar.
3. **Sumário executivo com denominador implícito errado.** *"A operação tratou 163.811
   retenções… Desse total, 6,23% ficaram fora do prazo"* — o 6,23% é sobre 163.274. O §3.1 e o
   §4.1 declaram corretamente; só o sumário mistura. Trocar por *"dos 163.274 avaliáveis"*.
4. **Janela temporal imprecisa no sumário.** *"tratou … entre 06/01/2026 e 30/06/2026"* é a
   janela das **anomalias**; os tratamentos vão até **05/08/2026** (valor correto no cartão de
   KPI da mesma página).
5. **`of_dist` truncado.** O blob soma 27.210 e não os 27.214 da MANUAL01 (7 baldes; faltam
   dias 7 e 13 e o registro invertido). O texto cita apenas os dias 0–4, todos corretos, mas o
   campo não representa o que o nome promete.
6. **`Estourou Saturação` é flag por linha na base exportada.** Somar a coluna dá 70.223,
   quando os estouros são 33 pares. O `.docx` usa 33 corretamente; quem abrir o `.xlsx` e
   somar a coluna chega a outro número. Vale uma nota na aba.
7. **Números literais no texto.** O `2,2%` aparece hardcoded em `app.py:541` e no `.docx` §3.2.
   Hoje bate (2,2077%), mas não acompanha recálculo.
8. **`lote_max` = 10.600.** Sob `[D4]`, um lote de 10.600 documentos custa 1,92 minuto no
   total. A premissa está declarada e o `.docx` a discute em §6.2 — mas é o ponto único de
   maior alavancagem sobre todos os números de horas do case.

---

## 5. Recálculo independente dos cinco números de destaque

**1. % fora do SLA.** `dias > 2` sobre 163.274 avaliáveis = 10.166 / 163.274 = **6,2263%**.
Sem excluir os 537 invertidos: 10.166 / 163.811 = 6,2059%. Sob `< 2 dias`: 10,5118%.
Sob dias úteis seg–sáb: 3,1199%. Todos batem com o publicado. Somas fecham
(153.108 + 10.166 + 537 = 163.811). **Confirmado.**

**2. Volume × esforço, manual vs massivo.** Volume: 31.319 / 163.811 = 19,1190% manual;
132.492 / 163.811 = 80,8810% massivo; somam 100%. Esforço **com** rateio `[D4]`:
1.540,54 h / 1.644,26 h = **93,6925%** manual e 6,3075% massivo; somam 100%. Esforço **sem**
rateio: 1.540,54 h / 7.347,52 h = **20,9669%** manual. Custo unitário: 2,9513 min manual
contra 0,0470 min massivo = **62,84×**. Aritmética confirmada nas duas convenções; o contraste
publicado depende inteiramente de `[D4]`. **Confirmado, com a ressalva do item 2.3.**

**3. Concentração em MANUAL01.** Volume 27.214 = 16,6130% da base. Quebras 5.425 =
**53,3642%** das 10.166 e **19,9346%** das próprias ocorrências. ALFREDO responde por 5.355
das 5.425 quebras = **98,7097%** (e por 25.632 dos 27.214 registros = 94,19% do volume — os
dois números são diferentes e o `.docx` usa o correto para a frase que faz). A soma das
quebras por anomalia fecha em 10.166. Distribuição completa de dias na MANUAL01:
`{−2: 1, 0: 19.222, 1: 2.430, 2: 136, 3: 3.241, 4: 2.166, 5: 13, 6: 2, 7: 2, 13: 1}` — o
"vale seguido de novo pico" descrito no §3.2 existe de fato. **Confirmado.**

**4. Dias-colaborador acima de 7 h.** 697 pares (colaborador, dia). Com rateio `[D4]`:
**33** pares > 7 h = 4,7346%. Sem rateio: **157** = 22,5251%. Soma das horas do groupby =
1.644,2553 h = total, sem perda nem duplicação. Pico: ANA em 25/05/2026, 8.225 chamados,
91,0294 h — dos quais 2.047 manuais respondem por 90,8081 h. A conta dos "12 segundos por
caso" é 7 h ÷ 2.047 = 12,3107 s, correta para a afirmação que sustenta. **Confirmado.**

**5. Os três rankings.**
- *Volume*: ZCDFNPARC 44.208 (26,987%), ZCAJALTO 37.635 (22,975%), MANUAL01 27.214 (16,613%).
  4º lugar 23.428 — sem empate na fronteira. **Idêntico nas duas análises.**
- *Tempo total, com rateio* `[D4]`: ZCLTAPDEF 542,57 h (32,998%), ZCAJALTO 287,56 h (17,489%),
  MANUAL03 231,14 h (14,057%). 4º = ZCDFNPARC 219,34 h — sem empate. **Confirmado.**
- *Tempo total, sem rateio*: ZCDFNPARC 2.431,44 h, ZCLTAPDEF 1.652,98 h, ZCAJALTO 1.202,23 h.
  **A convenção troca o 1º lugar e expulsa ZCDFNPARC do pódio.** Declarada.
- *Tempo unitário*: ZFML_X_MF 6,17 min, MANUAL02 6,05 min, ZCDEVEXC 6,02 min. 4º lugar é um
  empate quádruplo em 4,23 min, **fora do corte** — o top 3 não é arbitrário. **Confirmado.**

---

## 6. Veredito

**Os números estão corretos.** Das ~75 grandezas publicadas e recalculadas com aritmética
independente, **uma** está errada. Todas as demais reconciliam ao dígito, incluindo as que
dependem de convenção — quando reimplementadas sob a convenção declarada, batem exatamente.
Não encontrei denominador contaminado, dupla contagem em groupby, merge inflando linhas,
percentual sobre base errada nem empate de ranking resolvido no escuro. As somas fecham, os
percentuais somam 100%, a contagem de linhas é preservada em todo o pipeline, o cache Parquet
é idêntico à planilha, e `.docx`, `.xlsx`, `numeros.json` e o dashboard concordam entre si.

O tratamento das convenções é acima da média: cada escolha ambígua está declarada em três
lugares, com o cenário alternativo calculado e publicado ao lado. `[D4]` é a decisão mais
consequente do case e está exposta com honestidade, incluindo o fator 4,47×.

### Antes de enviar

**Bloqueante:**
1. Corrigir `com_correcao` para **49,9777%** em `numeros.json` e regerar o `.docx`. A frase
   *"0,0% contra 50,0%"* é indefensável numa banca — dois percentuais complementares que não
   somam 100 são a primeira coisa que um avaliador testa.

**Recomendado (baixo custo, alto retorno):**
2. Reescrever a frase do §3.1 sobre volume × atraso semanal. Como está, é refutável em trinta
   segundos: o mês de maior volume é o de maior % fora, com correlação +0,73. Substituir pela
   evidência mais forte que já existe na base — **72,7% das quebras em março, 5.341 delas
   MANUAL01/ALFREDO**.
3. Corrigir o denominador implícito e a janela temporal no sumário executivo (§4.2, itens 3 e 4).
4. Colocar piso de denominador na série semanal, ou plotar o volume junto do percentual.

**Estrutural, para depois da entrega:**
5. Gerar `numeros.json` a partir de `analise_core.analisar()` em vez de mantê-lo à mão, com
   asserção de que percentuais complementares somem 100%. É a causa raiz do item 1, e o
   comentário em `gerar_documento.js:4` hoje descreve um processo que não existe.
6. Unificar o denominador de "% Fora do SLA" entre os cortes (§4.2, item 2).

**Na apresentação, esteja pronto para uma pergunta:** *"e se eu não aceitar o rateio do
massivo?"* A resposta correta é que o esforço vai a 7.348 h, os estouros a 22,5% e a MANUAL01
continua com 53,4% das quebras — o achado sobre SLA sobrevive intacto, porque não depende de
tempo nenhum. É o achado sobre esforço que se inverte. Esse é o ponto forte da entrega e vale
dizê-lo antes de ser perguntado.
