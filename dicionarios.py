# dicionarios.py
from flask import Blueprint, render_template_string, request, session, redirect, url_for
from decorators import ip_permitido, requer_senha, get_db

dicionarios_bp = Blueprint('dicionarios', __name__)

@dicionarios_bp.route("/admin/dicionarios", methods=["GET", "POST"])
@ip_permitido
@requer_senha
def admin_dicionarios():
    if not session.get("admin"):
        return "Acesso restrito ao supervisor.", 403
    msg = ""
    conn = get_db()
    # Garantir que tabelas auxiliares existam
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS operacoes (nome TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS cids (codigo TEXT PRIMARY KEY, descricao TEXT);
        CREATE TABLE IF NOT EXISTS sites (nome TEXT PRIMARY KEY);
    """)
    if request.method == "POST":
        tipo = request.form.get("tipo")
        valor = request.form.get("valor", "").strip()
        if tipo == "operacao" and valor:
            conn.execute("INSERT OR IGNORE INTO operacoes (nome) VALUES (?)", (valor.upper(),))
            conn.commit()
            msg = "Operação adicionada."
        elif tipo == "cid" and valor:
            partes = valor.split("-", 1)
            codigo = partes[0].strip().upper()
            descricao = partes[1].strip() if len(partes) > 1 else ""
            conn.execute("INSERT OR REPLACE INTO cids (codigo, descricao) VALUES (?, ?)", (codigo, descricao))
            conn.commit()
            msg = "CID adicionado."
        elif tipo == "site" and valor:
            conn.execute("INSERT OR IGNORE INTO sites (nome) VALUES (?)", (valor,))
            conn.commit()
            msg = "Site adicionado."
    operacoes = [r['nome'] for r in conn.execute("SELECT nome FROM operacoes ORDER BY nome").fetchall()]
    cids = [f"{r['codigo']} - {r['descricao']}" for r in conn.execute("SELECT * FROM cids ORDER BY codigo").fetchall()]
    sites = [r['nome'] for r in conn.execute("SELECT nome FROM sites ORDER BY nome").fetchall()]
    conn.close()
    return render_template_string(HTML_DICIONARIOS, operacoes=operacoes, cids=cids, sites=sites, msg=msg)

HTML_DICIONARIOS = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>Dicionários SESMT</title>
  <style>
    body { background: #1e1e1e; color: #ddd; font-family: Arial; padding: 20px; }
    .container { max-width: 800px; margin: auto; }
    .btn { background: #00cc99; border: none; color: #000; padding: 8px 15px; border-radius: 4px; cursor: pointer; text-decoration: none; }
    select, input { padding: 8px; background: #2a2a2a; color: #fff; border: 1px solid #555; border-radius: 3px; margin: 5px; }
  </style>
</head>
<body>
  <div class="container">
    <h2>📚 Gerenciar Dicionários</h2>
    <a href="/" class="btn">← Voltar</a>
    {% if msg %}<p style="color:#00cc99;">{{ msg }}</p>{% endif %}
    <form method="post">
      <label>Tipo:</label>
      <select name="tipo">
        <option value="operacao">Operação</option>
        <option value="cid">CID</option>
        <option value="site">Site</option>
      </select>
      <label>Valor:</label>
      <input type="text" name="valor" placeholder="Para CID: Z99 - Descrição">
      <button class="btn">Adicionar</button>
    </form>
    <h3>Operações</h3>
    <ul>{% for op in operacoes %}<li>{{ op }}</li>{% endfor %}</ul>
    <h3>CIDs</h3>
    <ul>{% for c in cids %}<li>{{ c }}</li>{% endfor %}</ul>
    <h3>Sites</h3>
    <ul>{% for s in sites %}<li>{{ s }}</li>{% endfor %}</ul>
  </div>
</body>
</html>
"""