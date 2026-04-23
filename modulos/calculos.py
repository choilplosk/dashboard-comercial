"""
Módulo central de cálculos.
TODAS as fórmulas do dashboard estão aqui — nenhum cálculo ocorre nas páginas.
"""

import pandas as pd
import numpy as np
import re
import unicodedata
from typing import Optional


# ── Normalização de nomes ─────────────────────────────────────────────────────

def _norm_nome(nome: str) -> str:
    """
    Normaliza nome para join tolerante a variações de digitação:
    - Remove acentos
    - Converte para minúsculo
    - Remove letras duplicadas consecutivas (Rafaelle → Rafaele)
    """
    txt = re.sub(r'\s+', ' ', str(nome)).strip().lower()
    txt = ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')
    txt = re.sub(r'(.)\1+', r'\1', txt)
    return txt.strip()


# ── Normalização de escala de metas ──────────────────────────────────────────

def _normalizar_meta(meta_val, real_val) -> Optional[float]:
    """
    Garante que meta e realizado estão na mesma escala.
    Indicadores como pen_bt, conv_fluxo vêm em decimal (0-1).
    Se a meta foi cadastrada em percentual (>2) e o realizado em decimal,
    converte a meta dividindo por 100.
    """
    try:
        m = float(meta_val)
        r = float(real_val)
        # Se realizado está em decimal (0-1) e meta em percentual (>2), normaliza
        if 0 <= r <= 1 and m > 2:
            return m / 100
        return m
    except (TypeError, ValueError):
        return None


# ── Cálculos básicos ──────────────────────────────────────────────────────────

def atingimento(realizado, meta) -> Optional[float]:
    try:
        meta_f = float(meta)
        real_f = float(realizado)
        if meta_f == 0 or pd.isna(meta_f):
            return None
        return real_f / meta_f
    except (TypeError, ValueError):
        return None


def atingimento_pct(realizado, meta) -> Optional[float]:
    v = atingimento(realizado, meta)
    return round(v * 100, 2) if v is not None else None


def atingimento_com_escala(realizado, meta) -> Optional[float]:
    """
    Igual a atingimento() mas normaliza a escala da meta automaticamente.
    Evita erro quando meta foi cadastrada em % e realizado está em decimal.
    """
    try:
        meta_norm = _normalizar_meta(meta, realizado)
        if meta_norm is None:
            return None
        return atingimento(realizado, meta_norm)
    except Exception:
        return None


def cor_indicador(pct: Optional[float]) -> str:
    """pct é sempre decimal (ex: 1.05 = 105%). Multiplica por 100 sempre."""
    if pct is None or pd.isna(pct):
        return 'cinza'
    v = pct * 100
    if v >= 100:
        return 'verde'
    elif v >= 95:
        return 'amarelo'
    else:
        return 'vermelho'


def cor_indicador_invertido(pct: Optional[float]) -> str:
    """pct é sempre decimal (ex: 0.77 = 77%). Multiplica por 100 sempre."""
    if pct is None or pd.isna(pct):
        return 'cinza'
    v = pct * 100
    if v <= 100:
        return 'verde'
    elif v <= 110:
        return 'amarelo'
    else:
        return 'vermelho'


CORES = {
    'verde':    '#22c55e',
    'amarelo':  '#f59e0b',
    'vermelho': '#ef4444',
    'cinza':    '#9ca3af',
}

CORES_IAF = {
    'Diamante':        '#06b6d4',
    'Ouro':            '#f59e0b',
    'Prata':           '#94a3b8',
    'Bronze':          '#b45309',
    'Não classificado':'#6b7280',
}


TIPO_AGREGACAO = {
    'receita':            'soma',
    'qtd_boletos':        'soma',
    'qtd_itens':          'soma',
    'resgate_fidelidade': 'soma',
    'qtd_servicos':       'soma',
    'boleto_medio':       'media',
    'itens_por_boleto':   'media',
    'preco_medio':        'media',
    'pen_bt':             'media',
    'pen_bp':             'media',
    'pen_mobshop':        'media',
    'pen_boletos1':       'media',
    'pen_fidelidade':     'media',
    'conv_fluxo':         'media',
    'pen_facial':         'media',
    'pct_id_cliente':     'media',
}


def consolidar_indicadores(df: pd.DataFrame, agrupar_por: list = None) -> pd.DataFrame:
    colunas_num = [c for c in TIPO_AGREGACAO if c in df.columns]
    if agrupar_por:
        grupos = df.groupby(agrupar_por)
        resultado = {}
        for col in colunas_num:
            if TIPO_AGREGACAO[col] == 'soma':
                resultado[col] = grupos[col].sum()
            else:
                resultado[col] = grupos[col].mean()
        return pd.DataFrame(resultado).reset_index()
    else:
        resultado = {}
        for col in colunas_num:
            if TIPO_AGREGACAO[col] == 'soma':
                resultado[col] = df[col].sum()
            else:
                resultado[col] = df[col].mean()
        return pd.DataFrame([resultado])


def montar_base_consultores(
    df_cons: pd.DataFrame,
    df_metas: pd.DataFrame,
    df_serv: pd.DataFrame,
    df_trein: pd.DataFrame,
    df_id: pd.DataFrame,
) -> pd.DataFrame:
    df_cons = df_cons.copy()
    df_metas = df_metas.copy() if df_metas is not None else pd.DataFrame()

    # Chave normalizada — tolerante a variações de digitação (ex: Rafaelle vs Rafaele)
    df_cons['_key'] = df_cons['consultor'].apply(_norm_nome) + '_' + df_cons['pdv'].astype(str)

    if not df_metas.empty and 'consultor' in df_metas.columns and 'pdv' in df_metas.columns:
        df_metas['_key'] = df_metas['consultor'].apply(_norm_nome) + '_' + df_metas['pdv'].astype(str)
        colunas_drop = [c for c in ['consultor', 'pdv'] if c in df_metas.columns]
        base = df_cons.merge(
            df_metas.drop(columns=colunas_drop),
            on='_key',
            how='left'
        )
    else:
        base = df_cons.copy()
        base['_key'] = df_cons['_key']

    if df_serv is not None and not df_serv.empty:
        serv_agg = (
            df_serv.groupby(['consultor', 'pdv'])['qtd_servicos']
            .sum()
            .reset_index()
            .rename(columns={'qtd_servicos': 'servicos_real'})
        )
        serv_agg['_key'] = serv_agg['consultor'].apply(_norm_nome) + '_' + serv_agg['pdv'].astype(str)
        base = base.merge(serv_agg[['_key', 'servicos_real']], on='_key', how='left')
    else:
        base['servicos_real'] = None

    if df_trein is not None and not df_trein.empty:
        trein_agg = df_trein.groupby(['consultor', 'pdv']).agg(
            treinamento_concluido=('treinamento_concluido', 'max'),
            **({'treinamento_pct': ('treinamento_pct', 'max')} if 'treinamento_pct' in df_trein.columns else {})
        ).reset_index()
        trein_agg['_key'] = trein_agg['consultor'].apply(_norm_nome) + '_' + trein_agg['pdv'].astype(str)
        merge_cols = ['_key', 'treinamento_concluido'] + (['treinamento_pct'] if 'treinamento_pct' in trein_agg.columns else [])
        base = base.merge(trein_agg[merge_cols], on='_key', how='left')
    else:
        base['treinamento_concluido'] = False
        base['treinamento_pct'] = 0.0

    if df_id is not None and not df_id.empty:
        id_agg = df_id.groupby(['consultor', 'pdv'])['pct_id_cliente_iaf'].mean().reset_index()
        id_agg['_key'] = id_agg['consultor'].apply(_norm_nome) + '_' + id_agg['pdv'].astype(str)
        base = base.merge(id_agg[['_key', 'pct_id_cliente_iaf']], on='_key', how='left')
    else:
        base['pct_id_cliente_iaf'] = None

    base = base.drop(columns=['_key'])
    if 'is_gerente' in base.columns:
        base['is_gerente'] = base['is_gerente'].fillna(False).astype(bool)
    return base


def calcular_atingimentos(base: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona colunas de atingimento para cada par realizado/meta.
    Usa atingimento_com_escala() para normalizar metas cadastradas em % vs decimal.
    """
    pares = [
        ('receita',           'meta_receita'),
        ('boleto_medio',      'meta_boleto_medio'),
        ('itens_por_boleto',  'meta_itens_boleto'),
        ('preco_medio',       'meta_preco_medio'),
        ('pen_bt',            'meta_pen_bt'),
        ('pen_bp',            'meta_pen_bp'),
        ('pen_mobshop',       'meta_pen_mobshop'),
        ('pen_boletos1',      'meta_pen_boletos1'),
        ('pen_fidelidade',    'meta_pen_fidelidade'),
        ('resgate_fidelidade','meta_resgate_fidelidade'),
        ('conv_fluxo',        'meta_conv_fluxo'),
        ('pen_facial',        'meta_pen_facial'),
        ('pct_id_cliente_iaf','meta_pct_id_cliente'),
        ('servicos_real',     'meta_servicos'),
    ]

    df = base.copy()
    for real_col, meta_col in pares:
        nome_at = f"at_{real_col.replace('_real', '').replace('_iaf', '')}"
        if real_col in df.columns and meta_col in df.columns:
            df[nome_at] = df.apply(
                lambda r: atingimento_com_escala(r.get(real_col), r.get(meta_col)), axis=1
            )
        else:
            df[nome_at] = None

    return df


def resumo_consolidado(base: pd.DataFrame, metas: pd.DataFrame) -> dict:
    df = base[~base.get('is_gerente', pd.Series(False, index=base.index)).fillna(False).astype(bool)].copy()

    def soma(col):
        return df[col].sum() if col in df.columns else None

    def media(col):
        return df[col].mean() if col in df.columns else None

    def media_sem_zero(col):
        if col not in df.columns: return None
        vals = pd.to_numeric(df[col], errors='coerce')
        vals = vals[vals > 0]
        return vals.mean() if not vals.empty else None

    def meta_soma(col):
        if metas.empty: return None
        mask = metas['is_gerente'].fillna(False).astype(bool) if 'is_gerente' in metas.columns else pd.Series(False, index=metas.index)
        m = metas[~mask]
        return pd.to_numeric(m[col], errors='coerce').sum() if col in m.columns else None

    def meta_media(col):
        if metas.empty: return None
        mask = metas['is_gerente'].fillna(False).astype(bool) if 'is_gerente' in metas.columns else pd.Series(False, index=metas.index)
        m = metas[~mask]
        return pd.to_numeric(m[col], errors='coerce').mean() if col in m.columns else None

    indicadores = {
        'Receita':              (soma('receita'),            meta_soma('meta_receita')),
        'Qtd. Boletos':         (soma('qtd_boletos'),        None),
        'Boleto Médio':         (media('boleto_medio'),      meta_media('meta_boleto_medio')),
        'Itens/Boleto':         (media('itens_por_boleto'),  meta_media('meta_itens_boleto')),
        'Preço Médio':          (media('preco_medio'),       meta_media('meta_preco_medio')),
        'Pen. BT':              (media('pen_bt'),            meta_media('meta_pen_bt')),
        'Pen. BP':              (media('pen_bp'),            meta_media('meta_pen_bp')),
        'Pen. Mobshop':         (media('pen_mobshop'),       meta_media('meta_pen_mobshop')),
        'Pen. Boletos 1':       (media('pen_boletos1'),      meta_media('meta_pen_boletos1')),
        'Pen. Fidelidade':      (media('pen_fidelidade'),    meta_media('meta_pen_fidelidade')),
        'Resgate Fidelidade':   (media('resgate_fidelidade'), meta_media('meta_resgate_fidelidade')),
        'Conv. Fluxo':          (media('conv_fluxo'),        meta_media('meta_conv_fluxo')),
        'Pen. Facial':          (media('pen_facial'),        meta_media('meta_pen_facial')),
        '% ID Cliente':         (media_sem_zero('pct_id_cliente_iaf'), meta_media('meta_pct_id_cliente')),
        'Serviços':             (soma('servicos_real'),      meta_soma('meta_servicos')),
    }

    resultado = {}
    for nome, (real, meta) in indicadores.items():
        at = atingimento(real, meta) if real is not None else None
        resultado[nome] = {
            'realizado': real,
            'meta': meta,
            'atingimento': at,
            'cor': cor_indicador(at),
        }
    return resultado


def fmt_brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def fmt_pct(v, casas=1) -> str:
    try:
        return f"{float(v) * 100:.{casas}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def fmt_pct_direto(v, casas=1) -> str:
    try:
        return f"{float(v):.{casas}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def fmt_num(v, casas=2) -> str:
    try:
        return f"{float(v):.{casas}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"
