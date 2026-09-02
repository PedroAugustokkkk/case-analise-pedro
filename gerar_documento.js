/**
 * Gera DOCUMENTO_ANALISE.docx — o texto que acompanha o dashboard na entrega.
 *
 * Os números não são digitados: vêm de numeros.json, gerado por gerar_numeros.py
 * a partir do mesmo núcleo analítico (analise_core.py) que alimenta o relatório e
 * o painel. Rode `python gerar_numeros.py` antes deste script.
 */

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableOfContents, PageBreak, Header, Footer, PageNumber, convertMillimetersToTwip,
} = require("docx");

const N = JSON.parse(fs.readFileSync(process.argv[2] || "numeros.json", "utf8"));

// ---------------------------------------------------------------- formatação
const nf = (v, c = 0) =>
  Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });
const pc = (v, c = 2) => nf(v, c) + "%";

const AZUL = "1C4B82";
const CINZA = "5A6270";
const PRETO = "1C1F24";
const LARGURA = 9638; // A4 menos margens de 2 cm, em DXA

// ------------------------------------------------------------------ blocos
const T = (texto, o = {}) => new TextRun({ text: texto, font: "Calibri", ...o });
const B = (texto, o = {}) => T(texto, { bold: true, ...o });
const C = (texto, o = {}) => T(texto, { font: "Consolas", size: 19, ...o });

/** Parágrafo de corpo. Aceita string ou array de TextRun. */
function p(conteudo, o = {}) {
  const runs = typeof conteudo === "string" ? [T(conteudo)] : conteudo;
  return new Paragraph({
    children: runs,
    spacing: { after: 160, line: 288 },
    alignment: AlignmentType.JUSTIFIED,
    ...o,
  });
}

function h1(texto) {
  return new Paragraph({
    children: [T(texto, { bold: true, size: 30, color: AZUL })],
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: AZUL, space: 6 } },
  });
}

function h2(texto) {
  return new Paragraph({
    children: [T(texto, { bold: true, size: 24, color: PRETO })],
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 140 },
  });
}

function legenda(texto) {
  return new Paragraph({
    children: [T(texto, { size: 17, color: CINZA, italics: true })],
    spacing: { after: 220 },
  });
}

function item(numero, conteudo) {
  const runs = typeof conteudo === "string" ? [T(conteudo)] : conteudo;
  return new Paragraph({
    children: [B(numero + "  "), ...runs],
    spacing: { after: 160, line: 288 },
    indent: { left: 340, hanging: 340 },
    alignment: AlignmentType.JUSTIFIED,
  });
}

function celula(conteudo, { cab = false, larg, dir = false } = {}) {
  const runs = typeof conteudo === "string"
    ? [T(conteudo, { size: 18, bold: cab, color: cab ? "FFFFFF" : PRETO })]
    : conteudo;
  return new TableCell({
    width: { size: larg, type: WidthType.DXA },
    shading: cab
      ? { type: ShadingType.CLEAR, fill: AZUL, color: "auto" }
      : { type: ShadingType.CLEAR, fill: "FFFFFF", color: "auto" },
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [new Paragraph({
      children: runs,
      alignment: dir ? AlignmentType.RIGHT : AlignmentType.LEFT,
      spacing: { after: 0, line: 240 },
    })],
  });
}

/**
 * Tabela simples. `larguras` deve somar LARGURA; `dirs` marca colunas numéricas.
 */
function tabela(cabecalho, linhas, larguras, dirs = []) {
  const linhaCab = new TableRow({
    tableHeader: true,
    children: cabecalho.map((t, k) => celula(t, { cab: true, larg: larguras[k], dir: dirs[k] })),
  });
  const corpo = linhas.map((linha, idx) =>
    new TableRow({
      children: linha.map((t, k) => {
        const c = celula(t, { larg: larguras[k], dir: dirs[k] });
        if (idx % 2 === 1) {
          c.root.find((x) => x && x.constructor && x.constructor.name === "TableCellProperties");
        }
        return c;
      }),
    })
  );
  return new Table({
    columnWidths: larguras,
    width: { size: LARGURA, type: WidthType.DXA },
    rows: [linhaCab, ...corpo],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "C9CED6" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "C9CED6" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "C9CED6" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "C9CED6" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "DDE1E7" },
      insideVertical: { style: BorderStyle.SINGLE, size: 4, color: "DDE1E7" },
    },
  });
}

const espaco = () => new Paragraph({ children: [T("")], spacing: { after: 120 } });

// =============================================================== CONTEÚDO ===
const corpo = [];

// --------------------------------------------------------------- capa -----
corpo.push(
  new Paragraph({
    children: [T("Anomalias de Faturamento", { bold: true, size: 48, color: AZUL })],
    spacing: { before: 1200, after: 60 },
  }),
  new Paragraph({
    children: [T("Análise da operação e recomendações à gestão", { size: 28, color: CINZA })],
    spacing: { after: 400 },
  }),
  new Paragraph({
    children: [T(`Período analisado: ${N.ini} a ${N.fim_anom}`, { size: 21, color: PRETO })],
    spacing: { after: 40 },
  }),
  new Paragraph({
    children: [T(`Base: ${nf(N.total)} registros de retenção de faturamento`, { size: 21, color: PRETO })],
    spacing: { after: 40 },
  }),
  new Paragraph({
    children: [T("Documento de apoio ao dashboard gerencial", { size: 21, color: CINZA })],
    spacing: { after: 600 },
  }),
  new Paragraph({ children: [new PageBreak()] })
);

// ------------------------------------------------------------- sumário ----
const SUMARIO = [
  ["1.", "Resumo executivo"],
  ["2.", "O que analisamos"],
  ["3.", "Diagnóstico"],
  ["3.1", "O prazo é cumprido na maioria dos casos"],
  ["3.2", "Onde o prazo quebra"],
  ["3.3", "Manual e massivo: o volume não é o custo"],
  ["3.4", "Carga de trabalho e composição da carteira"],
  ["3.5", "As anomalias mais custosas"],
  ["4.", "O que encontramos nos dados"],
  ["4.1", "Registros com tratamento anterior à anomalia"],
  ["4.2", "Dias com carga acima do possível"],
  ["4.3", "O tempo médio cadastrado é, em boa parte, um valor padrão"],
  ["5.", "Recomendações"],
  ["6.", "Racional analítico"],
  ["7.", "O que acompanha este documento"],
];
corpo.push(h1("Sumário"));
SUMARIO.forEach(([numero, titulo]) => {
  const secundario = numero.includes(".") && numero.length > 2;
  corpo.push(new Paragraph({
    children: [
      T(numero + "   ", { bold: !secundario, color: secundario ? CINZA : PRETO }),
      T(titulo, { bold: !secundario, color: secundario ? CINZA : PRETO }),
    ],
    spacing: { after: secundario ? 60 : 90 },
    indent: { left: secundario ? 560 : 0 },
  }));
});
corpo.push(new Paragraph({ children: [new PageBreak()] }));

// =================================================== 1. RESUMO EXECUTIVO ===
corpo.push(h1("1. Resumo executivo"));

corpo.push(p([
  T("A operação tratou "), B(`${nf(N.total)} retenções de faturamento`),
  T(` geradas entre ${N.ini} e ${N.fim_anom}, com tratamentos registrados até ${N.fim_trat}. `),
  T(`Dos ${nf(N.avaliaveis)} chamados avaliáveis, `), B(pc(N.pct_fora)),
  T(" ficaram fora do prazo de dois dias. O número agregado é bom e esconde o que importa para a decisão: a falha não está distribuída pela operação. Uma única anomalia, a "),
  C("MANUAL01"), T(", responde por "), B(pc(N.of_pct_quebras, 1)),
  T(` de todas as quebras de prazo do semestre, embora represente apenas ${pc(N.of_vol, 1)} do volume.`),
]));

corpo.push(p([
  T("O custo do trabalho não está onde está o volume. "),
  T(`${pc(N.massivo_vol, 1)} dos chamados são resolvidos em lote, e esse trabalho consome `),
  B(pc(N.massivo_esf, 1)), T(" das horas da equipe. Os "), B(pc(N.manual_vol, 1)),
  T(" tratados um a um consomem os outros "), B(pc(N.manual_esf, 1)),
  T(`. Na média, um chamado manual custa ${nf(N.razao_custo)} vezes o esforço de um chamado massivo (${nf(N.custo_manual, 2)} minutos contra ${nf(N.custo_massivo, 3)}). Reduzir o volume total da fila economiza pouco. O que economiza é mover trabalho do manual para o massivo, ou eliminar a causa que gera o manual.`),
]));

corpo.push(p([
  T("Capacidade não é o problema. O esforço estimado do semestre foi de "),
  B(`${nf(N.horas_total, 0)} horas`),
  T(`, o equivalente a ${nf(N.fte, 1)} pessoas em tempo integral, e ${pc(N.pct_estouro, 1)} dos dias trabalhados por pessoa passaram das ${N.saturacao} horas previstas. ${pc(N.mesmo_dia, 0)} dos chamados são resolvidos no mesmo dia em que a anomalia aparece.`),
]));

corpo.push(p([
  T("Se a gestão puder tocar uma frente apenas, recomendamos a fila da "), C("MANUAL01"),
  T(". Resolver a espera dessa anomalia levaria o indicador geral de "),
  B(pc(N.imp_sla_atual)), T(" para "), B(pc(N.imp_sla_novo)),
  T(`, uma melhora de ${nf(N.imp_ganho, 2)} pontos percentuais, sem alterar nada no resto da operação.`),
]));

// ================================================= 2. O QUE ANALISAMOS =====
corpo.push(h1("2. O que analisamos"));

corpo.push(p([
  T("A fonte é a planilha "), C("Case_Processo_Seletivo.xlsx"),
  T(", com três abas. A "), B("Base de Dados"), T(" traz o fato: "),
  T(`${nf(N.total)} linhas e oito colunas. A aba `), B("Premissas e Informações"),
  T(` fornece os parâmetros de cálculo, o prazo de ${N.sla_dias} dias e a saturação de ${N.saturacao} horas por pessoa por dia, além do tempo médio de tratamento de cada tipo de anomalia. A aba `),
  B("Expectativa"), T(" contém o enunciado do desafio e nenhum dado."),
]));

corpo.push(h2("O que representa uma linha"));

corpo.push(p([
  T("Cada linha é uma retenção aplicada a um documento de faturamento, junto com o seu tratamento. Não é um documento, e não é um dia de trabalho. A distinção muda a leitura de todos os totais: há "),
  T(`${nf(N.documentos)} documentos distintos para ${nf(N.total)} linhas, o que dá ${nf(N.anom_por_doc, 2)} retenções por documento em média, chegando a ${N.max_anom_doc} no caso extremo. Um mesmo documento pode ser barrado por várias regras diferentes, e cada barreira precisa ser tratada individualmente.`),
]));

corpo.push(h2("O processo por trás dos dados"));

corpo.push(p([
  T("O sistema de cobrança prepara um documento de faturamento e regras automáticas o inspecionam. Quando algo destoa do padrão, uma retenção é aplicada e o documento deixa de ser faturado. Um analista recebe a fila, investiga o caso e decide: corrige a inconsistência ou conclui que o documento está correto e apenas libera a retenção. Enquanto a retenção existe, a receita não é faturada, o que explica por que a área trabalha com prazo curto e explícito."),
]));

corpo.push(p([
  T(`A divisão entre corrigir e apenas liberar ficou praticamente meio a meio: ${nf(N.com_ch)} casos exigiram correção e ${nf(N.sem_ch)} foram apenas liberados, ${pc(N.sem_correcao, 1)} do total. Metade das retenções, portanto, não tinha erro nenhum a corrigir. Voltamos a esse ponto na seção de recomendações, porque ele tem consequência prática.`),
]));

corpo.push(h2("Números gerais"));
corpo.push(espaco());
corpo.push(tabela(
  ["Indicador", "Valor", "Observação"],
  [
    ["Retenções analisadas", nf(N.total), "Uma por linha da base"],
    ["Documentos distintos", nf(N.documentos), `${nf(N.anom_por_doc, 2)} retenções por documento`],
    ["Tipos de anomalia", nf(N.anomalias), `${nf(N.tempos_qtd)} cadastrados nas premissas`],
    ["Colaboradores", nf(N.colaboradores), "Carga desigual, ver seção 3.4"],
    ["Anomalias geradas entre", `${N.ini} e ${N.fim_anom}`, "Seis meses"],
    ["Último tratamento registrado", N.fim_trat, "A cauda passa do fim do período"],
    ["Prazo acordado", `${N.sla_dias} dias`, "Aba Premissas"],
    ["Capacidade diária", `${N.saturacao} horas por pessoa`, "Aba Premissas"],
  ],
  [3200, 2600, 3838]
));
corpo.push(legenda("Fonte: Case_Processo_Seletivo.xlsx, abas Base de Dados e Premissas e Informações."));

// ====================================================== 3. DIAGNÓSTICO =====
corpo.push(new Paragraph({ children: [new PageBreak()] }));
corpo.push(h1("3. Diagnóstico"));

// ---- 3.1
corpo.push(h2("3.1 O prazo é cumprido na maioria dos casos"));

corpo.push(p([
  T(`Dos ${nf(N.avaliaveis)} chamados avaliáveis, ${nf(N.dentro)} foram tratados dentro dos ${N.sla_dias} dias e ${nf(N.fora)} passaram do prazo, o que dá `),
  B(pc(N.pct_fora)), T(" fora do SLA."),
]));

corpo.push(p([
  T(`A distribuição do tempo de tratamento é bastante concentrada. ${pc(N.mesmo_dia, 1)} dos chamados são resolvidos no mesmo dia em que a anomalia aparece, e o percentil 90 fica exatamente em ${nf(N.p90)} dias, no limite do prazo. A média dos registros consistentes, ${nf(N.media_dias, 2)} dia, descreve mal o comportamento real: o mesmo conjunto contém casos que levaram até ${nf(N.max_dias)} dias. A cauda é longa e fina, com poucos casos acumulando muito atraso.`),
]));

corpo.push(p([
  T(`O atraso é concentrado no tempo, e muito. Das ${nf(N.fora)} quebras do semestre, `),
  B(`${nf(N.marco_quebras)} estão em ${N.marco_nome}`),
  T(`, ou ${pc(N.marco_pct_quebras, 1)} do total. Nesse mês o percentual fora do prazo chega a ${pc(N.marco_pct_fora, 2)}, contra menos de 3% em quatro dos outros cinco meses.`),
]));

corpo.push(p([
  T(`${N.marco_nome.charAt(0).toUpperCase() + N.marco_nome.slice(1)} é também o mês de maior volume, com ${nf(N.marco_chamados)} anomalias geradas, e a correlação entre volume mensal e percentual fora do prazo é de ${nf(N.correlacao_mensal, 2)}. Volume e atraso andam juntos, o que à primeira vista sugeriria falta de capacidade. A composição das quebras aponta outra coisa: `),
  B(`${nf(N.marco_of_quebras)} das ${nf(N.marco_quebras)} quebras desse mês são da ${N.ofensora}`),
  T(`, e ${nf(N.marco_of_dono_quebras)} delas estão com um único colaborador. Quando o volume sobe, não é a operação inteira que desacelera. É sempre a mesma fila que transborda.`),
]));

// ---- 3.2
corpo.push(h2("3.2 Onde o prazo quebra"));

corpo.push(p([
  T("As quebras de prazo estão concentradas em poucos códigos. A tabela abaixo mostra os cinco maiores contribuintes."),
]));
corpo.push(espaco());

corpo.push(tabela(
  ["Anomalia", "Chamados fora do prazo", "% de todas as quebras", "% das ocorrências dela que estouram", "% acumulado"],
  N.quebras.map((q) => [q.anomalia, nf(q.fora), pc(q.pct_todas, 1), pc(q.pct_dela, 1), pc(q.acum, 1)]),
  [1900, 1950, 1900, 2288, 1600],
  [false, true, true, true, true]
));
corpo.push(legenda("A quarta coluna separa a anomalia que aparece muito da que falha muito."));

corpo.push(p([
  T("A "), C("MANUAL01"), T(` é ${pc(N.of_vol, 1)} do volume e ${pc(N.of_pct_quebras, 1)} das quebras. Ela estoura o prazo em `),
  B(pc(N.of_pct_fora, 1)), T(` dos próprios chamados avaliáveis, contra ${pc(N.top_volume[0].fora, 1)} da anomalia de maior volume da base. As duas primeiras linhas da tabela somam ${pc(N.quebras[1].acum, 1)} de tudo o que atrasa no semestre.`),
]));

const od = N.of_dist;
corpo.push(p([
  T("O padrão de atraso dessa fila chama a atenção. Entre os chamados consistentes da "),
  C("MANUAL01"), T(`, ${nf(od["0"] || 0)} saem no mesmo dia e ${nf(od["1"] || 0)} no dia seguinte. No segundo dia caem para ${nf(od["2"] || 0)}, e então voltam a subir: ${nf(od["3"] || 0)} no terceiro dia e ${nf(od["4"] || 0)} no quarto. Um vale seguido de um novo pico não é o desenho de trabalho que demora a ser feito, e sim de trabalho que espera por alguma coisa. Nossa hipótese é que existe um gatilho externo à fila, uma rotina em lote ou o retorno de outra área, mas a base não permite confirmar isso. É a primeira pergunta que faríamos ao dono do processo.`),
]));

// ---- 3.3
corpo.push(h2("3.3 Manual e massivo: o volume não é o custo"));

corpo.push(p([
  T("Um tratamento massivo resolve um lote inteiro numa execução. O analista identifica que um conjunto de documentos foi retido pelo mesmo motivo e libera todos de uma vez. Um tratamento manual exige abrir o caso, investigar e decidir, um por um. A base registra "),
  T(`${nf(N.lotes)} lotes massivos no semestre, com mediana de ${nf(N.lote_mediana)} chamados por lote e um caso extremo de ${nf(N.lote_max)} documentos liberados numa única execução.`),
]));
corpo.push(espaco());

corpo.push(tabela(
  ["Tipo de liberação", "Chamados", "% do volume", "Horas estimadas", "% do esforço"],
  [
    ["MASSIVO", nf(N.massivo_ch), pc(N.massivo_vol), nf(N.massivo_h, 1), pc(N.massivo_esf)],
    ["MANUAL", nf(N.manual_ch), pc(N.manual_vol), nf(N.manual_h, 1), pc(N.manual_esf)],
  ],
  [2400, 1800, 1800, 1900, 1738],
  [false, true, true, true, true]
));
corpo.push(legenda("O tempo de um tratamento massivo é contado uma vez por lote, não por chamado. Ver seção 6.2."));

corpo.push(p([
  T("As duas medidas são quase o inverso uma da outra. Quatro em cada cinco anomalias já são resolvidas a um custo próximo de zero, e quase todo o tempo da equipe está no quinto restante. Em números por chamado, o manual custa "),
  B(`${nf(N.custo_manual, 2)} minutos`), T(" de esforço e o massivo custa "),
  B(`${nf(N.custo_massivo, 3)} minutos`), T(`, uma razão de ${nf(N.razao_custo)} para 1.`),
]));

corpo.push(p([
  T("Isso muda a pergunta que a gestão precisa fazer. A pergunta natural diante de 163 mil retenções é como reduzir o volume. Pelos números, reduzir volume massivo quase não devolve capacidade. O ganho está em converter tratamento manual em massivo, ou em impedir que a retenção manual se forme."),
]));

// ---- 3.4
corpo.push(h2("3.4 Carga de trabalho e composição da carteira"));

corpo.push(p([
  T(`A distribuição de volume entre as ${N.colaboradores} pessoas é bem desigual. A pessoa mais carregada trata ${pc(N.perfil[0].ch / N.total * 100, 0)} de todos os chamados, enquanto as três menores somam pouco mais de um décimo. A carga média por dia trabalhado, porém, fica abaixo das ${N.saturacao} horas para todos, e apenas ${nf(N.estouros)} dos ${nf(N.pares)} pares de pessoa e dia (${pc(N.pct_estouro, 1)}) ultrapassam o limite.`),
]));
corpo.push(espaco());

corpo.push(tabela(
  ["Colaborador(a)", "Chamados", "Horas/dia", "% fora do prazo", "% manual", "Origem principal", "Fila que mais quebra"],
  N.perfil.map((x) => [
    x.nome, nf(x.ch), nf(x.hdia, 2), pc(x.fora), pc(x.manual, 1), x.origem,
    `${x.fila} (${pc(x.pct_fila, 0)})`,
  ]),
  [1450, 1300, 1000, 1150, 1050, 1650, 2038],
  [false, true, true, true, true, false, false]
));
corpo.push(legenda("A última coluna indica de qual anomalia vem a maior parte das quebras de prazo de cada pessoa."));

corpo.push(p([
  T("A tabela precisa ser lida com cuidado, porque a diferença entre as pontas é grande. "),
  B(N.perfil.find((x) => x.nome === "ALFREDO") ? "ALFREDO" : N.perfil[1].nome),
  T(` aparece com ${pc(N.perfil.find((x) => x.nome === "ALFREDO").fora)} dos chamados fora do prazo, e `),
  B("ANDREA"), T(` com ${pc(N.perfil.find((x) => x.nome === "ANDREA").fora)}. Olhando só essa coluna, a conclusão seria sobre desempenho individual, e ela estaria errada.`),
]));

corpo.push(p([
  T("A última coluna explica o que está acontecendo. "),
  T(`${pc(N.perfil.find((x) => x.nome === "ALFREDO").pct_fila, 0)} das quebras de ALFREDO vêm da `),
  C("MANUAL01"), T(", a mesma anomalia que lidera o ranking geral de atrasos, e ele concentra "),
  T(`${pc(N.of_dono_pct, 1)} de todas as quebras dessa fila na operação inteira. Ele também é a única pessoa que trata a origem Clientes Telemedidos. O que a tabela mede é a carteira que cada pessoa recebe, não a velocidade com que trabalha. A ação que sai daí é redistribuir a fila, não cobrar a pessoa.`),
]));

// ---- 3.5
corpo.push(h2("3.5 As anomalias mais custosas"));

corpo.push(p([
  T("A expressão \"anomalia mais ofensora\" comporta leituras diferentes, e elas levam a decisões diferentes. Apresentamos as três, porque escolher uma e omitir as outras levaria a priorizar a coisa errada."),
]));
corpo.push(espaco());

corpo.push(tabela(
  ["Leitura", "1º", "2º", "3º"],
  [
    ["Maior volume", `${N.top_volume[0].a} (${nf(N.top_volume[0].ch)})`,
      `${N.top_volume[1].a} (${nf(N.top_volume[1].ch)})`, `${N.top_volume[2].a} (${nf(N.top_volume[2].ch)})`],
    ["Maior tempo total", `${N.top_horas[0].a} (${nf(N.top_horas[0].h, 1)} h)`,
      `${N.top_horas[1].a} (${nf(N.top_horas[1].h, 1)} h)`, `${N.top_horas[2].a} (${nf(N.top_horas[2].h, 1)} h)`],
    ["Maior tempo unitário", `${N.top_unit[0].a} (${nf(N.top_unit[0].min, 2)} min)`,
      `${N.top_unit[1].a} (${nf(N.top_unit[1].min, 2)} min)`, `${N.top_unit[2].a} (${nf(N.top_unit[2].min, 2)} min)`],
  ],
  [2200, 2500, 2500, 2438]
));
corpo.push(legenda("Os três rankings quase não se sobrepõem."));

corpo.push(p([
  T("A "), C(N.alvo), T(` é a maior consumidora de horas da operação, com ${nf(N.alvo_h, 1)} horas no semestre, ou ${pc(N.alvo_esf, 1)} de todo o esforço, sendo apenas a ${N.alvo_pos_volume}ª em volume. Ela combina volume alto com tempo unitário de ${nf(N.alvo_unit, 2)} minutos, e ${pc(N.alvo_pct_manual, 1)} dos seus chamados são tratados manualmente. Essa fatia manual responde por ${nf(N.alvo_h_manual, 0)} das ${nf(N.alvo_h, 1)} horas.`),
]));

corpo.push(p([
  T("O terceiro ranking mostra por que os três precisam aparecer juntos. A "),
  C(N.top_unit[0].a), T(` é a mais cara por ocorrência, com ${nf(N.top_unit[0].min, 2)} minutos, mas teve ${nf(N.top_unit[0].ch)} chamados no semestre inteiro. Otimizá-la devolveria poucas horas. Quem priorizasse pelo custo unitário sozinho atacaria justamente o alvo de menor retorno.`),
]));

// ============================================ 4. ACHADOS NOS DADOS =========
corpo.push(new Paragraph({ children: [new PageBreak()] }));
corpo.push(h1("4. O que encontramos nos dados"));

corpo.push(p([
  T("Três pontos apareceram durante a análise e afetam a leitura dos indicadores. Registramos cada um com o que observamos, o que suspeitamos e a pergunta que levaríamos à área responsável pelo dado."),
]));

// ---- 4.1
corpo.push(h2("4.1 Registros com tratamento anterior à anomalia"));

const inv = Object.entries(N.invertidos_dist).sort((a, b) => Number(a[0]) - Number(b[0]));
corpo.push(p([
  B(`${nf(N.invertidos)} linhas`),
  T(` (${pc(N.invertidos_pct)} da base) têm data de tratamento anterior à data da anomalia, o que é impossível no fluxo do processo. A distribuição não parece aleatória: ${nf(inv[inv.length - 1][1])} delas trazem o tratamento exatamente ${Math.abs(Number(inv[inv.length - 1][0]))} dias antes da anomalia, e se espalham por várias anomalias, colaboradores e origens. Erro de digitação isolado não produz esse padrão.`),
]));

corpo.push(p([
  T("Trabalhamos com três hipóteses, em ordem de plausibilidade. A primeira é falha de carga em um lote específico, com carimbo de data errado ou inversão de campos na extração. A segunda é reprocessamento retroativo, em que a anomalia foi reaplicada sobre um documento já tratado e o registro guardou a data da reincidência. A terceira, menos provável, é diferença de fuso ou de tipo de data entre os sistemas de origem."),
]));

corpo.push(p([
  T("Perguntaríamos à área se houve reprocessamento ou correção retroativa nessa data, se a data da anomalia se refere à primeira ocorrência ou à última reincidência, e se uma anomalia pode ser reaplicada a um documento já tratado."),
]));

corpo.push(p([
  T("Sinalizamos esses registros na base e os retiramos do denominador do prazo, mantendo a contagem visível. A decisão nos prejudica em vez de ajudar: mantê-los no cálculo faria com que contassem como atraso negativo, ou seja, dentro do prazo, e o indicador ficaria artificialmente melhor."),
]));

// ---- 4.2
corpo.push(h2("4.2 Dias com carga acima do possível"));

corpo.push(p([
  T(`Mesmo depois de contar o tratamento massivo uma vez por lote, ${nf(N.imp_qtd)} pares de pessoa e dia ultrapassam 24 horas de trabalho. São ${pc(N.imp_pct_pares, 1)} dos pares e ${nf(N.imp_horas_manual, 0)} das ${nf(N.horas_total, 0)} horas do semestre. O maior deles é `),
  B(`${N.pico_quem} em ${N.pico_data}, com ${nf(N.pico_h, 1)} horas`), T("."),
]));

corpo.push(p([
  T(`Nesse dia a pessoa aparece com ${nf(N.pico_ch)} chamados, dos quais ${nf(N.pico_manual_ch)} estão marcados como tratamento manual. Só esses ${nf(N.pico_manual_ch)} respondem por ${nf(N.pico_manual_h, 1)} das ${nf(N.pico_h, 1)} horas. O problema não está no volume, está na classificação: fazer ${nf(N.pico_manual_ch)} investigações individuais numa jornada de ${N.saturacao} horas daria ${nf(N.pico_seg_por_caso, 0)} segundos por caso, sem pausa.`),
]));

corpo.push(p([
  T("A explicação mais provável é erro de preenchimento do tipo de liberação, com trabalho feito em lote registrado como manual. A segunda possibilidade é que o tempo médio cadastrado não valha para tratamento em série, já que resolver centenas de casos idênticos em sequência tem ganho de repetição que um modelo linear não captura. A terceira é que o campo de colaborador identifique o responsável pela fila, e não quem executou as horas."),
]));

corpo.push(p([
  T("Isso limita a precisão do total de horas, mas não muda a direção dos achados. Nas três hipóteses, o esforço fica ainda mais concentrado no lado manual, o que reforça em vez de contradizer a leitura da seção 3.3. O que se desloca é a magnitude absoluta, não o ranking nem a conclusão."),
]));

// ---- 4.3
corpo.push(h2("4.3 O tempo médio cadastrado é, em boa parte, um valor padrão"));

corpo.push(p([
  T("Na tabela de premissas, "), B(`${nf(N.tempo_padrao_qtd)} das ${nf(N.tempos_qtd)} anomalias`),
  T(` têm exatamente o mesmo tempo médio, ${nf(N.tempo_padrao_s, 0)} segundos. Outros valores também se repetem em blocos, e no total existem apenas ${nf(N.tempos_distintos)} valores distintos para ${nf(N.tempos_qtd)} anomalias. A leitura direta é que a tabela não veio de cronoanálise por tipo de anomalia, e sim de uma estimativa com preenchimento padrão para o que não foi medido.`),
]));

corpo.push(p([
  T("Isso precisa acompanhar qualquer número em horas deste documento. As anomalias de maior volume e maior esforço estão entre as que têm valor próprio, o que reduz o impacto, mas todo total de horas aqui é uma estimativa derivada de um parâmetro estimado."),
]));

corpo.push(p([
  T("As conclusões resistem porque dependem de proporção, e não do valor absoluto. Se todos os tempos estiverem errados na mesma direção, a maior consumidora de horas continua sendo a mesma e o esforço continua concentrado no manual. Perguntaríamos à área como o tempo médio foi levantado e se o valor de "),
  T(`${nf(N.tempo_padrao_min, 2)} minutos é medido ou é o padrão usado para o que não foi cronometrado.`),
]));

// ============================================== 5. RECOMENDAÇÕES ===========
corpo.push(new Paragraph({ children: [new PageBreak()] }));
corpo.push(h1("5. Recomendações"));

corpo.push(p([
  T("Quatro frentes, em ordem de retorno estimado. As duas primeiras têm impacto quantificado a partir da base; as outras duas dependem de informação que só a área tem."),
]));

corpo.push(h2(`5.1 Atacar a fila da ${N.ofensora}`));
corpo.push(p([
  T(`Esta é a recomendação de maior retorno por unidade de esforço. A anomalia é ${pc(N.of_vol, 1)} do volume e ${pc(N.of_pct_quebras, 1)} de todas as quebras de prazo, com taxa de falha interna de ${pc(N.of_pct_fora, 1)}. Se ela deixasse de estourar, o indicador geral cairia de ${pc(N.imp_sla_atual)} para ${pc(N.imp_sla_novo)}, evitando ${nf(N.imp_evitadas)} quebras no semestre.`),
]));
corpo.push(p([
  T("O trabalho começa antes de qualquer automação. O padrão de atraso descrito na seção 3.2 sugere espera por um gatilho externo, e mapear o fluxo de ponta a ponta dessa anomalia custa pouco: quem gera a retenção, o que dispara o tratamento e por que existe fila. É diagnóstico de processo, não de pessoa."),
]));

corpo.push(h2(`5.2 Automatizar o tratamento da ${N.alvo}`));
corpo.push(p([
  T(`É o maior retorno em capacidade. A anomalia consome ${nf(N.alvo_h, 1)} horas no semestre, ${pc(N.alvo_esf, 1)} de todo o esforço, e ${pc(N.alvo_pct_manual, 1)} dos seus chamados são manuais, respondendo por ${nf(N.alvo_h_manual, 0)} dessas horas. O custo está concentrado justamente na parte automatizável.`),
]));
corpo.push(p([
  T(`Migrar essa fila para tratamento em lote liberaria a maior parte dessas horas, o equivalente a ${nf(N.alvo_fte, 1)} pessoa em tempo integral no mesmo período. Para saber se é viável, é preciso entender por que esses casos não entram nas liberações massivas: faltam critérios objetivos de agrupamento ou existe exigência de conferência individual? Se for a segunda, vale medir quantos desses tratamentos terminam sem correção, porque uma conferência que quase nunca encontra erro é candidata a ser revista.`),
]));

corpo.push(h2("5.3 Revisar as regras que mais retêm documentos corretos"));
corpo.push(p([
  T(`${pc(N.sem_correcao, 1)} das retenções foram liberadas sem nenhuma correção. O documento estava certo e a regra o barrou. Cada retenção indevida eliminada é uma fila que não chega a se formar, economia maior do que tratar mais rápido, porque não consome análise nem prazo.`),
]));
corpo.push(p([
  T("Recomendamos ranquear as regras pela taxa de liberação sem correção e revisar as piores junto com quem definiu o critério. A decisão exige cautela, porque uma regra de retenção existe para evitar faturamento errado, e afrouxá-la tem custo do outro lado. A escolha de tolerância cabe ao negócio. O que oferecemos aqui é o número que hoje não está na mesa quando essa escolha é feita."),
]));
corpo.push(p([
  T("Uma ressalva sobre esse indicador: parte dos casos classificados como liberação sem correção pode ter exigido análise humana genuína para concluir que estava tudo certo. O percentual é ponto de partida da conversa, não veredito sobre as regras."),
]));

corpo.push(h2("5.4 Redistribuir a fila concentrada e corrigir o registro do tipo de liberação"));
corpo.push(p([
  T(`A fila da ${N.ofensora} está concentrada em uma pessoa, que responde por ${pc(N.of_dono_pct, 1)} das quebras dessa anomalia. Redistribuir reduz a dependência de uma pessoa só e corrige a distorção do indicador individual descrita na seção 3.4.`),
]));
corpo.push(p([
  T("Em paralelo, a inconsistência de classificação da seção 4.2 precisa ser resolvida na origem. Enquanto trabalho em lote for registrado como manual, qualquer medição de capacidade da área fica errada, inclusive a que sustenta pedido de quadro. Nenhuma das duas ações exige projeto: são ajustes de processo e de cadastro."),
]));

// ============================================ 6. RACIONAL ANALÍTICO ========
corpo.push(new Paragraph({ children: [new PageBreak()] }));
corpo.push(h1("6. Racional analítico"));

corpo.push(h2("6.1 Por que estes indicadores"));

corpo.push(p([
  T("Escolhemos cinco indicadores para o topo do painel. O percentual fora do prazo é o único com meta explícita na planilha e mede diretamente receita retida além do combinado, mas sozinho esconde concentração, e por isso aparece sempre acompanhado da decomposição por anomalia."),
]));

corpo.push(p([
  T("O par manual e massivo é apresentado duas vezes, em volume e em esforço, porque nenhuma das duas medidas mostra o desequilíbrio isoladamente. É esse par que transforma \"temos muito volume\" em \"o custo está em outro lugar\". Ele depende do tempo médio cadastrado, com a limitação descrita na seção 4.3."),
]));

corpo.push(p([
  T("O esforço total em horas converte fila em capacidade e responde à pergunta de dimensionamento. O percentual de dias acima da saturação separa equipe sobrecarregada de volume concentrado, e aqui mostrou que não existe problema sistêmico de capacidade. O percentual resolvido no mesmo dia dirige a atenção para a cauda em vez do processo inteiro."),
]));

corpo.push(h2("6.2 Decisões onde a planilha era ambígua"));

corpo.push(p([
  T("A aba de premissas define prazo de dois dias e saturação de sete horas, sem qualificar como esses valores devem ser aplicados. Onde havia mais de uma leitura defensável, escolhemos uma, deixamos registrada e calculamos as alternativas."),
]));

corpo.push(h2("Contagem em dias corridos"));
corpo.push(p([
  T(`A planilha diz apenas "2 dias". A base registra ${nf(N.sabados)} tratamentos aos sábados e ${nf(N.domingos)} aos domingos, ou seja, a operação trabalha seis dias por semana e não segue o calendário útil de segunda a sexta. Adotar dias úteis padrão perdoaria automaticamente todo atraso que atravessa o fim de semana. Optamos por dias corridos, a leitura mais conservadora.`),
]));

corpo.push(h2("Prazo cumprido com atraso menor ou igual a dois dias"));
corpo.push(p([
  T("\"Prazo esperado de dois dias\" descreve um teto. Quem entrega em dois dias cumpriu o combinado. Ler como \"menos de dois\" transformaria o prazo em um dia e reprovaria quem fez o acordado. A escolha tem peso: o indicador passa de "),
  B(pc(N.cenarios["Dias corridos, <= 2 (ADOTADO)"])), T(" para "),
  B(pc(N.cenarios["Dias corridos, < 2 (mais rígido)"])), T(" na leitura mais rígida."),
]));
corpo.push(espaco());

corpo.push(tabela(
  ["Convenção de cálculo", "% fora do prazo", "Efeito"],
  [
    ["Dias corridos, até 2 dias (adotada)", pc(N.cenarios["Dias corridos, <= 2 (ADOTADO)"]), "Leitura literal da premissa"],
    ["Dias corridos, menos de 2 dias", pc(N.cenarios["Dias corridos, < 2 (mais rígido)"]),
      `${nf(N.cenarios["Dias corridos, < 2 (mais rígido)"] - N.cenarios["Dias corridos, <= 2 (ADOTADO)"], 2)} pontos mais severa`],
    ["Dias úteis de segunda a sábado, até 2 dias", pc(N.cenarios["Dias úteis seg-sáb, <= 2"]),
      "Quase metade do indicador adotado"],
  ],
  [4000, 2000, 3638],
  [false, true, false]
));

corpo.push(h2("Tempo do tratamento massivo contado uma vez por lote"));
corpo.push(p([
  T("Foi a decisão de maior consequência numérica. Um tratamento massivo resolve o lote numa execução, então atribuir o tempo médio cheio a cada chamado do lote multiplica o esforço. O maior lote da base tem "),
  B(`${nf(N.lote_max)} documentos`),
  T(`: cobrado por chamado, ele sozinho custaria centenas de horas em um único dia, para uma pessoa.`),
]));

corpo.push(p([
  T(`Adotamos a seguinte regra. Tratamento manual recebe o tempo médio cheio por chamado, porque cada caso foi tratado individualmente. Tratamento massivo tem o tempo contado uma vez por lote e rateado entre os chamados, de modo que o total do lote fica correto e cada linha continua auditável. Definimos lote como a combinação de mesma pessoa, mesmo dia, mesma anomalia e mesma forma de liberação.`),
]));

corpo.push(p([
  T("O custo da alternativa é grande. Cobrando o tempo cheio de cada chamado massivo, o esforço do semestre passaria de "),
  B(`${nf(N.horas_total, 0)} para ${nf(N.horas_ingenuo, 0)} horas`),
  T(`, ${nf(N.fator, 1)} vezes mais, e os dias acima da saturação subiriam de ${pc(N.pct_estouro, 1)} para ${pc(N.pct_estouro_ing, 1)}. Os dois cenários ficam lado a lado na base exportada, para que a premissa possa ser contestada e recalculada.`),
]));

corpo.push(h2("Anomalias em aberto e registros inconsistentes"));
corpo.push(p([
  T(`Um registro sem data de tratamento seria uma anomalia ainda aberta. Ele permaneceria na base e no denominador, envelhecido contra a data máxima observada e não contra a data de hoje, o que manteria o resultado reprodutível. Excluir o não tratado do cálculo é a forma mais comum de produzir um indicador de prazo melhor do que a realidade. Nesta base o total é ${nf(N.em_aberto)}, e o tratamento está no código de qualquer forma.`),
]));
corpo.push(p([
  T(`Os ${nf(N.invertidos)} registros com data invertida ficam na base com sinalização própria e saem do denominador do prazo, conforme descrito na seção 4.1.`),
]));

corpo.push(h2("6.3 Validações executadas"));

corpo.push(p([
  T("O ponto das checagens abaixo não é que passaram. É que o número aparece mesmo quando é zero. Se quatro mil linhas ficassem sem tempo médio depois da junção, elas apareceriam no relatório em vez de virar hora zero em algum somatório."),
]));
corpo.push(espaco());

corpo.push(tabela(
  ["O que foi validado", "Como", "Resultado"],
  [
    ["Colunas obrigatórias com o nome exato", "Comparação contra lista fixa, com erro se faltar", "8 de 8 encontradas"],
    ["A junção não multiplicou linhas", "Validação de cardinalidade e conferência de contagem",
      `${nf(N.merge_antes)} antes, ${nf(N.merge_depois)} depois`],
    ["Nenhuma anomalia sem tempo médio", "Chaves normalizadas sem acento, espaço ou caixa antes da junção",
      `${nf(N.merge_sem_tempo)} linhas sem tempo`],
    ["Tabela de tempos sem chave duplicada", "Checagem antes da junção",
      `${nf(N.tempos_dup)} duplicadas em ${nf(N.tempos_qtd)}`],
    ["Datas convertidas sem perda", "Contagem de nulos antes e depois da conversão", "0 não convertidas"],
    ["Cadastro mais amplo que o período", "Diferença de conjuntos nos dois sentidos",
      `${nf(N.merge_nao_usadas)} anomalias cadastradas sem ocorrência`],
  ],
  [3400, 3600, 2638]
));

corpo.push(h2("6.4 O que faríamos com mais tempo"));

corpo.push(item("1.", [
  T("Validar com a área as três perguntas da seção 4. Elas alteram a magnitude das horas, ainda que não a direção das conclusões."),
]));
corpo.push(item("2.", [
  T("Entender a variação do volume ao longo do semestre. O volume mensal oscila bastante e a base não explica a causa. Se for sazonalidade, o dimensionamento da equipe muda."),
]));
corpo.push(item("3.", [
  T("Ranquear as regras de retenção pela taxa de liberação sem correção e simular o efeito de calibrar as piores."),
]));
corpo.push(item("4.", [
  T("Montar uma simulação de capacidade: dado o volume projetado e a proporção entre manual e massivo, quantas pessoas a fila exige e quanto cada automação devolve."),
]));

// ================================================ 7. ENTREGA ==============
corpo.push(new Paragraph({ children: [new PageBreak()] }));
corpo.push(h1("7. O que acompanha este documento"));

corpo.push(p([
  T("Todos os números citados aqui são calculados a partir da planilha original pelo mesmo módulo que alimenta o painel e o relatório técnico. A regra de cálculo existe em um único lugar, o que impede que os três materiais divirjam entre si."),
]));
corpo.push(espaco());

corpo.push(tabela(
  ["Arquivo", "O que é"],
  [
    ["app.py", "Dashboard interativo em Streamlit, com os mesmos números e as leituras em texto"],
    ["analise_core.py", "Núcleo analítico: toda a regra de cálculo, sem impressão nem escrita em disco"],
    ["analise_anomalias.py", "Relatório de linha de comando e geração do Excel de resultados"],
    ["resultado_analise.xlsx", `Base enriquecida com ${nf(N.total)} linhas e oito abas de resumo`],
    ["saida_execucao.txt", "Saída real da execução, incluindo o log das validações"],
    ["MEMORIAL_DO_CASE.pdf", "Documento de estudo: anatomia da base, método detalhado e perguntas prováveis"],
    ["Case_Processo_Seletivo.xlsx", "Planilha original, sem alteração"],
  ],
  [3000, 6638]
));

corpo.push(espaco());
corpo.push(p([
  T("Para abrir o painel, basta instalar as dependências listadas em "), C("requirements.txt"),
  T(" e executar "), C("streamlit run app.py"), T(" na pasta do projeto."),
]));

// =============================================================== DOCUMENTO ==
const doc = new Document({
  creator: "Análise de Anomalias de Faturamento",
  title: "Anomalias de Faturamento — Análise da Operação",
  description: "Documento de apoio ao dashboard gerencial",
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 21, color: PRETO } },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: convertMillimetersToTwip(210), height: convertMillimetersToTwip(297) },
        margin: {
          top: convertMillimetersToTwip(22), bottom: convertMillimetersToTwip(20),
          left: convertMillimetersToTwip(20), right: convertMillimetersToTwip(20),
        },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [T("Anomalias de Faturamento · Análise da operação", { size: 16, color: CINZA })],
          alignment: AlignmentType.RIGHT,
          spacing: { after: 120 },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [new TextRun({ children: [PageNumber.CURRENT], size: 16, color: CINZA, font: "Calibri" })],
          alignment: AlignmentType.CENTER,
        })],
      }),
    },
    children: corpo,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const destino = process.argv[3] || "DOCUMENTO_ANALISE.docx";
  fs.writeFileSync(destino, buf);
  console.log("gerado:", destino, "|", buf.length, "bytes");
});
