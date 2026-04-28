"""
Aba 1 — Resumo Consolidado.
Visão gerencial de toda a rede com indicadores somados e em média.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from modulos.calculos import (
    resumo_consolidado, cor_indicador, cor_indicador_invertido, CORES, CORES_IAF,
    fmt_brl, fmt_pct, fmt_num, atingimento_pct, atingimento
)
from modulos.iaf import calcular_iaf_base


def _badge_cor(cor: str):
    mapa = {
        'verde':    ('#dcfce7', '#166534'),
        'amarelo':  ('#fef9c3', '#854d0e'),
        'vermelho': ('#fee2e2', '#991b1b'),
        'cinza':    ('#f3f4f6', '#374151'),
    }
    return mapa.get(cor, mapa['cinza'])


def _fmt_vs_ly(v) -> str:
    """Formata variação vs LY com seta colorida."""
    if v is None:
        return ''
    try:
        import math
        f = float(v)
        if math.isnan(f) or str(v) == '-':
            return ''
        pct = f * 100
        sinal = '▲' if pct >= 0 else '▼'
        cor = '#16a34a' if pct >= 0 else '#dc2626'
        return (f'<div style="font-size:11px;color:{cor};font-weight:600;margin-top:3px;">'
                f'{sinal} {abs(pct):.1f}% vs LY</div>')
    except (TypeError, ValueError):
        return ''


def _card_indicador(nome: str, real, meta, at, cor: str, fmt_fn=None, vs_ly=None):
    """Renderiza um card de indicador com semáforo de cor e vs LY opcional."""
    bg, fg = _badge_cor(cor)
    fmt = fmt_fn or fmt_num
    real_str = fmt(real) if real is not None else "—"
    meta_str = fmt(meta) if meta is not None else "—"
    at_str   = f"{at*100:.1f}%" if at is not None else "—"
    ly_html  = _fmt_vs_ly(vs_ly) if vs_ly is not None else ''

    st.markdown(f"""
    <div style="background:{bg}; border-radius:10px; padding:14px 16px; margin-bottom:8px;">
        <div style="font-size:12px; color:{fg}; font-weight:600; margin-bottom:4px;">{nome}</div>
        <div style="font-size:22px; font-weight:700; color:{fg};">{real_str}</div>
        <div style="font-size:12px; color:{fg}; opacity:0.8;">
            Meta: {meta_str} &nbsp;|&nbsp; x Meta: {at_str}
        </div>
        {ly_html}
    </div>
    """, unsafe_allow_html=True)


def _get_vs_ly_total(dados: dict) -> dict:
    """Busca os valores vs LY da linha TOTAL do arquivo PDV."""
    df_pdv = dados.get('pdv')
    if df_pdv is None or df_pdv.empty:
        return {}
    # A linha TOTAL já foi removida no processamento — buscar do raw
    # Precisamos do df original antes do processamento
    # Alternativa: usar a média ponderada das linhas disponíveis
    # Como pdv já está processado, calculamos a média ponderada dos vs_ly por PDV
    resultado = {}
    try:
        if 'receita_vs_ly' in df_pdv.columns:
            # Média ponderada pela receita
            rec = pd.to_numeric(df_pdv.get('receita', pd.Series()), errors='coerce')
            for col, chave in [
                ('receita_vs_ly',          'receita'),
                ('boleto_medio_vs_ly',     'boleto_medio'),
                ('itens_por_boleto_vs_ly', 'itens_por_boleto'),
                ('preco_medio_vs_ly',      'preco_medio'),
            ]:
                if col in df_pdv.columns:
                    vals = pd.to_numeric(df_pdv[col], errors='coerce')
                    # Média simples entre os PDVs (exclui NaN e '-')
                    validos = vals.dropna()
                    if not validos.empty:
                        resultado[chave] = validos.mean()
    except Exception:
        pass
    return resultado


def render(dados: dict, nps_por_pdv: dict):
    st.header("📊 Resumo Consolidado — Toda a Rede")

    if 'consultor' not in dados or 'metas' not in dados:
        st.info("Carregue os arquivos de Consultores e Metas para visualizar o resumo.")
        return

    base_raw = dados.get('_base_calculada')
    if base_raw is None:
        st.info("Processando dados...")
        return

    metas = dados['metas']
    consolidado = resumo_consolidado(base_raw, metas)
    vs_ly = _get_vs_ly_total(dados)

    # ── KPIs principais ──────────────────────────────────────────────────────
    st.subheader("Indicadores Principais")

    principais = ['Receita', 'Boleto Médio', 'Itens/Boleto', 'Preço Médio', 'Serviços']
    cols = st.columns(len(principais))
    for i, nome in enumerate(principais):
        if nome not in consolidado:
            continue
        d = consolidado[nome]
        with cols[i]:
            if nome == 'Receita':
                _card_indicador(nome, d['realizado'], d['meta'], d['atingimento'], d['cor'],
                                fmt_brl, vs_ly=vs_ly.get('receita'))
            elif nome == 'Boleto Médio':
                _card_indicador(nome, d['realizado'], d['meta'], d['atingimento'], d['cor'],
                                fmt_brl, vs_ly=vs_ly.get('boleto_medio'))
            elif nome == 'Itens/Boleto':
                _card_indicador(nome, d['realizado'], d['meta'], d['atingimento'], d['cor'],
                                lambda v: fmt_num(v, 1), vs_ly=vs_ly.get('itens_por_boleto'))
            elif nome == 'Preço Médio':
                _card_indicador(nome, d['realizado'], d['meta'], d['atingimento'], d['cor'],
                                fmt_brl, vs_ly=vs_ly.get('preco_medio'))
            elif nome == 'Serviços':
                _card_indicador(nome, d['realizado'], d['meta'], d['atingimento'], d['cor'],
                                lambda v: fmt_num(v, 0))

    st.divider()

    # ── Penetrações ──────────────────────────────────────────────────────────
    st.subheader("Indicadores de Penetração")

    penetracoes = ['Pen. BT', 'Pen. BP', 'Pen. Mobshop', 'Pen. Boletos 1',
                   'Pen. Fidelidade', 'Resgate Fidelidade', 'Conv. Fluxo',
                   'Pen. Facial', '% ID Cliente']

    cols2 = st.columns(3)
    for i, nome in enumerate(penetracoes):
        if nome not in consolidado:
            continue
        d = consolidado[nome]
        with cols2[i % 3]:
            if nome == 'Resgate Fidelidade':
                meta_rf = d['meta'] * 100 if d['meta'] is not None else None
                at_rf = atingimento(d['realizado'], meta_rf)
                cor_rf = cor_indicador(at_rf) if at_rf is not None else 'cinza'
                _card_indicador(nome, d['realizado'], meta_rf, at_rf, cor_rf,
                                lambda v: f"{v:.1f}%")
            elif nome == 'Pen. Boletos 1':
                at_b1 = atingimento(d['realizado'], d['meta'])
                cor_b1 = cor_indicador_invertido(at_b1) if at_b1 is not None else 'cinza'
                _card_indicador(nome, d['realizado'], d['meta'], at_b1, cor_b1, fmt_pct)
            else:
                _card_indicador(nome, d['realizado'], d['meta'], d['atingimento'], d['cor'], fmt_pct)

    st.divider()

    # ── NPS ──────────────────────────────────────────────────────────────────
    st.subheader("NPS")
    pdvs_com_nps = {k: v for k, v in nps_por_pdv.items() if v and float(v) > 0} if nps_por_pdv else {}

    if pdvs_com_nps:
        meta_nps = None
        if not metas.empty and 'meta_nps' in metas.columns:
            meta_nps = pd.to_numeric(metas['meta_nps'], errors='coerce').mean()

        valores_nps = [float(v) for v in pdvs_com_nps.values()]
        media_nps = sum(valores_nps) / len(valores_nps)
        at_media = atingimento_pct(media_nps, meta_nps) if meta_nps else None
        cor_media = cor_indicador(at_media / 100 if at_media else None)
        bg_m, fg_m = _badge_cor(cor_media)

        col_med, col_esp = st.columns([1, 3])
        with col_med:
            st.markdown(f"""
            <div style="background:{bg_m};border-radius:10px;padding:14px;text-align:center;margin-bottom:8px;">
                <div style="font-size:11px;color:{fg_m};font-weight:600;">NPS Médio da Rede</div>
                <div style="font-size:28px;font-weight:700;color:{fg_m};">{media_nps:.1f}</div>
                <div style="font-size:11px;color:{fg_m};">Meta: {f'{meta_nps:.1f}' if meta_nps else 's/ meta'}</div>
            </div>
            """, unsafe_allow_html=True)

        st.caption("Por PDV:")
        cols_nps = st.columns(min(len(pdvs_com_nps), 4))
        for i, (pdv, valor) in enumerate(pdvs_com_nps.items()):
            at = atingimento_pct(float(valor), meta_nps) if meta_nps else None
            cor = cor_indicador(at / 100 if at else None)
            bg, fg = _badge_cor(cor)
            with cols_nps[i % 4]:
                st.markdown(f"""
                <div style="background:{bg};border-radius:10px;padding:10px;text-align:center;">
                    <div style="font-size:11px;color:{fg};font-weight:600;">PDV {pdv}</div>
                    <div style="font-size:20px;font-weight:700;color:{fg};">{float(valor):.1f}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.caption("Nenhum NPS lançado ainda. Acesse 'Por PDV' → Configurações para inserir.")

    st.divider()

    # ── Gráfico receita vs meta por PDV ──────────────────────────────────────
    st.subheader("Receita vs. Meta por PDV")

    _mask_ger = base_raw['is_gerente'].fillna(False).astype(bool) if 'is_gerente' in base_raw.columns else pd.Series(False, index=base_raw.index)
    pdv_rec = base_raw[~_mask_ger].groupby('pdv').agg(receita=('receita', 'sum')).reset_index()

    _mask_ger_m = metas['is_gerente'].fillna(False).astype(bool) if 'is_gerente' in metas.columns else pd.Series(False, index=metas.index)
    meta_pdv = metas[~_mask_ger_m].groupby('pdv').agg(meta=('meta_receita', 'sum')).reset_index()

    pdv_merge = pdv_rec.merge(meta_pdv, on='pdv', how='left')
    pdv_merge['pdv'] = pdv_merge['pdv'].astype(str)
    pdv_merge['at'] = pdv_merge.apply(lambda r: atingimento_pct(r['receita'], r['meta']), axis=1)
    pdv_merge['cor'] = pdv_merge['at'].apply(lambda v: CORES[cor_indicador(v / 100 if v else None)])

    fig = go.Figure()
    fig.add_bar(
        name="Realizado", x=pdv_merge['pdv'], y=pdv_merge['receita'],
        marker_color=pdv_merge['cor'].tolist(),
        text=pdv_merge['receita'].apply(fmt_brl), textposition='outside'
    )
    fig.add_scatter(
        name="Meta", x=pdv_merge['pdv'], y=pdv_merge['meta'],
        mode='markers+lines',
        marker=dict(symbol='diamond', size=10, color='#374151'),
        line=dict(color='#374151', dash='dot', width=1.5)
    )
    fig.update_layout(
        height=360, margin=dict(t=20, b=20),
        yaxis_tickformat=',.0f',
        legend=dict(orientation='h', y=1.08),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Distribuição IAF ─────────────────────────────────────────────────────
    st.subheader("Distribuição de Classificação IAF")

    base_iaf = calcular_iaf_base(base_raw, nps_por_pdv)
    classif_count = (
        base_iaf[base_iaf['classificacao'].notna() &
                 ~base_iaf['classificacao'].isin(['Gerente', 'Sem meta'])]
        ['classificacao'].value_counts()
    )

    ordem = ['Diamante', 'Ouro', 'Prata', 'Bronze', 'Não classificado']
    classif_ord = classif_count.reindex([c for c in ordem if c in classif_count.index], fill_value=0)

    fig2 = go.Figure(go.Bar(
        x=classif_ord.index.tolist(),
        y=classif_ord.values,
        marker_color=[CORES_IAF.get(c, '#6b7280') for c in classif_ord.index],
        text=classif_ord.values, textposition='outside'
    ))
    fig2.update_layout(
        height=300, margin=dict(t=20, b=20),
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig2, use_container_width=True)
