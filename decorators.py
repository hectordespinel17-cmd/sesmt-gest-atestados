# decorators.py
from functools import wraps
from flask import session, request, redirect, url_for
import json

def carregar_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

config = carregar_config()

def ip_permitido(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        whitelist = config.get("whitelist_ips", [])
        if whitelist and request.remote_addr not in whitelist:
            return "Acesso não autorizado", 403
        return f(*args, **kwargs)
    return decorated

def requer_senha(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("autenticado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# Banco de dados (usado pelos Blueprints)
import sqlite3
from pathlib import Path

BANCO = Path("sesmt.db")

def get_db():
    conn = sqlite3.connect(str(BANCO))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn