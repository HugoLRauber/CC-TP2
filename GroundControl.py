import urllib.request
import json
import time
import os
import sys

# Configuração
IP_NAVE_MAE = "127.0.0.1"
PORTA_API = 8080
# Agora apontamos para um endpoint específico
URL_ENDPOINT = f"http://{IP_NAVE_MAE}:{PORTA_API}/api/global"

def limpar_ecra():
    os.system('cls' if os.name == 'nt' else 'clear')

def obter_dados():
    try:
        # Faz pedido GET ao endpoint /api/global
        with urllib.request.urlopen(URL_ENDPOINT, timeout=2) as response:
            if response.status == 200:
                return json.loads(response.read().decode())
            return None
    except Exception:
        return None

def barra(p):
    cheio = int(p/10); vazio = 10-cheio
    cor = "\033[92m" if p>60 else "\033[93m" if p>30 else "\033[91m"
    return f"{cor}[{'#'*cheio}{'-'*vazio}]\033[0m"

def menu_frota(dados):
    print("\n--- [1] ESTADO DA FROTA (Endpoint: /api/telemetria) ---")
    # Nota: Aqui usamos os dados globais, mas num cliente real poderiamos
    # fazer um pedido específico a /api/telemetria
    telemetria = dados.get("telemetria", {})
    if not telemetria:
        print(" (Nenhum rover ligado)")
    else:
        print(f" {'NOME':<15} | {'BAT':<15} | {'TEMP':<8} | {'STATUS':<10}")
        print("-" * 55)
        for nome, info in telemetria.items():
            bat = info.get('bat', 0); temp = info.get('temp', 0); st = info.get('status', '?')
            print(f" {nome:<15} | {barra(bat)} {bat}% | {temp}C    | {st}")
    input("\n[Enter] Voltar...")

def menu_historico(dados):
    print("\n--- [2] HISTÓRICO DE MISSÕES (Endpoint: /api/missoes) ---")
    historico = dados.get("historico", [])
    if not historico:
        print(" (Vazio)")
    else:
        for h in historico:
            print(f" > {h}")
    input("\n[Enter] Voltar...")

def menu_logs(dados):
    print("\n--- [3] LOGS TÉCNICOS (UDP) ---")
    eventos = dados.get("eventos_recentes", [])
    if not eventos:
        print(" (Vazio)")
    else:
        for msg, qtd in eventos:
            short = (msg[:70] + '..') if len(msg) > 70 else msg
            print(f" [{qtd}] {short}")
    input("\n[Enter] Voltar...")

def main():
    print(f"A conectar ao Ground Control via API REST...")
    print(f"Endpoint: {URL_ENDPOINT}")
    time.sleep(1.5)

    while True:
        limpar_ecra()
        print("==========================================")
        print("       GROUND CONTROL - MANUAL            ")
        print("==========================================")

        dados = obter_dados()
        estado_conexao = "\033[92mONLINE\033[0m" if dados else "\033[91mOFFLINE\033[0m"

        print(f"API Nave-Mãe: {estado_conexao}")
        print("------------------------------------------")
        print(" 1. Ver Frota (Telemetria)")
        print(" 2. Ver Histórico de Missões")
        print(" 3. Ver Logs do Sistema")
        print(" 0. Sair")
        print("==========================================")

        op = input("Opção > ")

        if op == '0':
            print("A sair...")
            sys.exit(0)

        if not dados:
            print("Erro: Não foi possível obter dados da API.")
            time.sleep(2)
            continue

        if op == '1': menu_frota(dados)
        elif op == '2': menu_historico(dados)
        elif op == '3': menu_logs(dados)
        else: pass

if __name__ == "__main__":
    main()