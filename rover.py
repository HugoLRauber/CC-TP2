from socket import *
import sys
import time
import os
import json
import random
from threading import Thread
from Pacote import *

MAX_PAYLOAD = 255
estado_partilhado = {"bateria": 100, "posicao": [0, 0], "temperatura": 25.0, "status": "AGUARDANDO"}
NOME_ROVER = "Rover-Genérico"

# --- THREAD TCP (TELEMETRIA EM BACKGROUND) ---
def thread_tcp(addr, port):
    while True:
        try:
            s = socket(AF_INET, SOCK_STREAM); s.connect((addr, port))
            # print(f"[TCP] Ligado.") # Comentado para não poluir o menu
            while True:
                t = {"id": NOME_ROVER, "bat": estado_partilhado["bateria"], "pos": estado_partilhado["posicao"], "temp": estado_partilhado["temperatura"], "status": estado_partilhado["status"]}
                s.send((json.dumps(t)+"\n").encode('utf-8'))
                estado_partilhado["temperatura"] = round(20+random.random()*10, 1)
                if estado_partilhado["status"] == "EM_MISSAO": estado_partilhado["posicao"][0]+=1
                time.sleep(1)
        except: time.sleep(5)

# --- Tentativas ---
def receber_ack(sock, seq, timeout_s=5.0, tries=3, dest=None):
    sock.settimeout(timeout_s)
    for i in range(tries):
        try:
            d, a = sock.recvfrom(1024); p = MissionPacket.unpack(d)
            if p.tipo_msg == TIPO_ACK and p.ack_num == seq: return True
        except timeout:
            if dest:
                req = {"msg": "RETRY", "bat": estado_partilhado["bateria"], "id": NOME_ROVER}
                sock.sendto(MissionPacket(tipo_msg=TIPO_PEDIDO_MISSAO, num_seq=seq, payload=json.dumps(req).encode('utf-8')).pack(), dest)
            continue
        except: continue
    return False

def receber_missao_fiavel(sock, dest, timeout_s=5.0):
    sock.settimeout(timeout_s); frags = {}; final_sz = None; curr_id = None
    while True:
        try: d, a = sock.recvfrom(2048); p = MissionPacket.unpack(d)
        except:
            if final_sz: return b"".join([frags[i] for i in sorted(frags.keys())]), curr_id
            return None, None
        if p.tipo_msg != TIPO_DADOS_MISSAO: continue
        sock.sendto(MissionPacket(tipo_msg=TIPO_ACK, ack_num=p.num_seq).pack(), a)
        if curr_id is None: curr_id = p.num_seq
        elif curr_id != p.num_seq: continue
        frags[p.frag_offset] = p.payload
        if not p.has_more_fragments(): final_sz = p.frag_offset + len(p.payload)
        if final_sz and sum(len(v) for v in frags.values()) >= final_sz: break
    return b"".join([frags[i] for i in sorted(frags.keys())]), curr_id

def enviar_progresso_fiavel(sock, seq, pay):
    if isinstance(pay, str): pay = pay.encode('utf-8')
    pkt = MissionPacket(tipo_msg=TIPO_PROGRESSO, num_seq=seq, payload=pay)
    for i in range(3):
        try:
            sock.send(pkt.pack()); sock.settimeout(2.0); d, _ = sock.recvfrom(1024); r = MissionPacket.unpack(d)
            if r.tipo_msg == TIPO_ACK and r.ack_num == seq: return True
            if r.tipo_msg == TIPO_DADOS_MISSAO and b'"progresso": 100' in r.payload: return True
        except: continue
    return False

def enviar_foto(sock, seq_base, size, dest):
    print(f"[{NOME_ROVER}]  Foto ({size} B)..."); time.sleep(1)
    dat = os.urandom(size); h = json.dumps({"tipo":"FOTO","origem":NOME_ROVER}).encode('utf-8')
    full = h + b"||END_HEADER||" + dat
    off = 0; id_f = (seq_base+50)%256
    print(f"[{NOME_ROVER}]  A enviar foto...")
    while off < len(full):
        ch = full[off : off+MAX_PAYLOAD]; off_frag = off; off += len(ch)
        fl = FLAG_MORE_FRAGMENTS if off < len(full) else 0
        pkt = MissionPacket(tipo_msg=TIPO_DADOS_MISSAO, num_seq=id_f, flags=fl, frag_offset=off_frag, payload=ch)
        ok = False; tr = 0
        while not ok and tr < 5:
            sock.sendto(pkt.pack(), dest)
            try: sock.settimeout(1.0); d, _ = sock.recvfrom(1024); r = MissionPacket.unpack(d);
            except: tr += 1; continue
            if r.tipo_msg == TIPO_ACK and r.ack_num == id_f: ok = True
        if not ok: return
        id_f = (id_f+1)%256
    print(f"[{NOME_ROVER}]  Foto enviada.")

# --- LOOP PRINCIPAL MANUAL ---
def loop_manual(addr, port):
    dest = (addr, port)
    s = socket(AF_INET, SOCK_DGRAM)
    try: s.connect(dest)
    except: pass

    seq = 1
    estado_partilhado["bateria"] = random.randint(60, 100)

    print(f"\n=== {NOME_ROVER} ONLINE ===")
    print("Modo: Manual Interativo")

    while True:
        # MENU
        estado_partilhado["status"] = "AGUARDANDO"
        print(f"\n[{NOME_ROVER}] Bat: {estado_partilhado['bateria']}%")
        opt = input("Comandos: [ENTER] Pedir Missão | [r] Recarregar | [q] Sair > ")

        if opt.lower() == 'q':
            print("Desligando..."); break

        elif opt.lower() == 'r':
            print("A recarregar...")
            while estado_partilhado["bateria"] < 95:
                estado_partilhado["bateria"] += 5
                print(f"Bat: {estado_partilhado['bateria']}%")
                time.sleep(0.5)
            if estado_partilhado["bateria"] < 100:
                estado_partilhado["bateria"] = 100
                print(f"Bat: {estado_partilhado['bateria']}%")
                time.sleep(0.5)
            
            continue

        # PEDIR MISSÃO
        print(f"[{NOME_ROVER}] A contactar Nave-Mãe...")
        req = {"msg":"QUERO_MISSAO", "bat":estado_partilhado["bateria"], "id":NOME_ROVER}
        s.send(MissionPacket(tipo_msg=TIPO_PEDIDO_MISSAO, num_seq=seq, payload=json.dumps(req).encode('utf-8')).pack())

        if not receber_ack(s, seq, dest=dest):
            print(f"[{NOME_ROVER}]  Sem resposta da Nave-Mãe."); continue

        seq=(seq+1)%256
        if seq==0: seq=1

        dados, _ = receber_missao_fiavel(s, dest)
        if not dados:
            print(" Erro na receção."); continue

        txt = dados.decode('utf-8')
        print(f"[{NOME_ROVER}]  Recebido: {txt}")

        if "RECARREGAR" in txt:
            print(f" ORDEM: Bateria insuficiente para esta missão.")
            continue

        if "sem mais" in txt.lower():
            print(f" Nave-Mãe diz: Sem missões disponíveis.")
            continue

        if "erro" in txt.lower(): continue

        # EXECUÇÃO DA MISSÃO
        foto = False
        try:
            if "foto" in json.loads(txt).get("tarefa","").lower(): foto=True
        except: pass

        estado_partilhado["status"]="EM_MISSAO"
        print(f" A executar missão...")
        for e in ["0%","25%","50%","75%","100%"]:
            estado_partilhado["bateria"] = max(0, estado_partilhado["bateria"]-3)
            if e=="50%" and foto:
                enviar_foto(s, seq, 1200, dest)
                estado_partilhado["bateria"]-=5

            p = json.dumps({"id":NOME_ROVER, "p":e, "b":estado_partilhado["bateria"]}).encode('utf-8')
            print(f"   Progresso: {e}")
            if not enviar_progresso_fiavel(s, seq, p): break

            seq=(seq+1)%256
            if seq==0: seq=1
            if estado_partilhado["bateria"]<=0:
                print(" BATERIA ZERO."); break
            time.sleep(1.5)

        print(f" Missão terminada.")

    s.close()

def main():
    global NOME_ROVER
    # Lê argumentos: python rover.py [IP] [PORTA] [NOME]
    # Ou apenas: python rover.py [NOME]
    if len(sys.argv) >= 4:
        a=sys.argv[1]; p=int(sys.argv[2]); NOME_ROVER=sys.argv[3]
    elif len(sys.argv) == 2:
        a="127.0.0.1"; p=4444; NOME_ROVER=sys.argv[1]
    else:
        a="127.0.0.1"; p=4444; NOME_ROVER="Rover-Padrao"

    Thread(target=thread_tcp, args=(a, 5555), daemon=True).start()
    loop_manual(a, p)

if __name__=="__main__": main()