"""
app.py — Dashboard Comercial IAF 2026.
Navegação lateral com menu fixo.
Dados persistidos no session_state para não sumir ao trocar de página.
"""

import streamlit as st
import pandas as pd
from datetime import date
import os, sys

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="Dashboard Comercial IAF",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Fundo branco limpo */
    .stApp { background-color: #ffffff; }
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

    /* Sidebar escura */
    [data-testid="stSidebar"] { background-color: #1e293b !important; min-width: 240px; }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div { color: #cbd5e1 !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #f1f5f9 !important; }

    /* Botões do menu lateral */
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        border: none !important;
        color: #94a3b8 !important;
        text-align: left !important;
        padding: 9px 14px !important;
        border-radius: 8px !important;
        font-size: 14px !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #334155 !important;
        color: #f1f5f9 !important;
    }

    /* Cards de seção */
    .card-secao {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }

    /* Títulos */
    h1 { color: #0f172a !important; font-weight: 700 !important; }
    h2, h3, h4 { color: #1e293b !important; font-weight: 600 !important; }

    /* Tabelas */
    .stDataFrame { border-radius: 10px; }

    /* Remove barra de abas se existir */
    .stTabs [data-baseweb="tab-list"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Login ─────────────────────────────────────────────────────────────────────
from modulos.autenticacao import tela_login, logout, is_admin
if not tela_login():
    st.stop()

# ── Imports ───────────────────────────────────────────────────────────────────
from modulos.leitura import widget_upload_sidebar
from modulos.calculos import montar_base_consultores, calcular_atingimentos
from modulos.historico import salvar_snapshot, seletor_data_sidebar, carregar_snapshot
from modulos.nps import carregar_nps
import paginas.resumo    as pg_resumo
import paginas.pdv       as pg_pdv
import paginas.consultor as pg_consultor
import paginas.ranking    as pg_ranking
import paginas.iaf_painel as pg_iaf
import paginas.ai_chat     as pg_ia

# ── Inicializa estado ─────────────────────────────────────────────────────────
if 'pagina' not in st.session_state:
    st.session_state['pagina'] = 'resumo'
if 'dados' not in st.session_state:
    st.session_state['dados'] = {}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:16px 8px 4px 8px;'>
        <div style='font-size:18px;font-weight:700;color:#f1f5f9;'>📊 Dashboard IAF</div>
        <div style='font-size:12px;color:#64748b;margin-top:2px;'>""" +
        f"Olá, {st.session_state.get('nome_usuario','')}" +
        "</div></div>", unsafe_allow_html=True)

    st.divider()

    # ── Menu de navegação ─────────────────────────────────────────────────────
    MENU = [
        ('resumo',    '🏠', 'Resumo Consolidado'),
        ('pdv',       '🏪', 'Por PDV'),
        ('consultor', '👤', 'Por Consultor'),
        ('ranking',   '🏆', 'Ranking'),
        ('iaf',       '🎯', 'IAF'),
        ('ia',        '🤖', 'IA & Chat'),
    ]
    for key, icone, label in MENU:
        ativo = st.session_state['pagina'] == key
        # Destaque visual para item ativo via markdown
        if ativo:
            st.markdown(
                f"<div style='background:#2563eb;border-radius:8px;padding:9px 14px;"
                f"font-size:14px;color:white;font-weight:600;margin-bottom:4px;'>"
                f"{icone} {label}</div>",
                unsafe_allow_html=True
            )
        else:
            if st.button(f"{icone}  {label}", key=f"nav_{key}", use_container_width=True):
                st.session_state['pagina'] = key
                st.rerun()

    st.divider()

    # ── Upload de arquivos ────────────────────────────────────────────────────
    novos_dados = widget_upload_sidebar()

    # Persiste dados no session_state se novos arquivos foram carregados
    if novos_dados:
        for tipo, df in novos_dados.items():
            if not tipo.startswith('_'):
                st.session_state['dados'][tipo] = df

    st.divider()

    # ── Histórico ─────────────────────────────────────────────────────────────
    data_sel = seletor_data_sidebar()

    st.divider()

    if is_admin():
        if st.button("⚙️ Administração", use_container_width=True, key="nav_admin"):
            st.session_state['pagina'] = 'admin'
            st.rerun()

    if st.button("🔓 Sair", use_container_width=True, key="nav_sair"):
        logout()

# ── Montagem da base ──────────────────────────────────────────────────────────
dados = st.session_state['dados']

@st.cache_data(show_spinner="Processando dados...")
def _montar_base(hash_k: str, _dados: dict) -> pd.DataFrame:
    base = montar_base_consultores(
        df_cons  = _dados.get('consultor', pd.DataFrame()),
        df_metas = _dados.get('metas',     pd.DataFrame()),
        df_serv  = _dados.get('servicos'),
        df_trein = _dados.get('treinamentos'),
        df_id    = _dados.get('id_cliente'),
    )
    return calcular_atingimentos(base)

# Recalcula base sempre que dados mudam
if 'consultor' in dados and 'metas' in dados:
    hash_k = (str(sorted(dados.keys())) +
              str(len(dados.get('consultor', pd.DataFrame()))) +
              str(len(dados.get('metas', pd.DataFrame()))))
    base_calc = _montar_base(hash_k, dados)
    dados['_base_calculada'] = base_calc
    st.session_state['dados'] = dados

    col_snap = st.sidebar.columns([1])
    if st.sidebar.button("💾 Salvar snapshot de hoje", key="btn_snap"):
        salvar_snapshot(base_calc, date.today())
        st.sidebar.success("Snapshot salvo!")

elif data_sel:
    base_hist = carregar_snapshot(data_sel)
    if base_hist is not None and '_base_calculada' not in dados:
        dados['_base_calculada'] = base_hist
        dados.setdefault('metas', pd.DataFrame())
        st.session_state['dados'] = dados
        st.sidebar.info(f"Dados de {data_sel.strftime('%d/%m/%Y')}")

nps_atual = carregar_nps()

# ── Roteador de páginas ───────────────────────────────────────────────────────
pagina = st.session_state.get('pagina', 'resumo')

if pagina == 'admin' and is_admin():
    from modulos.autenticacao import painel_gestao_usuarios
    st.title("⚙️ Administração")
    painel_gestao_usuarios()

elif pagina == 'resumo':
    pg_resumo.render(dados, nps_atual)

elif pagina == 'pdv':
    pg_pdv.render(dados)

elif pagina == 'consultor':
    pg_consultor.render(dados, nps_atual)

elif pagina == 'ranking':
    pg_ranking.render(dados, nps_atual)

elif pagina == 'iaf':
    pg_iaf.render(dados)

elif pagina == 'ia':
    pg_ia.render(dados)
