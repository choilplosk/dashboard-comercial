"""
Módulo de histórico.
Salva e recupera snapshots diários dos dados processados.
Cada upload gera um arquivo AAAA-MM-DD.json na pasta dados/historico/.
Snapshots nunca são sobrescritos — apenas acumulados.
"""

import json
import os
import pandas as pd
from datetime import datetime, date

CAMINHO_HISTORICO = os.path.join(os.path.dirname(__file__), '..', 'dados', 'historico')


def _caminho_snapshot(data: date) -> str:
    return os.path.join(CAMINHO_HISTORICO, f"{data.strftime('%Y-%m-%d')}.json")


def salvar_snapshot(base: pd.DataFrame, data: date = None):
    """
    Salva o snapshot dos dados processados para a data informada.
    Se data não for informada, usa hoje.
    Se já existir snapshot para essa data, substitui (dados mais recentes do dia).
    """
    if data is None:
        data = date.today()

    os.makedirs(CAMINHO_HISTORICO, exist_ok=True)

    # Converte DataFrame para JSON serializável
    dados = base.copy()
    for col in dados.select_dtypes(include=['Int64', 'int64']).columns:
        dados[col] = dados[col].astype(object).where(dados[col].notna(), None)

    snapshot = {
        'data': data.isoformat(),
        'gerado_em': datetime.now().isoformat(),
        'registros': dados.to_dict(orient='records')
    }

    with open(_caminho_snapshot(data), 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, default=str)


def carregar_snapshot(data: date) -> pd.DataFrame | None:
    """Carrega o snapshot de uma data específica. Retorna None se não existir."""
    caminho = _caminho_snapshot(data)
    if not os.path.exists(caminho):
        return None

    with open(caminho, 'r', encoding='utf-8') as f:
        snapshot = json.load(f)

    return pd.DataFrame(snapshot['registros'])


def listar_snapshots() -> list[date]:
    """Retorna lista de datas com snapshots disponíveis, em ordem decrescente."""
    if not os.path.exists(CAMINHO_HISTORICO):
        return []

    datas = []
    for arquivo in os.listdir(CAMINHO_HISTORICO):
        if arquivo.endswith('.json'):
            try:
                datas.append(date.fromisoformat(arquivo.replace('.json', '')))
            except ValueError:
                pass
    return sorted(datas, reverse=True)


def seletor_data_sidebar(label: str = "📅 Período de referência") -> date | None:
    """
    Widget de seleção de data histórica para a sidebar.
    Retorna a data selecionada ou None se não houver histórico.
    """
    import streamlit as st

    datas = listar_snapshots()
    if not datas:
        return None

    opcoes = {d.strftime('%d/%m/%Y'): d for d in datas}
    escolha = st.sidebar.selectbox(label, list(opcoes.keys()))
    return opcoes[escolha]
