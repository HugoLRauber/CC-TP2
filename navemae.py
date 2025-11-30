from socket import *
from threading import *
from database import Database
import Pacote
import json
from HTTP import arranca_api_http 
from Pacote import (TIPO_DADOS_MISSAO, TIPO_ACK, TIPO_PROGRESSO)

MAX_PAYLOAD = 255

def enviar_comando_udp(db, target_id, payload_str):
    # Usa a config para saber onde mandar
    target_id = int(target_id)
    conf = db.config_rovers.get(target_id)
    
    if conf:
        addr = (conf["ip"], conf["porta_udp"])
    else:
        # Fallback para localhost
        addr = ("127.0.0.1", 6000 + target_id)

    s = socket(AF_INET, SOCK_DGRAM)
    try:
        print(f"[CMD] A enviar '{payload_str}' para Rover {target_id} {addr}...")
        pct = Pacote.MissionPacket(
            tipo_msg=TIPO_DADOS_MISSAO, 
            num_seq=db.get_novo_id_missao(), 
            payload=payload_str.encode('utf-8')
        )
        s.sendto(pct.pack(), addr)
        return True
    except Exception as e:
        print(f"Erro envio: {e}")
        return False
    finally: s.close()

def handler_api_post(dados):
    db = dados["_db_ref"] 
    tid = int(dados.get("target_id"))
    acao = dados.get("acao")

    if acao == "CHARGE":
        return enviar_comando_udp(db, tid, "CMD:CHARGE")
    elif acao == "MISSAO":
        missao = dados.get("missao")
        return enviar_comando_udp(db, tid, json.dumps(missao))
    return False

def servico_udp(addr, dados, s, db):
    try:
        pct = Pacote.MissionPacket.unpack(dados)
        
        if pct.tipo_msg == TIPO_PROGRESSO:
            msg = pct.payload.decode('utf-8')
            print(f"[UDP] {addr}: {msg}")
            
            # Tentar adivinhar ID pela porta (se for localhost)
            # ou confiar na telemetria TCP já registada
            rid = addr[1] - 6000
            
            if "IDLE" in msg: db.atualizar_estado_rover(rid, "IDLE")
            if "CHARGING" in msg: db.atualizar_estado_rover(rid, "CHARGING")
            
            db.processa_e_insere(addr, pct.num_seq, f"R{rid}: {msg}")
            
            ack = Pacote.MissionPacket(type_msg=TIPO_ACK, ack_num=pct.num_seq)
            s.sendto(ack.pack(), addr)
    except: pass

def loop_udp(db):
    s = socket(AF_INET, SOCK_DGRAM)
    s.bind(("0.0.0.0", 4444))
    print("✅ UDP 4444 Online")
    while True:
        d, a = s.recvfrom(4096)
        Thread(target=servico_udp, args=(a, d, s, db)).start()

def loop_tcp(db):
    s = socket(AF_INET, SOCK_STREAM)
    s.bind(("0.0.0.0", 6000))
    s.listen(5)
    print("✅ TCP 6000 Online")
    while True:
        c, a = s.accept()
        def trata(conn, addr):
            try:
                d = conn.recv(1024).decode('utf-8')
                js = json.loads(d)
                # JSON vem com "id": 1 (int)
                rid = js.get("id") 
                if rid: 
                    js["ip_real"] = f"{addr[0]}:{addr[1]}"
                    db.atualizar_telemetria(rid, js)
                    print(f"📊 [TEL] Rover {rid}: {js.get('bat')}%")
            except: pass
            finally: conn.close()
        Thread(target=trata, args=(c, a)).start()

def main():
    db = Database()
    db.carregar_missoes_do_ficheiro("missoes.json")
    db.carregar_config() # IMPORTANTE: Carrega rovers_config.json
    
    Thread(target=loop_udp, args=(db,), daemon=True).start()
    Thread(target=loop_tcp, args=(db,), daemon=True).start()
    
    # Prepara lista para API
    lista_rovers = {}
    for rid, conf in db.config_rovers.items():
        lista_rovers[rid] = (conf["ip"], conf["porta_udp"])

    arranca_api_http(db, lista_rovers, handler_api_post)

if __name__ == "__main__":
    main()