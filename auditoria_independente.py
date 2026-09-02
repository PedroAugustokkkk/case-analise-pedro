# -*- coding: utf-8 -*-
"""
Auditoria independente - reimplementacao cega do case de anomalias de faturamento.
Escrito SEM leitura previa de analise_core.py / analise_anomalias.py / app.py.

CONVENCOES DECLARADAS (escolhas explicitas desta implementacao):
  C1. Dias = dias CORRIDOS entre Data da Anomalia e Data de Tratamento (nao uteis).
  C2. SLA (prazo esperado = 2 dias): DENTRO se dias <= 2 ; FORA se dias > 2.
      Sensibilidade reportada tambem para o corte estrito (dias < 2).
  C3. Registros com data invertida (dias < 0) sao mantidos na base principal
      (contam como dentro do SLA por dias<=2) e reportados a parte como
      problema de qualidade de dado. Sensibilidade excluindo-os e reportada.
  C4. Merge dos Tempos Medios: LEFT JOIN many-to-one em 'Anomalia', com
      validacao de cardinalidade e de preservacao de contagem de linhas.
  C5. Horas/colaborador/dia: soma do tempo medio das anomalias agrupada por
      (Colaborador, Data de Tratamento). Cenario A = TODAS as linhas.
      Cenario B (sensibilidade) = apenas Tipo de Liberacao == MANUAL.
  C6. Empates no top-3 sao explicitamente detectados e reportados.
"""
import pandas as pd
import numpy as np

ARQ = 'Case_Processo_Seletivo.xlsx'
LIM_SLA_DIAS = 2
LIM_SATURACAO_H = 7.0
sec = []
def out(*a):
    s = ' '.join(str(x) for x in a)
    print(s); sec.append(s)

def h(t):
    out('\n' + '=' * 78); out(t); out('=' * 78)

# ---------------------------------------------------------------- 0. carga
h('0. CARGA E INTEGRIDADE DE ENTRADA')
base = pd.read_excel(ARQ, 'Base de Dados')
N0 = len(base)
out(f'Linhas na Base de Dados (bruto)........: {N0}')
out(f'Colunas................................: {list(base.columns)}')
out(f'Nulos por coluna.......................: {base.isna().sum().to_dict()}')
out(f'Linhas 100% duplicadas.................: {base.duplicated().sum()}')

prem_raw = pd.read_excel(ARQ, 'Premissas e Informações', header=None)
prem = prem_raw.iloc[3:, 1:3].dropna(how='all').copy()
prem.columns = ['Anomalia', 'TempoMedio']
prem = prem.dropna(subset=['Anomalia', 'TempoMedio'])
prem['TempoMedioSeg'] = prem['TempoMedio'].map(
    lambda t: t.hour * 3600 + t.minute * 60 + t.second)
out(f'Tipos de anomalia nas Premissas........: {len(prem)}')
out(f'Chave duplicada nas Premissas..........: {prem["Anomalia"].duplicated().sum()}')

# datas vem como texto no arquivo -> parse explicito
base['dt_anom'] = pd.to_datetime(base['Data da Anomalia'])
base['dt_trat'] = pd.to_datetime(base['Data de Tratamento'])
out(f'Falhas de parse de data................: '
    f'{base["dt_anom"].isna().sum()} / {base["dt_trat"].isna().sum()}')
out(f'Janela Data da Anomalia................: '
    f'{base["dt_anom"].min().date()} a {base["dt_anom"].max().date()}')
out(f'Janela Data de Tratamento..............: '
    f'{base["dt_trat"].min().date()} a {base["dt_trat"].max().date()}')

# --------------------------------------------------- 1. dias e flag de SLA
h('1. DIAS DE TRATAMENTO E FLAG DE SLA (limite 2 dias)')
base['dias'] = (base['dt_trat'] - base['dt_anom']).dt.days
neg = base['dias'] < 0
out(f'Registros com data invertida (dias<0)..: {neg.sum()} '
    f'({neg.mean()*100:.4f}%)  [C3]')
out(f'  distribuicao dos negativos...........: '
    f'{base.loc[neg, "dias"].value_counts().sort_index().to_dict()}')
out(f'dias: min={base["dias"].min()} max={base["dias"].max()} '
    f'media={base["dias"].mean():.4f} mediana={base["dias"].median()}')

base['fora_sla'] = base['dias'] > LIM_SLA_DIAS          # C2
fora = int(base['fora_sla'].sum())
dentro = N0 - fora
pct_fora = fora / N0 * 100
out(f'DENTRO do SLA (dias<=2)................: {dentro} ({dentro/N0*100:.4f}%)')
out(f'FORA   do SLA (dias> 2)................: {fora} ({pct_fora:.4f}%)')
out(f'CHECK soma das partes = total..........: {dentro + fora} == {N0} -> '
    f'{dentro + fora == N0}')
out(f'CHECK percentuais somam 100............: '
    f'{dentro/N0*100 + pct_fora:.6f}')

# sensibilidades de convencao
alt_estrito = int((base['dias'] >= LIM_SLA_DIAS).sum())
sem_neg = base[~neg]
alt_semneg = int(sem_neg['fora_sla'].sum())
out(f'[sens] corte estrito dias>=2 -> fora...: {alt_estrito} '
    f'({alt_estrito/N0*100:.4f}%)')
out(f'[sens] excluindo invertidos (n={len(sem_neg)}) -> fora: {alt_semneg} '
    f'({alt_semneg/len(sem_neg)*100:.4f}%)')
out(f'[sens] dias uteis (busday) -> fora.....: ', end='') if False else None
du = np.busday_count(base['dt_anom'].values.astype('datetime64[D]'),
                     base['dt_trat'].values.astype('datetime64[D]'))
base['dias_uteis'] = du
fora_u = int((base['dias_uteis'] > LIM_SLA_DIAS).sum())
out(f'[sens] dias UTEIS >2 -> fora do SLA....: {fora_u} '
    f'({fora_u/N0*100:.4f}%)')

out('\nDistribuicao de dias corridos (top 15):')
out(base['dias'].value_counts().sort_index().head(15).to_string())

# ------------------------------------------------------------- 2. merge
h('2. MERGE COM OS TEMPOS MEDIOS DAS PREMISSAS')
sem_prem = set(base['Anomalia']) - set(prem['Anomalia'])
nao_usadas = set(prem['Anomalia']) - set(base['Anomalia'])
out(f'Anomalias da base SEM tempo medio......: {len(sem_prem)} {sorted(sem_prem)}')
out(f'Premissas nunca usadas na base.........: {len(nao_usadas)} '
    f'{sorted(nao_usadas)}')

df = base.merge(prem[['Anomalia', 'TempoMedioSeg']], on='Anomalia',
                how='left', validate='many_to_one')
out(f'CHECK linhas antes/depois do merge.....: {N0} -> {len(df)} -> '
    f'{"PRESERVADO" if len(df) == N0 else "INFLOU/PERDEU"}')
out(f'CHECK tempo medio nulo apos merge......: {df["TempoMedioSeg"].isna().sum()}')
df['TempoMedioH'] = df['TempoMedioSeg'] / 3600.0
tot_h = df['TempoMedioH'].sum()
out(f'Esforco total da operacao..............: {tot_h:,.2f} h '
    f'({df["TempoMedioSeg"].sum():,.0f} s)')

# ------------------------------- 3. horas por colaborador por dia + estouro
h('3. HORAS POR COLABORADOR POR DIA DE TRATAMENTO (limite 7h/dia)')

def carga(d, rotulo):
    g = (d.groupby(['Colaborador(a)', 'dt_trat'], as_index=False)
           .agg(horas=('TempoMedioH', 'sum'), n=('TempoMedioH', 'size')))
    g['estouro'] = g['horas'] > LIM_SATURACAO_H
    est = int(g['estouro'].sum())
    out(f'\n--- {rotulo} ---')
    out(f'Pares colaborador-dia..................: {len(g)}')
    out(f'CHECK soma das horas do grupo = total..: {g["horas"].sum():,.4f} vs '
        f'{d["TempoMedioH"].sum():,.4f} -> '
        f'{np.isclose(g["horas"].sum(), d["TempoMedioH"].sum())}')
    out(f'CHECK soma das linhas do grupo = total.: {g["n"].sum()} vs {len(d)} -> '
        f'{g["n"].sum() == len(d)}')
    out(f'Dias-colaborador ACIMA de 7h...........: {est} '
        f'({est/len(g)*100:.4f}% dos pares)')
    out(f'Horas/dia: media={g["horas"].mean():.4f} '
        f'mediana={g["horas"].median():.4f} max={g["horas"].max():.4f}')
    out('Top 10 pares por horas:')
    out(g.nlargest(10, 'horas').to_string(index=False))
    out('Estouros por colaborador:')
    pc = (g.groupby('Colaborador(a)')
            .agg(dias=('estouro', 'size'), dias_estouro=('estouro', 'sum'),
                 h_media=('horas', 'mean'), h_max=('horas', 'max'))
            .sort_values('dias_estouro', ascending=False))
    pc['pct_dias_estouro'] = pc['dias_estouro'] / pc['dias'] * 100
    out(pc.to_string())
    return g

gA = carga(df, 'CENARIO A: todas as linhas (C5)')
gB = carga(df[df['Tipo de Liberação'] == 'MANUAL'],
           'CENARIO B (sensibilidade): apenas liberacao MANUAL')

# ----------------------------------------- 4. indicadores pedidos no item 4
h('4a. % FORA DO SLA')
out(f'% fora do SLA (base completa, dias>2)..: {pct_fora:.4f}%  '
    f'({fora}/{N0})')

h('4b. MANUAL vs MASSIVO - volume e esforco')
vol = df['Tipo de Liberação'].value_counts()
esf = df.groupby('Tipo de Liberação')['TempoMedioH'].sum()
mix = pd.DataFrame({'linhas': vol, 'pct_volume': vol / N0 * 100,
                    'horas': esf, 'pct_horas': esf / tot_h * 100})
mix['h_media_por_linha'] = mix['horas'] / mix['linhas']
out(mix.to_string())
out(f'CHECK volume soma total................: {int(mix["linhas"].sum())} == {N0}')
out(f'CHECK % volume soma 100................: {mix["pct_volume"].sum():.6f}')
out(f'CHECK % horas soma 100.................: {mix["pct_horas"].sum():.6f}')
out(f'CHECK horas somam o total..............: {mix["horas"].sum():,.4f} vs '
    f'{tot_h:,.4f}')
# SLA por tipo de liberacao
sla_lib = df.groupby('Tipo de Liberação')['fora_sla'].agg(['size', 'sum'])
sla_lib['pct_fora'] = sla_lib['sum'] / sla_lib['size'] * 100
out('\n% fora do SLA por tipo de liberacao:')
out(sla_lib.to_string())

h('4c. TOP 3 ANOMALIAS POR VOLUME')
tv = (df.groupby('Anomalia')
        .agg(linhas=('Anomalia', 'size'), horas=('TempoMedioH', 'sum'))
        .sort_values('linhas', ascending=False))
tv['pct_volume'] = tv['linhas'] / N0 * 100
out(tv.head(10).to_string())
out(f'TOP3 volume............................: {list(tv.head(3).index)}')
out(f'TOP3 volume concentra..................: '
    f'{tv.head(3)["pct_volume"].sum():.4f}% do volume')
v3 = tv['linhas'].iloc[2]
out(f'CHECK empate na 3a posicao (volume)....: '
    f'{(tv["linhas"] == v3).sum()} anomalia(s) com {v3} linhas')

h('4d. TOP 3 ANOMALIAS POR TEMPO GASTO')
tt = tv.sort_values('horas', ascending=False).copy()
tt['pct_horas'] = tt['horas'] / tot_h * 100
out(tt.head(10).to_string())
out(f'TOP3 tempo.............................: {list(tt.head(3).index)}')
out(f'TOP3 tempo concentra...................: '
    f'{tt.head(3)["pct_horas"].sum():.4f}% do esforco')
h3 = tt['horas'].iloc[2]
out(f'CHECK empate na 3a posicao (tempo).....: '
    f'{(np.isclose(tt["horas"], h3)).sum()} anomalia(s)')
out(f'CHECK soma % volume das anomalias......: {tv["pct_volume"].sum():.6f}')
out(f'CHECK soma % horas das anomalias.......: {tt["pct_horas"].sum():.6f}')

# ------------------------------------------------- 5. destaques auxiliares
h('5. RECORTES DE APOIO')
out('MANUAL01 - concentracao de quebras de SLA:')
m1 = df[df['Anomalia'] == 'MANUAL01']
out(f'  linhas MANUAL01......................: {len(m1)} '
    f'({len(m1)/N0*100:.4f}% da base)')
out(f'  quebras de SLA em MANUAL01...........: {int(m1["fora_sla"].sum())}')
out(f'  % das quebras totais que sao MANUAL01: '
    f'{int(m1["fora_sla"].sum())/fora*100:.4f}%')
out(f'  % de MANUAL01 fora do SLA............: {m1["fora_sla"].mean()*100:.4f}%')
out('\nTop 5 anomalias por numero absoluto de quebras de SLA:')
qb = (df[df['fora_sla']].groupby('Anomalia').size()
        .sort_values(ascending=False))
qbd = pd.DataFrame({'quebras': qb, 'pct_das_quebras': qb / fora * 100,
                    'linhas': tv['linhas']})
qbd['taxa_quebra'] = qbd['quebras'] / qbd['linhas'] * 100
out(qbd.head(5).to_string())
out(f'CHECK quebras somam o total............: {int(qb.sum())} == {fora}')

out('\nTipo de Tratamento:')
tt2 = df['Tipo de Tratamento'].value_counts()
out(pd.DataFrame({'linhas': tt2, 'pct': tt2 / N0 * 100}).to_string())
out('\nOrigem:')
og = df['Origem'].value_counts()
out(pd.DataFrame({'linhas': og, 'pct': og / N0 * 100}).to_string())
out('\nColaborador:')
cb = df.groupby('Colaborador(a)').agg(linhas=('dias', 'size'),
                                      horas=('TempoMedioH', 'sum'),
                                      fora_sla=('fora_sla', 'sum'))
cb['pct_fora_sla'] = cb['fora_sla'] / cb['linhas'] * 100
cb['pct_volume'] = cb['linhas'] / N0 * 100
out(cb.sort_values('linhas', ascending=False).to_string())
out(f'CHECK colaboradores somam total........: {int(cb["linhas"].sum())} == {N0}')
out(f'CHECK horas colaboradores = total......: {cb["horas"].sum():,.4f} vs '
    f'{tot_h:,.4f}')

df.to_pickle('/tmp/auditoria_df.pkl')
with open('saida_auditoria_independente.txt', 'w') as f:
    f.write('\n'.join(sec))
print('\n[ok] saida gravada em saida_auditoria_independente.txt')
