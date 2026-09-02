# -*- coding: utf-8 -*-
"""
================================================================================
DASHBOARD GERENCIAL — ANOMALIAS DE FATURAMENTO
================================================================================
Case de processo seletivo. Este app foi desenhado para ser LIDO SEM NARRADOR:
o destinatário abre o link sozinho, sem apresentação ao vivo. Por isso:

    - todo indicador vem acompanhado da leitura em texto, não só do número;
    - todo gráfico declara a pergunta que responde e a conclusão que produz;
    - toda recomendação é escrita por extenso, com impacto estimado;
    - as decisões metodológicas ficam expostas, não em rodapé.

Nenhum número é digitado à mão: tudo vem de `analise_core.py`, o mesmo módulo
que alimenta o relatório `analise_anomalias.py`. A regra de negócio existe em um
lugar só, e o dashboard não pode divergir do relatório.
================================================================================
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analise_core as core
import auth
from analise_core import (
    COL_ANOMALIA, COL_COLABORADOR, COL_DT_ANOMALIA, COL_DT_TRATAMENTO,
    COL_ORIGEM, COL_TIPO_LIBERACAO, COL_TIPO_TRATAMENTO,
    SATURACAO_HORAS_DIA, SLA_DIAS, formatar_horas, num,
)

# ==============================================================================
# CONFIGURAÇÃO E IDENTIDADE VISUAL
# ==============================================================================

st.set_page_config(
    page_title="Anomalias de Faturamento — Dashboard Gerencial",
    page_icon="📊",
    layout="wide",
    # "auto": aberta no desktop, recolhida no celular — no telefone a barra
    # cobriria o conteúdo, e os filtros são opcionais por construção.
    initial_sidebar_state="auto",
)

# Paleta sóbria, adequada a leitura corporativa: um azul institucional para o
# "normal", um vermelho contido para o "fora do padrão", cinzas para contexto.
AZUL = "#1c4b82"
AZUL_CLARO = "#5b8db8"
VERMELHO = "#b4472f"
AMBAR = "#c8912a"
VERDE = "#3f7d5a"
CINZA = "#8a8f98"
CINZA_CLARO = "#d5dae1"

# Proteção por senha. Precisa vir antes de qualquer processamento: o st.stop()
# lá dentro interrompe o script, então nada do conteúdo protegido é lido do disco
# nem enviado ao navegador de quem não entrou.
auth.exigir_senha()

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px; }
      h1 { font-size: 1.9rem !important; letter-spacing: -0.3px; }
      h2 { font-size: 1.28rem !important; margin-top: 1.6rem !important; }
      h3 { font-size: 1.05rem !important; color: #1c4b82; margin-top: 1.1rem !important; }
      .kpi-card { background: #f6f8fa; border: 1px solid #e3e8ee; border-left: 4px solid #1c4b82;
                  border-radius: 4px; padding: 0.85rem 1rem; height: 100%; }
      .kpi-card.alerta { border-left-color: #b4472f; }
      .kpi-card.bom    { border-left-color: #3f7d5a; }
      .kpi-rotulo { font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.6px;
                    color: #6b7280; font-weight: 600; min-height: 2.4em; line-height: 1.2; }
      .kpi-valor  { font-size: 1.85rem; font-weight: 700; color: #10131a; line-height: 1.15;
                    margin: 0.15rem 0 0.3rem; }
      .kpi-leitura{ font-size: 0.82rem; color: #3c424c; line-height: 1.42; }
      .pergunta { background: #eef2f7; border-left: 3px solid #5b8db8; padding: 0.55rem 0.85rem;
                  border-radius: 3px; font-size: 0.88rem; color: #23303f; margin-bottom: 0.5rem; }
      .leitura  { background: #fbfbfa; border: 1px solid #e6e6e2; border-left: 3px solid #c8912a;
                  padding: 0.65rem 0.9rem; border-radius: 3px; font-size: 0.9rem;
                  color: #2b2f36; line-height: 1.55; margin-top: 0.4rem; }
      .nota { font-size: 0.82rem; color: #6b7280; line-height: 1.5; }
      div[data-testid="stMetricValue"] { font-size: 1.5rem; }
      .stTabs [data-baseweb="tab"] { font-size: 0.94rem; font-weight: 600; padding: 0 1.1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

CONFIG_GRAFICO = {"displayModeBar": False, "responsive": True, "locale": "pt-BR"}

LAYOUT_BASE = dict(
    font=dict(family="Segoe UI, Helvetica, Arial, sans-serif", size=13, color="#2b2f36"),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=10, r=10, t=50, b=10),
    hoverlabel=dict(font_size=13),
    title=dict(font=dict(size=15, color="#10131a"), x=0, xanchor="left"),
)


def pct(valor, casas: int = 2) -> str:
    """Percentual no padrão pt-BR: vírgula decimal e o símbolo colado."""
    if pd.isna(valor):
        return "n/d"
    return f"{valor:.{casas}f}".replace(".", ",") + "%"


def estilizar(fig: go.Figure, altura: int = 380, **extra) -> go.Figure:
    """
    Aplica o padrão visual comum a todos os gráficos.

    O layout base é mesclado com os ajustes específicos (em vez de passado junto
    por **kwargs), para que um gráfico possa sobrescrever margem ou título sem
    colidir com a chave já presente no padrão.
    """
    layout = dict(LAYOUT_BASE)
    layout["height"] = altura
    if "title" in extra:
        layout["title"] = {**LAYOUT_BASE["title"], "text": extra.pop("title")}
    layout.update(extra)
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=False, linecolor=CINZA_CLARO, ticks="outside", tickcolor=CINZA_CLARO)
    fig.update_yaxes(showgrid=True, gridcolor="#eef0f3", zeroline=False, linecolor=CINZA_CLARO)
    return fig


def pergunta(texto: str) -> None:
    """Caixa que declara a pergunta de negócio que o gráfico seguinte responde."""
    st.markdown(f'<div class="pergunta"><b>A pergunta:</b> {texto}</div>', unsafe_allow_html=True)


def leitura(texto: str) -> None:
    """Caixa com a conclusão — o app não deixa o gráfico 'falar sozinho'."""
    st.markdown(f'<div class="leitura"><b>A leitura:</b> {texto}</div>', unsafe_allow_html=True)


def kpi(rotulo: str, valor: str, texto: str, estilo: str = "") -> None:
    """Cartão de indicador: número acompanhado da interpretação, nunca sozinho."""
    st.markdown(
        f'<div class="kpi-card {estilo}"><div class="kpi-rotulo">{rotulo}</div>'
        f'<div class="kpi-valor">{valor}</div>'
        f'<div class="kpi-leitura">{texto}</div></div>',
        unsafe_allow_html=True,
    )


# ==============================================================================
# ARQUIVOS PARA DOWNLOAD
# ==============================================================================
# Os bytes vêm dos artefatos já versionados no repositório, lidos em tempo de
# execução. Nada é gerado no servidor: montar o .docx ou o .xlsx a cada partida
# a frio custaria caro na camada gratuita, e o resultado seria o mesmo arquivo.
#
# O caminho sai de core.RAIZ (a pasta do módulo), e não do diretório de trabalho
# do processo, porque a hospedagem inicia o app de outro lugar.

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_PY = "text/x-python"
MIME_TXT = "text/plain"


@st.cache_data(show_spinner=False)
def ler_arquivo(nome: str) -> bytes | None:
    """
    Lê um artefato do repositório. Em cache para não reler do disco a cada
    interação: o Excel de resultado tem 13 MB e o app re-executa o script
    inteiro a cada clique.
    """
    caminho = core.RAIZ / nome
    if not caminho.exists():
        return None
    return caminho.read_bytes()


def botao_download(nome: str, rotulo: str, descricao: str, mime: str, chave: str) -> None:
    """Botão de download com uma linha explicando o que é o arquivo."""
    dados = ler_arquivo(nome)
    if dados is None:
        st.caption(f"`{nome}` não está disponível neste ambiente.")
        return
    tamanho = len(dados) / 1024
    medida = f"{num(tamanho / 1024, 1)} MB" if tamanho >= 1024 else f"{num(tamanho)} KB"
    st.download_button(
        rotulo, data=dados, file_name=nome, mime=mime, key=chave,
        width="stretch", type="secondary",
    )
    st.caption(f"{descricao} · {nome} · {medida}")


# ==============================================================================
# CARREGAMENTO (cache: a análise completa leva ~9s e não pode rodar a cada clique)
# ==============================================================================

@st.cache_data(show_spinner="Processando as 163 mil linhas da base...")
def carregar(caminho: str = core.ARQUIVO_ENTRADA) -> dict:
    """Roda o pipeline do núcleo uma única vez por sessão."""
    return core.analisar(caminho)


try:
    DADOS = carregar()
except FileNotFoundError:
    st.error(
        "Planilha `Case_Processo_Seletivo.xlsx` não encontrada. "
        "Ela precisa estar na mesma pasta do `app.py`."
    )
    st.stop()

BASE = DADOS["df"]
META = DADOS["meta"]

# ==============================================================================
# FILTROS — opcionais por construção: o app se explica sem tocar em nenhum
# ==============================================================================

with st.sidebar:
    st.markdown("### Filtros")
    st.caption(
        "Opcionais. O documento foi escrito para ser lido **sem tocar em nada** — "
        "os textos descrevem a operação inteira. Use os filtros só para conferir um recorte."
    )

    dt_min = BASE[COL_DT_ANOMALIA].min().date()
    dt_max = BASE[COL_DT_ANOMALIA].max().date()
    periodo = st.date_input(
        "Período (data da anomalia)", value=(dt_min, dt_max),
        min_value=dt_min, max_value=dt_max, format="DD/MM/YYYY",
    )

    colaboradores = sorted(BASE[COL_COLABORADOR].dropna().unique())
    sel_colab = st.multiselect("Colaborador(a)", colaboradores, default=[])

    tipos = sorted(BASE[COL_TIPO_TRATAMENTO].dropna().unique())
    sel_tipo = st.multiselect("Tipo de tratamento", tipos, default=[])

    origens = sorted(BASE[COL_ORIGEM].dropna().unique())
    sel_origem = st.multiselect("Origem", origens, default=[])

    st.divider()
    st.markdown(
        f'<div class="nota"><b>Premissas da planilha</b><br>'
        f"SLA: {SLA_DIAS} dias &nbsp;·&nbsp; Saturação: {SATURACAO_HORAS_DIA} h/dia<br>"
        f"Fonte: <code>Case_Processo_Seletivo.xlsx</code></div>",
        unsafe_allow_html=True,
    )
    st.divider()
    auth.botao_sair(st.sidebar)


def aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica os filtros da barra lateral.

    Observação metodológica: o rateio do esforço massivo [D4] é calculado sobre a
    base COMPLETA, antes de filtrar. Assim, o esforço de cada chamado permanece
    correto mesmo quando só parte de um lote entra no recorte.
    """
    recorte = df
    if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
        ini, fim = (pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1]))
        recorte = recorte[recorte[COL_DT_ANOMALIA].between(ini, fim)]
    if sel_colab:
        recorte = recorte[recorte[COL_COLABORADOR].isin(sel_colab)]
    if sel_tipo:
        recorte = recorte[recorte[COL_TIPO_TRATAMENTO].isin(sel_tipo)]
    if sel_origem:
        recorte = recorte[recorte[COL_ORIGEM].isin(sel_origem)]
    return recorte


DF = aplicar_filtros(BASE)
FILTRADO = len(DF) != len(BASE)

if DF.empty:
    st.warning("Nenhum registro no recorte selecionado. Ajuste os filtros na barra lateral.")
    st.stop()

# Agregados derivados (~0,1 s sobre 163 mil linhas — recalculados a cada filtro).
SATURACAO, POR_COLAB = core.resumo_saturacao(DF)
PERFIL = core.perfil_colaborador(DF, POR_COLAB)
RANKINGS = core.ranking_anomalias(DF)
QUEBRAS = core.contribuicao_quebras_sla(DF)
DIST_LIB = core.distribuicao_liberacao(DF)
SERIE = core.serie_temporal(DF, "W")
ATRASO = core.distribuicao_atraso(DF)
IMPOSSIVEIS, META_IMP = core.dias_impossiveis(SATURACAO, DF)
CUSTO_UNIT = core.esforco_por_liberacao_unitario(DF)

# Indicadores de topo.
TOTAL = len(DF)
AVALIAVEIS = int(DF["Dentro do SLA"].notna().sum())
FORA = int(DF["Fora do SLA"].eq(True).sum())
PCT_FORA = FORA / AVALIAVEIS * 100 if AVALIAVEIS else float("nan")
PCT_MANUAL_VOL = DF[COL_TIPO_LIBERACAO].eq("MANUAL").mean() * 100
PCT_MANUAL_ESF = float(
    DIST_LIB.loc[DIST_LIB[COL_TIPO_LIBERACAO].eq("MANUAL"), "% do Esforço"].sum()
)
HORAS = DF["Horas Atribuídas"].sum()
ESTOUROS = int(SATURACAO["Estourou Saturação"].sum())
PCT_ESTOURO = ESTOUROS / max(len(SATURACAO), 1) * 100
MESMO_DIA = (
    DF.loc[DF[COL_DT_TRATAMENTO].notna() & ~DF["Registro Inconsistente"], "Dias para Tratamento"]
    .eq(0).mean() * 100
)
PCT_SEM_CORRECAO = DF[COL_TIPO_TRATAMENTO].eq("Sem Correção").mean() * 100
# Sábados trabalhados: é a evidência que sustenta a escolha de dias corridos [D1].
SABADOS = num(int((BASE[COL_DT_TRATAMENTO].dt.dayofweek == 5).sum()))
DIAS_UTEIS_BASE = DF[COL_DT_TRATAMENTO].nunique()
FTE = HORAS / max(DIAS_UTEIS_BASE * SATURACAO_HORAS_DIA, 1e-9)

# A anomalia que mais quebra o SLA — base de toda a priorização das recomendações.
if not QUEBRAS.empty:
    OFENSORA = QUEBRAS.iloc[0][COL_ANOMALIA]
    IMPACTO = core.impacto_zerar_anomalia(DF, OFENSORA)
else:
    OFENSORA, IMPACTO = None, {}

# Maior consumidora de horas.
TOP_HORAS = RANKINGS["por_horas"].iloc[0]

# Posição da maior consumidora de horas no ranking POR VOLUME — o contraste entre
# "consome mais horas" e "aparece mais vezes" é o ponto da seção 1.4.
_ordem_volume = list(RANKINGS["ranking"][COL_ANOMALIA])
POSICAO_VOLUME = _ordem_volume.index(TOP_HORAS[COL_ANOMALIA]) + 1


# ==============================================================================
# ABERTURA
# ==============================================================================

st.title("Anomalias de Faturamento — Dashboard Gerencial")
st.markdown(
    f"""
**O que é isto.** Análise das **{num(TOTAL)} retenções de faturamento** registradas entre
**{DF[COL_DT_ANOMALIA].min():%d/%m/%Y}** e **{DF[COL_DT_ANOMALIA].max():%d/%m/%Y}**, sobre
{num(DF['Documento'].nunique())} documentos, tratadas por {DF[COL_COLABORADOR].nunique()} colaboradores.

**O processo por trás dos dados.** Regras automáticas de validação barram documentos com
possível inconsistência antes do faturamento. Cada retenção precisa ser analisada por uma pessoa,
que corrige o problema ou libera o documento sem ajuste. Enquanto a retenção existe, **a receita
não é faturada** — por isso a área trabalha com um prazo de {SLA_DIAS} dias e uma capacidade de
{SATURACAO_HORAS_DIA} horas por pessoa por dia.

**Como ler este painel.** Cada indicador vem com a leitura escrita abaixo do número, e cada
gráfico declara a pergunta que responde e a conclusão que produz. As decisões metodológicas estão
abertas na última aba.
"""
)

if FILTRADO:
    st.info(
        f"**Filtro ativo** — exibindo {num(TOTAL)} de {num(len(BASE))} chamados "
        f"({pct(TOTAL / len(BASE) * 100, 1)} da base). Os textos de leitura descrevem a operação "
        "completa; limpe os filtros para conferir os números citados."
    )

st.markdown("#### Os cinco indicadores que resumem a operação")

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi(
        "Chamados no período", num(TOTAL),
        f"{pct(MESMO_DIA, 0)} são resolvidos <b>no mesmo dia</b>. O volume é alto, "
        "mas a operação dá vazão.",
    )
with c2:
    kpi(
        f"Fora do SLA (> {SLA_DIAS} dias)", f"{pct(PCT_FORA, 2)}",
        f"{num(FORA)} chamados. No agregado o processo cumpre o prazo — mas a falha "
        "é <b>concentrada</b>, não difusa (ver Diagnóstico).",
        "alerta" if PCT_FORA > 5 else "bom",
    )
with c3:
    kpi(
        "Volume tratado em massa", f"{pct(100 - PCT_MANUAL_VOL, 0)}",
        f"Só {pct(PCT_MANUAL_VOL, 0)} dos chamados são tratados um a um — e são eles "
        "que consomem quase todo o tempo da equipe.",
    )
with c4:
    kpi(
        "Esforço que é manual", f"{pct(PCT_MANUAL_ESF, 0)}",
        "O inverso do indicador anterior. <b>É o achado central:</b> o custo humano "
        "está concentrado numa fatia pequena do volume.",
        "alerta",
    )
with c5:
    kpi(
        "Esforço total estimado", f"{num(HORAS, 0)} h",
        f"Equivale a <b>{num(FTE, 1)} pessoa(s)</b> em tempo integral no período. "
        f"{ESTOUROS} dias-pessoa passaram de {SATURACAO_HORAS_DIA}h ({pct(PCT_ESTOURO, 1)}).",
    )

st.markdown(
    f"""
<div class="leitura" style="margin-top:1rem">
<b>Se você só ler uma frase:</b> a operação <b>não tem problema de capacidade</b> —
{pct(MESMO_DIA, 0)} dos casos saem no mesmo dia e apenas {pct(PCT_ESTOURO, 1)} dos dias-pessoa
estouram a jornada. O que ela tem é <b>concentração</b>: {pct(PCT_MANUAL_ESF, 0)} do esforço humano
está em {pct(PCT_MANUAL_VOL, 0)} do volume, e
{pct((QUEBRAS.iloc[0]['% de Todas as Quebras'] if not QUEBRAS.empty else 0), 0)} de todas as
quebras de SLA vêm de <b>uma única anomalia</b>. Isso torna o problema endereçável com
poucas ações, e não com mais gente.
</div>
""",
    unsafe_allow_html=True,
)

st.divider()

aba_diag, aba_achados, aba_reco, aba_racional, aba_base = st.tabs([
    "1 · Diagnóstico", "2 · Achados nos dados", "3 · Recomendações",
    "4 · Racional analítico", "5 · A base",
])


# ==============================================================================
# ABA 1 — DIAGNÓSTICO
# ==============================================================================

with aba_diag:
    # ------------------------------------------------------------------ SLA --
    st.header("1.1 Cumprimento do SLA")
    st.markdown(
        f"O prazo acordado é de **{SLA_DIAS} dias corridos** entre a data da anomalia e a do "
        f"tratamento. No período, **{pct(PCT_FORA, 2)}** dos chamados avaliáveis ficaram fora dele."
    )

    col_a, col_b = st.columns([1, 1])

    with col_a:
        pergunta("Quanto tempo a operação leva para tratar uma anomalia?")
        cores = [VERDE if d else VERMELHO for d in ATRASO["Dentro do SLA"]]
        fig = go.Figure(go.Bar(
            x=ATRASO["Rotulo"], y=ATRASO["Chamados"], marker_color=cores,
            hovertemplate="%{x} dia(s)<br>%{y:,.0f} chamados<extra></extra>",
        ))
        fig.add_annotation(
            x=SLA_DIAS + 0.5, y=1, yref="paper", text="limite do SLA", showarrow=False,
            font=dict(size=11, color=CINZA), xanchor="left", yanchor="top",
        )
        fig.add_vline(x=SLA_DIAS + 0.5, line_width=1.5, line_dash="dot", line_color=CINZA)
        # Eixo categórico: sem isso o plotly trata os rótulos como números e o
        # último balde ("> 10", a cauda longa) some do gráfico.
        fig.update_xaxes(type="category")
        st.plotly_chart(
            estilizar(fig, 340, title="Chamados por tempo de tratamento (dias corridos)",
                      yaxis_title="Chamados", xaxis_title="Dias até o tratamento"),
            width="stretch", config=CONFIG_GRAFICO,
        )
        leitura(
            f"A distribuição é fortemente concentrada em zero: <b>{pct(MESMO_DIA, 1)}</b> dos "
            "chamados são resolvidos no mesmo dia. Em verde, o que cumpre o prazo; em vermelho, "
            "o que estoura. O problema não é a operação estar lenta — é uma <b>cauda</b> de casos "
            "que fica parada muito além do prazo."
        )

    with col_b:
        pergunta("O desempenho está piorando, melhorando ou é estável ao longo do semestre?")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=SERIE["periodo"], y=SERIE["Chamados"], name="Chamados",
            marker_color=CINZA_CLARO, hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.0f} chamados<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=SERIE["periodo"], y=SERIE["% Fora do SLA"], name="% fora do SLA",
            yaxis="y2", mode="lines+markers", line=dict(color=VERMELHO, width=2.5),
            marker=dict(size=5), hovertemplate="%{x|%d/%m/%Y}<br>%{y:.1f}% fora do SLA<extra></extra>",
        ))
        st.plotly_chart(
            estilizar(
                fig, 340, title="Volume semanal e % fora do SLA",
                xaxis=dict(dtick="M1", tickformat="%m/%Y"),
                yaxis=dict(title="Chamados"),
                yaxis2=dict(title="% fora do SLA", overlaying="y", side="right",
                            showgrid=False, ticksuffix="%"),
                legend=dict(orientation="h", y=1.12, x=0),
            ),
            width="stretch", config=CONFIG_GRAFICO,
        )
        leitura(
            "O volume oscila bastante entre semanas, mas o <b>% fora do SLA não acompanha os "
            "picos de volume</b> — sobe e desce em momentos próprios. Isso é evidência de que "
            "o atraso não vem de sobrecarga geral: se viesse, as duas linhas andariam juntas. "
            "Vem de filas específicas que travam."
        )

    st.markdown("### Onde o SLA quebra")
    pergunta("As quebras de prazo estão espalhadas pela operação ou concentradas em algum ponto?")

    # Gráfico e tabela ocupam a largura toda: em duas colunas, a tabela perdia
    # as últimas colunas por corte lateral — e é justamente a coluna do fim que
    # separa "aparece muito" de "falha muito".
    if True:
        q = QUEBRAS.sort_values("Chamados Fora do SLA")
        fig = go.Figure(go.Bar(
            x=q["Chamados Fora do SLA"], y=q[COL_ANOMALIA], orientation="h",
            marker_color=[VERMELHO if i == len(q) - 1 else AZUL_CLARO for i in range(len(q))],
            text=[f"{pct(v, 1)} das quebras" for v in q["% de Todas as Quebras"]],
            textposition="outside", textfont=dict(size=11),
            hovertemplate="%{y}<br>%{x:,.0f} chamados fora do SLA<extra></extra>",
        ))
        st.plotly_chart(
            estilizar(fig, 330, title="Anomalias que mais quebram o SLA",
                      xaxis=dict(title="Chamados fora do prazo",
                                 range=[0, q["Chamados Fora do SLA"].max() * 1.35])),
            width="stretch", config=CONFIG_GRAFICO,
        )

    tabela_quebras = QUEBRAS.rename(columns={
        COL_ANOMALIA: "Anomalia",
        "Chamados Fora do SLA": "Fora do SLA",
        "% de Todas as Quebras": "% de todas as quebras",
        "% do Volume da Anomalia": "% das ocorrências dela que estouram",
        "% Acumulado": "% acumulado",
    })
    st.dataframe(
        tabela_quebras.style.format({
            "Fora do SLA": lambda v: num(v),
            "% de todas as quebras": (lambda v: pct(v, 1)),
            "% das ocorrências dela que estouram": (lambda v: pct(v, 1)),
            "% acumulado": (lambda v: pct(v, 1)),
        }),
        hide_index=True, width="stretch",
    )
    st.caption(
        "**% das ocorrências dela que estouram** é a coluna decisiva: separa a anomalia que "
        "*aparece muito* da que *falha muito*. As duas primeiras linhas somam dois terços de "
        "todas as quebras do período."
    )

    if not QUEBRAS.empty:
        linha = QUEBRAS.iloc[0]
        vol_ofensora = RANKINGS["ranking"].loc[
            RANKINGS["ranking"][COL_ANOMALIA].eq(OFENSORA), "% do Volume"
        ].iloc[0]
        leitura(
            f"<b>Aqui está o achado mais acionável de toda a análise.</b> A anomalia "
            f"<code>{OFENSORA}</code> representa {pct(vol_ofensora, 1)} do volume, mas responde por "
            f"<b>{pct(linha['% de Todas as Quebras'], 1)} de todas as quebras de SLA</b>. Ela falha em "
            f"{pct(linha['% do Volume da Anomalia'], 1)} das próprias ocorrências — contra 2,2% da maior "
            "anomalia em volume. O indicador agregado de "
            f"{pct(PCT_FORA, 2)} esconde que metade da dor está em um único código."
        )

    st.divider()

    # ------------------------------------------------ MANUAL VS MASSIVO -----
    st.header("1.2 Manual × massivo: o contraste entre volume e esforço")
    st.markdown(
        "Um tratamento **massivo** resolve um lote inteiro numa execução só; um **manual** exige "
        "que o analista abra, investigue e decida caso a caso. A distinção parece administrativa, "
        "mas é ela que explica onde está o custo da operação."
    )

    pergunta(
        "Onde está o volume de trabalho — e onde está, de fato, o tempo gasto pela equipe? "
        "São o mesmo lugar?"
    )

    col_e, col_f = st.columns([1.1, 1])
    with col_e:
        manual = DIST_LIB[DIST_LIB[COL_TIPO_LIBERACAO].eq("MANUAL")].iloc[0]
        massivo = DIST_LIB[DIST_LIB[COL_TIPO_LIBERACAO].eq("MASSIVO")].iloc[0]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=["Volume de chamados", "Esforço em horas"], x=[manual["% dos Chamados"], manual["% do Esforço"]],
            name="MANUAL", orientation="h", marker_color=VERMELHO,
            text=[f"{pct(manual['% dos Chamados'], 1)}", f"{pct(manual['% do Esforço'], 1)}"],
            textposition="inside", insidetextanchor="middle", textfont=dict(color="white", size=14),
            hovertemplate="Manual: %{x:.1f}%<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            y=["Volume de chamados", "Esforço em horas"], x=[massivo["% dos Chamados"], massivo["% do Esforço"]],
            name="MASSIVO", orientation="h", marker_color=AZUL_CLARO,
            text=[f"{pct(massivo['% dos Chamados'], 1)}", f"{pct(massivo['% do Esforço'], 1)}"],
            textposition="inside", insidetextanchor="middle", textfont=dict(color="white", size=14),
            hovertemplate="Massivo: %{x:.1f}%<extra></extra>",
        ))
        st.plotly_chart(
            estilizar(fig, 300, barmode="stack",
                      title="A mesma operação, medida de duas formas",
                      xaxis=dict(ticksuffix="%", range=[0, 100]),
                      legend=dict(orientation="h", y=1.15, x=0)),
            width="stretch", config=CONFIG_GRAFICO,
        )
    with col_f:
        if "razao" in CUSTO_UNIT:
            st.metric(
                "Custo de um chamado manual vs. um massivo",
                f"{num(CUSTO_UNIT['razao'], 0)}× mais caro",
            )
            st.caption(
                f"Esforço médio por chamado — manual: **{num(CUSTO_UNIT['MANUAL'], 2)} min**; "
                f"massivo: **{num(CUSTO_UNIT['MASSIVO'], 3)} min**. "
                "É a razão quantitativa a favor de automatizar, e não de contratar."
            )

    st.dataframe(
        DIST_LIB.rename(columns={COL_TIPO_LIBERACAO: "Tipo de Liberação"}).style.format({
            "Chamados": lambda v: num(v),
            "% dos Chamados": (lambda v: pct(v, 2)),
            "Horas Atribuídas": (lambda v: num(v, 1)),
            "% do Esforço": (lambda v: pct(v, 2)),
        }),
        hide_index=True, width="stretch",
    )

    leitura(
        f"As duas barras são quase o inverso uma da outra. O massivo faz "
        f"<b>{pct(massivo['% dos Chamados'], 0)} do volume com {pct(massivo['% do Esforço'], 0)} do "
        f"esforço</b>; o manual faz <b>{pct(manual['% dos Chamados'], 0)} do volume com "
        f"{pct(manual['% do Esforço'], 0)} do esforço</b>. Em uma frase: <b>quatro em cada cinco "
        "anomalias já são resolvidas de forma praticamente gratuita, e quase todo o custo humano "
        "está no quinto restante.</b> Isso redireciona a pergunta de gestão: reduzir o volume total "
        "economiza pouco — o que economiza é migrar trabalho de manual para massivo, ou eliminar "
        "a causa do manual."
    )

    st.divider()

    # ----------------------------------------------- CARGA E SATURAÇÃO ------
    st.header("1.3 Carga de trabalho e saturação")
    st.warning(
        "**Como esta seção deve ser lida.** Os números abaixo medem a **carteira que cada pessoa "
        "recebe**, não o desempenho de cada pessoa. Quem trata uma fila estruturalmente atrasada "
        "aparece com pior indicador de prazo mesmo trabalhando bem — e é exatamente o que os dados "
        "mostram aqui. As colunas de composição existem para impedir a leitura de produtividade "
        "individual.",
        icon="⚠️",
    )

    col_g, col_h = st.columns([1, 1])
    with col_g:
        pergunta("A carga de trabalho está equilibrada entre as pessoas da equipe?")
        p = POR_COLAB.sort_values("Horas Totais")
        fig = go.Figure(go.Bar(
            x=p["Horas Totais"], y=p[COL_COLABORADOR], orientation="h", marker_color=AZUL,
            text=[f"{num(v, 0)} h" for v in p["Horas Totais"]],
            textposition="outside", textfont=dict(size=11),
            hovertemplate="%{y}<br>%{x:,.1f} horas no período<extra></extra>",
        ))
        st.plotly_chart(
            estilizar(fig, 330, title="Esforço total por colaborador(a)",
                      xaxis=dict(title="Horas estimadas no período",
                                 range=[0, p["Horas Totais"].max() * 1.22])),
            width="stretch", config=CONFIG_GRAFICO,
        )

    with col_h:
        pergunta(
            f"Alguém opera acima da capacidade diária de {SATURACAO_HORAS_DIA} horas de forma "
            "recorrente?"
        )
        p2 = POR_COLAB.sort_values("Horas/Dia (média)")
        fig = go.Figure(go.Bar(
            x=p2["Horas/Dia (média)"], y=p2[COL_COLABORADOR], orientation="h",
            marker_color=[VERMELHO if v > SATURACAO_HORAS_DIA else AZUL_CLARO
                          for v in p2["Horas/Dia (média)"]],
            text=[f"{num(v, 1)} h/dia" for v in p2["Horas/Dia (média)"]],
            textposition="outside", textfont=dict(size=11),
            hovertemplate="%{y}<br>média de %{x:.2f} h/dia<extra></extra>",
        ))
        fig.add_vline(x=SATURACAO_HORAS_DIA, line_width=1.5, line_dash="dot", line_color=VERMELHO)
        fig.add_annotation(
            x=SATURACAO_HORAS_DIA, y=1, yref="paper", text=f"capacidade: {SATURACAO_HORAS_DIA}h",
            showarrow=False, font=dict(size=11, color=VERMELHO),
            xanchor="right", yanchor="top", xshift=-6,
        )
        st.plotly_chart(
            estilizar(fig, 330, title="Carga média por dia trabalhado",
                      xaxis=dict(title="Horas por dia",
                                 range=[0, max(p2["Horas/Dia (média)"].max() * 1.3,
                                               SATURACAO_HORAS_DIA * 1.2)])),
            width="stretch", config=CONFIG_GRAFICO,
        )

    leitura(
        f"A carga é <b>muito desigual em volume</b> — a pessoa mais carregada concentra "
        f"{pct(POR_COLAB.iloc[0]['Chamados Tratados'] / TOTAL * 100, 0)} dos chamados —, mas a carga "
        f"média diária fica <b>abaixo da capacidade de {SATURACAO_HORAS_DIA}h para todos</b>. "
        f"Apenas {pct(PCT_ESTOURO, 1)} dos dias-pessoa estouram o limite. Ou seja: a equipe não está "
        "saturada no agregado; há concentração de volume, não falta de capacidade."
    )

    st.markdown("### Composição da carteira — por que comparar pessoas seria um erro")
    # Horas totais, horas/dia e dias com estouro já aparecem nos gráficos acima:
    # aqui ficam só as colunas de COMPOSIÇÃO, que é o propósito da tabela.
    colunas_perfil = [COL_COLABORADOR, "Chamados Tratados", "% Fora do SLA", "% Manual",
                      "Origem Predominante"]
    if "Anomalia que Mais Quebra SLA" in PERFIL.columns:
        colunas_perfil += ["Anomalia que Mais Quebra SLA", "% das Quebras nessa Anomalia"]
    st.dataframe(
        PERFIL[colunas_perfil].rename(columns={
            "Chamados Tratados": "Chamados",
            "Origem Predominante": "Origem principal",
            "Anomalia que Mais Quebra SLA": "Fila que mais quebra",
            "% das Quebras nessa Anomalia": "% das quebras dela",
        }).style.format({
            "Chamados": lambda v: num(v),
            "% Fora do SLA": (lambda v: pct(v, 2)), "% Manual": (lambda v: pct(v, 1)),
            "% das quebras dela": (lambda v: pct(v, 1)),
        }),
        hide_index=True, width="stretch",
    )

    if "Anomalia que Mais Quebra SLA" in PERFIL.columns:
        pior = PERFIL.sort_values("% Fora do SLA", ascending=False).iloc[0]
        melhor = PERFIL.sort_values("% Fora do SLA").iloc[0]
        leitura(
            f"Compare as duas pontas. <b>{pior[COL_COLABORADOR]}</b> aparece com "
            f"{pct(pior['% Fora do SLA'], 2)} fora do prazo e <b>{melhor[COL_COLABORADOR]}</b> com "
            f"{pct(melhor['% Fora do SLA'], 2)}. Mas olhe a penúltima coluna: "
            f"<b>{pct(pior['% das Quebras nessa Anomalia'], 0)} das quebras de "
            f"{pior[COL_COLABORADOR]} vêm de uma única anomalia — a "
            f"<code>{pior['Anomalia que Mais Quebra SLA']}</code></b>, a mesma que lidera o ranking "
            "geral de quebras. A diferença entre as pessoas é <b>a fila que cada uma recebe</b>, "
            "não a velocidade com que trabalham. Concluir o contrário seria um erro de análise "
            "com consequência real para alguém."
        )

    st.divider()

    # ------------------------------------------------------ RANKING ---------
    st.header("1.4 Anomalias mais ofensoras — três leituras diferentes")
    st.markdown(
        "\"Mais ofensora\" é ambíguo, e as leituras possíveis levam a decisões diferentes. "
        "Por isso as três são apresentadas lado a lado, em vez de escolher uma e omitir o resto."
    )

    col_i, col_j, col_k = st.columns(3)
    trios = [
        (col_i, "por_volume", "Chamados", "A) Maior VOLUME",
         "Onde está a maior fila.", "chamados", 0),
        (col_j, "por_horas", "Horas Totais", "B) Maior TEMPO TOTAL",
         "Onde a operação queima horas — prioridade de automação.", "h no período", 1),
        (col_k, "por_unitario", "Tempo Médio Unitário (min)", "C) Maior TEMPO UNITÁRIO",
         "Qual caso é individualmente mais caro.", "min por chamado", 2),
    ]
    for coluna, chave, campo, titulo_g, sub, unidade, casas in trios:
        with coluna:
            st.markdown(f"**{titulo_g}**")
            st.caption(sub)
            dados_t = RANKINGS[chave].sort_values(campo)
            fig = go.Figure(go.Bar(
                x=dados_t[campo], y=dados_t[COL_ANOMALIA], orientation="h",
                marker_color=AZUL,
                text=[f"{num(v, casas)} {unidade.split()[0]}" if campo != "Chamados"
                      else num(v) for v in dados_t[campo]],
                textposition="outside", textfont=dict(size=11),
                hovertemplate="%{y}<br>%{x:,.2f} " + unidade + "<extra></extra>",
            ))
            st.plotly_chart(
                estilizar(fig, 240, title="", showlegend=False,
                          margin=dict(l=10, r=10, t=10, b=10),
                          xaxis=dict(range=[0, dados_t[campo].max() * 1.4])),
                width="stretch", config=CONFIG_GRAFICO,
            )

    unit_top = RANKINGS["por_unitario"].iloc[0]
    leitura(
        f"Os rankings quase não se sobrepõem, e isso é o ponto. <code>{TOP_HORAS[COL_ANOMALIA]}</code> "
        f"consome <b>{pct(TOP_HORAS['% do Esforço'], 0)} de todo o esforço</b> sendo apenas a "
        f"{POSICAO_VOLUME}ª "
        f"em volume — é a melhor candidata a automação. Já <code>{unit_top[COL_ANOMALIA]}</code> lidera "
        f"o custo por ocorrência ({num(unit_top['Tempo Médio Unitário (min)'], 2)} min), mas teve apenas "
        f"{num(unit_top['Chamados'])} chamados no período: otimizá-la seria irrelevante. "
        "<b>Usar só o ranking unitário levaria a priorizar a anomalia errada</b> — por isso os três "
        "aparecem juntos."
    )

    st.markdown("###### Conferir os números por conta própria")
    col_dl, col_txt = st.columns([1, 2.2])
    with col_dl:
        botao_download(
            "resultado_analise.xlsx", "Baixar a base enriquecida (Excel)",
            "Arquivo", MIME_XLSX, "dl_xlsx_diag",
        )
    with col_txt:
        st.caption(
            "Traz as 163.811 linhas com as colunas calculadas (dias até o tratamento, "
            "flags de SLA e de consistência, tamanho do lote, esforço nos dois cenários) "
            "e oito abas de resumo. Todo número deste painel pode ser refeito a partir dele."
        )

    with st.expander("Ver o ranking completo das anomalias"):
        st.dataframe(
            RANKINGS["ranking"].rename(columns={COL_ANOMALIA: "Anomalia"}).style.format({
                "Chamados": lambda v: num(v), "Horas Totais": (lambda v: num(v, 2)),
                "Tempo Médio Unitário (min)": (lambda v: num(v, 2)), "Chamados Fora do SLA": lambda v: num(v),
                "Dias Médios p/ Tratamento": (lambda v: num(v, 2)), "% do Volume": (lambda v: pct(v, 2)),
                "% do Esforço": (lambda v: pct(v, 2)), "% Fora do SLA": (lambda v: pct(v, 2)), "% Manual": (lambda v: pct(v, 1)),
            }),
            hide_index=True, width="stretch", height=420,
        )


# ==============================================================================
# ABA 2 — ACHADOS NOS DADOS
# ==============================================================================

with aba_achados:
    st.header("Achados de qualidade de dado")
    st.markdown(
        "Estes três pontos foram encontrados durante a análise. Estão aqui como **resultado do "
        "trabalho**, não como ressalva: eles afetam a leitura dos indicadores e cada um traz uma "
        "pergunta objetiva a ser levada à área responsável pelo dado."
    )

    inconsistentes = int(DF["Registro Inconsistente"].sum())

    # ----------------------------------------------------- ACHADO 1 ---------
    st.subheader(f"Achado 1 — {num(inconsistentes)} registros com tratamento anterior à anomalia")
    col_a, col_b = st.columns([0.8, 1.7])
    with col_a:
        st.metric("Registros com data invertida", num(inconsistentes))
        st.caption(f"{pct(inconsistentes / TOTAL * 100, 2)} da base")
        dist_inv = (
            DF.loc[DF["Registro Inconsistente"], "Dias para Tratamento"]
            .value_counts().sort_index().rename_axis("Atraso (dias)").reset_index(name="Registros")
        )
        st.dataframe(dist_inv, hide_index=True, width="stretch")
    with col_b:
        st.markdown(
            f"""
**O fato.** {num(inconsistentes)} linhas têm `Data de Tratamento` **anterior** à
`Data da Anomalia` — impossível no fluxo do processo. E não é ruído aleatório: a quase totalidade
compartilha exatamente o mesmo par de datas, espalhada por várias anomalias, colaboradores e
origens. Erro de digitação individual não produz esse padrão.

**Hipóteses de causa,** em ordem de plausibilidade:
1. **Erro de carga/ETL num lote específico** — um job processou o dia com carimbo de data errado,
   ou houve inversão de campos na extração.
2. **Reprocessamento retroativo** — a anomalia foi *reaplicada* sobre um documento já tratado, e o
   registro guardou a data da reincidência.
3. **Fusos ou tipos de data diferentes** entre os sistemas de origem da anomalia e do tratamento.

**O que perguntar à área:** houve reprocessamento ou correção retroativa nessa data? A
`Data da Anomalia` é a da **primeira** ocorrência ou a da **última reincidência**? Uma anomalia
pode ser reaplicada a um documento já tratado?

**Como foi tratado aqui:** sinalizados na base, mantidos visíveis e **excluídos do denominador do
SLA**. Não foram descartados em silêncio — e note que a decisão nos *prejudica*: mantê-los contaria
como atraso negativo, ou seja, dentro do prazo, melhorando artificialmente o indicador.
"""
        )

    st.divider()

    # ----------------------------------------------------- ACHADO 2 ---------
    st.subheader(
        f"Achado 2 — {META_IMP['qtd']} dias-colaborador com carga fisicamente impossível"
    )
    if META_IMP["qtd"]:
        col_c, col_d = st.columns([1.25, 1])
        with col_c:
            st.markdown(
                f"""
**O fato.** Mesmo **depois** do rateio correto do tratamento massivo, {META_IMP['qtd']} pares
(colaborador, dia) ultrapassam **{core.LIMITE_JORNADA_IMPOSSIVEL_H} horas** de trabalho. O pico
chega a **{formatar_horas(SATURACAO['Horas Trabalhadas'].max())}** num único dia.

**A causa está isolada no dado:** nesses dias, **{pct(META_IMP['pct_manual'], 1)} dos chamados estão
marcados como `MANUAL`**, e eles respondem por
{num(META_IMP['horas_manual'], 0)} das {num(META_IMP['horas_total'], 0)} horas.
O problema não é volume — é **classificação**.

**Hipóteses de causa:**
1. **Erro de classificação do `Tipo de Liberação`** (mais provável) — trabalho feito em lote foi
   registrado como manual. Fazer esse tanto de investigações individuais num dia exigiria poucos
   segundos por caso, sem pausa.
2. **O tempo médio não vale para tratamento em série** — mesmo genuinamente manual, tratar
   centenas de casos idênticos em sequência tem ganho de repetição que o modelo linear não capta.
3. **O campo identifica o dono da fila, não quem executou** as horas.

**O que perguntar à área:** quando um analista libera vários documentos numa mesma ação, isso sai
como MASSIVO ou pode sair como MANUAL? O tempo médio foi medido em tratamento individual?
`Colaborador(a)` é quem executou ou o responsável pela fila?
"""
            )
        with col_d:
            mostra = IMPOSSIVEIS.head(8).copy()
            mostra["Data"] = pd.to_datetime(mostra["Data"]).dt.strftime("%d/%m/%Y")
            st.dataframe(
                mostra[[COL_COLABORADOR, "Data", "Chamados Tratados", "Horas Trabalhadas"]]
                .rename(columns={"Chamados Tratados": "Chamados", "Horas Trabalhadas": "Horas"})
                .style.format({"Chamados": lambda v: num(v), "Horas": (lambda v: num(v, 1))}),
                hide_index=True, width="stretch", height=320,
            )
            st.caption("Dias com carga acima do limite físico, em ordem decrescente.")

        st.info(
            f"**Por que isso não invalida a análise.** Afeta {META_IMP['qtd']} de "
            f"{num(len(SATURACAO))} pares colaborador-dia "
            f"({pct(META_IMP['qtd'] / max(len(SATURACAO), 1) * 100, 1)}) e "
            f"{num(META_IMP['horas_manual'], 0)} de {num(HORAS, 0)} horas. A direção de todos os achados "
            "— o esforço concentrado no manual, a anomalia que domina as quebras de SLA, a maior "
            "consumidora de horas — **se mantém nas três hipóteses**, porque todas concentram ainda "
            "mais o esforço no lado manual. O que muda é a magnitude absoluta das horas, não o "
            "ranking nem a conclusão.",
            icon="ℹ️",
        )
    else:
        st.success("Nenhum dia-colaborador acima do limite físico neste recorte.")

    st.divider()

    # ----------------------------------------------------- ACHADO 3 ---------
    tempos = DADOS["tempos"]
    contagem_tempos = tempos["Tempo Médio (s)"].value_counts()
    valor_padrao = contagem_tempos.index[0]
    qtd_padrao = int(contagem_tempos.iloc[0])

    st.subheader(
        f"Achado 3 — {qtd_padrao} das {len(tempos)} anomalias têm o mesmo tempo médio cadastrado"
    )
    col_e, col_f = st.columns([1, 1.25])
    with col_e:
        dist_tempos = (
            contagem_tempos.rename_axis("Tempo (s)").reset_index(name="Anomalias").sort_values("Tempo (s)")
        )
        fig = go.Figure(go.Bar(
            x=dist_tempos["Tempo (s)"].astype(str), y=dist_tempos["Anomalias"],
            marker_color=[AMBAR if v == valor_padrao else AZUL_CLARO for v in dist_tempos["Tempo (s)"]],
            hovertemplate="%{x} s<br>%{y} anomalias<extra></extra>",
        ))
        st.plotly_chart(
            estilizar(fig, 300, title="Quantas anomalias compartilham cada tempo médio",
                      xaxis_title="Tempo médio cadastrado (segundos)", yaxis_title="Anomalias"),
            width="stretch", config=CONFIG_GRAFICO,
        )
    with col_f:
        minutos = valor_padrao / 60
        st.markdown(
            f"""
**O fato.** Na tabela de premissas, **{qtd_padrao} das {len(tempos)} anomalias** têm exatamente
o mesmo tempo médio: **{int(valor_padrao)} segundos** ({num(minutos, 2)} min). Outros valores também se
repetem em blocos. Apenas cerca de uma dúzia são genuinamente distintos.

**A leitura.** A tabela não é resultado de cronoanálise por tipo de anomalia. É uma estimativa com
um **valor padrão de preenchimento** para o que não foi medido.

**Impacto real — e por que é menor do que parece.** As anomalias de maior volume e maior esforço
estão entre as que têm valor próprio. Ainda assim, **todo número em horas deste painel é uma
estimativa derivada de um parâmetro estimado**, e deve ser lido como tal.

**Por que as conclusões resistem:** os rankings dependem de **proporção**, não de valor absoluto.
Se todos os tempos estiverem errados na mesma direção, a maior consumidora de horas continua sendo
a maior, e o esforço continua concentrado no manual.

**O que perguntar à área:** como o tempo médio de cada anomalia foi levantado? O valor de
{num(minutos, 2)} min é medido ou é um padrão para o que não foi cronometrado?
"""
        )


# ==============================================================================
# ABA 3 — RECOMENDAÇÕES
# ==============================================================================

with aba_reco:
    st.header("Recomendações à gestão")
    st.markdown(
        "Quatro ações, em ordem de retorno. Cada uma traz o impacto estimado a partir dos dados "
        "e o que seria necessário para executá-la."
    )

    # -------------------------------------------------- RECOMENDAÇÃO 1 ------
    if IMPACTO:
        st.subheader(f"1. Atacar a fila `{OFENSORA}` — maior retorno por unidade de esforço")
        c1, c2, c3 = st.columns(3)
        c1.metric("% fora do SLA hoje", f"{pct(IMPACTO['sla_atual'], 2)}")
        c2.metric(
            "% fora do SLA se essa fila deixar de estourar", f"{pct(IMPACTO['sla_novo'], 2)}",
            f"-{num(IMPACTO['ganho_pontos'], 2)} p.p.", delta_color="inverse",
        )
        c3.metric("Quebras de SLA evitadas", num(IMPACTO["quebras_evitadas"]))
        c3.caption(f"{pct(IMPACTO['pct_das_quebras'], 1)} de todas as quebras do período")

        linha_of = RANKINGS["ranking"][RANKINGS["ranking"][COL_ANOMALIA].eq(OFENSORA)].iloc[0]
        st.markdown(
            f"""
**Por quê.** `{OFENSORA}` é apenas {pct(linha_of['% do Volume'], 1)} do volume, mas responde por
**{pct(IMPACTO['pct_das_quebras'], 1)} de todas as quebras de SLA**. Sua taxa de falha interna é de
**{pct(linha_of['% Fora do SLA'], 1)}** — várias vezes a das anomalias de maior volume. Resolver
apenas essa fila levaria o indicador geral de **{pct(IMPACTO['sla_atual'], 2)} para
{pct(IMPACTO['sla_novo'], 2)}**, sem tocar em mais nada.

**O que investigar antes de agir.** A distribuição do atraso dessa anomalia não é gradual: os casos
saem no mesmo dia **ou** ficam parados vários dias, com pouca coisa no meio. Esse formato é típico
de **fila que espera por um gatilho** — rotina em lote, dependência de terceiro, retorno de área
externa — e não de trabalho que demora a ser feito.

**O que seria necessário.** Mapear o fluxo de ponta a ponta dessa anomalia: quem gera, o que
dispara o tratamento, e por que existe espera. É diagnóstico de processo, não de pessoa — e por
isso é barato de fazer antes de investir em qualquer automação.
"""
        )

        with st.expander(f"Ver a distribuição do atraso de `{OFENSORA}`"):
            recorte = DF[DF[COL_ANOMALIA].eq(OFENSORA) & ~DF["Registro Inconsistente"]]
            dist_of = (
                recorte["Dias para Tratamento"].value_counts().sort_index().head(9)
                .rename_axis("Dias").reset_index(name="Chamados")
            )
            fig = go.Figure(go.Bar(
                x=dist_of["Dias"].astype(int).astype(str), y=dist_of["Chamados"],
                marker_color=[VERDE if d <= SLA_DIAS else VERMELHO for d in dist_of["Dias"]],
                hovertemplate="%{x} dia(s)<br>%{y:,.0f} chamados<extra></extra>",
            ))
            st.plotly_chart(
                estilizar(fig, 300, title=f"{OFENSORA}: chamados por dia até o tratamento",
                          xaxis_title="Dias", yaxis_title="Chamados"),
                width="stretch", config=CONFIG_GRAFICO,
            )
            st.caption(
                "O vale entre os primeiros dias e o segundo grupo é a assinatura de uma espera "
                "estruturada, não de lentidão."
            )

    st.divider()

    # -------------------------------------------------- RECOMENDAÇÃO 2 ------
    st.subheader(f"2. Automatizar o tratamento de `{TOP_HORAS[COL_ANOMALIA]}` — maior retorno em capacidade")
    recorte_top = DF[DF[COL_ANOMALIA].eq(TOP_HORAS[COL_ANOMALIA])]
    horas_manual_top = recorte_top.loc[
        recorte_top[COL_TIPO_LIBERACAO].eq("MANUAL"), "Horas Atribuídas"
    ].sum()
    pct_manual_top = recorte_top[COL_TIPO_LIBERACAO].eq("MANUAL").mean() * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Horas consumidas no período", f"{num(TOP_HORAS['Horas Totais'], 0)} h")
    c2.metric("Participação no esforço total", f"{pct(TOP_HORAS['% do Esforço'], 1)}")
    c3.metric("Horas que são tratamento manual", f"{num(horas_manual_top, 0)} h")
    c3.caption(f"{pct(pct_manual_top, 1)} dos chamados da anomalia")

    st.markdown(
        f"""
**Por quê.** `{TOP_HORAS[COL_ANOMALIA]}` consome **{pct(TOP_HORAS['% do Esforço'], 1)} de todo o
esforço humano** do período, combinando volume alto com tempo unitário alto. E
**{pct(pct_manual_top, 1)} dos seus chamados são manuais**, respondendo por
{num(horas_manual_top, 0)} das {num(TOP_HORAS['Horas Totais'], 0)} horas — ou seja, o custo está
concentrado justamente na parte automatizável.

**Impacto estimado.** Migrar essa anomalia para tratamento massivo liberaria a maior parte dessas
horas. Em termos de capacidade, é o equivalente a
**{num(horas_manual_top / max(DIAS_UTEIS_BASE * SATURACAO_HORAS_DIA, 1e-9), 1)} pessoa(s) em tempo
integral** devolvidas à operação no mesmo período.

**O que seria necessário.** Identificar por que esses casos não entram nas liberações em lote:
faltam critérios objetivos de agrupamento, ou há exigência de conferência individual? Se for a
segunda, vale medir quantos desses tratamentos terminam em "Sem Correção" — se a maioria terminar,
a conferência não está encontrando erro.
"""
    )

    st.divider()

    # -------------------------------------------------- RECOMENDAÇÃO 3 ------
    st.subheader("3. Calibrar as regras que mais geram retenção sem erro real")
    c1, c2 = st.columns([1, 1.6])
    with c1:
        st.metric("Retenções liberadas SEM correção", f"{pct(PCT_SEM_CORRECAO, 1)}")
        st.caption("do total de chamados do período")
        tipo_trat = core.distribuicao_por(DF, COL_TIPO_TRATAMENTO)
        fig = go.Figure(go.Pie(
            labels=tipo_trat[COL_TIPO_TRATAMENTO], values=tipo_trat["Chamados"],
            hole=0.55, marker=dict(colors=[AZUL_CLARO, AMBAR]),
            textinfo="label+percent", textfont=dict(size=13),
            insidetextorientation="horizontal",
            hovertemplate="%{label}<br>%{value:,.0f} chamados<extra></extra>",
        ))
        st.plotly_chart(
            estilizar(fig, 280, title="Tratamentos com e sem correção", showlegend=False),
            width="stretch", config=CONFIG_GRAFICO,
        )
    with c2:
        st.markdown(
            f"""
**Por quê.** **{pct(PCT_SEM_CORRECAO, 1)} das retenções são liberadas sem nenhuma correção** — ou
seja, o documento estava certo e a regra o barrou por engano. São **falsos positivos das regras de
validação**: trabalho humano gasto para dizer "está tudo certo, pode passar".

**Impacto estimado.** Cada retenção indevida eliminada é uma fila que **nunca se forma** — economia
maior que tratar mais rápido, porque não consome nem análise nem prazo. Metade do volume atual da
operação está nessa categoria.

**O que seria necessário.** Ranquear as regras pela taxa de "Sem Correção" e revisar as piores, uma
a uma, com quem definiu o critério. É preciso cautela: uma regra de retenção existe para evitar
faturamento errado, e afrouxá-la tem custo do outro lado. A decisão de tolerância é do negócio, não
da análise — mas **hoje ela está sendo tomada sem o número na mesa**, e este painel o coloca lá.

**Ressalva honesta.** "Sem Correção" pode incluir casos em que a análise humana era genuinamente
necessária para concluir que estava tudo bem. O número é o ponto de partida da conversa, não a
resposta pronta.
"""
        )

    st.divider()

    # -------------------------------------------------- RECOMENDAÇÃO 4 ------
    st.subheader("4. Redistribuir a fila concentrada — e corrigir a classificação do tipo de liberação")
    st.markdown(
        f"""
**Por quê.** A fila `{OFENSORA}` está concentrada em uma única pessoa, o que produz um indicador
individual pior sem que isso reflita desempenho. Redistribuir a fila reduz o risco de dependência
de uma pessoa só e corrige a distorção do indicador.

**Em paralelo,** a inconsistência de classificação apontada no Achado 2 precisa ser resolvida na
origem: enquanto trabalho em lote for registrado como manual, **qualquer medição de capacidade
desta área ficará errada** — inclusive a que sustenta pedidos de headcount.

**O que seria necessário.** Uma revisão de como o `Tipo de Liberação` é preenchido no sistema, e
uma regra clara de rodízio ou de balanceamento de fila por volume. Nenhuma das duas exige projeto:
são ajustes de processo e de cadastro.
"""
    )

    st.success(
        f"**Se a gestão só puder fazer uma coisa:** atacar `{OFENSORA}`. "
        f"É {pct(linha_of['% do Volume'], 1)} do volume e "
        f"{pct(IMPACTO['pct_das_quebras'], 1)} de todas as quebras de SLA, e resolvê-la sozinha leva "
        f"o indicador de {pct(IMPACTO['sla_atual'], 2)} para {pct(IMPACTO['sla_novo'], 2)}."
        if IMPACTO else "",
        icon="✅",
    )


# ==============================================================================
# ABA 4 — RACIONAL ANALÍTICO
# ==============================================================================

with aba_racional:
    st.header("Racional analítico")
    st.markdown(
        "Por que estes indicadores, por que estas visualizações, e o que foi decidido onde a "
        "planilha era ambígua. **Cada decisão vem com o custo da alternativa**, para que possa ser "
        "contestada com número e não com opinião."
    )

    st.subheader("Por que estes KPIs")
    st.table(pd.DataFrame([
        ("% fora do SLA",
         "É o único indicador com meta explícita na planilha (2 dias). Mede diretamente receita "
         "retida além do prazo.",
         "Sozinho, esconde concentração — por isso vem sempre acompanhado da decomposição por anomalia."),
        ("% manual vs massivo — em volume E em esforço",
         "O par revela o desequilíbrio que nenhum dos dois mostra sozinho. É o que transforma "
         "'temos muito volume' em 'o custo está em outro lugar'.",
         "Depende do tempo médio cadastrado, que é estimado (Achado 3)."),
        ("Esforço total em horas / FTE",
         "Converte fila em capacidade: responde 'quantas pessoas esse volume exige?', que é a "
         "pergunta de dimensionamento.",
         "É estimativa derivada de parâmetro estimado; serve para ordem de grandeza e comparação."),
        ("Dias-pessoa acima da saturação",
         "Separa 'equipe sobrecarregada' de 'volume concentrado'. Aqui mostrou que não há problema "
         "sistêmico de capacidade.",
         "Sensível à classificação manual/massivo (Achado 2)."),
        ("% resolvido no mesmo dia",
         "Mostra que a operação é rápida no caso típico, o que direciona a atenção para a cauda em "
         "vez do processo inteiro.",
         "Não captura o que ainda não foi tratado (nesta base, zero registros em aberto)."),
    ], columns=["Indicador", "Por que foi escolhido", "Limitação conhecida"]))

    st.subheader("Por que estas visualizações")
    st.table(pd.DataFrame([
        ("Barras por dias até o tratamento, coloridas pelo SLA",
         "Mostra a forma da distribuição e a linha de corte no mesmo objeto. Uma média esconderia "
         "que 80% sai no mesmo dia e uma minoria fica semanas."),
        ("Barras 100% empilhadas: volume vs esforço",
         "O contraste é o conteúdo. Duas barras normalizadas lado a lado deixam a inversão óbvia "
         "sem exigir que o leitor compare escalas diferentes."),
        ("Barras horizontais ordenadas para todos os rankings",
         "Rótulo longo cabe, a ordem é imediata e a comparação é de comprimento — a codificação "
         "visual mais precisa que existe. Pizza foi evitada exceto onde há só duas categorias."),
        ("Volume semanal em barras + % fora do SLA em linha",
         "Duas grandezas de natureza diferente no mesmo eixo temporal, para responder se o atraso "
         "acompanha o volume. Aqui, mostra que não acompanha."),
        ("Tabela de composição da carteira ao lado da carga",
         "Impede a leitura de produtividade individual: o número só faz sentido junto da fila que "
         "cada pessoa recebe."),
    ], columns=["Visualização", "Por que esta e não outra"]))

    st.subheader("Decisões metodológicas — e o custo de cada alternativa")

    cen = DADOS["cenarios_sla"]
    adotado = cen.get("Dias corridos, <= 2 (ADOTADO)")
    rigido = cen.get("Dias corridos, < 2 (mais rígido)")
    uteis = cen.get("Dias úteis seg-sáb, <= 2")

    with st.expander("**[D4] Tratamento massivo: tempo rateado no lote** — a decisão mais importante", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Esforço — modelo adotado", f"{num(META['esforco']['horas_adotado'], 0)} h")
        c2.metric("Esforço — cenário ingênuo", f"{num(META['esforco']['horas_ingenuo'], 0)} h")
        c2.caption(f"{num(META['esforco']['fator'], 1)}× o modelo adotado")
        c3.metric("Maior lote massivo da base", num(META["esforco"]["lote_maximo"]))
        c3.caption("chamados resolvidos numa única execução")
        st.markdown(
            f"""
**O problema.** Um tratamento massivo resolve o lote inteiro numa execução. Atribuir o tempo médio
**cheio** a cada chamado faria o maior lote da base ({num(META['esforco']['lote_maximo'])} documentos)
custar centenas de horas em um único dia, para uma pessoa.

**A regra adotada.** `MANUAL` recebe o tempo cheio por chamado; `MASSIVO` tem o tempo contado **uma
vez por lote** e rateado entre os chamados — o total por lote fica correto e cada linha continua
auditável. Lote = mesma pessoa, mesmo dia, mesma anomalia, mesma forma de liberação.

**O custo da alternativa.** O cenário ingênuo produziria **{num(META['esforco']['fator'], 1)}× mais
esforço** ({num(META['esforco']['horas_ingenuo'], 0)} h contra {num(META['esforco']['horas_adotado'], 0)} h)
e levaria os dias saturados de {pct(PCT_ESTOURO, 1)} para
{pct(int(SATURACAO['Estourou Saturação (Cenário Ingênuo)'].sum()) / max(len(SATURACAO), 1) * 100, 1)}.
Seria um número que não sobrevive à primeira pergunta.

**Transparência.** Os dois cenários são calculados e ficam lado a lado na base exportada
(`Horas Atribuídas` e `Horas (Cenário Ingênuo)`), para que a premissa possa ser contestada e
recalculada.
"""
        )

    with st.expander("**[D1] e [D2] Dias corridos, e SLA como `<= 2`**"):
        st.table(pd.DataFrame({
            "Convenção": list(cen.keys()),
            "% fora do SLA": [f"{pct(v, 2)}" for v in cen.values()],
        }))
        st.markdown(
            f"""
**Dias corridos, não úteis.** A planilha diz apenas "2 dias", sem qualificar. E a base registra
**{SABADOS}** tratamentos aos sábados e
**nenhum** aos domingos: a operação não segue calendário útil seg-sex. Usar dias úteis padrão
perdoaria automaticamente todo atraso que atravessa o fim de semana — e levaria o indicador de
{pct(adotado, 2)} para {pct(uteis, 2)}, quase o dobrando de otimismo.

**`<= 2`, não `< 2`.** "Prazo esperado: 2 dias" descreve um teto: quem entrega em 2 dias cumpriu o
combinado. Ler como `< 2` transformaria o prazo em 1 dia e reprovaria quem fez o acordado — e
moveria o indicador de {pct(adotado, 2)} para **{pct(rigido, 2)}**, uma diferença de
{num(rigido - adotado, 2)} pontos percentuais. A convenção adotada é a leitura literal; a alternativa
está aqui para quem discordar poder recalcular.
"""
        )

    with st.expander("**[D3] e [D7] Anomalias em aberto e registros inconsistentes**"):
        st.markdown(
            f"""
**[D3] Anomalia sem tratamento não sai do denominador.** Registro sem `Data de Tratamento` seria
uma anomalia em aberto: ele permaneceria na base, envelhecido contra a **data máxima observada**
(não contra "hoje", que tornaria o resultado irreprodutível), e contaria como fora do prazo se já
tivesse ultrapassado o SLA. Excluir o não tratado é a forma clássica de fabricar um SLA bonito.
Nesta base o total é **{META['sla']['sem_tratamento']}** — o código trata o caso e reporta o zero.

**[D7] Registros com data invertida são sinalizados, não descartados.** Os
{num(META['sla']['invertidos'])} registros do Achado 1 ficam na base com a flag
`Registro Inconsistente`, saem do denominador do SLA e têm a contagem reportada. A decisão nos
prejudica: mantê-los contaria atraso negativo como "dentro do prazo".
"""
        )

    with st.expander("**[D5] Por que dois rankings de 'tempo gasto'**"):
        st.markdown(
            """
"Maior tempo gasto" é ambíguo e as duas leituras levam a decisões opostas de priorização. Por
**tempo total**, a líder é a anomalia onde a operação queima horas — alvo de automação. Por **tempo
médio unitário**, a líder é a mais cara por ocorrência, que pode ter volume irrelevante. Entregar
só o ranking unitário levaria a priorizar a anomalia errada. Por isso os três recortes aparecem
juntos na aba de Diagnóstico.
"""
        )

    st.subheader("Validações executadas")
    st.markdown(
        "Provar que se conferiu vale tanto quanto o resultado. Estas checagens rodam a cada "
        "execução e **falham alto** em vez de produzir número errado em silêncio:"
    )
    st.table(pd.DataFrame([
        ("Colunas obrigatórias existem com o nome exato",
         "Comparação contra lista fixa; `ValueError` se faltar",
         "8 de 8 encontradas"),
        ("O merge não multiplicou linhas",
         "`validate='many_to_one'` + comparação de contagem com `AssertionError`",
         f"{num(META['merge']['linhas_antes'])} → {num(META['merge']['linhas_depois'])}"),
        ("Nenhuma anomalia ficou sem tempo médio",
         "Contagem de nulos após o merge, com as chaves normalizadas (sem acento, sem espaço extra, caixa única)",
         f"{META['merge']['sem_tempo']} linhas sem tempo"),
        ("Chave de tempos sem duplicata",
         "Checagem de `duplicated()` antes do merge",
         f"{META['tempos']['duplicadas']} duplicadas em {META['tempos']['qtd']} anomalias"),
        ("Datas convertidas sem perda",
         "`to_datetime(errors='coerce')` com contagem de nulos antes e depois",
         "0 não convertidas"),
        ("Cadastro mais amplo que a base",
         "Diferença de conjuntos nos dois sentidos",
         f"{len(META['merge']['nao_usadas'])} anomalias cadastradas sem ocorrência no período"),
    ], columns=["O que foi validado", "Como", "Resultado"]))

    st.caption(
        "O ponto não é que as validações passaram: é que o número aparece **mesmo quando é zero**. "
        "Se 4.000 linhas ficassem sem tempo médio, elas apareceriam aqui em vez de virar hora zero "
        "em algum somatório."
    )

    st.subheader("O que faríamos com mais tempo")
    st.markdown(
        f"""
1. **Validar com a área** as três perguntas de qualidade de dado da aba de Achados — elas mudam a
   magnitude das horas, ainda que não a direção das conclusões.
2. **Entender a sazonalidade do volume.** O volume mensal varia muito ao longo do semestre e a base
   não explica por quê. Se for sazonal, muda o dimensionamento da equipe.
3. **Ranquear as regras por taxa de falso positivo** e simular o efeito de calibrar as piores.
4. **Simulação de capacidade**: dado o volume projetado e o mix manual/massivo, quantas pessoas a
   fila exige — e quanto cada automação devolve em FTE.
"""
    )


# ==============================================================================
# ABA 5 — A BASE
# ==============================================================================

with aba_base:
    st.header("A base de dados")
    st.markdown(
        f"""
A fonte é a planilha `Case_Processo_Seletivo.xlsx`, com três abas: **Expectativa** (o enunciado do
desafio), **Base de Dados** (o fato) e **Premissas e Informações** (os parâmetros).

**A granularidade importa:** uma linha é **uma retenção aplicada a um documento, e o seu
tratamento** — não um documento e não um dia de trabalho. Há
{num(DF['Documento'].nunique())} documentos distintos para {num(TOTAL)} linhas, ou seja
**{num(TOTAL / max(DF['Documento'].nunique(), 1), 2)} anomalias por documento** em média. Um mesmo
documento pode ser retido por várias regras diferentes, e cada retenção é tratada individualmente.
"""
    )

    st.subheader("Dicionário de campos (texto literal da planilha)")
    dicionario = DADOS["dicionario"]
    if not dicionario.empty:
        st.dataframe(dicionario, hide_index=True, width="stretch")
    st.caption(
        "O dicionário documenta 7 campos, mas a base tem 8 colunas: `Documento` não é descrito. "
        "É a diferença entre o que a área considera campo de negócio e a chave técnica que veio junto."
    )

    st.subheader("Tempo médio de tratamento cadastrado por anomalia")
    tempos_exibir = DADOS["tempos"][[COL_ANOMALIA, "Tempo Médio (s)", "Tempo Médio (min)"]].copy()
    volume_por_anomalia = BASE.groupby(COL_ANOMALIA).size()
    tempos_exibir["Chamados na base"] = tempos_exibir[COL_ANOMALIA].map(volume_por_anomalia).fillna(0).astype(int)
    tempos_exibir = tempos_exibir.sort_values("Tempo Médio (s)", ascending=False)
    st.dataframe(
        tempos_exibir.style.format({
            "Tempo Médio (s)": (lambda v: num(v, 0)), "Tempo Médio (min)": (lambda v: num(v, 2)),
            "Chamados na base": lambda v: num(v),
        }),
        hide_index=True, width="stretch", height=340,
    )
    st.caption(
        f"{len(DADOS['tempos'])} anomalias cadastradas; "
        f"{len(META['merge']['nao_usadas'])} delas não ocorrem no período analisado. "
        "Veja o Achado 3 sobre a repetição de valores nesta tabela."
    )

    st.subheader("Enunciado do desafio (aba Expectativa, na íntegra)")
    with st.expander("Ver o texto completo"):
        for linha_texto in DADOS["expectativa"]:
            st.markdown(f"- {linha_texto}")

    st.subheader("Base enriquecida")
    st.markdown(
        "Amostra da base com as colunas calculadas pela análise: tempo de tratamento, flags de SLA "
        "e de consistência, tempo médio, tamanho do lote e esforço atribuído nos dois cenários."
    )
    colunas_amostra = [
        "Documento", COL_ANOMALIA, COL_DT_ANOMALIA, COL_DT_TRATAMENTO, COL_TIPO_LIBERACAO,
        COL_COLABORADOR, "Dias para Tratamento", "Dentro do SLA", "Tempo Médio (min)",
        "Tamanho do Lote", "Horas Atribuídas",
    ]
    st.dataframe(DF[colunas_amostra].head(200), hide_index=True, width="stretch", height=320)
    st.caption(
        f"Exibindo 200 de {num(TOTAL)} linhas. A base completa, com todas as colunas e as abas de "
        "resumo, está em `resultado_analise.xlsx`."
    )

st.divider()
st.header("Materiais para download")
st.markdown(
    "Os quatro arquivos abaixo são os mesmos que sustentam este painel. "
    "Todos os números saem da planilha original, processada pelo módulo de análise."
)

col_d1, col_d2, col_d3, col_d4 = st.columns(4)
with col_d1:
    botao_download(
        "DOCUMENTO_ANALISE.docx", "Análise em Word",
        "Contexto, diagnóstico, achados, recomendações e racional analítico, em texto",
        MIME_DOCX, "dl_docx",
    )
with col_d2:
    botao_download(
        "resultado_analise.xlsx", "Base enriquecida em Excel",
        "163.811 linhas com as colunas calculadas e oito abas de resumo",
        MIME_XLSX, "dl_xlsx",
    )
with col_d3:
    botao_download(
        "Case_Processo_Seletivo.xlsx", "Planilha original",
        "A fonte, sem alteração: Base de Dados, Premissas e Expectativa",
        MIME_XLSX, "dl_fonte",
    )
with col_d4:
    botao_download(
        "analise_core.py", "Módulo de análise",
        "O núcleo com toda a regra de cálculo e as decisões [D1] a [D7] documentadas",
        MIME_PY, "dl_core",
    )

with st.expander("Também disponível: o log da execução com as validações"):
    st.markdown(
        "Saída completa do processamento, do inventário das colunas ao painel final. "
        "Inclui as checagens de integridade: contagem de linhas antes e depois da junção, "
        "linhas sem tempo médio, chaves duplicadas e datas não convertidas."
    )
    botao_download(
        "saida_execucao.txt", "Baixar o log da execução",
        "Auditoria do processamento", MIME_TXT, "dl_log",
    )

st.divider()
st.caption(
    "Case de processo seletivo · Análise de anomalias de faturamento · "
    "Todos os números são calculados a partir de `Case_Processo_Seletivo.xlsx` pelo módulo "
    "`analise_core.py`, o mesmo que gera o relatório `analise_anomalias.py` — regra de negócio "
    "em um lugar só, sem divergência entre o painel e o relatório."
)
