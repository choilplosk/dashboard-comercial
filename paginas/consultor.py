"""
Aba 3 — Por Consultor.
Duas visualizações:
  - Visão Geral: tabela com todos os consultores do PDV
  - Visão Individual: scorecard completo de um consultor (para sessão de feedback)
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from modulos.calculos import (
    cor_indicador, CORES, CORES_IAF,
    fmt_brl, fmt_pct, fmt_num, atingimento
)
from modulos.iaf import calcular_iaf_base, carregar_config


def _semaforo(at_decimal):
    if at_decimal is None:
        return '⚪'
    cor = cor_indicador(at_decimal)
    return {'verde': '🟢', 'amarelo': '🟡', 'vermelho': '🔴', 'cinza': '⚪'}.get(cor, '⚪')


def _bg_fg(cor: str):
    return {
        'verde':    ('#dcfce7', '#166534'),
        'amarelo':  ('#fef9c3', '#854d0e'),
        'vermelho': ('#fee2e2', '#991b1b'),
        'cinza':    ('#f3f4f6', '#374151'),
    }.get(cor, ('#f3f4f6', '#374151'))


def _card(label, valor, meta=None, at=None, fmt_fn=None):
    fmt = fmt_fn or (lambda v: fmt_num(v, 2))
    cor = cor_indicador(at)
    bg, fg = _bg_fg(cor)
    meta_str = fmt(meta) if meta is not None else "—"
    at_str = f"{at*100:.1f}%" if at is not None else "—"
    st.markdown(f"""
    <div style="background:{bg};border-radius:10px;padding:12px 14px;margin-bottom:8px;">
        <div style="font-size:11px;color:{fg};font-weight:600;">{label}</div>
        <div style="font-size:20px;font-weight:700;color:{fg};">{fmt(valor) if valor is not None else '—'}</div>
        <div style="font-size:11px;color:{fg};opacity:0.85;">Meta: {meta_str} &nbsp;|&nbsp; {at_str}</div>
    </div>
    """, unsafe_allow_html=True)


def render(dados: dict, nps_por_pdv: dict):
    st.header("👤 Por Consultor")

    base = dados.get('_base_calculada')
    if base is None:
        st.info("Carregue os arquivos para continuar.")
        return

    # ── Seletores ─────────────────────────────────────────────────────────────
    col_filtro1, col_filtro2, col_filtro3 = st.columns([1.5, 2, 1.5])

    with col_filtro1:
        pdvs = sorted(base['pdv'].dropna().unique().tolist())
        pdv_sel = st.selectbox("PDV", ["Todos"] + [str(p) for p in pdvs], key="pdv_cons")

    df_filtrado = base.copy()
    if pdv_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado['pdv'].astype(str) == pdv_sel]

    # Exclui gerentes da seleção de consultor
    df_consultores = df_filtrado[
        ~(df_filtrado.get('is_gerente', pd.Series(False, index=df_filtrado.index)).fillna(False).astype(bool))
    ]

    with col_filtro2:
        modo = st.radio("Visualização", ["Visão Geral", "Consultor Individual"],
                        horizontal=True, key="modo_cons")

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # VISÃO GERAL — tabela de todos os consultores
    # ════════════════════════════════════════════════════════════════════════
    if modo == "Visão Geral":
        st.subheader(f"Todos os Consultores — PDV {pdv_sel}")

        with col_filtro3:
            ordenar_por = st.selectbox("Ordenar por", [
                "Consultor", "Receita", "At. Receita", "Boleto Médio", "Serviços"
            ], key="ord_geral")

        linhas = []
        for _, row in df_consultores.iterrows():
            at_r   = atingimento(row.get('receita'),          row.get('meta_receita'))
            at_bm  = atingimento(row.get('boleto_medio'),     row.get('meta_boleto_medio'))
            at_it  = atingimento(row.get('itens_por_boleto'), row.get('meta_itens_boleto'))
            at_bt  = atingimento(row.get('pen_bt'),           row.get('meta_pen_bt'))
            at_bp  = atingimento(row.get('pen_bp'),           row.get('meta_pen_bp'))
            at_fac = atingimento(row.get('pen_facial'),       row.get('meta_pen_facial'))
            at_sv  = atingimento(row.get('servicos_real'),    row.get('meta_servicos'))

            sem_meta = row.get('meta_receita') is None or pd.isna(row.get('meta_receita', float('nan')))

            linhas.append({
                '_receita_raw':  row.get('receita', 0) or 0,
                '_at_raw':       at_r or 0,
                '_bm_raw':       row.get('boleto_medio', 0) or 0,
                '_sv_raw':       row.get('servicos_real', 0) or 0,
                'Consultor':     row.get('consultor', '—'),
                'PDV':           str(row.get('pdv', '—')),
                'Receita':       fmt_brl(row.get('receita')),
                'x Meta Rec.':   f"{_semaforo(at_r)} {at_r*100:.1f}%" if at_r else ('⚪ s/ meta' if sem_meta else '⚪ n/e'),
                'Boleto Médio':  fmt_brl(row.get('boleto_medio')),
                'x Meta BM':        f"{_semaforo(at_bm)} {at_bm*100:.1f}%" if at_bm else "⚪ —",
                'Itens/Boleto':  fmt_num(row.get('itens_por_boleto'), 2),
                'x Meta Itens':     f"{_semaforo(at_it)} {at_it*100:.1f}%" if at_it else "⚪ —",
                'Pen. BT':       f"{_semaforo(at_bt)} {fmt_pct(row.get('pen_bt'))}" if at_bt else "⚪ —",
                'Pen. BP':       f"{_semaforo(at_bp)} {fmt_pct(row.get('pen_bp'))}" if at_bp else "⚪ —",
                'Pen. Facial':   f"{_semaforo(at_fac)} {fmt_pct(row.get('pen_facial'))}" if at_fac else "⚪ —",
                'Serviços':      fmt_num(row.get('servicos_real'), 0) if row.get('servicos_real') is not None else "—",
                'x Meta Serv.':     f"{_semaforo(at_sv)} {at_sv*100:.1f}%" if at_sv else "⚪ —",
            })

        if not linhas:
            st.info("Nenhum consultor encontrado para o filtro selecionado.")
            return

        df_tabela = pd.DataFrame(linhas)

        col_ord_map = {
            "Consultor":   "Consultor",
            "Receita":     "_receita_raw",
            "At. Receita": "_at_raw",
            "Boleto Médio":"_bm_raw",
            "Serviços":    "_sv_raw",
        }
        df_tabela = df_tabela.sort_values(
            col_ord_map.get(ordenar_por, "Consultor"),
            ascending=(ordenar_por == "Consultor")
        )

        colunas_exibir = ['Consultor', 'PDV', 'Receita', 'x Meta Rec.',
                          'Boleto Médio', 'x Meta BM', 'Itens/Boleto', 'x Meta Itens',
                          'Pen. BT', 'Pen. BP', 'Pen. Facial', 'Serviços', 'x Meta Serv.']
        st.dataframe(
            df_tabela[colunas_exibir],
            use_container_width=True,
            hide_index=True,
            height=min(600, len(linhas) * 38 + 50)
        )

    # ════════════════════════════════════════════════════════════════════════
    # VISÃO INDIVIDUAL — scorecard para sessão de feedback
    # ════════════════════════════════════════════════════════════════════════
    else:
        consultores_lista = sorted(df_consultores['consultor'].dropna().unique().tolist())
        if not consultores_lista:
            st.info("Nenhum consultor encontrado.")
            return

        cons_sel = st.selectbox("Selecionar Consultor", consultores_lista, key="cons_ind")
        row = df_consultores[df_consultores['consultor'] == cons_sel].iloc[0]

        sem_meta = row.get('meta_receita') is None or pd.isna(row.get('meta_receita', float('nan')))

        # Cabeçalho
        pdv_cons = str(row.get('pdv', '—'))
        st.markdown(f"""
        <div style="background:#1e40af;color:white;border-radius:12px;padding:16px 20px;margin-bottom:16px;">
            <div style="font-size:22px;font-weight:700;">{cons_sel}</div>
            <div style="font-size:14px;opacity:0.85;">PDV {pdv_cons}
            {'&nbsp;&nbsp;|&nbsp;&nbsp;⚠️ Sem meta cadastrada' if sem_meta else ''}</div>
        </div>
        """, unsafe_allow_html=True)

        if sem_meta:
            st.warning("Este consultor não possui meta cadastrada. Os cálculos de atingimento não estão disponíveis.")

        st.subheader("Indicadores Principais")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            at = atingimento(row.get('receita'), row.get('meta_receita'))
            _card("💰 Receita", row.get('receita'), row.get('meta_receita'), at, fmt_brl)
        with c2:
            at = atingimento(row.get('boleto_medio'), row.get('meta_boleto_medio'))
            _card("🧾 Boleto Médio", row.get('boleto_medio'), row.get('meta_boleto_medio'), at, fmt_brl)
        with c3:
            at = atingimento(row.get('itens_por_boleto'), row.get('meta_itens_boleto'))
            _card("📦 Itens/Boleto", row.get('itens_por_boleto'), row.get('meta_itens_boleto'), at,
                  lambda v: fmt_num(v, 2))
        with c4:
            at = atingimento(row.get('servicos_real'), row.get('meta_servicos'))
            _card("✂️ Serviços", row.get('servicos_real'), row.get('meta_servicos'), at,
                  lambda v: fmt_num(v, 0))

        st.subheader("Penetrações e Indicadores de Qualidade")
        c1, c2, c3 = st.columns(3)
        pens = [
            ("🔵 Pen. BT",       'pen_bt',            'meta_pen_bt',            fmt_pct),
            ("🟣 Pen. BP",       'pen_bp',            'meta_pen_bp',            fmt_pct),
            ("📱 Mobshop",       'pen_mobshop',       'meta_pen_mobshop',       fmt_pct),
            ("1️⃣  Boletos 1",    'pen_boletos1',      'meta_pen_boletos1',      fmt_pct),
            ("💛 Fidelidade",    'pen_fidelidade',    'meta_pen_fidelidade',    fmt_pct),
            ("🔄 Resgate Fid.",  'resgate_fidelidade','meta_resgate_fidelidade', lambda v: fmt_num(v, 1)),
            ("🌊 Conv. Fluxo",   'conv_fluxo',        'meta_conv_fluxo',        fmt_pct),
            ("💄 Facial",        'pen_facial',        'meta_pen_facial',        fmt_pct),
            ("🪪 ID Cliente",    'pct_id_cliente_iaf','meta_pct_id_cliente',    fmt_pct),
        ]
        cols_pen = [c1, c2, c3]
        for i, (label, col_r, col_m, fmt_fn) in enumerate(pens):
            at = atingimento(row.get(col_r), row.get(col_m))
            with cols_pen[i % 3]:
                _card(label, row.get(col_r), row.get(col_m), at, fmt_fn)

        st.divider()

        # ── Radar de atingimento ─────────────────────────────────────────────
        st.subheader("Radar de Atingimento")

        rotulos = ["Receita", "BM", "Itens", "BT", "BP", "Facial", "ID Cliente", "Serviços"]
        pares_radar = [
            ('receita',           'meta_receita'),
            ('boleto_medio',      'meta_boleto_medio'),
            ('itens_por_boleto',  'meta_itens_boleto'),
            ('pen_bt',            'meta_pen_bt'),
            ('pen_bp',            'meta_pen_bp'),
            ('pen_facial',        'meta_pen_facial'),
            ('pct_id_cliente_iaf','meta_pct_id_cliente'),
            ('servicos_real',     'meta_servicos'),
        ]
        valores_radar = []
        for col_r, col_m in pares_radar:
            at = atingimento(row.get(col_r), row.get(col_m))
            valores_radar.append(min(round(at * 100, 1), 150) if at is not None else 0)

        vals_fechados = valores_radar + [valores_radar[0]]
        rots_fechados = rotulos + [rotulos[0]]

        fig_radar = go.Figure()
        fig_radar.add_scatterpolar(
            r=vals_fechados, theta=rots_fechados,
            fill='toself', fillcolor='rgba(30,64,175,0.15)',
            line=dict(color='#1e40af', width=2),
            name=cons_sel
        )
        fig_radar.add_scatterpolar(
            r=[100] * len(rots_fechados), theta=rots_fechados,
            mode='lines',
            line=dict(color='#94a3b8', width=1, dash='dot'),
            name='Meta (100%)'
        )
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(range=[0, 130], ticksuffix='%')),
            height=400, margin=dict(t=30, b=30),
            showlegend=True,
            legend=dict(orientation='h', y=-0.1),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # ── Scorecard IAF ────────────────────────────────────────────────────
        st.divider()
        st.subheader("🎯 Scorecard IAF")

        if sem_meta:
            st.info("Cálculo IAF indisponível — consultor sem meta cadastrada.")
            return

        base_iaf = calcular_iaf_base(
            df_filtrado[df_filtrado['consultor'] == cons_sel],
            nps_por_pdv
        )
        if base_iaf.empty or base_iaf.iloc[0].get('pct_iaf') is None:
            st.info("Dados insuficientes para calcular o IAF.")
            return

        iaf = base_iaf.iloc[0]
        pct  = iaf.get('pct_iaf', 0)
        pts  = iaf.get('pontos', 0)
        pts_max = iaf.get('pontos_possiveis', 310)
        classif = iaf.get('classificacao', 'Não classificado')
        falta   = iaf.get('falta_pontos', 0)
        entregas = iaf.get('entregas', 0)
        total_ind = iaf.get('total_indicadores', 9)
        cor_iaf = CORES_IAF.get(classif, '#6b7280')

        col_iaf1, col_iaf2, col_iaf3, col_iaf4 = st.columns(4)
        col_iaf1.metric("Pontuação", f"{pts:.1f} / {pts_max}")
        col_iaf2.metric("% IAF", f"{pct:.1f}%")
        col_iaf3.metric("Entregas", f"{entregas} de {total_ind}")
        col_iaf4.metric("Falta para subir", f"{falta:.1f} pts" if falta else "Nível máximo 🏆")

        # Badge de classificação
        st.markdown(f"""
        <div style="background:{cor_iaf};color:white;border-radius:12px;
                    padding:14px 20px;text-align:center;margin:12px 0;">
            <div style="font-size:13px;opacity:0.9;">Classificação Atual</div>
            <div style="font-size:28px;font-weight:700;">{classif}</div>
        </div>
        """, unsafe_allow_html=True)

        # Barra de progresso
        st.markdown("**Progresso para próxima faixa**")
        config = carregar_config()
        faixas_ord = sorted(config['faixas'], key=lambda f: f['min_pct'])
        proxima = next((f for f in faixas_ord if f['min_pct'] > pct), None)
        if proxima:
            faixa_atual_min = max((f['min_pct'] for f in faixas_ord if f['min_pct'] <= pct), default=0)
            progresso = (pct - faixa_atual_min) / (proxima['min_pct'] - faixa_atual_min)
            st.progress(min(progresso, 1.0))
            st.caption(f"{pct:.1f}% → meta: {proxima['min_pct']}% ({proxima['nome']})")
        else:
            st.progress(1.0)
            st.caption("💎 Classificação máxima atingida!")

        # Detalhamento por indicador
        st.markdown("**Detalhamento dos indicadores IAF**")
        detalhes = iaf.get('detalhes', [])
        if detalhes:
            cols_det = st.columns(2)
            for i, det in enumerate(detalhes):
                emoji = "🟢" if det['atingido'] else ("🟡" if det['parcial'] else "🔴")
                if det.get('atingimento') is not None:
                    at_str = f"{det['atingimento']*100:.1f}%"
                elif det.get('id') == 'treinamentos':
                    trein_pct = row.get('treinamento_pct')
                    at_str = f"{float(trein_pct)*100:.0f}%" if trein_pct is not None and not pd.isna(trein_pct) else "n/e"
                else:
                    at_str = "n/e"
                pts_str = f"{det['pontos']:.0f}/{det['pontos_max']:.0f} pts"
                with cols_det[i % 2]:
                    st.markdown(
                        f"{emoji} **{det['nome']}** &nbsp;|&nbsp; "
                        f"x Meta: {at_str} &nbsp;|&nbsp; {pts_str}"
                    )
