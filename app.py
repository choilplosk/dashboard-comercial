import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json as _json

st.set_page_config(page_title="Dashboard Venda Direta", page_icon="💼", layout="wide")

st.markdown("""<style>
    .stApp { background: #ffffff; }
    .block-container { padding-top: 1.2rem; padding-left: 1.5rem; padding-right: 1.5rem; padding-bottom: 2rem; }
    [data-testid="stSidebar"] { background-color: #1e293b !important; min-width: 220px; }
    [data-testid="stSidebar"] > div { background-color: #1e293b !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span, [data-testid="stSidebar"] div { color: #94a3b8 !important; }
    [data-testid="stSidebar"] .stButton > button {
        background: transparent !important; border: none !important;
        color: #94a3b8 !important; text-align: left !important;
        padding: 9px 14px !important; border-radius: 8px !important;
        font-size: 13px !important; width: 100% !important; }
    [data-testid="stSidebar"] .stButton > button:hover { background: #334155 !important; color: #f1f5f9 !important; }
    [data-testid="stSidebar"] .stSelectbox div { background: #334155 !important; border: none !important; }
    h1 { color: #0f172a !important; font-weight: 700 !important; font-size: 24px !important; }
    h2, h3, h4 { color: #1e293b !important; font-weight: 600 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; background: #f8fafc; border-radius: 8px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { font-size: 13px; border-radius: 6px; padding: 6px 16px; }
    .stTabs [aria-selected="true"] { background: #2563eb !important; color: white !important; }
    .stTabs [data-baseweb="tab-panel"] { padding-top: 16px; }
    .stExpander { border: 1px solid #e2e8f0 !important; border-radius: 8px !important; }
    .stDataFrame { border-radius: 8px; }
    p { font-size: 13px; }
    .stMarkdown hr { border-color: #e2e8f0; margin: 0.5rem 0; }
</style>""", unsafe_allow_html=True)

SUPABASE_URL = st.secrets.get("SUPABASE_URL","https://bddjuowbotsybamawsts.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY","eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkZGp1b3dib3RzeWJhbWF3c3RzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYzNzE3MjAsImV4cCI6MjA5MTk0NzcyMH0.QHDO0Ebfbx4rcV327g1KXD4Ep-jRstQXil_B6L445VU")

@st.cache_resource
def get_sb(): return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_config(k, d=None):
    try:
        r = get_sb().table("configuracoes").select("valor").eq("chave",k).single().execute()
        return r.data["valor"] if r.data else d
    except: return d

def set_config(k, v, u):
    sb = get_sb(); old = get_config(k)
    ex = sb.table("configuracoes").select("id").eq("chave",k).execute()
    if ex.data: sb.table("configuracoes").update({"valor":str(v),"updated_by":u}).eq("chave",k).execute()
    else: sb.table("configuracoes").insert({"chave":k,"valor":str(v),"updated_by":u}).execute()
    try: sb.table("log_alteracoes").insert({"tabela":"configuracoes","campo":k,"valor_anterior":str(old),"valor_novo":str(v),"usuario":u}).execute()
    except: pass

def get_ciclos(): return get_sb().table("ciclos").select("*").order("id",desc=True).execute().data or []
def get_ciclo_ativo():
    r = get_sb().table("ciclos").select("*").eq("ativo",True).order("id",desc=True).limit(1).execute()
    return r.data[0] if r.data else None
def get_setores(apenas_ativos=True, tipo=None):
    q = get_sb().table("setores").select("*")
    if apenas_ativos: q = q.eq("ativo",True)
    if tipo: q = q.eq("tipo",tipo)
    return q.order("nome").execute().data or []
def get_metas(cid, sid=None):
    q = get_sb().table("metas").select("*").eq("ciclo_id",cid)
    if sid: q = q.eq("setor_id",sid)
    return q.execute().data or []
def get_resultados(cid, tipo=None):
    q = get_sb().table("resultados").select("*").eq("ciclo_id",cid)
    if tipo: q = q.eq("tipo",tipo)
    return q.execute().data or []
def get_resultados_er(cid): return get_sb().table("resultados_er").select("*").eq("ciclo_id",cid).order("pct_nao_multimarca",desc=True).execute().data or []
def get_logs(cid): return get_sb().table("log_uploads").select("*").eq("ciclo_id",cid).order("data_upload",desc=True).execute().data or []
def log_upload(cid, arq, u): get_sb().table("log_uploads").insert({"ciclo_id":cid,"arquivo":arq,"usuario":u}).execute()
def upsert_meta(cid, sid, d):
    d['ciclo_id']=cid; d['setor_id']=sid
    get_sb().table("metas").upsert(d,on_conflict="ciclo_id,setor_id").execute()

def fmt_br(v,dec=2): return f"{v:_.{dec}f}".replace("_","X").replace(".",",").replace("X",".")
def fmt_moeda(v): return f"R$ {fmt_br(v)}"
def fmt_pct(v,dec=1): return f"{v:.{dec}f}%".replace(".",",")
def fmt_int(v): return f"{int(v):,}".replace(",",".")

PERFIS={"leitura":1,"gerencia":2,"admin":3}
def check_auth():
    for k in ["perfil","usuario","ciclo_sel_id"]:
        if k not in st.session_state: st.session_state[k]=None

def login_screen():
    _,col,_ = st.columns([1,1,1])
    with col:
        st.markdown('<div style="background:#1e293b;border-radius:12px;padding:28px;margin:40px 0 20px;text-align:center"><div style="font-size:20px;font-weight:700;color:white">💼 Venda Direta</div><div style="font-size:12px;color:#64748b;margin-top:4px">Dashboard de Gestão</div></div>',unsafe_allow_html=True)
        nome=st.text_input("Nome"); senha=st.text_input("Senha",type="password")
        if st.button("Entrar",use_container_width=True,type="primary"):
            if not nome: st.error("Informe seu nome.")
            elif senha==get_config("senha_admin","admin123"): st.session_state.perfil="admin";st.session_state.usuario=nome;st.rerun()
            elif senha==get_config("senha_gerencia","gerencia123"): st.session_state.perfil="gerencia";st.session_state.usuario=nome;st.rerun()
            elif senha==get_config("senha_leitura","leitura123"): st.session_state.perfil="leitura";st.session_state.usuario=nome;st.rerun()
            else: st.error("Senha incorreta.")

def requer_perfil(p):
    if PERFIS.get(st.session_state.get("perfil"),0)<PERFIS.get(p,99): st.warning("⛔ Sem permissão.");st.stop()

def cor_class(c): return {'Diamante':'#1e3a5f','Ouro':'#92400e','Prata':'#475569','Bronze':'#78350f'}.get(c,'#64748b')
def emoji_class(c): return {'Diamante':'💎','Ouro':'🥇','Prata':'🥈','Bronze':'🥉'}.get(c,'—')
def class_iaf(iaf,cfg={}):
    if iaf>=float(cfg.get('faixa_diamante_min',95)): return 'Diamante'
    if iaf>=float(cfg.get('faixa_ouro_min',85)): return 'Ouro'
    if iaf>=float(cfg.get('faixa_prata_min',75)): return 'Prata'
    if iaf>=float(cfg.get('faixa_bronze_min',65)): return 'Bronze'
    return 'Não Classificado'

def calc_pts(r,m,p,f50,f75,f100):
    if m<=0: return 0.0
    pct=r/m*100
    if pct>=f100: return p
    if pct>=f75: return p*0.75
    if pct>=f50: return p*0.50
    return 0.0

def ler_planilha(arq,marca):
    df=pd.read_excel(arq); df['Marca']=marca
    return df[~df['ValorPraticado'].isin([0,6])] if marca=='Oui' else df[df['ValorPraticado']>0]

def calc_multimarcas(df_ativos,dfs):
    at=df_ativos[df_ativos['ValorPraticado']>0].copy()
    cods=set(at['CodigoRevendedora'].unique()); cnt={c:0 for c in cods}
    for m in ['Boticario','Eudora','Oui','QDB']:
        if m in dfs:
            cm=set(dfs[m]['CodigoRevendedora'].unique())
            for c in cods:
                if c in cm: cnt[c]+=1
    multi={c for c,n in cnt.items() if n>=2}
    at['is_multimarca']=at['CodigoRevendedora'].isin(multi)
    return at

def processar_ciclo(dfs,metas_list,setores_list,cfg):
    df_at=dfs.get('Ativos')
    f50=float(cfg.get('faixa_pontuacao_50pct',85));f75=float(cfg.get('faixa_pontuacao_75pct',95));f100=float(cfg.get('faixa_pontuacao_100pct',100))
    pts_ir=float(cfg.get('pts_inicios_reinicios',800));pts_g=float(cfg.get('pts_meta_grupo',200))
    # Nova pontuação financeiro
    pts_bot=float(cfg.get('pts_boticario',300));pts_eud=float(cfg.get('pts_eudora',300))
    pts_at=float(cfg.get('pts_atividade',150));pts_mu=float(cfg.get('pts_multimarcas',90))
    pts_cab=float(cfg.get('pts_pct_cabelos',90));pts_mak=float(cfg.get('pts_pct_make',70))
    md={m['setor_id']:m for m in metas_list}
    df_multi=calc_multimarcas(df_at,dfs) if df_at is not None else None
    resultados=[]
    for s in setores_list:
        sid,nome,tipo=s['id'],s['nome'],s['tipo']; meta=md.get(sid,{})
        if tipo=='base':
            real=int(meta.get('realizado_inicios_reinicios',0));m_ir=int(meta.get('meta_inicios_reinicios',0))
            pts=calc_pts(real,m_ir,pts_ir,f50,f75,f100)
            resultados.append({'setor_id':sid,'tipo':'base','valor_boticario':0,'valor_eudora':0,'valor_oui':0,'valor_qdb':0,'valor_cabelos':0,'valor_make':0,'pct_multimarcas':0,'pct_cabelos':0,'pct_make':0,'pct_atividade':0,'ativos':0,'inicios_reinicios':real,'pontuacao_obtida':pts,'pontuacao_maxima':pts_ir,'iaf':0.0,'classificacao':'Não Classificado'})
        else:
            vals,po,pm={},0.0,0.0
            for marca,cv,cm_key,pts_marca in [('Boticario','valor_boticario','meta_boticario',pts_bot),('Eudora','valor_eudora','meta_eudora',pts_eud),('Oui','valor_oui','meta_oui',0),('QDB','valor_qdb','meta_qdb',0),('Cabelos','valor_cabelos','meta_cabelos',0),('Make','valor_make','meta_make',0)]:
                df=dfs.get(marca); val=df[df['Setor']==nome]['ValorPraticado'].sum() if df is not None else 0.0
                vals[cv]=val; mv=float(meta.get(cm_key,0))
                if mv>0 and pts_marca>0: po+=calc_pts(val,mv,pts_marca,f50,f75,f100); pm+=pts_marca
            at_s=None;n_at=0
            if df_at is not None:
                at_s=df_at[(df_at['Setor']==nome)&(df_at['ValorPraticado']>0)]; n_at=at_s['CodigoRevendedora'].nunique()
            pct_mu=0.0
            if df_multi is not None and n_at>0:
                pct_mu=df_multi[(df_multi['Setor']==nome)&(df_multi['is_multimarca'])]['CodigoRevendedora'].nunique()/n_at*100
            m_mu=float(meta.get('meta_multimarcas',0))
            if m_mu>0: po+=calc_pts(pct_mu,m_mu,pts_mu,f50,f75,f100); pm+=pts_mu
            pct_cab_v=0.0
            if dfs.get('Cabelos') is not None and n_at>0 and at_s is not None:
                pct_cab_v=len(set(at_s['CodigoRevendedora'].unique())&set(dfs['Cabelos'][dfs['Cabelos']['Setor']==nome]['CodigoRevendedora'].unique()))/n_at*100
            m_cab=float(meta.get('meta_pct_cabelos',0))
            if m_cab>0: po+=calc_pts(pct_cab_v,m_cab,pts_cab,f50,f75,f100); pm+=pts_cab
            pct_mak_v=0.0
            if dfs.get('Make') is not None and n_at>0 and at_s is not None:
                pct_mak_v=len(set(at_s['CodigoRevendedora'].unique())&set(dfs['Make'][dfs['Make']['Setor']==nome]['CodigoRevendedora'].unique()))/n_at*100
            m_mak=float(meta.get('meta_pct_make',0))
            if m_mak>0: po+=calc_pts(pct_mak_v,m_mak,pts_mak,f50,f75,f100); pm+=pts_mak
            tb=int(meta.get('tamanho_base',0)); pct_at_v=n_at/tb*100 if tb>0 else 0.0
            m_at_v=float(meta.get('meta_atividade',0))
            if m_at_v>0: po+=calc_pts(pct_at_v,m_at_v,pts_at,f50,f75,f100); pm+=pts_at
            iaf=po/pm*100 if pm>0 else 0.0
            resultados.append({'setor_id':sid,'tipo':'financeiro',**vals,'pct_multimarcas':round(pct_mu,2),'pct_cabelos':round(pct_cab_v,2),'pct_make':round(pct_mak_v,2),'pct_atividade':round(pct_at_v,2),'ativos':n_at,'inicios_reinicios':0,'pontuacao_obtida':round(po,2),'pontuacao_maxima':round(pm,2),'iaf':round(iaf,2),'classificacao':class_iaf(iaf,cfg)})
    base_res=[r for r in resultados if r['tipo']=='base']
    t_real=sum(r['inicios_reinicios'] for r in base_res)
    t_meta=sum(int(md.get(s['id'],{}).get('meta_inicios_reinicios',0)) for s in setores_list if s['tipo']=='base')
    gb=t_meta>0 and t_real>=t_meta
    for r in base_res:
        r['pontuacao_obtida']+=pts_g if gb else 0; r['pontuacao_maxima']+=pts_g
        r['iaf']=round(r['pontuacao_obtida']/r['pontuacao_maxima']*100 if r['pontuacao_maxima']>0 else 0,2)
        r['classificacao']=class_iaf(r['iaf'],cfg)
    er_res=[]
    if df_at is not None and dfs.get('ER') is not None and df_multi is not None:
        nao_m=set(df_multi[~df_multi['is_multimarca']]['CodigoRevendedora'].unique())
        df_er=dfs['ER'].copy(); df_er['is_nm']=df_er['Pessoa'].isin(nao_m)
        for u,g in df_er.groupby('Usuario de Finalização'):
            tot=len(g); nm=int(g['is_nm'].sum())
            er_res.append({'usuario_finalizacao':u,'total_pedidos':tot,'pedidos_nao_multimarca':nm,'pct_nao_multimarca':round(nm/tot*100 if tot>0 else 0,2)})
        er_res.sort(key=lambda x:x['pct_nao_multimarca'],reverse=True)
    ativos_unicos=int(df_at[df_at['ValorPraticado']>0]['CodigoRevendedora'].nunique()) if df_at is not None else 0
    return {'resultados':resultados,'resultados_er':er_res,'t_real':t_real,'t_meta':t_meta,'ativos_unicos_global':ativos_unicos}

# =============================================
# COMPONENTES VISUAIS
# =============================================
def _cor_bg(pct):
    if pct==0: return "#f8fafc","#64748b"
    if pct>=100: return "#f0fdf4","#166534"
    if pct>=95: return "#fefce8","#854d0e"
    return "#fef2f2","#991b1b"

def card_kpi(label, valor, meta_str=None, pct=0, delta=None):
    bg,tc = _cor_bg(pct)
    delta_html=""
    if delta is not None:
        dc="#16a34a" if delta>=0 else "#dc2626"
        delta_html=f'<div style="font-size:11px;color:{dc};font-weight:600;margin-top:3px">{"▲" if delta>=0 else "▼"} {abs(delta):.1f}%</div>'
    meta_html=f'<div style="font-size:11px;color:{tc}99;margin-top:3px">{meta_str}</div>' if meta_str else ""
    st.markdown(f'<div style="background:{bg};border-radius:10px;padding:14px 16px;border:1px solid {tc}22"><div style="font-size:10px;color:{tc}99;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">{label}</div><div style="font-size:26px;font-weight:700;color:{tc};line-height:1">{valor}</div>{meta_html}{delta_html}</div>',unsafe_allow_html=True)

def semaforo_linha(pct,label,rv,mv):
    bg,tc=_cor_bg(pct)
    ic="⚪" if pct==0 else ("🟢" if pct>=100 else ("🟡" if pct>=95 else "🔴"))
    return (f'<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;border-radius:6px;background:{bg};margin-bottom:3px">'
            f'<span style="font-size:11px;color:{tc}">{ic} {label}</span>'
            f'<div style="display:flex;align-items:center;gap:6px">'
            f'<span style="font-size:11px;font-weight:700;color:{tc}">{rv}</span>'
            f'<span style="font-size:10px;color:{tc}88">/ {mv}</span>'
            f'<span style="font-size:10px;color:{tc};background:{tc}22;padding:1px 5px;border-radius:3px;font-weight:600">{pct:.0f}%</span>'
            f'</div></div>')

def linha_rank(pos,nome,iaf,cl,delta=None,extra=None,atencao=False):
    cor=cor_class(cl); em=emoji_class(cl)
    pos_bg=["#f59e0b","#94a3b8","#92400e"][pos-1] if pos<=3 else "#e2e8f0"
    pos_txt="white" if pos<=3 else "#475569"
    barra=min(iaf,100)
    html=(f'<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:white;border-radius:8px;border:1px solid #e2e8f0;margin-bottom:4px{"border-left:3px solid #dc2626;" if atencao else ""}">'
          f'<div style="min-width:26px;height:26px;border-radius:50%;background:{pos_bg};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:{pos_txt}">{pos}</div>'
          f'<div style="flex:1"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px">'
          f'<span style="font-weight:600;font-size:13px;color:#0f172a">{nome}')
    if atencao: html+='<span style="font-size:10px;background:#fee2e2;color:#dc2626;padding:1px 5px;border-radius:4px;margin-left:6px">atenção</span>'
    html+=f'</span><div style="display:flex;align-items:center;gap:8px">'
    if delta is not None:
        dc="#16a34a" if delta>=0 else "#dc2626"
        html+=f'<span style="font-size:11px;color:{dc}">{"▲" if delta>=0 else "▼"}{abs(delta):.1f}%</span>'
    html+=(f'<span style="font-weight:700;font-size:15px;color:{cor}">{iaf:.1f}%</span>'
           f'<span style="background:{cor};color:white;padding:1px 8px;border-radius:10px;font-size:11px">{em} {cl}</span>')
    if extra: html+=f'<span style="font-size:11px;color:#94a3b8">{extra}</span>'
    html+=(f'</div></div><div style="background:#f1f5f9;border-radius:3px;height:4px;overflow:hidden">'
           f'<div style="background:{cor};width:{barra:.1f}%;height:100%;border-radius:3px"></div>'
           f'</div></div></div>')
    st.markdown(html,unsafe_allow_html=True)

def tabela_mini(titulo,dados,col_label,col_pct,col_extra=None):
    st.markdown(f'<p style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">{titulo}</p>',unsafe_allow_html=True)
    html='<div style="background:white;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0">'
    for i,(_,row) in enumerate(dados.iterrows()):
        bg="#f8fafc" if i%2==0 else "white"
        ex=f'<span style="font-size:10px;color:#94a3b8;margin-left:8px">{row[col_extra]}</span>' if col_extra and col_extra in row and row[col_extra] else ""
        html+=(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 12px;background:{bg}"><span style="font-size:12px;color:#475569">{row[col_label]}</span>'
               f'<div><span style="font-size:12px;font-weight:700;color:#1e293b">{row[col_pct]:.1f}%</span>{ex}</div></div>')
    html+='</div>'
    st.markdown(html,unsafe_allow_html=True)

ARQS=['Boticario','Cabelos','Eudora','Make','Oui','QDB','Ativos','ER']
MARCAS_CFG=[('valor_boticario','meta_boticario','Boticário'),('valor_eudora','meta_eudora','Eudora'),
            ('valor_oui','meta_oui','OUI'),('valor_qdb','meta_qdb','QDB'),
            ('valor_cabelos','meta_cabelos','Cabelos'),('valor_make','meta_make','Make')]
INDS_PCT=[('pct_multimarcas','meta_multimarcas','Multimarcas'),('pct_cabelos','meta_pct_cabelos','Cabelos %'),
          ('pct_make','meta_pct_make','Make %'),('pct_atividade','meta_atividade','Atividade')]

# =============================================
# HOME
# =============================================
def pg_home(cid):
    ciclo=get_ciclo_ativo(); ciclos=get_ciclos()
    cs=next((c for c in ciclos if c['id']==cid),ciclo) if cid else ciclo
    if not cs: st.warning("⚠️ Sem ciclo ativo."); return
    st.title(f"🏠 Visão Geral — {cs['nome']}")
    st.markdown("---")
    res=get_resultados(cs['id'])
    if not res: st.info("📊 Aguardando processamento."); _status_arqs(cs); return
    df=pd.DataFrame(res)
    fin=df[df['tipo']=='financeiro']; base=df[df['tipo']=='base']
    mc=['valor_boticario','valor_eudora','valor_oui','valor_qdb','valor_cabelos','valor_make']
    receita=df[mc].sum().sum()
    ativos_glob=int(get_config(f"ativos_unicos_{cs['id']}",0) or 0)
    sf=get_setores(tipo='financeiro'); ids_fin={s['id'] for s in sf}
    metas_h={m['setor_id']:m for m in get_metas(cs['id'])}
    meta_rec=sum(float(metas_h.get(sid,{}).get(f'meta_{m}',0)) for sid in ids_fin for m in ['boticario','eudora','oui','qdb','cabelos','make'])
    total_base=sum(int(metas_h.get(sid,{}).get('tamanho_base',0)) for sid in ids_fin)
    # Meta atividade global — manual
    meta_ativ_global=float(get_config(f"meta_atividade_global_{cs['id']}",0) or 0)
    pct_ativ=ativos_glob/total_base*100 if total_base>0 else 0
    pct_rec=receita/meta_rec*100 if meta_rec>0 else 0
    pct_make=fin['pct_make'].mean() if len(fin)>0 else 0
    pct_cab=fin['pct_cabelos'].mean() if len(fin)>0 else 0
    meta_make=sum(float(metas_h.get(sid,{}).get('meta_pct_make',0)) for sid in ids_fin)/len(sf) if sf else 0
    meta_cab=sum(float(metas_h.get(sid,{}).get('meta_pct_cabelos',0)) for sid in ids_fin)/len(sf) if sf else 0
    pct_make_c=pct_make/meta_make*100 if meta_make>0 else 0
    pct_cab_c=pct_cab/meta_cab*100 if meta_cab>0 else 0
    pct_ativ_c=pct_ativ/meta_ativ_global*100 if meta_ativ_global>0 else 0
    # Delta vs ciclo anterior
    c_ant=next((c for c in ciclos if c['id']<cs['id']),None)
    dr=dat=dmk=dcb=None
    if c_ant:
        ra=get_resultados(c_ant['id'])
        if ra:
            dfa=pd.DataFrame(ra); fa=dfa[dfa['tipo']=='financeiro']
            rec_a=dfa[mc].sum().sum(); dr=(receita-rec_a)/rec_a*100 if rec_a>0 else None
            dmk=(pct_make-fa['pct_make'].mean()) if len(fa)>0 else None
            dcb=(pct_cab-fa['pct_cabelos'].mean()) if len(fa)>0 else None
            at_a=int(get_config(f"ativos_unicos_{c_ant['id']}",0) or 0)
            base_a=sum(int({m['setor_id']:m for m in get_metas(c_ant['id'])}.get(sid,{}).get('tamanho_base',0)) for sid in ids_fin)
            pct_a=at_a/base_a*100 if base_a>0 else 0; dat=pct_ativ-pct_a
    st.markdown("#### Indicadores Principais")
    c1,c2,c3,c4=st.columns(4)
    with c1: card_kpi("Receita Total",fmt_moeda(receita),f"Meta: {fmt_moeda(meta_rec)} | {pct_rec:.0f}%",pct_rec,dr)
    with c2: card_kpi("Atividade Global",fmt_pct(pct_ativ),f"Meta: {fmt_pct(meta_ativ_global)} | {pct_ativ_c:.0f}%" if meta_ativ_global>0 else f"{fmt_int(ativos_glob)} ativos",pct_ativ_c,dat)
    with c3: card_kpi("Make",fmt_pct(pct_make),f"Meta: {fmt_pct(meta_make)} | {pct_make_c:.0f}%",pct_make_c,dmk)
    with c4: card_kpi("Cabelos",fmt_pct(pct_cab),f"Meta: {fmt_pct(meta_cab)} | {pct_cab_c:.0f}%",pct_cab_c,dcb)
    st.markdown("---")
    # Pódio
    st.markdown("#### 🏆 Pódio do Ciclo")
    try:
        sl=get_sb().table("setores").select("id,nome,ativo").execute().data or []
        nm_map={s['id']:s['nome'] for s in sl}; ids_at={s['id'] for s in sl if s['ativo']}
    except: nm_map={}; ids_at=set()
    todos=df[df['setor_id'].isin(ids_at)].sort_values('iaf',ascending=False).head(3)
    cp=st.columns(3)
    for i,(_,r) in enumerate(todos.iterrows()):
        nm=nm_map.get(r['setor_id'],"—"); cor=cor_class(r['classificacao'])
        bg,tc=_cor_bg(r['iaf'])
        with cp[i]:
            st.markdown(f'<div style="background:{bg};border-radius:10px;padding:16px;text-align:center;border:1px solid {tc}22"><div style="font-size:22px">{"🥇🥈🥉"[i]}</div><div style="font-size:13px;font-weight:600;color:#1e293b;margin:6px 0">{nm}</div><div style="font-size:28px;font-weight:700;color:{tc}">{fmt_pct(r["iaf"])}</div><div style="font-size:11px;color:{tc}88">{emoji_class(r["classificacao"])} {r["classificacao"]}</div></div>',unsafe_allow_html=True)
    st.markdown("")
    st.markdown("#### 🏅 Classificações")
    todos_r=df[df['setor_id'].isin(ids_at)].sort_values('iaf',ascending=False)
    for _,r in todos_r.iterrows():
        nm=nm_map.get(r['setor_id'],str(r['setor_id'])); cor=cor_class(r['classificacao']); em=emoji_class(r['classificacao'])
        bg,tc=_cor_bg(r['iaf'])
        st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 16px;border-radius:8px;background:{bg};border:1px solid {tc}22;margin-bottom:4px"><span style="font-size:13px;font-weight:600;color:#0f172a">{nm}</span><div style="display:flex;align-items:center;gap:14px"><span style="font-size:11px;color:{tc}88">{r["pontuacao_obtida"]:.0f}/{r["pontuacao_maxima"]:.0f} pts</span><span style="font-size:16px;font-weight:700;color:{tc}">{fmt_pct(r["iaf"])}</span><span style="background:{cor};color:white;padding:2px 8px;border-radius:10px;font-size:11px">{em} {r["classificacao"]}</span></div></div>',unsafe_allow_html=True)
    st.markdown("")
    _status_arqs(cs)

def _status_arqs(cs):
    with st.expander("📁 Status dos Arquivos",expanded=False):
        logs=get_logs(cs['id']); ok={l['arquivo'] for l in logs}; dt={l['arquivo']:l['data_upload'] for l in logs}
        cols=st.columns(4)
        for i,a in enumerate(ARQS):
            c="#16a34a" if a in ok else "#dc2626"
            with cols[i%4]: st.markdown(f'<div style="padding:6px 10px;border-radius:6px;background:{c}11;border:1px solid {c}33;margin-bottom:4px;font-size:12px">{"✅" if a in ok else "❌"} <b>{a}</b><br><span style="color:{c}">{dt.get(a,"")[:16] if a in ok else "Aguardando"}</span></div>',unsafe_allow_html=True)
        falt=[a for a in ARQS if a not in ok]
        if falt: st.warning(f"Pendentes: {', '.join(falt)}")
        else: st.success("Todos carregados!")

# =============================================
# BASE
# =============================================
def pg_base(cid):
    ciclo=get_ciclo_ativo(); ciclos=get_ciclos()
    cs=next((c for c in ciclos if c['id']==cid),ciclo) if cid else ciclo
    if not cs: st.warning("⚠️ Sem ciclo ativo."); return
    st.title("👥 Supervisoras de Base")
    st.markdown("---")
    sb_list=get_setores(tipo='base')
    if not sb_list: st.info("Nenhum setor Base configurado."); return
    res_all=get_resultados(cs['id'],tipo='base')
    metas={m['setor_id']:m for m in get_metas(cs['id'])}
    ids_at={s['id'] for s in sb_list}
    res=[r for r in res_all if r['setor_id'] in ids_at]
    sid_nm={s['id']:s['nome'] for s in sb_list}
    t_meta=sum(int(metas.get(s['id'],{}).get('meta_inicios_reinicios',0)) for s in sb_list)
    t_real=sum(int(metas.get(s['id'],{}).get('realizado_inicios_reinicios',0)) for s in sb_list)
    pct_g=t_real/t_meta*100 if t_meta>0 else 0
    gb=t_meta>0 and t_real>=t_meta
    base_atual=int(get_config(f"base_atual_{cs['id']}",0) or 0)
    base_pef=int(get_config(f"base_meta_pef_{cs['id']}",0) or 0)
    gap=base_atual-base_pef
    bg_g,tc_g=_cor_bg(pct_g)
    bg_gap="#f0fdf4" if gap>=0 else "#fef2f2"; tc_gap="#166534" if gap>=0 else "#991b1b"
    bg_gb="#f0fdf4" if gb else "#fef2f2"; tc_gb="#166534" if gb else "#991b1b"
    st.markdown("#### Indicadores do Grupo")
    c1,c2,c3,c4=st.columns(4)
    with c1: card_kpi("Meta do Grupo",f"{t_real} / {t_meta}",f"{fmt_pct(pct_g)} atingido",pct_g)
    with c2:
        st.markdown(f'<div style="background:{bg_gb};border-radius:10px;padding:14px 16px;border:1px solid {tc_gb}22"><div style="font-size:10px;color:{tc_gb}99;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Bônus Grupo</div><div style="font-size:18px;font-weight:700;color:{tc_gb}">{"✅ Conquistado" if gb else "❌ Não conquistado"}</div><div style="font-size:11px;color:{tc_gb}88;margin-top:3px">{"+200 pts para todas" if gb else f"Faltam {t_meta-t_real}"}</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div style="background:#f8fafc;border-radius:10px;padding:14px 16px;border:1px solid #e2e8f0"><div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Base Atual</div><div style="font-size:26px;font-weight:700;color:#1e293b">{fmt_int(base_atual)}</div><div style="font-size:11px;color:#94a3b8;margin-top:3px">Meta PEF: {fmt_int(base_pef)}</div></div>',unsafe_allow_html=True)
    with c4: st.markdown(f'<div style="background:{bg_gap};border-radius:10px;padding:14px 16px;border:1px solid {tc_gap}22"><div style="font-size:10px;color:{tc_gap}99;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:6px">Gap / Bônus</div><div style="font-size:26px;font-weight:700;color:{tc_gap}">{("+" if gap>=0 else "")}{fmt_int(gap)}</div><div style="font-size:11px;color:{tc_gap}88;margin-top:3px">base atual - meta PEF</div></div>',unsafe_allow_html=True)
    st.markdown("---")
    c_ant=next((c for c in ciclos if c['id']<cs['id']),None)
    r_ant={r['setor_id']:r for r in get_resultados(c_ant['id'],tipo='base')} if c_ant else {}
    st.markdown("#### 🏆 Ranking Individual")
    res_s=sorted(res,key=lambda x:x['iaf'],reverse=True)
    for pos,r in enumerate(res_s,1):
        sid=r['setor_id']; nome=sid_nm.get(sid,str(sid)); meta=metas.get(sid,{})
        real_ir=int(meta.get('realizado_inicios_reinicios',0)); meta_ir=int(meta.get('meta_inicios_reinicios',0))
        contrib=real_ir/t_meta*100 if t_meta>0 else 0
        delta=round(r['iaf']-r_ant[sid]['iaf'],1) if sid in r_ant else None
        linha_rank(pos,nome,r['iaf'],r['classificacao'],delta,f"I+R: {real_ir}/{meta_ir} | Contrib: {fmt_pct(contrib)}")
    st.markdown("")
    # Contribuição — tabela visual com barras
    if res and t_meta>0:
        st.markdown("#### 📊 Contribuição para Meta do Grupo")
        html='<div style="background:white;border-radius:10px;border:1px solid #e2e8f0;padding:16px">'
        for pos,r in enumerate(res_s,1):
            sid=r['setor_id']; meta=metas.get(sid,{})
            real_ir=int(meta.get('realizado_inicios_reinicios',0)); contrib=real_ir/t_meta*100
            barra=min(contrib/100*100,100) if t_meta>0 else 0
            cor_b=cor_class(r['classificacao'])
            pos_bg=["#f59e0b","#94a3b8","#92400e"][pos-1] if pos<=3 else "#e2e8f0"
            pos_txt="white" if pos<=3 else "#475569"
            html+=(f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #f8fafc">'
                   f'<div style="min-width:22px;height:22px;border-radius:50%;background:{pos_bg};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:{pos_txt}">{pos}</div>'
                   f'<div style="width:180px;font-size:12px;font-weight:600;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{sid_nm.get(sid,str(sid))}</div>'
                   f'<div style="flex:1;background:#f1f5f9;border-radius:4px;height:8px;overflow:hidden"><div style="background:{cor_b};width:{barra:.1f}%;height:100%;border-radius:4px"></div></div>'
                   f'<div style="width:28px;font-size:12px;font-weight:700;color:#1e293b;text-align:right">{real_ir}</div>'
                   f'<div style="width:42px;font-size:11px;font-weight:700;color:{cor_b};text-align:right">{contrib:.1f}%</div>'
                   f'</div>')
        total_pct=t_real/t_meta*100 if t_meta>0 else 0
        bg_t,tc_t=_cor_bg(total_pct)
        html+=(f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;padding-top:10px;border-top:1px solid #e2e8f0">'
               f'<div><div style="font-size:11px;color:#64748b">Total realizado vs meta do grupo</div>'
               f'<div style="font-size:11px;color:#94a3b8;margin-top:2px">{t_real} de {t_meta} inícios+reinícios</div></div>'
               f'<div style="display:flex;align-items:center;gap:8px">'
               f'<span style="font-size:10px;background:{bg_t};color:{tc_t};padding:2px 8px;border-radius:4px;border:1px solid {tc_t}22">Meta: {t_meta}</span>'
               f'<span style="font-size:14px;font-weight:700;color:{tc_t}">{fmt_pct(total_pct)}</span></div></div></div>')
        st.markdown(html,unsafe_allow_html=True)
    st.markdown("")
    # Evolução IAF
    st.markdown("#### 📈 Evolução I+R por Ciclo")
    evol=[]
    for c in ciclos[-6:]:
        mc2={m['setor_id']:m for m in get_metas(c['id'])}
        for rv in get_resultados(c['id'],tipo='base'):
            nm=sid_nm.get(rv['setor_id'],str(rv['setor_id']))
            evol.append({'Ciclo':c['nome'],'Supervisora':nm,'I+R':rv['inicios_reinicios'],'Meta':int(mc2.get(rv['setor_id'],{}).get('meta_inicios_reinicios',0))})
    if evol:
        fig=px.line(pd.DataFrame(evol),x='Ciclo',y='I+R',color='Supervisora',markers=True,color_discrete_sequence=['#1e3a5f','#2563eb','#64748b','#92400e','#16a34a'])
        fig.update_layout(height=300,margin=dict(t=10,b=10),plot_bgcolor='white',paper_bgcolor='white')
        st.plotly_chart(fig,use_container_width=True)

# =============================================
# FINANCEIRO
# =============================================
def pg_financeiro(cid):
    ciclo=get_ciclo_ativo(); ciclos=get_ciclos()
    cs=next((c for c in ciclos if c['id']==cid),ciclo) if cid else ciclo
    if not cs: st.warning("⚠️ Sem ciclo ativo."); return
    st.title("💼 Supervisoras de Financeiro")
    st.markdown("---")
    sf_list=get_setores(tipo='financeiro')
    if not sf_list: st.info("Sem setores Financeiro."); return
    res_all=get_resultados(cs['id'],tipo='financeiro')
    metas={m['setor_id']:m for m in get_metas(cs['id'])}
    ids_at={s['id'] for s in sf_list}
    res=[r for r in res_all if r['setor_id'] in ids_at]
    todos_s=get_sb().table("setores").select("id,nome").execute().data or []
    sid_nm={s['id']:s['nome'] for s in todos_s}
    c_ant=next((c for c in ciclos if c['id']<cs['id']),None)
    r_ant={r['setor_id']:r for r in get_resultados(c_ant['id'],tipo='financeiro')} if c_ant else {}
    if not res: st.info("Sem dados para este ciclo."); return
    df_r=pd.DataFrame(res)
    mc=['valor_boticario','valor_eudora','valor_oui','valor_qdb','valor_cabelos','valor_make']
    receita=sum(df_r[c].sum() for c in mc)
    meta_rec=sum(float(metas.get(s['id'],{}).get(f'meta_{m}',0)) for s in sf_list for m in ['boticario','eudora','oui','qdb','cabelos','make'])
    meta_multi=sum(float(metas.get(s['id'],{}).get('meta_multimarcas',0)) for s in sf_list)/len(sf_list) if sf_list else 0
    meta_ativ=sum(float(metas.get(s['id'],{}).get('meta_atividade',0)) for s in sf_list)/len(sf_list) if sf_list else 0
    pct_multi=df_r['pct_multimarcas'].mean(); pct_ativ=df_r['pct_atividade'].mean()
    pct_rec=receita/meta_rec*100 if meta_rec>0 else 0
    pct_mc=pct_multi/meta_multi*100 if meta_multi>0 else 0
    pct_ac=pct_ativ/meta_ativ*100 if meta_ativ>0 else 0
    st.markdown("#### Visão do Grupo")
    c1,c2,c3,c4=st.columns(4)
    with c1: card_kpi("Receita Total",fmt_moeda(receita),f"Meta: {fmt_moeda(meta_rec)} | {pct_rec:.0f}%",pct_rec)
    with c2: card_kpi("Ativos",fmt_int(int(df_r['ativos'].sum())))
    with c3: card_kpi("Multimarcas Méd.",fmt_pct(pct_multi),f"Meta: {fmt_pct(meta_multi)} | {pct_mc:.0f}%",pct_mc)
    with c4: card_kpi("Atividade Méd.",fmt_pct(pct_ativ),f"Meta: {fmt_pct(meta_ativ)} | {pct_ac:.0f}%",pct_ac)
    st.markdown("---")
    st.markdown("#### 🏆 Rankings por Indicador")
    tab_iaf,tab_multi,tab_ativ,tab_cab,tab_make=st.tabs(["IAF","Multimarcas","Atividade","Cabelos %","Make %"])
    dr=[]
    for r in res:
        nm=sid_nm.get(r['setor_id'],str(r['setor_id'])); meta=metas.get(r['setor_id'],{})
        dr.append({'nome':nm,'iaf':r['iaf'],'classificacao':r['classificacao'],'setor_id':r['setor_id'],
            'pct_multimarcas':r['pct_multimarcas'],'meta_multimarcas':float(meta.get('meta_multimarcas',0)),
            'pct_atividade':r['pct_atividade'],'meta_atividade':float(meta.get('meta_atividade',0)),
            'pct_cabelos':r['pct_cabelos'],'meta_cabelos':float(meta.get('meta_pct_cabelos',0)),
            'pct_make':r['pct_make'],'meta_make':float(meta.get('meta_pct_make',0))})
    def mini_rank(dados,key,mk):
        for pos,d in enumerate(sorted(dados,key=lambda x:x[key],reverse=True),1):
            v=d[key]; m=d[mk]; pct=v/m*100 if m>0 else 0
            bg,tc=_cor_bg(pct); ic="🟢" if pct>=100 else ("🟡" if pct>=95 else ("🔴" if pct>0 else "⚪"))
            pb=["#f59e0b","#94a3b8","#92400e"][pos-1] if pos<=3 else "#e2e8f0"; pt="white" if pos<=3 else "#475569"
            st.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:7px 12px;background:{bg};border-radius:8px;border:1px solid {tc}22;margin-bottom:3px"><div style="min-width:24px;height:24px;border-radius:50%;background:{pb};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:{pt}">{pos}</div><span style="flex:1;font-size:13px;font-weight:600;color:#0f172a">{d["nome"]}</span><span style="font-size:13px;font-weight:700;color:{tc}">{ic} {fmt_pct(v)}</span><span style="font-size:11px;color:{tc}88">meta {fmt_pct(m)} ({pct:.0f}%)</span></div>',unsafe_allow_html=True)
    with tab_iaf:
        for pos,r in enumerate(sorted(res,key=lambda x:x['iaf'],reverse=True),1):
            delta=round(r['iaf']-r_ant[r['setor_id']]['iaf'],1) if r['setor_id'] in r_ant else None
            linha_rank(pos,sid_nm.get(r['setor_id'],str(r['setor_id'])),r['iaf'],r['classificacao'],delta,atencao=r['iaf']<75)
    with tab_multi: mini_rank(dr,'pct_multimarcas','meta_multimarcas')
    with tab_ativ: mini_rank(dr,'pct_atividade','meta_atividade')
    with tab_cab: mini_rank(dr,'pct_cabelos','meta_cabelos')
    with tab_make: mini_rank(dr,'pct_make','meta_make')
    st.markdown("")
    st.markdown("#### 📋 Desempenho Individual")
    for r in sorted(res,key=lambda x:x['iaf'],reverse=True):
        sid=r['setor_id']; nome=sid_nm.get(sid,str(sid)); meta=metas.get(sid,{})
        delta=round(r['iaf']-r_ant[sid]['iaf'],1) if sid in r_ant else None
        cor=cor_class(r['classificacao']); em=emoji_class(r['classificacao'])
        atencao=r['iaf']<75
        receita_sup=sum(r.get(cv,0) for cv,_,_ in MARCAS_CFG)
        bg_card,tc_card=_cor_bg(r['iaf'])
        col1,col2=st.columns([1,1])
        with col1:
            delta_html=""
            if delta is not None:
                dc="#16a34a" if delta>=0 else "#dc2626"
                delta_html=f'<span style="font-size:10px;color:{dc}">{"▲" if delta>=0 else "▼"}{abs(delta):.1f}%</span>'
            warn_html='<span style="font-size:10px;background:#fee2e2;color:#dc2626;padding:1px 5px;border-radius:4px;margin-left:4px">atenção</span>' if atencao else ""
            # Indicadores combinados Make e Cabelos
            v_cab=r.get('valor_cabelos',0); m_cab=float(meta.get('meta_cabelos',0))
            v_mak=r.get('valor_make',0); m_mak=float(meta.get('meta_make',0))
            p_cab_pct=r.get('pct_cabelos',0); m_cab_pct=float(meta.get('meta_pct_cabelos',0))
            p_mak_pct=r.get('pct_make',0); m_mak_pct=float(meta.get('meta_pct_make',0))
            pct_cab_r=v_cab/m_cab*100 if m_cab>0 else 0
            pct_mak_r=v_mak/m_mak*100 if m_mak>0 else 0
            pct_cab_p=p_cab_pct/m_cab_pct*100 if m_cab_pct>0 else 0
            pct_mak_p=p_mak_pct/m_mak_pct*100 if m_mak_pct>0 else 0
            bg_cab,tc_cab=_cor_bg(min(pct_cab_r,pct_cab_p) if pct_cab_r>0 and pct_cab_p>0 else max(pct_cab_r,pct_cab_p))
            bg_mak,tc_mak=_cor_bg(min(pct_mak_r,pct_mak_p) if pct_mak_r>0 and pct_mak_p>0 else max(pct_mak_r,pct_mak_p))
            ind_html=""
            for cv,cm,label in [('valor_boticario','meta_boticario','Boticário'),('valor_eudora','meta_eudora','Eudora'),('valor_oui','meta_oui','OUI'),('valor_qdb','meta_qdb','QDB')]:
                v=r.get(cv,0); m=float(meta.get(cm,0)); pct=v/m*100 if m>0 else 0
                ind_html+=semaforo_linha(pct,label,fmt_moeda(v),fmt_moeda(m))
            # Cabelos combinado
            ic_cab="🟢" if pct_cab_r>=100 and pct_cab_p>=100 else ("🟡" if pct_cab_r>=95 or pct_cab_p>=95 else ("🔴" if pct_cab_r>0 or pct_cab_p>0 else "⚪"))
            ind_html+=(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;border-radius:6px;background:{bg_cab};margin-bottom:3px">'
                      f'<span style="font-size:11px;color:{tc_cab}">{ic_cab} Cabelos</span>'
                      f'<div style="display:flex;align-items:center;gap:8px">'
                      f'<span style="font-size:11px;font-weight:600;color:{tc_cab}">{fmt_moeda(v_cab)}</span><span style="font-size:10px;color:{tc_cab}88">R$ {pct_cab_r:.0f}%</span>'
                      f'<span style="font-size:11px;font-weight:600;color:{tc_cab}">{fmt_pct(p_cab_pct)}</span><span style="font-size:10px;color:{tc_cab}88">% {pct_cab_p:.0f}%</span>'
                      f'</div></div>')
            # Make combinado
            ic_mak="🟢" if pct_mak_r>=100 and pct_mak_p>=100 else ("🟡" if pct_mak_r>=95 or pct_mak_p>=95 else ("🔴" if pct_mak_r>0 or pct_mak_p>0 else "⚪"))
            ind_html+=(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:5px 8px;border-radius:6px;background:{bg_mak};margin-bottom:3px">'
                      f'<span style="font-size:11px;color:{tc_mak}">{ic_mak} Make</span>'
                      f'<div style="display:flex;align-items:center;gap:8px">'
                      f'<span style="font-size:11px;font-weight:600;color:{tc_mak}">{fmt_moeda(v_mak)}</span><span style="font-size:10px;color:{tc_mak}88">R$ {pct_mak_r:.0f}%</span>'
                      f'<span style="font-size:11px;font-weight:600;color:{tc_mak}">{fmt_pct(p_mak_pct)}</span><span style="font-size:10px;color:{tc_mak}88">% {pct_mak_p:.0f}%</span>'
                      f'</div></div>')
            for cv,cm,label in [('pct_multimarcas','meta_multimarcas','Multimarcas'),('pct_atividade','meta_atividade','Atividade')]:
                v=r.get(cv,0); m=float(meta.get(cm,0)); pct=v/m*100 if m>0 else 0
                ind_html+=semaforo_linha(pct,label,fmt_pct(v),fmt_pct(m))
            st.markdown(f'<div style="background:{bg_card};border-radius:10px;padding:14px;border:1px solid {tc_card}22"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px"><span style="font-weight:700;font-size:13px;color:#0f172a">{nome}{warn_html}</span><span style="background:{cor};color:white;padding:2px 8px;border-radius:10px;font-size:11px">{em} {r["classificacao"]}</span></div><div style="display:flex;align-items:baseline;gap:10px;margin-bottom:6px"><span style="font-size:30px;font-weight:700;color:{tc_card}">{fmt_pct(r["iaf"])}</span><span style="font-size:11px;color:{tc_card}88">{r["pontuacao_obtida"]:.0f}/{r["pontuacao_maxima"]:.0f} pts {delta_html}</span></div><div style="background:{tc_card}22;border-radius:3px;height:4px;overflow:hidden;margin-bottom:8px"><div style="background:{tc_card};width:{min(r["iaf"],100):.1f}%;height:100%;border-radius:3px"></div></div><div style="font-size:11px;color:{tc_card}88;margin-bottom:6px">Receita: <b style="color:{tc_card}">{fmt_moeda(receita_sup)}</b> | Ativos: <b style="color:{tc_card}">{r.get("ativos",0)}</b></div><div>{ind_html}</div></div>',unsafe_allow_html=True)
        with col2:
            cats=['Boticário','Eudora','OUI','QDB','Cabelos','Make','Multimarcas','Atividade']
            mts=[float(meta.get(k,0)) for k in ['meta_boticario','meta_eudora','meta_oui','meta_qdb','meta_cabelos','meta_make','meta_multimarcas','meta_atividade']]
            vrs=[min(r.get(cv,0)/m*100,150) if m>0 else 0 for (cv,_,_),m in zip([('valor_boticario','',''),('valor_eudora','',''),('valor_oui','',''),('valor_qdb','',''),('valor_cabelos','',''),('valor_make','',''),('pct_multimarcas','',''),('pct_atividade','','')],mts)]
            rgba_m={'Diamante':'rgba(30,58,95,0.15)','Ouro':'rgba(146,64,14,0.15)','Prata':'rgba(71,85,105,0.15)','Bronze':'rgba(120,53,15,0.15)'}
            fig_r=go.Figure()
            fig_r.add_trace(go.Scatterpolar(r=vrs+[vrs[0]],theta=cats+[cats[0]],fill='toself',fillcolor=rgba_m.get(r['classificacao'],'rgba(100,116,139,0.15)'),line=dict(color=cor,width=2),name=nome))
            fig_r.add_trace(go.Scatterpolar(r=[100]*len(cats)+[100],theta=cats+[cats[0]],line=dict(color='#e2e8f0',width=1,dash='dot'),showlegend=False))
            fig_r.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,150],ticksuffix="%",tickfont=dict(size=9),gridcolor='#f1f5f9'),angularaxis=dict(tickfont=dict(size=10))),showlegend=False,height=300,margin=dict(t=20,b=20,l=20,r=20),paper_bgcolor='white')
            st.plotly_chart(fig_r,use_container_width=True)
        st.markdown("")
    # Gráficos evolução
    st.markdown("#### 📈 Evolução de Ativos por Ciclo")
    evol_at=[]
    for c in ciclos[-6:]:
        for rv in get_resultados(c['id'],tipo='financeiro'):
            evol_at.append({'Ciclo':c['nome'],'Supervisora':sid_nm.get(rv['setor_id'],str(rv['setor_id'])),'Ativos':rv['ativos']})
    if evol_at:
        fig_at=px.line(pd.DataFrame(evol_at),x='Ciclo',y='Ativos',color='Supervisora',markers=True,color_discrete_sequence=['#1e3a5f','#2563eb','#64748b','#92400e','#16a34a','#dc2626'])
        fig_at.update_layout(height=280,margin=dict(t=10,b=10),plot_bgcolor='white',paper_bgcolor='white')
        st.plotly_chart(fig_at,use_container_width=True)
    st.markdown("#### 📈 Evolução de Receita do Grupo")
    evol_rec=[]
    for c in ciclos[-6:]:
        rl=get_resultados(c['id'],tipo='financeiro')
        if rl: evol_rec.append({'Ciclo':c['nome'],'Receita':sum(pd.DataFrame(rl)[cv].sum() for cv,_,_ in MARCAS_CFG)})
    if evol_rec:
        fig_rec=go.Figure(go.Scatter(x=[d['Ciclo'] for d in evol_rec],y=[d['Receita'] for d in evol_rec],mode='lines+markers',line=dict(color='#1e3a5f',width=2),marker=dict(size=8,color='#2563eb')))
        fig_rec.update_layout(height=240,margin=dict(t=10,b=10),plot_bgcolor='white',paper_bgcolor='white')
        fig_rec.update_yaxes(tickprefix="R$ ",tickformat=",.0f")
        st.plotly_chart(fig_rec,use_container_width=True)

# =============================================
# ER
# =============================================
def pg_er(cid):
    requer_perfil("gerencia")
    ciclo=get_ciclo_ativo(); ciclos=get_ciclos()
    cs=next((c for c in ciclos if c['id']==cid),ciclo) if cid else ciclo
    if not cs: st.warning("⚠️ Sem ciclo ativo."); return
    st.title("🏪 ER — Espaço Revendedor")
    st.markdown("---")
    res=get_resultados_er(cs['id'])
    if not res: st.info("📊 Sem dados ER para este ciclo."); return
    df=pd.DataFrame(res)
    tp=int(df['total_pedidos'].sum()); tnm=int(df['pedidos_nao_multimarca'].sum())
    pg_nm=tnm/tp*100 if tp>0 else 0
    total_ativos=int(get_config(f"ativos_unicos_{cs['id']}",0) or 0)
    rev_er=int(get_config(f"er_rev_total_{cs['id']}",0) or 0)
    rev_multi=int(get_config(f"er_rev_multi_{cs['id']}",0) or 0)
    rev_make=int(get_config(f"er_rev_make_{cs['id']}",0) or 0)
    rev_cab=int(get_config(f"er_rev_cab_{cs['id']}",0) or 0)
    pct_make_er=rev_make/rev_er*100 if rev_er>0 else 0
    pct_cab_er=rev_cab/rev_er*100 if rev_er>0 else 0
    cab_codes=set(_json.loads(get_config(f"er_cab_list_{cs['id']}","[]") or "[]"))
    make_codes=set(_json.loads(get_config(f"er_make_list_{cs['id']}","[]") or "[]"))
    df_er_raw=st.session_state.get('df_er_raw',None)
    st.markdown("#### Indicadores Principais")
    c1,c2,c3,c4=st.columns(4)
    with c1: card_kpi("Ativos no ER",fmt_int(rev_er),f"× {fmt_int(total_ativos)} ativos total" if total_ativos>0 else None)
    with c2: card_kpi("No. RV. Multimarcas",fmt_int(rev_multi),"dentre os que vieram ao ER")
    pct_make_c=pct_make_er/float(get_config(f"meta_pct_make_er",50) or 50)*100 if pct_make_er>0 else 0
    pct_cab_c=pct_cab_er/float(get_config(f"meta_pct_cab_er",40) or 40)*100 if pct_cab_er>0 else 0
    with c3: card_kpi("Compraram Make",f"{fmt_int(rev_make)} ({fmt_pct(pct_make_er)})",f"de {fmt_int(rev_er)} no ER")
    with c4: card_kpi("Compraram Cabelos",f"{fmt_int(rev_cab)} ({fmt_pct(pct_cab_er)})",f"de {fmt_int(rev_er)} no ER")
    st.markdown("---")
    st.markdown("#### 🏆 Ranking Multimarca")
    df['pedidos_multi']=df['total_pedidos']-df['pedidos_nao_multimarca']
    df['pct_multi']=100-df['pct_nao_multimarca']
    tab_m,tab_c,tab_mk=st.tabs(["Multimarcas","Cabelos","Make"])
    def rank_caixa(df_s,col_v):
        for pos,row in df_s.sort_values(col_v,ascending=False).reset_index(drop=True).iterrows():
            pos_n=pos+1; v=row[col_v]; bg,tc=_cor_bg(v)
            ic="🟢" if v>=70 else ("🟡" if v>=50 else "🔴")
            pb=["#f59e0b","#94a3b8","#92400e"][pos_n-1] if pos_n<=3 else "#e2e8f0"; pt="white" if pos_n<=3 else "#475569"
            ped_col='pedidos_multi' if col_v=='pct_multi' else col_v.replace('pct_','n_')
            n_ped=int(row.get(ped_col,0))
            st.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:{bg};border-radius:8px;border:1px solid {tc}22;margin-bottom:4px"><div style="min-width:26px;height:26px;border-radius:50%;background:{pb};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:{pt}">{pos_n}</div><span style="flex:1;font-size:13px;font-weight:600;color:#0f172a">{row["usuario_finalizacao"]}</span><span style="font-size:12px;color:{tc}88">{n_ped} pedidos</span><span style="font-size:15px;font-weight:700;color:{tc}">{ic} {fmt_pct(v)}</span></div>',unsafe_allow_html=True)
    with tab_m: rank_caixa(df,'pct_multi')
    with tab_c:
        if df_er_raw is not None and cab_codes:
            df_c=df_er_raw.copy(); df_c['is_cab']=df_c['Pessoa'].isin(cab_codes)
            cr=df_c.groupby('Usuario de Finalização').agg(total=('Pessoa','count'),n_cab=('is_cab','sum')).reset_index()
            cr['pct_cab']=cr['n_cab']/cr['total']*100
            for pos,row in cr.sort_values('pct_cab',ascending=False).reset_index(drop=True).iterrows():
                pos_n=pos+1; v=row['pct_cab']; bg,tc=_cor_bg(v)
                ic="🟢" if v>=70 else ("🟡" if v>=50 else "🔴")
                pb=["#f59e0b","#94a3b8","#92400e"][pos_n-1] if pos_n<=3 else "#e2e8f0"; pt="white" if pos_n<=3 else "#475569"
                st.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:{bg};border-radius:8px;border:1px solid {tc}22;margin-bottom:4px"><div style="min-width:26px;height:26px;border-radius:50%;background:{pb};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:{pt}">{pos_n}</div><span style="flex:1;font-size:13px;font-weight:600;color:#0f172a">{row["Usuario de Finalização"]}</span><span style="font-size:12px;color:{tc}88">{int(row["n_cab"])} pedidos</span><span style="font-size:15px;font-weight:700;color:{tc}">{ic} {fmt_pct(v)}</span></div>',unsafe_allow_html=True)
        else: st.info("Reprocesse os dados para ver este ranking.")
    with tab_mk:
        if df_er_raw is not None and make_codes:
            df_m=df_er_raw.copy(); df_m['is_mak']=df_m['Pessoa'].isin(make_codes)
            mr=df_m.groupby('Usuario de Finalização').agg(total=('Pessoa','count'),n_mak=('is_mak','sum')).reset_index()
            mr['pct_mak']=mr['n_mak']/mr['total']*100
            for pos,row in mr.sort_values('pct_mak',ascending=False).reset_index(drop=True).iterrows():
                pos_n=pos+1; v=row['pct_mak']; bg,tc=_cor_bg(v)
                ic="🟢" if v>=70 else ("🟡" if v>=50 else "🔴")
                pb=["#f59e0b","#94a3b8","#92400e"][pos_n-1] if pos_n<=3 else "#e2e8f0"; pt="white" if pos_n<=3 else "#475569"
                st.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:{bg};border-radius:8px;border:1px solid {tc}22;margin-bottom:4px"><div style="min-width:26px;height:26px;border-radius:50%;background:{pb};display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:{pt}">{pos_n}</div><span style="flex:1;font-size:13px;font-weight:600;color:#0f172a">{row["Usuario de Finalização"]}</span><span style="font-size:12px;color:{tc}88">{int(row["n_mak"])} pedidos</span><span style="font-size:15px;font-weight:700;color:{tc}">{ic} {fmt_pct(v)}</span></div>',unsafe_allow_html=True)
        else: st.info("Reprocesse os dados para ver este ranking.")
    st.markdown("")
    if df_er_raw is not None and rev_er>0:
        total_rev=df_er_raw['Pessoa'].nunique()
        col_a,col_b=st.columns(2)
        with col_a:
            df_b=df_er_raw.copy(); df_b['Bairro']=df_b['Bairro'].str.upper().str.strip()
            br=df_b.groupby('Bairro')['Pessoa'].nunique().reset_index(); br.columns=['Bairro','RVs']; br['%']=br['RVs']/total_rev*100
            tabela_mini("📍 Por Bairro",br.sort_values('RVs',ascending=False),'Bairro','%')
        with col_b:
            sr=df_er_raw.groupby('Papel')['Pessoa'].nunique().reset_index(); sr.columns=['Segmentação','RVs']; sr['%']=sr['RVs']/total_rev*100
            tk=df_er_raw.groupby('Papel').agg(rec=('ValorPraticado','sum'),rvs=('Pessoa','nunique')).reset_index()
            tk['tk']=tk['rec']/tk['rvs']; tk_map={r['Papel']:r['tk'] for _,r in tk.iterrows()}
            sr['Ticket']=sr['Segmentação'].map(tk_map)
            st.markdown('<p style="font-size:10px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px">🏅 Por Segmentação</p>',unsafe_allow_html=True)
            html='<div style="background:white;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0"><div style="display:flex;justify-content:space-between;padding:5px 12px;background:#f8fafc;border-bottom:1px solid #e2e8f0"><span style="font-size:10px;color:#94a3b8;font-weight:700">SEGMENTAÇÃO</span><span style="font-size:10px;color:#94a3b8;font-weight:700">RVs · % · TICKET MÉD.</span></div>'
            for _,row in sr.sort_values('RVs',ascending=False).iterrows():
                tk_str=f"R$ {row['Ticket']:,.0f}".replace(",",".") if row['Ticket']>0 else "—"
                html+=(f'<div style="display:flex;justify-content:space-between;align-items:center;padding:7px 12px;border-bottom:1px solid #f8fafc"><span style="font-size:12px;color:#475569">{row["Segmentação"]}</span><div style="display:flex;align-items:center;gap:10px"><span style="font-size:12px;color:#64748b">{int(row["RVs"])}</span><span style="font-size:12px;font-weight:700;color:#1e293b">{row["%"]:.1f}%</span><span style="font-size:11px;color:#94a3b8;min-width:80px;text-align:right">{tk_str}</span></div></div>')
            html+='</div>'
            st.markdown(html,unsafe_allow_html=True)
        st.markdown("")
        st.markdown("#### 📅 Frequência por Dia")
        dias_pt={0:'Segunda',1:'Terça',2:'Quarta',3:'Quinta',4:'Sexta',5:'Sábado',6:'Domingo'}
        df_er_raw['Data Captação']=pd.to_datetime(df_er_raw['Data Captação'],dayfirst=True,errors='coerce')
        freq=df_er_raw.groupby('Data Captação')['Pessoa'].nunique().reset_index(); freq.columns=['Data','RVs']
        freq=freq.dropna(subset=['Data']).sort_values('Data')
        freq['Label']=freq['Data'].dt.strftime('%d/%m')+'('+freq['Data'].dt.dayofweek.map(dias_pt)+')'
        fig3=go.Figure(go.Bar(x=freq['Label'],y=freq['RVs'],marker_color='#2563eb',text=freq['RVs'],textposition='outside'))
        fig3.update_layout(height=320,margin=dict(t=20,b=60),xaxis_tickangle=-45,yaxis_title="Revendedores Únicos",plot_bgcolor='white',paper_bgcolor='white')
        st.plotly_chart(fig3,use_container_width=True)
    else: st.info("ℹ️ Reprocesse os dados para ver análises detalhadas.")
    st.markdown("#### 📊 Comparativo por Caixa")
    df['pct_multi']=100-df['pct_nao_multimarca']
    df_g=df.sort_values('pedidos_multi',ascending=False)
    bg_list=[]; tc_list=[]
    for p in df_g['pct_multi']:
        b,t=_cor_bg(p); bg_list.append(b); tc_list.append(t)
    fig=go.Figure(go.Bar(x=df_g['usuario_finalizacao'],y=df_g['pct_multi'],marker_color=tc_list,text=[fmt_pct(p) for p in df_g['pct_multi']],textposition='outside'))
    fig.update_layout(height=320,margin=dict(t=10,b=10),plot_bgcolor='white',paper_bgcolor='white'); fig.update_yaxes(ticksuffix="%",title="% Multimarca")
    st.plotly_chart(fig,use_container_width=True)
    evol=[]
    for c in ciclos[-6:]:
        for rv in get_resultados_er(c['id']):
            evol.append({'Ciclo':c['nome'],'Caixa':rv['usuario_finalizacao'],'% Multimarca':100-rv['pct_nao_multimarca']})
    if evol:
        st.markdown("#### 📈 Evolução por Ciclo")
        fig2=px.line(pd.DataFrame(evol),x='Ciclo',y='% Multimarca',color='Caixa',markers=True,color_discrete_sequence=['#1e3a5f','#2563eb','#64748b','#92400e','#16a34a'])
        fig2.update_layout(height=280,margin=dict(t=10,b=10),plot_bgcolor='white',paper_bgcolor='white'); fig2.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig2,use_container_width=True)

# =============================================
# CONFIGURAÇÕES
# =============================================
def pg_config():
    requer_perfil("gerencia")
    st.title("⚙️ Configurações")
    aba=st.radio("",["Setores","Pontuação & IAF","Ciclos & Metas","Upload","Senhas","Logs"],horizontal=True)
    st.markdown("---")
    sb=get_sb(); usuario=st.session_state.get('usuario','sistema')
    if aba=="Setores":
        st.caption("Setores detectados automaticamente no upload. Defina tipo e status.")
        sdb=sb.table("setores").select("*").order("nome").execute().data or []
        if not sdb: st.info("Faça o upload primeiro.")
        else:
            for s in sdb:
                c1,c2,c3,c4=st.columns([3,2,2,1]); c1.markdown(f"**{s['nome']}**")
                with c2: ti=st.selectbox("Tipo",["financeiro","base"],index=0 if s['tipo']=='financeiro' else 1,key=f"t{s['id']}")
                with c3: at=st.selectbox("Status",["Ativo","Inativo"],index=0 if s['ativo'] else 1,key=f"a{s['id']}")
                with c4:
                    if st.button("💾",key=f"s{s['id']}"): sb.table("setores").update({"tipo":ti,"ativo":at=="Ativo"}).eq("id",s['id']).execute(); st.success("✓"); st.rerun()
    elif aba=="Pontuação & IAF":
        st.caption("Ajuste pesos e faixas.")
        t1,t2,t3=st.tabs(["Pontuação Base","Pontuação Financeiro","Faixas & IAF"])
        with t1:
            c1,c2=st.columns(2)
            with c1: pts_ir=st.number_input("Inícios+Reinícios (pts)",value=int(get_config('pts_inicios_reinicios',800)),step=50)
            with c2: pts_g=st.number_input("Meta Grupo (pts)",value=int(get_config('pts_meta_grupo',200)),step=50)
        with t2:
            c1,c2=st.columns(2)
            with c1:
                pts_bot=st.number_input("Boticário (pts)",value=int(get_config('pts_boticario',300)),step=10)
                pts_eud=st.number_input("Eudora (pts)",value=int(get_config('pts_eudora',300)),step=10)
                pts_at2=st.number_input("Atividade (pts)",value=int(get_config('pts_atividade',150)),step=10)
            with c2:
                pts_mu=st.number_input("Multimarcas (pts)",value=int(get_config('pts_multimarcas',90)),step=10)
                pts_cab=st.number_input("Cabelos % (pts)",value=int(get_config('pts_pct_cabelos',90)),step=10)
                pts_mak=st.number_input("Make % (pts)",value=int(get_config('pts_pct_make',70)),step=10)
            st.info(f"Total IAF Financeiro: {pts_bot+pts_eud+pts_at2+pts_mu+pts_cab+pts_mak} pts (meta: 1.000)")
        with t3:
            c1,c2=st.columns(2)
            with c1:
                st.caption("% da meta para pontuação")
                f50=st.number_input("≥X% → 50% pts",value=int(get_config('faixa_pontuacao_50pct',85)))
                f75=st.number_input("≥X% → 75% pts",value=int(get_config('faixa_pontuacao_75pct',95)))
                f100=st.number_input("≥X% → 100% pts",value=int(get_config('faixa_pontuacao_100pct',100)))
            with c2:
                st.caption("IAF mínimo por classificação (%)")
                br=st.number_input("Bronze ≥",value=int(get_config('faixa_bronze_min',65)))
                pr=st.number_input("Prata ≥",value=int(get_config('faixa_prata_min',75)))
                ou=st.number_input("Ouro ≥",value=int(get_config('faixa_ouro_min',85)))
                di=st.number_input("Diamante ≥",value=int(get_config('faixa_diamante_min',95)))
        if st.button("💾 Salvar",use_container_width=True):
            for k,v in [('pts_inicios_reinicios',pts_ir),('pts_meta_grupo',pts_g),('pts_boticario',pts_bot),('pts_eudora',pts_eud),('pts_atividade',pts_at2),('pts_multimarcas',pts_mu),('pts_pct_cabelos',pts_cab),('pts_pct_make',pts_mak),('faixa_pontuacao_50pct',f50),('faixa_pontuacao_75pct',f75),('faixa_pontuacao_100pct',f100),('faixa_bronze_min',br),('faixa_prata_min',pr),('faixa_ouro_min',ou),('faixa_diamante_min',di)]:
                set_config(k,str(v),usuario)
            st.success("✅ Salvo!")
    elif aba=="Ciclos & Metas":
        tc,tm=st.tabs(["Ciclos","Metas do Período"])
        with tc:
            with st.expander("➕ Novo ciclo"):
                nc=st.text_input("Nome (ex: 05/2026)"); d1,d2=st.columns(2); di=d1.date_input("Início"); dfc=d2.date_input("Fim")
                if st.button("Criar"):
                    if nc: sb.table("ciclos").insert({"nome":nc,"data_inicio":str(di),"data_fim":str(dfc),"ativo":True}).execute(); st.success("Criado!"); st.rerun()
            for c in get_ciclos():
                cc1,cc2,cc3=st.columns([3,2,2]); cc1.markdown(f"**{c['nome']}**"); cc2.markdown("✅ Ativo" if c['ativo'] else "⬜ Inativo")
                if not c['ativo']:
                    with cc3:
                        if st.button("Ativar",key=f"at{c['id']}"): sb.table("ciclos").update({"ativo":False}).execute(); sb.table("ciclos").update({"ativo":True}).eq("id",c['id']).execute(); st.rerun()
        with tm:
            ca=get_ciclo_ativo()
            if not ca: st.warning("Crie um ciclo ativo."); st.stop()
            st.caption(f"Ciclo ativo: **{ca['nome']}**")
            st.markdown("**Metas Globais**")
            mg1,mg2,mg3=st.columns(3)
            ba_v=mg1.number_input("Base Atual",min_value=0,value=int(get_config(f"base_atual_{ca['id']}",0) or 0),key="ba")
            bp_v=mg2.number_input("Base Meta PEF",min_value=0,value=int(get_config(f"base_meta_pef_{ca['id']}",0) or 0),key="bp")
            mag_v=mg3.number_input("Meta Atividade Global (%)",min_value=0.0,max_value=100.0,value=float(get_config(f"meta_atividade_global_{ca['id']}",0) or 0),step=0.1,key="mag")
            if st.button("💾 Salvar Metas Globais"):
                set_config(f"base_atual_{ca['id']}",ba_v,usuario); set_config(f"base_meta_pef_{ca['id']}",bp_v,usuario); set_config(f"meta_atividade_global_{ca['id']}",mag_v,usuario); st.success("Salvo!")
            st.markdown("---")
            setores=get_setores(); mex={m['setor_id']:m for m in get_metas(ca['id'])}
            tb,tf=st.tabs(["Base","Financeiro"])
            with tb:
                for s in [x for x in setores if x['tipo']=='base']:
                    ma=mex.get(s['id'],{})
                    with st.expander(s['nome'],expanded=False):
                        b1,b2=st.columns(2)
                        mir=b1.number_input("Meta I+R",min_value=0,value=int(ma.get('meta_inicios_reinicios',0)),key=f"mir{s['id']}")
                        rir=b2.number_input("Realizado I+R",min_value=0,value=int(ma.get('realizado_inicios_reinicios',0)),key=f"rir{s['id']}")
                        if st.button("💾 Salvar",key=f"sb{s['id']}"): upsert_meta(ca['id'],s['id'],{'meta_inicios_reinicios':mir,'realizado_inicios_reinicios':rir,'updated_by':usuario}); st.success("Salvo!")
            with tf:
                for s in [x for x in setores if x['tipo']=='financeiro']:
                    ma=mex.get(s['id'],{})
                    with st.expander(s['nome'],expanded=False):
                        f1,f2,f3=st.columns(3)
                        with f1:
                            st.caption("Receitas R$")
                            mbo=st.number_input("Boticário",min_value=0.0,value=float(ma.get('meta_boticario',0)),key=f"mb{s['id']}")
                            meu=st.number_input("Eudora",min_value=0.0,value=float(ma.get('meta_eudora',0)),key=f"me{s['id']}")
                            mou=st.number_input("OUI",min_value=0.0,value=float(ma.get('meta_oui',0)),key=f"mo{s['id']}")
                            mqd=st.number_input("QDB",min_value=0.0,value=float(ma.get('meta_qdb',0)),key=f"mq{s['id']}")
                            mca=st.number_input("Cabelos R$",min_value=0.0,value=float(ma.get('meta_cabelos',0)),key=f"mc{s['id']}")
                            mma=st.number_input("Make R$",min_value=0.0,value=float(ma.get('meta_make',0)),key=f"mm{s['id']}")
                        with f2:
                            st.caption("Indicadores %")
                            mmu=st.number_input("Multimarcas%",0.0,100.0,float(ma.get('meta_multimarcas',0)),key=f"mmu{s['id']}")
                            mpc=st.number_input("Cabelos%",0.0,100.0,float(ma.get('meta_pct_cabelos',0)),key=f"mpc{s['id']}")
                            mpm=st.number_input("Make%",0.0,100.0,float(ma.get('meta_pct_make',0)),key=f"mpm{s['id']}")
                            mat=st.number_input("Atividade%",0.0,100.0,float(ma.get('meta_atividade',0)),key=f"mat{s['id']}")
                        with f3:
                            st.caption("Base")
                            mtb=st.number_input("Tamanho Base",0,value=int(ma.get('tamanho_base',0)),key=f"mtb{s['id']}")
                        if st.button("💾 Salvar",key=f"sf{s['id']}"): upsert_meta(ca['id'],s['id'],{'meta_boticario':mbo,'meta_eudora':meu,'meta_oui':mou,'meta_qdb':mqd,'meta_cabelos':mca,'meta_make':mma,'meta_multimarcas':mmu,'meta_pct_cabelos':mpc,'meta_pct_make':mpm,'meta_atividade':mat,'tamanho_base':mtb,'updated_by':usuario}); st.success("Salvo!")
    elif aba=="Upload":
        requer_perfil("admin")
        st.caption("Carregue as planilhas do ERP para o ciclo ativo.")
        ca=get_ciclo_ativo()
        if not ca: st.warning("Sem ciclo ativo."); return
        st.info(f"Ciclo: **{ca['nome']}**")
        uploaded={}; c1u,c2u=st.columns(2)
        for i,nm in enumerate(ARQS):
            with (c1u if i%2==0 else c2u):
                f=st.file_uploader(f"📁 {nm}.xlsx",type=['xlsx'],key=f"up{nm}")
                if f: uploaded[nm]=f
        if uploaded and st.button("🚀 Processar",use_container_width=True,type="primary"):
            with st.spinner("Processando..."):
                try:
                    dfs={}
                    for nm,arq in uploaded.items():
                        dfs[nm]=pd.read_excel(arq) if nm in ['ER','Ativos'] else ler_planilha(arq,nm)
                    # Sincronizar setores
                    se=set()
                    for nm in ['Boticario','Cabelos','Eudora','Make','Oui','QDB','Ativos']:
                        if nm in dfs and 'Setor' in dfs[nm].columns:
                            for s in dfs[nm]['Setor'].dropna().unique(): se.add(str(s).strip())
                    ex_s={s['nome'] for s in (sb.table("setores").select("nome").execute().data or [])}
                    for s in se-ex_s: sb.table("setores").insert({"nome":s,"tipo":"financeiro","ativo":True}).execute()
                    cfg={r['chave']:r['valor'] for r in (sb.table("configuracoes").select("chave,valor").execute().data or [])}
                    rp=processar_ciclo(dfs,get_metas(ca['id']),get_setores(),cfg)
                    for r in rp['resultados']: r['ciclo_id']=ca['id']; sb.table("resultados").upsert(r,on_conflict="ciclo_id,setor_id").execute()
                    for r in rp['resultados_er']: r['ciclo_id']=ca['id']; sb.table("resultados_er").upsert(r,on_conflict="ciclo_id,usuario_finalizacao").execute()
                    ag=rp.get('ativos_unicos_global',0); st.session_state['ativos_unicos_global']=ag
                    def _uc(k,v):
                        ex=sb.table("configuracoes").select("id").eq("chave",k).execute()
                        if ex.data: sb.table("configuracoes").update({"valor":str(v),"updated_by":usuario}).eq("chave",k).execute()
                        else: sb.table("configuracoes").insert({"chave":k,"valor":str(v),"updated_by":usuario}).execute()
                    _uc(f"ativos_unicos_{ca['id']}",ag)
                    if 'ER' in dfs: st.session_state['df_er_raw']=dfs['ER']
                    if 'Make' in dfs: st.session_state['df_make_raw']=dfs['Make']
                    if 'Cabelos' in dfs: st.session_state['df_cab_raw']=dfs['Cabelos']
                    try:
                        if 'ER' in dfs:
                            er_s=set(int(x) for x in dfs['ER']['Pessoa'].dropna().unique())
                            rev_er_t=len(er_s); rev_mu_t=0; rev_mk_t=0; rev_cb_t=0; cb_l=[]; mk_l=[]
                            if 'Ativos' in dfs:
                                dfm2=calc_multimarcas(dfs['Ativos'],dfs)
                                ms=set(int(x) for x in dfm2[dfm2['is_multimarca']]['CodigoRevendedora'].dropna().unique())
                                rev_mu_t=len(er_s&ms)
                            if 'Make' in dfs:
                                mks=set(int(x) for x in dfs['Make']['CodigoRevendedora'].dropna().unique())
                                mk_l=[int(x) for x in (er_s&mks)]; rev_mk_t=len(mk_l)
                            if 'Cabelos' in dfs:
                                cbs=set(int(x) for x in dfs['Cabelos']['CodigoRevendedora'].dropna().unique())
                                cb_l=[int(x) for x in (er_s&cbs)]; rev_cb_t=len(cb_l)
                            for k2,v2 in [(f"er_rev_total_{ca['id']}",rev_er_t),(f"er_rev_multi_{ca['id']}",rev_mu_t),(f"er_rev_make_{ca['id']}",rev_mk_t),(f"er_rev_cab_{ca['id']}",rev_cb_t),(f"er_cab_list_{ca['id']}",_json.dumps(cb_l)),(f"er_make_list_{ca['id']}",_json.dumps(mk_l))]:
                                _uc(k2,v2)
                    except Exception as e_er: st.warning(f"⚠️ Métricas ER não salvas: {e_er}")
                    for nm in uploaded: log_upload(ca['id'],nm,usuario)
                    st.success(f"✅ {len(uploaded)} arquivo(s) processados!")
                except Exception as e: st.error(f"❌ Erro: {e}")
    elif aba=="Senhas":
        requer_perfil("admin")
        st.warning("⚠️ Alterar senhas afeta todos os usuários.")
        s1,s2,s3=st.columns(3)
        with s1:
            st.caption("Leitura"); nl=st.text_input("Nova",type="password",key="nl")
            if st.button("Alterar",key="al"):
                if nl: set_config('senha_leitura',nl,usuario); st.success("✓")
        with s2:
            st.caption("Gerência"); ng=st.text_input("Nova",type="password",key="ng")
            if st.button("Alterar",key="ag"):
                if ng: set_config('senha_gerencia',ng,usuario); st.success("✓")
        with s3:
            st.caption("Admin"); na=st.text_input("Nova",type="password",key="na")
            if st.button("Alterar",key="aa"):
                if na: set_config('senha_admin',na,usuario); st.success("✓")
    elif aba=="Logs":
        tl1,tl2=st.tabs(["Uploads","Alterações"])
        with tl1:
            ca=get_ciclo_ativo()
            if ca:
                logs=get_logs(ca['id'])
                if logs:
                    dl=pd.DataFrame(logs); dl['data_upload']=pd.to_datetime(dl['data_upload']).dt.strftime('%d/%m/%Y %H:%M')
                    st.dataframe(dl[['arquivo','usuario','data_upload']],use_container_width=True)
                else: st.info("Sem uploads.")
        with tl2:
            r=sb.table("log_alteracoes").select("*").order("created_at",desc=True).limit(50).execute()
            if r.data:
                dla=pd.DataFrame(r.data); dla['created_at']=pd.to_datetime(dla['created_at']).dt.strftime('%d/%m/%Y %H:%M')
                st.dataframe(dla[['tabela','campo','valor_anterior','valor_novo','usuario','created_at']],use_container_width=True)
            else: st.info("Sem alterações.")

# =============================================
# MAIN
# =============================================
check_auth()
if not st.session_state.get("perfil"):
    login_screen()
else:
    ciclos=get_ciclos(); ciclo_ativo=get_ciclo_ativo()
    with st.sidebar:
        iniciais="".join([p[0].upper() for p in st.session_state.usuario.split()[:2]])
        st.markdown(f'<div style="padding:16px 8px 12px"><div style="font-size:15px;font-weight:700;color:#f1f5f9;margin-bottom:12px">💼 Venda Direta</div><div style="display:flex;align-items:center;gap:10px;padding:10px;background:#334155;border-radius:8px"><div style="width:32px;height:32px;border-radius:50%;background:#f59e0b;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;color:#1e293b;flex-shrink:0">{iniciais}</div><div><div style="font-size:12px;font-weight:600;color:#f1f5f9">{st.session_state.usuario}</div><div style="font-size:10px;color:#64748b">{st.session_state.perfil}</div></div></div></div>',unsafe_allow_html=True)
        if ciclos:
            nc=[c['nome'] for c in ciclos]; ia=next((i for i,c in enumerate(ciclos) if c['ativo']),0)
            sn=st.selectbox("Ciclo",nc,index=ia); cs=next((c for c in ciclos if c['nome']==sn),ciclo_ativo)
            st.session_state.ciclo_sel_id=cs['id'] if cs else None
        st.markdown("<hr style='border-color:#334155;margin:8px 0'>",unsafe_allow_html=True)
        MENU=[("🏠 Home","pg_home"),("👥 Base","pg_base"),("💼 Financeiro","pg_financeiro"),("🏪 ER","pg_er"),("⚙️ Configurações","pg_config")]
        if 'pg_atual' not in st.session_state: st.session_state.pg_atual="🏠 Home"
        for label,_ in MENU:
            ativo=st.session_state.pg_atual==label
            if ativo:
                st.markdown(f'<div style="background:#2563eb;border-radius:8px;padding:9px 14px;font-size:13px;color:white;font-weight:600;margin-bottom:3px">{label}</div>',unsafe_allow_html=True)
            else:
                if st.button(label,key=f"nav_{label}",use_container_width=True):
                    st.session_state.pg_atual=label; st.rerun()
        st.markdown("<hr style='border-color:#334155;margin:8px 0'>",unsafe_allow_html=True)
        if st.button("Sair",use_container_width=True):
            st.session_state.perfil=None; st.session_state.usuario=None; st.rerun()
    cid=st.session_state.get('ciclo_sel_id')
    pg=st.session_state.get('pg_atual',"🏠 Home")
    if pg=="🏠 Home": pg_home(cid)
    elif pg=="👥 Base": pg_base(cid)
    elif pg=="💼 Financeiro": pg_financeiro(cid)
    elif pg=="🏪 ER": pg_er(cid)
    elif pg=="⚙️ Configurações": pg_config()
