# 🏥 Sistema de Gestão de Atestados – SESMT

Sistema web local desenvolvido em Python (Flask) para o setor de Saúde e Segurança do Trabalho (SESMT). Permite:

- 🔍 **Consulta rápida** de funcionários (por nome, matrícula, CPF ou PIS)
- 🩺 **Lançamento de atestados médicos** com validação de datas e controle de supervisor
- ✏️ **Edição e exclusão** de registros
- 📊 **Dashboards interativos** com Chart.js (CIDs, ranking, evolução mensal)
- ⚠️ **Monitoramento de alertas** – funcionários com excesso de atestados
- 📚 **Gestão de dicionários** (operações, CIDs, sites) para o supervisor
- 🔒 **Dupla autenticação** (usuário comum e supervisor) e IP whitelist
- 💾 **Backup automático** do banco SQLite

Totalmente offline, roda em rede local e não depende de internet (exceto CDN do Chart.js, facilmente substituível).

---

## 🧱 Tecnologias

- Python 3.13
- Flask
- SQLite (via `sqlite3` nativo)
- Chart.js (visualização)
- HTML5 + CSS3 (tema escuro executivo)

---

## 🚀 Como usar

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/sesmt-gestao-atestados.git
   cd sesmt-gestao-atestados

2. Instale as dependências:
   pip install -r requirements.txt

3. Configure o config.json a partir do exemplo:
    copy config.exemplo.json config.json
   # Edite config.json com seus caminhos e senhas

4. Crie o banco de dados e popule com dados do DP:
   python criar_banco_sesmt.py --popular

5. Inicie o servidor:
   python portal_sesmt.py

6. Acesse http://localhost:5050 e faça login.

📂 Estrutura do projeto (modular)
Arquivo				Função
portal_sesmt.py			Aplicação principal (rotas, templates)
decorators.py			Decoradores de segurança e conexão com banco
monitoramento.py		Blueprint de monitoramento de alertas
dicionarios.py			Blueprint de gestão de listas auxiliares
copiar_base_sesmt.py		Sincroniza dados do DP para o banco SESMT
criar_banco_sesmt.py		Cria e popula o banco SQLite
normalizar_importar.py		Importa atestados antigos de CSV
backup_banco.py			Script de backup diário


⚠️ Aviso
Este repositório contém apenas a estrutura de código. Nenhum dado real de funcionários ou atestados está incluído. O sistema foi projetado para operar exclusivamente em ambiente local

👤 Autor
Hector Enrique Dominguez Espinel
Analista de Departamento Pessoal | Automatizador de Processos de RH
LinkedIn | GitHub

📄 Licença
Este projeto é de uso interno. Para fins de portfólio, os scripts estão publicados com autorização.