import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
from io import BytesIO

# ========== AUTENTICAÇÃO ==========
SENHA_CORRETA = "pricing2025"

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

def validar_senha():
    if st.session_state["senha_digitada"] == SENHA_CORRETA:
        st.session_state["autenticado"] = True
    else:
        st.session_state["erro_autenticacao"] = True

if not st.session_state["autenticado"]:
    st.image("Logo.png", width=220)
    st.title("🔒 Acesso Restrito")
    st.text_input("Digite a senha:", type="password", key="senha_digitada", on_change=validar_senha)
    if st.session_state.get("erro_autenticacao", False):
        st.error("Senha incorreta.")
        st.session_state["erro_autenticacao"] = False
    st.stop()

# ========== CONFIGURAÇÃO VISUAL ==========
meses_pt = {'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr', 'May': 'Mai',
            'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago', 'Sep': 'Set', 'Oct': 'Out', 'Nov': 'Nov', 'Dec': 'Dez'}

st.set_page_config(page_title="Dashboard de Sinistralidade", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
.stMultiSelect [data-baseweb="tag"] {
    background-color: #1f77b4 !important;
    color: white !important;
}
.stMultiSelect [data-baseweb="tag"] .remove-button {
    color: white !important;
}
.stMultiSelect [role="option"]:hover {
    background-color: #d0e3f3 !important;
}
.stDateInput, .stDateInput input {
    direction: ltr;
    text-align: left;
}
.st-emotion-cache-1wmy9hl {
    font-family: "Segoe UI", sans-serif;
}
</style>
""", unsafe_allow_html=True)
# ========== SIDEBAR ==========
with st.sidebar:
    st.image("Logo.png", width=150)
    pagina = st.sidebar.radio("📌 Navegação", ["Resumo e Evolução", "Análise de Markup", "Simulações & Tendências"])
    st.title("📁 Política de Markup")
    st.caption("📌 Esta base será usada para comparar os dados reais com os valores ideais de markup.")
    base_politica = st.file_uploader("Upload da Política (.xlsx)", type="xlsx")

# ========== FUNÇÕES ==========
def calcular_indicadores(df):
    df["Sinistralidade"] = df["Despesa"] / df["Receita"]
    df["Frequência"] = (df["OS"] * 12) / df["Itens"]
    df["Markup"] = (1 - 0.0615) / df["Sinistralidade"]
    return df

def exportar_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Dados Filtrados")
    output.seek(0)
    return output

def obter_markup_politica(row, politica_df):
    politicas_produto = politica_df[politica_df["Produto"] == row["Produto"]]
    politicas_validas = politicas_produto[politicas_produto["Itens"] >= row["Itens"]]
    if not politicas_validas.empty:
        return politicas_validas.sort_values("Itens").iloc[0]["Markup Política"]
    return np.nan

def calcular_markup_politica(row, politica_df, produto_filtro):
    if produto_filtro == "Todos":
        return np.nan
    else:
        return obter_markup_politica({"Itens": row["Itens"], "Produto": produto_filtro}, politica_df)

# ========== BASE PRINCIPAL ==========
df = pd.read_excel("Base Final.xlsx")
df["Referência"] = pd.to_datetime(df["Referência"])
df["Período Formatado"] = df["Referência"].dt.strftime("%b/%Y").apply(lambda x: meses_pt.get(x[:3], x[:3]) + x[3:])
df = calcular_indicadores(df)

if base_politica:
    politica = pd.read_excel(base_politica)
    politica["Produto"] = politica["Produto"].astype(str)
    politica["Itens"] = politica["Itens"].astype(int)
else:
    politica = pd.DataFrame(columns=["Produto", "Itens", "Markup Política"])
# ========== PÁGINA 1 ==========
if pagina == "Resumo e Evolução":
    st.subheader("📈 Evolução Mensal do Markup")
    st.caption("ℹ️ Se nenhum valor for selecionado, todos os dados serão considerados.")

    col1, col2 = st.columns(2)
    filtro_seg = col1.multiselect("Filtrar Seguradora (Gráfico)", sorted(df["Seguradora"].unique()), default=[])
    filtro_prod = col2.selectbox("Filtrar Produto (Gráfico)", sorted(df["Produto"].unique()), index=sorted(df["Produto"].unique()).index("Geral"))

    df_agg = df.copy()
    if filtro_seg:
        df_agg = df_agg[df_agg["Seguradora"].isin(filtro_seg)]
    df_agg = df_agg[df_agg["Produto"] == filtro_prod]
    df_agg["Período Ordenado"] = df_agg["Referência"]

    df_agg = df_agg.groupby(["Período Formatado", "Período Ordenado"]).agg(
        Receita=('Receita', 'sum'),
        Despesa=('Despesa', 'sum'),
        Itens=('Itens', 'sum'),
        OS=('OS', 'sum')
    ).reset_index()

    df_agg = calcular_indicadores(df_agg)
    df_agg["Markup Política"] = np.nan
    if not politica.empty:
        df_agg["Markup Política"] = df_agg.apply(lambda row: calcular_markup_politica(row, politica, filtro_prod), axis=1)

    df_agg = df_agg.sort_values("Período Ordenado")
    fig = px.line(df_agg, x="Período Formatado", y="Markup", title="Evolução do Markup")
    if not df_agg["Markup Política"].isna().all():
        fig.add_scatter(x=df_agg["Período Formatado"], y=df_agg["Markup Política"], mode='lines+markers', name='Markup Política', line=dict(dash='dash', color='red'))
    st.plotly_chart(fig, use_container_width=True)

    df_filtro_resumo = df.copy()
    if filtro_seg:
        df_filtro_resumo = df_filtro_resumo[df_filtro_resumo["Seguradora"].isin(filtro_seg)]
    df_filtro_resumo = df_filtro_resumo[df_filtro_resumo["Produto"] == filtro_prod]
    qtd_meses_resumo = df_filtro_resumo["Referência"].nunique()
    receita_total = df_filtro_resumo["Receita"].sum()
    despesa_total = df_filtro_resumo["Despesa"].sum()
    receita_media = receita_total / qtd_meses_resumo if qtd_meses_resumo else 0
    despesa_media = despesa_total / qtd_meses_resumo if qtd_meses_resumo else 0
    sinistralidade_media = despesa_total / receita_total if receita_total else 0
    markup_medio = (1 - 0.0615) / sinistralidade_media if sinistralidade_media else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Receita Média Mensal", f"R$ {receita_media:,.2f}")
    col2.metric("Despesa Média Mensal", f"R$ {despesa_media:,.2f}")
    col3.metric("Sinistralidade Média", f"{sinistralidade_media:.2%}")
    col4.metric("Markup Médio", "---" if np.isinf(markup_medio) or np.isnan(markup_medio) else f"{markup_medio:.2f}")
elif pagina == "Análise de Markup":
    st.title("🧮 Análise Detalhada de Markup por Produto (Média Mensal)")
    df["Período Formatado"] = df["Referência"].dt.strftime("%b/%Y").str.capitalize()

    with st.sidebar:
        st.markdown("### 🎛️ Filtros")
        st.caption("ℹ️ Se nenhum valor for selecionado, todos os dados serão considerados.")
        periodos_disponiveis = sorted(df["Período Formatado"].unique(), key=lambda x: datetime.strptime(x, "%b/%Y"))
        periodo_selec = st.multiselect("Período", options=periodos_disponiveis, default=[])
        seguradora_selec = st.multiselect("Seguradora", sorted(df["Seguradora"].unique()), default=[])
        produto_selec = st.multiselect("Produto", sorted(df["Produto"].unique()), default=[])
        segmento_selec = st.multiselect("Segmento", sorted(df["Segmento"].unique()), default=[])
        novo_prod_selec = st.multiselect("Novo Produto?", df["Novo Produto?"].dropna().unique().tolist(), default=[])

    df_filtro = df.copy()
    if periodo_selec:
        df_filtro = df_filtro[df_filtro["Período Formatado"].isin(periodo_selec)]
    if seguradora_selec:
        df_filtro = df_filtro[df_filtro["Seguradora"].isin(seguradora_selec)]
    if produto_selec:
        df_filtro = df_filtro[df_filtro["Produto"].isin(produto_selec)]
    if segmento_selec:
        df_filtro = df_filtro[df_filtro["Segmento"].isin(segmento_selec)]
    if novo_prod_selec:
        df_filtro = df_filtro[df_filtro["Novo Produto?"].isin(novo_prod_selec)]

    qtd_meses_filtro = df_filtro["Referência"].nunique()
    df_filtro = calcular_indicadores(df_filtro)

    df_detalhado = df_filtro.groupby(["Seguradora", "Produto", "Segmento", "Novo Produto?"]).agg(
        Receita=("Receita", "sum"), Despesa=("Despesa", "sum"),
        OS=("OS", "sum"), Itens=("Itens", "sum")
    ).reset_index()

    df_detalhado[["Receita", "Despesa", "OS", "Itens"]] /= qtd_meses_filtro
    df_detalhado = calcular_indicadores(df_detalhado)
    df_detalhado["Markup"] = df_detalhado["Markup"].replace([np.inf, -np.inf], np.nan)

    if not politica.empty:
        df_detalhado["Markup Política"] = df_detalhado.apply(lambda row: obter_markup_politica(row, politica), axis=1)
    else:
        df_detalhado["Markup Política"] = np.nan

    df_detalhado["Gap Markup"] = df_detalhado["Markup"] - df_detalhado["Markup Política"]
    df_detalhado["Alerta"] = df_detalhado.apply(
        lambda row: "Não Calculado" if pd.isna(row["Markup"]) or pd.isna(row["Markup Política"]) else
        "❌ Muito Abaixo" if row["Gap Markup"] <= -2 else
        "⚠️ Abaixo" if -2 < row["Gap Markup"] <= -0.5 else
        "✔️ Dentro" if -0.5 < row["Gap Markup"] < 0.5 else
        "⚠️ Acima" if 0.5 <= row["Gap Markup"] < 2 else
        "❌ Muito Acima", axis=1
    )

    st.subheader("📌 Visão por Seguradora - Desvios do Markup Ideal")
    visao_seg = df_detalhado.copy()
    visao_seg["Fora da Política"] = visao_seg["Alerta"].isin(["❌ Muito Abaixo", "⚠️ Abaixo", "⚠️ Acima", "❌ Muito Acima"])
    resumo_seg = visao_seg.groupby("Seguradora").agg(
        Qtd_Produtos=("Produto", "count"),
        Qtd_Fora_Política=("Fora da Política", "sum")
    ).reset_index()
    resumo_seg["% Fora Política"] = resumo_seg["Qtd_Fora_Política"] / resumo_seg["Qtd_Produtos"]

    st.dataframe(resumo_seg.style.format({
        "Qtd_Produtos": "{:,.0f}",
        "Qtd_Fora_Política": "{:,.0f}",
        "% Fora Política": "{:.2%}"
    }), use_container_width=True)

    st.subheader("🚨 Markups Fora da Política")
    fora = df_detalhado[df_detalhado["Alerta"].isin(["❌ Muito Abaixo", "⚠️ Abaixo", "⚠️ Acima", "❌ Muito Acima"])]
    st.dataframe(fora[["Seguradora", "Produto", "Segmento", "Itens", "Markup", "Markup Política", "Gap Markup", "Alerta"]].style.format({
        "Itens": "{:,.0f}",
        "Markup": lambda x: "---" if pd.isna(x) else f"{x:.2f}",
        "Markup Política": lambda x: "---" if pd.isna(x) else f"{x:.2f}",
        "Gap Markup": lambda x: "---" if pd.isna(x) else f"{x:.2f}"
    }), use_container_width=True)

    st.subheader("🔍 Análise Detalhada")
    st.dataframe(df_detalhado.style.format({
        "Receita": "R$ {:,.2f}",
        "Despesa": "R$ {:,.2f}",
        "Itens": "{:,.0f}",
        "OS": "{:,.0f}",
        "Frequência": "{:.2%}",
        "Sinistralidade": "{:.2%}",
        "Markup": lambda x: "---" if pd.isna(x) else f"{x:.2f}",
        "Markup Política": lambda x: "---" if pd.isna(x) else f"{x:.2f}",
        "Gap Markup": lambda x: "---" if pd.isna(x) else f"{x:.2f}"
    }), use_container_width=True)

    excel = exportar_excel(df_detalhado)
    st.download_button(
        label="📥 Baixar Excel (Markup)",
        data=excel,
        file_name="analise_markup.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
# Adicione este trecho ao seu script Streamlit principal após as demais abas

elif pagina == "Simulações & Tendências":
    st.title("🔄 Simulações e Análise de Tendência")

    # ===== Simulador Detalhado =====
    st.subheader("🔢 Simulador: Impacto do Novo Markup por Produto e Seguradora")
    col1, col2, col3 = st.columns(3)
    produto_sim = col1.selectbox("Selecionar Produto", sorted(df["Produto"].unique()))
    seguradora_sim = col2.selectbox("Selecionar Seguradora", sorted(df["Seguradora"].unique()))
    novo_markup = col3.number_input("Novo Markup Ideal", min_value=0.01, max_value=10.0, step=0.05, value=1.5)

    df_impacto = df[(df["Produto"] == produto_sim) & (df["Seguradora"] == seguradora_sim)].copy()
    qtd_meses_impacto = df_impacto["Referência"].nunique()

    receita_m = df_impacto["Receita"].sum() / qtd_meses_impacto if qtd_meses_impacto else 0
    despesa_m = df_impacto["Despesa"].sum() / qtd_meses_impacto if qtd_meses_impacto else 0
    sinistralidade_atual = despesa_m / receita_m if receita_m else np.nan
    markup_atual = (1 - 0.0615) / sinistralidade_atual if sinistralidade_atual else np.nan
    sinistralidade_necessaria = (1 - 0.0615) / novo_markup if novo_markup != 0 else np.nan
    gap_simulado = novo_markup - markup_atual if not pd.isna(markup_atual) else np.nan

    alerta = "Não Calculado"
    if not pd.isna(gap_simulado):
        if gap_simulado <= -2:
            alerta = "❌ Muito Abaixo"
        elif -2 < gap_simulado <= -0.5:
            alerta = "⚠️ Abaixo"
        elif -0.5 < gap_simulado < 0.5:
            alerta = "✔️ Dentro"
        elif 0.5 <= gap_simulado < 2:
            alerta = "⚠️ Acima"
        else:
            alerta = "❌ Muito Acima"

    st.markdown(f"**Receita Média:** R$ {receita_m:,.2f} | **Despesa Média:** R$ {despesa_m:,.2f}")
    st.markdown(f"**Markup Atual:** {markup_atual:.2f} | **Gap Simulado:** {gap_simulado:.2f} ({alerta})")
    st.markdown(f"**Para atingir o markup de {novo_markup:.2f}, a sinistralidade máxima deve ser de {sinistralidade_necessaria:.2%}**")

    st.divider()

    # ===== Tendência com Previsão =====
    st.subheader("📊 Tendência Histórica e Previsão de Markup")
    tipo_tendencia = st.selectbox("Métrica a Analisar", ["Markup", "Gap Markup"])
    filtro_prod = st.multiselect("Produto", sorted(df["Produto"].unique()), default=[])
    filtro_seg = st.multiselect("Seguradora", sorted(df["Seguradora"].unique()), default=[])
    prever = st.checkbox("🔮 Incluir previsão para próximos 3 meses")

    df_trend = df.copy()
    if filtro_prod:
        df_trend = df_trend[df_trend["Produto"].isin(filtro_prod)]
    if filtro_seg:
        df_trend = df_trend[df_trend["Seguradora"].isin(filtro_seg)]

    df_trend = calcular_indicadores(df_trend)
    df_trend["Gap Markup"] = df_trend["Markup"] - df_trend.apply(lambda row: obter_markup_politica(row, politica) if not politica.empty else np.nan, axis=1)

    df_trend = df_trend.sort_values("Referência")
    df_trend["Período"] = df_trend["Referência"].dt.strftime("%b/%y")
    color_col = "Produto" if filtro_prod else "Seguradora"
    y_col = tipo_tendencia

    if prever:
        import statsmodels.api as sm
        forecast_df = pd.DataFrame()

        for key, grupo in df_trend.groupby(color_col):
            g = grupo.groupby("Referência")[y_col].mean().reset_index()
            g["num"] = range(len(g))
            X = sm.add_constant(g["num"])
            model = sm.OLS(g[y_col], X).fit()

            future = pd.DataFrame({"num": list(range(len(g), len(g)+3))})
            future_X = sm.add_constant(future)
            future[y_col] = model.predict(future_X)
            future["Referência"] = pd.date_range(g["Referência"].max() + pd.DateOffset(months=1), periods=3, freq="MS")
            future[color_col] = key

            forecast_df = pd.concat([forecast_df, future[["Referência", y_col, color_col]]])

        df_plot = pd.concat([df_trend[["Referência", y_col, color_col]], forecast_df])
        df_plot["Previsao"] = df_plot["Referência"] > df_trend["Referência"].max()
    else:
        df_plot = df_trend[["Referência", y_col, color_col]].copy()
        df_plot["Previsao"] = False

    fig = px.line(df_plot, x="Referência", y=y_col, color=color_col, line_dash="Previsao",
                  title=f"Tendência de {y_col} com ou sem previsão", markers=True)
    st.plotly_chart(fig, use_container_width=True)

# ========== RODAPÉ ==========
st.markdown("---")
st.image("Logo.png", width=120)
st.caption("© 2025 - Maxpar | Painel desenvolvido pela equipe de Pricing.")
