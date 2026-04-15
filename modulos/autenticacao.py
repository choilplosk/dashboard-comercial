"""
Módulo de autenticação.
Gerencia login, perfis (admin, lideranca, consultor) e sessão.
Senhas armazenadas como hash SHA-256 — nunca em texto puro.
"""

import json
import hashlib
import os
import streamlit as st
from datetime import datetime

CAMINHO_USUARIOS = os.path.join(os.path.dirname(__file__), '..', 'dados', 'usuarios.json')


# ── Utilitários ──────────────────────────────────────────────────────────────

def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def _carregar_usuarios() -> dict:
    if not os.path.exists(CAMINHO_USUARIOS):
        return {}
    with open(CAMINHO_USUARIOS, 'r', encoding='utf-8') as f:
        return json.load(f)


def _salvar_usuarios(usuarios: dict):
    os.makedirs(os.path.dirname(CAMINHO_USUARIOS), exist_ok=True)
    with open(CAMINHO_USUARIOS, 'w', encoding='utf-8') as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=2)


def _criar_usuarios_padrao():
    """Cria usuários iniciais se o arquivo não existir."""
    usuarios = {
        "admin": {
            "nome": "Administrador",
            "senha_hash": _hash("admin2026"),
            "perfil": "admin",
            "pdvs": [],          # lista vazia = acesso a todos
            "ativo": True,
            "criado_em": datetime.now().isoformat()
        }
    }
    _salvar_usuarios(usuarios)
    return usuarios


# ── Login ────────────────────────────────────────────────────────────────────

def tela_login():
    """
    Exibe a tela de login e gerencia a sessão.
    Retorna True se autenticado, False caso contrário.
    """
    if st.session_state.get('autenticado'):
        return True

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<h2 style='text-align:center; margin-bottom:2rem;'>📊 Dashboard Comercial</h2>",
            unsafe_allow_html=True
        )

        with st.container():
            usuario = st.text_input("Usuário", placeholder="seu.usuario")
            senha   = st.text_input("Senha", type="password", placeholder="••••••••")

            if st.button("Entrar", use_container_width=True):
                usuarios = _carregar_usuarios()
                if not usuarios:
                    usuarios = _criar_usuarios_padrao()

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


# ── Controle de acesso ────────────────────────────────────────────────────────

def perfil_atual() -> str:
    return st.session_state.get('perfil', '')


def is_admin() -> bool:
    return perfil_atual() == 'admin'


def is_lideranca() -> bool:
    return perfil_atual() in ('admin', 'lideranca')


def pdvs_permitidos(todos_pdvs: list) -> list:
    """
    Retorna a lista de PDVs que o usuário atual pode ver.
    Admin e liderança veem todos. Consultor vê só os seus.
    """
    acesso = st.session_state.get('pdvs_acesso', [])
    if not acesso:
        return todos_pdvs
    return [p for p in todos_pdvs if str(p) in [str(a) for a in acesso]]


# ── Gestão de usuários (só para admin) ───────────────────────────────────────

def painel_gestao_usuarios():
    """Painel completo de gestão de usuários — exibido só para admins."""
    if not is_admin():
        st.warning("Acesso restrito ao administrador.")
        return

    st.subheader("👥 Gestão de Usuários")
    usuarios = _carregar_usuarios()
    if not usuarios:
        usuarios = _criar_usuarios_padrao()

    # Tabela de usuários existentes
    with st.expander("Usuários cadastrados", expanded=True):
        for login, dados in usuarios.items():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 1.5, 1, 1])
            c1.write(f"**{dados['nome']}**")
            c2.write(login)
            c3.write(dados['perfil'].capitalize())
            status = "✅ Ativo" if dados.get('ativo') else "❌ Inativo"
            c4.write(status)
            if login != 'admin':
                novo_status = not dados.get('ativo', True)
                label = "Desativar" if dados.get('ativo') else "Ativar"
                if c5.button(label, key=f"toggle_{login}"):
                    usuarios[login]['ativo'] = novo_status
                    _salvar_usuarios(usuarios)
                    st.rerun()

    # Criar novo usuário
    st.divider()
    st.markdown("**Criar novo usuário**")
    col1, col2 = st.columns(2)
    with col1:
        novo_login  = st.text_input("Login (sem espaços)", key="novo_login")
        novo_nome   = st.text_input("Nome completo", key="novo_nome")
        nova_senha  = st.text_input("Senha inicial", type="password", key="nova_senha")
    with col2:
        novo_perfil = st.selectbox("Perfil", ["lideranca", "consultor", "admin"], key="novo_perfil")
        novos_pdvs  = st.text_input(
            "PDVs permitidos (separados por vírgula — deixe vazio para todos)",
            key="novos_pdvs"
        )

    if st.button("Criar usuário"):
        if not novo_login or not novo_nome or not nova_senha:
            st.error("Preencha todos os campos obrigatórios.")
        elif novo_login in usuarios:
            st.error("Esse login já existe.")
        else:
            pdvs_lista = [p.strip() for p in novos_pdvs.split(',') if p.strip()] if novos_pdvs else []
            usuarios[novo_login] = {
                "nome": novo_nome,
                "senha_hash": _hash(nova_senha),
                "perfil": novo_perfil,
                "pdvs": pdvs_lista,
                "ativo": True,
                "criado_em": datetime.now().isoformat()
            }
            _salvar_usuarios(usuarios)
            st.success(f"Usuário '{novo_login}' criado com sucesso.")
            st.rerun()

    # Resetar senha
    st.divider()
    st.markdown("**Resetar senha**")
    col1, col2, col3 = st.columns(3)
    login_reset = col1.selectbox("Usuário", list(usuarios.keys()), key="login_reset")
    nova_senha_reset = col2.text_input("Nova senha", type="password", key="senha_reset")
    if col3.button("Resetar", key="btn_reset"):
        if nova_senha_reset:
            usuarios[login_reset]['senha_hash'] = _hash(nova_senha_reset)
            _salvar_usuarios(usuarios)
            st.success("Senha atualizada.")
        else:
            st.error("Digite a nova senha.")
