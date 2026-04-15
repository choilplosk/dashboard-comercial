"""
Aba IA & Chat.
Diagnóstico automático + chatbox com memória de sessão.
Ambos baseados nos dados carregados.
"""

import streamlit as st
import pandas as pd
from modulos.calculos import fmt_brl, fmt_pct, fmt_num, atingimento
from modulos.iaf import calcular_iaf_base, CORES_IAF
from modulos.nps import carregar_nps


# ── Resumo dos dados para contexto da IA ─────────────────────────────────────

def _montar_contexto(base: pd.DataFrame, metas: pd.DataFrame, nps: dict) -> str:
    """Monta um resumo estruturado dos dados para enviar à IA."""
    is_ger = base.get('is_gerente', pd.Series(False, index=base.index)).fillna(False).astype(bool)
    df = base[~is_ger].copy()

    total_cons = len(df)
    total_rec  = df['receita'].sum()
    meta_rec   = pd.to_numeric(metas.get('meta_receita', pd.Series()), errors='coerce').sum() if not metas.empty else 0
    at_rec     = atingimento(total_rec, meta_rec)

    media_bm   = df['boleto_medio'].mean()
    media_it   = df['itens_por_boleto'].mean()
    total_serv = df['servicos_real'].sum() if 'servicos_real' in df.columns else 0

    # IAF
    base_iaf = calcular_iaf_base(base, nps)
    df_iaf = base_iaf[~base_iaf['classificacao'].isin(['Gerente','Sem meta'])].copy()
    contagem_iaf = df_iaf['classificacao'].value_counts().to_dict()
    media_iaf = df_iaf['pct_iaf'].mean() if 'pct_iaf' in df_iaf.columns else 0

    # Top 3 e bottom 3
    df_rank = df_iaf.dropna(subset=['pct_iaf']).sort_values('pct_iaf', ascending=False)
    top3    = df_rank.head(3)[['consultor','pdv','pct_iaf','classificacao']].to_dict('records')
    bot3    = df_rank.tail(3)[['consultor','pdv','pct_iaf','classificacao']].to_dict('records')

    # Indicadores com maior desvio negativo
    desvios = []
    for col_r, col_m, nome in [
        ('pen_bt','meta_pen_bt','Pen. BT'),
        ('pen_bp','meta_pen_bp','Pen. BP'),
        ('pen_facial','meta_pen_facial','Pen. Facial'),
        ('servicos_real','meta_servicos','Serviços'),
    ]:
        if col_r in df.columns and col_m in df.columns:
            at = atingimento(df[col_r].mean(), pd.to_numeric(metas.get(col_m, pd.Series()), errors='coerce').mean() if not metas.empty else None)
            if at is not None:
                desvios.append((nome, at))

    desvios_neg = sorted([d for d in desvios if d[1] < 0.95], key=lambda x: x[1])

    ctx = f"""
DADOS DO PERÍODO ATUAL — Dashboard Comercial IAF

EQUIPE:
- Total de consultores: {total_cons}
- Receita total: R$ {total_rec:,.2f}
- Meta total de receita: R$ {meta_rec:,.2f}
- % Atingimento receita: {f'{at_rec*100:.1f}%' if at_rec else 'n/e'}
- Boleto médio da equipe: R$ {media_bm:.2f}
- Itens por boleto: {media_it:.2f}
- Total de serviços: {int(total_serv) if total_serv else 'n/e'}

IAF (Instrumento de Avaliação de Franquia):
- % IAF médio da equipe: {media_iaf:.1f}%
- Distribuição: {contagem_iaf}

TOP 3 consultores (% IAF):
{chr(10).join([f"  {i+1}. {r['consultor']} (PDV {r['pdv']}) — {r['pct_iaf']:.1f}% — {r['classificacao']}" for i,r in enumerate(top3)])}

Bottom 3 consultores (% IAF):
{chr(10).join([f"  {i+1}. {r['consultor']} (PDV {r['pdv']}) — {r['pct_iaf']:.1f}% — {r['classificacao']}" for i,r in enumerate(bot3)])}

Indicadores abaixo de 95% da meta:
{chr(10).join([f"  - {nome}: {at*100:.1f}%" for nome, at in desvios_neg]) if desvios_neg else "  Nenhum indicador crítico identificado"}

NPS por PDV: {nps if nps else 'Não lançado'}
"""
    return ctx.strip()


# ── Chamada à API Anthropic ───────────────────────────────────────────────────

def _chamar_ia(mensagens: list, contexto: str, api_key: str) -> str:
    """Chama a API do Claude com o histórico de mensagens e contexto dos dados."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        system_prompt = f"""Você é um analista comercial especializado em varejo e franquias.
Você tem acesso aos dados reais do dashboard comercial da empresa.
Responda sempre em português, de forma direta e objetiva.
Use números quando disponíveis. Seja como um gestor experiente dando feedback.

CONTEXTO DOS DADOS ATUAIS:
{contexto}
"""
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system_prompt,
            messages=mensagens,
        )
        return response.content[0].text
    except ImportError:
        return "❌ Biblioteca 'anthropic' não instalada. Execute: pip install anthropic"
    except Exception as e:
        return f"❌ Erro ao conectar com a IA: {str(e)}"


def _gerar_diagnostico(contexto: str, api_key: str) -> str:
    """Gera diagnóstico executivo automático."""
    prompt = """Com base nos dados fornecidos, gere um relatório executivo estruturado em:

1. DIAGNÓSTICO GERAL (2-3 frases resumindo o momento da equipe)
2. DESTAQUES POSITIVOS (bullet points com números)
3. PONTOS DE ATENÇÃO (bullet points com números)
4. RECOMENDAÇÕES TÁTICAS (3 ações concretas e específicas)

Seja direto, use os números dos dados, fale como gestor experiente."""

    return _chamar_ia(
        [{"role": "user", "content": prompt}],
        contexto, api_key
    )


# ── Render principal ──────────────────────────────────────────────────────────

def render(dados: dict):
    st.header("🤖 IA & Chat")

    base  = dados.get('_base_calculada')
    metas = dados.get('metas', pd.DataFrame())

    if base is None:
        st.info("Carregue os arquivos para continuar.")
        return

    nps = carregar_nps()

    # ── Configuração da API ───────────────────────────────────────────────────
    with st.expander("🔑 Configuração da API", expanded='api_key' not in st.session_state):
        st.caption("A chave API é necessária para usar os recursos de IA. Obtenha em console.anthropic.com")
        api_key_input = st.text_input(
            "Chave API Anthropic",
            type="password",
            value=st.session_state.get('api_key', ''),
            placeholder="sk-ant-...",
            key="api_key_input"
        )
        if st.button("💾 Salvar chave", key="btn_salvar_key"):
            if api_key_input.strip():
                st.session_state['api_key'] = api_key_input.strip()
                st.success("Chave salva para esta sessão.")
                st.rerun()
            else:
                st.warning("Digite a chave antes de salvar.")

    api_key = st.session_state.get('api_key', '')

    if not api_key:
        st.warning("Configure a chave da API acima para usar os recursos de IA.")
        return

    # ── Contexto dos dados ────────────────────────────────────────────────────
    contexto = _montar_contexto(base, metas, nps)

    # ── Navegação ─────────────────────────────────────────────────────────────
    if 'ia_modo' not in st.session_state:
        st.session_state['ia_modo'] = 'diagnostico'

    col1, col2, col_esp = st.columns([1.5, 1.5, 5])
    with col1:
        if st.button("📋 Diagnóstico Automático",
                     type="primary" if st.session_state['ia_modo']=='diagnostico' else "secondary",
                     use_container_width=True, key="ia_btn_diag"):
            st.session_state['ia_modo'] = 'diagnostico'
            st.rerun()
    with col2:
        if st.button("💬 Chat com os Dados",
                     type="primary" if st.session_state['ia_modo']=='chat' else "secondary",
                     use_container_width=True, key="ia_btn_chat"):
            st.session_state['ia_modo'] = 'chat'
            st.rerun()

    st.divider()

    # ── DIAGNÓSTICO AUTOMÁTICO ────────────────────────────────────────────────
    if st.session_state['ia_modo'] == 'diagnostico':
        st.markdown("### 📋 Diagnóstico Executivo")
        st.caption("A IA analisa os dados do período atual e gera um relatório executivo.")

        if st.button("▶ Gerar Diagnóstico", type="primary", key="btn_gerar_diag"):
            with st.spinner("Analisando dados..."):
                resultado = _gerar_diagnostico(contexto, api_key)
                st.session_state['ultimo_diagnostico'] = resultado

        if 'ultimo_diagnostico' in st.session_state:
            st.markdown('<div class="card-secao">', unsafe_allow_html=True)
            st.markdown(st.session_state['ultimo_diagnostico'])
            st.markdown('</div>', unsafe_allow_html=True)

        # Preview dos dados enviados à IA
        with st.expander("🔍 Ver dados enviados para a IA"):
            st.code(contexto, language='text')

    # ── CHAT ──────────────────────────────────────────────────────────────────
    elif st.session_state['ia_modo'] == 'chat':
        st.markdown("### 💬 Chat com os Dados")
        st.caption(
            "Faça perguntas sobre os dados em linguagem natural. "
            "Exemplos: 'Por que o PDV 7473 está abaixo da meta?', "
            "'Quem está em risco de não classificar no IAF?', "
            "'Compare o desempenho dos PDVs.'"
        )

        # Inicializa histórico do chat
        if 'chat_historico' not in st.session_state:
            st.session_state['chat_historico'] = []

        # Exibe histórico
        for msg in st.session_state['chat_historico']:
            with st.chat_message(msg['role'],
                                  avatar="🧑‍💼" if msg['role']=='user' else "🤖"):
                st.markdown(msg['content'])

        # Input de mensagem
        pergunta = st.chat_input("Faça uma pergunta sobre os dados...")

        if pergunta:
            # Adiciona mensagem do usuário
            st.session_state['chat_historico'].append({
                "role": "user",
                "content": pergunta
            })

            with st.chat_message("user", avatar="🧑‍💼"):
                st.markdown(pergunta)

            # Gera resposta
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Pensando..."):
                    # Monta histórico no formato da API
                    msgs_api = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state['chat_historico']
                    ]
                    resposta = _chamar_ia(msgs_api, contexto, api_key)
                    st.markdown(resposta)

            # Salva resposta no histórico
            st.session_state['chat_historico'].append({
                "role": "assistant",
                "content": resposta
            })

        # Botão para limpar histórico
        if st.session_state.get('chat_historico'):
            if st.button("🗑️ Limpar conversa", key="btn_limpar_chat"):
                st.session_state['chat_historico'] = []
                st.rerun()
