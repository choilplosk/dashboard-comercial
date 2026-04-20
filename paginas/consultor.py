""
Aba Por Consultor.
Visão geral (tabela) e visão individual (scorecard para feedback).
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from modulos.calculos import (
    cor_indicador, cor_indicador_invertido, CORES, CORES_IAF,
    fmt_brl, fmt_pct, fmt_num, atingimento
)
from modulos.iaf import calcular_iaf_base, carregar_config
from modulos.nps import carregar_nps


# ── Helpers ───────────────────────────────────────────────────────────────────

def _semaforo(at, invertido=False):
    if at is None: return '⚪'
    cor = cor_indicador_invertido(at) if invertido else cor_indicador(at)
    return {'verde':'🟢','amarelo':'🟡','vermelho':'🔴','cinza':'⚪'}.get(cor,'⚪')


def _bg_fg(cor):
    return {
        'verde':    ('#dcfce7', '#166534'),
        'amarelo':  ('#fef9c3', '#854d0e'),
        'vermelho': ('#fee2e2', '#991b1b'),
        'cinza':    ('#f1f5f9', '#475569'),
    }.get(cor, ('#f1f5f9', '#475569'))


def _card(label, valor, meta=None, at=None, fmt_fn=None,
          iaf_peso=None, invertido=False):
    """Card de indicador com semáforo, badge IAF e suporte a lógica invertida."""
    fmt  = fmt_fn or (lambda v: fmt_num(v, 2))
    cor  = cor_indicador_invertido(at) if invertido else cor_indicador(at)
    bg, fg = _bg_fg(cor)

    val_str  = fmt(valor) if valor is not None else '—'
    meta_str = fmt(meta)  if meta  is not None else 's/ meta'
    at_str   = f"{at*100:.1f}%" if at is not None else '—'

    badge = (
        f'<span style="font-size:10px;background:#1e40af;color:white;'
        f'padding:1px 6px;border-radius:4px;margin-left:4px;">IAF {iaf_peso}</span>'
    ) if iaf_peso else ''

    st.markdown(f"""
    <div style="background:{bg};border-radius:10px;padding:12px 14px;margin-bottom:8px;">
        <div style="font-size:11px;color:{fg};font-weight:600;margin-bottom:3px;">
            {label}{badge}
        </div>
        <div style="font-size:20px;font-weight:700;color:{fg};">{val_str}</div>
        <div style="font-size:11px;color:{fg};opacity:0.85;">
            Meta: {meta_str} &nbsp;|&nbsp; x Meta: {at_str}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Render principal ──────────────────────────────────────────────────────────

def render(dados: dict, nps_por_pdv: dict):
    st.header("👤 Por Consultor")

    base = dados.get('_base_calculada')
    if base is None:
        st.info("Carregue os arquivos para continuar.")
        return

    # Pesos IAF
    pesos_iaf = {ind['id']: ind['pontos'] for ind in carregar_config().get('indicadores', [])}

    # Filtros
    col_f1, col_f2, col_f3 = st.columns([1.5, 2, 1.5])
    with col_f1:
        pdvs = sorted(base['pdv'].dropna().unique().tolist())
        pdv_sel = st.selectbox("PDV", ["Todos"] + [str(p) for p in pdvs], key="pdv_cons")
    with col_f2:
        modo = st.radio("Visualização", ["Visão Geral", "Consultor Individual"],
                        horizontal=True, key="modo_cons")

    df_filtrado = base.copy()
    if pdv_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado['pdv'].astype(str) == pdv_sel]

    is_ger = df_filtrado.get('is_gerente',
             pd.Series(False, index=df_filtrado.index)).fillna(False).astype(bool)
    df_consultores = df_filtrado[~is_ger]

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # VISÃO GERAL
    # ════════════════════════════════════════════════════════════════════════
    if modo == "Visão Geral":
        st.subheader(f"Todos os Consultores — PDV {pdv_sel}")

        with col_f3:
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

            def fat(at, sem=False, inv=False):
                if sem: return '⚪ s/ meta'
                return f"{_semaforo(at,inv)} {at*100:.1f}%" if at is not None else '⚪ n/e'

            linhas.append({
                '_rec':  row.get('receita', 0) or 0,
                '_at':   at_r or 0,
                '_bm':   row.get('boleto_medio', 0) or 0,
                '_sv':   row.get('servicos_real', 0) or 0,
                'Consultor':    row.get('consultor', '—'),
                'PDV':          str(row.get('pdv', '—')),
                'Receita':      fmt_brl(row.get('receita')),
                'x Meta Rec.':  fat(at_r, sem_meta),
                'Boleto Médio': fmt_brl(row.get('boleto_medio')),
                'x Meta BM':    fat(at_bm),
                'Itens/Boleto': fmt_num(row.get('itens_por_boleto'), 2),
                'x Meta Itens': fat(at_it),
                'Pen. BT':      f"{_semaforo(at_bt)} {fmt_pct(row.get('pen_bt'))}" if at_bt else '⚪ —',
                'Pen. BP':      f"{_semaforo(at_bp)} {fmt_pct(row.get('pen_bp'))}" if at_bp else '⚪ —',
                'Pen. Facial':  f"{_semaforo(at_fac)} {fmt_pct(row.get('pen_facial'))}" if at_fac else '⚪ —',
                'Serviços':     str(int(row.get('servicos_real') or 0)) if row.get('servicos_real') is not None and not pd.isna(row.get('servicos_real', float('nan'))) else 'n/e',
                'x Meta Serv.': fat(at_sv),
            })

        if not linhas:
            st.info("Nenhum consultor encontrado.")
            return

        df_tab = pd.DataFrame(linhas)
        col_ord = {'Consultor':'Consultor','Receita':'_rec','At. Receita':'_at',
                   'Boleto Médio':'_bm','Serviços':'_sv'}.get(ordenar_por,'Consultor')
        df_tab = df_tab.sort_values(col_ord, ascending=(ordenar_por=='Consultor'))

        cols_exib = ['Consultor','PDV','Receita','x Meta Rec.','Boleto Médio','x Meta BM',
                     'Itens/Boleto','x Meta Itens','Pen. BT','Pen. BP','Pen. Facial',
                     'Serviços','x Meta Serv.']
        st.dataframe(df_tab[cols_exib], use_container_width=True, hide_index=True,
                     height=min(600, len(linhas)*38+50))

    # ════════════════════════════════════════════════════════════════════════
    # VISÃO INDIVIDUAL
    # ════════════════════════════════════════════════════════════════════════
    else:
        lista = sorted(df_consultores['consultor'].dropna().unique().tolist())
        if not lista:
            st.info("Nenhum consultor encontrado.")
            return

        cons_sel = st.selectbox("Selecionar Consultor", lista, key="cons_ind")
        row = df_consultores[df_consultores['consultor'] == cons_sel].iloc[0]

        sem_meta = row.get('meta_receita') is None or pd.isna(row.get('meta_receita', float('nan')))
        pdv_cons = str(row.get('pdv', '—'))

        # Cabeçalho
        aviso_meta = '&nbsp;&nbsp;|&nbsp;&nbsp;⚠️ Sem meta cadastrada' if sem_meta else ''
        nome_safe = str(cons_sel).replace("'", "&#39;").replace('"', '&quot;')
        st.markdown(
            f'<div style="background:#1e40af;color:white;border-radius:12px;'
            f'padding:16px 20px;margin-bottom:16px;">'
            f'<div style="font-size:22px;font-weight:700;">{nome_safe}</div>'
            f'<div style="font-size:14px;opacity:0.85;">PDV {pdv_cons}{aviso_meta}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        if sem_meta:
            st.warning("Consultor sem meta cadastrada — atingimentos indisponíveis.")

        # ── Indicadores Principais ────────────────────────────────────────────
        st.subheader("Indicadores Principais")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            at = atingimento(row.get('receita'), row.get('meta_receita'))
            _card("💰 Receita",
                  row.get('receita'), row.get('meta_receita'), at,
                  fmt_fn=fmt_brl, iaf_peso=pesos_iaf.get('receita'))
        with c2:
            at = atingimento(row.get('boleto_medio'), row.get('meta_boleto_medio'))
            _card("🧾 Boleto Médio",
                  row.get('boleto_medio'), row.get('meta_boleto_medio'), at,
                  fmt_fn=fmt_brl)
        with c3:
            at = atingimento(row.get('itens_por_boleto'), row.get('meta_itens_boleto'))
            _card("📦 Itens/Boleto",
                  row.get('itens_por_boleto'), row.get('meta_itens_boleto'), at,
                  fmt_fn=lambda v: fmt_num(v, 2))
        with c4:
            at = atingimento(row.get('servicos_real'), row.get('meta_servicos'))
            _card("✂️ Serviços",
                  row.get('servicos_real'), row.get('meta_servicos'), at,
                  fmt_fn=lambda v: fmt_num(v, 0),
                  iaf_peso=pesos_iaf.get('servicos'))

        # ── Penetrações ───────────────────────────────────────────────────────
        st.subheader("Penetrações e Indicadores de Qualidade")
        c1, c2, c3 = st.columns(3)

        # (label, col_real, col_meta, fmt_fn, iaf_id, invertido)
        pens = [
            ("🔵 Pen. BT",      'pen_bt',            'meta_pen_bt',             fmt_pct,                None,                 False),
            ("🟣 Pen. BP",      'pen_bp',            'meta_pen_bp',             fmt_pct,                'pen_bp',             False),
            ("📱 Mobshop",      'pen_mobshop',       'meta_pen_mobshop',        fmt_pct,                None,                 False),
            ("1️⃣ Boletos 1",   'pen_boletos1',      'meta_pen_boletos1',       fmt_pct,                None,                 True),
            ("💛 Fidelidade",   'pen_fidelidade',    'meta_pen_fidelidade',     fmt_pct,                None,                 False),
            ("🔄 Resg. Fid.",   'resgate_fidelidade','meta_resgate_fidelidade', lambda v: f"{v:.1f}%",  'resgate_fidelidade', False),
            ("🌊 Conv. Fluxo",  'conv_fluxo',        'meta_conv_fluxo',         fmt_pct,                None,                 False),
            ("💄 Facial",       'pen_facial',        'meta_pen_facial',         fmt_pct,                'pen_facial',         False),
            ("🪪 ID Cliente",   'pct_id_cliente_iaf','meta_pct_id_cliente',     fmt_pct,                'id_cliente',         False),
        ]
        cols_pen = [c1, c2, c3]
        for i, (label, col_r, col_m, fmt_fn, iaf_id, inv) in enumerate(pens):
            real_v = row.get(col_r)
            meta_v = row.get(col_m)
            # Resgate: real já × 100, meta em decimal → converte meta para %
            if inv and meta_v is not None:
                try:
                    meta_v = float(meta_v) * 100
                except (TypeError, ValueError):
                    meta_v = None
            at = atingimento(real_v, meta_v)
            peso = pesos_iaf.get(iaf_id) if iaf_id else None
            with cols_pen[i % 3]:
                _card(label, real_v, meta_v, at,
                      fmt_fn=fmt_fn, iaf_peso=peso, invertido=inv)

        st.divider()

        # ── Radar ─────────────────────────────────────────────────────────────
        st.subheader("Radar de Atingimento")
        rotulos = ["Receita","BM","Itens","BT","BP","Facial","ID Cliente","Serviços"]
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
        vals = []
        for col_r, col_m in pares_radar:
            at = atingimento(row.get(col_r), row.get(col_m))
            vals.append(min(round(at*100, 1), 150) if at is not None else 0)

        vals_f = vals + [vals[0]]
        rots_f = rotulos + [rotulos[0]]

        fig = go.Figure()
        fig.add_scatterpolar(
            r=vals_f, theta=rots_f, fill='toself',
            fillcolor='rgba(30,64,175,0.15)',
            line=dict(color='#1e40af', width=2), name=cons_sel
        )
        fig.add_scatterpolar(
            r=[100]*len(rots_f), theta=rots_f, mode='lines',
            line=dict(color='#94a3b8', width=1, dash='dot'), name='Meta (100%)'
        )
        fig.update_layout(
            polar=dict(radialaxis=dict(range=[0,130], ticksuffix='%')),
            height=400, margin=dict(t=30,b=30),
            legend=dict(orientation='h', y=-0.1),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Scorecard IAF ──────────────────────────────────────────────────────
        st.divider()
        st.subheader("🎯 Scorecard IAF")

        if sem_meta:
            st.info("Cálculo IAF indisponível — consultor sem meta cadastrada.")
            return

        nps_por_pdv_atual = carregar_nps()
        base_iaf = calcular_iaf_base(
            df_filtrado[df_filtrado['consultor'] == cons_sel],
            nps_por_pdv_atual
        )
        if base_iaf.empty or base_iaf.iloc[0].get('pct_iaf') is None:
            st.info("Dados insuficientes para calcular o IAF.")
            return

        iaf    = base_iaf.iloc[0]
        pct    = iaf.get('pct_iaf', 0)
        pts    = iaf.get('pontos', 0)
        pts_max = iaf.get('pontos_possiveis', 310)
        classif = iaf.get('classificacao', 'Não classificado')
        falta   = iaf.get('falta_pontos', 0)
        entregas = iaf.get('entregas', 0)
        total_ind = iaf.get('total_indicadores', 9)
        cor_iaf = CORES_IAF.get(classif, '#6b7280')

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pontuação",     f"{pts:.1f} / {pts_max}")
        c2.metric("% IAF",         f"{pct:.1f}%")
        c3.metric("Entregas",      f"{entregas} de {total_ind}")
        c4.metric("Falta p/ subir", f"{falta:.1f} pts" if falta else "Nível máximo 🏆")

        st.markdown(
            f'<div style="background:{cor_iaf};color:white;border-radius:12px;'
            f'padding:14px 20px;text-align:center;margin:12px 0;">'
            f'<div style="font-size:13px;opacity:0.9;">Classificação Atual</div>'
            f'<div style="font-size:28px;font-weight:700;">{classif}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Barra de progresso
        config = carregar_config()
        faixas_ord = sorted(config['faixas'], key=lambda f: f['min_pct'])
        proxima = next((f for f in faixas_ord if f['min_pct'] > pct), None)
        if proxima:
            faixa_min = max((f['min_pct'] for f in faixas_ord if f['min_pct'] <= pct), default=0)
            prog = (pct - faixa_min) / (proxima['min_pct'] - faixa_min)
            st.progress(min(prog, 1.0))
            st.caption(f"{pct:.1f}% → próxima faixa: {proxima['min_pct']}% ({proxima['nome']})")
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
                    tp = row.get('treinamento_pct')
                    at_str = f"{float(tp)*100:.0f}%" if tp is not None and not pd.isna(tp) else "n/e"
                else:
                    at_str = "n/e"
                pts_str = f"{det['pontos']:.0f}/{det['pontos_max']:.0f} pts"
                with cols_det[i % 2]:
                    st.markdown(
                        f"{emoji} **{det['nome']}** &nbsp;|&nbsp; "
                        f"x Meta: {at_str} &nbsp;|&nbsp; {pts_str}"
                    )
