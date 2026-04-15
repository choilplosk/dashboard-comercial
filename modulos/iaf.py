"""
Módulo do IAF (Instrumento de Avaliação de Franquia).
Lógica de pontuação, classificação e configuração editável com salvamento persistente.
"""

import json
import os
import pandas as pd
from typing import Optional
from modulos.calculos import atingimento, CORES_IAF

CAMINHO_CONFIG = os.path.join(os.path.dirname(__file__), '..', 'dados', 'iaf_config.json')

# ── Configuração padrão do IAF ────────────────────────────────────────────────

CONFIG_PADRAO = {
    "indicadores": [
        {
            "id": "receita",
            "nome": "Receita",
            "pontos": 100,
            "coluna_real": "receita",
            "coluna_meta": "meta_receita",
            "tipo": "automatico",
            "logica": "padrao"   # padrao = <95%→0, 95-99,9%→50%, ≥100%→100%
        },
        {
            "id": "pen_bt",
            "nome": "Penetração Boleto Turbinado (BT)",
            "pontos": 20,
            "coluna_real": "pen_bt",
            "coluna_meta": "meta_pen_bt",
            "tipo": "automatico",
            "logica": "padrao"
        },
        {
            "id": "pen_bp",
            "nome": "Penetração Boleto Promocional (BP)",
            "pontos": 20,
            "coluna_real": "pen_bp",
            "coluna_meta": "meta_pen_bp",
            "tipo": "automatico",
            "logica": "padrao"
        },
        {
            "id": "pen_facial",
            "nome": "Penetração Cuidados Faciais",
            "pontos": 25,
            "coluna_real": "pen_facial",
            "coluna_meta": "meta_pen_facial",
            "tipo": "automatico",
            "logica": "padrao"
        },
        {
            "id": "resgate_fidelidade",
            "nome": "Resgate Fidelidade",
            "pontos": 25,
            "coluna_real": "resgate_fidelidade",
            "coluna_meta": "meta_resgate_fidelidade",
            "tipo": "automatico",
            "logica": "padrao"
        },
        {
            "id": "servicos",
            "nome": "Serviços em Loja",
            "pontos": 35,
            "coluna_real": "servicos_real",
            "coluna_meta": "meta_servicos",
            "tipo": "automatico",
            "logica": "padrao"
        },
        {
            "id": "treinamentos",
            "nome": "Treinamentos",
            "pontos": 30,
            "coluna_real": "treinamento_concluido",
            "coluna_meta": None,
            "tipo": "automatico",
            "logica": "tudo_ou_nada"   # 30 pts se True, 0 se False
        },
        {
            "id": "id_cliente",
            "nome": "ID Cliente (% Boletos Válidos)",
            "pontos": 20,
            "coluna_real": "pct_id_cliente_iaf",
            "coluna_meta": "meta_pct_id_cliente",
            "tipo": "automatico",
            "logica": "padrao"
        },
        {
            "id": "nps",
            "nome": "NPS",
            "pontos": 35,
            "coluna_real": "nps_real",       # valor inserido manualmente por PDV
            "coluna_meta": "meta_nps",
            "tipo": "manual",
            "logica": "padrao"
        },
    ],
    "faixas": [
        {"nome": "Diamante",        "min_pct": 95.0},
        {"nome": "Ouro",            "min_pct": 85.0},
        {"nome": "Prata",           "min_pct": 75.0},
        {"nome": "Bronze",          "min_pct": 65.0},
        {"nome": "Não classificado","min_pct": 0.0},
    ]
}


# ── Persistência ──────────────────────────────────────────────────────────────

def carregar_config() -> dict:
    """Carrega configuração do IAF salva. Se não existir, usa o padrão."""
    if os.path.exists(CAMINHO_CONFIG):
        with open(CAMINHO_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    return CONFIG_PADRAO.copy()


def salvar_config(config: dict):
    """Salva configuração do IAF no disco."""
    os.makedirs(os.path.dirname(CAMINHO_CONFIG), exist_ok=True)
    with open(CAMINHO_CONFIG, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ── Cálculo do IAF ────────────────────────────────────────────────────────────

def pontos_indicador(real, meta, pontos_max: float, logica: str) -> float:
    """
    Calcula os pontos de um indicador baseado na lógica configurada.

    Lógica 'padrao':
      - < 95% da meta  → 0 pontos
      - 95% a 99,9%    → 50% dos pontos
      - >= 100%        → 100% dos pontos

    Lógica 'tudo_ou_nada':
      - True/1/qualquer valor positivo → 100% dos pontos
      - False/0/nulo                   → 0 pontos
    """
    if logica == 'tudo_ou_nada':
        if real is None or pd.isna(real):
            return 0.0
        return float(pontos_max) if bool(real) else 0.0

    at = atingimento(real, meta)
    if at is None:
        return 0.0

    if at >= 1.0:
        return float(pontos_max)
    elif at >= 0.95:
        return float(pontos_max) * 0.5
    else:
        return 0.0


def calcular_iaf_linha(row: pd.Series, config: dict) -> dict:
    """
    Calcula o IAF completo de uma linha (consultor).
    Retorna dicionário com pontuação total, % IAF, classificação,
    falta para próxima faixa e detalhamento por indicador.
    """
    indicadores = config['indicadores']
    total_pontos_possiveis = sum(ind['pontos'] for ind in indicadores)

    detalhes = []
    pontos_obtidos = 0.0

    for ind in indicadores:
        real = row.get(ind['coluna_real'])
        meta = row.get(ind['coluna_meta']) if ind['coluna_meta'] else None
        pts = pontos_indicador(real, meta, ind['pontos'], ind['logica'])
        at  = atingimento(real, meta) if ind['logica'] != 'tudo_ou_nada' else None

        pontos_obtidos += pts
        detalhes.append({
            'id':        ind['id'],
            'nome':      ind['nome'],
            'pontos_max': ind['pontos'],
            'pontos':    pts,
            'atingido':  pts >= ind['pontos'],
            'parcial':   0 < pts < ind['pontos'],
            'atingimento': at,
        })

    pct_iaf = (pontos_obtidos / total_pontos_possiveis * 100) if total_pontos_possiveis > 0 else 0.0
    classificacao = _classificar(pct_iaf, config['faixas'])
    falta = _falta_proxima_faixa(pct_iaf, total_pontos_possiveis, config['faixas'])
    entregas = sum(1 for d in detalhes if d['atingido'])

    return {
        'pontos':            round(pontos_obtidos, 1),
        'pontos_possiveis':  total_pontos_possiveis,
        'pct_iaf':           round(pct_iaf, 2),
        'classificacao':     classificacao,
        'falta_pontos':      round(falta, 1) if falta else 0.0,
        'entregas':          entregas,
        'total_indicadores': len(indicadores),
        'detalhes':          detalhes,
    }


def _classificar(pct_iaf: float, faixas: list) -> str:
    """Determina a classificação com base no % IAF e nas faixas configuradas."""
    for faixa in sorted(faixas, key=lambda f: f['min_pct'], reverse=True):
        if pct_iaf >= faixa['min_pct']:
            return faixa['nome']
    return 'Não classificado'


def _falta_proxima_faixa(pct_atual: float, total_pts: float, faixas: list) -> Optional[float]:
    """
    Calcula quantos pontos faltam para subir de faixa.
    Ex: pct_atual=68% (Bronze) → próxima faixa é Prata (75%) → falta (75-68)/100 * total_pts pontos.
    Retorna None se já está na faixa máxima.
    """
    faixas_ord = sorted(faixas, key=lambda f: f['min_pct'])
    proxima_pct = None

    for faixa in faixas_ord:
        if faixa['min_pct'] > pct_atual:
            proxima_pct = faixa['min_pct']
            break

    if proxima_pct is None:
        return None  # Já é Diamante

    return ((proxima_pct - pct_atual) / 100) * total_pts


def calcular_iaf_base(base: pd.DataFrame, nps_por_pdv: dict) -> pd.DataFrame:
    """
    Aplica o cálculo do IAF a toda a base de consultores.
    nps_por_pdv: dicionário {pdv: valor_nps} inserido manualmente.
    Gerentes e consultores sem meta são excluídos do cálculo.
    """
    config = carregar_config()

    # Injeta NPS por PDV
    df = base.copy()
    df['nps_real'] = df['pdv'].astype(str).map(
        {str(k): v for k, v in nps_por_pdv.items()}
    )

    resultados = []
    for _, row in df.iterrows():
        if row.get('is_gerente') or row.get('meta_receita') is None:
            resultados.append({
                'pontos': None, 'pct_iaf': None,
                'classificacao': 'Sem meta' if not row.get('is_gerente') else 'Gerente',
                'falta_pontos': None, 'entregas': None,
                'total_indicadores': None, 'detalhes': [],
            })
        else:
            resultados.append(calcular_iaf_linha(row, config))

    df_iaf = pd.DataFrame(resultados)
    return pd.concat([df.reset_index(drop=True), df_iaf.reset_index(drop=True)], axis=1)


# ── Ranking de gerentes ───────────────────────────────────────────────────────

def consolidar_gerentes(base: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida resultados dos gerentes.
    Gerentes com mais de uma loja têm resultados consolidados por média simples
    para taxas e soma para volumes.
    """
    from modulos.calculos import TIPO_AGREGACAO, atingimento

    gerentes = base[base.get('is_gerente', pd.Series(False, index=base.index)) == True].copy()
    if gerentes.empty:
        # Tenta identificar gerentes por ausência de meta de receita com valor numérico
        return pd.DataFrame()

    colunas_num = [c for c in TIPO_AGREGACAO if c in gerentes.columns]
    agg = {}
    for col in colunas_num:
        if TIPO_AGREGACAO[col] == 'soma':
            agg[col] = 'sum'
        else:
            agg[col] = 'mean'

    resultado = gerentes.groupby('consultor').agg(agg).reset_index()
    resultado['pdvs'] = gerentes.groupby('consultor')['pdv'].apply(
        lambda x: ', '.join(x.astype(str).unique())
    ).values

    # Atingimento de receita consolidado
    metas_ger = gerentes.groupby('consultor')['meta_receita'].sum().reset_index()
    metas_ger.columns = ['consultor', 'meta_receita_total']
    resultado = resultado.merge(metas_ger, on='consultor', how='left')
    resultado['at_receita_gerente'] = resultado.apply(
        lambda r: atingimento(r.get('receita'), r.get('meta_receita_total')), axis=1
    )
    return resultado
