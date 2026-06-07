"""
Importador de atestados antigos via CSV.
Formato esperado do CSV (separador ;):
matricula;data_atestado;data_entrega;cid;dias;tipo;medico;crm;site;operacao;observacao
"""
import csv
import sqlite3
from pathlib import Path
from datetime import datetime

BANCO = Path("sesmt.db")
ARQUIVO_CSV = Path("entradas/atestados_antigos.csv")  # <-- ajuste aqui

def normalizar_data(data_str):
    """Tenta converter datas para o formato dd/mm/aaaa."""
    if not data_str or data_str.strip() == "":
        return ""
    data_str = data_str.strip()
    # Se já está no formato dd/mm/aaaa
    try:
        datetime.strptime(data_str, "%d/%m/%Y")
        return data_str
    except:
        pass
    # Tenta dd/mm/aa (ex.: 01/04/26)
    try:
        dt = datetime.strptime(data_str, "%d/%m/%y")
        return dt.strftime("%d/%m/%Y")
    except:
        pass
    # Tenta aaaa-mm-dd
    try:
        dt = datetime.strptime(data_str, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except:
        pass
    return data_str  # mantém original se não reconhecer

def importar():
    conn = sqlite3.connect(str(BANCO))
    cursor = conn.cursor()
    
    total = 0
    erros = 0
    with open(ARQUIVO_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            matricula = row.get("matricula", "").strip()
            if not matricula:
                erros += 1
                continue

            # Busca o CPF no banco SESMT
            cpf_row = cursor.execute(
                "SELECT cpf FROM vinculos WHERE matricula = ? LIMIT 1",
                (matricula,)
            ).fetchone()
            if not cpf_row:
                # tenta buscar em funcionarios se a matrícula for o CPF (improvável)
                erros += 1
                continue
            cpf = cpf_row[0]

            data_atestado = normalizar_data(row.get("data_atestado", ""))
            data_entrega = normalizar_data(row.get("data_entrega", ""))
            cid = row.get("cid", "").strip().upper()
            dias = int(row.get("dias", 0))
            tipo = row.get("tipo", "atestado").strip().lower()
            if tipo not in ("atestado", "declaracao"):
                tipo = "atestado"
            medico = row.get("medico", "").strip()
            crm = row.get("crm", "").strip()
            site = row.get("site", "").strip()
            operacao = row.get("operacao", "").strip()
            observacao = row.get("observacao", "").strip()

            cursor.execute("""
                INSERT INTO atestados (matricula, cpf, data_atestado, data_entrega, cid, dias, tipo, medico, crm, site, operacao, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (matricula, cpf, data_atestado, data_entrega, cid, dias, tipo, medico, crm, site, operacao, observacao))
            total += 1

    conn.commit()
    conn.close()
    print(f"✅ Importação concluída: {total} atestados importados.")
    if erros > 0:
        print(f"⚠️ {erros} linhas ignoradas (matrícula não encontrada ou vazia).")

if __name__ == "__main__":
    importar()