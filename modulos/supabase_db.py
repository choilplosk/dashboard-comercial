"""
Módulo de integração com Supabase.
Gerencia salvamento e leitura de todos os dados do dashboard.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
import math


# ── Conexão ───────────────────────────────────────────────────────────────────

@st.cache_resource
def get_client():
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None


def _limpar_nan(df: pd.DataFrame) -> list:
    records = []
    for _, row in df.iterrows():
        rec = {}
        for col, val in row.items():
            if hasattr(val, 'item'):
                val = val.item()
            if val is None:
                rec[col] = None
            elif isinstance(val, float) and math.isnan(val):
                rec[col] = None
            elif isinstance(val, bool):
                rec[col] = bool(val)
            elif isinstance(val, (int, float)):
                rec[col] = val
            elif isinstance(val, str):
                rec[col] = val if val.strip() not in ('', 'nan', 'None', '-') else None
            elif hasattr(val, 'isoformat'):
                rec[col] = val.isoformat()
            else:
                try:
                    rec[col] = str(val) if val is not None else None
                except Exception:
                    rec[col] = None
        records.append(rec)
    return records


def _colunas_tabela(tabela: str) -> list:
    colunas = {
        'dados_consultor': [
            'data_upload', 'consultor', 'pdv', 'receita', 'qtd_boletos',
            'boleto_medio', 'qtd_itens', 'itens_por_boleto', 'preco_medio',
            'pen_bt', 'pen_bp', 'pen_mobshop', 'pen_boletos1', 'pen_fidelidade',
            'resgate_fidelidade', 'conv_fluxo', 'pen_facial', 'pct_id_cliente',
        ],
        'dados_pdv': [
            'data_upload', 'pdv', 'receita', 'receita_vs_ly', 'qtd_boletos',
            'boleto_medio', 'boleto_medio_vs_ly', 'qtd_itens',
            'itens_por_boleto', 'itens_por_boleto_vs_ly', 'preco_medio',
            'preco_medio_vs_ly', 'pen_bt', 'pen_bp', 'pen_mobshop',
            'pen_boletos1', 'pen_fidelidade', 'resgate_fidelidade',
            'conv_fluxo', 'pen_facial', 'pct_id_cliente', 'qtd_servicos',
        ],
        'dados_servicos': [
            'data_upload', 'pdv', 'consultor', 'nome_servico', 'data', 'qtd_servicos',
        ],
        'dados_treinamentos': [
            'data_upload', 'pdv', 'consultor', 'cargo', 'login',
            'adesao_iaf', 'conclusao_geral', 'treinamento_concluido', 'treinamento_pct',
        ],
        'dados_id_cliente': [
            'data_upload', 'pdv', 'consultor', 'pct_atend_cpf',
            'pct_uso_indevido', 'pct_id_cliente_iaf', 'pct_id_indevido', 'pct_id_tma',
        ],
    }
    return colunas.get(tabela, [])


# ── Salvar upload diário ──────────────────────────────────────────────────────

def salvar_upload(dados: dict, data_ref: date = None) -> bool:
    """
    Salva todos os dados do upload diário no Supabase.
    APAGA TUDO antes de inserir — garante sem duplicatas.
    """
    client = get_client()
    if client is None:
        return False

    if data_ref is None:
        data_ref = date.today()

    data_str = data_ref.isoformat()

    mapa_tabelas = {
        'consultor':    'dados_consultor',
        'pdv':          'dados_pdv',
        'servicos':     'dados_servicos',
        'treinamentos': 'dados_treinamentos',
        'id_cliente':   'dados_id_cliente',
    }

    erros = []
    for tipo, tabela in mapa_tabelas.items():
        df = dados.get(tipo)
        if df is None or (hasattr(df, 'empty') and df.empty):
            continue

        try:
            # ── APAGA TODOS os registros da tabela antes de inserir ──────────
            # Usa gt(0) para garantir que deleta tudo (id sempre > 0)
            client.table(tabela).delete().gt('id', 0).execute()

            # Adiciona coluna de data
            df_save = df.copy()
            df_save['data_upload'] = data_str

            # Filtra apenas colunas válidas
            colunas_validas = _colunas_tabela(tabela)
            if colunas_validas:
                df_save = df_save[[c for c in df_save.columns if c in colunas_validas]]

            records = _limpar_nan(df_save)
            if records:
                # Insere em lotes de 500
                for i in range(0, len(records), 500):
                    res = client.table(tabela).insert(records[i:i+500]).execute()
                    if not res.data:
                        erros.append(f"{tabela}: sem retorno na inserção")

        except Exception as e:
            erros.append(f"{tabela}: {str(e)}")

    if erros:
        st.warning(f"Avisos ao salvar: {'; '.join(erros)}")
    return True


# ── Carregar dados mais recentes ──────────────────────────────────────────────

def carregar_dados_recentes() -> dict:
    """Carrega os dados do upload mais recente do Supabase."""
    client = get_client()
    if client is None:
        return {}

    dados = {}
    mapa = {
        'consultor':    'dados_consultor',
        'pdv':          'dados_pdv',
        'servicos':     'dados_servicos',
        'treinamentos': 'dados_treinamentos',
        'id_cliente':   'dados_id_cliente',
    }

    try:
        for tipo, tabela in mapa.items():
            try:
                res_data = (client.table(tabela)
                            .select('data_upload')
                            .order('data_upload', desc=True)
                            .limit(1)
                            .execute())

                if not res_data.data:
                    continue

                data_mais_recente = res_data.data[0]['data_upload']

                res = (client.table(tabela)
                       .select('*')
                       .eq('data_upload', data_mais_recente)
                       .execute())

                if res.data:
                    df = pd.DataFrame(res.data)
                    df = df.drop(columns=['id', 'data_upload'], errors='ignore')
                    dados[tipo] = df
                    dados[f'_data_{tipo}'] = data_mais_recente

            except Exception:
                pass

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")

    return dados


def data_ultimo_upload() -> str | None:
    client = get_client()
    if client is None:
        return None
    try:
        res = (client.table('dados_consultor')
               .select('data_upload')
               .order('data_upload', desc=True)
               .limit(1)
               .execute())
        if res.data:
            d = date.fromisoformat(res.data[0]['data_upload'])
            return d.strftime('%d/%m/%Y')
    except Exception:
        pass
    return None


# ── Metas ─────────────────────────────────────────────────────────────────────

def carregar_metas() -> pd.DataFrame:
    client = get_client()
    if client is None:
        return pd.DataFrame()
    try:
        res = client.table('metas').select('*').execute()
        if res.data:
            df = pd.DataFrame(res.data)
            return df.drop(columns=['id', 'atualizado_em'], errors='ignore')
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar metas: {e}")
        return pd.DataFrame()


def salvar_metas(df_metas: pd.DataFrame) -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        client.table('metas').delete().gt('id', 0).execute()
        records = _limpar_nan(df_metas)
        if records:
            for i in range(0, len(records), 500):
                client.table('metas').insert(records[i:i+500]).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar metas: {e}")
        return False


def salvar_meta_linha(consultor: str, pdv: int, campos: dict) -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        res = (client.table('metas')
               .select('id')
               .eq('consultor', consultor)
               .eq('pdv', pdv)
               .execute())

        campos['consultor'] = consultor
        campos['pdv'] = pdv
        campos['atualizado_em'] = datetime.now().isoformat()

        if res.data:
            client.table('metas').update(campos).eq('id', res.data[0]['id']).execute()
        else:
            client.table('metas').insert(campos).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar meta: {e}")
        return False


# ── NPS ───────────────────────────────────────────────────────────────────────

def carregar_nps_supabase() -> dict:
    client = get_client()
    if client is None:
        return {}
    try:
        res = client.table('nps_pdv').select('*').execute()
        if res.data:
            return {str(r['pdv']): r['valor'] for r in res.data}
        return {}
    except Exception:
        return {}


def salvar_nps_supabase(pdv: int, valor: float) -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        res = client.table('nps_pdv').select('id').eq('pdv', pdv).execute()
        dados = {'pdv': pdv, 'valor': valor, 'atualizado_em': datetime.now().isoformat()}
        if res.data:
            client.table('nps_pdv').update(dados).eq('pdv', pdv).execute()
        else:
            client.table('nps_pdv').insert(dados).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar NPS: {e}")
        return False


# ── Verificação ───────────────────────────────────────────────────────────────

def verificar_conexao() -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        client.table('metas').select('id').limit(1).execute()
        return True
    except Exception:
        return False
