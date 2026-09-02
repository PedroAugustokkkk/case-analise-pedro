# -*- coding: utf-8 -*-
"""
Gera `numeros.json` a partir de `analise_core.py`.

POR QUE ESTE ARQUIVO EXISTE
    O `numeros.json` alimenta o documento em Word. Até aqui ele era mantido à
    mão, e o cabeçalho do gerador do .docx afirmava que vinha do núcleo. Não
    vinha. O resultado foi um campo publicado que nunca havia sido calculado:
    `com_correcao` ficou em 0,0 e o documento imprimiu "0,0% contra 50,0%", dois
    percentuais complementares que não somam 100.

    A causa concreta do zero: o núcleo normaliza `Tipo de Tratamento` com
    `.str.title()`, então o valor vira "Com Correção" e a comparação contra
    "Com correção" (c minúsculo) não casava com nada. Um `.mean()` sobre uma
    máscara toda falsa devolve 0,0 sem levantar erro.

    Daí as validações no fim deste arquivo. Elas existem para que um número que
    nunca foi calculado não consiga chegar ao documento outra vez.

USO
    python gerar_numeros.py              # gera numeros.json e valida
    python gerar_numeros.py --conferir   # valida o arquivo existente, sem gravar
"""

import json
import sys

import pandas as pd

import analise_core as core

DESTINO = core.RAIZ / "numeros.json"

# O strftime depende do locale do sistema, que na hospedagem é o inglês.
MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril", 5: "maio", 6: "junho",
    7: "julho", 8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

# Chaves que precisam existir e ser diferentes de zero. Um zero aqui quase
# sempre significa filtro que não casou, e não uma medição legítima.
NAO_PODEM_SER_ZERO = [
    "total", "documentos", "anomalias", "colaboradores", "avaliaveis", "fora",
    "dentro", "pct_fora", "mesmo_dia", "media_dias", "max_dias", "invertidos",
    "sabados", "manual_ch", "massivo_ch", "manual_vol", "massivo_vol",
    "manual_h", "massivo_h", "manual_esf", "massivo_esf", "custo_manual",
    "custo_massivo", "razao_custo", "horas_total", "horas_ingenuo", "fator",
    "lotes", "lote_max", "dias_trat", "fte", "pares", "estouros", "pct_estouro",
    "carga_media", "pico_h", "pico_ch", "imp_qtd", "merge_antes", "merge_depois",
    "tempos_qtd", "tempo_padrao_s", "tempo_padrao_qtd", "tempos_distintos",
    "sem_correcao", "com_correcao", "of_vol", "of_ch", "of_pct_fora",
    "of_pct_quebras", "of_dono_pct", "imp_sla_atual", "imp_sla_novo",
    "imp_ganho", "imp_evitadas", "alvo_h", "alvo_esf", "alvo_vol", "alvo_ch",
    "alvo_unit", "alvo_pct_manual", "alvo_h_manual", "alvo_fte",
    "com_ch", "sem_ch",
    "marco_chamados", "marco_quebras", "marco_pct_quebras", "marco_pct_fora",
    "correlacao_mensal",
]

# Zeros legítimos: são achados da análise, não falhas de cálculo.
ZERO_ESPERADO = ["em_aberto", "domingos", "merge_sem_tempo", "tempos_dup"]

# Pares que descrevem partes de um todo e precisam somar 100.
PARES_COMPLEMENTARES = [
    ("com_correcao", "sem_correcao"),
    ("manual_vol", "massivo_vol"),
    ("manual_esf", "massivo_esf"),
]


def _f(x) -> float:
    return float(x)


def _i(x) -> int:
    return int(x)


def coletar() -> dict:
    """Roda o núcleo e monta o dicionário de números do documento."""
    r = core.analisar()
    df = r["df"]
    m = r["meta"]
    sat = r["saturacao"]
    perfil = r["perfil_colaborador"]
    rk = r["rankings"]["ranking"]
    q = r["quebras"]

    total = len(df)
    avali = m["sla"]["avaliaveis"]
    fora = m["sla"]["fora"]
    trat = df[df[core.COL_DT_TRATAMENTO].notna() & ~df["Registro Inconsistente"]]
    dist = r["dist_liberacao"].set_index(core.COL_TIPO_LIBERACAO)
    custo = core.esforco_por_liberacao_unitario(df)

    # Tipos de tratamento: lidos das categorias presentes, e não de literais
    # digitados aqui. Foi um literal que produziu o zero silencioso.
    contagem_tratamento = df[core.COL_TIPO_TRATAMENTO].value_counts()
    rotulo_com = next(k for k in contagem_tratamento.index if str(k).lower().startswith("com"))
    rotulo_sem = next(k for k in contagem_tratamento.index if str(k).lower().startswith("sem"))

    ofensora = q.iloc[0][core.COL_ANOMALIA]
    imp = core.impacto_zerar_anomalia(df, ofensora)
    top_horas = rk.sort_values("Horas Totais", ascending=False).iloc[0]
    alvo = top_horas[core.COL_ANOMALIA]
    rec_alvo = df[df[core.COL_ANOMALIA].eq(alvo)]
    horas_manual_alvo = _f(
        rec_alvo.loc[rec_alvo[core.COL_TIPO_LIBERACAO].eq("MANUAL"), "Horas Atribuídas"].sum()
    )
    dias_trat = df[core.COL_DT_TRATAMENTO].nunique()
    cap_dia = dias_trat * core.SATURACAO_HORAS_DIA

    pico = sat.iloc[0]
    det_pico = df[
        (df[core.COL_COLABORADOR] == pico[core.COL_COLABORADOR])
        & (df[core.COL_DT_TRATAMENTO] == pico["Data"])
    ]
    pico_manual = det_pico[det_pico[core.COL_TIPO_LIBERACAO].eq("MANUAL")]

    vc = r["tempos"]["Tempo Médio (s)"].value_counts()

    of_df = df[df[core.COL_ANOMALIA].eq(ofensora)]
    of_fora = of_df[of_df["Fora do SLA"].eq(True)]
    dono = of_fora[core.COL_COLABORADOR].value_counts()
    dist_of = of_df["Dias para Tratamento"].value_counts().sort_index()

    # --- concentração temporal: a evidência do §3.1 -------------------------
    mensal = core.distribuicao_mensal(df)
    pior_mes = mensal.sort_values("Fora do SLA", ascending=False).iloc[0]
    maior_volume = mensal.sort_values("Chamados", ascending=False).iloc[0]
    correlacao = _f(mensal["Chamados"].corr(mensal["% Fora do SLA"]))
    mes_pior = str(pior_mes["Mês"])
    no_mes = df[df[core.COL_DT_ANOMALIA].dt.to_period("M").astype(str) == mes_pior]
    fora_no_mes = no_mes[no_mes["Fora do SLA"].eq(True)]
    of_no_mes = fora_no_mes[fora_no_mes[core.COL_ANOMALIA].eq(ofensora)]
    of_dono_no_mes = of_no_mes[of_no_mes[core.COL_COLABORADOR].eq(str(dono.index[0]))]

    return {
        "total": total, "documentos": _i(df["Documento"].nunique()),
        "anomalias": _i(df[core.COL_ANOMALIA].nunique()),
        "colaboradores": _i(df[core.COL_COLABORADOR].nunique()),
        "anom_por_doc": _f(total / df["Documento"].nunique()),
        "max_anom_doc": _i(df.groupby("Documento").size().max()),
        "ini": df[core.COL_DT_ANOMALIA].min().strftime("%d/%m/%Y"),
        "fim_anom": df[core.COL_DT_ANOMALIA].max().strftime("%d/%m/%Y"),
        "fim_trat": df[core.COL_DT_TRATAMENTO].max().strftime("%d/%m/%Y"),
        "sla_dias": core.SLA_DIAS, "saturacao": core.SATURACAO_HORAS_DIA,
        "avaliaveis": avali, "fora": fora, "dentro": m["sla"]["dentro"],
        "pct_fora": _f(fora / avali * 100),
        "mesmo_dia": _f((trat["Dias para Tratamento"] == 0).mean() * 100),
        "media_dias": _f(trat["Dias para Tratamento"].mean()),
        "p90": _f(trat["Dias para Tratamento"].quantile(0.9)),
        "max_dias": _i(trat["Dias para Tratamento"].max()),
        "invertidos": m["sla"]["invertidos"],
        "invertidos_pct": _f(m["sla"]["invertidos"] / total * 100),
        "invertidos_dist": {str(k): _i(v) for k, v in m["sla"]["distribuicao_invertidos"].items()},
        "em_aberto": m["sla"]["sem_tratamento"],
        "sabados": _i((df[core.COL_DT_TRATAMENTO].dt.dayofweek == 5).sum()),
        "domingos": _i((df[core.COL_DT_TRATAMENTO].dt.dayofweek == 6).sum()),
        "cenarios": {k: _f(v) for k, v in r["cenarios_sla"].items()},
        "manual_ch": _i(dist.loc["MANUAL", "Chamados"]),
        "massivo_ch": _i(dist.loc["MASSIVO", "Chamados"]),
        "manual_vol": _f(dist.loc["MANUAL", "% dos Chamados"]),
        "massivo_vol": _f(dist.loc["MASSIVO", "% dos Chamados"]),
        "manual_h": _f(dist.loc["MANUAL", "Horas Atribuídas"]),
        "massivo_h": _f(dist.loc["MASSIVO", "Horas Atribuídas"]),
        "manual_esf": _f(dist.loc["MANUAL", "% do Esforço"]),
        "massivo_esf": _f(dist.loc["MASSIVO", "% do Esforço"]),
        "custo_manual": _f(custo["MANUAL"]), "custo_massivo": _f(custo["MASSIVO"]),
        "razao_custo": _f(custo["razao"]),
        "horas_total": _f(m["esforco"]["horas_adotado"]),
        "horas_ingenuo": _f(m["esforco"]["horas_ingenuo"]),
        "fator": _f(m["esforco"]["fator"]), "lotes": m["esforco"]["lotes_massivos"],
        "lote_max": m["esforco"]["lote_maximo"],
        "lote_mediana": _f(m["esforco"]["lote_mediana"]),
        "dias_trat": dias_trat, "fte": _f(m["esforco"]["horas_adotado"] / cap_dia),
        "pares": len(sat), "estouros": _i(sat["Estourou Saturação"].sum()),
        "pct_estouro": _f(sat["Estourou Saturação"].mean() * 100),
        "estouros_ing": _i(sat["Estourou Saturação (Cenário Ingênuo)"].sum()),
        "pct_estouro_ing": _f(sat["Estourou Saturação (Cenário Ingênuo)"].mean() * 100),
        "carga_media": _f(sat["Horas Trabalhadas"].mean()),
        "pico_h": _f(pico["Horas Trabalhadas"]), "pico_quem": str(pico[core.COL_COLABORADOR]),
        "pico_data": pd.Timestamp(pico["Data"]).strftime("%d/%m/%Y"),
        "pico_ch": _i(pico["Chamados Tratados"]), "pico_manual_ch": len(pico_manual),
        "pico_manual_h": _f(pico_manual["Horas Atribuídas"].sum()),
        "pico_seg_por_caso": _f(core.SATURACAO_HORAS_DIA * 3600 / max(len(pico_manual), 1)),
        "imp_qtd": m["impossiveis"]["qtd"], "imp_pct_manual": _f(m["impossiveis"]["pct_manual"]),
        "imp_horas_manual": _f(m["impossiveis"]["horas_manual"]),
        "imp_horas_total": _f(m["impossiveis"]["horas_total"]),
        "imp_pct_pares": _f(m["impossiveis"]["qtd"] / len(sat) * 100),
        "merge_antes": m["merge"]["linhas_antes"], "merge_depois": m["merge"]["linhas_depois"],
        "merge_sem_tempo": m["merge"]["sem_tempo"],
        "merge_nao_usadas": len(m["merge"]["nao_usadas"]),
        "tempos_qtd": m["tempos"]["qtd"], "tempos_dup": m["tempos"]["duplicadas"],
        "tempo_min": _f(r["tempos"]["Tempo Médio (s)"].min()),
        "tempo_max": _f(r["tempos"]["Tempo Médio (s)"].max()),
        "tempo_padrao_s": _f(vc.index[0]), "tempo_padrao_qtd": _i(vc.iloc[0]),
        "tempo_padrao_min": _f(vc.index[0] / 60), "tempos_distintos": _i(len(vc)),
        "rotulo_com": str(rotulo_com), "rotulo_sem": str(rotulo_sem),
        "com_ch": _i(contagem_tratamento[rotulo_com]),
        "sem_ch": _i(contagem_tratamento[rotulo_sem]),
        "com_correcao": _f(contagem_tratamento[rotulo_com] / total * 100),
        "sem_correcao": _f(contagem_tratamento[rotulo_sem] / total * 100),
        "ofensora": str(ofensora),
        "of_vol": _f(rk[rk[core.COL_ANOMALIA].eq(ofensora)]["% do Volume"].iloc[0]),
        "of_ch": _i(rk[rk[core.COL_ANOMALIA].eq(ofensora)]["Chamados"].iloc[0]),
        "of_pct_fora": _f(rk[rk[core.COL_ANOMALIA].eq(ofensora)]["% Fora do SLA"].iloc[0]),
        "of_pct_quebras": _f(q.iloc[0]["% de Todas as Quebras"]),
        "of_dono": str(dono.index[0]), "of_dono_qtd": _i(dono.iloc[0]),
        "of_dono_pct": _f(dono.iloc[0] / len(of_fora) * 100),
        "of_dist": {str(_i(k)): _i(v) for k, v in dist_of.items()},
        "imp_sla_atual": _f(imp["sla_atual"]), "imp_sla_novo": _f(imp["sla_novo"]),
        "imp_ganho": _f(imp["ganho_pontos"]), "imp_evitadas": _i(imp["quebras_evitadas"]),
        "alvo": str(alvo), "alvo_h": _f(top_horas["Horas Totais"]),
        "alvo_esf": _f(top_horas["% do Esforço"]), "alvo_vol": _f(top_horas["% do Volume"]),
        "alvo_ch": _i(top_horas["Chamados"]), "alvo_unit": _f(top_horas["Tempo Médio Unitário (min)"]),
        "alvo_pct_manual": _f(rec_alvo[core.COL_TIPO_LIBERACAO].eq("MANUAL").mean() * 100),
        "alvo_h_manual": horas_manual_alvo, "alvo_fte": _f(horas_manual_alvo / cap_dia),
        "alvo_pos_volume": _i(
            list(rk.sort_values("Chamados", ascending=False)[core.COL_ANOMALIA]).index(alvo) + 1
        ),
        # --- concentração temporal ----------------------------------------
        "marco_mes": mes_pior,
        "marco_nome": MESES_PT[pd.Period(mes_pior).month] + f" de {pd.Period(mes_pior).year}",
        "marco_chamados": _i(pior_mes["Chamados"]),
        "marco_quebras": _i(pior_mes["Fora do SLA"]),
        "marco_pct_quebras": _f(pior_mes["% das Quebras do Semestre"]),
        "marco_pct_fora": _f(pior_mes["% Fora do SLA"]),
        "marco_of_quebras": _i(len(of_no_mes)),
        "marco_of_dono_quebras": _i(len(of_dono_no_mes)),
        "mes_maior_volume": str(maior_volume["Mês"]),
        "maior_volume_e_pior": bool(str(maior_volume["Mês"]) == mes_pior),
        "correlacao_mensal": correlacao,
        "piso_semanal": core.PISO_DENOMINADOR_SEMANAL,
        "mensal": [
            {"mes": str(x["Mês"]), "ch": _i(x["Chamados"]), "fora": _i(x["Fora do SLA"]),
             "pct_fora": _f(x["% Fora do SLA"]), "pct_quebras": _f(x["% das Quebras do Semestre"])}
            for _, x in mensal.iterrows()
        ],
        "quebras": [
            {"anomalia": str(x[core.COL_ANOMALIA]), "fora": _i(x["Chamados Fora do SLA"]),
             "pct_todas": _f(x["% de Todas as Quebras"]), "pct_dela": _f(x["% do Volume da Anomalia"]),
             "acum": _f(x["% Acumulado"])} for _, x in q.head(5).iterrows()
        ],
        "top_volume": [
            {"a": str(x[core.COL_ANOMALIA]), "ch": _i(x["Chamados"]), "pct": _f(x["% do Volume"]),
             "fora": _f(x["% Fora do SLA"])} for _, x in r["rankings"]["por_volume"].iterrows()
        ],
        "top_horas": [
            {"a": str(x[core.COL_ANOMALIA]), "h": _f(x["Horas Totais"]), "pct": _f(x["% do Esforço"]),
             "manual": _f(x["% Manual"])} for _, x in r["rankings"]["por_horas"].iterrows()
        ],
        "top_unit": [
            {"a": str(x[core.COL_ANOMALIA]), "min": _f(x["Tempo Médio Unitário (min)"]),
             "ch": _i(x["Chamados"])} for _, x in r["rankings"]["por_unitario"].iterrows()
        ],
        "perfil": [
            {"nome": str(x[core.COL_COLABORADOR]), "ch": _i(x["Chamados Tratados"]),
             "h": _f(x["Horas Totais"]), "hdia": _f(x["Horas/Dia (média)"]),
             "fora": _f(x["% Fora do SLA"]), "manual": _f(x["% Manual"]),
             "origem": str(x["Origem Predominante"]),
             "fila": str(x.get("Anomalia que Mais Quebra SLA", "")),
             "pct_fila": _f(x.get("% das Quebras nessa Anomalia", 0))}
            for _, x in perfil.iterrows()
        ],
        "origens": [
            {"o": str(x[core.COL_ORIGEM]), "ch": _i(x["Chamados"]), "pct": _f(x["% Chamados"]),
             "fora": _f(x["% Fora do SLA"])}
            for _, x in core.distribuicao_por(df, core.COL_ORIGEM).iterrows()
        ],
    }


def validar(d: dict) -> list:
    """
    Devolve a lista de problemas encontrados. Lista vazia significa aprovado.

    As três famílias de checagem existem por causa do bug que motivou este
    arquivo: chave ausente, valor zerado por filtro que não casou, e par
    complementar que não fecha em 100.
    """
    problemas = []

    ausentes = [k for k in NAO_PODEM_SER_ZERO + ZERO_ESPERADO if k not in d]
    if ausentes:
        problemas.append(f"chaves ausentes: {ausentes}")

    for chave in NAO_PODEM_SER_ZERO:
        if chave in d and not d[chave]:
            problemas.append(
                f"'{chave}' está zerado. Zero aqui costuma ser filtro que não casou, "
                "e não medição legítima."
            )

    for a, b in PARES_COMPLEMENTARES:
        if a in d and b in d:
            soma = d[a] + d[b]
            if abs(soma - 100) > 0.01:
                problemas.append(
                    f"'{a}' + '{b}' = {soma:.4f}, deveria somar 100. "
                    "Percentuais complementares que não fecham indicam categoria perdida."
                )

    # Coerências aritméticas simples entre campos que descrevem o mesmo fato.
    if {"fora", "avaliaveis", "pct_fora"} <= d.keys():
        esperado = d["fora"] / d["avaliaveis"] * 100
        if abs(esperado - d["pct_fora"]) > 0.001:
            problemas.append(f"'pct_fora' não bate com fora/avaliaveis ({esperado:.4f})")
    if {"total", "avaliaveis", "invertidos", "em_aberto"} <= d.keys():
        if d["avaliaveis"] + d["invertidos"] != d["total"]:
            problemas.append("avaliaveis + invertidos != total")
    if {"marco_quebras", "fora", "marco_pct_quebras"} <= d.keys():
        esperado = d["marco_quebras"] / d["fora"] * 100
        if abs(esperado - d["marco_pct_quebras"]) > 0.001:
            problemas.append("'marco_pct_quebras' não bate com marco_quebras/fora")

    return problemas


def main(conferir_apenas: bool = False) -> int:
    if conferir_apenas:
        if not DESTINO.exists():
            print("numeros.json não existe. Rode sem --conferir para gerá-lo.")
            return 1
        dados = json.loads(DESTINO.read_text(encoding="utf-8"))
        print(f"Conferindo {DESTINO.name} ({len(dados)} chaves)...")
    else:
        print("Rodando o núcleo analítico...")
        dados = coletar()
        print(f"  {len(dados)} chaves coletadas")

    problemas = validar(dados)
    if problemas:
        print("\nVALIDAÇÃO FALHOU:")
        for p in problemas:
            print(f"  - {p}")
        print("\nNada foi gravado.")
        return 1

    print("\nValidação:")
    print(f"  [ok] nenhuma das {len(NAO_PODEM_SER_ZERO)} chaves obrigatórias está zerada")
    for a, b in PARES_COMPLEMENTARES:
        print(f"  [ok] {a} + {b} = {dados[a] + dados[b]:.4f}")
    print("  [ok] coerências aritméticas entre campos")

    if not conferir_apenas:
        DESTINO.write_text(
            json.dumps(dados, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"\nGravado: {DESTINO.name} ({DESTINO.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(conferir_apenas="--conferir" in sys.argv))
