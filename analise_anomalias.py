# -*- coding: utf-8 -*-
"""
================================================================================
CASE DE PROCESSO SELETIVO — ANÁLISE DE ANOMALIAS DE FATURAMENTO
================================================================================
Autor : Engenharia de Dados
Fonte : Case_Processo_Seletivo.xlsx
        Abas: 'Expectativa', 'Base de Dados', 'Premissas e Informações'

O QUE ESTE SCRIPT ENTREGA
    1. Tempo (em dias) entre 'Data da Anomalia' e 'Data de Tratamento' e a flag
       'Dentro do SLA' (SLA = 2 dias).
    2. Merge da Base de Dados com a tabela de Tempo Médio de Tratamento
       (aba 'Premissas e Informações'), com auditoria de linhas não casadas.
    3. Horas trabalhadas por 'Colaborador(a)' por dia de tratamento e a flag
       'Estourou Saturação' (limite = 7 horas/dia).
    4. Taxas gerais: % fora do SLA, % manual vs massivo e top 3 anomalias
       mais ofensoras (por volume e por tempo gasto).
    5. Exportação de `resultado_analise.xlsx` (base enriquecida + resumos).

ARQUITETURA
    Toda a REGRA DE NEGÓCIO vive em `analise_core.py`, que não imprime nada.
    Este arquivo é a camada de RELATÓRIO: chama o núcleo, imprime a auditoria e
    exporta o Excel. O dashboard (`app.py`) consome o mesmo núcleo, de modo que
    os dois nunca divergem — a regra existe em um lugar só.

DECISÕES INTERPRETATIVAS
    Documentadas em `analise_core.py`, no bloco [D1]–[D7], e repetidas em
    contexto nos comentários de cada etapa abaixo. Todas são parametrizáveis.
================================================================================
"""

import os
import sys

import numpy as np
import pandas as pd

import analise_core as core
from analise_core import (
    ABA_BASE, ABA_EXPECTATIVA, ABA_PREMISSAS,
    ARQUIVO_ENTRADA, ARQUIVO_SAIDA,
    COL_ANOMALIA, COL_COLABORADOR, COL_DOCUMENTO, COL_DT_ANOMALIA,
    COL_DT_TRATAMENTO, COL_ORIGEM, COL_TIPO_LIBERACAO, COL_TIPO_TRATAMENTO,
    COLUNAS_OBRIGATORIAS, SATURACAO_HORAS_DIA, SLA_DIAS,
    formatar_horas, num,
)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 50)


# ==============================================================================
# UTILITÁRIO DE APRESENTAÇÃO
# ==============================================================================

def titulo(texto: str, nivel: int = 1) -> None:
    """Imprime um cabeçalho de seção padronizado."""
    largura = 80
    if nivel == 1:
        print("\n" + "=" * largura)
        print(texto.upper())
        print("=" * largura)
    else:
        print("\n" + "-" * largura)
        print(texto)
        print("-" * largura)


# ==============================================================================
# ETAPA 0 — INSPEÇÃO DA PLANILHA
# ==============================================================================

def inspecionar_planilha(caminho: str) -> dict:
    """
    Lê e imprime a estrutura real do arquivo antes de qualquer análise: abas,
    nomes exatos de coluna (com repr(), para expor espaço/acento/quebra de
    linha), dtypes, nulos e cardinalidade. Nada de nome de coluna inventado.
    """
    titulo("Etapa 0 — Inspeção da planilha")

    # A validação de abas e colunas obrigatórias acontece dentro do núcleo:
    # estrutura inesperada levanta ValueError em vez de virar número errado.
    dados = core.carregar_planilha(caminho)
    print(f"Arquivo    : {os.path.basename(caminho)}")
    print(f"Abas       : {[repr(a) for a in dados['abas']]}")

    # --- Aba 'Expectativa': verificar se define formato de saída [D6] ---------
    titulo("Aba 'Expectativa' — conteúdo integral (verificação de formato)", 2)
    for texto in core.texto_expectativa(dados["expectativa_raw"]):
        print(f"  {texto}")
    print(
        "\n  >> LEITURA: a aba traz o ENUNCIADO do desafio (dashboard de KPIs,\n"
        "     análise crítica, recomendações e apresentação de 10 min). Não há\n"
        "     cabeçalho, layout ou convenção de cálculo a espelhar — logo, o\n"
        "     formato de saída segue os requisitos do enunciado. [D6]"
    )

    # --- Aba 'Base de Dados' -------------------------------------------------
    titulo("Aba 'Base de Dados' — estrutura", 2)
    base = dados["base"]
    print(f"Dimensões  : {num(base.shape[0])} linhas x {base.shape[1]} colunas")
    print("\nColunas (nome exato via repr, dtype, nulos, cardinalidade):")
    for i, col in enumerate(base.columns):
        print(
            f"  [{i}] {col!r:<26} dtype={str(base[col].dtype):<10} "
            f"nulos={int(base[col].isna().sum()):>7,} "
            f"distintos={num(int(base[col].nunique(dropna=False))):>9}"
        )
    print("\n  >> Todas as colunas obrigatórias foram encontradas com o nome exato.")

    print("\nPrimeiras 5 linhas:")
    print(base.head(5).to_string(index=False))

    print("\nDistribuição das colunas categóricas:")
    for col in (COL_TIPO_TRATAMENTO, COL_TIPO_LIBERACAO, COL_ORIGEM, COL_COLABORADOR):
        contagem = base[col].value_counts(dropna=False)
        resumo = ", ".join(f"{k}={num(v)}" for k, v in contagem.items())
        print(f"  {col!r}: {resumo}")

    # --- Aba 'Premissas e Informações' ---------------------------------------
    # A tabela de Tempo Médio NÃO começa na linha 1: a aba tem três blocos lado a
    # lado com títulos mesclados (B1:C2 'Tempo Médio...', E1:F2 'SLA e Saturação',
    # H1:I2 'Dados Complementares'). Por isso a leitura é feita sem cabeçalho e a
    # tabela é localizada pelo rótulo 'Anomalia'/'Tempo', em vez de posição fixa.
    titulo("Aba 'Premissas e Informações' — estrutura (blocos lado a lado)", 2)
    premissas_raw = dados["premissas_raw"]
    print(f"Dimensões brutas: {premissas_raw.shape[0]} linhas x {premissas_raw.shape[1]} colunas")
    print("Blocos identificados na primeira linha preenchida:")
    for _, linha in premissas_raw.head(3).iterrows():
        textos = [f"col{ix}={v!r}" for ix, v in linha.items() if pd.notna(v)]
        if textos:
            print("  " + " | ".join(textos))

    return dados


def extrair_tempos_medios(premissas_raw: pd.DataFrame) -> pd.DataFrame:
    """Extrai a tabela de Tempo Médio (via núcleo) e audita o resultado."""
    titulo("Etapa 0b — Extração da tabela de Tempo Médio de Tratamento", 2)

    dados, meta = core.extrair_tempos_medios(premissas_raw)

    print(
        f"Cabeçalho localizado na linha {meta['linha_cabecalho']} da planilha, "
        f"colunas {meta['coluna_anomalia']} e {meta['coluna_tempo']}."
    )
    print(f"Anomalias com tempo médio cadastrado: {len(dados)}")
    print(
        f"Tempo médio — mín: {dados['Tempo Médio (s)'].min():.0f}s | "
        f"máx: {dados['Tempo Médio (s)'].max():.0f}s | "
        f"mediana: {dados['Tempo Médio (s)'].median():.0f}s"
    )

    # Chave duplicada no lado direito de um merge multiplica linhas e infla todos
    # os totais silenciosamente — por isso a checagem é explícita.
    if meta["duplicadas"]:
        print(f"  !! ATENÇÃO: {meta['duplicadas']} anomalia(s) duplicada(s) na tabela de tempos — mantida a primeira.")
    else:
        print("  >> Sem chaves duplicadas na tabela de tempos (merge não vai multiplicar linhas).")

    return dados


# ==============================================================================
# ETAPA 1 — LIMPEZA E SLA
# ==============================================================================

def preparar_e_calcular_sla(base: pd.DataFrame) -> pd.DataFrame:
    """
    Converte as datas, calcula o atraso em dias e cria a flag 'Dentro do SLA'.

    Regras aplicadas (definidas em analise_core):
      [D1] dias corridos como métrica oficial (+ dias úteis seg-sáb como apoio);
      [D2] SLA cumprido quando atraso <= 2 dias;
      [D3] anomalia sem tratamento permanece na base e no denominador;
      [D7] tratamento anterior à anomalia é sinalizado, não descartado.
    """
    titulo("Etapa 1 — Tempo de tratamento e flag 'Dentro do SLA'")

    df, meta = core.preparar_e_calcular_sla(base)

    for coluna, c in meta["conversao"].items():
        print(
            f"{coluna!r}: nulos antes={c['antes']} | após conversão={c['depois']} "
            f"| não convertidos={c['nao_convertidos']}"
        )

    print(f"\nRegistros sem 'Data de Tratamento' (em aberto)     : {num(meta['sem_tratamento'])}")
    print(f"Registros sem 'Data da Anomalia'                   : {num(meta['sem_data_anomalia'])}")
    print(f"Registros com tratamento ANTES da anomalia (< 0 d) : {num(meta['invertidos'])}")
    if meta["invertidos"]:
        print(
            "  >> [D7] Impossíveis no fluxo do processo (data invertida na origem).\n"
            "     Ficam na base com 'Dentro do SLA' nulo e SAEM do denominador do SLA.\n"
            f"     Distribuição do atraso negativo: {meta['distribuicao_invertidos']}"
        )

    # Data de corte para envelhecer anomalias em aberto: a data mais recente
    # observada na base (não "hoje", que tornaria o resultado irreprodutível).
    print(f"\nData de corte da base (máxima observada): {meta['data_corte']:%d/%m/%Y}")

    print(f"\nRegistros avaliáveis para SLA : {num(meta['avaliaveis'])} de {num(meta['total'])}")
    print(f"Dentro do SLA (<= {SLA_DIAS} dias corridos) : {num(meta['dentro'])}")
    print(f"Fora do SLA                    : {num(meta['fora'])}")

    # Sensibilidade da convenção adotada — mostra o impacto de cada escolha.
    titulo("Sensibilidade das convenções de cálculo do SLA", 2)
    for nome, pct_fora in core.cenarios_sla(df, meta["mascara_tratado_ok"]).items():
        print(f"  {nome:<34} -> fora do SLA: {pct_fora:6.2f}%")
    print(
        "  >> A escolha entre <=2 e <2 move o indicador; a convenção adotada é a\n"
        "     leitura literal de 'prazo esperado: 2 dias' (até 2 dias cumpre). [D2]"
    )

    return df


# ==============================================================================
# ETAPA 2 — MERGE COM OS TEMPOS MÉDIOS
# ==============================================================================

def merge_tempos_medios(df: pd.DataFrame, tempos: pd.DataFrame) -> pd.DataFrame:
    """
    Junta a base com a tabela de tempos médios pela chave normalizada e AUDITA a
    cobertura: nenhuma linha pode sair com tempo médio NaN sem que isso apareça
    no relatório.
    """
    titulo("Etapa 2 — Merge com os Tempos Médios de Tratamento")

    resultado, meta = core.merge_tempos_medios(df, tempos)

    print(f"Linhas antes do merge : {num(meta['linhas_antes'])}")
    print(f"Linhas após o merge   : {num(meta['linhas_depois'])}")
    print("  >> Cardinalidade preservada (validate='many_to_one').")

    # --- Auditoria de cobertura ---------------------------------------------
    print(f"\nLinhas SEM tempo médio após o merge: {num(meta['sem_tempo'])}")
    if meta["sem_tempo"]:
        print("  !! Anomalias da base sem tempo médio cadastrado:")
        print(meta["faltantes"].to_string(index=False))
        print(
            "  >> Elas entram nas contagens de volume, mas ficam fora do esforço em\n"
            "     horas (não há como estimar tempo sem parâmetro). Reportado acima."
        )
    else:
        print("  >> 100% das anomalias da base encontraram tempo médio. Nenhum NaN silencioso.")

    print(f"\nAnomalias cadastradas na aba de Premissas mas AUSENTES da base: {len(meta['nao_usadas'])}")
    if meta["nao_usadas"]:
        print(f"  {meta['nao_usadas']}")
        print("  >> Cadastro mais amplo que o período analisado. Não afeta os cálculos.")

    return resultado


# ==============================================================================
# ETAPA 3 — HORAS POR COLABORADOR E SATURAÇÃO
# ==============================================================================

def calcular_esforco(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converte cada chamado em esforço (horas), tratando corretamente o tratamento
    massivo [D4] — tempo contado uma vez por lote e rateado entre os chamados.
    O cenário ingênuo é calculado em paralelo só para dimensionar o erro.
    """
    titulo("Etapa 3 — Esforço por chamado e saturação diária")

    resultado, meta = core.calcular_esforco(df)

    print(f"Lotes massivos identificados : {num(meta['lotes_massivos'])}")
    if meta["lotes_massivos"]:
        print(
            f"Chamados por lote massivo    : média {meta['lote_media']:.1f} | "
            f"mediana {meta['lote_mediana']:.0f} | máximo {num(meta['lote_maximo'])}"
        )
    print(f"\nEsforço total no cenário ADOTADO  : {num(meta['horas_adotado'], 1)} horas")
    print(f"Esforço total no cenário INGÊNUO  : {num(meta['horas_ingenuo'], 1)} horas")
    print(
        f"  >> [D4] Cobrar o tempo cheio de cada chamado massivo inflaria o esforço\n"
        f"     em {meta['fator']:.1f}x e tornaria a leitura de saturação inutilizável."
    )
    return resultado


def resumo_saturacao(df: pd.DataFrame) -> tuple:
    """
    Agrega as horas trabalhadas por 'Colaborador(a)' e por dia de tratamento e
    reporta a flag 'Estourou Saturação' (> 7 horas/dia).
    """
    saturacao, por_colaborador = core.resumo_saturacao(df)

    titulo("Horas por Colaborador(a) x dia — flag 'Estourou Saturação'", 2)
    print(f"Limite de saturação: {SATURACAO_HORAS_DIA} horas/dia\n")
    print(f"Pares (colaborador, dia) analisados : {num(len(saturacao))}")
    estouros = int(saturacao["Estourou Saturação"].sum())
    print(
        f"Dias com estouro de saturação       : {num(estouros)}"
        + f" ({estouros / max(len(saturacao), 1) * 100:.1f}%)"
    )
    estouros_ing = int(saturacao["Estourou Saturação (Cenário Ingênuo)"].sum())
    print(
        f"  (no cenário ingênuo seriam        : {num(estouros_ing)}"
        + f" — {estouros_ing / max(len(saturacao), 1) * 100:.1f}% — evidência de [D4])"
    )

    print("\nResumo por colaborador(a):")
    exibir = por_colaborador.copy()
    for col in ("Horas Totais", "Horas/Dia (média)", "Horas/Dia (máximo)", "% Dias com Estouro"):
        exibir[col] = exibir[col].round(2)
    print(exibir.to_string(index=False))

    # --- Sinalização de cargas fisicamente impossíveis -----------------------
    # Mesmo com o rateio correto do massivo [D4], alguns dias ultrapassam a
    # jornada humana. Isso não é erro de cálculo: é sintoma de que trabalho em
    # lote está registrado como 'MANUAL' (tempo cheio por chamado) ou de que o
    # tempo médio cadastrado está superestimado para essas anomalias.
    impossiveis, meta_imp = core.dias_impossiveis(saturacao, df)
    print(f"\nDias com carga acima de 24h (fisicamente impossíveis): {num(meta_imp['qtd'])}")
    if meta_imp["qtd"]:
        print(
            f"  Nesses dias, {meta_imp['pct_manual']:.1f}% dos chamados estão marcados como MANUAL,\n"
            f"  respondendo por {num(meta_imp['horas_manual'], 1)} das horas.\n"
            "  >> INCONSISTÊNCIA A REPORTAR: volume desta ordem tratado 'manualmente'\n"
            "     em um único dia é implausível. Ou o 'Tipo de Liberação' está\n"
            "     classificado errado nesses lotes, ou o tempo médio da anomalia não\n"
            "     vale para tratamento em série. Impacta diretamente a saturação."
        )

    print("\nTop 10 dias de maior carga (colaborador x dia):")
    top_dias = saturacao.head(10).copy()
    top_dias["Data"] = top_dias["Data"].dt.strftime("%d/%m/%Y")
    top_dias["Horas Trabalhadas"] = top_dias["Horas Trabalhadas"].round(2)
    print(
        top_dias[[COL_COLABORADOR, "Data", "Chamados Tratados", "Horas Trabalhadas", "Estourou Saturação"]]
        .to_string(index=False)
    )

    return saturacao, por_colaborador


# ==============================================================================
# ETAPA 4 — TAXAS GERAIS E TOP 3 OFENSORAS
# ==============================================================================

def taxas_gerais(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula as taxas gerais: SLA e distribuição manual vs massivo."""
    titulo("Etapa 4 — Taxas gerais")

    total = len(df)
    avaliaveis = int(df["Dentro do SLA"].notna().sum())
    fora = int(df["Dentro do SLA"].eq(False).sum())
    dentro = int(df["Dentro do SLA"].eq(True).sum())
    inconsistentes = int(df["Registro Inconsistente"].sum())
    em_aberto = int(df["Anomalia em Aberto"].sum())

    pct_fora = fora / avaliaveis * 100 if avaliaveis else np.nan
    pct_fora_total = fora / total * 100 if total else np.nan

    titulo("4.1 — Percentual de chamados fora do SLA", 2)
    print(f"Total de chamados na base                     : {num(total)}")
    print(f"Chamados avaliáveis (denominador oficial)     : {num(avaliaveis)}")
    print(f"  (-) registros com data invertida, excluídos : {num(inconsistentes)}")
    print(f"  (+) anomalias em aberto mantidas [D3]       : {num(em_aberto)}")
    print(f"Dentro do SLA                                 : {num(dentro)}" + f" ({dentro / avaliaveis * 100:.2f}%)")
    print(f"Fora do SLA                                   : {num(fora)}" + f" ({pct_fora:.2f}%)")
    print(f"\n>> % FORA DO SLA = {pct_fora:.2f}%  (sobre chamados avaliáveis)")
    print(f">> % FORA DO SLA = {pct_fora_total:.2f}%  (sobre a base inteira, pior caso)")

    tratados = df[df[COL_DT_TRATAMENTO].notna() & ~df["Registro Inconsistente"]]
    print(f"\nTempo de tratamento (dias corridos, apenas registros consistentes):")
    print(
        f"  média {tratados['Dias para Tratamento'].mean():.2f} | "
        f"mediana {tratados['Dias para Tratamento'].median():.0f} | "
        f"p90 {tratados['Dias para Tratamento'].quantile(0.9):.0f} | "
        f"máximo {tratados['Dias para Tratamento'].max():.0f}"
    )
    print(f"  tratados no mesmo dia (0 dia): {(tratados['Dias para Tratamento'] == 0).mean() * 100:.2f}%")

    titulo("4.2 — Percentual de tratamentos manuais vs massivos", 2)
    # Além do volume, o esforço: massivo é muito volume e pouca hora [D4].
    dist = core.distribuicao_liberacao(df)
    print(dist.round(2).to_string(index=False))
    print(
        "\n>> Leitura: o massivo domina o VOLUME, mas o manual domina o ESFORÇO —\n"
        "   é onde a automação tem retorno."
    )

    titulo("4.3 — Distribuição por 'Tipo de Tratamento' e 'Origem' (contexto)", 2)
    for coluna in (COL_TIPO_TRATAMENTO, COL_ORIGEM):
        print(f"\nPor {coluna!r}:")
        print(core.distribuicao_por(df, coluna).round(2).to_string(index=False))

    return dist


def top_anomalias(df: pd.DataFrame) -> dict:
    """
    Top 3 anomalias mais ofensoras.

    [D5] "Maior tempo gasto" é entregue nos dois recortes possíveis:
         - Tempo TOTAL agregado (custo operacional acumulado);
         - Tempo MÉDIO unitário (custo de cada ocorrência).
    """
    titulo("4.4 — Top 3 anomalias mais ofensoras")

    tops = core.ranking_anomalias(df)
    colunas = [COL_ANOMALIA, "Chamados", "% do Volume", "Horas Totais", "% do Esforço",
               "Tempo Médio Unitário (min)", "% Fora do SLA"]

    print("A) MAIOR VOLUME (número de chamados):")
    print(tops["por_volume"][colunas].round(2).to_string(index=False))

    print("\nB) MAIOR TEMPO GASTO — TOTAL AGREGADO (horas de operação consumidas):")
    print(tops["por_horas"][colunas].round(2).to_string(index=False))

    print("\nC) MAIOR TEMPO GASTO — MÉDIO UNITÁRIO (custo por ocorrência):")
    print(tops["por_unitario"][colunas].round(2).to_string(index=False))

    print(
        "\n>> [D5] Os rankings B e C respondem perguntas diferentes: B aponta onde a\n"
        "   operação queima horas (prioridade de automação); C aponta a anomalia\n"
        "   individualmente mais cara (prioridade de simplificação do procedimento)."
    )
    return tops


# ==============================================================================
# ETAPA 5 — EXPORTAÇÃO
# ==============================================================================

def exportar(df: pd.DataFrame, saturacao: pd.DataFrame, por_colaborador: pd.DataFrame,
             dist_liberacao: pd.DataFrame, tops: dict, caminho: str) -> None:
    """Grava a base enriquecida e as abas de resumo em um único arquivo Excel."""
    titulo("Etapa 5 — Exportação dos resultados")

    colunas_saida = [
        COL_DOCUMENTO, COL_ANOMALIA, COL_DT_ANOMALIA, COL_DT_TRATAMENTO,
        COL_TIPO_TRATAMENTO, COL_TIPO_LIBERACAO, COL_ORIGEM, COL_COLABORADOR,
        "Dias para Tratamento", "Dias Úteis (Seg-Sáb)", "Dentro do SLA", "Fora do SLA",
        "Anomalia em Aberto", "Registro Inconsistente",
        "Tempo Médio (s)", "Tempo Médio (min)", "Tamanho do Lote",
        "Horas Atribuídas", "Horas (Cenário Ingênuo)", "Execuções Equivalentes",
    ]
    base_enriquecida = df[colunas_saida].copy()

    # A flag de saturação é diária; trazemos de volta para a linha do chamado
    # para que a base enriquecida seja autossuficiente na análise.
    chave_dia = saturacao[[COL_COLABORADOR, "Data", "Horas Trabalhadas", "Estourou Saturação"]].rename(
        columns={"Data": COL_DT_TRATAMENTO, "Horas Trabalhadas": "Horas do Colaborador no Dia"}
    )
    base_enriquecida = base_enriquecida.merge(
        chave_dia, on=[COL_COLABORADOR, COL_DT_TRATAMENTO], how="left"
    )

    # Ficha de premissas e decisões, para o resultado não depender deste script.
    premissas_doc = pd.DataFrame(
        [
            ("SLA", f"{SLA_DIAS} dias", "Prazo esperado (aba Premissas, célula F3)"),
            ("Saturação", f"{SATURACAO_HORAS_DIA} horas/dia", "Saturação esperada (aba Premissas, célula F4)"),
            ("[D1] Contagem de dias", "Dias corridos", "Operação trabalha aos sábados; 'dias' não é qualificado na planilha"),
            ("[D2] Leitura do SLA", "atraso <= 2 dias", "'Prazo esperado: 2 dias' = até 2 dias cumpre o acordo"),
            ("[D3] Anomalia sem tratamento", "Mantida no denominador", "Envelhecida contra a data máxima da base"),
            ("[D4] Tratamento massivo", "Tempo rateado no lote", "Uma execução resolve o lote; tempo cheio por chamado infla o esforço"),
            ("[D5] Top 3 por tempo", "Total e médio unitário", "Rankings diferentes, ambos entregues"),
            ("[D6] Aba Expectativa", "Enunciado, não layout", "Não define formato de saída a ser espelhado"),
            ("[D7] Data invertida", "Sinalizada e excluída do SLA", "Tratamento anterior à anomalia é impossível no processo"),
            ("Denominador de '% Fora do SLA'", "Chamados avaliáveis",
             "Mesmo denominador em todos os cortes (geral, anomalia, colaborador, origem): "
             "o total menos os registros com data invertida"),
            ("Coluna 'Estourou Saturação' na Base Enriquecida", "Flag do DIA, repetida por linha",
             "Somar a coluna NÃO dá o número de estouros. Ela marca todas as linhas de um dia "
             "que estourou. A contagem correta (33) está na aba 'Saturação por Dia', com um "
             "registro por par colaborador-dia"),
        ],
        columns=["Item", "Definição", "Justificativa"],
    )

    saturacao_saida = saturacao.copy()

    with pd.ExcelWriter(caminho, engine="xlsxwriter") as writer:
        premissas_doc.to_excel(writer, sheet_name="Premissas e Decisões", index=False)
        base_enriquecida.to_excel(writer, sheet_name="Base Enriquecida", index=False)
        saturacao_saida.to_excel(writer, sheet_name="Saturação por Dia", index=False)
        por_colaborador.to_excel(writer, sheet_name="Resumo Colaborador", index=False)
        dist_liberacao.to_excel(writer, sheet_name="Manual vs Massivo", index=False)
        tops["ranking"].to_excel(writer, sheet_name="Ranking Anomalias", index=False)
        tops["por_volume"].to_excel(writer, sheet_name="Top3 Volume", index=False)
        tops["por_horas"].to_excel(writer, sheet_name="Top3 Horas Totais", index=False)
        tops["por_unitario"].to_excel(writer, sheet_name="Top3 Tempo Unitário", index=False)

    print(f"Arquivo gerado: {os.path.basename(caminho)}")
    print("Abas: Premissas e Decisões | Base Enriquecida | Saturação por Dia | Resumo Colaborador |")
    print("      Manual vs Massivo | Ranking Anomalias | Top3 Volume | Top3 Horas Totais | Top3 Tempo Unitário")
    print(f"Linhas na base enriquecida: {num(len(base_enriquecida))}")


# ==============================================================================
# ETAPA 6 — PAINEL FINAL DE ESTATÍSTICAS
# ==============================================================================

def painel_final(df: pd.DataFrame, saturacao: pd.DataFrame, tops: dict) -> None:
    """Imprime o resumo executivo com os indicadores principais."""
    titulo("Painel final — indicadores principais")

    total = len(df)
    avaliaveis = int(df["Dentro do SLA"].notna().sum())
    fora = int(df["Dentro do SLA"].eq(False).sum())
    pct_fora = fora / avaliaveis * 100 if avaliaveis else np.nan
    massivo = df[COL_TIPO_LIBERACAO].eq("MASSIVO").mean() * 100
    manual = df[COL_TIPO_LIBERACAO].eq("MANUAL").mean() * 100
    horas = df["Horas Atribuídas"].sum()
    estouros = int(saturacao["Estourou Saturação"].sum())
    pct_estouro = estouros / max(len(saturacao), 1) * 100

    periodo_ini = df[COL_DT_ANOMALIA].min()
    periodo_fim = df[COL_DT_TRATAMENTO].max()

    linhas = [
        ("Período analisado", f"{periodo_ini:%d/%m/%Y} a {periodo_fim:%d/%m/%Y}"),
        ("Chamados (linhas da base)", f"{num(total)}"),
        ("Documentos distintos", f"{num(df[COL_DOCUMENTO].nunique())}"),
        ("Anomalias distintas", f"{df[COL_ANOMALIA].nunique()}"),
        ("Colaboradores", f"{df[COL_COLABORADOR].nunique()}"),
        ("", ""),
        (f"% fora do SLA (> {SLA_DIAS} dias corridos)", f"{pct_fora:.2f}%"),
        ("Chamados fora do SLA", f"{num(fora)}"),
        ("Tempo médio de tratamento", f"{df['Dias para Tratamento'].mean():.2f} dias"),
        ("", ""),
        ("% tratamentos MASSIVOS (volume)", f"{massivo:.2f}%"),
        ("% tratamentos MANUAIS (volume)", f"{manual:.2f}%"),
        ("Esforço total estimado", f"{formatar_horas(horas)} ({num(horas)} h)"),
        ("", ""),
        (f"Dias-colaborador acima de {SATURACAO_HORAS_DIA}h", f"{num(estouros)}" + f" ({pct_estouro:.1f}%)"),
        ("Carga média por colaborador/dia", formatar_horas(saturacao["Horas Trabalhadas"].mean())),
        ("Pico de carga em um único dia", formatar_horas(saturacao["Horas Trabalhadas"].max())),
    ]
    for rotulo, valor in linhas:
        if not rotulo:
            print()
        else:
            print(f"  {rotulo:<42} {valor}")

    print("\n  TOP 3 POR VOLUME:")
    for _, linha in tops["por_volume"].iterrows():
        print(
            f"    - {linha[COL_ANOMALIA]:<12} {num(linha['Chamados']):>9} chamados"
            + f" ({linha['% do Volume']:.1f}% do volume) | fora do SLA: {linha['% Fora do SLA']:.1f}%"
        )
    print("\n  TOP 3 POR TEMPO TOTAL GASTO:")
    for _, linha in tops["por_horas"].iterrows():
        print(
            f"    - {linha[COL_ANOMALIA]:<12} {num(linha['Horas Totais'], 1):>9} h"
            + f" ({linha['% do Esforço']:.1f}% do esforço)"
        )
    print("\n  TOP 3 POR TEMPO MÉDIO UNITÁRIO:")
    for _, linha in tops["por_unitario"].iterrows():
        print(f"    - {linha[COL_ANOMALIA]:<12} {linha['Tempo Médio Unitário (min)']:>6.2f} min por chamado")

    print("\n" + "=" * 80)
    print("FIM DA EXECUÇÃO")
    print("=" * 80)


# ==============================================================================
# ORQUESTRAÇÃO
# ==============================================================================

def main() -> int:
    titulo("Case de Processo Seletivo — Análise de Anomalias de Faturamento")

    contexto = inspecionar_planilha(ARQUIVO_ENTRADA)
    tempos = extrair_tempos_medios(contexto["premissas_raw"])

    df = preparar_e_calcular_sla(contexto["base"])          # Requisito 1
    df = merge_tempos_medios(df, tempos)                    # Requisito 2
    df = calcular_esforco(df)                               # Requisito 3 (parte 1)
    saturacao, por_colaborador = resumo_saturacao(df)       # Requisito 3 (parte 2)
    dist_liberacao = taxas_gerais(df)                       # Requisito 4 (parte 1)
    tops = top_anomalias(df)                                # Requisito 4 (parte 2)

    exportar(df, saturacao, por_colaborador, dist_liberacao, tops, ARQUIVO_SAIDA)
    painel_final(df, saturacao, tops)                       # Requisito 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
