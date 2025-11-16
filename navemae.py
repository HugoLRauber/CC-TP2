from socket import *
import time
from threading import *

from database import Database
import Pacote
import json

# Importar TODAS as constantes necessárias do protocolo
from Pacote import (
    TIPO_PEDIDO_MISSAO,
    TIPO_DADOS_MISSAO,
    TIPO_ACK,
    TIPO_PROGRESSO,
    FLAG_MORE_FRAGMENTS
)

MAX_PAYLOAD = 255

def carregar_missoes(ficheiro="missoes.json"):
    """ Carrega a lista de missões do ficheiro JSON. """
    try:
        with open(ficheiro, 'r') as f:
            missoes = json.load(f)
            return missoes
    except Exception as e:
        print(f"Erro a carregar missoes.json: {e}")
        return [] # Retorna lista vazia se falhar

def servico(addr : tuple, dados_brutos : bytes, s : socket.socket, database : Database):
    """
    Esta é a função que corre numa thread e trata de CADA pacote recebido.
    """
    try:
        # 1. Desempacotar os bytes para um objeto Pacote
        pacote_recebido = Pacote.MissionPacket.unpack(dados_brutos)

        print(f"[Thread] Recebi um pacote de {addr} (Seq={pacote_recebido.num_seq})")
        print(f"  -> Tipo Msg.: {pacote_recebido.tipo_msg}")

        # --------------------
        # 1. TIPO_PEDIDO_MISSAO
        # --------------------
        if pacote_recebido.tipo_msg == TIPO_PEDIDO_MISSAO:

            payload_str = pacote_recebido.payload.decode('utf-8')

            # 1.1. Verificar duplicados e inserir
            foi_processado = database.processa_e_insere(
                addr,
                pacote_recebido.num_seq,
                payload_str
            )

            # 1.2. Enviar ACK
            pacote_ack = Pacote.MissionPacket(
                tipo_msg=TIPO_ACK,
                ack_num=pacote_recebido.num_seq
            )
            s.sendto(pacote_ack.pack(), addr)
            print(f"[Thread] ACK enviado para {addr} (confirmando seq {pacote_ack.ack_num})")


            id_da_missao_a_enviar = None
            dados_missao_completos = None

            if foi_processado:
                # --- PEDIDO NOVO ---
                print(f"[Thread] Pedido novo, a gerar e cachear missão...")

                missao_dict = database.get_proxima_missao()
                if missao_dict:
                    try:
                        json_string = json.dumps(missao_dict)
                        dados_missao_completos = json_string.encode('utf-8')
                        print(f"[Thread] A enviar missão: {missao_dict.get('id', 'SEM ID')}")
                    except Exception as e:
                        print(f"[Thread] Erro a converter missão: {e}")
                        dados_missao_completos = b'{"erro": "Erro ao gerar missao"}'
                else:
                    print("[Thread] AVISO: Não há missões carregadas.")
                    dados_missao_completos = b'{"erro": "Nenhuma missao disponivel"}'

                # Obter um ID de protocolo novo
                id_da_missao_a_enviar = database.get_novo_id_missao()

                # GUARDAR NO CACHE
                database.cache_missao_atribuida(addr, id_da_missao_a_enviar, dados_missao_completos)

            else:
                # --- PEDIDO DUPLICADO ---
                print(f"[Thread] Pacote duplicado! A re-enviar missão do cache...")

                # OBTER DO CACHE
                cached_data = database.get_missao_cache(addr)
                if cached_data:
                    id_da_missao_a_enviar, dados_missao_completos = cached_data
                else:
                    print(f"[Thread] ERRO: Duplicado, mas não há missão em cache para {addr}!")
                    dados_missao_completos = b'{"erro": "Cache de missao perdido"}'
                    id_da_missao_a_enviar = 404 # ID de erro

            # Esta lógica agora corre SEMPRE, quer a missão seja nova ou do cache.

            if dados_missao_completos:
                offset = 0
                while offset < len(dados_missao_completos):
                    payload_fragmento = dados_missao_completos[offset : offset + MAX_PAYLOAD]
                    offset_deste_fragmento = offset
                    offset += len(payload_fragmento)

                    flags = 0
                    if offset < len(dados_missao_completos):
                        flags = FLAG_MORE_FRAGMENTS

                    pacote_fragmento = Pacote.MissionPacket(
                        tipo_msg=TIPO_DADOS_MISSAO,
                        num_seq=id_da_missao_a_enviar, # Usa o ID (novo ou cacheado)
                        flags=flags,
                        frag_offset=offset_deste_fragmento,
                        payload=payload_fragmento
                    )
                    s.sendto(pacote_fragmento.pack(), addr)

                print(f"[Thread] Envio/Re-envio de fragmentos (ID {id_da_missao_a_enviar}) para {addr} concluído.")

            # --- TIPO_PROGRESSO ---
            elif pacote_recebido.tipo_msg == TIPO_PROGRESSO:

                progresso_str = pacote_recebido.payload.decode('utf-8')
                foi_processado = database.processa_e_insere(
                    addr,
                    pacote_recebido.num_seq,
                    f"PROGRESSO ROVER {addr}: {progresso_str}"
                )

                if foi_processado:
                    print(f"  -> Payload (Progresso NOVO): {progresso_str}")
                else:
                    print(f"[Thread] Progresso duplicado! (Seq={pacote_recebido.num_seq}).")

                pacote_ack_progresso = Pacote.MissionPacket(
                    tipo_msg=TIPO_ACK,
                    ack_num=pacote_recebido.num_seq
                )
                s.sendto(pacote_ack_progresso.pack(), addr)
                print(f"[Thread] ACK (Progresso) enviado para {addr}")

        # --------------------
        # 3. TIPO_ACK (O Rover a confirmar os nossos dados)
        # --------------------
        elif pacote_recebido.tipo_msg == TIPO_ACK:
            print(f"[Thread] Recebido ACK do Rover (confirmando o nosso Seq {pacote_recebido.ack_num})")
            # Aqui, a Nave-Mãe pararia de retransmitir os dados da missão
            # (se tivéssemos implementado esse loop de retransmissão no servidor)

        # --------------------
        # 4. Outros Tipos
        # --------------------
        else:
            print(f"Tipo de mensagem {pacote_recebido.tipo_msg} não conhecido.")

    except Exception as e:
        print(f"Erro a processar pacote de {addr}: {e}")


def arranca_servico1(database : Database):
    """
    O "Dispatcher" - Apenas escuta e delega trabalho para as threads 'servico'.
    """
    s : socket = socket(AF_INET, SOCK_DGRAM)

    endereco : str = "127.0.0.1" # Escuta em localhost
    porta : int = 4444

    try:
        s.bind((endereco, porta))
    except OSError as e:
        print(f"Isto correu mal ao fazer bind (porta 4444): {e}")
        exit(1)

    print(f"Servidor MissionLink (UDP) à escuta em {endereco}:{porta}")

    while True:
        dados, addr = s.recvfrom(1024)
        Thread(target=servico, args=(addr, dados, s, database)).start()

    s.close() # Nunca será alcançado

def servico2(addr : tuple, dados : bytes, s : socket, database : Database):
    # TODO: Esta função também precisa de ser atualizada -> protocolo TCP
    # para usar Pacote.unpack() e Pacote.pack() e fiabilidade
    print("SERVIÇO 2 AINDA NÃO IMPLEMENTA O PROTOCOLO FIÁVEL!")

    database.apaga(dados.decode('utf-8'))
    time.sleep(8)
    s.sendto("Recebido".encode('utf-8'), addr)

def arranca_servico2(database : Database):
    s : socket = socket(AF_INET, SOCK_DGRAM)

    endereco : str = "127.0.0.1"
    porta : int = 5555

    try:
        s.bind((endereco, porta))
    except OSError as e:
        print(f"Isto correu mal (porta 5555): {e}")
        exit(1)

    print(f"Servidor (serviço 2) à escuta em {endereco}:{porta}")

    while True:
        dados, addr = s.recvfrom(1000)
        Thread(target=servico2, args=(addr, dados, s, database)).start()

    s.close()

def arranca_servico3(database : Database):
    """
    Thread que periodicamente mostra o estado da base de dados.
    """
    while True:
        time.sleep(15) # Mostrar o estado a cada 15 segundos
        print("\n--- [Estado Atual da Database] ---")
        database.show()
        print("--- [Fim do Estado] ---\n")

def main():
    threads : list = list()
    database : Database = Database()

    database.carregar_missoes_do_ficheiro("missoes.json")

    # Arrancar os 3 serviços em threads separadas
    threads.append(Thread(target=arranca_servico1, args=(database,)))
    threads.append(Thread(target=arranca_servico2, args=(database,)))
    threads.append(Thread(target=arranca_servico3, args=(database,)))

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()