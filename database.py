import time
import threading
import json

class Database:
    dados : dict
    quantos : int
    lock : threading.Lock
    ultimos_seq_vistos : dict
    lista_de_missoes : list
    proxima_missao_idx : int
    missao_atribuida_cache: dict

    def __init__(self):
        self.dados = dict()
        self.quantos = 0
        self.lock = threading.Lock()
        self.ultimos_seq_vistos = dict()
        self.lista_de_missoes = []
        self.proxima_missao_idx = 0
        self.missao_seq_counter = 1
        self.missao_atribuida_cache = dict()

    def carregar_missoes_do_ficheiro(self, ficheiro="missoes.json"):
        """ Carrega as missões do JSON para a memória. """
        try:
            with open(ficheiro, 'r') as f:
                self.lista_de_missoes = json.load(f)
                print(f"INFO: Carregadas {len(self.lista_de_missoes)} missões do ficheiro {ficheiro}.")
        except Exception as e:
            print(f"ERRO: Não foi possível carregar {ficheiro}: {e}")
            self.lista_de_missoes = []

    def get_novo_id_missao(self) -> int:
        """
        Obtém um ID de sequência único para uma nova transmissão de missão.
        """
        try:
            self.lock.acquire()
            # Pega o ID atual
            novo_id = self.missao_seq_counter
            # Incrementa o contador para a próxima vez
            self.missao_seq_counter += 1
            return novo_id
        finally:
            self.lock.release()

    def get_proxima_missao(self) -> dict | None:
        """
        Retorna a próxima missão da lista, de forma 'round-robin'.
        """
        try:
            self.lock.acquire() # Proteger o índice

            if not self.lista_de_missoes:
                return None # Não há missões

            # Escolher a missão
            missao = self.lista_de_missoes[self.proxima_missao_idx]

            # Avançar o índice para a próxima
            self.proxima_missao_idx = (self.proxima_missao_idx + 1) % len(self.lista_de_missoes)

            return missao
        finally:
            self.lock.release()

    def processa_e_insere(self, addr: tuple, num_seq: int, mensagem: str) -> bool:
        """
        Verifica se um pacote é novo. Se for, insere-o.
        Retorna True se foi inserido, False se for um duplicado.
        """
        try:
            self.lock.acquire()

            ultimo_seq = self.ultimos_seq_vistos.get(addr, -1)

            if num_seq <= ultimo_seq:
                # Não faz nada, apenas liberta o lock e retorna False
                return False

            self.ultimos_seq_vistos[addr] = num_seq # Atualiza o último seq visto

            self.quantos += 1
            self.dados[mensagem] = self.quantos

            return True # Retorna True (foi processado)

        finally:
            self.lock.release()

    def apaga(self, mensagem : str):
        if mensagem in self.dados:
            self.dados.pop(mensagem)
            self.quantos -= 1


    def show(self):
        try:
            self.lock.acquire()
            novo = dict(self.dados)   
        finally:
            self.lock.release()

        for mensagem, quantos in novo.items():
            print(f"mensagem {quantos}: {mensagem}")
            time.sleep(2)

        pass

    def cache_missao_atribuida(self, addr, id_missao, dados_missao_bytes):
        """ Guarda a última missão que foi enviada para um Rover. """
        try:
            self.lock.acquire()
            self.missao_atribuida_cache[addr] = (id_missao, dados_missao_bytes)
        finally:
            self.lock.release()

    def get_missao_cache(self, addr):
        """ Obtém a última missão enviada para um Rover. """
        try:
            self.lock.acquire()
            # Retorna a missão (tuplo) ou None se não houver
            return self.missao_atribuida_cache.get(addr, None)
        finally:
            self.lock.release()