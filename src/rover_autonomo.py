from socket import *
import sys
import time
import json
import threading
import random
import Pacote 
from Pacote import (TIPO_PEDIDO_MISSAO, TIPO_DADOS_MISSAO, TIPO_ACK, TIPO_PROGRESSO, FLAG_MORE_FRAGMENTS)

IP_NAVE = "127.0.0.1"
PORTA_UDP_NAVE = 4444
PORTA_TCP_NAVE = 6000

class RoverAutonomo:
    def __init__(self, rover_id):
        self.id = int(rover_id)
        # Tenta carregar nome do config ou usa default
        self.nome = f"Rover-{self.id}" 
        
        self.porta_local = 6000 + self.id 
        self.endereco_nave = (IP_NAVE, PORTA_UDP_NAVE)
        
        self.bateria = 100
        self.status = "IDLE"
        
        # Posição 3D: X, Y, Z
        self.posicao = [
            random.randint(0, 5000), 
            random.randint(0, 5000), 
            random.randint(0, 100) # Altitude inicial
        ]
        
        self.seq = 100
        self.sock = socket(AF_INET, SOCK_DGRAM)
        try: self.sock.bind(("0.0.0.0", self.porta_local))
        except: sys.exit(1)
        
        print(f"🤖 {self.nome} ONLINE | Pos: {self.posicao}")

    def log(self, t): print(f"[{time.strftime('%H:%M:%S')}] {t}")

    # --- BATERIA ---
    def loop_bateria(self):
        while True:
            time.sleep(10) # Tick de 10s
            if self.status == "CHARGING":
                if self.bateria < 100: self.bateria = min(100, self.bateria + 10) 
                else: 
                    self.status = "IDLE"
                    self.avisar_udp("STATUS: IDLE (Carregado)")
            elif self.status == "EM_MISSAO":
                self.bateria = max(0, self.bateria - 2) 
            else:
                # IDLE: Carrega 1% a cada 10s (Painel Solar)
                if self.bateria < 100: self.bateria += 1 

            if self.bateria <= 10 and self.status != "CHARGING":
                self.log("⚠️ BAT < 10%. AUTO-CARGA.")
                self.status = "CHARGING"
                self.avisar_udp("STATUS: CHARGING")

    # --- TELEMETRIA TCP ---
    def loop_telemetria(self):
        while True:
            try:
                s = socket(AF_INET, SOCK_STREAM); s.settimeout(2)
                s.connect((IP_NAVE, PORTA_TCP_NAVE))
                d = {
                    "id": self.id, 
                    "nome": self.nome,
                    "bat": self.bateria, 
                    "pos": self.posicao, 
                    "status": self.status
                }
                s.sendall(json.dumps(d).encode('utf-8')); s.close()
            except: pass
            time.sleep(5)

    def avisar_udp(self, msg):
        self.seq += 1
        payload = f"[{self.nome}] {msg}".encode('utf-8')
        p = Pacote.MissionPacket(TIPO_PROGRESSO, self.seq, payload=payload)
        try: self.sock.sendto(p.pack(), self.endereco_nave)
        except: pass

    # --- EXECUÇÃO (SEM PEDIR NOVA MISSÃO NO FIM) ---
    def executar(self, missao):
        tarefa = missao.get("tarefa", "?")
        dur = int(missao.get("duracao", 10))
        
        # Verificar bateria
        custo = dur / 2
        if self.bateria < custo + 5:
            self.log(f"❌ Missão recusada: Bat fraca.")
            self.avisar_udp("RECUSADO: Bateria")
            return

        self.status = "EM_MISSAO"
        self.log(f"🚀 A Executar: {tarefa}")
        self.avisar_udp(f"STARTED: {tarefa}")
        
        for i in range(dur):
            if self.status != "EM_MISSAO": break
            time.sleep(1)
            # Simular Movimento 3D
            self.posicao[0] += random.randint(-5, 5)
            self.posicao[1] += random.randint(-5, 5)
            self.posicao[2] += random.randint(-1, 2) 
            if self.posicao[2] < 0: self.posicao[2] = 0

        if self.status == "EM_MISSAO":
            self.status = "IDLE"
            self.log("🏁 Missão Feita.")
            self.avisar_udp(f"COMPLETED: {tarefa}")
            # [REMOVIDO] self.pedir_missao() -> Agora ele fica quieto!

    def run(self):
        threading.Thread(target=self.loop_bateria, daemon=True).start()
        threading.Thread(target=self.loop_telemetria, daemon=True).start()
        
        self.avisar_udp("STATUS: IDLE")
        # [REMOVIDO] self.pedir_missao() -> Não pede nada ao iniciar
        
        print("✅ Rover Autónomo Ativo (Modo Passivo).")
        while True:
            try:
                d, a = self.sock.recvfrom(4096)
                pct = Pacote.MissionPacket.unpack(d)
                ack = Pacote.MissionPacket(TIPO_ACK, ack_num=pct.num_seq)
                self.sock.sendto(ack.pack(), a)

                if pct.tipo_msg == TIPO_DADOS_MISSAO:
                    txt = pct.payload.decode('utf-8')
                    if "CMD:CHARGE" in txt:
                        self.status = "CHARGING"; self.log("🔌 A Carregar (Comando)")
                    elif "{" in txt:
                        try:
                            m = json.loads(txt)
                            threading.Thread(target=self.executar, args=(m,)).start()
                        except: pass
            except: pass

if __name__ == "__main__":
    rid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    RoverAutonomo(rid).run()