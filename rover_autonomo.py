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
        self.id = int(rover_id)
        self.porta_local = 6000 + self.id 
        self.endereco_nave = (IP_NAVE, PORTA_UDP_NAVE)
        
        self.bateria = 100
        self.status = "IDLE"
        self.posicao = [10 * self.id, 20 * self.id]
        self.seq = 100
        
        self.sock = socket(AF_INET, SOCK_DGRAM)
        try:
            self.sock.bind(("0.0.0.0", self.porta_local))
            print(f"🤖 ROVER-{self.id} ONLINE (UDP {self.porta_local})")
        except:
            print(f"❌ Erro: Porta {self.porta_local} ocupada.")
            sys.exit(1)

    def log(self, texto):
        print(f"[{time.strftime('%H:%M:%S')}] {texto}")

    # --- THREAD BATERIA (Lógica de Sobrevivência) ---
    def loop_bateria(self):
        while True:
            time.sleep(10) # Bateria desce a cada 10 segundos
            
            if self.status == "CHARGING":
                if self.bateria < 100: 
                    self.bateria = min(100, self.bateria + 5)
                    self.log(f"⚡ A carregar... {self.bateria}%")
                else:
                    self.status = "IDLE"
                    self.log("🔋 Carga completa.")
                    self.avisar_udp("STATUS: IDLE")
            
            elif self.status == "EM_MISSAO":
                self.bateria = max(0, self.bateria - 2) # Gasta mais em missão
            
            elif self.bateria > 0:
                self.bateria -= 1 # Gasta 1% em repouso

            # --- AUTO-SALVAMENTO ---
            # Se a bateria chegar a 10% e não estiver a carregar, carrega sozinho
            if self.bateria <= 10 and self.status != "CHARGING":
                self.log("⚠️ BATERIA CRÍTICA (10%)! A INICIAR CARGA DE EMERGÊNCIA.")
                self.status = "CHARGING"
                self.avisar_udp("STATUS: CHARGING (AUTO)")

    # --- THREAD TELEMETRIA (TCP a cada 5s) ---
    def loop_telemetria_tcp(self):
        while True:
            # Separador visual no terminal
            print("-" * 40)
            try:
                s = socket(AF_INET, SOCK_STREAM)
                s.settimeout(2)
                s.connect((IP_NAVE, PORTA_TCP_NAVE))
                
                dados = {
                    "id": self.id, 
                    "bat": self.bateria,
                    "pos": self.posicao,
                    "status": self.status
                }
                msg = json.dumps(dados)
                s.sendall(msg.encode('utf-8'))
                s.close()
                self.log(f"📡 Telemetria enviada (Bat: {self.bateria}%)")
            except ConnectionRefusedError:
                pass 
            except Exception as e:
                pass
            
            time.sleep(5) # Envia a cada 5 segundos

    def avisar_udp(self, msg):
        self.seq += 1
        p = Pacote.MissionPacket(TIPO_PROGRESSO, self.seq, payload=msg.encode('utf-8'))
        try: self.sock.sendto(p.pack(), self.endereco_nave)
        except: pass

    def executar_missao(self, missao):
        self.status = "EM_MISSAO"
        duracao = int(missao.get("duracao", 5))
        self.log(f"🚀 INICIANDO MISSÃO: {missao.get('tarefa')} ({duracao}s)")
        self.avisar_udp(f"STARTED: {missao.get('tarefa')}")
        
        for i in range(duracao):
            time.sleep(1)
            self.posicao[0] += 1
            if self.status != "EM_MISSAO": break 

        if self.status == "EM_MISSAO":
            self.status = "IDLE"
            self.log("🏁 Missão Concluída.")
            self.avisar_udp("STATUS: IDLE (Missao Feita)")

    def run(self):
        threading.Thread(target=self.loop_bateria, daemon=True).start()
        threading.Thread(target=self.loop_telemetria_tcp, daemon=True).start()
        
        self.avisar_udp("STATUS: IDLE")
        print("✅ Sistemas automáticos ativos.")
        
        while True:
            try:
                d, a = self.sock.recvfrom(4096)
                pct = Pacote.MissionPacket.unpack(d)
                
                ack = Pacote.MissionPacket(TIPO_ACK, ack_num=pct.num_seq)
                self.sock.sendto(ack.pack(), a)

                if pct.tipo_msg == TIPO_DADOS_MISSAO:
                    txt = pct.payload.decode('utf-8')
                    
                    if "CMD:CHARGE" in txt:
                        self.log("🔌 COMANDO REMOTO: CARREGAR")
                        self.status = "CHARGING"
                        self.avisar_udp("STATUS: CHARGING")
                    
                    elif "{" in txt:
                        try:
                            missao = json.loads(txt)
                            threading.Thread(target=self.executar_missao, args=(missao,)).start()
                        except: pass

            except ConnectionResetError:
                print("⚠️ Aviso: Nave-Mãe offline. À espera...")
                time.sleep(1)
            except Exception as e:
                print(f"Erro loop: {e}")

if __name__ == "__main__":
    rid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    RoverAutonomo(rid).run()