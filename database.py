import time
import threading
import json
import os
from datetime import datetime

class Database:
    dados : dict
    quantos : int
    lock : threading.Lock

    # Controlo de Fiabilidade UDP
    ultimos_seq_vistos : dict

    # Gestão de Missões
    lista_de_missoes : list
    missao_seq_counter : int
    missoes_atribuidas_historico : dict

    # Cache e Estado
    missao_atribuida_cache: dict
    missoes_concluidas: dict
    historico_permanente: list

    # Telemetria (TCP)
    telemetria_rovers: dict

    # Buffer de Fotos
    buffer_fotos: dict

    FICHEIRO_LOG = "historico_log.txt"

    def __init__(self):
        self.dados = dict()
        self.quantos = 0
        self.lock = threading.Lock()

        self.ultimos_seq_vistos = dict()

        self.lista_de_missoes = []
        self.missao_seq_counter = 100

        self.missoes_atribuidas_historico = dict()
        self.missao_atribuida_cache = dict()
        self.missoes_concluidas = dict()
        self.historico_permanente = []
        self.telemetria_rovers = dict()
        self.buffer_fotos = dict()

        self.ack_events = dict()

        # self._carregar_historico_disco()

    def preparar_espera_ack(self, addr, seq_num):
        try:
            self.lock.acquire()
            chave = (addr, seq_num)
            self.ack_events[chave] = threading.Event()
            return self.ack_events[chave]
        finally: self.lock.release()

    def notificar_ack_recebido(self, addr, seq_num):
        try:
            self.lock.acquire()
            chave = (addr, seq_num)
            if chave in self.ack_events: self.ack_events[chave].set()
        finally: self.lock.release()

    def limpar_espera_ack(self, addr, seq_num):
        try:
            self.lock.acquire()
            chave = (addr, seq_num)
            if chave in self.ack_events: del self.ack_events[chave]
        finally: self.lock.release()

    def _carregar_historico_disco(self):
        if os.path.exists(self.FICHEIRO_LOG):
            try:
                with open(self.FICHEIRO_LOG, "r", encoding="utf-8") as f:
                    linhas = f.readlines()
                    self.historico_permanente = [linha.strip() for linha in linhas]
            except Exception as e: print(f"AVISO: {e}")

    def carregar_missoes_do_ficheiro(self, ficheiro="missoes.json"):
        try:
            with open(ficheiro, 'r') as f:
                self.lista_de_missoes = json.load(f)
                print(f"INFO: Carregadas {len(self.lista_de_missoes)} missões.")
        except Exception as e: print(f"ERRO: {e}")

    def get_novo_id_missao(self) -> int:
        try:
            self.lock.acquire()
            self.missao_seq_counter += 1
            return (self.missao_seq_counter - 1) % 256
        finally: self.lock.release()

    def get_proxima_missao(self, addr) -> dict | None:
        try:
            self.lock.acquire()
            if not self.lista_de_missoes: return None
            if addr not in self.missoes_atribuidas_historico:
                self.missoes_atribuidas_historico[addr] = []

            ids_ocupados = set()
            for l in self.missoes_atribuidas_historico.values(): ids_ocupados.update(l)

            for missao in self.lista_de_missoes:
                mid = missao.get("id")
                if mid not in ids_ocupados:
                    self.missoes_atribuidas_historico[addr].append(mid)
                    return missao
            return None
        finally: self.lock.release()

    def remover_atribuicao_historico(self, addr, mission_id):
        try:
            self.lock.acquire()
            if addr in self.missoes_atribuidas_historico and mission_id in self.missoes_atribuidas_historico[addr]:
                self.missoes_atribuidas_historico[addr].remove(mission_id)
        finally: self.lock.release()

    def processa_e_insere(self, addr: tuple, num_seq: int, mensagem: str) -> bool:
        try:
            self.lock.acquire()
            ultimo_seq = self.ultimos_seq_vistos.get(addr, -1)
            if num_seq == ultimo_seq: return False
            self.ultimos_seq_vistos[addr] = num_seq
            if mensagem != "DATA_FRAGMENT":
                self.quantos += 1
                self.dados[mensagem] = self.quantos
            return True
        finally: self.lock.release()

    def apaga(self, mensagem : str):
        try:
            self.lock.acquire()
            if mensagem in self.dados:
                self.dados.pop(mensagem)
                self.quantos -= 1
        finally: self.lock.release()

    def limpar_historico_rover(self, addr):
        try:
            self.lock.acquire()
            chaves_para_apagar = []
            for msg in self.dados.keys():
                if "QUERO_MISSAO" in msg: chaves_para_apagar.append(msg)
                elif f"{addr}" in msg:
                    if "100%" not in msg and "DONE" not in msg: chaves_para_apagar.append(msg)
            for k in chaves_para_apagar:
                if k in self.dados: del self.dados[k]
        finally: self.lock.release()

    def atualizar_telemetria(self, nome, dados_dict):
        try:
            self.lock.acquire()
            self.telemetria_rovers[nome] = dados_dict
        finally: self.lock.release()

    def adicionar_fragmento_foto(self, addr, dados):
        try:
            self.lock.acquire()
            self.buffer_fotos[addr] = self.buffer_fotos.get(addr, b"") + dados
        finally: self.lock.release()

    def finalizar_foto(self, addr):
        try:
            self.lock.acquire()
            return self.buffer_fotos.pop(addr, b"")
        finally: self.lock.release()

    def show(self):
        try:
            self.lock.acquire()
            novo = dict(self.dados)
            hist_copia = list(self.historico_permanente)
            telemetria_copia = dict(self.telemetria_rovers)
        finally: self.lock.release()

        print("\n" + "="*40)
        print("       DASHBOARD NAVE-MÃE")
        print("="*40)
        if telemetria_copia:
            print("\n[TCP] TELEMETRIA EM TEMPO REAL:")
            for nome, dados in telemetria_copia.items():
                s = dados.get('status', 'N/A'); ip = dados.get('ip_real', 'N/A')
                print(f"  {nome} ({ip}) | Bat: {dados.get('bat')}% | {s}")
        else: print("\n[TCP] NENHUM ROVER LIGADO")
        print("\n[UDP] EVENTOS RECENTES:")
        if not novo: print("  (Vazio)")
        for m, q in list(novo.items())[-5:]: print(f"  Msg {q}: {m}")
        print("\n[HISTÓRICO] CONCLUÍDAS:")
        if not hist_copia: print("  (Nenhuma)")
        for e in hist_copia[-5:]: print(f"  {e}")
        print("="*40 + "\n")

    def cache_missao_atribuida(self, addr, id_missao, dados_missao_bytes):
        try:
            self.lock.acquire()
            self.missao_atribuida_cache[addr] = (id_missao, dados_missao_bytes)
        finally: self.lock.release()

    def get_missao_cache(self, addr):
        try:
            self.lock.acquire()
            return self.missao_atribuida_cache.get(addr, None)
        finally: self.lock.release()

    def clear_missao_cache(self, addr):
        try:
            self.lock.acquire()
            if addr in self.missao_atribuida_cache: self.missao_atribuida_cache.pop(addr, None)
        finally: self.lock.release()

    def marcar_missao_concluida(self, addr, mission_id_str):
        try:
            self.lock.acquire()
            self.missoes_concluidas[addr] = mission_id_str
            timestamp = datetime.now().strftime("%H:%M:%S")
            log = f"[{timestamp}] Rover {addr} terminou {mission_id_str}"
            self.historico_permanente.append(log)
            try: open(self.FICHEIRO_LOG, "a", encoding="utf-8").write(log + "\n")
            except: pass
        finally: self.lock.release()

    def get_missao_concluida_id(self, addr):
        try:
            self.lock.acquire()
            return self.missoes_concluidas.get(addr, None)
        finally: self.lock.release()

    def is_missao_concluida(self, addr) -> bool:
        try:
            self.lock.acquire()
            return addr in self.missoes_concluidas
        finally: self.lock.release()

    def clear_missao_concluida(self, addr):
        try:
            self.lock.acquire()
            if addr in self.missoes_concluidas: self.missoes_concluidas.pop(addr, None)
        finally: self.lock.release()

    # --- MÉTODO CORRIGIDO PARA A API ---
    def get_estado_completo(self):
        """ Retorna uma cópia segura de todo o estado para enviar via API. """
        try:
            self.lock.acquire()

            # CONVERSÃO DE CHAVES: Tuplo (IP, Port) -> String "IP:Port"
            # O JSON não suporta tuplos como chaves
            concluidas_str = {}
            for addr_tuple, mission_id in self.missoes_concluidas.items():
                key_str = f"{addr_tuple[0]}:{addr_tuple[1]}"
                concluidas_str[key_str] = mission_id

            return {
                "telemetria": dict(self.telemetria_rovers),
                "missoes_concluidas": concluidas_str, # Usar o dicionário convertido
                "historico": list(self.historico_permanente)[-10:],
                "eventos_recentes": list(self.dados.items())[-10:]
            }
        finally:
            self.lock.release()