"""
Aba — Por PDV.
Botões de seleção, todos os indicadores com marcador IAF,
x LY nos indicadores principais, NPS em Configurações.
"""

import streamlit as st
import pandas as pd
import math
from modulos.calculos import (
    atingimento, cor_indicador, cor_indicador_invertido,
    fmt_brl, fmt_pct, fmt_num
)
from modulos.nps import carregar_nps, salvar_nps
from modulos.supabase_db import salvar_nps_supabase
from modulos.iaf import carregar_config


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_nan(v) -> bool:
    try: return math.isnan(float(v))
    except: return False

def _fmt_inteiro(v) -> str:
    if v is None or _is_nan(v): return 'n/e'
    try: return str(int(float(v)))
    except: return 'n/e'

def _fmt_val(v, tipo='num', casas=2) -> str:
    if v is None or _is_nan(v): return 'n/e'
    if v == 0:
        if tipo == 'brl': return 'R$ 0,00'
        if tipo == 'pct': return '0,0%'
        return '0'
    if tipo == 'brl': return fmt_brl(v)
    if tipo == 'pct': return fmt_pct(v)
    return fmt_num(v, casas)

def _fmt_ly(v) -> str:
    """Formata variação vs LY em percentual com sinal."""
    if v is None or _is_nan(v) or v == '-': return 'n/e'
    try:
        pct = float(v) * 100
        sinal = '+' if pct >= 0 else ''
        return f"{sinal}{pct:.1f}%"
    except: return 'n/e'

def _bg_fg(cor):
    return {
        'verde':    ('#dcfce7', '#166534'),
        'amarelo':  ('#fef9c3', '#854d0e'),
        'vermelho': ('#fee2e2', '#991b1b'),
        'cinza':    ('#f1f5f9', '#475569'),
    }.get(cor, ('#f1f5f9', '#475569'))

def _semaforo(at):
    if at is None: return '⚪'
    return {'verde':'🟢','amarelo':'🟡','vermelho':'🔴','cinza':'⚪'}.get(cor_indicador(at),'⚪')

def _pesos_iaf() -> dict:
    config = carregar_config()
    return {ind['id']: ind['pontos'] for ind in config.get('indicadores', [])}


# ── Card com x LY ─────────────────────────────────────────────────────────────

def _card_com_ly(label, real, meta, ly=None, iaf_peso=None, tipo='num', casas=2, invertido=False):
    """Card de indicador com meta, x Meta e x LY."""
    if invertido:
        at = atingimento(real, meta)
        cor = cor_indicador_invertido(at) if at is not None else 'cinza'
    else:
        at = atingimento(real, meta) if (real is not None and not _is_nan(real)
                                         and meta is not None and not _is_nan(meta)) else None
        cor = cor_indicador(at) if at is not None else 'cinza'

    real_str = _fmt_val(real, tipo, casas) if real is not None and not _is_nan(real) else 'n/e'

    if meta is None or _is_nan(meta):
        meta_str, at_str = 's/ meta', 's/ meta'
        cor = 'cinza'
    else:
        meta_str = _fmt_val(meta, tipo, casas)
        at_str = f"{at*100:.1f}%" if at is not None else 'n/e'

    ly_str = _fmt_ly(ly) if ly is not None else None
    ly_cor = '#166534' if ly is not None and not _is_nan(ly) and float(ly) >= 0 else '#991b1b'

    bg, fg = _bg_fg(cor)
    badge = (f'<span style="font-size:10px;background:#1e40af;color:white;'
             f'padding:1px 6px;border-radius:4px;margin-left:4px;">IAF {iaf_peso}</span>'
             ) if iaf_peso else ''

    ly_html = ''
    if ly_str and ly_str != 'n/e':
        ly_html = (f'<span style="font-size:11px;color:{ly_cor};font-weight:600;">'
                   f'x LY: {ly_str}</span>')

    st.markdown(f"""
    <div style="background:{bg};border-radius:10px;padding:12px 14px;
                margin-bottom:8px;min-height:90px;">
        <div style="font-size:11px;color:{fg};font-weight:600;margin-bottom:3px;">
            {label}{badge}
        </div>
        <div style="font-size:20px;font-weight:700;color:{fg};">{real_str}</div>
        <div style="font-size:11px;color:{fg};opacity:0.85;">
            Meta: {meta_str} &nbsp;|&nbsp; x Meta: {at_str}
        </div>
        <div style="margin-top:2px;">{ly_html}</div>
    </div>
    """, unsafe_allow_html=True)


# ── Card simples (sem x LY) ───────────────────────────────────────────────────

def _card(label, real, meta, iaf_peso=None, tipo='num', casas=2, invertido=False):
    _card_com_ly(label, real, meta, ly=None,
                 iaf_peso=iaf_peso, tipo=tipo, casas=casas, invertido=invertido)


# ── Linha da tabela de consultores ────────────────────────────────────────────

def _linha_tabela(row) -> dict:
    def get(col): return row.get(col)

    at_r  = atingimento(get('receita'),          get('meta_receita'))
    at_bm = atingimento(get('boleto_medio'),      get('meta_boleto_medio'))
    at_it = atingimento(get('itens_por_boleto'),  get('meta_itens_boleto'))
    at_sv = atingimento(get('servicos_real'),      get('meta_servicos'))
    at_bt = atingimento(get('pen_bt'),             get('meta_pen_bt'))
    at_bp = atingimento(get('pen_bp'),             get('meta_pen_bp'))
    at_fc = atingimento(get('pen_facial'),         get('meta_pen_facial'))
    at_id = atingimento(get('pct_id_cliente_iaf'), get('meta_pct_id_cliente'))
    # Resgate Fidelidade — cor invertida
    at_rf = atingimento(get('resgate_fidelidade'), get('meta_resgate_fidelidade'))

    sem_meta = get('meta_receita') is None or _is_nan(get('meta_receita') or float('nan'))
    trein_pct = get('treinamento_pct')
    trein_str = f"{float(trein_pct)*100:.0f}%" if trein_pct is not None and not _is_nan(trein_pct) else 'n/e'

    def s(at, inv=False):
        if at is None: return '⚪'
        cor = cor_indicador_invertido(at) if inv else cor_indicador(at)
        return {'verde':'🟢','amarelo':'🟡','vermelho':'🔴','cinza':'⚪'}.get(cor,'⚪')

    def fmt_at(at, sem=False, inv=False):
        if sem: return '⚪ s/ meta'
        return f"{s(at,inv)} {at*100:.1f}%" if at is not None else '⚪ n/e'

    # Resgate Fidelidade: valor já vem × 100 do arquivo PDV
    rf_real = get('resgate_fidelidade')
    rf_str = f"{rf_real:.1f}%" if rf_real is not None and not _is_nan(rf_real) else 'n/e'
    rf_meta = get('meta_resgate_fidelidade')
    rf_meta_str = f"{rf_meta*100:.1f}%" if rf_meta is not None and not _is_nan(rf_meta) else 's/ meta'

    return {
        'Consultor':       row.get('consultor', '—'),
        'Receita':         _fmt_val(get('receita'), 'brl'),
        'x Meta Rec.':     fmt_at(at_r, sem_meta),
        'Boleto Médio':    _fmt_val(get('boleto_medio'), 'brl'),
        'x Meta BM':       fmt_at(at_bm),
        'Itens/Boleto':    _fmt_val(get('itens_por_boleto'), 'num', 2),
        'x Meta Itens':    fmt_at(at_it),
        'Pen. BT':         _fmt_val(get('pen_bt'), 'pct'),
        'x Meta BT':       fmt_at(at_bt),
        'Pen. BP':         _fmt_val(get('pen_bp'), 'pct'),
        'x Meta BP':       fmt_at(at_bp),
        'Facial':          _fmt_val(get('pen_facial'), 'pct'),
        'x Meta Facial':   fmt_at(at_fc),
        'ID Cliente':      _fmt_val(get('pct_id_cliente_iaf'), 'pct'),
        'x Meta ID':       fmt_at(at_id),
        'Resg. Fid.':      rf_str,
        'x Meta RF':       fmt_at(at_rf, inv=True),
        'Serviços':        _fmt_inteiro(get('servicos_real')),
        'x Meta Serv.':    fmt_at(at_sv),
        'Treinamento':     trein_str,
    }


# ── Render principal ──────────────────────────────────────────────────────────

def render(dados: dict):
    st.header("🏪 Resultado por PDV")

    base = dados.get('_base_calculada')
    if base is None:
        st.info("Carregue os arquivos para continuar.")
        return

    metas  = dados.get('metas', pd.DataFrame())
    pdvs   = sorted(base['pdv'].dropna().unique().tolist())
    if not pdvs:
        st.warning("Nenhum PDV encontrado.")
        return

    # ── Botões de PDV ─────────────────────────────────────────────────────────
    if 'pdv_selecionado' not in st.session_state or \
       st.session_state['pdv_selecionado'] not in pdvs:
        st.session_state['pdv_selecionado'] = pdvs[0]

    st.markdown("**Selecionar PDV:**")
    cols_btn = st.columns(len(pdvs))
    for i, pdv in enumerate(pdvs):
        ativo = st.session_state['pdv_selecionado'] == pdv
        with cols_btn[i]:
            if st.button(str(pdv), key=f"btn_pdv_{pdv}",
                         use_container_width=True,
                         type="primary" if ativo else "secondary"):
                st.session_state['pdv_selecionado'] = pdv
                st.rerun()

    pdv_sel = st.session_state['pdv_selecionado']
    pdv_int = int(pdv_sel)
    st.divider()

    # ── Pesos IAF ─────────────────────────────────────────────────────────────
    pesos = _pesos_iaf()

    # ── Helpers de meta ───────────────────────────────────────────────────────
    def meta_media(col):
        if metas.empty or col not in metas.columns: return None
        v = pd.to_numeric(metas[metas['pdv']==pdv_int][col], errors='coerce').mean()
        return None if pd.isna(v) else v

    def meta_soma(col):
        if metas.empty or col not in metas.columns: return None
        v = pd.to_numeric(metas[metas['pdv']==pdv_int][col], errors='coerce').sum()
        return None if v == 0 else v

    # ── Dados do arquivo PDV ──────────────────────────────────────────────────
    df_pdv_dados = dados.get('pdv')
    pdv_row = None
    if df_pdv_dados is not None and not df_pdv_dados.empty:
        rows = df_pdv_dados[df_pdv_dados['pdv'] == pdv_int]
        if not rows.empty:
            pdv_row = rows.iloc[0]

    def get_pdv(col):
        if pdv_row is not None and col in pdv_row.index:
            v = pdv_row[col]
            return None if (isinstance(v, float) and pd.isna(v)) or v == '-' else v
        return None

    def get_base_media(col):
        """Busca média de uma coluna da base calculada para o PDV selecionado."""
        df_pdv_calc = base[base['pdv'] == pdv_int].copy()
        is_ger = df_pdv_calc['is_gerente'].fillna(False).astype(bool) if 'is_gerente' in df_pdv_calc.columns else pd.Series(False, index=df_pdv_calc.index)
        df_pdv_calc = df_pdv_calc[~is_ger]
        if col not in df_pdv_calc.columns:
            return None
        vals = pd.to_numeric(df_pdv_calc[col], errors='coerce')
        vals = vals[vals > 0]  # exclui zeros
        return vals.mean() if not vals.empty else None

    nps_dict = carregar_nps()
    nps_val  = nps_dict.get(str(pdv_int))

    # ── Bloco 1: Indicadores Comerciais ──────────────────────────────────────
    st.markdown('<div class="card-secao">', unsafe_allow_html=True)
    st.markdown(f"#### PDV {pdv_sel} — Indicadores Comerciais")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _card_com_ly("💰 Receita",
                     get_pdv('receita'), meta_soma('meta_receita'),
                     ly=get_pdv('receita_vs_ly'),
                     iaf_peso=pesos.get('receita'), tipo='brl')
    with c2:
        _card_com_ly("💲 Boleto Médio",
                     get_pdv('boleto_medio'), meta_media('meta_boleto_medio'),
                     ly=get_pdv('boleto_medio_vs_ly'),
                     tipo='brl')
    with c3:
        _card_com_ly("📦 Itens/Boleto",
                     get_pdv('itens_por_boleto'), meta_media('meta_itens_boleto'),
                     ly=get_pdv('itens_por_boleto_vs_ly'),
                     tipo='num', casas=2)
    with c4:
        _card_com_ly("💲 Preço Médio",
                     get_pdv('preco_medio'), meta_media('meta_preco_medio'),
                     ly=get_pdv('preco_medio_vs_ly'),
                     tipo='brl')

    c5, c6, c7, c8 = st.columns(4)
    with c5: _card("🧾 Qtd. Boletos",  get_pdv('qtd_boletos'),    None,                             None, 'num', 0)
    with c6: _card("✂️ Serviços",      get_pdv('qtd_servicos'),   meta_soma('meta_servicos'),       pesos.get('servicos'), 'num', 0)
    with c7: _card("🏆 NPS",           nps_val,                   meta_media('meta_nps'),           pesos.get('nps'), 'num', 1)
    with c8: _card("🪪 ID Cliente",    get_base_media('pct_id_cliente_iaf'), meta_media('meta_pct_id_cliente'), pesos.get('id_cliente'), 'pct')

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Bloco 2: Penetrações ──────────────────────────────────────────────────
    st.markdown('<div class="card-secao">', unsafe_allow_html=True)
    st.markdown("#### Penetrações e Mix")

    c1, c2, c3, c4 = st.columns(4)
    with c1: _card("🔵 Pen. BT",      get_pdv('pen_bt'),          meta_media('meta_pen_bt'),           pesos.get('pen_bt'), 'pct')
    with c2: _card("🟣 Pen. BP",      get_pdv('pen_bp'),          meta_media('meta_pen_bp'),           pesos.get('pen_bp'), 'pct')
    with c3: _card("📱 Mobshop",      get_pdv('pen_mobshop'),     meta_media('meta_pen_mobshop'),      None, 'pct')
    with c4: _card("1️⃣ Boletos 1",   get_pdv('pen_boletos1'),    meta_media('meta_pen_boletos1'),     None, 'pct', 3, invertido=True)

    c5, c6, c7, c8 = st.columns(4)
    with c5: _card("💛 Fidelidade",   get_pdv('pen_fidelidade'),  meta_media('meta_pen_fidelidade'),   None, 'pct')
    with c6:
        # Resgate Fidelidade — valor já × 100, lógica invertida
        rf_real = get_pdv('resgate_fidelidade')
        rf_meta = meta_media('meta_resgate_fidelidade')
        # Meta vem em decimal (0.52), converte para percentual para comparar
        rf_meta_pct = rf_meta * 100 if rf_meta is not None else None
        _card("🔄 Resg. Fid.",  rf_real, rf_meta_pct,
              pesos.get('resgate_fidelidade'), 'num', 1, invertido=False)
    with c7: _card("🌊 Conv. Fluxo",  get_pdv('conv_fluxo'),      meta_media('meta_conv_fluxo'),       None, 'pct')
    with c8: _card("💄 Facial",       get_pdv('pen_facial'),      meta_media('meta_pen_facial'),       pesos.get('pen_facial'), 'pct')

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Bloco 3: Tabela de Consultores ────────────────────────────────────────
    st.markdown('<div class="card-secao">', unsafe_allow_html=True)
    st.markdown(f"#### Consultores — PDV {pdv_sel}")

    df_pdv_base = base[base['pdv'] == pdv_int].copy()
    is_ger = df_pdv_base['is_gerente'].fillna(False).astype(bool) if 'is_gerente' in df_pdv_base.columns else pd.Series(False, index=df_pdv_base.index)
    df_cons_pdv = df_pdv_base[~is_ger].copy()
    df_ger_pdv  = df_pdv_base[is_ger].copy()

    if not df_cons_pdv.empty:
        linhas = [_linha_tabela(r) for _, r in df_cons_pdv.iterrows()]
        st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True,
                     height=min(600, len(linhas)*38+50))

    if not df_ger_pdv.empty:
        st.caption("**Gerência**")
        linhas_g = [_linha_tabela(r) for _, r in df_ger_pdv.iterrows()]
        st.dataframe(pd.DataFrame(linhas_g), use_container_width=True, hide_index=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Configurações ─────────────────────────────────────────────────────────
    with st.expander("⚙️ Configurações do PDV"):
        st.markdown("**Lançar NPS**")
        st.caption("O NPS representa o resultado da loja inteira — inserido manualmente.")
        novo_nps = st.number_input(
            f"NPS — PDV {pdv_sel}",
            min_value=0.0, max_value=100.0,
            value=float(nps_val) if nps_val is not None else 0.0,
            step=0.1, format="%.1f",
            key=f"nps_cfg_{pdv_sel}"
        )
        if st.button("💾 Salvar NPS", key=f"salvar_nps_{pdv_sel}"):
            nps_dict[str(pdv_int)] = novo_nps
            salvar_nps(nps_dict)
            salvar_nps_supabase(pdv_int, novo_nps)
            st.success(f"NPS do PDV {pdv_sel} salvo: {novo_nps:.1f}")
            st.rerun()

