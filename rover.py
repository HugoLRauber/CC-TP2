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

def thread_telemetria_tcp(endereco_mae, porta_mae):
    while True:
        try:
            s = socket(AF_INET, SOCK_STREAM)
            s.connect((endereco_mae, porta_mae))
            print(f"[TCP] {NOME_ROVER} ligado à Nave-Mãe.")
            while True:
                t = {"id": NOME_ROVER, "bat": estado_partilhado["bateria"], "pos": estado_partilhado["posicao"], "temp": estado_partilhado["temperatura"], "status": estado_partilhado["status"]}
                s.send((json.dumps(t)+"\n").encode('utf-8'))
                estado_partilhado["temperatura"] = round(20+random.random()*10, 1)
                if estado_partilhado["status"] == "EM_MISSAO": estado_partilhado["posicao"][0]+=1
                time.sleep(1)
        except: time.sleep(5)

def receber_ack(sock, esperado_ack, timeout_s=3.0, tentativas=3, destino=None):
    sock.settimeout(timeout_s)
    for _ in range(tentativas):
        try:
            d, a = sock.recvfrom(1024); pkt = MissionPacket.unpack(d)
            if pkt.tipo_msg == TIPO_ACK and pkt.ack_num == esperado_ack: return True
        except timeout:
            if destino:
                req = {"msg": "RETRY", "bat": estado_partilhado["bateria"], "id": NOME_ROVER}
                sock.sendto(MissionPacket(tipo_msg=TIPO_PEDIDO_MISSAO, num_seq=esperado_ack, payload=json.dumps(req).encode('utf-8')).pack(), destino)
            continue
        except: continue
    return False

# --- RECEÇÃO COM ENVIO DE ACKS ---
def receber_fragmentos_missao_fiavel(sock, destino, timeout_s=5.0):
    sock.settimeout(timeout_s)
    fragmentos = {}
    tamanho_final = None
    id_corrente = None

    while True:
        try:
            dados, addr = sock.recvfrom(2048)
            pkt = MissionPacket.unpack(dados)
        except timeout:
            if tamanho_final is not None:
                return b"".join([fragmentos[i] for i in sorted(fragmentos.keys())]), id_corrente
            return None, None
        except: continue

        if pkt.tipo_msg != TIPO_DADOS_MISSAO: continue

        # ENVIAR ACK IMEDIATAMENTE
        ack = MissionPacket(tipo_msg=TIPO_ACK, ack_num=pkt.num_seq)
        sock.sendto(ack.pack(), destino)

        if id_corrente is None: id_corrente = pkt.num_seq
        elif id_corrente != pkt.num_seq: continue

        fragmentos[pkt.frag_offset] = pkt.payload
        if not pkt.has_more_fragments():
            tamanho_final = pkt.frag_offset + len(pkt.payload)

        if tamanho_final is not None:
            curr = sum(len(v) for v in fragmentos.values())
            if curr >= tamanho_final: break

    return b"".join([fragmentos[i] for i in sorted(fragmentos.keys())]), id_corrente

def enviar_progresso_e_esperar_ack(sock, seq, payload):
    if isinstance(payload, str): payload = payload.encode('utf-8')
    pkt = MissionPacket(tipo_msg=TIPO_PROGRESSO, num_seq=seq, payload=payload)

    for tentativa in range(1, 4): # 3 Tentativas
        try:
            print(f"   (Tentativa {tentativa}) A enviar...")

            # --- SIMULAÇÃO DE PERDA DE PACOTE (30% de chance) ---
            if random.random() > 0.3:
                sock.send(pkt.pack()) # Envia normalmente (70% sucesso)
            else:
                print("   [Simulação] 💥 Ops! O pacote 'perdeu-se' no caminho.")
                # Não envia nada, vai forçar o timeout
            # ----------------------------------------------------

            sock.settimeout(2.0)
            d, _ = sock.recvfrom(1024)
            r = MissionPacket.unpack(d)

            if r.tipo_msg == TIPO_ACK and r.ack_num == seq:
                return True
            if r.tipo_msg == TIPO_DADOS_MISSAO and b'"progresso": 100' in r.payload:
                return True

        except timeout:
            print(f"   [!] Timeout no ACK (Seq {seq}). O protocolo vai retransmitir...")
            continue
        except: continue

    print("   [X] Falha crítica: Desistiu após 3 tentativas.")
    return False

def enviar_foto_fragmentada(sock, seq_base, tamanho_bytes, destino):
    print(f"[{NOME_ROVER}] 📷 Foto ({tamanho_bytes} B)...")
    time.sleep(1)
    dat = os.urandom(tamanho_bytes)
    h = json.dumps({"tipo":"FOTO","origem":NOME_ROVER}).encode('utf-8')
    full = h + b"||END_HEADER||" + dat
    off = 0; id_f = (seq_base+50)%256
    print(f"[{NOME_ROVER}] 📡 A enviar (ID {id_f})...")

    while off < len(full):
        ch = full[off : off+MAX_PAYLOAD]; off_frag = off; off += len(ch)
        fl = FLAG_MORE_FRAGMENTS if off < len(full) else 0
        pkt = MissionPacket(tipo_msg=TIPO_DADOS_MISSAO, num_seq=id_f, flags=fl, frag_offset=off_frag, payload=ch)
        ack_ok = False; tries = 0
        while not ack_ok and tries < 5:
            sock.sendto(pkt.pack(), destino)
            try:
                sock.settimeout(1.0); d, _ = sock.recvfrom(1024); r = MissionPacket.unpack(d)
                if r.tipo_msg == TIPO_ACK and r.ack_num == id_f: ack_ok = True
            except: tries += 1
        if not ack_ok: return
        id_f = (id_f+1)%256
    print(f"[{NOME_ROVER}] ✅ Foto enviada.")

def loop_missao_udp(endereco, porta):
    destino = (endereco, porta)
    s = socket(AF_INET, SOCK_DGRAM)
    try: s.connect(destino)
    except: pass
    seq = 1; estado_partilhado["bateria"] = random.randint(60,100)

    while True:
        print(f"[{NOME_ROVER}] Pedir missão (Bat={estado_partilhado['bateria']}%)...")
        estado_partilhado["status"] = "AGUARDANDO"
        req = {"msg":"QUERO_MISSAO", "bat":estado_partilhado["bateria"], "id":NOME_ROVER}
        s.send(MissionPacket(tipo_msg=TIPO_PEDIDO_MISSAO, num_seq=seq, payload=json.dumps(req).encode('utf-8')).pack())

        if not receber_ack(s, seq, destino=destino):
            print(f"[{NOME_ROVER}] Sem resposta."); time.sleep(2); continue

        # --- CORREÇÃO AQUI ---
        seq = (seq + 1) % 256
        if seq == 0:
            seq = 1
        # ---------------------

        dados, _ = receber_fragmentos_missao_fiavel(s, destino)
        if not dados: continue

        txt = dados.decode('utf-8')
        print(f"[{NOME_ROVER}] Recebido: {txt}")

        if "RECARREGAR" in txt:
            print(f"[{NOME_ROVER}] Recarregar..."); estado_partilhado["status"]="RECARREGANDO"
            time.sleep(1); estado_partilhado["bateria"]=100; time.sleep(2); continue
        if "sem mais" in txt.lower():
            print(f"[{NOME_ROVER}] Fim."); estado_partilhado["status"]="OFFLINE"; break
        if "erro" in txt.lower() or "100%" in txt: time.sleep(2); continue

        foto = False
        try:
            if "foto" in json.loads(txt).get("tarefa","").lower(): foto=True
        except: pass

        estado_partilhado["status"]="EM_MISSAO"
        etapas = ["0%", "25%", "50%", "75%", "100%"]
        for e in etapas:
            estado_partilhado["bateria"] = max(0, estado_partilhado["bateria"]-2)
            if e=="50%" and foto: enviar_foto_fragmentada(s, seq, 1200, destino); estado_partilhado["bateria"]-=5

            p = json.dumps({"id":NOME_ROVER, "p":e, "b":estado_partilhado["bateria"]}).encode('utf-8')
            print(f"[{NOME_ROVER}] {e}")
            if not enviar_progresso_e_esperar_ack(s, seq, p): break

            # --- CORREÇÃO AQUI TAMBÉM ---
            seq = (seq + 1) % 256
            if seq == 0:
                seq = 1
            # ----------------------------

            if estado_partilhado["bateria"]<=0: return
            time.sleep(2)

        print(f"[{NOME_ROVER}] Concluída."); time.sleep(5)
    s.close()

def main():
    global NOME_ROVER
    if len(sys.argv)>=4: a=sys.argv[1]; p=int(sys.argv[2]); NOME_ROVER=sys.argv[3]
    elif len(sys.argv)==2: a="127.0.0.1"; p=4444; NOME_ROVER=sys.argv[1]
    else: a="127.0.0.1"; p=4444; NOME_ROVER="Rover-Padrao"
    t = Thread(target=thread_telemetria_tcp, args=(a, 5555)); t.daemon=True; t.start()
    loop_missao_udp(a, p)

if __name__=="__main__": main()