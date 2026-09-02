# -*- coding: utf-8 -*-
"""
================================================================================
NÚCLEO ANALÍTICO — CASE DE ANOMALIAS DE FATURAMENTO
================================================================================
Este módulo concentra TODA a regra de negócio da análise. Ele não imprime nada e
não escreve arquivo: só lê a planilha e devolve DataFrames.

Quem consome:
    - `analise_anomalias.py` — relatório de linha de comando e exportação Excel;
    - `app.py`               — dashboard Streamlit.

A regra vive aqui uma única vez. Se o SLA mudar de 2 para 3 dias, muda-se
`SLA_DIAS` neste arquivo e os dois consumidores acompanham.

DECISOES INTERPRETATIVAS [D1] a [D7]
    [D1] "Dias" = dias corridos. A planilha diz apenas "2 dias", sem qualificar,
         e a base tem tratamentos aos sábados e nenhum aos domingos — a operação
         não segue calendário útil seg-sex. `Dias Úteis (Seg-Sáb)` é calculado em
         paralelo, apenas como análise de sensibilidade.
    [D2] SLA cumprido quando `atraso <= 2`, não `< 2`. "Prazo esperado: 2 dias"
         descreve um teto; tratar em 2 dias cumpre o acordo.
    [D3] Anomalia sem 'Data de Tratamento' permanece no denominador, envelhecida
         contra a data máxima observada na base (não contra "hoje", que tornaria
         o resultado irreprodutível).
    [D4] Tratamento massivo resolve o lote em uma execução: o tempo médio é
         contado UMA vez por lote e rateado entre os chamados. Cobrar o tempo
         cheio de cada chamado infla o esforço em ~4,5x.
    [D5] "Maior tempo gasto" é ambíguo: entregamos o ranking por tempo total
         agregado E por tempo médio unitário.
    [D6] A aba 'Expectativa' é o enunciado do desafio, não um formato de saída.
    [D7] Tratamento anterior à anomalia é impossível no processo: o registro é
         sinalizado e sai do denominador do SLA, com a contagem reportada.
================================================================================
"""

from __future__ import annotations

import unicodedata
from datetime import time
from pathlib import Path

import numpy as np
import pandas as pd

# ==============================================================================
# CONSTANTES
# ==============================================================================

# Caminhos resolvidos a partir da pasta do módulo, e não do diretório de onde o
# processo foi iniciado: a hospedagem executa o app de outro lugar.
RAIZ = Path(__file__).resolve().parent
ARQUIVO_ENTRADA = str(RAIZ / "Case_Processo_Seletivo.xlsx")
ARQUIVO_SAIDA = str(RAIZ / "resultado_analise.xlsx")

# Derivado da aba 'Base de Dados', gerado por preparar_dados.py. Existe só por
# desempenho; a planilha continua sendo a fonte da verdade.
PARQUET_BASE = RAIZ / "dados" / "base.parquet"

ABA_BASE = "Base de Dados"
ABA_PREMISSAS = "Premissas e Informações"
ABA_EXPECTATIVA = "Expectativa"

# Premissas lidas literalmente da aba 'Premissas e Informações' (células E3:F4).
SLA_DIAS = 2
SATURACAO_HORAS_DIA = 7

# Limite acima do qual uma jornada diária é fisicamente impossível — usado para
# separar "colaborador sobrecarregado" de "registro inconsistente".
LIMITE_JORNADA_IMPOSSIVEL_H = 24

COL_DOCUMENTO = "Documento"
COL_ANOMALIA = "Anomalia"
COL_DT_ANOMALIA = "Data da Anomalia"
COL_DT_TRATAMENTO = "Data de Tratamento"
COL_TIPO_TRATAMENTO = "Tipo de Tratamento"
COL_TIPO_LIBERACAO = "Tipo de Liberação"
COL_ORIGEM = "Origem"
COL_COLABORADOR = "Colaborador(a)"

COLUNAS_OBRIGATORIAS = [
    COL_DOCUMENTO, COL_ANOMALIA, COL_DT_ANOMALIA, COL_DT_TRATAMENTO,
    COL_TIPO_TRATAMENTO, COL_TIPO_LIBERACAO, COL_ORIGEM, COL_COLABORADOR,
]


# ==============================================================================
# UTILITÁRIOS DE FORMATAÇÃO E NORMALIZAÇÃO
# ==============================================================================

def num(valor, casas: int = 0) -> str:
    """Formata número no padrão pt-BR: ponto como separador de milhar e vírgula
    como separador decimal (evita o clássico '1.644.3' de um replace ingênuo)."""
    if pd.isna(valor):
        return "n/d"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "|").replace(".", ",").replace("|", ".")


def formatar_horas(horas: float) -> str:
    """Formata horas decimais como 'Xh YYmin'."""
    if pd.isna(horas):
        return "n/d"
    total_min = int(round(horas * 60))
    return f"{total_min // 60}h {total_min % 60:02d}min"


def normalizar_chave(serie: pd.Series) -> pd.Series:
    """
    Normaliza uma chave textual para merge: remove acentos, espaços nas bordas,
    espaços internos duplicados e caixa. É a defesa contra o erro clássico de
    divergência de grafia entre a base e a tabela de premissas.
    """
    s = serie.astype("string").fillna("")
    s = s.map(lambda x: unicodedata.normalize("NFKD", x))
    s = s.str.encode("ascii", errors="ignore").str.decode("ascii")
    s = s.str.replace(r"\s+", " ", regex=True).str.strip().str.upper()
    return s


def tempo_para_segundos(valor) -> float:
    """
    Converte a coluna 'Tempo' da aba de Premissas para segundos.

    A célula é formatada como hora (datetime.time) — por exemplo 00:06:10, que no
    contexto operacional significa 6 minutos e 10 segundos de tratamento médio.
    Aceita também string 'HH:MM:SS', Timedelta ou número (fração de dia do Excel).
    """
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return np.nan
    if isinstance(valor, time):
        return valor.hour * 3600 + valor.minute * 60 + valor.second
    if isinstance(valor, pd.Timedelta):
        return valor.total_seconds()
    if isinstance(valor, (int, float)):
        # Serial de tempo do Excel: fração de um dia.
        return float(valor) * 86400
    texto = str(valor).strip()
    partes = texto.split(":")
    if len(partes) == 3:
        h, m, s = (float(p) for p in partes)
        return h * 3600 + m * 60 + s
    if len(partes) == 2:
        m, s = (float(p) for p in partes)
        return m * 60 + s
    return np.nan


def dias_uteis_seg_sab(inicio: pd.Series, fim: pd.Series) -> pd.Series:
    """
    Conta dias entre duas datas excluindo apenas domingos (calendário observado na
    operação: há tratamentos aos sábados e nenhum aos domingos). Usado somente
    como análise de sensibilidade — a métrica oficial é dias corridos [D1].
    Feriados não são descontados: não há calendário de feriados na planilha.
    """
    validos = inicio.notna() & fim.notna()
    resultado = pd.Series(np.nan, index=inicio.index, dtype="float64")
    if not validos.any():
        return resultado
    ini = inicio[validos].dt.date.to_numpy().astype("datetime64[D]")
    fi = fim[validos].dt.date.to_numpy().astype("datetime64[D]")
    # Semana de trabalho de segunda a sábado (domingo = 0 na máscara).
    contagem = np.busday_count(ini, fi, weekmask="1111110").astype("float64")
    resultado.loc[validos] = contagem
    return resultado


# ==============================================================================
# LEITURA DA PLANILHA
# ==============================================================================

def carregar_planilha(caminho: str = ARQUIVO_ENTRADA, usar_cache: bool = True) -> dict:
    """
    Lê as três abas e valida a presença das colunas obrigatórias.

    Falha alto (ValueError) se a estrutura mudar, em vez de calcular errado em
    silêncio a partir de uma coluna que não é a esperada.

    Desempenho: ler as 163 mil linhas da aba 'Base de Dados' com o openpyxl leva
    cerca de 8 segundos, o que pesa a cada partida a frio na hospedagem. Quando
    existe o Parquet derivado (`dados/base.parquet`, gerado por
    `preparar_dados.py`), ele é usado no lugar. O conteúdo é idêntico, incluindo
    os dtypes; a planilha continua sendo a fonte da verdade e o Parquet é
    descartável. `usar_cache=False` força a leitura do .xlsx.
    """
    excel = pd.ExcelFile(caminho)
    for aba in (ABA_BASE, ABA_PREMISSAS, ABA_EXPECTATIVA):
        if aba not in excel.sheet_names:
            raise ValueError(f"Aba obrigatória ausente na planilha: {aba!r}")

    origem_base = "planilha"
    if usar_cache and PARQUET_BASE.exists():
        base = pd.read_parquet(PARQUET_BASE)
        origem_base = "parquet"
    else:
        base = pd.read_excel(caminho, sheet_name=ABA_BASE)

    faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in base.columns]
    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes na Base de Dados: {faltantes}")

    return {
        "origem_base": origem_base,
        "caminho": caminho,
        "abas": list(excel.sheet_names),
        "base": base,
        "premissas_raw": pd.read_excel(caminho, sheet_name=ABA_PREMISSAS, header=None),
        "expectativa_raw": pd.read_excel(caminho, sheet_name=ABA_EXPECTATIVA, header=None),
    }


def texto_expectativa(expectativa_raw: pd.DataFrame) -> list:
    """Devolve as linhas não vazias da aba 'Expectativa', na ordem original."""
    linhas = []
    for _, linha in expectativa_raw.iterrows():
        textos = [str(v).strip() for v in linha if pd.notna(v) and str(v).strip()]
        if textos:
            linhas.append(" | ".join(textos))
    return linhas


def extrair_tempos_medios(premissas_raw: pd.DataFrame) -> tuple:
    """
    Localiza dinamicamente a tabela 'Anomalia' x 'Tempo' dentro da aba de
    Premissas (ela não começa na linha 1 — a aba tem três blocos lado a lado com
    títulos mesclados) e a devolve com o tempo convertido para segundos.

    Retorna (tempos, meta).
    """
    pos_anomalia = pos_tempo = None
    for idx_linha in range(len(premissas_raw)):
        for idx_col in range(premissas_raw.shape[1]):
            valor = premissas_raw.iat[idx_linha, idx_col]
            if isinstance(valor, str) and valor.strip().upper() == "ANOMALIA":
                # O cabeçalho da tabela de tempos tem 'Tempo' imediatamente à direita.
                direita = (
                    premissas_raw.iat[idx_linha, idx_col + 1]
                    if idx_col + 1 < premissas_raw.shape[1] else None
                )
                if isinstance(direita, str) and direita.strip().upper() == "TEMPO":
                    pos_anomalia = (idx_linha, idx_col)
                    pos_tempo = (idx_linha, idx_col + 1)
                    break
        if pos_anomalia:
            break

    if pos_anomalia is None:
        raise ValueError("Não foi possível localizar o cabeçalho 'Anomalia'/'Tempo' na aba de Premissas.")

    linha_cab, col_anom = pos_anomalia
    col_tempo = pos_tempo[1]

    dados = premissas_raw.iloc[linha_cab + 1:, [col_anom, col_tempo]].copy()
    dados.columns = [COL_ANOMALIA, "Tempo"]
    dados = dados[dados[COL_ANOMALIA].notna()].reset_index(drop=True)

    dados["Tempo Médio (s)"] = dados["Tempo"].map(tempo_para_segundos)
    dados["Tempo Médio (min)"] = dados["Tempo Médio (s)"] / 60
    dados["chave_anomalia"] = normalizar_chave(dados[COL_ANOMALIA])

    duplicadas = int(dados["chave_anomalia"].duplicated().sum())
    if duplicadas:
        # Chave duplicada no lado direito de um merge multiplica linhas e infla
        # todos os totais silenciosamente. Mantemos a primeira ocorrência.
        dados = dados.drop_duplicates(subset="chave_anomalia", keep="first")

    meta = {
        "linha_cabecalho": linha_cab + 1,
        "coluna_anomalia": col_anom,
        "coluna_tempo": col_tempo,
        "duplicadas": duplicadas,
        "qtd": len(dados),
    }
    return dados, meta


def extrair_dicionario(premissas_raw: pd.DataFrame) -> pd.DataFrame:
    """Extrai o bloco 'Dados Complementares' (dicionário de campos) da aba de
    Premissas, localizado pelo rótulo, não por posição fixa."""
    for idx_linha in range(len(premissas_raw)):
        for idx_col in range(premissas_raw.shape[1] - 1):
            valor = premissas_raw.iat[idx_linha, idx_col]
            direita = premissas_raw.iat[idx_linha, idx_col + 1]
            if (isinstance(valor, str) and valor.strip().upper() == "ANOMALIA"
                    and isinstance(direita, str) and len(str(direita)) > 30):
                dados = premissas_raw.iloc[idx_linha:, [idx_col, idx_col + 1]].copy()
                dados.columns = ["Campo", "Definição"]
                return dados[dados["Campo"].notna()].reset_index(drop=True)
    return pd.DataFrame(columns=["Campo", "Definição"])


# ==============================================================================
# ETAPA 1 — LIMPEZA, TEMPO DE TRATAMENTO E SLA
# ==============================================================================

def preparar_e_calcular_sla(base: pd.DataFrame) -> tuple:
    """
    Converte as datas, calcula o atraso em dias e cria a flag 'Dentro do SLA'.
    Aplica [D1], [D2], [D3] e [D7]. Retorna (df, meta).
    """
    df = base.copy()

    # Datas vêm como texto ISO (AAAA-MM-DD). Conversão explícita; o que não
    # converter vira NaT e é auditado — não sai como número errado.
    conversao = {}
    for coluna in (COL_DT_ANOMALIA, COL_DT_TRATAMENTO):
        antes = int(df[coluna].isna().sum())
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce")
        depois = int(df[coluna].isna().sum())
        conversao[coluna] = {"antes": antes, "depois": depois, "nao_convertidos": depois - antes}

    # Normalização das chaves textuais (usadas no merge e nos agrupamentos).
    df["chave_anomalia"] = normalizar_chave(df[COL_ANOMALIA])
    df[COL_TIPO_LIBERACAO] = df[COL_TIPO_LIBERACAO].astype("string").str.strip().str.upper()
    df[COL_TIPO_TRATAMENTO] = df[COL_TIPO_TRATAMENTO].astype("string").str.strip().str.title()
    df[COL_COLABORADOR] = df[COL_COLABORADOR].astype("string").str.strip().str.upper()

    # --- Tempo de tratamento -------------------------------------------------
    df["Dias para Tratamento"] = (df[COL_DT_TRATAMENTO] - df[COL_DT_ANOMALIA]).dt.days
    df["Dias Úteis (Seg-Sáb)"] = dias_uteis_seg_sab(df[COL_DT_ANOMALIA], df[COL_DT_TRATAMENTO])

    # --- Auditoria de consistência [D3] e [D7] -------------------------------
    sem_tratamento = df[COL_DT_TRATAMENTO].isna()
    sem_data_anomalia = df[COL_DT_ANOMALIA].isna()
    invertidos = df["Dias para Tratamento"].notna() & (df["Dias para Tratamento"] < 0)

    df["Registro Inconsistente"] = invertidos
    df["Anomalia em Aberto"] = sem_tratamento

    # --- Flag 'Dentro do SLA' ------------------------------------------------
    # Data de corte para envelhecer anomalias em aberto: a data mais recente
    # observada na base (não "hoje", que tornaria o resultado irreprodutível).
    data_corte = pd.concat([df[COL_DT_ANOMALIA], df[COL_DT_TRATAMENTO]]).max()
    idade_em_aberto = (data_corte - df[COL_DT_ANOMALIA]).dt.days

    dentro = pd.Series(pd.NA, index=df.index, dtype="boolean")
    # Caso 1 — tratado e consistente: cumpre o SLA se levou até 2 dias [D2].
    tratado_ok = df[COL_DT_TRATAMENTO].notna() & ~invertidos & df["Dias para Tratamento"].notna()
    dentro.loc[tratado_ok] = df.loc[tratado_ok, "Dias para Tratamento"] <= SLA_DIAS
    # Caso 2 — em aberto [D3]: continua no denominador; estoura o SLA se já
    # envelheceu mais que o prazo.
    em_aberto_com_data = sem_tratamento & df[COL_DT_ANOMALIA].notna()
    dentro.loc[em_aberto_com_data] = idade_em_aberto[em_aberto_com_data] <= SLA_DIAS
    # Caso 3 — inconsistentes [D7] e sem data de anomalia: permanecem nulos.

    df["Dentro do SLA"] = dentro
    df["Fora do SLA"] = dentro.eq(False)

    meta = {
        "conversao": conversao,
        "sem_tratamento": int(sem_tratamento.sum()),
        "sem_data_anomalia": int(sem_data_anomalia.sum()),
        "invertidos": int(invertidos.sum()),
        "distribuicao_invertidos": dict(
            df.loc[invertidos, "Dias para Tratamento"].value_counts().sort_index()
        ),
        "data_corte": data_corte,
        "mascara_tratado_ok": tratado_ok,
        "avaliaveis": int(dentro.notna().sum()),
        "dentro": int(dentro.eq(True).sum()),
        "fora": int(dentro.eq(False).sum()),
        "total": len(df),
    }
    return df, meta


def cenarios_sla(df: pd.DataFrame, mascara_tratado_ok: pd.Series) -> dict:
    """
    Sensibilidade das convenções de cálculo do SLA. Mostra explicitamente o custo
    de cada escolha, para que a decisão adotada possa ser contestada com número.
    """
    base_av = df.loc[df["Dentro do SLA"].notna() & mascara_tratado_ok]
    cenarios = {
        "Dias corridos, <= 2 (ADOTADO)": base_av["Dias para Tratamento"] <= 2,
        "Dias corridos, < 2 (mais rígido)": base_av["Dias para Tratamento"] < 2,
        "Dias úteis seg-sáb, <= 2": base_av["Dias Úteis (Seg-Sáb)"] <= 2,
    }
    return {nome: (1 - mascara.mean()) * 100 for nome, mascara in cenarios.items()}


# ==============================================================================
# ETAPA 2 — MERGE COM OS TEMPOS MÉDIOS
# ==============================================================================

def merge_tempos_medios(df: pd.DataFrame, tempos: pd.DataFrame) -> tuple:
    """
    Junta a base com a tabela de tempos médios pela chave normalizada e audita a
    cobertura: nenhuma linha sai com tempo médio NaN sem que isso seja contado.
    Retorna (df, meta).
    """
    linhas_antes = len(df)
    colunas_tempo = ["chave_anomalia", "Tempo Médio (s)", "Tempo Médio (min)"]
    resultado = df.merge(
        tempos[colunas_tempo], on="chave_anomalia", how="left", validate="many_to_one"
    )
    if len(resultado) != linhas_antes:
        raise AssertionError("O merge alterou a contagem de linhas — chave de tempos duplicada.")

    sem_tempo = resultado["Tempo Médio (s)"].isna()
    faltantes = (
        resultado.loc[sem_tempo, COL_ANOMALIA]
        .value_counts().rename_axis("Anomalia").reset_index(name="Chamados")
    )
    nao_usadas = sorted(
        set(tempos["chave_anomalia"].unique()) - set(resultado["chave_anomalia"].unique())
    )

    meta = {
        "linhas_antes": linhas_antes,
        "linhas_depois": len(resultado),
        "sem_tempo": int(sem_tempo.sum()),
        "faltantes": faltantes,
        "nao_usadas": nao_usadas,
    }
    return resultado, meta


# ==============================================================================
# ETAPA 3 — ESFORÇO E SATURAÇÃO
# ==============================================================================

def calcular_esforco(df: pd.DataFrame) -> tuple:
    """
    Converte cada chamado em esforço (horas), tratando o massivo conforme [D4].

    Cenário ADOTADO ('Horas Atribuídas'):
        MANUAL  -> tempo médio cheio por chamado (cada um foi tratado sozinho).
        MASSIVO -> tempo médio contado UMA vez por lote, rateado entre os
                   chamados do lote (o total por lote fica correto e cada linha
                   continua auditável).
    Cenário de controle ('Horas (Cenário Ingênuo)'):
        tempo cheio para todo chamado — serve só para dimensionar o erro.
    """
    resultado = df.copy()
    resultado["Horas (Cenário Ingênuo)"] = resultado["Tempo Médio (s)"] / 3600

    # Lote = mesma pessoa, mesmo dia, mesma anomalia, mesma forma de liberação.
    # É a menor unidade que representa "uma execução".
    chaves_lote = [COL_COLABORADOR, COL_DT_TRATAMENTO, COL_ANOMALIA, COL_TIPO_LIBERACAO]
    resultado["Tamanho do Lote"] = resultado.groupby(
        chaves_lote, dropna=False
    )[COL_DOCUMENTO].transform("size")

    eh_massivo = resultado[COL_TIPO_LIBERACAO].eq("MASSIVO")
    resultado["Horas Atribuídas"] = np.where(
        eh_massivo,
        resultado["Horas (Cenário Ingênuo)"] / resultado["Tamanho do Lote"],
        resultado["Horas (Cenário Ingênuo)"],
    )
    # Execuções equivalentes: 1 por chamado manual, 1 por lote massivo.
    resultado["Execuções Equivalentes"] = np.where(eh_massivo, 1 / resultado["Tamanho do Lote"], 1.0)

    lotes = resultado.loc[eh_massivo].groupby(chaves_lote, dropna=False).size()
    total_adotado = resultado["Horas Atribuídas"].sum()
    total_ingenuo = resultado["Horas (Cenário Ingênuo)"].sum()

    meta = {
        "lotes_massivos": int(len(lotes)),
        "lote_media": float(lotes.mean()) if len(lotes) else np.nan,
        "lote_mediana": float(lotes.median()) if len(lotes) else np.nan,
        "lote_maximo": int(lotes.max()) if len(lotes) else 0,
        "horas_adotado": float(total_adotado),
        "horas_ingenuo": float(total_ingenuo),
        "fator": float(total_ingenuo / max(total_adotado, 1e-9)),
    }
    return resultado, meta


def resumo_saturacao(df: pd.DataFrame) -> tuple:
    """
    Agrega as horas por 'Colaborador(a)' e por dia de tratamento e cria a flag
    'Estourou Saturação' (> 7 h/dia). Retorna (saturacao, por_colaborador).
    """
    tratados = df[df[COL_DT_TRATAMENTO].notna()].copy()

    saturacao = (
        tratados.groupby([COL_COLABORADOR, COL_DT_TRATAMENTO], dropna=False)
        .agg(**{
            "Chamados Tratados": (COL_DOCUMENTO, "size"),
            "Horas Trabalhadas": ("Horas Atribuídas", "sum"),
            "Horas (Cenário Ingênuo)": ("Horas (Cenário Ingênuo)", "sum"),
            "Execuções Equivalentes": ("Execuções Equivalentes", "sum"),
        })
        .reset_index()
        .rename(columns={COL_DT_TRATAMENTO: "Data"})
    )
    saturacao["Estourou Saturação"] = saturacao["Horas Trabalhadas"] > SATURACAO_HORAS_DIA
    saturacao["Estourou Saturação (Cenário Ingênuo)"] = (
        saturacao["Horas (Cenário Ingênuo)"] > SATURACAO_HORAS_DIA
    )
    saturacao["% da Capacidade Diária"] = saturacao["Horas Trabalhadas"] / SATURACAO_HORAS_DIA * 100
    saturacao = saturacao.sort_values("Horas Trabalhadas", ascending=False).reset_index(drop=True)

    por_colaborador = (
        saturacao.groupby(COL_COLABORADOR)
        .agg(**{
            "Dias Trabalhados": ("Data", "nunique"),
            "Chamados Tratados": ("Chamados Tratados", "sum"),
            "Horas Totais": ("Horas Trabalhadas", "sum"),
            "Horas/Dia (média)": ("Horas Trabalhadas", "mean"),
            "Horas/Dia (máximo)": ("Horas Trabalhadas", "max"),
            "Dias com Estouro": ("Estourou Saturação", "sum"),
        })
        .reset_index()
    )
    por_colaborador["% Dias com Estouro"] = (
        por_colaborador["Dias com Estouro"] / por_colaborador["Dias Trabalhados"] * 100
    )
    por_colaborador = por_colaborador.sort_values("Horas Totais", ascending=False).reset_index(drop=True)
    return saturacao, por_colaborador


def dias_impossiveis(saturacao: pd.DataFrame, df: pd.DataFrame,
                     limite: float = LIMITE_JORNADA_IMPOSSIVEL_H) -> tuple:
    """
    Isola os pares (colaborador, dia) com carga acima do limite físico e mede
    quanto deles vem de chamados classificados como MANUAL.

    Mesmo com o rateio correto do massivo [D4], alguns dias ultrapassam a jornada
    humana. Isso não é erro de cálculo: é sintoma de que trabalho em lote está
    registrado como 'MANUAL', ou de que o tempo médio não vale para série.
    """
    impossiveis = saturacao[saturacao["Horas Trabalhadas"] > limite].copy()
    if impossiveis.empty:
        return impossiveis, {"qtd": 0, "pct_manual": np.nan, "horas_manual": 0.0, "horas_total": 0.0}

    detalhe = df.merge(
        impossiveis[[COL_COLABORADOR, "Data"]].rename(columns={"Data": COL_DT_TRATAMENTO}),
        on=[COL_COLABORADOR, COL_DT_TRATAMENTO], how="inner",
    )
    eh_manual = detalhe[COL_TIPO_LIBERACAO].eq("MANUAL")
    meta = {
        "qtd": len(impossiveis),
        "pct_manual": float(eh_manual.mean() * 100),
        "horas_manual": float(detalhe.loc[eh_manual, "Horas Atribuídas"].sum()),
        "horas_total": float(detalhe["Horas Atribuídas"].sum()),
    }
    return impossiveis, meta


# ==============================================================================
# ETAPA 4 — TAXAS E RANKINGS
# ==============================================================================

def distribuicao_liberacao(df: pd.DataFrame) -> pd.DataFrame:
    """Volume x esforço por 'Tipo de Liberação' — o contraste central do case."""
    total = len(df)
    dist = (
        df[COL_TIPO_LIBERACAO].value_counts(dropna=False)
        .rename_axis(COL_TIPO_LIBERACAO).reset_index(name="Chamados")
        .assign(**{"% dos Chamados": lambda x: x["Chamados"] / total * 100})
    )
    esforco = df.groupby(COL_TIPO_LIBERACAO, dropna=False)["Horas Atribuídas"].sum()
    dist["Horas Atribuídas"] = dist[COL_TIPO_LIBERACAO].map(esforco)
    dist["% do Esforço"] = dist["Horas Atribuídas"] / dist["Horas Atribuídas"].sum() * 100
    return dist


def distribuicao_por(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Volume, esforço e % fora do SLA por uma dimensão categórica qualquer."""
    total = len(df)
    tabela = (
        df.groupby(coluna, dropna=False)
        .agg(**{"Chamados": (COL_DOCUMENTO, "size"), "Horas": ("Horas Atribuídas", "sum")})
        .assign(**{
            "% Chamados": lambda x: x["Chamados"] / total * 100,
            "% Fora do SLA": df.groupby(coluna, dropna=False)["Dentro do SLA"].apply(
                lambda s: s.eq(False).sum() / max(s.notna().sum(), 1) * 100
            ),
        })
        .reset_index()
    )
    return tabela


def ranking_anomalias(df: pd.DataFrame) -> dict:
    """
    Ranking das anomalias nas três leituras [D5]: volume, tempo total agregado e
    tempo médio unitário. São perguntas de gestão diferentes.
    """
    ranking = (
        df.groupby(COL_ANOMALIA, dropna=False)
        .agg(**{
            "Chamados": (COL_DOCUMENTO, "size"),
            "Horas Totais": ("Horas Atribuídas", "sum"),
            "Tempo Médio Unitário (min)": ("Tempo Médio (min)", "first"),
            "Chamados Fora do SLA": ("Fora do SLA", "sum"),
            "Dias Médios p/ Tratamento": ("Dias para Tratamento", "mean"),
        })
        .reset_index()
    )
    ranking["% do Volume"] = ranking["Chamados"] / len(df) * 100
    ranking["% do Esforço"] = ranking["Horas Totais"] / ranking["Horas Totais"].sum() * 100
    # Denominador: chamados AVALIÁVEIS da anomalia, e não o volume dela. É o mesmo
    # denominador do indicador geral e dos cortes por origem, para que os recortes
    # possam ser comparados entre si sem ressalva.
    avaliaveis_por_anomalia = df.groupby(COL_ANOMALIA)["Dentro do SLA"].apply(
        lambda s: s.notna().sum()
    )
    ranking["Chamados Avaliáveis"] = ranking[COL_ANOMALIA].map(avaliaveis_por_anomalia)
    ranking["% Fora do SLA"] = (
        ranking["Chamados Fora do SLA"] / ranking["Chamados Avaliáveis"].replace(0, np.nan) * 100
    )
    ranking["% Manual"] = ranking[COL_ANOMALIA].map(
        df.groupby(COL_ANOMALIA)[COL_TIPO_LIBERACAO].apply(lambda s: s.eq("MANUAL").mean() * 100)
    )
    return {
        "ranking": ranking.sort_values("Chamados", ascending=False).reset_index(drop=True),
        "por_volume": ranking.sort_values("Chamados", ascending=False).head(3),
        "por_horas": ranking.sort_values("Horas Totais", ascending=False).head(3),
        "por_unitario": ranking.sort_values("Tempo Médio Unitário (min)", ascending=False).head(3),
    }


def contribuicao_quebras_sla(df: pd.DataFrame, topo: int = 8) -> pd.DataFrame:
    """
    De onde vêm as quebras de SLA. O indicador agregado esconde concentração: é
    esta tabela que revela que metade das quebras está em um único código.
    """
    fora = df[df["Fora do SLA"].eq(True)]
    if fora.empty:
        return pd.DataFrame()
    tabela = fora.groupby(COL_ANOMALIA).size().sort_values(ascending=False).reset_index(
        name="Chamados Fora do SLA"
    )
    tabela["% de Todas as Quebras"] = tabela["Chamados Fora do SLA"] / len(fora) * 100
    # Mesmo denominador do indicador geral: avaliáveis, não volume bruto.
    avaliaveis = df.groupby(COL_ANOMALIA)["Dentro do SLA"].apply(lambda s: s.notna().sum())
    tabela["% do Volume da Anomalia"] = (
        tabela["Chamados Fora do SLA"]
        / tabela[COL_ANOMALIA].map(avaliaveis).replace(0, np.nan) * 100
    )
    tabela["% Acumulado"] = tabela["% de Todas as Quebras"].cumsum()
    return tabela.head(topo)


def impacto_zerar_anomalia(df: pd.DataFrame, anomalia: str) -> dict:
    """
    Simula o efeito, sobre o SLA geral, de eliminar as quebras de UMA anomalia.

    Serve para priorizar recomendação com número, não com opinião: responde
    "se essa fila parasse de estourar, quanto o indicador melhora?".
    """
    avaliaveis = int(df["Dentro do SLA"].notna().sum())
    fora_total = int(df["Fora do SLA"].eq(True).sum())
    fora_alvo = int(df.loc[df[COL_ANOMALIA].eq(anomalia), "Fora do SLA"].eq(True).sum())
    if not avaliaveis:
        return {}
    atual = fora_total / avaliaveis * 100
    novo = (fora_total - fora_alvo) / avaliaveis * 100
    return {
        "anomalia": anomalia,
        "quebras_evitadas": fora_alvo,
        "pct_das_quebras": fora_alvo / max(fora_total, 1) * 100,
        "sla_atual": atual,
        "sla_novo": novo,
        "ganho_pontos": atual - novo,
    }


def esforco_por_liberacao_unitario(df: pd.DataFrame) -> dict:
    """Custo médio de esforço de um chamado manual contra um massivo — a razão
    entre os dois é o argumento quantitativo a favor da automação."""
    resultado = {}
    for tipo in ("MANUAL", "MASSIVO"):
        recorte = df[df[COL_TIPO_LIBERACAO].eq(tipo)]
        resultado[tipo] = (
            recorte["Horas Atribuídas"].sum() / len(recorte) * 60 if len(recorte) else np.nan
        )
    if resultado.get("MASSIVO"):
        resultado["razao"] = resultado["MANUAL"] / resultado["MASSIVO"]
    return resultado


# Abaixo deste número de chamados avaliáveis, o percentual de uma semana é ruído:
# a base tem semanas de pouco mais de cem chamados, onde meia dúzia de atrasos vira
# dezenas de pontos percentuais e domina o gráfico sem significar nada.
PISO_DENOMINADOR_SEMANAL = 500


def serie_temporal(df: pd.DataFrame, freq: str = "W",
                   piso: int = PISO_DENOMINADOR_SEMANAL) -> pd.DataFrame:
    """
    Evolução do volume e do % fora do SLA ao longo do tempo, pela data da
    anomalia (quando o problema nasceu, não quando foi resolvido).

    Períodos com menos de `piso` chamados avaliáveis ficam com o percentual nulo
    em vez de um número instável. A coluna 'Denominador Suficiente' registra quais
    entraram no cálculo.
    """
    temp = df[df[COL_DT_ANOMALIA].notna()].copy()
    temp["periodo"] = temp[COL_DT_ANOMALIA].dt.to_period(freq).dt.start_time
    serie = (
        temp.groupby("periodo")
        .agg(**{
            "Chamados": (COL_DOCUMENTO, "size"),
            "Fora do SLA": ("Fora do SLA", "sum"),
            "Avaliáveis": ("Dentro do SLA", lambda s: s.notna().sum()),
            "Horas": ("Horas Atribuídas", "sum"),
        })
        .reset_index()
    )
    serie["% Fora do SLA"] = serie["Fora do SLA"] / serie["Avaliáveis"].replace(0, np.nan) * 100
    serie["Denominador Suficiente"] = serie["Avaliáveis"] >= piso
    serie.loc[~serie["Denominador Suficiente"], "% Fora do SLA"] = np.nan
    return serie


def distribuicao_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Volume e cumprimento de prazo por mês de geração da anomalia.

    A leitura mensal é a defensável para relacionar volume e atraso: no semanal,
    períodos de poucas centenas de chamados produzem percentuais instáveis.
    """
    temp = df[df[COL_DT_ANOMALIA].notna()].copy()
    temp["Mês"] = temp[COL_DT_ANOMALIA].dt.to_period("M").astype(str)
    total_fora = int(df["Fora do SLA"].eq(True).sum())
    mensal = (
        temp.groupby("Mês")
        .agg(**{
            "Chamados": (COL_DOCUMENTO, "size"),
            "Avaliáveis": ("Dentro do SLA", lambda s: s.notna().sum()),
            "Fora do SLA": ("Fora do SLA", "sum"),
        })
        .reset_index()
    )
    mensal["% Fora do SLA"] = (
        mensal["Fora do SLA"] / mensal["Avaliáveis"].replace(0, np.nan) * 100
    )
    mensal["% das Quebras do Semestre"] = mensal["Fora do SLA"] / max(total_fora, 1) * 100
    return mensal


def distribuicao_atraso(df: pd.DataFrame, maximo: int = 10) -> pd.DataFrame:
    """Histograma do atraso em dias, com a cauda agrupada no último balde."""
    consistentes = df[df[COL_DT_TRATAMENTO].notna() & ~df["Registro Inconsistente"]]
    contagem = consistentes["Dias para Tratamento"].value_counts().sort_index()
    dentro = contagem[contagem.index <= maximo]
    cauda = int(contagem[contagem.index > maximo].sum())

    tabela = dentro.rename_axis("Dias").reset_index(name="Chamados")
    tabela["Rotulo"] = tabela["Dias"].astype(int).astype(str)
    tabela["Dentro do SLA"] = tabela["Dias"] <= SLA_DIAS
    if cauda:
        tabela = pd.concat([
            tabela,
            pd.DataFrame([{"Dias": maximo + 1, "Chamados": cauda,
                           "Rotulo": f"> {maximo}", "Dentro do SLA": False}]),
        ], ignore_index=True)
    return tabela


def perfil_colaborador(df: pd.DataFrame, por_colaborador: pd.DataFrame) -> pd.DataFrame:
    """
    Enriquece o resumo por colaborador com a COMPOSIÇÃO da carteira.

    IMPORTANTE: as diferenças de % fora do SLA entre pessoas se explicam pela
    carteira que cada uma recebe (origem e mix de anomalias), não por
    produtividade individual. Estas colunas existem justamente para impedir a
    leitura de desempenho.
    """
    perfil = por_colaborador.copy()
    # Denominador: avaliáveis, igual ao indicador geral e aos demais cortes.
    fora = df.groupby(COL_COLABORADOR).agg(
        av=("Dentro do SLA", lambda s: s.notna().sum()), fo=("Fora do SLA", "sum")
    )
    perfil["% Fora do SLA"] = perfil[COL_COLABORADOR].map(
        fora["fo"] / fora["av"].replace(0, np.nan) * 100
    )
    perfil["% Manual"] = perfil[COL_COLABORADOR].map(
        df.groupby(COL_COLABORADOR)[COL_TIPO_LIBERACAO].apply(lambda s: s.eq("MANUAL").mean() * 100)
    )
    perfil["Origem Predominante"] = perfil[COL_COLABORADOR].map(
        pd.crosstab(df[COL_COLABORADOR], df[COL_ORIGEM]).idxmax(axis=1)
    )
    perfil["Anomalia Predominante"] = perfil[COL_COLABORADOR].map(
        df.groupby(COL_COLABORADOR)[COL_ANOMALIA].agg(lambda s: s.value_counts().index[0])
    )
    # Qual anomalia responde pela maior parte das quebras de SLA da pessoa —
    # a evidência de que o problema é de fila, não de pessoa.
    quebras = df[df["Fora do SLA"].eq(True)]
    if not quebras.empty:
        perfil["Anomalia que Mais Quebra SLA"] = perfil[COL_COLABORADOR].map(
            quebras.groupby(COL_COLABORADOR)[COL_ANOMALIA].agg(
                lambda s: s.value_counts().index[0] if len(s) else None)
        )
        perfil["% das Quebras nessa Anomalia"] = perfil[COL_COLABORADOR].map(
            quebras.groupby(COL_COLABORADOR)[COL_ANOMALIA].agg(
                lambda s: s.value_counts().iloc[0] / len(s) * 100 if len(s) else np.nan)
        )
    return perfil


# ==============================================================================
# ORQUESTRAÇÃO COMPLETA
# ==============================================================================

def analisar(caminho: str = ARQUIVO_ENTRADA) -> dict:
    """
    Executa o pipeline inteiro e devolve tudo o que os consumidores precisam.
    É a única porta de entrada usada pelo dashboard.
    """
    dados = carregar_planilha(caminho)
    tempos, meta_tempos = extrair_tempos_medios(dados["premissas_raw"])
    df, meta_sla = preparar_e_calcular_sla(dados["base"])
    df, meta_merge = merge_tempos_medios(df, tempos)
    df, meta_esforco = calcular_esforco(df)
    saturacao, por_colaborador = resumo_saturacao(df)
    impossiveis, meta_impossiveis = dias_impossiveis(saturacao, df)

    return {
        "df": df,
        "base_bruta": dados["base"],
        "tempos": tempos,
        "dicionario": extrair_dicionario(dados["premissas_raw"]),
        "expectativa": texto_expectativa(dados["expectativa_raw"]),
        "saturacao": saturacao,
        "por_colaborador": por_colaborador,
        "perfil_colaborador": perfil_colaborador(df, por_colaborador),
        "impossiveis": impossiveis,
        "dist_liberacao": distribuicao_liberacao(df),
        "rankings": ranking_anomalias(df),
        "quebras": contribuicao_quebras_sla(df),
        "cenarios_sla": cenarios_sla(df, meta_sla["mascara_tratado_ok"]),
        "meta": {
            "tempos": meta_tempos, "sla": meta_sla, "merge": meta_merge,
            "esforco": meta_esforco, "impossiveis": meta_impossiveis,
        },
    }
