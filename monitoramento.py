# monitoramento.py
from flask import Blueprint, render_template_string, request, jsonify, session
from datetime import datetime, timedelta
from decorators import ip_permitido, requer_senha, get_db

monitoramento_bp = Blueprint('monitoramento', __name__)

@monitoramento_bp.route("/monitoramento")
@ip_permitido
@requer_senha
def monitoramento():
    return render_template_string(HTML_MONITORAMENTO)

@monitoramento_bp.route("/api/alertas")
@ip_permitido
@requer_senha
def api_alertas():
    limite = int(request.args.get("limite", 15))
    dias = request.args.get("dias", "")
    empresa = request.args.get("empresa", "")
    operacao = request.args.get("operacao", "")
    ano = request.args.get("ano", "")

    conn = get_db()
    params = []
    where = []

    if empresa:
        where.append("f.cpf IN (SELECT DISTINCT cpf FROM vinculos WHERE empresa_filial LIKE ?)")
        params.append(f"%{empresa}%")
    if operacao:
        where.append("a.operacao LIKE ?")
        params.append(f"%{operacao}%")
    if dias:
        try:
            qtd = int(dias)
            data_limite = (datetime.now() - timedelta(days=qtd)).strftime("%Y-%m-%d")
            where.append("a.data_atestado >= ?")
            params.append(data_limite)
        except:
            pass
    elif ano:
        where.append("a.data_atestado LIKE ?")
        params.append(f"%/{ano}")

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    query = f"""
        SELECT a.matricula, f.nome, f.cpf, COUNT(*) as total
        FROM atestados a
        JOIN funcionarios f ON a.cpf = f.cpf
        {where_sql}
        GROUP BY a.cpf
        HAVING COUNT(*) >= ?
        ORDER BY total DESC
    """
    params.append(limite)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([{
        "matricula": r['matricula'], "nome": r['nome'],
        "cpf": r['cpf'], "total": r['total']
    } for r in rows])

HTML_MONITORAMENTO = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>Monitoramento SESMT</title>
  <style>
    body { background: #1e1e1e; color: #ddd; font-family: Arial; margin: 0; padding: 20px; }
    .container { max-width: 1200px; margin: auto; }
    .btn { background: #00cc99; border: none; color: #000; padding: 8px 15px; border-radius: 4px; cursor: pointer; text-decoration: none; margin-right: 10px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; background: #2a2a2a; }
    th, td { padding: 10px; border-bottom: 1px solid #444; }
    th { color: #00cc99; }
    input, select { padding: 8px; background: #2a2a2a; color: #fff; border: 1px solid #555; border-radius: 3px; margin-right: 10px; }
  </style>
</head>
<body>
  <div class="container">
    <h2>⚠️ Monitoramento de Atestados</h2>
    <a href="/" class="btn">← Voltar</a>
    <div style="margin: 20px 0;">
      <label>Limite:</label><input type="number" id="limite" value="15" min="1" style="width:80px;">
      <label>Período (dias):</label>
      <select id="periodo">
        <option value="">Todos</option>
        <option value="30">30 dias</option>
        <option value="60" selected>60 dias</option>
        <option value="90">90 dias</option>
        <option value="180">6 meses</option>
        <option value="365">1 ano</option>
      </select>
      <label>Ano:</label><input type="number" id="ano" placeholder="2026" style="width:80px;" disabled>
      <label>Empresa:</label><input type="text" id="empresa" placeholder="Ex.: ELO">
      <label>Operação:</label><input type="text" id="operacao" placeholder="Ex.: TIM">
      <button class="btn" onclick="carregar()">Filtrar</button>
      <button class="btn" onclick="exportarCSV()" style="background:#ff6600;">CSV</button>
    </div>
    <div id="tabela"></div>
  </div>
  <script>
    const selPeriodo = document.getElementById('periodo');
    const inpAno = document.getElementById('ano');
    selPeriodo.onchange = () => { inpAno.disabled = selPeriodo.value !== ''; if(selPeriodo.value) inpAno.value=''; };
    inpAno.oninput = () => { if(inpAno.value) selPeriodo.value=''; };
    async function carregar() {
      const params = new URLSearchParams({
        limite: document.getElementById('limite').value || 15,
        dias: selPeriodo.value,
        ano: inpAno.value,
        empresa: document.getElementById('empresa').value,
        operacao: document.getElementById('operacao').value
      });
      const resp = await fetch('/api/alertas?' + params);
      const data = await resp.json();
      let html = '<table><tr><th>Nome</th><th>Matrícula</th><th>CPF</th><th>Total</th></tr>';
      data.forEach(d => html += `<tr><td>${d.nome}</td><td>${d.matricula}</td><td>${d.cpf}</td><td><strong>${d.total}</strong></td></tr>`);
      html += '</table>';
      document.getElementById('tabela').innerHTML = data.length ? html : '<p>Nenhum resultado.</p>';
      window._dados = data;
    }
    function exportarCSV() {
      if(!window._dados) return;
      let csv = 'Nome;Matrícula;CPF;Total\\n';
      window._dados.forEach(d => csv += `${d.nome};${d.matricula};${d.cpf};${d.total}\\n`);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'}));
      a.download = 'alertas.csv';
      a.click();
    }
    window.onload = carregar;
  </script>
</body>
</html>
"""