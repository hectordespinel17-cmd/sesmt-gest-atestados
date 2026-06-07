"""
Criador do Banco de Dados SQLite do SESMT
==========================================
- Cria o arquivo sesmt.db na raiz do projeto.
- Tabelas: funcionarios, vinculos, afastamentos, atestados.
- Opção de popular com dados públicos do DP.
"""

import sqlite3
import json
import sys
from pathlib import Path

# Caminhos (ajuste conforme necessário)
BANCO_SESMT = Path(r"C:\projetos\projeto_sesmt\sesmt.db")
BANCO_DP = Path(r"C:\projetos\projeto_hector_def\dp_data\dp_hector.db")
PASTA_JSONS_DP = Path(r"C:\projetos\projeto_hector_def\dp_data\processados\funcionarios")

def criar_tabelas(conn):
    cursor = conn.cursor()
    
    # Tabela de funcionários (dados públicos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS funcionarios (
            cpf TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            pis TEXT,
            cpf_mascarado TEXT
        )
    """)
    
    # Vínculos (apenas campos públicos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vinculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf TEXT NOT NULL,
            matricula TEXT NOT NULL,
            empresa_filial TEXT,
            data_admissao TEXT,
            status TEXT CHECK(status IN ('ATIVO','AFASTADO','DESLIGADO')) DEFAULT 'ATIVO',
            data_desligamento TEXT,
            FOREIGN KEY (cpf) REFERENCES funcionarios(cpf)
        )
    """)
    
    # Afastamentos (extraídos do DP)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS afastamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf TEXT NOT NULL,
            matricula TEXT,
            data_inicio TEXT,
            data_fim TEXT,
            dias INTEGER DEFAULT 0,
            cid TEXT DEFAULT '',
            tipo TEXT DEFAULT 'afastamento',
            motivo TEXT,
            FOREIGN KEY (cpf) REFERENCES funcionarios(cpf)
        )
    """)
    
    # Atestados (lançados pela equipe SESMT)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS atestados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT NOT NULL,
            cpf TEXT NOT NULL,
            data_atestado TEXT NOT NULL,
            data_entrega TEXT,
            cid TEXT,
            dias INTEGER DEFAULT 0,
            tipo TEXT CHECK(tipo IN ('atestado','declaracao')) DEFAULT 'atestado',
            medico TEXT,
            crm TEXT,
            site TEXT,
            operacao TEXT,
            observacao TEXT,
            data_lancamento TEXT DEFAULT (datetime('now','localtime')),
            data_modificacao TEXT,
            FOREIGN KEY (cpf) REFERENCES funcionarios(cpf)
        )
    """)
    
    conn.commit()
    print("✅ Tabelas do SESMT criadas.")

def criar_indices(conn):
    cursor = conn.cursor()
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_sesmt_func_nome ON funcionarios(nome)",
        "CREATE INDEX IF NOT EXISTS idx_sesmt_vinc_cpf ON vinculos(cpf)",
        "CREATE INDEX IF NOT EXISTS idx_sesmt_vinc_mat ON vinculos(matricula)",
        "CREATE INDEX IF NOT EXISTS idx_sesmt_atest_cpf ON atestados(cpf)",
        "CREATE INDEX IF NOT EXISTS idx_sesmt_atest_mat ON atestados(matricula)",
        "CREATE INDEX IF NOT EXISTS idx_sesmt_atest_data ON atestados(data_atestado)",
        "CREATE INDEX IF NOT EXISTS idx_sesmt_afast_cpf ON afastamentos(cpf)",
    ]
    for idx in indices:
        cursor.execute(idx)
    conn.commit()
    print("✅ Índices criados.")

def popular_a_partir_do_dp(conn):
    """Copia dados públicos do banco do DP (se existir) ou dos JSONs."""
    if BANCO_DP.exists():
        print("📥 Importando do banco dp_hector.db...")
        dp_conn = sqlite3.connect(str(BANCO_DP))
        dp_conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Copiar funcionários (dados públicos)
        dps = dp_conn.execute("SELECT cpf, nome, pis FROM funcionarios").fetchall()
        for row in dps:
            cpf_mascarado = row['cpf'][:3] + ".***.***-**" if row['cpf'] else ""
            cursor.execute(
                "INSERT OR REPLACE INTO funcionarios (cpf, nome, pis, cpf_mascarado) VALUES (?, ?, ?, ?)",
                (row['cpf'], row['nome'], row['pis'], cpf_mascarado)
            )
        print(f"   👥 Funcionários: {len(dps)}")
        
        # Copiar vínculos com status traduzido
        vinculos = dp_conn.execute("""
            SELECT cpf, matricula, empresa_filial, data_admissao, 
                   situacao, data_desligamento 
            FROM vinculos
        """).fetchall()
        status_map = {'A': 'ATIVO', 'F': 'AFASTADO', 'D': 'DESLIGADO'}
        for v in vinculos:
            status = status_map.get(v['situacao'], 'ATIVO')
            cursor.execute(
                "INSERT INTO vinculos (cpf, matricula, empresa_filial, data_admissao, status, data_desligamento) VALUES (?, ?, ?, ?, ?, ?)",
                (v['cpf'], v['matricula'], v['empresa_filial'], v['data_admissao'], status, v['data_desligamento'])
            )
        print(f"   📋 Vínculos: {len(vinculos)}")
        
        # Copiar afastamentos (todos os campos)
        afastamentos = dp_conn.execute("""
            SELECT cpf, matricula, data_inicio, data_fim, dias, cid, motivo 
            FROM afastamentos
        """).fetchall()
        for a in afastamentos:
            cursor.execute(
                "INSERT INTO afastamentos (cpf, matricula, data_inicio, data_fim, dias, cid, motivo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (a['cpf'], a['matricula'], a['data_inicio'], a['data_fim'], a['dias'], a['cid'], a['motivo'])
            )
        print(f"   🏥 Afastamentos: {len(afastamentos)}")
        
        conn.commit()
        dp_conn.close()
    else:
        print("⚠️ Banco do DP não encontrado. Populando a partir dos JSONs...")
        # Fallback: leitura direta dos JSONs (similar ao script original)
        popular_via_jsons(conn)

def popular_via_jsons(conn):
    """Fallback: popula lendo os JSONs originais."""
    cursor = conn.cursor()
    total_func, total_vinc, total_afast = 0, 0, 0
    arquivos = sorted(PASTA_JSONS_DP.glob("*.json"))
    
    for arq in arquivos:
        with open(arq, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        cpf = dados['dados_pessoais']['cpf']
        nome = dados['dados_pessoais']['nome']
        pis = dados['dados_pessoais'].get('pis', '')
        cpf_masc = cpf[:3] + ".***.***-**"
        
        cursor.execute(
            "INSERT OR REPLACE INTO funcionarios (cpf, nome, pis, cpf_mascarado) VALUES (?, ?, ?, ?)",
            (cpf, nome, pis, cpf_masc)
        )
        total_func += 1
        
        for v in dados.get('vinculos', []):
            situacao = v.get('situacao', '')
            status = 'ATIVO' if situacao == 'A' else ('AFASTADO' if situacao == 'F' else 'DESLIGADO')
            cursor.execute(
                "INSERT INTO vinculos (cpf, matricula, empresa_filial, data_admissao, status, data_desligamento) VALUES (?, ?, ?, ?, ?, ?)",
                (cpf, v.get('matricula'), v.get('empresa_filial'), v.get('data_admissao'), status, v.get('data_desligamento'))
            )
            total_vinc += 1
        
        for a in dados.get('afastamentos', []):
            cursor.execute(
                "INSERT INTO afastamentos (cpf, matricula, data_inicio, data_fim, dias, cid, motivo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cpf, a.get('matricula'), a.get('data_inicio'), a.get('data_fim'), a.get('dias', 0), a.get('cid', ''), a.get('motivo', ''))
            )
            total_afast += 1
    
    conn.commit()
    print(f"   👥 Funcionários: {total_func}")
    print(f"   📋 Vínculos: {total_vinc}")
    print(f"   🏥 Afastamentos: {total_afast}")

def main():
    popular = '--popular' in sys.argv
    BANCO_SESMT.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(BANCO_SESMT))
    conn.execute("PRAGMA journal_mode=WAL")
    print(f"🗄️ Banco SESMT: {BANCO_SESMT}")
    
    criar_tabelas(conn)
    criar_indices(conn)
    
    if popular:
        print("\n📥 Populando dados públicos do DP...")
        popular_a_partir_do_dp(conn)
    
    conn.close()
    print("\n✅ Banco do SESMT pronto!")

if __name__ == "__main__":
    main()