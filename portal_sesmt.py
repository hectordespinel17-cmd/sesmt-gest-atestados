"""
Portal SESMT – Gestão de Atestados e Afastamentos (Flask + SQLite – versão modular)
"""
import csv
import io
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import json

from flask import Flask, request, render_template_string, session, redirect, url_for, jsonify, Response

# ---------- MÓDULOS EXTERNOS (decorators, monitoramento, dicionários) ----------
from decorators import ip_permitido, requer_senha, get_db
from monitoramento import monitoramento_bp
from dicionarios import dicionarios_bp

app = Flask(__name__)
app.secret_key = 'sesmt_secret_change_me'

app.register_blueprint(monitoramento_bp)
app.register_blueprint(dicionarios_bp)

# ---------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------
def carregar_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

config = carregar_config()
PASTA_SAIDAS = Path(config["caminho_saidas"])
PASTA_SAIDAS.mkdir(parents=True, exist_ok=True)
SENHA = config["senha_sesmt"]
SENHA_ADMIN = config.get("senha_admin", "admin123")

LISTA_OPERACOES = [
    "EUROP", "CLARO COMBO", "TIM", "PLANEJAMENTO", "QUALIDADE",
    "O BOTICARIO", "GESTAO EMPRESARIAL", "MIS", "SKY", "COMUNICACAO",
    "MOVIDA", "NET", "VIVO SLZ", "MOBIFACIL", "HAPVIDA", "VIVO SP",
    "NEXTEL", "EUDORA", "UNIMED", "YDUQS", "OI", "BANCO INTER",
    "WELLHUB", "TALKLINE", "COMPORTE", "THOPEN", "CLIENTE YDUQS",
    "PAYONEER", "TI", "FINANCEIRO", "RH", "COMPRAS", "VR MULT",
    "BANCO BV", "ASA INVESTMENTS", "MERCANTIL", "SORRI DAY",
    "PICPAY", "DIRECIONAL", "BANCO BS2", "SESMT", "DEP PESSOAL",
    "SECRETARIA DA SAUDE", "TREINAMENTO", "FACILITES", "INFRA",
    "JURIDICO", "GESTÃO DE ACESSSOS", "PROJETO", "MASSOTERAPIA",
    "DESENVOLVIMENTO", "PROCESSOS", "VENDAS"
]

# ---------------------------------------------------------------------
# Rotas principais do portal
# ---------------------------------------------------------------------
@app.route("/")
@ip_permitido
def index():
    return render_template_string(HTML_INDEX)

@app.route("/login", methods=["GET", "POST"])
@ip_permitido
def login():
    if request.method == "POST":
        senha = request.form.get("senha")
        if senha == SENHA_ADMIN:
            session["autenticado"] = True
            session["admin"] = True
            return redirect(url_for("index"))
        elif senha == SENHA:
            session["autenticado"] = True
            session["admin"] = False
            return redirect(url_for("index"))
        else:
            return render_template_string(HTML_LOGIN, erro="Senha incorreta.")
    return render_template_string(HTML_LOGIN, erro="")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/buscar")
@ip_permitido
def buscar():
    termo = request.args.get("q", "").strip()
    if not termo:
        return jsonify([])

    termo_lower = termo.lower()
    conn = get_db()
    query = """
        SELECT DISTINCT f.cpf, f.nome, f.cpf_mascarado
        FROM funcionarios f
        LEFT JOIN vinculos v ON f.cpf = v.cpf
        WHERE LOWER(f.nome) LIKE ?
           OR v.matricula = ?
           OR f.cpf = ?
           OR f.pis = ?
        LIMIT 20
    """
    like_termo = f"%{termo_lower}%"
    rows = conn.execute(query, (like_termo, termo, termo, termo)).fetchall()
    conn.close()

    resultados = []
    for row in rows:
        conn2 = get_db()
        vinculos = conn2.execute(
            "SELECT matricula, empresa_filial, status FROM vinculos WHERE cpf = ?",
            (row['cpf'],)
        ).fetchall()
        conn2.close()
        resultados.append({
            "nome": row['nome'],
            "arquivo": row['cpf'],
            "cpf_mascarado": row['cpf_mascarado'],
            "matriculas": [{"matricula": v['matricula'], "empresa_filial": v['empresa_filial'], "status": v['status']} for v in vinculos]
        })
    return jsonify(resultados)

@app.route("/ficha/<cpf>")
@ip_permitido
def ficha(cpf):
    conn = get_db()
    func = conn.execute("SELECT * FROM funcionarios WHERE cpf = ?", (cpf,)).fetchone()
    if not func:
        conn.close()
        return "Funcionário não encontrado", 404

    vinculos = conn.execute("SELECT * FROM vinculos WHERE cpf = ?", (cpf,)).fetchall()
    atestados = conn.execute(
        "SELECT rowid as _id, * FROM atestados WHERE cpf = ? ORDER BY data_atestado DESC",
        (cpf,)
    ).fetchall()
    afastamentos = conn.execute("SELECT * FROM afastamentos WHERE cpf = ?", (cpf,)).fetchall()
    conn.close()

    func_dict = dict(func)
    func_dict['matriculas'] = [dict(v) for v in vinculos]
    atestados_list = [dict(a) for a in atestados]
    afastamentos_list = [dict(a) for a in afastamentos]

    hoje = datetime.now().date()
    if session.get("admin"):
        data_maxima = "2999-12-31"
    else:
        data_maxima = (hoje + timedelta(days=7)).strftime("%Y-%m-%d")

    return render_template_string(HTML_FICHA,
                                  func=func_dict,
                                  atestados=atestados_list,
                                  afastamentos=afastamentos_list,
                                  operacoes=LISTA_OPERACOES,
                                  autenticado=session.get("autenticado"),
                                  admin=session.get("admin"),
                                  data_maxima=data_maxima)

@app.route("/lancar", methods=["POST"])
@ip_permitido
@requer_senha
def lancar():
    data = request.form
    matricula = data.get("matricula")
    cpf = data.get("cpf", "")

    if not session.get("admin"):
        hoje = datetime.now().date()
        limite = hoje + timedelta(days=7)
        try:
            data_at = datetime.strptime(data.get("data_atestado"), "%Y-%m-%d").date()
            if data_at > limite:
                return f"Erro: Data do atestado não pode ser maior que {limite.strftime('%d/%m/%Y')}", 400
        except:
            return "Erro: Data do atestado inválida.", 400
        try:
            data_en = datetime.strptime(data.get("data_entrega"), "%Y-%m-%d").date()
            if data_en > limite:
                return f"Erro: Data de entrega não pode ser maior que {limite.strftime('%d/%m/%Y')}", 400
        except:
            return "Erro: Data de entrega inválida.", 400

    conn = get_db()
    conn.execute("""
        INSERT INTO atestados (matricula, cpf, data_atestado, data_entrega, cid, dias, tipo, medico, crm, site, operacao, observacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        matricula, cpf,
        data.get("data_atestado"),
        data.get("data_entrega"),
        data.get("cid", ""),
        int(data.get("dias", 0)),
        data.get("tipo"),
        data.get("medico", ""),
        data.get("crm", ""),
        data.get("site", ""),
        data.get("operacao", ""),
        data.get("observacao", "")
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("ficha", cpf=cpf))

@app.route("/editar_atestado/<int:atestado_id>", methods=["GET", "POST"])
@ip_permitido
@requer_senha
def editar_atestado(atestado_id):
    conn = get_db()
    atestado = conn.execute("SELECT *, rowid as _id FROM atestados WHERE rowid = ?", (atestado_id,)).fetchone()
    if not atestado:
        conn.close()
        return "Atestado não encontrado", 404

    if request.method == "POST":
        if not session.get("admin"):
            hoje = datetime.now().date()
            limite = hoje + timedelta(days=7)
            try:
                data_at = datetime.strptime(request.form.get("data_atestado"), "%Y-%m-%d").date()
                if data_at > limite:
                    return f"Erro: Data do atestado não pode ser maior que {limite.strftime('%d/%m/%Y')}", 400
            except:
                return "Erro: Data do atestado inválida.", 400
            try:
                data_en = datetime.strptime(request.form.get("data_entrega"), "%Y-%m-%d").date()
                if data_en > limite:
                    return f"Erro: Data de entrega não pode ser maior que {limite.strftime('%d/%m/%Y')}", 400
            except:
                return "Erro: Data de entrega inválida.", 400

        conn.execute("""
            UPDATE atestados SET
                data_atestado = ?, data_entrega = ?, cid = ?, dias = ?, tipo = ?,
                medico = ?, crm = ?, site = ?, operacao = ?, observacao = ?,
                data_modificacao = datetime('now','localtime')
            WHERE rowid = ?
        """, (
            request.form.get("data_atestado"),
            request.form.get("data_entrega"),
            request.form.get("cid", ""),
            int(request.form.get("dias", 0)),
            request.form.get("tipo"),
            request.form.get("medico", ""),
            request.form.get("crm", ""),
            request.form.get("site", ""),
            request.form.get("operacao", ""),
            request.form.get("observacao", ""),
            atestado_id
        ))
        conn.commit()
        cpf = atestado['cpf']
        conn.close()
        return redirect(url_for("ficha", cpf=cpf))

    conn.close()
    data_maxima = "2999-12-31" if session.get("admin") else (datetime.now().date() + timedelta(days=7)).strftime("%Y-%m-%d")
    return render_template_string(HTML_EDITAR_ATESTADO, atestado=dict(atestado), operacoes=LISTA_OPERACOES, data_maxima=data_maxima)

@app.route("/deletar_atestado/<int:atestado_id>")
@ip_permitido
@requer_senha
def deletar_atestado(atestado_id):
    conn = get_db()
    atestado = conn.execute("SELECT cpf FROM atestados WHERE rowid = ?", (atestado_id,)).fetchone()
    if atestado:
        conn.execute("DELETE FROM atestados WHERE rowid = ?", (atestado_id,))
        conn.commit()
        cpf = atestado['cpf']
    else:
        cpf = ""
    conn.close()
    return redirect(url_for("ficha", cpf=cpf))

@app.route("/relatorio")
@ip_permitido
@requer_senha
def relatorio():
    tipo = request.args.get("tipo", "todos")
    hoje = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    if tipo == "diario":
        query = """
            SELECT a.*, f.nome 
            FROM atestados a 
            JOIN funcionarios f ON a.cpf = f.cpf 
            WHERE DATE(a.data_lancamento) = DATE('now','localtime')
            ORDER BY a.data_atestado DESC
        """
    else:
        query = """
            SELECT a.*, f.nome 
            FROM atestados a 
            JOIN funcionarios f ON a.cpf = f.cpf 
            ORDER BY a.data_atestado DESC
        """
    rows = conn.execute(query).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Matrícula", "Nome", "Data Atestado", "Dias", "CID", "Médico", "CRM", "Tipo", "Data Entrega", "Site", "Operação", "Observação"])
    for r in rows:
        writer.writerow([
            r['matricula'], r['nome'], r['data_atestado'], r['dias'], r['cid'],
            r['medico'], r['crm'], r['tipo'], r['data_entrega'],
            r['site'] or "", r['operacao'] or "", r['observacao'] or ""
        ])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arq = f"atestados_{tipo}_{timestamp}.csv"
    caminho_csv = PASTA_SAIDAS / nome_arq
    with open(caminho_csv, "w", encoding="utf-8-sig", newline="") as f:
        f.write(output.getvalue())
    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-disposition": f"attachment; filename={nome_arq}"})

@app.route("/admin/sincronizar")
@ip_permitido
@requer_senha
def sincronizar():
    subprocess.Popen(["py", "copiar_base_sesmt.py"], shell=True)
    return "Sincronização iniciada. <a href='/'>Voltar</a>"

# ---------------------------------------------------------------------
# APIs para gráficos
# ---------------------------------------------------------------------
@app.route("/relatorios")
@ip_permitido
@requer_senha
def relatorios():
    return render_template_string(HTML_RELATORIOS)

@app.route("/api/atestados_por_funcionario/<cpf>")
@ip_permitido
@requer_senha
def api_atestados_funcionario(cpf):
    dias = int(request.args.get("dias", 30))
    limite = (datetime.now() - timedelta(days=dias)).strftime("%d/%m/%Y")
    conn = get_db()
    rows = conn.execute("""
        SELECT cid, COUNT(*) as qtd 
        FROM atestados 
        WHERE cpf = ? AND data_atestado >= ? 
        GROUP BY cid 
        ORDER BY qtd DESC
    """, (cpf, limite)).fetchall()
    conn.close()
    return jsonify([{"cid": r['cid'] or "S/ CID", "quantidade": r['qtd']} for r in rows])

@app.route("/api/top_funcionarios")
@ip_permitido
@requer_senha
def api_top_funcionarios():
    meses = int(request.args.get("meses", 6))
    limite = (datetime.now() - timedelta(days=meses*30)).strftime("%d/%m/%Y")
    conn = get_db()
    rows = conn.execute("""
        SELECT a.matricula, f.nome, COUNT(*) as qtd
        FROM atestados a
        JOIN funcionarios f ON a.cpf = f.cpf
        WHERE a.data_atestado >= ?
        GROUP BY a.matricula
        ORDER BY qtd DESC
        LIMIT 10
    """, (limite,)).fetchall()
    conn.close()
    return jsonify([{"matricula": r['matricula'], "nome": r['nome'], "quantidade": r['qtd']} for r in rows])

@app.route("/api/atestados_por_mes")
@ip_permitido
@requer_senha
def api_atestados_por_mes():
    ano = int(request.args.get("ano", datetime.now().year))
    conn = get_db()
    rows = conn.execute("""
        SELECT substr(data_atestado,4,7) as mes, COUNT(*) as qtd
        FROM atestados
        WHERE data_atestado LIKE ? 
        GROUP BY mes
        ORDER BY mes
    """, (f"%/{ano}",)).fetchall()
    conn.close()
    meses = {str(i): 0 for i in range(1,13)}
    for r in rows:
        partes = r['mes'].split('/')
        if len(partes) >= 1:
            mes = str(int(partes[0]))
            meses[mes] = r['qtd']
    return jsonify([{"mes": k, "quantidade": v} for k, v in meses.items()])

@app.route("/admin/backup")
@ip_permitido
@requer_senha
def backup_banco():
    if not session.get("admin"):
        return "Acesso restrito ao supervisor.", 403
    import shutil
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("_backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2("sesmt.db", backup_dir / f"sesmt_backup_{timestamp}.db")
    return f"Backup criado: sesmt_backup_{timestamp}.db <a href='/'>Voltar</a>"

@app.route("/api/atestados_por_cid")
@ip_permitido
@requer_senha
def api_atestados_por_cid():
    meses = int(request.args.get("meses", 6))
    limite = (datetime.now() - timedelta(days=meses*30)).strftime("%d/%m/%Y")
    conn = get_db()
    rows = conn.execute("""
        SELECT cid, COUNT(*) as qtd
        FROM atestados
        WHERE data_atestado >= ?
        GROUP BY cid
        ORDER BY qtd DESC
        LIMIT 15
    """, (limite,)).fetchall()
    conn.close()
    return jsonify([{"cid": r['cid'] or "S/ CID", "quantidade": r['qtd']} for r in rows])

@app.route("/api/atestados_por_tipo")
@ip_permitido
@requer_senha
def api_atestados_por_tipo():
    meses = int(request.args.get("meses", 6))
    limite = (datetime.now() - timedelta(days=meses*30)).strftime("%d/%m/%Y")
    conn = get_db()
    rows = conn.execute("""
        SELECT tipo, COUNT(*) as qtd
        FROM atestados
        WHERE data_atestado >= ?
        GROUP BY tipo
    """, (limite,)).fetchall()
    conn.close()
    return jsonify([{"tipo": r['tipo'], "quantidade": r['qtd']} for r in rows])

# ---------------------------------------------------------------------
# Templates (somente os do portal principal)
# ---------------------------------------------------------------------
HTML_INDEX = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>SESMT – Consulta</title>
  <style>
    body { background: #1e1e1e; color: #ddd; font-family: Arial; margin: 0; padding: 20px; }
    .container { max-width: 1000px; margin: auto; }
    .header { display: flex; justify-content: space-between; align-items: center; }
    .logo { color: #00cc99; font-size: 24px; font-weight: bold; }
    .btn { background: #00cc99; border: none; color: #000; padding: 8px 15px; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin: 5px; }
    .btn-outline { background: transparent; border: 1px solid #00cc99; color: #00cc99; }
    .search { margin: 20px 0; display: flex; }
    input[type="text"] { flex: 1; padding: 10px; background: #2a2a2a; border: 1px solid #555; color: #fff; border-radius: 4px; }
    .results { background: #2a2a2a; border-radius: 5px; margin-top: 20px; }
    .result-item { padding: 10px; border-bottom: 1px solid #444; cursor: pointer; }
    .result-item:hover { background: #333; }
    .admin-badge { background: #ff6600; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-left: 10px; }
    .menu { margin-bottom: 15px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo">🏥 SESMT {% if session.admin %}<span class="admin-badge">🔓 Supervisor</span>{% endif %}</div>
      <div>
        {% if session.autenticado %}
        <a href="/relatorios" class="btn">📊 Relatórios</a>
        <a href="/monitoramento" class="btn">⚠️ Monitoramento</a>
        {% if session.admin %}<a href="/admin/dicionarios" class="btn">📚 Dicionários</a>{% endif %}
        <a href="/logout" class="btn btn-outline">Sair</a>
        {% else %}
        <a href="/login" class="btn">Entrar</a>
        {% endif %}
      </div>
    </div>
    <div class="search">
      <input type="text" id="busca" placeholder="Nome, matrícula, CPF ou PIS..." autofocus>
      <button id="btn-buscar" class="btn" style="margin-left:10px;">🔍 Buscar</button>
    </div>
    <div class="results" id="resultados"></div>
    {% if session.autenticado %}
    <div style="margin-top:20px;">
      <a href="/admin/sincronizar" class="btn" onclick="return confirm('A sincronização pode levar alguns minutos. Continuar?')">🔄 Atualizar Base</a>
      <a href="/relatorio?tipo=diario" class="btn">📅 Exportar Hoje</a>
      <a href="/relatorio?tipo=todos" class="btn">📁 Exportar Histórico</a>
      {% if session.admin %}<a href="/admin/backup" class="btn">💾 Backup Banco</a>{% endif %}
    </div>
    {% endif %}
  </div>
  <script>
    const busca = document.getElementById('busca');
    const resultados = document.getElementById('resultados');
    const btnBuscar = document.getElementById('btn-buscar');
    async function executarBusca() {
      const q = busca.value.trim();
      if (q.length < 2) { resultados.innerHTML = ''; return; }
      const resp = await fetch(`/buscar?q=${encodeURIComponent(q)}`);
      const data = await resp.json();
      resultados.innerHTML = data.map(f => `
        <div class="result-item" onclick="window.location='/ficha/${f.arquivo}'">
          <strong>${f.nome}</strong> – ${f.matriculas[0]?.empresa_filial || ''} (Matrícula: ${f.matriculas[0]?.matricula || 'N/A'})
        </div>
      `).join('');
    }
    let timer;
    busca.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(executarBusca, 300);
    });
    busca.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        clearTimeout(timer);
        executarBusca();
      }
    });
    btnBuscar.addEventListener('click', executarBusca);
  </script>
</body>
</html>
"""

HTML_LOGIN = """
<!DOCTYPE html>
<html>
<head><title>SESMT – Login</title></head>
<body style="background:#1e1e1e; display:flex; justify-content:center; align-items:center; height:100vh;">
  <form method="post" style="background:#2a2a2a; padding:30px; border-radius:10px;">
    <h2 style="color:#00cc99;">Acesso SESMT</h2>
    {% if erro %}<p style="color:red;">{{ erro }}</p>{% endif %}
    <input type="password" name="senha" placeholder="Senha" required style="width:100%; padding:10px; margin:10px 0; background:#1e1e1e; color:#fff; border:1px solid #555;">
    <button type="submit" class="btn" style="width:100%; background:#00cc99; border:none; color:#000; padding:10px; border-radius:4px; cursor:pointer;">Entrar</button>
  </form>
</body>
</html>
"""

HTML_FICHA = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>Ficha do Funcionário</title>
  <style>
    body { background: #1e1e1e; color: #ddd; font-family: Arial; margin: 0; padding: 20px; }
    .container { max-width: 900px; margin: auto; }
    .ficha { background: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
    .btn { background: #00cc99; border: none; color: #000; padding: 8px 15px; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }
    table { width: 100%; border-collapse: collapse; margin: 10px 0; }
    th, td { padding: 8px; text-align: left; border-bottom: 1px solid #444; font-size: 0.9em; }
    th { color: #00cc99; }
    .form-lancamento { background: #2a2a2a; padding: 20px; border-radius: 8px; }
    input, select, textarea { width: 100%; padding: 8px; margin: 5px 0; background: #1e1e1e; color: #fff; border: 1px solid #555; border-radius: 3px; }
    .secao { margin: 20px 0; }
    .obs-icon { cursor: help; color: #00cc99; }
    .admin-badge { background: #ff6600; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
  </style>
</head>
<body>
  <div class="container">
    <a href="/" style="color:#00cc99;">← Voltar</a>
    <div class="ficha">
      <h2>{{ func.nome or "NÃO INFORMADO" }}</h2>
      {% if autenticado %}
        <p>CPF: {{ func.cpf or "N/I" }} | PIS: {{ func.pis or "N/I" }}</p>
      {% else %}
        <p>CPF: {{ func.cpf_mascarado or "N/I" }}</p>
      {% endif %}
      {% for v in func.matriculas or [] %}
      <p>🏢 {{ v.empresa_filial }} | Matrícula: {{ v.matricula }} | Status: <strong>{{ v.status }}</strong></p>
      {% endfor %}
    </div>

    {% if not autenticado %}
      <p style="color:orange;">⚠️ Faça <a href="/login" style="color:#00cc99;">login</a> para ver detalhes dos atestados/afastamentos e lançar.</p>
    {% else %}
      {% if admin %}<p class="admin-badge">🔓 Modo Supervisor – datas sem restrição</p>{% endif %}
      <div class="secao">
        <h3>📋 Atestados</h3>
        {% if atestados %}
        <table>
          <tr>
            <th>Data Atestado</th><th>Dias</th><th>CID</th><th>Médico</th><th>CRM</th><th>Tipo</th><th>Site</th><th>Operação</th><th>Obs.</th><th>Ação</th>
          </tr>
          {% for a in atestados %}
          <tr>
            <td>{{ a.data_atestado }}</td>
            <td>{{ a.dias }}</td>
            <td>{{ a.cid }}</td>
            <td>{{ a.medico }}</td>
            <td>{{ a.crm }}</td>
            <td>{{ a.tipo }}</td>
            <td>{{ a.site or "" }}</td>
            <td>{{ a.operacao or "" }}</td>
            <td>{% if a.observacao %}<span class="obs-icon" title="{{ a.observacao }}">💬</span>{% endif %}</td>
            <td>
              <a href="/editar_atestado/{{ a._id }}" style="color:#ffcc00; margin-right:5px;" title="Editar">✏️</a>
              <a href="/deletar_atestado/{{ a._id }}" style="color:red;" onclick="return confirm('Excluir este atestado?')">❌</a>
            </td>
          </tr>
          {% endfor %}
        </table>
        {% else %}<p>Nenhum atestado registrado.</p>{% endif %}
      </div>

      <div class="secao">
        <h3>🏥 Afastamentos</h3>
        {% if afastamentos %}
        <table>
          <tr><th>Início</th><th>Fim</th><th>Dias</th><th>CID</th><th>Tipo</th><th>Motivo</th></tr>
          {% for af in afastamentos %}
          <tr>
            <td>{{ af.data_inicio }}</td><td>{{ af.data_fim }}</td><td>{{ af.dias }}</td><td>{{ af.cid }}</td><td>{{ af.tipo }}</td><td>{{ af.motivo }}</td>
          </tr>
          {% endfor %}
        </table>
        {% else %}<p>Nenhum afastamento registrado.</p>{% endif %}
      </div>

      <div class="form-lancamento">
        <h3>🩺 Lançar Atestado</h3>
        <form action="/lancar" method="post">
          <input type="hidden" name="matricula" value="{{ func.matriculas[0].matricula if func.matriculas else '' }}">
          <input type="hidden" name="cpf" value="{{ func.cpf }}">
          <label>Data Atestado:</label><input type="date" name="data_atestado" required max="{{ data_maxima }}">
          <label>Data Entrega:</label><input type="date" name="data_entrega" required max="{{ data_maxima }}">
          <label>CID:</label><input type="text" name="cid">
          <label>Dias:</label><input type="number" name="dias" required>
          <label>Tipo:</label>
          <select name="tipo">
            <option value="atestado">Atestado</option>
            <option value="declaracao">Declaração</option>
          </select>
          <label>Médico:</label><input type="text" name="medico">
          <label>CRM:</label><input type="text" name="crm">
          <label>Site:</label><input type="text" name="site" placeholder="Ex.: São Paulo, Rio...">
          <label>Operação:</label>
          <select name="operacao">
            <option value="">-- Selecione --</option>
            {% for op in operacoes %}
            <option value="{{ op }}">{{ op }}</option>
            {% endfor %}
          </select>
          <label>Observação:</label><textarea name="observacao" rows="2" placeholder="Ex.: teste, pendência..."></textarea>
          <button type="submit" class="btn">Salvar</button>
        </form>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""

HTML_EDITAR_ATESTADO = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>Editar Atestado</title>
  <style>
    body { background: #1e1e1e; color: #ddd; font-family: Arial; padding: 20px; }
    .container { max-width: 600px; margin: auto; }
    h2 { color: #00cc99; }
    .btn { background: #00cc99; border: none; color: #000; padding: 10px 20px; border-radius: 4px; cursor: pointer; text-decoration: none; }
    input, select, textarea { width: 100%; padding: 8px; margin: 5px 0; background: #2a2a2a; color: #fff; border: 1px solid #555; border-radius: 3px; }
    label { margin-top: 10px; display: block; }
  </style>
</head>
<body>
  <div class="container">
    <h2>✏️ Editar Atestado</h2>
    <form method="post">
      <label>Data Atestado:</label><input type="date" name="data_atestado" value="{{ atestado.data_atestado }}" required max="{{ data_maxima }}">
      <label>Data Entrega:</label><input type="date" name="data_entrega" value="{{ atestado.data_entrega }}" required max="{{ data_maxima }}">
      <label>CID:</label><input type="text" name="cid" value="{{ atestado.cid }}">
      <label>Dias:</label><input type="number" name="dias" value="{{ atestado.dias }}" required>
      <label>Tipo:</label>
      <select name="tipo">
        <option value="atestado" {% if atestado.tipo == 'atestado' %}selected{% endif %}>Atestado</option>
        <option value="declaracao" {% if atestado.tipo == 'declaracao' %}selected{% endif %}>Declaração</option>
      </select>
      <label>Médico:</label><input type="text" name="medico" value="{{ atestado.medico }}">
      <label>CRM:</label><input type="text" name="crm" value="{{ atestado.crm }}">
      <label>Site:</label><input type="text" name="site" value="{{ atestado.site }}">
      <label>Operação:</label>
      <select name="operacao">
        <option value="">-- Selecione --</option>
        {% for op in operacoes %}
        <option value="{{ op }}" {% if atestado.operacao == op %}selected{% endif %}>{{ op }}</option>
        {% endfor %}
      </select>
      <label>Observação:</label><textarea name="observacao" rows="2">{{ atestado.observacao }}</textarea>
      <br><br>
      <button type="submit" class="btn">💾 Salvar Alterações</button>
      <a href="javascript:history.back()" style="color:#ff6600; margin-left:15px;">Cancelar</a>
    </form>
  </div>
</body>
</html>
"""

HTML_RELATORIOS = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>SESMT – Relatórios</title>
  <style>
    body { background: #1e1e1e; color: #ddd; font-family: Arial; margin: 0; padding: 20px; }
    .container { max-width: 1200px; margin: auto; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .logo { color: #00cc99; font-size: 24px; font-weight: bold; }
    .btn { background: #00cc99; border: none; color: #000; padding: 8px 15px; border-radius: 4px; cursor: pointer; text-decoration: none; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .card { background: #2a2a2a; padding: 20px; border-radius: 8px; }
    canvas { width: 100% !important; height: 300px !important; }
    .filtros { margin-bottom: 20px; }
    select, input { padding: 8px; background: #1e1e1e; color: #fff; border: 1px solid #555; border-radius: 3px; margin-right: 10px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo">📊 Relatórios SESMT</div>
      <a href="/" class="btn">← Voltar</a>
    </div>
    <div class="filtros">
      <label>Período (meses):</label>
      <select id="filtroMeses" onchange="atualizarGraficos()">
        <option value="3">3 meses</option>
        <option value="6" selected>6 meses</option>
        <option value="12">12 meses</option>
      </select>
      <label>Ano:</label>
      <input type="number" id="filtroAno" value="2026" onchange="atualizarGraficos()" style="width:100px;">
      <label>CPF para análise individual:</label>
      <input type="text" id="filtroCPF" placeholder="CPF" onchange="atualizarGraficos()" style="width:150px;">
      <label>Dias:</label>
      <select id="filtroDias" onchange="atualizarGraficos()">
        <option value="15">15 dias</option>
        <option value="30" selected>30 dias</option>
        <option value="60">60 dias</option>
      </select>
    </div>
    <div class="grid">
      <div class="card"><h3>📅 Atestados por Mês</h3><canvas id="chartMes"></canvas></div>
      <div class="card"><h3>🩺 Atestados por CID</h3><canvas id="chartCID"></canvas></div>
      <div class="card"><h3>👥 Top 10 Funcionários</h3><canvas id="chartTop"></canvas></div>
      <div class="card"><h3>📋 Atestado vs Declaração</h3><canvas id="chartTipo"></canvas></div>
      <div class="card" style="grid-column: span 2;"><h3>🔍 Atestados por Funcionário (CID)</h3><canvas id="chartFunc"></canvas></div>
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script>
    Chart.defaults.color = '#ddd';
    Chart.defaults.borderColor = '#444';
    let charts = {};
    async function fetchJSON(url) {
      const resp = await fetch(url);
      return await resp.json();
    }
    function destroyChart(key) {
      if (charts[key]) { charts[key].destroy(); }
    }
    async function atualizarGraficos() {
      const meses = document.getElementById('filtroMeses').value;
      const ano = document.getElementById('filtroAno').value;
      const cpf = document.getElementById('filtroCPF').value.trim();
      const dias = document.getElementById('filtroDias').value;

      const dataMes = await fetchJSON(`/api/atestados_por_mes?ano=${ano}`);
      const labelsMes = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
      const valoresMes = labelsMes.map((_, i) => {
        const item = dataMes.find(d => d.mes == (i+1));
        return item ? item.quantidade : 0;
      });
      destroyChart('mes');
      charts.mes = new Chart(document.getElementById('chartMes'), {
        type: 'line',
        data: { labels: labelsMes, datasets: [{ label: 'Atestados', data: valoresMes, borderColor: '#00cc99', tension: 0.3 }] },
        options: { plugins: { legend: { display: false } } }
      });

      const dataCID = await fetchJSON(`/api/atestados_por_cid?meses=${meses}`);
      destroyChart('cid');
      charts.cid = new Chart(document.getElementById('chartCID'), {
        type: 'bar',
        data: { labels: dataCID.map(d => d.cid), datasets: [{ label: 'Quantidade', data: dataCID.map(d => d.quantidade), backgroundColor: '#00cc99' }] },
        options: { plugins: { legend: { display: false } } }
      });

      const dataTop = await fetchJSON(`/api/top_funcionarios?meses=${meses}`);
      destroyChart('top');
      charts.top = new Chart(document.getElementById('chartTop'), {
        type: 'bar',
        data: { labels: dataTop.map(d => d.nome.substring(0,20)), datasets: [{ label: 'Atestados', data: dataTop.map(d => d.quantidade), backgroundColor: '#ff6600' }] },
        options: { indexAxis: 'y', plugins: { legend: { display: false } } }
      });

      const dataTipo = await fetchJSON(`/api/atestados_por_tipo?meses=${meses}`);
      destroyChart('tipo');
      charts.tipo = new Chart(document.getElementById('chartTipo'), {
        type: 'doughnut',
        data: { labels: dataTipo.map(d => d.tipo), datasets: [{ data: dataTipo.map(d => d.quantidade), backgroundColor: ['#00cc99','#ff6600'] }] }
      });

      destroyChart('func');
      if (cpf) {
        const dataFunc = await fetchJSON(`/api/atestados_por_funcionario/${cpf}?dias=${dias}`);
        if (dataFunc.length > 0) {
          charts.func = new Chart(document.getElementById('chartFunc'), {
            type: 'bar',
            data: { labels: dataFunc.map(d => d.cid), datasets: [{ label: 'Atestados', data: dataFunc.map(d => d.quantidade), backgroundColor: '#00cc99' }] },
            options: { plugins: { legend: { display: false } } }
          });
        }
      }
    }
    window.onload = atualizarGraficos;
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config["porta"], debug=False)