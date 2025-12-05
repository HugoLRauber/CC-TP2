import socket
import time
import json
import threading
import sys
import os

# Hack para importar Pacote que está na pasta pai (src)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Pacote
from Pacote import (TIPO_PEDIDO_MISSAO, TIPO_DADOS_MISSAO, TIPO_ACK, TIPO_PROGRESSO, FLAG_MORE_FRAGMENTS)

MAX_PAYLOAD = 255

def enviar_comando_manual(database, target_id, payload_str):
    """ Chamado pela API HTTP para enviar comandos via UDP """
    target_id = int(target_id)
    conf = database.config_rovers.get(target_id)
    addr = (conf["ip"], conf["porta_udp"]) if conf else ("127.0.0.1", 6000 + target_id)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        print(f"[CMD] A enviar para Rover {target_id} {addr}...")
        pct = Pacote.MissionPacket(
            tipo_msg=TIPO_DADOS_MISSAO, 
            num_seq=database.get_novo_id_missao(), 
            payload=payload_str.encode('utf-8')
        )
        s.sendto(pct.pack(), addr)
        return True
    except Exception as e:
        print(f"Erro envio: {e}")
        return False
    finally: s.close()

def processar_pacote(addr, dados, s, db):
    try:
        pct = Pacote.MissionPacket.unpack(dados)
        
        if pct.tipo_msg == TIPO_PROGRESSO:
            msg = pct.payload.decode('utf-8')
            print(f"[UDP] {addr}: {msg}")
            
            # Identificar ID pela porta
            rid = addr[1] - 6000
            if "IDLE" in msg: db.atualizar_estado_rover(rid, "IDLE")
            if "CHARGING" in msg: db.atualizar_estado_rover(rid, "CHARGING")
            
            db.processa_e_insere(addr, pct.num_seq, f"R{rid}: {msg}")
            
            ack = Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pct.num_seq)
            s.sendto(ack.pack(), addr)

    except Exception as e: print(f"Erro UDP: {e}")

def start_udp_service(database):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", 4444))
        print("✅ [UDP] MissionLink Online (Porta 4444)")
        while True:
            d, a = s.recvfrom(4096)
            threading.Thread(target=processar_pacote, args=(a, d, s, database)).start()
    except Exception as e:
        print(f"❌ Falha fatal no UDP: {e}")
    finally: s.close()