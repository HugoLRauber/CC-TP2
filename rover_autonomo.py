from socket import *
import sys
import time
import json
import threading
import Pacote 

from Pacote import (
    TIPO_PEDIDO_MISSAO, TIPO_DADOS_MISSAO, TIPO_ACK, 
    TIPO_PROGRESSO, FLAG_MORE_FRAGMENTS
)

IP_NAVE = "127.0.0.1"
PORTA_UDP_NAVE = 4444
PORTA_TCP_NAVE = 6000

class RoverAutonomo:
    def __init__(self, rover_id):
        self.id = rover_id
        # Porta local = 6000 + ID (Ex: Rover 1 = 6001)
        self.porta_local = 6000 + rover_id 
        self.endereco_nave = (IP_NAVE, PORTA_UDP_NAVE)
        
        self.bateria = 100
        self.status = "IDLE"
        self.posicao = [10 * rover_id, 20 * rover_id]
        self.seq = 100
        
        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", self.porta_local))
        print(f"🤖 ROVER-{self.id} ONLINE (UDP {self.porta_local})")

    def log(self, texto):
        print(f"[{time.strftime('%H:%M:%S')}] {texto}")

    # --- BATERIA (Desce sozinha) ---
    def loop_bateria(self):
        while True:
            time.sleep(2)
            if self.status == "CHARGING":
                if self.bateria < 100: self.bateria += 5
                else:
                    self.status = "IDLE"
                    self.avisar_udp("STATUS: IDLE")
            elif self.status == "EM_MISSAO":
                self.bateria -= 2
            elif self.bateria > 0:
                self.bateria -= 1

    # --- TELEMETRIA (Para o Site ver) ---
    def loop_telemetria_tcp(self):
        while True:
            try:
                s = socket(AF_INET, SOCK_STREAM)
                s.settimeout(2)
                s.connect((IP_NAVE, PORTA_TCP_NAVE))
                dados = {
                    "id": f"Rover-{self.id}", 
                    "bat": self.bateria,
                    "pos": self.posicao,
                    "status": self.status
                }
                s.sendall(json.dumps(dados).encode('utf-8'))
                s.close()
            except: pass
            time.sleep(2)

    def avisar_udp(self, msg):
        self.seq += 1
        p = Pacote.MissionPacket(TIPO_PROGRESSO, self.seq, payload=msg.encode('utf-8'))
        self.sock.sendto(p.pack(), self.endereco_nave)

    def run(self):
        threading.Thread(target=self.loop_bateria, daemon=True).start()
        threading.Thread(target=self.loop_telemetria_tcp, daemon=True).start()
        
        self.avisar_udp("STATUS: IDLE")
        
        while True:
            try:
                d, a = self.sock.recvfrom(4096)
                pct = Pacote.MissionPacket.unpack(d)
                
                # ACK sempre
                ack = Pacote.MissionPacket(TIPO_ACK, ack_num=pct.num_seq)
                self.sock.sendto(ack.pack(), a)

                if pct.tipo_msg == TIPO_DADOS_MISSAO:
                    txt = pct.payload.decode('utf-8')
                    if "CMD:CHARGE" in txt:
                        self.log("🔌 A Carregar...")
                        self.status = "CHARGING"
                    elif "{" in txt:
                        self.log(f"🚀 Missão Recebida: {txt}")
                        self.status = "EM_MISSAO"
                        # (Aqui podes adicionar logica para voltar a IDLE apos X segundos)
                        def voltar_idle():
                            time.sleep(10)
                            self.status = "IDLE"
                            self.avisar_udp("MISSAO CONCLUIDA")
                        threading.Thread(target=voltar_idle).start()

            except Exception as e: print(f"Erro: {e}")

if __name__ == "__main__":
    rid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    RoverAutonomo(rid).run()