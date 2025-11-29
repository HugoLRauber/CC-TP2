import time
import threading
import json
import os
from datetime import datetime

class Database:
    def __init__(self):
        self.lock = threading.Lock()
        
        # Dados voláteis
        self.dados = dict()
        self.quantos = 0
        self.ultimos_seq_vistos = dict()
        self.ack_events = dict()
        self.telemetria_rovers = dict()
        self.missao_atribuida_cache = dict()
        
        # Dados estáticos
        self.lista_de_missoes = []
        self.config_rovers = {}
        
        # Estado Lógico
        self.estado_rovers = {} # {id_rover: "IDLE" | "EM_MISSAO" | "CHARGING"}
        self.missao_seq_counter = 100
        
        # Histórico
        self.historico_permanente = []
        self.missoes_concluidas = dict()

    # --- CONFIGURAÇÃO ---
    def carregar_tudo(self):
        try:
            with open("missoes.json", 'r') as f: self.lista_de_missoes = json.load(f)
            print(f"✅ DB: {len(self.lista_de_missoes)} missões carregadas.")
        except: print("❌ DB: Erro ao carregar missoes.json")

        try:
            with open("rovers_config.json", 'r') as f: 
                conf = json.load(f)
                # Converter chaves para int para facilitar
                self.config_rovers = {int(k): v for k,v in conf.items()}
                # Inicializar estado
                for rid in self.config_rovers:
                    self.estado_rovers[rid] = "OFFLINE"
            print(f"✅ DB: {len(self.config_rovers)} rovers configurados.")
        except: print("❌ DB: Erro ao carregar rovers_config.json")

    def get_rover_id_by_addr(self, addr):
        # Tenta mapear IP/Porta ao ID configurado (Simplificação para localhost: assume portas diferentes)
        # Num cenário real, usariamos o payload para identificar.
        # Aqui, vamos confiar que o Rover manda o seu ID nas mensagens.
        pass 

    def atualizar_estado_rover(self, rover_id, estado):
        with self.lock:
            self.estado_rovers[rover_id] = estado

    def atualizar_telemetria(self, rover_id, dados):
        with self.lock:
            self.telemetria_rovers[rover_id] = dados
            # Atualizar estado baseado na telemetria também
            if "status" in dados:
                self.estado_rovers[rover_id] = dados["status"]

    # --- ACKS & SEQUENCIA ---
    def get_novo_id_missao(self):
        with self.lock: 
            self.missao_seq_counter += 1
            return (self.missao_seq_counter - 1) % 65000

    def preparar_espera_ack(self, addr, seq_num):
        with self.lock:
            k = (addr, seq_num); self.ack_events[k] = threading.Event(); return self.ack_events[k]
    
    def notificar_ack_recebido(self, addr, seq_num):
        with self.lock:
            k = (addr, seq_num)
            if k in self.ack_events: self.ack_events[k].set()
            
    def processa_e_insere(self, addr, num_seq, msg):
        with self.lock:
            last = self.ultimos_seq_vistos.get(addr, -1)
            if num_seq <= last and last - num_seq < 1000: return False
            self.ultimos_seq_vistos[addr] = num_seq
            if "DATA" not in msg:
                self.quantos += 1
                ts = datetime.now().strftime('%H:%M:%S')
                self.dados[f"[{ts}] {msg}"] = self.quantos
            return True

    # --- CACHE ---
    def cache_missao(self, rover_id, id_missao, dados):
        with self.lock: self.missao_atribuida_cache[rover_id] = (id_missao, dados)
    
    def get_cache(self, rover_id):
        with self.lock: return self.missao_atribuida_cache.get(rover_id, None)

    # --- API GETTER ---
    def get_estado_completo(self):
        with self.lock:
            # Fundir config estática com dados dinâmicos
            frota = {}
            for rid, conf in self.config_rovers.items():
                tel = self.telemetria_rovers.get(rid, {})
                st = self.estado_rovers.get(rid, "OFFLINE")
                frota[rid] = {
                    "config": conf,
                    "telemetria": tel,
                    "estado_missao": st
                }
            
            return {
                "frota": frota,
                "missoes_disponiveis": self.lista_de_missoes,
                "eventos_recentes": list(self.dados.items())[-10:]
            }