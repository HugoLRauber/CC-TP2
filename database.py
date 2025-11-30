import threading
import json

class Database:
    def __init__(self):
        self.dados = dict()
        self.quantos = 0
        self.lock = threading.Lock()
        self.ultimos_seq_vistos = dict()
        self.lista_de_missoes = []
        
        # Estruturas de Dados
        self.telemetria_rovers = {} # Guarda o último JSON recebido de cada rover
        self.config_rovers = {}     # Guarda a config estática (IPs, Portas)
        self.missao_seq_counter = 100
        self.missao_atribuida_cache = {}

    def carregar_missoes_do_ficheiro(self, ficheiro="missoes.json"):
        try:
            with open(ficheiro, 'r') as f: self.lista_de_missoes = json.load(f)
        except: pass

    def carregar_config(self):
        try:
            with open("rovers_config.json", 'r') as f: 
                raw = json.load(f)
                # Converter chaves string "1" para int 1
                self.config_rovers = {int(k): v for k,v in raw.items()}
        except: pass

    def atualizar_telemetria(self, rover_id, dados):
        with self.lock:
            rover_id = int(rover_id) # Assegurar int
            if rover_id not in self.telemetria_rovers:
                self.telemetria_rovers[rover_id] = {}
            self.telemetria_rovers[rover_id].update(dados)

    def atualizar_estado_rover(self, rover_id, estado):
        self.atualizar_telemetria(rover_id, {"status": estado})

    # --- FUNÇÃO CRUCIAL PARA A API ---
    def get_estado_completo(self):
        with self.lock:
            # Constrói uma visão unificada para o HTML
            visao_frota = {}
            
            # 1. Cria entradas para todos os rovers configurados
            for rid, conf in self.config_rovers.items():
                visao_frota[rid] = {
                    "id": rid,
                    "nome": conf["nome"],
                    "ip": conf["ip"],
                    "bat": 0,
                    "status": "OFFLINE",
                    "pos": [0,0]
                }

            # 2. Preenche com dados de telemetria se existirem
            for rid, tel in self.telemetria_rovers.items():
                if rid in visao_frota:
                    visao_frota[rid].update(tel)
                else:
                    # Rover não configurado mas detetado
                    visao_frota[rid] = tel

            return {
                "telemetria": visao_frota, # O HTML usa isto
                "frota": visao_frota,      # O NaveMae usa isto
                "eventos_recentes": list(self.dados.items())[-10:]
            }
            
    # --- MÉTODOS UDP ---
    def get_novo_id_missao(self):
        with self.lock: 
            self.missao_seq_counter += 1
            return self.missao_seq_counter

    def processa_e_insere(self, addr, num_seq, msg):
        with self.lock:
            self.quantos += 1
            self.dados[msg] = self.quantos
            return True

    def cache_missao_atribuida(self, addr, mid, dados): pass
    def get_missao_cache(self, addr): return None
    def get_proxima_missao(self): return None
    def apaga(self, msg): pass
    def show(self): pass