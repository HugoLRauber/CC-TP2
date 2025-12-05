from socket import *
from threading import *
from database import Database
import Pacote
import json
from HTTP import arranca_api_http 
from Pacote import (TIPO_PEDIDO_MISSAO, TIPO_DADOS_MISSAO, TIPO_ACK, TIPO_PROGRESSO, FLAG_MORE_FRAGMENTS)

MAX_PAYLOAD = 255

# --- SERVIÇO UDP (MissionLink) ---
def servico_udp(addr, dados, s, db):
    try:
        pct = Pacote.MissionPacket.unpack(dados)
        ack = Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pct.num_seq)
        s.sendto(ack.pack(), addr) # ACK Imediato

        # 1. PEDIDO DE MISSÃO
        if pct.tipo_msg == TIPO_PEDIDO_MISSAO:
            try:
                payload = json.loads(pct.payload.decode('utf-8'))
                # O payload do rover traz {"id": "Rover-Alpha", ...}
                nome_rover = str(payload.get("id", f"Rover-{addr[1]}"))
                # Resolve para nome bonito se for numero
                nome_rover = db.resolver_nome_rover(nome_rover)
                
                print(f"[UDP] 📩 Pedido de Missão de {nome_rover}")
                db.processa_e_insere(addr, pct.num_seq, f"Pedido de {nome_rover}")

                # Verificar se é novo
                if True: # Simplificação: processa sempre, o DB gere o histórico
                    proxima = db.get_proxima_missao(nome_rover)
                    
                    if proxima:
                        print(f"  -> Atribuindo {proxima['id']} a {nome_rover}")
                        msg_bytes = json.dumps(proxima).encode('utf-8')
                        id_m = db.get_novo_id_missao()
                        
                        # Enviar Fragmentado
                        offset = 0
                        while offset < len(msg_bytes):
                            chunk = msg_bytes[offset : offset + MAX_PAYLOAD]
                            local_off = offset
                            offset += len(chunk)
                            flags = FLAG_MORE_FRAGMENTS if offset < len(msg_bytes) else 0
                            
                            p = Pacote.MissionPacket(
                                tipo_msg=TIPO_DADOS_MISSAO, num_seq=id_m,
                                flags=flags, frag_offset=local_off, payload=chunk
                            )
                            s.sendto(p.pack(), addr)
                            time.sleep(0.02)
                    else:
                        print(f"  -> {nome_rover} já fez tudo!")
                        # Opcional: Enviar msg "SEM_MISSOES"
            
            except Exception as e: print(f"Erro Pedido: {e}")

        # 2. PROGRESSO
        elif pct.tipo_msg == TIPO_PROGRESSO:
            txt = pct.payload.decode('utf-8')
            # Formato esperado: "[Nome] Msg" ou JSON
            print(f"[UDP] 📢 {txt}")
            
            # Se for conclusão, registar na BD
            if "COMPLETED:" in txt:
                try:
                    # Ex: "[Rover-Alpha] COMPLETED: Coleta"
                    partes = txt.split("] ")
                    nome = partes[0].replace("[","")
                    tarefa = partes[1].split(": ")[1]
                    db.registar_conclusao(nome, tarefa)
                except: pass

    except Exception as e: print(f"Erro UDP: {e}")

def loop_udp(db):
    s = socket(AF_INET, SOCK_DGRAM)
    try: s.bind(("0.0.0.0", 4444)); print("✅ UDP 4444 Online")
    except: return
    while True:
        d, a = s.recvfrom(4096)
        Thread(target=servico_udp, args=(a, d, s, db)).start()

# --- SERVIÇO TCP (Telemetria) ---
def trata_tcp(conn, addr, db):
    try:
        d = conn.recv(4096).decode('utf-8')
        if d:
            js = json.loads(d)
            # Normalizar ID (se vier 1, converte para Rover-Alpha)
            if "id" in js:
                js["nome"] = db.resolver_nome_rover(js["id"])
            
            js["ip"] = addr # Guardar IP real
            db.atualizar_telemetria(js.get("nome", "Unknown"), js)
            # print(f"📊 TCP: {js.get('nome')} Bat:{js.get('bat')}%")
    except: pass
    finally: conn.close()

def loop_tcp(db):
    s = socket(AF_INET, SOCK_STREAM)
    try: s.bind(("0.0.0.0", 6000)); s.listen(5); print("✅ TCP 6000 Online")
    except: return
    while True:
        c, a = s.accept()
        Thread(target=trata_tcp, args=(c, a, db)).start()

# --- COMANDO MANUAL VIA API ---
def handler_api(dados):
    # dados = {acao, target_id (Ex: 1), missao}
    db = dados["_db_ref"]
    tid = int(dados.get("target_id"))
    
    # Descobrir IP do Rover
    # 1. Config Estática
    conf = db.config_rovers.get(tid)
    addr = None
    if conf: addr = (conf["ip"], conf["porta_udp"])
    # 2. Se for localhost (teste)
    if not addr: addr = ("127.0.0.1", 6000 + tid)

    s = socket(AF_INET, SOCK_DGRAM)
    try:
        payload = ""
        if dados["acao"] == "CHARGE": payload = "CMD:CHARGE"
        elif dados["acao"] == "MISSAO": payload = json.dumps(dados["missao"])
        
        print(f"[CMD] A enviar para Rover {tid} ({addr})...")
        pct = Pacote.MissionPacket(
            tipo_msg=TIPO_DADOS_MISSAO, 
            num_seq=db.get_novo_id_missao(), 
            payload=payload.encode('utf-8')
        )
        s.sendto(pct.pack(), addr)
        return True
    except: return False
    finally: s.close()

def main():
    db = Database()
    db.carregar_dados() # Carrega JSONs
    
    Thread(target=loop_udp, args=(db,), daemon=True).start()
    Thread(target=loop_tcp, args=(db,), daemon=True).start()
    
    # API
    rovers_api = {rid: (c["ip"], c["porta_udp"]) for rid, c in db.config_rovers.items()}
    arranca_api_http(db, rovers_api, handler_api)

if __name__ == "__main__":
    main()