import threading
import time
import sys
import os

# Garante que os módulos da pasta src são resolvidos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database import Database
    # Importa serviços de rede (UDP envia/recebe comandos)
    from services.udp import start_udp_service, enviar_comando_manual
    from services.tcp import start_tcp_service
    from HTTP import arranca_api_http # Mantemos o HTTP.py pois é o que tens
except ImportError as e:
    print(f" ERRO CRÍTICO DE IMPORTAÇÃO: {e}")
    sys.exit(1)

import json

# Callback da API para envio de comandos/missões
def handler_api(dados):
    """Recebe dados do HTTP e envia ordem via UDP para o rover alvo."""
    db = dados.get("_db_ref")
    tid = int(dados.get("target_id"))
    
    payload = ""
    if dados["acao"] == "CHARGE": payload = "CMD:CHARGE"
    elif dados["acao"] == "MISSAO": payload = json.dumps(dados["missao"])
    
    print(f"[API] A pedir envio UDP para Rover {tid}...")
    
    # Usa a função avançada do services/udp.py
    return enviar_comando_manual(db, tid, payload)

def main():
    print("========================================")
    print("         NAVE-MÃE SERVER (CORE)")
    print("========================================")

    # 1. Iniciar Base de Dados
    db = Database()
    db.carregar_dados() 

    print(">>> A iniciar serviços de rede...")
    
    # 2. Lançar serviços (udp/tcp/http)
    
    # UDP: Porta 4444 (canal de missões)
    t_udp = threading.Thread(target=start_udp_service, args=(db,), daemon=True)
    
    # TCP: Porta 6000 (telemetria contínua)
    t_tcp = threading.Thread(target=start_tcp_service, args=(db,), daemon=True)
    
    # HTTP API: Porta 8080 (controlo e visualização)
    rovers_api = {rid: (c["ip"], c["porta_udp"]) for rid, c in db.config_rovers.items()}
    t_api = threading.Thread(target=arranca_api_http, args=(db, rovers_api, handler_api, 8080), daemon=True)

    t_udp.start()
    t_tcp.start()
    t_api.start()

    print(" SISTEMA ONLINE.")
    print("   - UDP MissionLink: Porta 4444")
    print("   - TCP Telemetry:   Porta 6000")
    print("   - HTTP API:        Porta 8080")
    print("\n[A aguardar conexões... Pressione CTRL+C para sair]\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n A encerrar Nave-Mãe...")
        sys.exit(0)

if __name__ == "__main__":
    main()
