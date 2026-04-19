from supabase import create_client
import pandas as pd
 
client = create_client(
    'https://susmetemkdovalnhtdsi.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN1c21ldGVta2RvdmFsbmh0ZHNpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY0MzY5NTQsImV4cCI6MjA5MjAxMjk1NH0.XXK_foNpOfLuppdG2sf5VMayb59M-th_NjOYKKtM-sM'
)
 
print("=== VERIFICAÇÃO COMPLETA DO BANCO ===\n")
 
# Dados diários
tabelas = ['dados_consultor', 'dados_pdv', 'dados_servicos', 'dados_treinamentos', 'dados_id_cliente']
for tabela in tabelas:
    res = client.table(tabela).select('data_upload').order('data_upload', desc=True).limit(1).execute()
    if res.data:
        data = res.data[0]['data_upload']
        total = client.table(tabela).select('id', count='exact').eq('data_upload', data).execute()
        print(f"✅ {tabela}: {total.count} registros (data: {data})")
    else:
        print(f"❌ {tabela}: VAZIO")
 
# Metas
res_m = client.table('metas').select('id', count='exact').execute()
print(f"\n✅ metas: {res_m.count} registros" if res_m.count else "\n❌ metas: VAZIO")
 
# Colunas das metas
if res_m.count:
    res_cols = client.table('metas').select('*').limit(1).execute()
    print(f"   Colunas: {list(res_cols.data[0].keys()) if res_cols.data else 'nenhuma'}")