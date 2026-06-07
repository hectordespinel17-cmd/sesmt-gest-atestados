"""
Backup diário do banco sesmt.db para a pasta _backups.
Execute via Agendador de Tarefas do Windows (diário, às 06:00).
"""
import shutil
from datetime import datetime
from pathlib import Path

BANCO = Path("sesmt.db")
BACKUP_DIR = Path("_backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_nome = f"sesmt_backup_{timestamp}.db"
shutil.copy2(BANCO, BACKUP_DIR / backup_nome)
print(f"Backup criado: {backup_nome}")