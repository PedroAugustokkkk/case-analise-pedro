# -*- coding: utf-8 -*-
"""
Confere que os quatro artefatos publicados contam a mesma história.

O QUE ISSO EVITA
    Os números aparecem em quatro lugares: o núcleo (`analise_core.py`), o
    `numeros.json` que alimenta o Word, o `DOCUMENTO_ANALISE.docx` e o
    `resultado_analise.xlsx`. Nada impede que um seja atualizado e os outros
    fiquem para trás. Foi assim que `com_correcao` acabou publicado como 0,0%:
    o JSON era mantido à mão e ninguém confrontava com o núcleo.

    Este script recalcula tudo do núcleo e confronta com o que está gravado.

USO
    python verificar_consistencia.py
    Sai com código 1 se qualquer confronto falhar.
"""

import json
import re
import sys
import zipfile

import pandas as pd

import analise_core as core
import gerar_numeros

JSON = core.RAIZ / "numeros.json"
DOCX = core.RAIZ / "DOCUMENTO_ANALISE.docx"
XLSX = core.RAIZ / "resultado_analise.xlsx"

falhas = []
avisos = []


def ok(nome: str, condicao: bool, detalhe: str = "") -> None:
    marca = "  [ok]  " if condicao else "  [FALHA]"
    print(f"{marca} {nome}{(' — ' + detalhe) if detalhe else ''}")
    if not condicao:
        falhas.append(nome)


def texto_docx(caminho) -> str:
    """Extrai o texto corrido do .docx sem dependência externa."""
    with zipfile.ZipFile(caminho) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml)


def fmt(valor, casas=0) -> str:
    """Mesma formatação pt-BR usada no documento."""
    return f"{valor:,.{casas}f}".replace(",", "|").replace(".", ",").replace("|", ".")


def main() -> int:
    print("=" * 78)
    print("VERIFICAÇÃO CRUZADA DOS ARTEFATOS")
    print("=" * 78)

    for arquivo in (JSON, DOCX, XLSX):
        if not arquivo.exists():
            print(f"Arquivo ausente: {arquivo.name}")
            return 1

    salvo = json.loads(JSON.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- 1 ----
    print("\n1. numeros.json reproduz o núcleo analítico")
    fresco = gerar_numeros.coletar()
    divergentes = []
    for chave, valor in fresco.items():
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            gravado = salvo.get(chave)
            if gravado is None or abs(float(gravado) - float(valor)) > 1e-6:
                divergentes.append(f"{chave}: json={gravado} núcleo={valor}")
    ok(f"{len(fresco)} chaves conferidas contra uma execução nova do núcleo",
       not divergentes, "; ".join(divergentes[:3]) if divergentes else "")

    print("\n2. validações internas do numeros.json")
    problemas = gerar_numeros.validar(salvo)
    ok("nenhuma chave zerada, ausente ou par que não fecha em 100",
       not problemas, "; ".join(problemas[:2]) if problemas else "")

    # ---------------------------------------------------------------- 3 ----
    print("\n3. o .docx imprime os números do numeros.json")
    texto = texto_docx(DOCX)
    esperados = [
        ("total de retenções", fmt(salvo["total"])),
        ("chamados avaliáveis", fmt(salvo["avaliaveis"])),
        ("% fora do prazo", fmt(salvo["pct_fora"], 2) + "%"),
        ("quebras da anomalia ofensora", fmt(salvo["of_pct_quebras"], 1) + "%"),
        ("esforço total", fmt(salvo["horas_total"], 0)),
        ("com correção", fmt(salvo["com_correcao"], 1) + "%"),
        ("sem correção", fmt(salvo["sem_correcao"], 1) + "%"),
        ("quebras do pior mês", fmt(salvo["marco_quebras"])),
        ("% das quebras no pior mês", fmt(salvo["marco_pct_quebras"], 1) + "%"),
        ("último tratamento", salvo["fim_trat"]),
    ]
    for nome, valor in esperados:
        ok(f"{nome} ({valor})", valor in texto)

    # ---------------------------------------------------------------- 4 ----
    print("\n4. o .docx não contém o erro que a auditoria apontou")
    # O padrão antigo era "0,0% contra 50,0%". A busca precisa exigir que o zero
    # não seja precedido de dígito, senão "50,0% contra" dá falso positivo.
    ok("nenhum percentual de tratamento sai como 0,0%",
       re.search(r"(?<!\d)0,0% contra", texto) is None)
    ok("as contagens de tratamento aparecem e somam o total",
       fmt(salvo["com_ch"]) in texto and fmt(salvo["sem_ch"]) in texto
       and salvo["com_ch"] + salvo["sem_ch"] == salvo["total"])
    soma = salvo["com_correcao"] + salvo["sem_correcao"]
    ok("os dois percentuais de tratamento somam 100", abs(soma - 100) < 0.01, f"{soma:.4f}%")
    ok("não afirma que o atraso ignora os picos de volume",
       "não coincidem com as semanas" not in texto)

    # ---------------------------------------------------------------- 5 ----
    print("\n5. o .xlsx bate com o núcleo")
    base = pd.read_excel(XLSX, sheet_name="Base Enriquecida")
    sat = pd.read_excel(XLSX, sheet_name="Saturação por Dia")
    rk = pd.read_excel(XLSX, sheet_name="Ranking Anomalias")
    ok("linhas da base enriquecida", len(base) == salvo["total"], fmt(len(base)))
    ok("chamados fora do SLA", int(base["Fora do SLA"].sum()) == salvo["fora"],
       fmt(int(base["Fora do SLA"].sum())))
    ok("esforço total", abs(base["Horas Atribuídas"].sum() - salvo["horas_total"]) < 0.01,
       fmt(base["Horas Atribuídas"].sum(), 2))
    ok("soma do ranking = total de chamados", int(rk["Chamados"].sum()) == salvo["total"])
    ok("soma do ranking = esforço total",
       abs(rk["Horas Totais"].sum() - salvo["horas_total"]) < 0.01)
    ok("pares colaborador-dia", len(sat) == salvo["pares"], fmt(len(sat)))
    ok("dias acima da saturação", int(sat["Estourou Saturação"].sum()) == salvo["estouros"],
       str(int(sat["Estourou Saturação"].sum())))

    # ---------------------------------------------------------------- 6 ----
    print("\n6. o app lê os mesmos agregados")
    # O app não é importável sem o runtime do Streamlit; conferimos as funções do
    # núcleo que ele chama, que são a única fonte dos números exibidos.
    r = core.analisar()
    df = r["df"]
    ok("% fora do SLA do painel",
       abs(r["meta"]["sla"]["fora"] / r["meta"]["sla"]["avaliaveis"] * 100 - salvo["pct_fora"]) < 1e-9)
    ok("esforço do painel",
       abs(r["meta"]["esforco"]["horas_adotado"] - salvo["horas_total"]) < 0.01)
    ok("anomalia ofensora do painel", r["quebras"].iloc[0][core.COL_ANOMALIA] == salvo["ofensora"])
    mensal = core.distribuicao_mensal(df)
    pior = mensal.sort_values("Fora do SLA", ascending=False).iloc[0]
    ok("pior mês do painel", int(pior["Fora do SLA"]) == salvo["marco_quebras"])

    print("\n7. denominador unificado entre os cortes")
    for nome, tabela, coluna in [
        ("por anomalia", r["rankings"]["ranking"], "% Fora do SLA"),
        ("por colaborador", r["perfil_colaborador"], "% Fora do SLA"),
        ("por origem", core.distribuicao_por(df, core.COL_ORIGEM), "% Fora do SLA"),
    ]:
        dentro = tabela[coluna].dropna().between(0, 100).all()
        ok(f"{nome}: percentuais em faixa válida", bool(dentro))
    total_fora = int(df["Fora do SLA"].eq(True).sum())
    ok("soma das quebras por anomalia = total",
       int(r["rankings"]["ranking"]["Chamados Fora do SLA"].sum()) == total_fora,
       fmt(total_fora))

    print("\n8. série semanal com piso de denominador")
    serie = core.serie_temporal(df)
    baixas = serie[~serie["Denominador Suficiente"]]
    ok("semanas de baixo volume ficam sem percentual",
       bool(baixas["% Fora do SLA"].isna().all()),
       f"{len(baixas)} semanas abaixo de {core.PISO_DENOMINADOR_SEMANAL} chamados")

    print("\n" + "=" * 78)
    if falhas:
        print(f"FALHOU: {len(falhas)} verificação(ões)")
        for f in falhas:
            print(f"  - {f}")
        return 1
    print("TODOS OS ARTEFATOS CONCORDAM")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
