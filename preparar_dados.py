# -*- coding: utf-8 -*-
"""
Gera o derivado `dados/base.parquet` a partir da planilha original.

POR QUE ISSO EXISTE
    Ler as 163 mil linhas da aba 'Base de Dados' com o openpyxl leva cerca de
    8 segundos e consome CPU. Na hospedagem gratuita do Streamlit Community
    Cloud, onde a máquina pode receber uma fração de núcleo, esse custo aparece
    a cada partida a frio e a cada vez que o app acorda depois de hibernar.

    O Parquet carrega o mesmo conteúdo, com os mesmos dtypes, em centésimos de
    segundo, e ocupa menos de 1 MB.

O QUE É FONTE E O QUE É DERIVADO
    `Case_Processo_Seletivo.xlsx` continua sendo a fonte da verdade e permanece
    no repositório. `dados/base.parquet` é descartável: se sumir, o núcleo volta
    a ler a planilha sozinho. Se a planilha mudar, rode este script de novo.

USO
    python preparar_dados.py            # gera o derivado e confere
    python preparar_dados.py --conferir # só confere, sem regravar
"""

import sys

import pandas as pd

import analise_core as core


def gerar(conferir_apenas: bool = False) -> int:
    """Grava o Parquet e verifica que ele reproduz a planilha linha a linha."""
    print("Lendo a aba 'Base de Dados' da planilha original...")
    base = pd.read_excel(core.ARQUIVO_ENTRADA, sheet_name=core.ABA_BASE)
    print(f"  {len(base):,} linhas x {base.shape[1]} colunas".replace(",", "."))

    faltantes = [c for c in core.COLUNAS_OBRIGATORIAS if c not in base.columns]
    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes na planilha: {faltantes}")

    destino = core.PARQUET_BASE
    if not conferir_apenas:
        destino.parent.mkdir(parents=True, exist_ok=True)
        # zstd comprime bem melhor que snappy neste conjunto e é lido igualmente
        # rápido; o arquivo fica pequeno o suficiente para versionar sem incomodar.
        base.to_parquet(destino, engine="pyarrow", compression="zstd", index=False)
        print(f"\nGravado: {destino}")
        print(f"  {destino.stat().st_size / 1024:.0f} KB")

    if not destino.exists():
        print("\nDerivado ainda não existe. Rode sem --conferir para gerá-lo.")
        return 1

    # --- Conferência: o derivado precisa ser indistinguível da planilha ------
    print("\nConferindo o derivado contra a planilha:")
    lido = pd.read_parquet(destino)

    checagens = [
        ("mesmo número de linhas", len(lido) == len(base), f"{len(lido)} vs {len(base)}"),
        ("mesmas colunas, na mesma ordem", list(lido.columns) == list(base.columns), ""),
        ("mesmos dtypes", (lido.dtypes.astype(str) == base.dtypes.astype(str)).all(), ""),
        ("mesmo conteúdo", lido.equals(base), ""),
    ]
    tudo_ok = True
    for nome, ok, detalhe in checagens:
        print(f"  [{'ok' if ok else 'FALHOU'}] {nome}{(' — ' + detalhe) if detalhe else ''}")
        tudo_ok = tudo_ok and bool(ok)

    if not tudo_ok:
        print("\nO derivado NÃO reproduz a planilha. Não use este arquivo.")
        return 1

    print("\nO derivado reproduz a planilha exatamente. O app pode usá-lo com segurança.")
    return 0


if __name__ == "__main__":
    sys.exit(gerar(conferir_apenas="--conferir" in sys.argv))
