"""
Aba Ranking.
Ranking de consultores por indicador + botão para alternar ranking de gerentes.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from modulos.calculos import (
    cor_indicador, CORES, fmt_brl, fmt_pct, fmt_num, atingimento
)
from modulos.iaf import consolidar_gerentes

INDICADORES_RANKING = {
    "Receita (R$)":            ("receita",            fmt_brl,                False),
    "% Ating. Receita":        ("at_receita",         lambda v: f"{v*100:.1f}%", False),
    "Boleto Médio (R$)":       ("boleto_medio",       fmt_brl,                False),
    "Itens por Boleto":        ("itens_por_boleto",   lambda v: fmt_num(v,2), False),
    "Preço Médio (R$)":        ("preco_medio",        fmt_brl,                False),
    "Pen. Boleto Turbinado":   ("pen_bt",             fmt_pct,                False),
    "Pen. Boleto Promocional": ("pen_bp",             fmt_pct,                False),
    "Pen. Facial":             ("pen_facial",         fmt_pct,                False),
    "% ID Cliente":            ("pct_id_cliente_iaf", fmt_pct,                False),
    "Serviços":                ("servicos_real",      lambda v: fmt_num(v,0), False),
}

def _cor_pos(pos):
    if pos == 1: return '#f59e0b'
    if pos == 2: return '#94a3b8'
    if pos == 3: return '#b45309'
    if pos <= 10: return '#2563eb'
    return '#6b7280'

def _grafico(df_rank, col_valor, fmt_fn, titulo, n=20):
    top = df_rank.head(n)
    fig = go.Figure(go.Bar(
        x=top[col_valor].fillna(0),
        y=top['consultor'],
        orientation='h',
        marker_color=[_cor_pos(i+1) for i in range(len(top))],
        text=top[col_valor].apply(lambda v: fmt_fn(v) if v is not None and not pd.isna(v) else "—"),
        textposition='outside',
        cliponaxis=False,
    ))
    fig.update_layout(
        title=titulo,
        height=max(380, len(top)*30+80),
        margin=dict(l=10, r=120, t=40, b=20),
        yaxis=dict(autorange='reversed'),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
    )
    return fig

def render(dados: dict, nps_por_pdv: dict = None):
    st.header("🏆 Ranking")

    base = dados.get('_base_calculada')
    if base is None:
        st.info("Carregue os arquivos para continuar.")
        return

    # Toggle consultores / gerentes
    if 'ranking_modo' not in st.session_state:
        st.session_state['ranking_modo'] = 'consultores'

    col_t1, col_t2, col_esp = st.columns([1.2, 1.2, 4])
    with col_t1:
        if st.button("👥 Consultores",
                     type="primary" if st.session_state['ranking_modo']=='consultores' else "secondary",
                     use_container_width=True, key="rank_btn_cons"):
            st.session_state['ranking_modo'] = 'consultores'
            st.rerun()
    with col_t2:
        if st.button("🏪 Gerentes",
                     type="primary" if st.session_state['ranking_modo']=='gerentes' else "secondary",
                     use_container_width=True, key="rank_btn_ger"):
            st.session_state['ranking_modo'] = 'gerentes'
            st.rerun()

    st.divider()

    # ── RANKING CONSULTORES ───────────────────────────────────────────────────
    if st.session_state['ranking_modo'] == 'consultores':
        is_ger = base.get('is_gerente', pd.Series(False, index=base.index)).fillna(False).astype(bool)
        df_cons = base[~is_ger].copy()
        sem_meta_mask = df_cons['meta_receita'].isna()

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            metrica = st.selectbox("Indicador", list(INDICADORES_RANKING.keys()), key="rank_metrica")
        with col2:
            pdv_filtro = st.selectbox(
                "Filtrar PDV",
                ["Todos"] + [str(p) for p in sorted(df_cons['pdv'].dropna().unique())],
                key="rank_pdv"
            )
        with col3:
            top_n = st.selectbox("Exibir top", [10, 20, 30, "Todos"], key="rank_topn")

        col_val, fmt_fn, _ = INDICADORES_RANKING[metrica]

        df_rank = df_cons[~sem_meta_mask].copy()
        if pdv_filtro != "Todos":
            df_rank = df_rank[df_rank['pdv'].astype(str) == pdv_filtro]

        if col_val.startswith('at_') and col_val not in df_rank.columns:
            col_base = col_val.replace('at_', '')
            col_meta = f"meta_{col_base}"
            if col_base in df_rank.columns and col_meta in df_rank.columns:
                df_rank[col_val] = df_rank.apply(
                    lambda r: atingimento(r.get(col_base), r.get(col_meta)), axis=1
                )

        df_rank = df_rank.dropna(subset=[col_val]).sort_values(col_val, ascending=False).reset_index(drop=True)
        df_rank.index += 1
        n_exibir = len(df_rank) if top_n == "Todos" else int(top_n)

        if df_rank.empty:
            st.info("Nenhum dado para o filtro selecionado.")
        else:
            fig = _grafico(df_rank, col_val, fmt_fn, f"Top {n_exibir} — {metrica}", n_exibir)
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📋 Tabela completa"):
                df_show = df_rank[['consultor','pdv',col_val]].copy()
                df_show[col_val] = df_show[col_val].apply(
                    lambda v: fmt_fn(v) if v is not None and not pd.isna(v) else "—"
                )
                df_show.columns = ['Consultor','PDV', metrica]
                st.dataframe(df_show, use_container_width=True)

            sem_meta_df = df_cons[sem_meta_mask][['consultor','pdv']].copy()
            if not sem_meta_df.empty:
                with st.expander(f"⚪ Sem meta ({len(sem_meta_df)})"):
                    st.dataframe(sem_meta_df.rename(columns={'consultor':'Consultor','pdv':'PDV'}),
                                 use_container_width=True, hide_index=True)

    # ── RANKING GERENTES ──────────────────────────────────────────────────────
    else:
        st.markdown(
            "Ranking consolidado dos gerentes pelas lojas que gerenciam. "
            "Gerentes com mais de uma loja têm resultados unificados "
            "(soma para volumes, média simples para taxas)."
        )

        is_ger = base.get('is_gerente', pd.Series(False, index=base.index)).fillna(False).astype(bool)
        df_ger_raw = base[is_ger]

        if df_ger_raw.empty:
            st.info(
                "Nenhum gerente identificado nos dados. "
                "Gerentes são reconhecidos pela meta 'GERENTE' no arquivo de metas."
            )
            st.markdown("**Visão alternativa: receita consolidada por PDV**")
            from modulos.calculos import TIPO_AGREGACAO
            colunas_agg = {c: ('sum' if TIPO_AGREGACAO.get(c)=='soma' else 'mean')
                           for c in TIPO_AGREGACAO if c in base.columns}
            df_pdv = base.groupby('pdv').agg(colunas_agg).reset_index()
            df_pdv['consultor'] = "PDV " + df_pdv['pdv'].astype(str)
            if 'receita' in df_pdv.columns:
                df_pdv = df_pdv.sort_values('receita', ascending=False)
                fig = _grafico(df_pdv, 'receita', fmt_brl, "Receita por PDV")
                st.plotly_chart(fig, use_container_width=True)
            return

        df_ger_cons = consolidar_gerentes(base)
        if df_ger_cons.empty:
            st.info("Não foi possível consolidar os dados dos gerentes.")
            return

        metrica_ger = st.selectbox("Indicador", [
            "Receita (R$)", "% Ating. Receita", "Boleto Médio (R$)",
            "Pen. Boleto Turbinado", "Pen. Facial", "Serviços"
        ], key="rank_ger_metrica")

        col_ger_map = {
            "Receita (R$)":          ("receita",            fmt_brl),
            "% Ating. Receita":      ("at_receita_gerente", lambda v: f"{v*100:.1f}%"),
            "Boleto Médio (R$)":     ("boleto_medio",       fmt_brl),
            "Pen. Boleto Turbinado": ("pen_bt",             fmt_pct),
            "Pen. Facial":           ("pen_facial",         fmt_pct),
            "Serviços":              ("servicos_real",      lambda v: fmt_num(v,0)),
        }
        col_ger, fmt_ger = col_ger_map[metrica_ger]

        if 'pdvs' in df_ger_cons.columns:
            with st.expander("Ver lojas por gerente"):
                for _, r in df_ger_cons.iterrows():
                    st.markdown(f"**{r['consultor']}** → PDVs: {r.get('pdvs','—')}")

        if col_ger in df_ger_cons.columns:
            df_ger_rank = (df_ger_cons.dropna(subset=[col_ger])
                           .sort_values(col_ger, ascending=False)
                           .reset_index(drop=True))
            df_ger_rank.index += 1
            fig_ger = _grafico(df_ger_rank, col_ger, fmt_ger,
                               f"Ranking Gerentes — {metrica_ger}")
            st.plotly_chart(fig_ger, use_container_width=True)
        else:
            st.info(f"Indicador '{metrica_ger}' não disponível para gerentes.")
