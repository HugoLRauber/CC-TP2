import time
import threading
import json
import os
from datetime import datetime

class Database:
    def __init__(self):
        self.dados = dict()
        self.quantos = 0
        self.lock = threading.Lock()

        self.ultimos_seq_vistos = dict()
        self.ack_events = dict()

        self.lista_de_missoes = []
        self.telemetria_rovers = {}
        self.config_rovers = {}

        self.missao_seq_counter = 100
        self.missao_atribuida_cache = {}

        self.historico_concluido = {}
        self.missoes_em_curso = {}
        self.buffer_fotos = {}
        self.missoes_concluidas = {} # Estado atual (addr->mid)
        self.historico_permanente = [] # Log lista

        self.FICHEIRO_LOG = "historico_log.txt"
        self._carregar_historico_disco()

    def _get_path(self, filename):
        if os.path.exists(filename): return filename
        # Tenta encontrar ../data/filename
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", filename)
        if os.path.exists(path): return path
        return filename

    def _carregar_historico_disco(self):
        if os.path.exists(self.FICHEIRO_LOG):
            try:
                with open(self.FICHEIRO_LOG, "r", encoding="utf-8") as f:
                    self.historico_permanente = [l.strip() for l in f.readlines()]
            except: pass

    def carregar_missoes_do_ficheiro(self, ficheiro="missoes.json"):
        try:
            with open(self._get_path(ficheiro), 'r', encoding='utf-8') as f:
                self.lista_de_missoes = json.load(f)
            print(f" DB: {len(self.lista_de_missoes)} missões carregadas.")
        except Exception as e: print(f" DB: Erro missoes: {e}")

    def carregar_config(self):
        try:
            with open(self._get_path("rovers_config.json"), 'r', encoding='utf-8') as f:
                raw = json.load(f)
                self.config_rovers = {int(k): v for k,v in raw.items()}
            print(f" DB: {len(self.config_rovers)} rovers configurados.")
        except Exception as e: print(f" DB: Erro config: {e}")

    def carregar_dados(self):
        self.carregar_missoes_do_ficheiro("missoes.json")
        self.carregar_config()

    # --- LÓGICA GERAL ---
    def resolver_nome_rover(self, rover_id_ou_nome):
        try:
            rid = int(rover_id_ou_nome)
            if rid in self.config_rovers: return self.config_rovers[rid]["nome"]
        except: pass
        return str(rover_id_ou_nome)

    def atualizar_telemetria(self, rover_key, dados):
        with self.lock:
            # Tenta normalizar o ID
            rid = dados.get("id")
            if rid: rover_key = self.resolver_nome_rover(rid)

            if rover_key not in self.telemetria_rovers:
                self.telemetria_rovers[rover_key] = {}

            self.telemetria_rovers[rover_key].update(dados)

    def processa_e_insere(self, addr, num_seq, msg):
        with self.lock:
            last = self.ultimos_seq_vistos.get(addr, -1)
            if num_seq == last: return False
            self.ultimos_seq_vistos[addr] = num_seq
            if msg != "DATA_FRAGMENT":
                self.quantos += 1
                ts = datetime.now().strftime('%H:%M:%S')
                self.dados[f"[{ts}] {msg}"] = self.quantos
            return True

    # --- API DATA GENERATION (CORRIGIDO) ---
    def get_estado_completo(self):
        with self.lock:
            frota = {}

            # 1. Configuração Estática (Base)
            for rid, conf in self.config_rovers.items():
                nome = conf["nome"]
                # Inicializa com valores padrão para aparecer no HTML mesmo se offline
                frota[nome] = {
                    "id": rid,
                    "nome": nome,
                    "ip": conf["ip"],
                    "bat": 0,
                    "status": "OFFLINE",
                    "pos": [0,0],
                    "progresso": 0
                }

            # 2. Telemetria Real (Sobrepõe)
            for nome, dados in self.telemetria_rovers.items():
                # Se o rover já existe na config, atualizamos
                # Se for novo (não configurado), criamos entrada
                if nome in frota:
                    frota[nome].update(dados)
                else:
                    frota[nome] = dados

            # 3. Histórico
            for nome in frota:
                frota[nome]["historico"] = self.historico_concluido.get(nome, [])

            return {
                "frota": frota, # <--- O HTML PROCURA ESTA CHAVE!
                "logs": list(self.dados.items())[-15:]
            }

    # --- MÉTODOS AUXILIARES (UDP/FOTO/MISSÃO) ---
    def get_novo_id_missao(self):
        with self.lock: self.missao_seq_counter += 1; return self.missao_seq_counter % 256

    def get_proxima_missao(self, nome_rover):
        with self.lock:
            if not self.lista_de_missoes: return None
            feitos = [m["id"] for m in self.historico_concluido.get(nome_rover, [])]
            for m in self.lista_de_missoes:
                if m["id"] not in feitos: return m
            return None

    def registar_conclusao(self, nome_rover, tarefa):
        with self.lock:
            if nome_rover not in self.historico_concluido: self.historico_concluido[nome_rover] = []
            reg = {"id": tarefa, "ts": datetime.now().strftime('%H:%M:%S'), "status": "SUCESSO"}
            # Evita duplicados exatos
            if not any(x['id'] == tarefa for x in self.historico_concluido[nome_rover]):
                self.historico_concluido[nome_rover].append(reg)

    def preparar_espera_ack(self, addr, seq):
        with self.lock:
            k = (addr, seq); self.ack_events[k] = threading.Event(); return self.ack_events[k]
    def notificar_ack_recebido(self, addr, seq):
        with self.lock:
            k = (addr, seq);
            if k in self.ack_events: self.ack_events[k].set()
    def limpar_espera_ack(self, addr, seq):
        with self.lock:
            k = (addr, seq);
            if k in self.ack_events: del self.ack_events[k]

    def cache_missao_atribuida(self, addr, mid, d):
        with self.lock: self.missao_atribuida_cache[addr] = (mid, d)
    def get_missao_cache(self, addr):
        with self.lock: return self.missao_atribuida_cache.get(addr, None)
    def clear_missao_concluida(self, addr):
        with self.lock: self.missoes_concluidas.pop(addr, None)
    def clear_missao_cache(self, addr):
        with self.lock: self.missao_atribuida_cache.pop(addr, None)
    def get_missao_concluida_id(self, addr):
        with self.lock: return self.missoes_concluidas.get(addr, None)
    def marcar_missao_concluida(self, addr, mid):
        with self.lock:
            self.missoes_concluidas[addr] = mid
            try: open(self.FICHEIRO_LOG, "a").write(f"{mid}\n")
            except: pass
    def adicionar_fragmento_foto(self, addr, d):
        with self.lock: self.buffer_fotos[addr] = self.buffer_fotos.get(addr, b"") + d
    def finalizar_foto(self, addr):
        with self.lock: return self.buffer_fotos.pop(addr, b"")
    def limpar_historico_rover(self, addr): pass
