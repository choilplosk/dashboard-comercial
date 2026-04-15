"""
Módulo de NPS.
Gerencia o cadastro e persistência do NPS por PDV.
O NPS é inserido manualmente — não vem dos arquivos CSV.
"""

import json
import os

CAMINHO_NPS = os.path.join(os.path.dirname(__file__), '..', 'dados', 'nps.json')


def carregar_nps() -> dict:
    """Retorna dicionário {pdv_str: valor_nps}."""
    if not os.path.exists(CAMINHO_NPS):
        return {}
    with open(CAMINHO_NPS, 'r', encoding='utf-8') as f:
        return json.load(f)


def salvar_nps(nps_dict: dict):
    """Salva dicionário de NPS por PDV."""
    os.makedirs(os.path.dirname(CAMINHO_NPS), exist_ok=True)
    with open(CAMINHO_NPS, 'w', encoding='utf-8') as f:
        json.dump(nps_dict, f, ensure_ascii=False, indent=2)


def widget_nps(pdvs: list) -> dict:
    """
    Exibe campos de entrada de NPS para cada PDV.
    Retorna dicionário atualizado.
    Deve ser chamado dentro de um expander ou container na Aba 2.
    """
    import streamlit as st

    nps_atual = carregar_nps()
    nps_novo = {}
    alterado = False

    st.markdown("**Lançar NPS por PDV**")
    st.caption("O NPS é inserido manualmente e representa o resultado da loja.")

    cols = st.columns(min(len(pdvs), 4))
    for i, pdv in enumerate(pdvs):
        pdv_str = str(pdv)
        valor_atual = nps_atual.get(pdv_str)
        with cols[i % 4]:
            novo_valor = st.number_input(
                f"PDV {pdv}",
                min_value=0.0,
                max_value=100.0,
                value=float(valor_atual) if valor_atual is not None else 0.0,
                step=0.1,
                format="%.1f",
                key=f"nps_{pdv}"
            )
            nps_novo[pdv_str] = novo_valor
            if valor_atual != novo_valor:
                alterado = True

    if st.button("💾 Salvar NPS", key="btn_salvar_nps"):
        salvar_nps(nps_novo)
        st.success("NPS salvo com sucesso.")
        alterado = False

    return nps_novo
