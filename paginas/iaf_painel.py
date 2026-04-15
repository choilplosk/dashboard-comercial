"""
Aba IAF — Instrumento de Avaliação de Franquia.
Tabela completa de classificação + painel de configuração editável com salvamento.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modulos.iaf import (
    calcular_iaf_base, carregar_config, salvar_config,
    CONFIG_PADRAO, CORES_IAF
)
from modulos.nps import carregar_nps
from modulos.calculos import fmt_num


# ── Helpers visuais ───────────────────────────────────────────────────────────

def _badge_classif(classif: str) -> str:
    cor = CORES_IAF.get(classif, '#6b7280')
    return (f'<span style="background:{cor};color:white;padding:3px 10px;'
            f'border-radius:12px;font-size:12px;font-weight:600;">{classif}</span>')


def _barra_progresso(pct: float, classif: str) -> str:
    cor = CORES_IAF.get(classif, '#6b7280')
    pct_clip = min(pct, 100)
    return f"""
    <div style="background:#e2e8f0;border-radius:6px;height:8px;margin-top:4px;">
        <div style="background:{cor};width:{pct_clip}%;height:8px;border-radius:6px;
                    transition:width 0.3s;"></div>
    </div>
    <div style="font-size:11px;color:#64748b;margin-top:2px;">{pct:.1f}%</div>
    """


# ── Tabela IAF ────────────────────────────────────────────────────────────────

def _render_tabela(base_iaf: pd.DataFrame):
    st.markdown("### Classificação da Equipe")

    # Exclui gerentes e sem meta
    df = base_iaf[
        ~base_iaf['classificacao'].isin(['Gerente', 'Sem meta'])
    ].copy()

    if df.empty:
        st.info("Nenhum dado disponível.")
        return

    # Ordena por pontuação decrescente
    df = df.sort_values('pct_iaf', ascending=False).reset_index(drop=True)

    # ── Resumo de classificações ──────────────────────────────────────────────
    ordem = ['Diamante', 'Ouro', 'Prata', 'Bronze', 'Não classificado']
    contagem = df['classificacao'].value_counts()

    cols_res = st.columns(len(ordem))
    for i, classif in enumerate(ordem):
        qtd = contagem.get(classif, 0)
        cor = CORES_IAF.get(classif, '#6b7280')
        with cols_res[i]:
            st.markdown(f"""
            <div style="background:{cor}22;border:1px solid {cor}66;border-radius:10px;
                        padding:12px;text-align:center;">
                <div style="font-size:24px;font-weight:700;color:{cor};">{qtd}</div>
                <div style="font-size:12px;color:{cor};font-weight:600;">{classif}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabela detalhada ──────────────────────────────────────────────────────
    # Filtro por PDV
    pdvs_disp = sorted(df['pdv'].dropna().unique().tolist())
    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        pdv_filtro = st.selectbox(
            "Filtrar PDV", ["Todos"] + [str(p) for p in pdvs_disp],
            key="iaf_pdv_filtro"
        )
    with col_f2:
        classif_filtro = st.multiselect(
            "Filtrar classificação", ordem,
            default=ordem, key="iaf_classif_filtro"
        )

    df_view = df.copy()
    if pdv_filtro != "Todos":
        df_view = df_view[df_view['pdv'].astype(str) == pdv_filtro]
    if classif_filtro:
        df_view = df_view[df_view['classificacao'].isin(classif_filtro)]

    # Monta tabela de exibição
    linhas = []
    for _, row in df_view.iterrows():
        pts     = row.get('pontos', 0) or 0
        pts_max = row.get('pontos_possiveis', 310) or 310
        pct     = row.get('pct_iaf', 0) or 0
        classif = row.get('classificacao', 'Não classificado')
        falta   = row.get('falta_pontos', 0) or 0
        entregas = row.get('entregas', 0) or 0
        total_ind = row.get('total_indicadores', 9) or 9

        cor = CORES_IAF.get(classif, '#6b7280')
        badge = (f'<span style="background:{cor};color:white;padding:2px 8px;'
                 f'border-radius:10px;font-size:11px;">{classif}</span>')

        linhas.append({
            'Consultor':      row.get('consultor', '—'),
            'PDV':            str(row.get('pdv', '—')),
            'Pontos':         f"{pts:.0f} / {pts_max:.0f}",
            '% IAF':          f"{pct:.1f}%",
            'Classificação':  classif,
            'Entregas':       f"{int(entregas)} de {int(total_ind)}",
            'Falta p/ subir': f"{falta:.0f} pts" if falta > 0 else "—",
        })

    if linhas:
        df_tabela = pd.DataFrame(linhas)
        st.dataframe(
            df_tabela,
            use_container_width=True,
            hide_index=True,
            height=min(700, len(linhas) * 38 + 50),
            column_config={
                'Classificação': st.column_config.TextColumn('Classificação', width='medium'),
                '% IAF': st.column_config.TextColumn('% IAF', width='small'),
                'Pontos': st.column_config.TextColumn('Pontos', width='medium'),
            }
        )

    # ── Gráfico de distribuição ───────────────────────────────────────────────
    st.markdown("#### Distribuição de pontuação")
    fig = go.Figure()
    for classif in ordem:
        df_c = df_view[df_view['classificacao'] == classif]
        if df_c.empty:
            continue
        cor = CORES_IAF.get(classif, '#6b7280')
        fig.add_bar(
            name=classif,
            x=df_c['consultor'],
            y=df_c['pct_iaf'],
            marker_color=cor,
            text=df_c['pct_iaf'].apply(lambda v: f"{v:.1f}%"),
            textposition='outside',
        )

    # Linhas de faixa
    config = carregar_config()
    for faixa in config['faixas']:
        if faixa['min_pct'] > 0:
            fig.add_hline(
                y=faixa['min_pct'],
                line_dash='dot',
                line_color='#94a3b8',
                line_width=1,
                annotation_text=faixa['nome'],
                annotation_position='right',
                annotation_font_size=10,
            )

    fig.update_layout(
        height=420,
        margin=dict(t=20, b=20, r=80),
        yaxis=dict(title='% IAF', range=[0, 110]),
        xaxis=dict(tickangle=-30),
        barmode='group',
        showlegend=True,
        legend=dict(orientation='h', y=1.08),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Painel de configuração ────────────────────────────────────────────────────

# Colunas disponíveis na base para mapeamento
COLUNAS_DISPONIVEIS = [
    ('receita',            'Receita'),
    ('boleto_medio',       'Boleto Médio'),
    ('itens_por_boleto',   'Itens por Boleto'),
    ('preco_medio',        'Preço Médio'),
    ('pen_bt',             'Penetração BT'),
    ('pen_bp',             'Penetração BP'),
    ('pen_mobshop',        'Penetração Mobshop'),
    ('pen_boletos1',       'Penetração Boletos 1'),
    ('pen_fidelidade',     'Penetração Fidelidade'),
    ('resgate_fidelidade', 'Resgate Fidelidade'),
    ('conv_fluxo',         'Conversão Fluxo'),
    ('pen_facial',         'Penetração Facial'),
    ('pct_id_cliente_iaf', 'ID Cliente (% Válidos)'),
    ('servicos_real',      'Serviços'),
    ('treinamento_concluido', 'Treinamentos (concluído)'),
    ('nps_real',           'NPS (manual)'),
]
COLUNAS_META = [
    ('meta_receita',           'Meta Receita'),
    ('meta_boleto_medio',      'Meta Boleto Médio'),
    ('meta_itens_boleto',      'Meta Itens/Boleto'),
    ('meta_preco_medio',       'Meta Preço Médio'),
    ('meta_pen_bt',            'Meta Pen. BT'),
    ('meta_pen_bp',            'Meta Pen. BP'),
    ('meta_pen_mobshop',       'Meta Pen. Mobshop'),
    ('meta_pen_boletos1',      'Meta Pen. Boletos 1'),
    ('meta_pen_fidelidade',    'Meta Pen. Fidelidade'),
    ('meta_resgate_fidelidade','Meta Resgate Fidelidade'),
    ('meta_conv_fluxo',        'Meta Conv. Fluxo'),
    ('meta_pen_facial',        'Meta Pen. Facial'),
    ('meta_pct_id_cliente',    'Meta ID Cliente'),
    ('meta_servicos',          'Meta Serviços'),
    ('',                       '(sem meta — tudo ou nada)'),
]


def _render_configuracao():
    st.markdown("### ⚙️ Configuração do IAF")
    st.caption("Alterações são salvas permanentemente e refletem imediatamente na pontuação.")

    config = carregar_config()
    indicadores = config['indicadores']

    st.markdown("#### Indicadores e pesos")

    # Cabeçalho
    h1, h2, h3, h4, h5, h6 = st.columns([2.5, 1, 2, 2, 1.5, 0.8])
    h1.markdown("**Nome**")
    h2.markdown("**Pontos**")
    h3.markdown("**Coluna realizado**")
    h4.markdown("**Coluna meta**")
    h5.markdown("**Lógica**")
    h6.markdown("**Ação**")

    nomes_real  = {k: v for k, v in COLUNAS_DISPONIVEIS}
    nomes_meta  = {k: v for k, v in COLUNAS_META}
    opcoes_real = [k for k, _ in COLUNAS_DISPONIVEIS]
    opcoes_meta = [k for k, _ in COLUNAS_META]
    labels_real = [v for _, v in COLUNAS_DISPONIVEIS]
    labels_meta = [v for _, v in COLUNAS_META]

    indicadores_novos = []
    remover_ids = set()

    for ind in indicadores:
        c1, c2, c3, c4, c5, c6 = st.columns([2.5, 1, 2, 2, 1.5, 0.8])

        with c1:
            nome = st.text_input("", value=ind['nome'], key=f"iaf_nome_{ind['id']}",
                                  label_visibility='collapsed')
        with c2:
            pontos = st.number_input("", value=float(ind['pontos']), min_value=0.0,
                                      max_value=500.0, step=5.0,
                                      key=f"iaf_pts_{ind['id']}",
                                      label_visibility='collapsed')
        with c3:
            idx_real = opcoes_real.index(ind['coluna_real']) if ind['coluna_real'] in opcoes_real else 0
            col_real = st.selectbox("", labels_real, index=idx_real,
                                     key=f"iaf_real_{ind['id']}",
                                     label_visibility='collapsed')
            col_real_val = opcoes_real[labels_real.index(col_real)]

        with c4:
            col_meta_atual = ind.get('coluna_meta') or ''
            idx_meta = opcoes_meta.index(col_meta_atual) if col_meta_atual in opcoes_meta else len(opcoes_meta)-1
            col_meta = st.selectbox("", labels_meta, index=idx_meta,
                                     key=f"iaf_meta_{ind['id']}",
                                     label_visibility='collapsed')
            col_meta_val = opcoes_meta[labels_meta.index(col_meta)] or None

        with c5:
            logica_opcoes = ['padrao', 'tudo_ou_nada']
            logica_labels = ['Padrão (<95/95-100/≥100)', 'Tudo ou nada']
            idx_log = logica_opcoes.index(ind.get('logica', 'padrao'))
            logica = st.selectbox("", logica_labels, index=idx_log,
                                   key=f"iaf_log_{ind['id']}",
                                   label_visibility='collapsed')
            logica_val = logica_opcoes[logica_labels.index(logica)]

        with c6:
            if st.button("🗑️", key=f"iaf_del_{ind['id']}", help="Remover indicador"):
                remover_ids.add(ind['id'])

        if ind['id'] not in remover_ids:
            indicadores_novos.append({
                **ind,
                'nome':         nome,
                'pontos':       pontos,
                'coluna_real':  col_real_val,
                'coluna_meta':  col_meta_val,
                'logica':       logica_val,
            })

    # ── Adicionar novo indicador ──────────────────────────────────────────────
    st.divider()
    st.markdown("#### Adicionar indicador")
    a1, a2, a3, a4, a5, a6 = st.columns([2.5, 1, 2, 2, 1.5, 0.8])
    with a1: novo_nome  = st.text_input("Nome", placeholder="Ex: Ticket Médio", key="iaf_add_nome")
    with a2: novo_pts   = st.number_input("Pontos", value=10.0, min_value=0.0, max_value=500.0, step=5.0, key="iaf_add_pts")
    with a3:
        novo_real_lbl = st.selectbox("Coluna realizado", labels_real, key="iaf_add_real")
        novo_real_val = opcoes_real[labels_real.index(novo_real_lbl)]
    with a4:
        novo_meta_lbl = st.selectbox("Coluna meta", labels_meta, key="iaf_add_meta")
        novo_meta_val = opcoes_meta[labels_meta.index(novo_meta_lbl)] or None
    with a5:
        novo_log_lbl = st.selectbox("Lógica", logica_labels, key="iaf_add_log")
        novo_log_val = logica_opcoes[logica_labels.index(novo_log_lbl)]
    with a6:
        if st.button("➕ Adicionar", key="iaf_add_btn"):
            if novo_nome.strip():
                novo_id = novo_nome.lower().replace(' ', '_')[:20]
                indicadores_novos.append({
                    'id':          novo_id,
                    'nome':        novo_nome.strip(),
                    'pontos':      novo_pts,
                    'coluna_real': novo_real_val,
                    'coluna_meta': novo_meta_val,
                    'tipo':        'automatico',
                    'logica':      novo_log_val,
                })
                st.rerun()
            else:
                st.warning("Digite um nome para o indicador.")

    # ── Salvar configuração ───────────────────────────────────────────────────
    st.divider()
    total_pts = sum(ind['pontos'] for ind in indicadores_novos)
    st.markdown(f"**Total de pontos possíveis: {total_pts:.0f}**")

    if st.button("💾 Salvar configuração do IAF", type="primary", key="iaf_salvar"):
        nova_config = {**config, 'indicadores': indicadores_novos}
        salvar_config(nova_config)
        st.success("✅ Configuração salva! A pontuação foi recalculada.")
        st.rerun()

    # ── Reset para padrão ─────────────────────────────────────────────────────
    if st.button("↩️ Restaurar configuração padrão", key="iaf_reset"):
        salvar_config(CONFIG_PADRAO.copy())
        st.success("Configuração restaurada para o padrão.")
        st.rerun()


# ── Histórico IAF ────────────────────────────────────────────────────────────

def _render_historico():
    from modulos.historico import listar_snapshots, carregar_snapshot
    from modulos.nps import carregar_nps

    st.markdown("### 📅 Histórico de Classificações")
    st.caption("Evolução mensal do IAF por consultor, baseada nos snapshots salvos.")

    datas = listar_snapshots()
    if len(datas) < 1:
        st.info(
            "Nenhum snapshot salvo ainda. "
            "Carregue os arquivos e clique em 'Salvar snapshot de hoje' na barra lateral."
        )
        return

    # Carrega todos os snapshots e calcula IAF de cada um
    nps_por_pdv = carregar_nps()
    historico = []

    for data in datas:
        df_snap = carregar_snapshot(data)
        if df_snap is None or df_snap.empty:
            continue
        try:
            base_iaf = calcular_iaf_base(df_snap, nps_por_pdv)
            base_iaf = base_iaf[
                ~base_iaf['classificacao'].isin(['Gerente', 'Sem meta'])
            ].copy()
            base_iaf['data'] = data.strftime('%d/%m/%Y')
            base_iaf['data_ord'] = data
            historico.append(base_iaf[['consultor','pdv','data','data_ord',
                                        'pontos','pct_iaf','classificacao']])
        except Exception:
            continue

    if not historico:
        st.info("Snapshots encontrados mas sem dados suficientes para calcular o IAF.")
        return

    df_hist = pd.concat(historico, ignore_index=True)
    df_hist = df_hist.sort_values('data_ord')

    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        pdvs = ["Todos"] + sorted(df_hist['pdv'].dropna().astype(str).unique().tolist())
        pdv_h = st.selectbox("Filtrar PDV", pdvs, key="hist_pdv")
    with col2:
        consultores = sorted(df_hist['consultor'].dropna().unique().tolist())
        cons_h = st.multiselect("Filtrar consultores (vazio = todos)",
                                consultores, key="hist_cons")

    df_view = df_hist.copy()
    if pdv_h != "Todos":
        df_view = df_view[df_view['pdv'].astype(str) == pdv_h]
    if cons_h:
        df_view = df_view[df_view['consultor'].isin(cons_h)]

    if df_view.empty:
        st.info("Nenhum dado para os filtros selecionados.")
        return

    # ── Tabela pivot: consultores x datas ────────────────────────────────────
    st.markdown("#### Evolução de classificação")
    pivot = df_view.pivot_table(
        index='consultor', columns='data',
        values='classificacao', aggfunc='last'
    )
    # Ordena colunas cronologicamente
    datas_cols = sorted(df_view['data'].unique(),
                        key=lambda d: pd.to_datetime(d, dayfirst=True))
    pivot = pivot.reindex(columns=[c for c in datas_cols if c in pivot.columns])
    st.dataframe(pivot, use_container_width=True)

    # ── Gráfico de evolução % IAF ────────────────────────────────────────────
    st.markdown("#### Evolução do % IAF")
    fig = go.Figure()

    consultores_view = df_view['consultor'].unique()
    # Limita a 15 consultores para não poluir o gráfico
    if len(consultores_view) > 15:
        st.caption(f"Exibindo os 15 primeiros consultores. Use o filtro para ver outros.")
        consultores_view = consultores_view[:15]

    for cons in consultores_view:
        df_c = df_view[df_view['consultor']==cons].sort_values('data_ord')
        fig.add_scatter(
            x=df_c['data'], y=df_c['pct_iaf'],
            mode='lines+markers', name=cons,
            line=dict(width=2), marker=dict(size=6),
        )

    # Linhas de faixa
    from modulos.iaf import carregar_config as _cc
    for faixa in _cc()['faixas']:
        if faixa['min_pct'] > 0:
            fig.add_hline(
                y=faixa['min_pct'], line_dash='dot',
                line_color='#94a3b8', line_width=1,
                annotation_text=faixa['nome'],
                annotation_position='right',
                annotation_font_size=10,
            )

    fig.update_layout(
        height=420, margin=dict(t=20, b=20, r=100),
        yaxis=dict(title='% IAF', range=[0,110]),
        xaxis_title='Data do snapshot',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation='v', x=1.02, y=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Tabela de pontuação ao longo do tempo ─────────────────────────────────
    st.markdown("#### Pontuação por snapshot")
    pivot_pts = df_view.pivot_table(
        index='consultor', columns='data',
        values='pct_iaf', aggfunc='last'
    ).reindex(columns=[c for c in datas_cols if c in pivot.columns])
    pivot_pts = pivot_pts.applymap(lambda v: f"{v:.1f}%" if pd.notna(v) else "—")
    st.dataframe(pivot_pts, use_container_width=True)


# ── Render principal ──────────────────────────────────────────────────────────

def render(dados: dict):
    st.header("🎯 IAF — Instrumento de Avaliação de Franquia")

    base = dados.get('_base_calculada')
    if base is None:
        st.info("Carregue os arquivos para continuar.")
        return

    nps_por_pdv = carregar_nps()
    base_iaf = calcular_iaf_base(base, nps_por_pdv)

    if 'iaf_modo' not in st.session_state:
        st.session_state['iaf_modo'] = 'resultados'

    col1, col2, col3, col_esp = st.columns([1.2, 1.2, 1.2, 4])
    with col1:
        if st.button("📊 Resultados",
                     type="primary" if st.session_state['iaf_modo']=='resultados' else "secondary",
                     use_container_width=True, key="iaf_btn_res"):
            st.session_state['iaf_modo'] = 'resultados'
            st.rerun()
    with col2:
        if st.button("📅 Histórico",
                     type="primary" if st.session_state['iaf_modo']=='historico' else "secondary",
                     use_container_width=True, key="iaf_btn_hist"):
            st.session_state['iaf_modo'] = 'historico'
            st.rerun()
    with col3:
        if st.button("⚙️ Configuração",
                     type="primary" if st.session_state['iaf_modo']=='config' else "secondary",
                     use_container_width=True, key="iaf_btn_cfg"):
            st.session_state['iaf_modo'] = 'config'
            st.rerun()

    st.divider()

    modo = st.session_state['iaf_modo']
    if modo == 'resultados':
        _render_tabela(base_iaf)
    elif modo == 'historico':
        _render_historico()
    elif modo == 'config':
        _render_configuracao()
