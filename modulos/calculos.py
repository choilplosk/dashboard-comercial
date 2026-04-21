"""
Módulo central de cálculos.
TODAS as fórmulas do dashboard estão aqui — nenhum cálculo ocorre nas páginas.
Cada função tem nome descritivo e comentário explicando a lógica.
Para corrigir um cálculo errado: edite só este arquivo.
"""

import pandas as pd
import numpy as np
from typing import Optional


# ── Cálculos básicos ──────────────────────────────────────────────────────────

def atingimento(realizado, meta) -> Optional[float]:
    """
    Calcula o % de atingimento: realizado / meta.
    Retorna None se meta for zero, nula ou não numérica.
    Resultado em decimal (ex: 1.05 = 105%).
    """
    try:
        meta_f = float(meta)
        real_f = float(realizado)
        if meta_f == 0 or pd.isna(meta_f):
            return None
        return real_f / meta_f
    except (TypeError, ValueError):
        return None


def atingimento_pct(realizado, meta) -> Optional[float]:
    """
    Igual ao atingimento(), mas retorna em percentual (ex: 105.0 para 105%).
    """
    v = atingimento(realizado, meta)
    return round(v * 100, 2) if v is not None else None


def cor_indicador(pct: Optional[float]) -> str:
    """
    Retorna a cor semáforo baseada no % de atingimento.
    pct deve estar em decimal (1.0 = 100%) ou percentual (100.0).
    A função detecta automaticamente a escala.

    Verde:    >= 100%
    Amarelo:  >= 95% e < 100%
    Vermelho: < 95%
    Cinza:    sem dado
    """
    if pct is None or pd.isna(pct):
        return 'cinza'
    v = pct * 100 if pct <= 2 else pct
    if v >= 100:
        return 'verde'
    elif v >= 95:
        return 'amarelo'
    else:
        return 'vermelho'


def cor_indicador_invertido(pct: Optional[float]) -> str:
    """
    Lógica de cor INVERTIDA — usado para indicadores onde menor é melhor.
    Ex: Resgate Fidelidade — abaixo da meta = verde, acima = vermelho.
    pct = realizado / meta (em decimal).

    Verde:    <= 100% (está abaixo ou igual à meta — bom)
    Amarelo:  entre 100% e 110%
    Vermelho: > 110% (está acima da meta — ruim)
    Cinza:    sem dado
    """
    if pct is None or pd.isna(pct):
        return 'cinza'
    v = pct * 100 if pct <= 2 else pct
    if v <= 100:
        return 'verde'
    elif v <= 110:
        return 'amarelo'
    else:
        return 'vermelho'


# Mapa de cores para uso no Plotly e CSS
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


# ── Consolidação de indicadores ───────────────────────────────────────────────

# Indica como cada indicador deve ser agregado ao consolidar PDVs ou equipes.
# 'soma'  = soma direta (volumes absolutos)
# 'media' = média simples
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
    """
    Consolida indicadores aplicando soma ou média conforme TIPO_AGREGACAO.
    Se agrupar_por for fornecido (ex: ['pdv']), agrupa por esses campos.
    Se None, retorna uma linha com totais de toda a equipe.
    """
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


# ── Merge de dados ────────────────────────────────────────────────────────────

def montar_base_consultores(
    df_cons: pd.DataFrame,
    df_metas: pd.DataFrame,
    df_serv: pd.DataFrame,
    df_trein: pd.DataFrame,
    df_id: pd.DataFrame,
) -> pd.DataFrame:
    """
    Junta todos os DataFrames em uma base única por consultor+PDV.
    Essa é a base de dados usada por todas as páginas do dashboard.
    """
    # Chave de join: consultor (normalizado) + PDV
    df_cons = df_cons.copy()
    df_metas = df_metas.copy() if df_metas is not None else pd.DataFrame()

    df_cons['_key'] = df_cons['consultor'].str.strip().str.upper() + '_' + df_cons['pdv'].astype(str)

    # Metas podem estar vazias ou sem coluna consultor (ex: primeira vez sem metas)
    if not df_metas.empty and 'consultor' in df_metas.columns and 'pdv' in df_metas.columns:
        df_metas['_key'] = df_metas['consultor'].str.strip().str.upper() + '_' + df_metas['pdv'].astype(str)
        colunas_drop = [c for c in ['consultor', 'pdv'] if c in df_metas.columns]
        base = df_cons.merge(
            df_metas.drop(columns=colunas_drop),
            on='_key',
            how='left'
        )
    else:
        base = df_cons.copy()
        base['_key'] = df_cons['_key']

    # Serviços agregados por consultor + PDV
    if df_serv is not None and not df_serv.empty:
        serv_agg = (
            df_serv.groupby(['consultor', 'pdv'])['qtd_servicos']
            .sum()
            .reset_index()
            .rename(columns={'qtd_servicos': 'servicos_real'})
        )
        serv_agg['_key'] = serv_agg['consultor'].str.strip().str.upper() + '_' + serv_agg['pdv'].astype(str)
        base = base.merge(serv_agg[['_key', 'servicos_real']], on='_key', how='left')
    else:
        base['servicos_real'] = None

    # Treinamentos: percentual e flag de conclusão (por consultor + PDV)
    if df_trein is not None and not df_trein.empty:
        cols_trein = ['consultor', 'pdv', 'treinamento_concluido']
        if 'treinamento_pct' in df_trein.columns:
            cols_trein.append('treinamento_pct')
        trein_agg = df_trein.groupby(['consultor', 'pdv']).agg(
            treinamento_concluido=('treinamento_concluido', 'max'),
            **({'treinamento_pct': ('treinamento_pct', 'max')} if 'treinamento_pct' in df_trein.columns else {})
        ).reset_index()
        trein_agg['_key'] = trein_agg['consultor'].str.strip().str.upper() + '_' + trein_agg['pdv'].astype(str)
        merge_cols = ['_key', 'treinamento_concluido'] + (['treinamento_pct'] if 'treinamento_pct' in trein_agg.columns else [])
        base = base.merge(trein_agg[merge_cols], on='_key', how='left')
    else:
        base['treinamento_concluido'] = False
        base['treinamento_pct'] = 0.0

    # ID Cliente: % boletos ID válidos
    if df_id is not None and not df_id.empty:
        id_agg = df_id.groupby(['consultor', 'pdv'])['pct_id_cliente_iaf'].mean().reset_index()
        id_agg['_key'] = id_agg['consultor'].str.strip().str.upper() + '_' + id_agg['pdv'].astype(str)
        base = base.merge(id_agg[['_key', 'pct_id_cliente_iaf']], on='_key', how='left')
    else:
        base['pct_id_cliente_iaf'] = None

    base = base.drop(columns=['_key'])
    # Garante que is_gerente é sempre booleano, nunca float/NaN
    if 'is_gerente' in base.columns:
        base['is_gerente'] = base['is_gerente'].fillna(False).astype(bool)
    return base


def calcular_atingimentos(base: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona colunas de atingimento (%) para cada par realizado/meta.
    Nomes seguem o padrão: at_<indicador>
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
                lambda r: atingimento(r.get(real_col), r.get(meta_col)), axis=1
            )
        else:
            df[nome_at] = None

    return df


# ── Consolidação do Resumo (Aba 1) ────────────────────────────────────────────

def resumo_consolidado(base: pd.DataFrame, metas: pd.DataFrame) -> dict:
    """
    Calcula os indicadores consolidados de toda a rede.
    Retorna dicionário com realizado, meta e atingimento de cada indicador.
    Gerentes são excluídos.
    """
    df = base[~base.get('is_gerente', pd.Series(False, index=base.index)).fillna(False).astype(bool)].copy()

    def soma(col):
        return df[col].sum() if col in df.columns else None

    def media(col):
        return df[col].mean() if col in df.columns else None

    def media_sem_zero(col):
        """Média excluindo zeros — usado para indicadores onde zero = ausência de dado."""
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
        '% ID Cliente':         (media_sem_zero('pct_id_cliente_iaf'),meta_media('meta_pct_id_cliente')),
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


# ── Formatação ────────────────────────────────────────────────────────────────

def fmt_brl(v) -> str:
    """Formata valor em Reais brasileiros."""
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def fmt_pct(v, casas=1) -> str:
    """Formata valor decimal como percentual (0.95 → '95,0%')."""
    try:
        return f"{float(v) * 100:.{casas}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def fmt_pct_direto(v, casas=1) -> str:
    """Formata valor já em percentual (95.0 → '95,0%')."""
    try:
        return f"{float(v):.{casas}f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def fmt_num(v, casas=2) -> str:
    """Formata número com casas decimais."""
    try:
        return f"{float(v):.{casas}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"
