"""
Página de Metas.
Permite lideranças editarem metas diretamente no dashboard.
Também permite upload de CSV para substituição em massa.
"""

import streamlit as st
import pandas as pd
from modulos.supabase_db import carregar_metas, salvar_metas, salvar_meta_linha
from modulos.calculos import fmt_brl, fmt_pct, fmt_num


COLUNAS_METAS = [
    ('meta_receita',            'Receita (R$)',          'brl'),
    ('meta_boleto_medio',       'Boleto Médio (R$)',     'brl'),
    ('meta_itens_boleto',       'Itens/Boleto',          'num'),
    ('meta_preco_medio',        'Preço Médio (R$)',      'brl'),
    ('meta_pen_bt',             'Pen. BT (%)',           'pct'),
    ('meta_pen_bp',             'Pen. BP (%)',           'pct'),
    ('meta_pen_mobshop',        'Pen. Mobshop (%)',      'pct'),
    ('meta_pen_boletos1',       'Pen. Boletos 1 (%)',    'pct'),
    ('meta_pen_fidelidade',     'Pen. Fidelidade (%)',   'pct'),
    ('meta_resgate_fidelidade', 'Resgate Fid. (%)',      'pct'),
    ('meta_conv_fluxo',         'Conv. Fluxo (%)',       'pct'),
    ('meta_pen_facial',         'Pen. Facial (%)',       'pct'),
    ('meta_pct_id_cliente',     'ID Cliente (%)',        'pct'),
    ('meta_servicos',           'Serviços',              'num'),
    ('meta_nps',                'NPS',                   'num'),
]


def _fmt(v, tipo):
    if v is None or pd.isna(v): return '—'
    if tipo == 'brl': return fmt_brl(v)
    if tipo == 'pct': return fmt_pct(v)
    return fmt_num(v, 2)


def render():
    st.header("🎯 Gestão de Metas")

    df_metas = carregar_metas()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    if 'metas_modo' not in st.session_state:
        st.session_state['metas_modo'] = 'visualizar'

    c1, c2, c3, col_esp = st.columns([1.2, 1.2, 1.5, 4])
    with c1:
        if st.button("👁️ Visualizar",
                     type="primary" if st.session_state['metas_modo']=='visualizar' else "secondary",
                     use_container_width=True, key="meta_btn_vis"):
            st.session_state['metas_modo'] = 'visualizar'
            st.rerun()
    with c2:
        if st.button("✏️ Editar",
                     type="primary" if st.session_state['metas_modo']=='editar' else "secondary",
                     use_container_width=True, key="meta_btn_edit"):
            st.session_state['metas_modo'] = 'editar'
            st.rerun()
    with c3:
        if st.button("📤 Upload CSV",
                     type="primary" if st.session_state['metas_modo']=='upload' else "secondary",
                     use_container_width=True, key="meta_btn_up"):
            st.session_state['metas_modo'] = 'upload'
            st.rerun()

    st.divider()

    # ── VISUALIZAR ────────────────────────────────────────────────────────────
    if st.session_state['metas_modo'] == 'visualizar':
        if df_metas.empty:
            st.info("Nenhuma meta cadastrada ainda. Use 'Editar' ou 'Upload CSV' para cadastrar.")
            return

        # Filtro por PDV
        pdvs = sorted(df_metas['pdv'].dropna().unique().tolist())
        pdv_f = st.selectbox("Filtrar PDV", ["Todos"] + [str(p) for p in pdvs], key="meta_pdv_vis")

        df_view = df_metas.copy()
        if pdv_f != "Todos":
            df_view = df_view[df_view['pdv'].astype(str) == pdv_f]

        # Monta tabela formatada
        linhas = []
        for _, row in df_view.iterrows():
            linha = {
                'Consultor': row.get('consultor', '—'),
                'PDV': str(row.get('pdv', '—')),
                'Tipo': '👔 Gerente' if row.get('is_gerente') else '👤 Consultor',
            }
            for col, label, tipo in COLUNAS_METAS:
                linha[label] = _fmt(row.get(col), tipo)
            linhas.append(linha)

        st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)

    # ── EDITAR ────────────────────────────────────────────────────────────────
    elif st.session_state['metas_modo'] == 'editar':
        if df_metas.empty:
            st.info("Nenhuma meta cadastrada. Faça o upload de um CSV primeiro para criar a base.")
            return

        st.caption("Selecione um consultor para editar suas metas individualmente.")

        pdvs = sorted(df_metas['pdv'].dropna().unique().tolist())
        col1, col2 = st.columns(2)
        with col1:
            pdv_e = st.selectbox("PDV", [str(p) for p in pdvs], key="meta_pdv_edit")
        with col2:
            cons_pdv = df_metas[df_metas['pdv'].astype(str) == pdv_e]['consultor'].tolist()
            cons_e = st.selectbox("Consultor", cons_pdv, key="meta_cons_edit")

        if cons_e:
            row = df_metas[
                (df_metas['pdv'].astype(str) == pdv_e) &
                (df_metas['consultor'] == cons_e)
            ].iloc[0]

            st.markdown(f"**Editando metas de: {cons_e} — PDV {pdv_e}**")
            st.divider()

            campos = {}
            cols = st.columns(3)
            for i, (col, label, tipo) in enumerate(COLUNAS_METAS):
                val_atual = row.get(col)
                try:
                    val_atual = float(val_atual) if val_atual is not None and not pd.isna(val_atual) else 0.0
                except (TypeError, ValueError):
                    val_atual = 0.0

                with cols[i % 3]:
                    novo_val = st.number_input(
                        label,
                        value=val_atual,
                        step=0.01 if tipo in ('pct', 'num') else 100.0,
                        format="%.4f" if tipo == 'pct' else "%.2f",
                        key=f"meta_edit_{col}_{cons_e}"
                    )
                    campos[col] = novo_val

            if st.button("💾 Salvar metas", type="primary", key="meta_salvar_edit"):
                if salvar_meta_linha(cons_e, int(pdv_e), campos):
                    st.success(f"Metas de {cons_e} salvas com sucesso!")
                    st.rerun()

    # ── UPLOAD CSV ────────────────────────────────────────────────────────────
    elif st.session_state['metas_modo'] == 'upload':
        st.markdown("**Upload do arquivo de metas**")
        st.caption(
            "Faça upload do arquivo Metas.xlsx ou CSV. "
            "Isso substituirá TODAS as metas cadastradas."
        )

        arq_meta = st.file_uploader(
            "Arquivo de metas", type=['xlsx', 'csv'], key="meta_upload_arq"
        )

        if arq_meta:
            try:
                if arq_meta.name.endswith('.csv'):
                    df_new = pd.read_csv(arq_meta)
                else:
                    df_new = pd.read_excel(arq_meta, engine='openpyxl')

                # Processa via módulo de leitura
                from modulos.leitura import processar_metas
                df_proc = processar_metas(df_new)

                st.markdown(f"**Preview — {len(df_proc)} consultores encontrados:**")
                st.dataframe(df_proc.head(5), use_container_width=True, hide_index=True)

                if st.button("⚠️ Confirmar substituição das metas", type="primary",
                             key="meta_confirmar_upload"):
                    if salvar_metas(df_proc):
                        st.success(f"✅ {len(df_proc)} metas salvas com sucesso!")
                        st.rerun()

            except Exception as e:
                st.error(f"Erro ao processar arquivo: {e}")

        # Download do template
        st.divider()
        st.caption("Não tem o arquivo? Baixe o template:")
        template_cols = ['Consultor', 'PDV', 'Receita', 'Boleto Médio', 'Itens por Boleto',
                         'Preço Médio', 'Penetração de Boleto Turbinado',
                         'Penetração de Boleto Promocional', 'Penetração de Receita Mobshop',
                         'Penetração de Boletos 1', 'Penetração de Boletos Fidelidade',
                         'Resgate Fidelidade', 'Conversão de Ação de Fluxo',
                         'Penetração de Cuidados Faciais', '% Boletos ID Cliente',
                         'Serviços', 'NPS']
        df_template = pd.DataFrame(columns=template_cols)
        csv_template = df_template.to_csv(index=False)
        st.download_button(
            "📥 Baixar template CSV",
            data=csv_template,
            file_name="template_metas.csv",
            mime="text/csv"
        )
