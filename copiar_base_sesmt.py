"""
Script de sincronizacao LOCAL da base do DP para o SESMT.
Atualizado: utiliza campo 'situacao' do DP como fonte oficial.
A = ATIVO, F = AFASTADO, D = DESLIGADO.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

def carregar_config(caminho_config="config.json"):
    with open(caminho_config, "r", encoding="utf-8") as f:
        return json.load(f)

# Mapeamento direto do campo situacao para status exibido
MAPA_SITUACAO = {
    'A': 'ATIVO',
    'F': 'AFASTADO',   # ou 'AFASTADO', conforme preferir
    'D': 'DESLIGADO'
}

def traduzir_situacao(situacao):
    """Retorna o status legível com base na situação original."""
    if not situacao or situacao not in MAPA_SITUACAO:
        return 'ATIVO'   # fallback seguro
    return MAPA_SITUACAO[situacao]

def copiar_funcionarios(origem, destino):
    destino.mkdir(parents=True, exist_ok=True)
    total = 0
    for arquivo in origem.glob("*.json"):
        nome_arquivo = arquivo.name
        destino_arquivo = destino / nome_arquivo

        with open(arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)

        nome = dados.get("dados_pessoais", {}).get("nome", "NÃO INFORMADO")
        cpf = dados.get("dados_pessoais", {}).get("cpf", "")
        pis = dados.get("dados_pessoais", {}).get("pis", "")

        publico = {
            "nome": nome,
            "cpf": cpf,
            "pis": pis,
            "cpf_mascarado": cpf[:3] + ".***.***-**" if cpf else "",
            "matriculas": []
        }

        for vinculo in dados.get("vinculos", []):
            situacao_original = vinculo.get("situacao", "")
            publico["matriculas"].append({
                "matricula": vinculo.get("matricula"),
                "empresa_filial": vinculo.get("empresa_filial"),
                "data_admissao": vinculo.get("data_admissao"),
                "status": traduzir_situacao(situacao_original),
                "data_desligamento": vinculo.get("data_desligamento")
            })

        # Sobrescreve se o status mudou ou origem mais recente
        if destino_arquivo.exists():
            with open(destino_arquivo, "r", encoding="utf-8") as f:
                existente = json.load(f)
            status_antigos = [v.get("status") for v in existente.get("matriculas", [])]
            status_novos = [v["status"] for v in publico["matriculas"]]
            if status_antigos == status_novos and os.path.getmtime(arquivo) <= os.path.getmtime(destino_arquivo):
                continue

        with open(destino_arquivo, "w", encoding="utf-8") as f:
            json.dump(publico, f, indent=2, ensure_ascii=False)
        total += 1

    print(f"[OK] Funcionários sincronizados: {total} arquivos.")
    return total

# ... (copiar_afastamentos e gerar_indice permanecem idênticos)

def copiar_afastamentos(origem_funcionarios, destino_afastamentos):
    destino_afastamentos.mkdir(parents=True, exist_ok=True)
    total_eventos = 0
    for arquivo in origem_funcionarios.glob("*.json"):
        with open(arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)
        afastamentos = dados.get("afastamentos", [])
        if not afastamentos:
            continue
        for evento in afastamentos:
            matricula = evento.get("matricula")
            if not matricula:
                vinculos = dados.get("vinculos", [])
                matricula = vinculos[0].get("matricula") if vinculos else None
            if not matricula:
                continue
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            nome_arquivo = f"{matricula}_{timestamp}.json"
            registro = {
                "matricula": matricula,
                "data_inicio": evento.get("data_inicio"),
                "data_fim": evento.get("data_fim"),
                "dias": evento.get("dias"),
                "cid": evento.get("cid", ""),
                "tipo": "afastamento",
                "motivo": evento.get("motivo", "")
            }
            with open(destino_afastamentos / nome_arquivo, "w", encoding="utf-8") as f_out:
                json.dump(registro, f_out, indent=2, ensure_ascii=False)
            total_eventos += 1
    print(f"[OK] Afastamentos sincronizados: {total_eventos} eventos.")
    return total_eventos

def gerar_indice(base_funcionarios, arquivo_indice="indice_busca_sesmt.json"):
    indice = defaultdict(set)
    for arq in base_funcionarios.glob("*.json"):
        with open(arq, "r", encoding="utf-8") as f:
            func = json.load(f)
        arq_id = arq.stem
        nome = func.get("nome", "").lower()
        for parte in nome.split():
            indice[parte].add(arq_id)
        if nome:
            indice[nome].add(arq_id)
        for v in func.get("matriculas", []):
            mat = v.get("matricula")
            if mat:
                indice[mat].add(arq_id)
                indice[mat.lower()].add(arq_id)
        cpf = func.get("cpf", "")
        if cpf:
            indice[cpf].add(arq_id)
        pis = func.get("pis", "")
        if pis:
            indice[pis].add(arq_id)
    indice_list = {k: list(v) for k, v in indice.items()}
    with open(arquivo_indice, "w", encoding="utf-8") as f:
        json.dump(indice_list, f, indent=2, ensure_ascii=False)
    print(f"[OK] Índice gerado com {len(indice_list)} termos.")

def sincronizar(config):
    print(f"[{datetime.now()}] Iniciando sincronização...")
    origem_func = Path(config["caminho_base_dp_funcionarios"])
    local = Path(config["caminho_dados_locais"])
    copiar_funcionarios(origem_func, local / "funcionarios")
    copiar_afastamentos(origem_func, local / "afastamentos")
    gerar_indice(local / "funcionarios", Path("indice_busca_sesmt.json"))
    print("Sincronização concluída.\n")

if __name__ == "__main__":
    config = carregar_config()
    sincronizar(config)