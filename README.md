# Análise de Anomalias de Faturamento

Análise da base de retenções de faturamento e dashboard gerencial.

A operação tratou **163.811 retenções** em seis meses, com **6,23% fora do prazo**
de dois dias. O dashboard mostra o diagnóstico, os achados de qualidade de dado e
as recomendações, com a leitura de cada número escrita ao lado dele.

---

## Como rodar localmente

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # e edite a senha
streamlit run app.py
```

O app abre em `http://localhost:8501` e pede a senha antes de qualquer coisa.

Para gerar o relatório de linha de comando e o Excel de resultados:

```bash
python analise_anomalias.py
```

Para regerar o Parquet derivado, depois de alterar a planilha:

```bash
python preparar_dados.py
```

Depois de qualquer mudança que afete números, regere os derivados nesta ordem e
confira que os quatro artefatos continuam concordando:

```bash
python analise_anomalias.py        # relatório e resultado_analise.xlsx
python gerar_numeros.py            # numeros.json, com validação
node gerar_documento.js numeros.json DOCUMENTO_ANALISE.docx
python verificar_consistencia.py   # confronta os quatro entre si
```

---

## Senha do dashboard

A senha fica em `st.secrets`, nunca no código nem no repositório. A comparação usa
`hmac.compare_digest` em vez de `==`, porque o `==` de strings sai no primeiro
caractere diferente e o tempo de resposta acaba revelando quantos caracteres
iniciais estão certos.

**Rodando local**, crie `.streamlit/secrets.toml` (já está no `.gitignore`):

```toml
senha = "sua-senha-aqui"
```

**No Streamlit Community Cloud**, não crie arquivo. Abra o app no painel, vá em
**Settings › Secrets** e cole a mesma linha. O app reinicia sozinho.

Sem segredo configurado o dashboard não abre: mostra uma tela explicando como
configurar e para por ali.

> A senha protege o **app**. Ela não protege o **repositório**. Veja a próxima
> seção antes de escolher entre repo público e privado.

---

## Antes de publicar: o repositório contém a planilha

`Case_Processo_Seletivo.xlsx` está versionado, porque é a fonte de todos os
números. Se o repositório for **público**, a planilha fica pública junto, com
senha no dashboard ou sem. Qualquer pessoa pode baixar o arquivo direto do GitHub.

A recomendação é **repositório privado com o app público**. Isso funciona na
camada gratuita e dá a combinação que interessa:

| | Repo público | **Repo privado, app público** | Repo privado, app privado |
|---|---|---|---|
| Planilha exposta | sim | não | não |
| Link funciona para qualquer pessoa | sim | sim | não, só convidados por e-mail |
| Dado protegido por senha | só o app | app e repo | app e repo |
| Cabe na camada gratuita | sim | sim | sim (1 app privado) |

O Community Cloud aceita repositório privado na camada gratuita. O app criado a
partir dele **nasce privado** e pode ser tornado público em
**Settings › Sharing › "This app is public and searchable"**. Público aqui
significa que a URL abre para qualquer um, e a senha do dashboard continua sendo
o que separa quem vê os dados de quem não vê.

Se preferir não versionar a planilha, tire-a do repositório e suba apenas
`dados/base.parquet` (757 KB, mesmo conteúdo da aba `Base de Dados`). O app roda
igual. As abas de premissas e do enunciado, porém, só existem no `.xlsx`, então
seria preciso derivá-las também.

---

## Deploy no Streamlit Community Cloud

1. Crie o repositório no GitHub, **privado**, e suba este projeto.
2. Entre em [share.streamlit.io](https://share.streamlit.io) com a conta do GitHub.
   Para repositório privado é preciso autorizar o escopo `repo`, que o Streamlit
   pede na primeira vez.
3. **Create app › Deploy a public app from GitHub repo** e preencha:
   - **Repository:** `seu-usuario/seu-repo`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **Advanced settings › Python version:** `3.11` (foi a versão usada aqui)
4. Ainda em **Advanced settings › Secrets**, cole:

   ```toml
   senha = "sua-senha-aqui"
   ```

5. **Deploy**. A primeira construção instala as dependências e leva alguns
   minutos. As seguintes são rápidas.
6. Se quiser o link aberto a qualquer pessoa, vá em **Settings › Sharing** e
   marque que o app é público.

Cada `git push` na branch publicada atualiza o app automaticamente.

### Limites da camada gratuita, e como este app se comporta neles

| Limite | Valor | Situação deste app |
|---|---|---|
| Memória | 690 MB a 2,7 GB | pico medido de 291 MB no processamento |
| CPU | 0,078 a 2 núcleos | ver observação sobre o Parquet abaixo |
| Armazenamento | até 50 GB | repositório com cerca de 21 MB |
| Hibernação | dorme após 12 h sem acesso | acorda no primeiro acesso, com alguns segundos de espera |
| Apps privados | 1 por conta | a recomendação usa app público, então não consome essa cota |

**Sobre o tempo de partida.** Ler as 163 mil linhas da aba `Base de Dados` com o
openpyxl leva cerca de 8 segundos aqui, e numa fração de núcleo levaria bem mais.
Por isso `preparar_dados.py` grava `dados/base.parquet`, que carrega o mesmo
conteúdo com os mesmos dtypes em centésimos de segundo. O pipeline inteiro caiu
de **11,2 s para 2,8 s**, com resultado idêntico ao da planilha.

O núcleo usa o Parquet quando ele existe e volta a ler o `.xlsx` quando não
existe. A planilha continua sendo a fonte da verdade; o Parquet é descartável e
pode ser regerado a qualquer momento com `python preparar_dados.py`.

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `app.py` | Dashboard Streamlit, com a leitura de cada número escrita ao lado |
| `auth.py` | Proteção por senha (`st.secrets` + `hmac.compare_digest`) |
| `analise_core.py` | **Núcleo analítico**: toda a regra de negócio, sem impressão nem escrita em disco |
| `analise_anomalias.py` | Relatório de linha de comando e exportação do Excel |
| `preparar_dados.py` | Gera e confere `dados/base.parquet` a partir da planilha |
| `Case_Processo_Seletivo.xlsx` | Planilha original, fonte da verdade |
| `dados/base.parquet` | Derivado da aba `Base de Dados`, só por desempenho |
| `resultado_analise.xlsx` | Base enriquecida (163.811 linhas) e oito abas de resumo |
| `saida_execucao.txt` | Saída real da execução, com o log das validações |
| `DOCUMENTO_ANALISE.docx` | Documento de entrega: contexto, diagnóstico, achados, recomendações e racional |
| `MEMORIAL_DO_CASE.md` / `.pdf` | Memorial de estudo: anatomia da base, método detalhado, perguntas prováveis |
| `gerar_numeros.py` | Gera e valida `numeros.json` a partir do núcleo; falha se alguma chave ficar zerada ou se percentuais complementares não somarem 100 |
| `gerar_documento.js` / `numeros.json` | Geração do `.docx` a partir dos números do núcleo |
| `verificar_consistencia.py` | Confronta núcleo, `numeros.json`, `.docx` e `.xlsx` entre si; sai com erro se divergirem |
| `RELATORIO_AUDITORIA.md` | Auditoria independente que recalculou ~75 grandezas do zero |
| `auditoria_independente.py` | Reimplementação da análise usada pela auditoria, sem importar o núcleo |

A regra de negócio existe **apenas** em `analise_core.py`. O relatório, o
dashboard e o documento são camadas de apresentação sobre ele, o que impede que
os três divirjam entre si.

---

## Premissas e decisões

Lidas da aba `Premissas e Informações`: SLA de **2 dias**, saturação de
**7 h/dia**.

Onde a planilha era ambígua, escolhemos uma leitura, registramos e calculamos as
alternativas. As decisões estão no cabeçalho de `analise_core.py` (blocos `[D1]`
a `[D7]`), na aba **Racional analítico** do dashboard e na aba
`Premissas e Decisões` do Excel de resultados. As três de maior efeito:

- **`[D1]`** dias **corridos**, não úteis: a operação registra 5.342 tratamentos
  aos sábados e nenhum aos domingos, então o calendário útil padrão não se aplica;
- **`[D2]`** prazo cumprido com `atraso <= 2`; a leitura `< 2` levaria o
  indicador de 6,23% para 10,51%;
- **`[D4]`** tratamento massivo tem o tempo contado **uma vez por lote** e
  rateado; cobrar o tempo cheio por chamado inflaria o esforço em 4,5 vezes.
