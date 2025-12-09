from socket import *
import sys
import time
import json
import threading
import random
import os

# Caminho para importar Pacote
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Pacote
from Pacote import (TIPO_DADOS_MISSAO, TIPO_ACK, TIPO_PROGRESSO, FLAG_MORE_FRAGMENTS)

IP_NAVE = "10.0.0.10"
PORTA_UDP_NAVE = 4444
PORTA_TCP_NAVE = 6000
MAX_PAYLOAD = 250

ROVER_NAMES = {
    1: "Rover-Alpha",
    2: "Rover-Beta",
    3: "Rover-Gamma"
}

class RoverAutonomo:
    def __init__(self, rover_id, ip_nave_custom=None):
        self.id = int(rover_id)
        self.nome = ROVER_NAMES.get(self.id, f"Rover-{self.id}")
        self.porta_local = 6000 + self.id
        self.ip_nave = ip_nave_custom if ip_nave_custom else IP_NAVE
        self.endereco_nave = (self.ip_nave, PORTA_UDP_NAVE)

        self.bateria = 100
        self.status = "DESCONECTADO" 
        self.posicao = [random.randint(20, 400), random.randint(20, 400), 0]

        self.seq = 100
        self.last_rx_seq = -1 
        
        self.sock = socket(AF_INET, SOCK_DGRAM)
        try: self.sock.bind(("0.0.0.0", self.porta_local))
        except: pass

        self.ack_events = {}
        self.lock = threading.Lock()

        print(f"[{self.nome}] ONLINE | Pos: {self.posicao}")

    # --- SISTEMA DE ACKS ---
    def esperar_ack(self, seq, timeout=3.0):
        evt = threading.Event()
        with self.lock:
            self.ack_events[seq] = evt
        recebeu = evt.wait(timeout)
        with self.lock:
            if seq in self.ack_events:
                del self.ack_events[seq]
        return recebeu

    def notificar_ack(self, seq_recebido):
        with self.lock:
            if seq_recebido in self.ack_events:
                self.ack_events[seq_recebido].set()

    def enviar_pacote_seguro(self, pct, verbose=True):
        pacote_bytes = pct.pack()
        
        while True:
            tentativas = 5
            for t in range(tentativas):
                self.sock.sendto(pacote_bytes, self.endereco_nave)

                if self.esperar_ack(pct.num_seq, timeout=3.0):
                    if verbose: 
                        print(f"[{self.nome}] [ACK-RX] Sucesso! Nave confirmou Seq {pct.num_seq}.")
                    return True

                if verbose: 
                    print(f"[{self.nome}] [TIMEOUT] Sem ACK para Seq {pct.num_seq}. Retransmitindo ({t+1}/{tentativas})...")

            print(f"[{self.nome}] [REDE EM BAIXO] Falha apos 5 tentativas. A aguardar 5s...")
            time.sleep(5)
            print(f"[{self.nome}] A retomar envio persistente do Seq {pct.num_seq}...")

    def enviar_foto(self, missao_id):
        tamanho_total = random.randint(500, 1000)
        dados_foto = os.urandom(tamanho_total)

        print(f"\n[{self.nome}] [FOTO] A enviar dados binarios da Missao {missao_id}...")
        offset = 0
        while offset < tamanho_total:
            chunk = dados_foto[offset : offset + MAX_PAYLOAD]
            self.seq = (self.seq + 1) % 255
            prox_offset = offset + len(chunk)
            flags = FLAG_MORE_FRAGMENTS if prox_offset < tamanho_total else 0
            
            flag_val = 1 if flags else 0
            flag_str = f"MORE_FRAGS ({flag_val})"

            cabecalho = f"FOTO:{missao_id}:".encode('utf-8')
            payload = cabecalho + chunk

            pct = Pacote.MissionPacket(
                tipo_msg=TIPO_DADOS_MISSAO,
                num_seq=self.seq,
                flags=flags,
                frag_offset=offset,
                payload=payload
            )

            print(f"[{self.nome}] [FRAG] Envio Seq {self.seq} | Offset {offset} | {flag_str}")
            self.enviar_pacote_seguro(pct, verbose=True)

            offset = prox_offset
            time.sleep(0.2)
        print(f"[{self.nome}] [FIM] Foto enviada com sucesso.\n")

    def loop_bateria(self):
        while True:
            time.sleep(2)
            if self.status == "DESCONECTADO":
                continue

            if self.status == "CHARGING":
                self.bateria = min(100, self.bateria + 1)
                if self.bateria >= 100: 
                    self.status = "IDLE"
                    self.avisar_udp("STATUS: IDLE")
            else:
                gasto = 2 if self.status == "EM_MISSAO" else 0
                self.bateria = max(0, min(100, self.bateria - gasto))
                if self.bateria <= 15: 
                    self.avisar_udp("STATUS: CHARGING")
                    self.status = "CHARGING"

    def loop_telemetria(self):
        while True:
            try:
                s = socket(AF_INET, SOCK_STREAM)
                s.settimeout(None)
                s.connect((self.ip_nave, PORTA_TCP_NAVE))
                while True:
                    d = { "id": self.id, "bat": self.bateria, "pos": self.posicao, "status": self.status }
                    msg = json.dumps(d) + "\n"
                    s.sendall(msg.encode('utf-8'))
                    time.sleep(10)
            except Exception: pass
            finally: s.close()
            time.sleep(5)

    def avisar_udp(self, msg, seguro=True):
        self.seq = (self.seq + 1) % 255
        payload = f"[{self.nome}] {msg}".encode('utf-8')
        pct = Pacote.MissionPacket(TIPO_PROGRESSO, self.seq, payload=payload)

        e_progresso = "PROGRESS" in msg
        if not e_progresso:
            print(f"[{self.nome}] [ENVIO] '{msg}' (Seq {self.seq}) -> A aguardar ACK...")
        
        self.enviar_pacote_seguro(pct, verbose=(not e_progresso))

    def executar(self, missao):
        if self.status == "DESCONECTADO": return

        tarefa = missao.get("tarefa", "?")
        duracao = int(missao.get("duracao", 15))
        mid = missao.get("id", "M-???")

        self.status = "EM_MISSAO"
        self.avisar_udp(f"STARTED: {tarefa}")

        INTERVALO = 2
        passos = int(duracao / INTERVALO)
        if passos < 1: passos = 1
        perc_passo = 100 / passos
        progresso = 0.0

        for i in range(passos):
            if self.status != "EM_MISSAO": break
            time.sleep(INTERVALO)

            progresso += perc_passo
            if progresso > 100: progresso = 100

            self.posicao[0] += random.randint(-8, 8)
            self.posicao[1] += random.randint(-8, 8)

            msg_progresso = f"PROGRESS: {int(progresso)} POS:{self.posicao[0]},{self.posicao[1]}"
            self.avisar_udp(msg_progresso)

            if "fotografia" in tarefa.lower() and i == int(passos/2):
                self.enviar_foto(mid)

        if self.status == "EM_MISSAO":
            self.status = "IDLE"
            time.sleep(0.5)
            self.avisar_udp(f"COMPLETED: {tarefa}")

    def loop_escuta(self):
        print(f"[{self.nome}] A escuta (UDP)...")
        while True:
            try:
                d, a = self.sock.recvfrom(4096)
                pct = Pacote.MissionPacket.unpack(d)

                if pct.tipo_msg == TIPO_ACK:
                    self.notificar_ack(pct.ack_num)
                    continue

                ack = Pacote.MissionPacket(TIPO_ACK, ack_num=pct.num_seq)
                self.sock.sendto(ack.pack(), self.endereco_nave)

                # --- CORREÇÃO: Deteção de Duplicados e Fora de Ordem ---
                # Se o pacote for antigo (<=), ignoramos.
                if pct.num_seq <= self.last_rx_seq:
                    # Opcional: print para debug
                    # print(f"[{self.nome}] [UDP] Pacote antigo/duplicado descartado (Seq {pct.num_seq})")
                    continue
                self.last_rx_seq = pct.num_seq

                if pct.tipo_msg == TIPO_DADOS_MISSAO:
                    txt = pct.payload.decode('utf-8', errors='ignore')
                    
                    if "CMD:CHARGE" in txt:
                        # --- CORREÇÃO: Só carrega se não estiver cheio ---
                        if self.bateria >= 100:
                            print(f"[{self.nome}] Comando Carga ignorado (Bateria Cheia)")
                            # Força atualização de estado para IDLE na nave se houver desincronização
                            self.avisar_udp("STATUS: IDLE")
                        else:
                            self.status = "CHARGING"
                            self.avisar_udp("STATUS: CHARGING")
                            print(f"[{self.nome}] A Carregar...")
                            
                    elif "{" in txt:
                        if self.status == "IDLE":
                            m = json.loads(txt)
                            print(f"[{self.nome}] Missao Recebida: {m.get('tarefa')} [ID: {m.get('id')}]")
                            threading.Thread(target=self.executar, args=(m,)).start()
                        else:
                            self.avisar_udp(f"RECUSADO: Rover {self.status}")
            except: pass

    def run(self):
        threading.Thread(target=self.loop_bateria, daemon=True).start()
        threading.Thread(target=self.loop_telemetria, daemon=True).start()
        threading.Thread(target=self.loop_escuta, daemon=True).start()
        
        print(f"[{self.nome}] A tentar estabelecer conexao com a Nave...")
        self.avisar_udp("STATUS: DESCONECTADO")
        
        print(f"[{self.nome}] Conexao Estabelecida!")
        self.status = "IDLE"
        self.avisar_udp("STATUS: IDLE")
        
        while True:
            time.sleep(1)

if __name__ == "__main__":
    rid = sys.argv[1] if len(sys.argv) > 1 else "1"
    ip = sys.argv[2] if len(sys.argv) > 2 else None
    RoverAutonomo(rid, ip).run()
