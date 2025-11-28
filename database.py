import time
import threading
import json
import os
from datetime import datetime

class Database:
    dados : dict
    quantos : int
    lock : threading.Lock

    ultimos_seq_vistos : dict
    ack_events: dict

    lista_de_missoes : list
    missao_seq_counter : int

    # Cache e Estado
    missoes_atribuidas_historico : dict
    missao_atribuida_cache: dict
    missoes_concluidas: dict
    historico_permanente: list
    telemetria_rovers: dict
    buffer_fotos: dict

    FICHEIRO_LOG = "historico_log.txt"

    def __init__(self):
        self.dados = dict()
        self.quantos = 0
        self.lock = threading.Lock()
        self.ultimos_seq_vistos = dict()
        self.ack_events = dict()

        self.lista_de_missoes = []
        self.missao_seq_counter = 100
        self.missoes_atribuidas_historico = dict()
        self.missao_atribuida_cache = dict()
        self.missoes_concluidas = dict()
        self.historico_permanente = []
        self.telemetria_rovers = dict()
        self.buffer_fotos = dict()

        # Limpar log antigo ao iniciar (opcional)
        # if os.path.exists(self.FICHEIRO_LOG): os.remove(self.FICHEIRO_LOG)

    # --- ACKS ---
    def preparar_espera_ack(self, addr, seq_num):
        with self.lock:
            k = (addr, seq_num); self.ack_events[k] = threading.Event(); return self.ack_events[k]
    def notificar_ack_recebido(self, addr, seq_num):
        with self.lock:
            k = (addr, seq_num);
            if k in self.ack_events: self.ack_events[k].set()
    def limpar_espera_ack(self, addr, seq_num):
        with self.lock:
            k = (addr, seq_num);
            if k in self.ack_events: del self.ack_events[k]

    # --- MISSÕES (MODO SEQUENCIAL FINITO) ---
    def carregar_missoes_do_ficheiro(self, f="missoes.json"):
        try:
            with open(f,'r') as file: self.lista_de_missoes = json.load(file)
            print(f"INFO: Carregadas {len(self.lista_de_missoes)} missões base.")
        except Exception as e: print(f"ERRO JSON: {e}")

    def get_novo_id_missao(self):
        with self.lock: self.missao_seq_counter += 1; return (self.missao_seq_counter - 1) % 256

    def get_proxima_missao(self, addr) -> dict | None:
        """
        Retorna a próxima missão da lista que este Rover AINDA NÃO FEZ.
        Se já fez todas, retorna None.
        """
        try:
            self.lock.acquire()
            if not self.lista_de_missoes: return None

            if addr not in self.missoes_atribuidas_historico:
                self.missoes_atribuidas_historico[addr] = []

            # Percorrer a lista fixa de missões
            for missao in self.lista_de_missoes:
                mid = missao.get("id")
                # Se este rover ainda não recebeu esta missão
                if mid not in self.missoes_atribuidas_historico[addr]:
                    self.missoes_atribuidas_historico[addr].append(mid)
                    return missao # Retorna a missão original

            return None # Não há mais missões novas para este rover
        finally:
            self.lock.release()

    def remover_atribuicao_historico(self, addr, mid):
        """ Liberta a missão (ex: por falta de bateria) para tentar de novo. """
        with self.lock:
            if addr in self.missoes_atribuidas_historico and mid in self.missoes_atribuidas_historico[addr]:
                self.missoes_atribuidas_historico[addr].remove(mid)

    # --- PROCESSAMENTO ---
    def processa_e_insere(self, addr, num_seq, msg):
        with self.lock:
            last = self.ultimos_seq_vistos.get(addr, -1)
            if num_seq == last: return False
            self.ultimos_seq_vistos[addr] = num_seq
            if msg != "DATA_FRAGMENT": self.quantos += 1; self.dados[msg] = self.quantos
            return True

    def adicionar_fragmento_foto(self, addr, data):
        with self.lock: self.buffer_fotos[addr] = self.buffer_fotos.get(addr, b"") + data
    def finalizar_foto(self, addr):
        with self.lock: return self.buffer_fotos.pop(addr, b"")
    def atualizar_telemetria(self, nome, dados_dict):
        with self.lock: self.telemetria_rovers[nome] = dados_dict

    def show(self):
        with self.lock:
            nov = dict(self.dados); tel = dict(self.telemetria_rovers); his = list(self.historico_permanente)
        print("\n=== DASHBOARD NAVE-MÃE ===")
        if tel:
            for k,v in tel.items(): print(f"TCP {k} ({v.get('ip_real')}) | Bat:{v.get('bat')}% | {v.get('status')}")
        else: print("[TCP] À espera de rovers...")
        print("[Eventos Recentes]")
        for m, q in list(nov.items())[-5:]: print(f" {q}: {m}")
        print("[Histórico]")
        for h in his[-5:]: print(f" {h}")
        print("==========================\n")

    def cache_missao_atribuida(self, addr, mid, dat):
            with self.lock:
                self.missao_atribuida_cache[addr] = (mid, dat)
    def get_missao_cache(self, addr):
            with self.lock:
                return self.missao_atribuida_cache.get(addr, None)
    def clear_missao_concluida(self, addr):
            with self.lock:
                self.missoes_concluidas.pop(addr, None)
    def clear_missao_cache(self, addr):
            with self.lock:
                self.missao_atribuida_cache.pop(addr, None)
    def get_missao_concluida_id(self, addr):
            with self.lock:
                return self.missoes_concluidas.get(addr, None)

    def marcar_missao_concluida(self, addr, mid):
        with self.lock:
            self.missoes_concluidas[addr] = mid
            log = f"[{datetime.now().strftime('%H:%M:%S')}] {addr} terminou {mid}"
            self.historico_permanente.append(log)
            try: open(self.FICHEIRO_LOG,"a", encoding="utf-8").write(log+"\n")
            except: pass

    def limpar_historico_rover(self, addr):
        with self.lock:
            d = [k for k in self.dados if f"{addr}" in k and "100%" not in k];
            for k in d: del self.dados[k]

    def get_estado_completo(self):
        with self.lock:
            c_str = {f"{k[0]}:{k[1]}":v for k,v in self.missoes_concluidas.items()}
            return {
                "telemetria": dict(self.telemetria_rovers),
                "missoes_concluidas": c_str,
                "historico": list(self.historico_permanente)[-10:],
                "eventos_recentes": list(self.dados.items())[-10:]
            }