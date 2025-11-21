import urllib.request
import json
import time
import os
import sys

# Configuração
IP_NAVE_MAE = "127.0.0.1"
PORTA_API = 8080
URL_API = f"http://{IP_NAVE_MAE}:{PORTA_API}"

def limpar_ecra():
    # Comando para limpar o terminal (Windows ou Linux/Mac)
    os.system('cls' if os.name == 'nt' else 'clear')

def obter_dados():
    """ Faz um pedido HTTP GET à Nave-Mãe para obter o estado. """
    try:
        with urllib.request.urlopen(URL_API, timeout=1) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None

def desenhar_barra(percentagem):
    """ Cria uma barra de progresso visual para a bateria. """
    cheio = int(percentagem / 10)
    vazio = 10 - cheio

    # Cores ANSI para o terminal
    cor = ""
    if percentagem > 60: cor = "\033[92m" # Verde
    elif percentagem > 30: cor = "\033[93m" # Amarelo
    else: cor = "\033[91m" # Vermelho
    reset = "\033[0m"

    barra = f"{cor}[{'#' * cheio}{'-' * vazio}]{reset}"
    return barra

def main():
    print(f"A ligar ao Ground Control em {URL_API}...")
    time.sleep(1)

    while True:
        dados = obter_dados()
        limpar_ecra()

        print("============================================================")
        print("               GROUND CONTROL - DASHBOARD                   ")
        print("============================================================")

        if dados is None:
            print(f"\n\033[91m[ERRO] Sem ligação à Nave-Mãe ({URL_API})\033[0m")
            print("A tentar reconectar...")
        else:
            # 1. Tabela de Rovers (Telemetria TCP)
            telemetria = dados.get("telemetria", {})

            print(f"\n FROTA ATIVA ({len(telemetria)} Rovers):")
            print(f" {'ID / NOME':<20} | {'IP:PORTA':<21} | {'BAT':<15} | {'STATUS':<12}")
            print("-" * 75)

            if not telemetria:
                print(" (Nenhum rover detetado)")

            for nome, info in telemetria.items():
                # O 'nome' aqui é o ID (ex: Rover-Alpha). O IP está dentro do info.
                ip_real = info.get('ip_real', 'N/A')
                bat = info.get('bat', 0)
                status = info.get('status', 'UNK')

                barra_bat = desenhar_barra(bat)

                print(f" {nome:<20} | {ip_real:<21} | {barra_bat} {bat}% | {status}")

            # 2. Histórico de Missões
            historico = dados.get("historico", [])
            print("\n ÚLTIMAS MISSÕES CONCLUÍDAS:")
            print("-" * 75)
            if not historico:
                print(" (Nenhuma)")
            else:
                for h in historico[-5:]: # Mostrar apenas as ultimas 5
                    print(f" > {h}")

            # 3. Logs de Sistema (UDP)
            eventos = dados.get("eventos_recentes", [])
            if eventos:
                print("\n LOGS DE SISTEMA (UDP):")
                print("-" * 75)
                for msg, qtd in eventos:
                    # Cortar mensagem se for muito longa
                    msg_limpa = (msg[:70] + '..') if len(msg) > 70 else msg
                    print(f" [{qtd}] {msg_limpa}")

        print("\n============================================================")
        print(" Pressione CTRL+C para encerrar. Atualizado a cada 1s.")

        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nGround Control encerrado.")
            sys.exit(0)

if __name__ == "__main__":
    main()