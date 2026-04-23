"""
app.py — Dashboard Comercial IAF 2026.
Dados persistidos no Supabase — sem necessidade de upload a cada sessão.
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
    .stApp { background-color: #ffffff; }
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; min-width: 240px; }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div { color: #cbd5e1 !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 { color: #f1f5f9 !important; }
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
    .card-secao {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
    }
    h1 { color: #0f172a !important; font-weight: 700 !important; }
    h2, h3, h4 { color: #1e293b !important; font-weight: 600 !important; }
    .stDataFrame { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ── Login ─────────────────────────────────────────────────────────────────────
from modulos.autenticacao import tela_login, logout, is_admin, is_lideranca
if not tela_login():
    st.stop()

# ── Imports ───────────────────────────────────────────────────────────────────
from modulos.leitura import widget_upload_sidebar
from modulos.calculos import montar_base_consultores, calcular_atingimentos
from modulos.historico import salvar_snapshot, seletor_data_sidebar, carregar_snapshot
from modulos.supabase_db import (
    carregar_dados_recentes, salvar_upload, carregar_metas,
    carregar_nps_supabase, salvar_nps_supabase, data_ultimo_upload,
    verificar_conexao
)
import paginas.resumo      as pg_resumo
import paginas.pdv         as pg_pdv
import paginas.consultor   as pg_consultor
import paginas.ranking     as pg_ranking
import paginas.iaf_painel  as pg_iaf
import paginas.ai_chat     as pg_ia
import paginas.metas_painel as pg_metas

# ── Inicializa estado ─────────────────────────────────────────────────────────
if 'pagina' not in st.session_state:
    st.session_state['pagina'] = 'resumo'
if 'dados' not in st.session_state:
    st.session_state['dados'] = {}
if 'supabase_carregado' not in st.session_state:
    st.session_state['supabase_carregado'] = False

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"<div style='padding:16px 8px 4px 8px;'>"
        f"<div style='font-size:18px;font-weight:700;color:#f1f5f9;'>📊 Dashboard IAF</div>"
        f"<div style='font-size:12px;color:#64748b;margin-top:2px;'>"
        f"Olá, {st.session_state.get('nome_usuario','')}</div></div>",
        unsafe_allow_html=True
    )
    st.divider()

    MENU = [
        ('resumo',    '🏠', 'Resumo Consolidado'),
        ('pdv',       '🏪', 'Por PDV'),
        ('consultor', '👤', 'Por Consultor'),
        ('ranking',   '🏆', 'Ranking'),
        ('iaf',       '🎯', 'IAF'),
        ('ia',        '🤖', 'IA & Chat'),
    ]
    if is_lideranca():
        MENU.append(('metas', '🎯', 'Gestão de Metas'))

    for key, icone, label in MENU:
        ativo = st.session_state['pagina'] == key
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

    ultimo = data_ultimo_upload()
    if ultimo:
        st.markdown(
            f"<div style='font-size:11px;color:#64748b;padding:4px 8px;'>"
            f"📅 Dados de: <b style='color:#94a3b8;'>{ultimo}</b></div>",
            unsafe_allow_html=True
        )

    st.markdown(
        "<div style='font-size:12px;color:#94a3b8;padding:4px 8px 2px;font-weight:600;'>"
        "📁 Atualizar dados</div>",
        unsafe_allow_html=True
    )
    novos_dados = widget_upload_sidebar()

    if novos_dados and 'consultor' in novos_dados:
        for tipo, df in novos_dados.items():
            if not tipo.startswith('_'):
                st.session_state['dados'][tipo] = df

        data_ref = st.sidebar.date_input(
            "Data de referência dos dados",
            value=date.today(),
            key="data_upload_ref"
        )
        if st.sidebar.button("💾 Salvar no banco", type="primary", key="btn_salvar_supa"):
            with st.spinner("Salvando..."):
                ok = salvar_upload(st.session_state['dados'], data_ref)
                if ok:
                    st.sidebar.success("✅ Dados salvos!")
                    st.session_state['dados'] = {}
                    st.session_state['supabase_carregado'] = False
                    st.rerun()

    st.divider()

    if is_admin():
        if st.button("⚙️ Administração", use_container_width=True, key="nav_admin"):
            st.session_state['pagina'] = 'admin'
            st.rerun()

    if st.button("🔓 Sair", use_container_width=True, key="nav_sair"):
        logout()

# ── Carrega dados do Supabase automaticamente ────────────────────────────────
dados = st.session_state['dados']

if 'consultor' not in dados:
    try:
        from supabase import create_client
        _url = st.secrets["supabase"]["url"]
        _key = st.secrets["supabase"]["key"]
        _cli = create_client(_url, _key)

        _tabelas = {
            'consultor':    'dados_consultor',
            'pdv':          'dados_pdv',
            'servicos':     'dados_servicos',
            'treinamentos': 'dados_treinamentos',
            'id_cliente':   'dados_id_cliente',
        }
        for _tipo, _tabela in _tabelas.items():
            try:
                _rd = _cli.table(_tabela).select('data_upload').order('data_upload', desc=True).limit(1).execute()
                if _rd.data:
                    _data = _rd.data[0]['data_upload']
                    _res = _cli.table(_tabela).select('*').eq('data_upload', _data).execute()
                    if _res.data:
                        _df = pd.DataFrame(_res.data)
                        _df = _df.drop(columns=['id','data_upload'], errors='ignore')
                        dados[_tipo] = _df
            except Exception:
                pass

        if dados:
            st.session_state['dados'] = dados
    except Exception as _e:
        st.error(f"Erro ao carregar dados: {_e}")

if 'metas' not in dados or dados.get('metas', pd.DataFrame()).empty:
    metas_supa = carregar_metas()
    if not metas_supa.empty:
        dados['metas'] = metas_supa
        st.session_state['dados'] = dados

# ── Monta base calculada ──────────────────────────────────────────────────────
# VERSÃO DO CACHE: incrementar sempre que alterar calculos.py ou iaf.py
# para forçar recálculo e invalidar cache antigo.
CACHE_VERSION = "v3"

@st.cache_data(show_spinner="Processando dados...")
def _montar_base(hash_k: str, _dados: dict) -> pd.DataFrame:
    from modulos.calculos import montar_base_consultores, calcular_atingimentos
    base = montar_base_consultores(
        df_cons  = _dados.get('consultor', pd.DataFrame()),
        df_metas = _dados.get('metas',     pd.DataFrame()),
        df_serv  = _dados.get('servicos'),
        df_trein = _dados.get('treinamentos'),
        df_id    = _dados.get('id_cliente'),
    )
    return calcular_atingimentos(base)

if 'consultor' in dados:
    hash_k = (
        str(sorted([k for k in dados.keys() if not k.startswith('_')])) +
        str(len(dados.get('consultor', pd.DataFrame()))) +
        str(len(dados.get('metas', pd.DataFrame()))) +
        CACHE_VERSION  # força recálculo quando código muda
    )
    base_calc = _montar_base(hash_k, dados)
    dados['_base_calculada'] = base_calc
    st.session_state['dados'] = dados

nps_atual = carregar_nps_supabase()

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

elif pagina == 'metas' and is_lideranca():
    pg_metas.render()
