import threading
import json
import os
from datetime import datetime

class Database:
    def __init__(self):
        self.lock = threading.Lock()
        self.dados = dict()
        self.quantos = 0
        self.ultimos_seq_vistos = dict()
        self.ack_events = dict()
        
        self.lista_de_missoes = []
        self.telemetria_rovers = {} 
        self.config_rovers = {}
        
        self.missao_seq_counter = 100
        self.missao_atribuida_cache = {}
        
        # Histórico por Nome/ID do Rover (não por IP, porque o IP muda)
        self.historico_concluido = {} # { "Rover-Alpha": [missao1, missao2] }
        self.missoes_em_curso = {}    # { "Rover-Alpha": "M-001" }

    def _get_path(self, filename):
        # Procura na pasta atual ou ../data
        if os.path.exists(filename): return filename
        path = os.path.join("..", "data", filename)
        if os.path.exists(path): return path
        # Tenta ../ se estivermos em src
        path = os.path.join("..", filename)
        if os.path.exists(path): return path
        return filename

    def carregar_dados(self):
        # 1. Missões
        try:
            with open(self._get_path("missoes.json"), 'r', encoding='utf-8') as f:
                self.lista_de_missoes = json.load(f)
            print(f"📦 DB: {len(self.lista_de_missoes)} missões carregadas.")
        except Exception as e: print(f"❌ DB: Erro missoes.json: {e}")

        # 2. Config Rovers
        try:
            with open(self._get_path("rovers_config.json"), 'r', encoding='utf-8') as f:
                raw = json.load(f)
                self.config_rovers = {int(k): v for k,v in raw.items()}
            print(f"📦 DB: {len(self.config_rovers)} rovers configurados.")
        except Exception as e: print(f"❌ DB: Erro rovers_config.json: {e}")

    # --- IDENTIFICAÇÃO ---
    def resolver_nome_rover(self, rover_id_ou_nome):
        # Tenta encontrar o nome bonito baseado no ID
        try:
            rid = int(rover_id_ou_nome)
            if rid in self.config_rovers:
                return self.config_rovers[rid]["nome"]
        except: pass
        return str(rover_id_ou_nome) # Retorna o original se falhar

    # --- TELEMETRIA ---
    def atualizar_telemetria(self, rover_key, dados):
        with self.lock:
            # Garante que temos o nome oficial se disponível
            if "id" in dados:
                rover_key = self.resolver_nome_rover(dados["id"])
                dados["nome_oficial"] = rover_key
            
            if rover_key not in self.telemetria_rovers:
                self.telemetria_rovers[rover_key] = {}
            
            dados["last_seen"] = datetime.now().timestamp()
            self.telemetria_rovers[rover_key].update(dados)

    # --- MISSÕES ---
    def get_proxima_missao(self, nome_rover):
        with self.lock:
            if not self.lista_de_missoes: return None
            
            # Histórico deste rover
            feitos = [m["id"] for m in self.historico_concluido.get(nome_rover, [])]
            
            # Procura a primeira missão não feita
            for m in self.lista_de_missoes:
                if m["id"] not in feitos:
                    return m
            return None # Já fez tudo

    def registar_conclusao(self, nome_rover, missao_id):
        with self.lock:
            if nome_rover not in self.historico_concluido:
                self.historico_concluido[nome_rover] = []
            
            # Adiciona ao histórico com timestamp
            registo = {
                "id": missao_id,
                "ts": datetime.now().strftime('%H:%M:%S'),
                "status": "SUCESSO"
            }
            # Evitar duplicados no log
            if not any(x['id'] == missao_id for x in self.historico_concluido[nome_rover]):
                self.historico_concluido[nome_rover].append(registo)
                print(f"🏁 DB: {nome_rover} concluiu {missao_id}")

    # --- API ---
    def get_estado_completo(self):
        with self.lock:
            frota = {}
            # Preenche com rovers configurados (mesmo que offline)
            for rid, conf in self.config_rovers.items():
                nome = conf["nome"]
                frota[nome] = {
                    "id": rid, "nome": nome, "status": "OFFLINE", 
                    "bat": 0, "pos": [0,0,0], "ip": conf.get("ip", "?")
                }
            
            # Atualiza com telemetria real
            for nome, dados in self.telemetria_rovers.items():
                if nome in frota: frota[nome].update(dados)
                else: frota[nome] = dados # Rover desconhecido
            
            # Adiciona histórico a cada rover para o UI
            for nome in frota:
                frota[nome]["historico"] = self.historico_concluido.get(nome, [])

            return {
                "frota": frota,
                "logs": list(self.dados.items())[-15:]
            }

    # --- UDP UTILS ---
    def get_novo_id_missao(self):
        with self.lock: 
            self.missao_seq_counter += 1
            return self.missao_seq_counter

    def processa_e_insere(self, addr, num_seq, msg):
        with self.lock:
            last = self.ultimos_seq_vistos.get(addr, -1)
            if num_seq <= last: return False
            self.ultimos_seq_vistos[addr] = num_seq
            self.quantos += 1
            ts = datetime.now().strftime('%H:%M:%S')
            self.dados[f"[{ts}] {msg}"] = self.quantos
            return True

    def cache_missao_atribuida(self, addr, mid, dados): 
        with self.lock: self.missao_atribuida_cache[addr] = (mid, dados)
    def get_missao_cache(self, addr): 
        with self.lock: return self.missao_atribuida_cache.get(addr, None)
    
    # Métodos placeholder para compatibilidade
    def preparar_espera_ack(self, a, b): pass
    def limpar_espera_ack(self, a, b): pass
    def notificar_ack_recebido(self, a, b): pass