import re
import glob
import pandas as pd
import streamlit as st
import plotly.express as px

# ------------------------------
# Config da página
# ------------------------------
st.set_page_config(page_title="IDEB — Comparação IDEB × Meta", layout="wide")

st.title("📊 IDEB — Comparação IDEB × Meta")
st.markdown(
    "**Autora:** Millena Simoncelo de Lima  \n"
    "**Fonte:** INEP — Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira  \n"
    "**Abrangência:** Municípios do Espírito Santo"
)

with st.expander("📖 Entenda a relação entre o IDEB observado e a meta"):
    st.markdown("""
    O IDEB combina **desempenho (nota do SAEB)** e **fluxo escolar (taxa de aprovação)**.  
    As metas do IDEB são definidas pelo MEC com base em projeções de crescimento para cada rede e escola,  
    visando que o Brasil atinja média **6,0 até 2022**.

    A diferença entre o **IDEB observado** e a **meta projetada** indica o progresso da rede de ensino  
    em relação aos objetivos estabelecidos.

    🔗 Saiba mais em: [Metas do IDEB – QEdu](https://conteudos.qedu.org.br/metas-do-ideb/)
    """)

with st.expander("ℹ️ Sobre o app / dados utilizados"):
    st.write("Tema: comparação do IDEB observado com a Meta prevista, por etapa (Anos Iniciais/Finais/Médio).")
    st.write("Base atual: INEP (IDEB – escolas dos municípios do Espírito Santo)")

# ------------------------------
# Carregamento da base
# ------------------------------
PADRAO = "divulgacao_anos_finais_escolas_2023 - Copia.xlsx"

def try_load_local():
    xlsx_files = [f for f in glob.glob("*.xlsx")]
    preferida = PADRAO if PADRAO in xlsx_files else (xlsx_files[0] if xlsx_files else None)
    if preferida:
        try:
            return pd.read_excel(preferida), preferida
        except Exception:
            return None, None
    return None, None

df_raw, nome_arquivo = try_load_local()

if df_raw is None:
    st.info("Envie a base (.xlsx) para continuar.")
    up = st.file_uploader("Arquivo Excel", type=["xlsx"])
    if up is not None:
        df_raw = pd.read_excel(up)
        nome_arquivo = up.name

if df_raw is None:
    st.stop()

# ------------------------------
# Normalização das colunas
# ------------------------------
df = df_raw.rename(columns={
    "Nome do Município": "Município",
    "Nome da Escola": "Escola",
    "Rede": "Rede",
    "ETAPA": "Etapa"
})

def limpa(c: str) -> str:
    return re.sub(r"\s+", " ", str(c)).strip()

cols = {c: limpa(c) for c in df.columns}
df = df.rename(columns=cols)

ideb_cols = [c for c in df.columns if re.match(r"^IDEB\s*\d{4}$", c)]
meta_cols = [c for c in df.columns if re.match(r"^META\s*\d{4}$", c)]

def ano_de(c):  # extrai yyyy
    return int(re.search(r"(\d{4})", c).group(1))

ideb_map = {ano_de(c): c for c in ideb_cols}
meta_map = {ano_de(c): c for c in meta_cols}
anos_comuns = sorted(set(ideb_map.keys()) & set(meta_map.keys()))

# formato longo
long_rows = []
base_cols = ["Município", "Escola", "Rede", "Etapa"]
for ano in anos_comuns:
    bloco = df[base_cols].copy()
    bloco["Ano"] = ano
    bloco["Resultado"] = pd.to_numeric(df[ideb_map[ano]], errors="coerce")
    bloco["Meta"] = pd.to_numeric(df[meta_map[ano]], errors="coerce")
    long_rows.append(bloco)

df_long = pd.concat(long_rows, ignore_index=True)

# ------------------------------
# Filtros
# ------------------------------
with st.sidebar:
    st.header("Filtros")
    rede_opt = sorted(df_long["Rede"].dropna().unique())
    etapa_opt = sorted(df_long["Etapa"].dropna().unique())
    muni_opt = sorted(df_long["Município"].dropna().unique())
    escola_opt = sorted(df_long["Escola"].dropna().unique())

    sel_rede = st.multiselect("Rede", rede_opt)
    sel_etapa = st.multiselect("Etapa", etapa_opt)
    sel_muni = st.multiselect("Município", muni_opt)
    sel_escola = st.multiselect("Escola", escola_opt)

df_f = df_long.copy()
if sel_rede:
    df_f = df_f[df_f["Rede"].isin(sel_rede)]
if sel_etapa:
    df_f = df_f[df_f["Etapa"].isin(sel_etapa)]
if sel_muni:
    df_f = df_f[df_f["Município"].isin(sel_muni)]
if sel_escola:
    df_f = df_f[df_f["Escola"].isin(sel_escola)]

st.caption(f"Arquivo: *{nome_arquivo}* • Linhas totais: {len(df_long):,} • Linhas após filtros: {len(df_f):,}".replace(",", "."))

# ------------------------------
# Abas
# ------------------------------
tab_tabela, tab_desc, tab_graf, tab_rank = st.tabs(["📋 Tabela", "📊 Descritivas", "📈 Gráfico", "🏅 Ranking"])

# TABELA
with tab_tabela:
    st.subheader("Tabela detalhada (linhas por Escola/Ano)")
    st.dataframe(df_f, use_container_width=True)
    st.download_button(
        "Baixar CSV (filtrado)",
        df_f.to_csv(index=False).encode("utf-8"),
        file_name="tabela_filtrada.csv"
    )

# DESCRITIVAS
with tab_desc:
    st.subheader("Estatísticas descritivas — IDEB Observado (por Etapa)")
    if df_f.empty:
        st.warning("Sem dados após os filtros.")
    else:
        desc_etapa = df_f.groupby("Etapa")["Resultado"].describe().reset_index()
        st.dataframe(desc_etapa, use_container_width=True)

# GRÁFICOS
with tab_graf:
    st.subheader("Comparação IDEB (barras) × Meta (linha) — por Etapa")
    if df_f.empty:
        st.warning("Sem dados após os filtros.")
    else:
        etapas_presentes = sorted(df_f["Etapa"].dropna().unique())
        for etapa_nome in etapas_presentes:
            df_e = (df_f[df_f["Etapa"] == etapa_nome]
                    .groupby("Ano")[["Resultado", "Meta"]]
                    .mean()
                    .reset_index()
                    .sort_values("Ano"))

            st.markdown(f"**{etapa_nome}**")
            fig = px.bar(
                df_e, x="Ano", y="Resultado",
                labels={"Resultado": "IDEB observado", "Ano": "Ano"},
                color_discrete_sequence=["#1f77b4"]
            )
            fig.add_scatter(
                x=df_e["Ano"], y=df_e["Meta"],
                mode="lines+markers", name="Meta",
                line=dict(color="#7fc8ff")
            )
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

# ---------------------------
# ABA — Ranking
# ---------------------------
with tab_rank:
    st.subheader("🏅 Ranking de Escolas por Etapa (IDEB 2021)")

    # Filtra apenas o ano de 2021 e remove valores ausentes
    df_2021 = df_f[df_f["Ano"] == 2021].dropna(subset=["Resultado", "Etapa", "Escola"])

    if df_2021.empty:
        st.info("Não há dados disponíveis para o ano de 2021 com os filtros selecionados.")
    else:
        etapas = df_2021["Etapa"].dropna().unique()

        for etapa in etapas:
            st.markdown(f"### 🎓 {etapa}")
            df_etapa = df_2021[df_2021["Etapa"] == etapa].copy()

            # Ordena do maior para o menor IDEB
            ranking = (
                df_etapa.groupby("Escola")["Resultado"]
                .mean()
                .sort_values(ascending=False)
                .reset_index()
            )

            # Mostra tabela
            st.dataframe(ranking, use_container_width=True)

            # Gráfico de barras decrescente (Top 10)
            top10 = ranking.head(10)
            fig = px.bar(
                top10,
                x="Resultado",
                y="Escola",
                orientation="h",
                text="Resultado",
                color="Resultado",
                color_continuous_scale="Blues",
                title=f"Top 10 Escolas — {etapa}",
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig.update_layout(
                xaxis_title="IDEB 2021",
                yaxis_title=None,
                yaxis={"categoryorder": "total ascending"},
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
