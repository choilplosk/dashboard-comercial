"""
Módulo de autenticação.
Usuários armazenados no Supabase — funciona em qualquer ambiente.
"""

import streamlit as st
import hashlib
from datetime import datetime


def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def _get_client():
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception:
        return None


def _carregar_usuarios() -> dict:
    """Carrega usuários do Supabase."""
    client = _get_client()
    if client is None:
        return {}
    try:
        res = client.table('usuarios').select('*').execute()
        usuarios = {}
        for u in res.data:
            usuarios[u['login']] = {
                'nome':       u['nome'],
                'senha_hash': u['senha_hash'],
                'perfil':     u['perfil'],
                'pdvs':       [p.strip() for p in u.get('pdvs', '').split(',') if p.strip()],
                'ativo':      u.get('ativo', True),
                'id':         u['id'],
            }
        return usuarios
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return {}


def _salvar_usuario(login: str, dados: dict) -> bool:
    """Insere ou atualiza um usuário no Supabase."""
    client = _get_client()
    if client is None:
        return False
    try:
        pdvs_str = ','.join(str(p) for p in dados.get('pdvs', []))
        payload = {
            'login':      login,
            'nome':       dados['nome'],
            'senha_hash': dados['senha_hash'],
            'perfil':     dados['perfil'],
            'pdvs':       pdvs_str,
            'ativo':      dados.get('ativo', True),
        }
        # Upsert — insere ou atualiza
        client.table('usuarios').upsert(payload, on_conflict='login').execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar usuário: {e}")
        return False


def _atualizar_campo(login: str, campo: str, valor) -> bool:
    """Atualiza um campo específico de um usuário."""
    client = _get_client()
    if client is None:
        return False
    try:
        client.table('usuarios').update({campo: valor}).eq('login', login).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar usuário: {e}")
        return False


# ── Tela de login ─────────────────────────────────────────────────────────────

def tela_login() -> bool:
    if st.session_state.get('autenticado'):
        return True

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h2 style='text-align:center; margin-bottom:2rem;'>📊 Dashboard Comercial</h2>",
            unsafe_allow_html=True
        )

        usuario = st.text_input("Usuário", placeholder="seu.usuario")
        senha   = st.text_input("Senha", type="password", placeholder="••••••••")

        if st.button("Entrar", use_container_width=True):
            usuarios = _carregar_usuarios()

            # Fallback admin se Supabase vazio
            if not usuarios:
                if usuario == 'admin' and senha == 'admin2026':
                    st.session_state['autenticado']  = True
                    st.session_state['usuario']      = 'admin'
                    st.session_state['nome_usuario'] = 'Administrador'
                    st.session_state['perfil']       = 'admin'
                    st.session_state['pdvs_acesso']  = []
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
                return False

            u = usuarios.get(usuario)
            if u and u.get('ativo') and u['senha_hash'] == _hash(senha):
                st.session_state['autenticado']  = True
                st.session_state['usuario']      = usuario
                st.session_state['nome_usuario'] = u['nome']
                st.session_state['perfil']       = u['perfil']
                st.session_state['pdvs_acesso']  = u.get('pdvs', [])
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

        st.markdown(
            "<p style='text-align:center; font-size:12px; color:gray; margin-top:2rem;'>"
            "Acesso restrito. Em caso de problemas, contate o administrador.</p>",
            unsafe_allow_html=True
        )
    return False


def logout():
    for chave in ['autenticado', 'usuario', 'nome_usuario', 'perfil', 'pdvs_acesso']:
        st.session_state.pop(chave, None)
    st.rerun()


def perfil_atual() -> str:
    return st.session_state.get('perfil', '')


def is_admin() -> bool:
    return perfil_atual() == 'admin'


def is_lideranca() -> bool:
    return perfil_atual() in ('admin', 'lideranca')


# ── Painel de gestão de usuários ──────────────────────────────────────────────

def painel_gestao_usuarios():
    if not is_admin():
        st.warning("Acesso restrito ao administrador.")
        return

    st.subheader("👥 Gestão de Usuários")
    usuarios = _carregar_usuarios()

    # Tabela de usuários existentes
    with st.expander("Usuários cadastrados", expanded=True):
        for login, dados in usuarios.items():
            c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 1.5, 1.5, 1, 1])
            c1.write(f"**{dados['nome']}**")
            c2.write(login)
            c3.write(dados['perfil'].capitalize())
            pdvs_str = ', '.join(dados.get('pdvs', [])) or 'Todos'
            c4.write(f"PDVs: {pdvs_str}")
            status = "✅ Ativo" if dados.get('ativo') else "❌ Inativo"
            c5.write(status)
            if login != 'admin':
                novo_status = not dados.get('ativo', True)
                label = "Desativar" if dados.get('ativo') else "Ativar"
                if c6.button(label, key=f"toggle_{login}"):
                    _atualizar_campo(login, 'ativo', novo_status)
                    st.rerun()

    # Criar novo usuário
    st.divider()
    st.markdown("**Criar novo usuário**")
    col1, col2 = st.columns(2)
    with col1:
        novo_login = st.text_input("Login (sem espaços)", key="novo_login")
        novo_nome  = st.text_input("Nome completo", key="novo_nome")
        nova_senha = st.text_input("Senha inicial", type="password", key="nova_senha")
    with col2:
        novo_perfil = st.selectbox("Perfil", ["lideranca", "consultor", "admin"], key="novo_perfil")
        novos_pdvs  = st.text_input(
            "PDVs permitidos (separados por vírgula — vazio = todos)",
            key="novos_pdvs"
        )

    if st.button("✅ Criar usuário", key="btn_criar"):
        if not novo_login or not novo_nome or not nova_senha:
            st.error("Preencha todos os campos obrigatórios.")
        elif novo_login in usuarios:
            st.error("Esse login já existe.")
        else:
            pdvs_lista = [p.strip() for p in novos_pdvs.split(',') if p.strip()] if novos_pdvs else []
            ok = _salvar_usuario(novo_login, {
                'nome':       novo_nome,
                'senha_hash': _hash(nova_senha),
                'perfil':     novo_perfil,
                'pdvs':       pdvs_lista,
                'ativo':      True,
            })
            if ok:
                st.success(f"Usuário '{novo_login}' criado com sucesso!")
                st.rerun()

    # Resetar senha
    st.divider()
    st.markdown("**Resetar senha**")
    col1, col2, col3 = st.columns(3)
    login_reset      = col1.selectbox("Usuário", list(usuarios.keys()), key="login_reset")
    nova_senha_reset = col2.text_input("Nova senha", type="password", key="senha_reset")
    if col3.button("Resetar", key="btn_reset"):
        if nova_senha_reset:
            _atualizar_campo(login_reset, 'senha_hash', _hash(nova_senha_reset))
            st.success(f"Senha de '{login_reset}' atualizada.")
        else:
            st.error("Digite a nova senha.")
