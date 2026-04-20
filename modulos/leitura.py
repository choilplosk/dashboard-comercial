"""
Módulo de leitura de arquivos.
Identifica automaticamente cada arquivo pelo conteúdo interno.
Não depende do nome do arquivo.
Assinaturas validadas contra os arquivos reais do cliente.
"""

import pandas as pd
import re
import unicodedata
import streamlit as st


# ── Normalização ──────────────────────────────────────────────────────────────

def _n(texto: str) -> str:
    """Remove acentos, espaços extras e converte para minúsculo."""
    txt = re.sub(r'\s+', ' ', str(texto)).strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', txt)
        if unicodedata.category(c) != 'Mn'
    )

def _cols(df: pd.DataFrame) -> set:
    """Retorna conjunto de colunas normalizadas."""
    return set(_n(c) for c in df.columns if c is not None)


# ── Assinaturas ───────────────────────────────────────────────────────────────
# Ordem importa: tipos mais específicos primeiro.
# Validadas contra os arquivos reais — não alterar sem testar.

ASSINATURAS = {
    'pdv': {
        'obrigatorias': {'pdv', 'receita', 'vs. meta pef'},
        'descricao': 'Resultados por PDV',
    },
    'consultor': {
        'obrigatorias': {'consultor', 'pdv', 'receita', 'vs. periodo anterior', 'quantidade de boletos'},
        'descricao': 'Resultados por Consultor',
    },
    'servicos': {
        'obrigatorias': {'pdv', 'consultor', 'quantidade de servicos completos'},
        'descricao': 'Serviços em Loja',
    },
    'treinamentos': {
        'obrigatorias': {'nome', 'cargo', 'codigo de pdv'},
        'descricao': 'Treinamentos',
    },
    'id_cliente': {
        'obrigatorias': {'pdv', 'consultor', 'atendimentos no id cliente'},
        'descricao': 'ID Cliente',
    },
}


def _identificar(df: pd.DataFrame) -> str | None:
    cols = _cols(df)
    for tipo, assin in ASSINATURAS.items():
        if assin['obrigatorias'].issubset(cols):
            return tipo
    return None


# ── Leitura de arquivo ────────────────────────────────────────────────────────

def _ler(arquivo) -> pd.DataFrame | None:
    nome = arquivo.name.lower()
    try:
        if nome.endswith('.csv'):
            for enc in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    arquivo.seek(0)
                    return pd.read_csv(arquivo, encoding=enc, sep=None, engine='python')
                except UnicodeDecodeError:
                    continue
        elif nome.endswith(('.xlsx', '.xlsm', '.xls')):
            arquivo.seek(0)
            return pd.read_excel(arquivo, engine='openpyxl')
    except Exception:
        pass
    return None


# ── Processadores ─────────────────────────────────────────────────────────────

def processar_consultor(df: pd.DataFrame) -> pd.DataFrame:
    # Remove linhas de cabeçalho duplo e totais
    df = df[~df.iloc[:, 0].astype(str).str.strip().isin(
        ['Tipo de Receita', 'TOTAL', 'Consultor', '', 'nan']
    )].copy()
    df = df[df.iloc[:, 0].notna()].reset_index(drop=True)

    cols = list(df.columns)

    # Mapeamento posicional — cada indicador ocupa 2 colunas (valor + vs período anterior)
    mapa = {}
    for i, c in enumerate(cols):
        cn = _n(c)
        if cn == 'consultor': mapa[c] = 'consultor'
        elif cn == 'pdv':     mapa[c] = 'pdv'

    pos = {
        2:  'receita',
        4:  'qtd_boletos',
        6:  'boleto_medio',
        8:  'qtd_itens',
        10: 'itens_por_boleto',
        12: 'preco_medio',
        14: 'pen_bt',
        16: 'pen_bp',
        20: 'pen_mobshop',
        22: 'pen_boletos1',
        24: 'pen_fidelidade',
        26: 'resgate_fidelidade',
        28: 'conv_fluxo',
        30: 'pen_facial',
        32: 'pct_id_cliente',
    }
    for i, nome in pos.items():
        if i < len(cols):
            mapa[cols[i]] = nome

    df = df.rename(columns=mapa)
    manter = [v for v in mapa.values() if v in df.columns]
    df = df[manter].copy()

    for c in df.columns:
        if c != 'consultor':
            df[c] = pd.to_numeric(df[c], errors='coerce')

    df['pdv'] = df['pdv'].astype('Int64')
    df['consultor'] = df['consultor'].astype(str).str.strip().str.title()
    return df


def processar_pdv(df: pd.DataFrame) -> pd.DataFrame:
    col0 = df.columns[0]
    df = df[~df[col0].astype(str).str.strip().isin(
        ['Tipo de Receita', 'TOTAL', 'PDV', '', 'nan']
    )].copy()
    df = df[df[col0].notna()].reset_index(drop=True)

    cols = list(df.columns)
    pos = {
        0:  'pdv',
        1:  'receita',
        3:  'receita_vs_ly',
        4:  'qtd_boletos',
        7:  'boleto_medio',
        9:  'boleto_medio_vs_ly',
        10: 'qtd_itens',
        13: 'itens_por_boleto',
        15: 'itens_por_boleto_vs_ly',
        16: 'preco_medio',
        18: 'preco_medio_vs_ly',
        19: 'pen_bt',
        22: 'pen_bp',
        28: 'pen_mobshop',
        31: 'pen_boletos1',
        34: 'pen_fidelidade',
        37: 'resgate_fidelidade',
        40: 'conv_fluxo',
        43: 'pen_facial',
        46: 'pct_id_cliente',
        49: 'qtd_servicos',
    }
    mapa = {cols[i]: nome for i, nome in pos.items() if i < len(cols)}
    df = df.rename(columns=mapa)
    manter = [v for v in pos.values() if v in df.columns]
    df = df[manter].copy()

    for c in df.columns:
        if c != 'pdv':
            df[c] = pd.to_numeric(df[c], errors='coerce')

    df['pdv'] = pd.to_numeric(df['pdv'], errors='coerce').astype('Int64')
    return df


def processar_metas(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df.iloc[:, 0].notna()].copy()
    df.columns = [str(c).strip() for c in df.columns]

    renomear = {
        'Consultor': 'consultor',
        'PDV': 'pdv',
        'Receita': 'meta_receita',
        'Boleto Médio': 'meta_boleto_medio',
        'Itens por Boleto': 'meta_itens_boleto',
        'Preço Médio': 'meta_preco_medio',
        'Penetração de Boleto Turbinado': 'meta_pen_bt',
        'Penetração de Boleto Promocional': 'meta_pen_bp',
        'Penetração de Receita Mobshop': 'meta_pen_mobshop',
        'Penetração de Boletos 1': 'meta_pen_boletos1',
        'Penetração de Boletos Fidelidade': 'meta_pen_fidelidade',
        'Resgate Fidelidade': 'meta_resgate_fidelidade',
        'Conversão de Ação de Fluxo': 'meta_conv_fluxo',
        'Penetração de Cuidados Faciais': 'meta_pen_facial',
        '% Boletos ID Cliente': 'meta_pct_id_cliente',
        'Serviços': 'meta_servicos',
        'NPS': 'meta_nps',
    }
    df = df.rename(columns={k: v for k, v in renomear.items() if k in df.columns})
    df['is_gerente'] = df['meta_receita'].astype(str).str.upper().str.strip() == 'GERENTE'

    for c in [col for col in df.columns if col.startswith('meta_')]:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    df['pdv'] = pd.to_numeric(df['pdv'], errors='coerce').astype('Int64')
    df['consultor'] = df['consultor'].astype(str).str.strip().str.title()
    return df[df['consultor'].str.strip() != ''].reset_index(drop=True)


def processar_servicos(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    renomear = {
        'PDV': 'pdv', 'CONSULTOR': 'consultor', 'UN': 'un',
        'NOME DO SERVIÇO': 'nome_servico', 'DATA REALIZAÇÃO': 'data',
        'QUANTIDADE DE SERVIÇOS COMPLETOS': 'qtd_servicos',
    }
    df = df.rename(columns={k: v for k, v in renomear.items() if k in df.columns})
    df['pdv'] = pd.to_numeric(df['pdv'], errors='coerce').astype('Int64')
    df['qtd_servicos'] = pd.to_numeric(df['qtd_servicos'], errors='coerce')
    df['consultor'] = df['consultor'].astype(str).str.strip().str.title()
    return df


def processar_treinamentos(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    renomear = {
        'NOME': 'consultor', 'CARGO': 'cargo', 'CÓDIGO DE PDV': 'pdv',
        'LOGIN EXTRANET': 'login', 'ADMISSÃO': 'admissao',
        'ADESÃO IAF': 'adesao_iaf', 'CONCLUSÃO GERAL': 'conclusao_geral',
    }
    df = df.rename(columns={k: v for k, v in renomear.items() if k in df.columns})
    df['pdv'] = pd.to_numeric(df['pdv'], errors='coerce').astype('Int64')
    df['consultor'] = df['consultor'].astype(str).str.strip().str.title()
    # ADESÃO IAF é o percentual de conclusão dos treinamentos (1.0 = 100% concluído)
    # CONCLUSÃO GERAL pode estar vazia — nesse caso usa ADESÃO IAF como indicador
    if 'adesao_iaf' in df.columns:
        df['treinamento_pct'] = pd.to_numeric(df['adesao_iaf'], errors='coerce').fillna(0)
        df['treinamento_concluido'] = df['treinamento_pct'] >= 1.0
    elif 'conclusao_geral' in df.columns:
        df['treinamento_pct'] = df['conclusao_geral'].apply(
            lambda v: 1.0 if (v is not None and str(v).strip() not in ['', '-', 'None', 'nan']) else 0.0
        )
        df['treinamento_concluido'] = df['treinamento_pct'] >= 1.0
    else:
        df['treinamento_pct'] = 0.0
        df['treinamento_concluido'] = False
    return df


def processar_id_cliente(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    renomear = {
        'PDV': 'pdv', 'CONSULTOR': 'consultor',
        # Coluna E — % Atendimentos com CPF (IAF 2026) — é o indicador oficial do ID Cliente
        '% Atendimentos com CPF (IAF 2026)': 'pct_id_cliente_iaf',
        '% ATENDIMENTOS USO INDEVIDO': 'pct_uso_indevido',
        '% BOLETOS ID CLIENTE USO INDEVIDO': 'pct_id_indevido',
        '% BOLETOS ID CLIENTE TMA CPF ABAIXO DE 2MIN': 'pct_id_tma',
    }
    df = df.rename(columns={k: v for k, v in renomear.items() if k in df.columns})
    df['pdv'] = pd.to_numeric(df['pdv'], errors='coerce').astype('Int64')
    df['consultor'] = df['consultor'].astype(str).str.strip().str.title()
    for c in ['pct_id_cliente_iaf', 'pct_uso_indevido',
              'pct_id_indevido', 'pct_id_tma']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


PROCESSADORES = {
    'consultor':    processar_consultor,
    'pdv':          processar_pdv,

    'servicos':     processar_servicos,
    'treinamentos': processar_treinamentos,
    'id_cliente':   processar_id_cliente,
}


# ── Widget de upload ──────────────────────────────────────────────────────────

def widget_upload_sidebar() -> dict:
    """Upload na sidebar. Identifica cada arquivo pelo conteúdo."""
    st.sidebar.subheader("📁 Carregar arquivos")
    st.sidebar.caption("O sistema identifica cada arquivo automaticamente.")

    arquivos = st.sidebar.file_uploader(
        "Selecione os arquivos (CSV ou XLSX)",
        type=['csv', 'xlsx', 'xlsm', 'xls'],
        accept_multiple_files=True,
        key="upload_arquivos"
    )

    dados = {}
    if not arquivos:
        return dados

    encontrados = {}
    erros = []

    for arq in arquivos:
        df_raw = _ler(arq)
        if df_raw is None:
            erros.append(f"❌ Não foi possível ler: **{arq.name}**")
            continue

        tipo = _identificar(df_raw)
        if tipo is None:
            erros.append(f"❓ Não reconhecido: **{arq.name}**")
            continue

        if tipo in encontrados:
            erros.append(f"⚠️ Duplicado ignorado: **{arq.name}**")
            continue

        try:
            df_proc = PROCESSADORES[tipo](df_raw)
            dados[tipo] = df_proc
            encontrados[tipo] = arq.name
        except Exception as e:
            erros.append(f"❌ Erro ao processar **{arq.name}**: {e}")

    if encontrados:
        st.sidebar.markdown("**Identificados:**")
        for tipo in encontrados:
            st.sidebar.success(f"✅ {ASSINATURAS[tipo]['descricao']}")

    for e in erros:
        st.sidebar.warning(e)

    faltando = set(ASSINATURAS.keys()) - set(encontrados.keys())
    if faltando:
        st.sidebar.markdown("**Aguardando:**")
        for t in sorted(faltando):
            st.sidebar.caption(f"○ {ASSINATURAS[t]['descricao']}")

    return dados
