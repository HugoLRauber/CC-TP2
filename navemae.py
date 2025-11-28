from socket import *
import time
from threading import *
from database import Database
import Pacote
import json

# IMPORTAR O MÓDULO NOVO
from HTTP import arranca_api_http

from Pacote import (
    TIPO_PEDIDO_MISSAO,
    TIPO_DADOS_MISSAO,
    TIPO_ACK,
    TIPO_PROGRESSO,
    FLAG_MORE_FRAGMENTS
)

MAX_PAYLOAD = 255

def abrir_socket(endereco: str = "127.0.0.1", porta: int = 4444):
    try:
        s = socket(AF_INET, SOCK_DGRAM)
        # s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        s.bind((endereco, porta))
        return s
    except OSError as e:
        print(f"Erro crítico ao fazer bind na porta {porta}: {e}")
        return None

# --- ENVIO FIÁVEL (Stop-and-Wait) ---
def enviar_pacote_fiavel(sock, addr, pacote, database):
    pacote_bytes = pacote.pack()
    seq = pacote.num_seq
    tentativas = 0; max_tentativas = 5
    evento_ack = database.preparar_espera_ack(addr, seq)

    while tentativas < max_tentativas:
        sock.sendto(pacote_bytes, addr)
        if evento_ack.wait(timeout=1.0):
            database.limpar_espera_ack(addr, seq)
            return True
        tentativas += 1

    database.limpar_espera_ack(addr, seq)
    print(f"[UDP] FALHA ENVIO para {addr}.")
    return False

# --- SERVIÇO 1: UDP (MISSION LINK) ---
def servico_udp(addr : tuple, dados_brutos : bytes, s : socket, database : Database):
    str_addr = f"{addr[0]}:{addr[1]}"
    try:
        pacote_recebido = Pacote.MissionPacket.unpack(dados_brutos)

        # 1. ACK RECEBIDO
        if pacote_recebido.tipo_msg == TIPO_ACK:
            database.notificar_ack_recebido(addr, pacote_recebido.ack_num)
            return

            # 2. PEDIDO DE MISSÃO
        if pacote_recebido.tipo_msg == TIPO_PEDIDO_MISSAO:
            payload_str = pacote_recebido.payload.decode('utf-8')
            bat = 100; nome = "Desconhecido"
            try:
                req = json.loads(payload_str)
                if isinstance(req, dict):
                    bat = int(req.get("bat", 100))
                    nome = req.get("id", f"Rover-{addr[1]}")
            except: pass

            foi_processado = database.processa_e_insere(addr, pacote_recebido.num_seq, payload_str)
            s.sendto(Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pacote_recebido.num_seq).pack(), addr)

            id_e = None; data_e = None
            if foi_processado:
                print(f"[UDP] Pedido de {nome} ({str_addr}). Bat: {bat}%")
                missao = database.get_proxima_missao(addr)
                if missao:
                    dur = int(missao.get("duracao", 0)); custo = dur
                    print(f"[UDP] Missão {missao['id']} requer {custo}%")
                    if bat >= custo:
                        try:
                            data_e = json.dumps(missao).encode('utf-8')
                            print(f"[UDP] Atribuída: {missao['id']}")
                            id_e = database.get_novo_id_missao()
                            database.cache_missao_atribuida(addr, id_e, data_e)
                            database.clear_missao_concluida(addr)
                        except: data_e = b'ERR'
                    else:
                        print(f"[UDP] RECUSADO: Bat baixa.")
                        database.remover_atribuicao_historico(addr, missao['id'])
                        m = {"erro":"Bateria","acao":"RECARREGAR"}; data_e = json.dumps(m).encode('utf-8'); id_e = 0
                else:
                    print(f"[UDP] {nome} completou tudo.")
                    data_e = b'{"erro":"Sem mais missoes", "concluido": true}'; id_e = database.get_novo_id_missao()
            else:
                # Duplicado
                id_c = database.get_missao_concluida_id(addr)
                if id_c:
                    r = {"id": id_c, "progresso": 100}
                    s.sendto(Pacote.MissionPacket(tipo_msg=TIPO_DADOS_MISSAO, num_seq=0, payload=json.dumps(r).encode('utf-8')).pack(), addr)
                    return
                c = database.get_missao_cache(addr)
                if c: id_e, data_e = c
                else: return

            if data_e:
                o = 0
                while o < len(data_e):
                    ch = data_e[o : o + MAX_PAYLOAD]; off_f = o; o += len(ch)
                    fl = FLAG_MORE_FRAGMENTS if o < len(data_e) else 0
                    p = Pacote.MissionPacket(tipo_msg=TIPO_DADOS_MISSAO, num_seq=id_e, flags=fl, frag_offset=off_f, payload=ch)
                    if not enviar_pacote_fiavel(s, addr, p, database): break
                print(f"[UDP] Enviado para {nome}.")

        # 3. PROGRESSO
        elif pacote_recebido.tipo_msg == TIPO_PROGRESSO:
            id_c = database.get_missao_concluida_id(addr)
            if id_c:
                r = {"id": id_c, "progresso": 100}
                s.sendto(Pacote.MissionPacket(tipo_msg=TIPO_DADOS_MISSAO, num_seq=0, payload=json.dumps(r).encode('utf-8')).pack(), addr)
                s.sendto(Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pacote_recebido.num_seq).pack(), addr)
                return

            pay = pacote_recebido.payload.decode('utf-8'); prog=pay; nome="R"
            try:
                d = json.loads(pay)
                if isinstance(d, dict): prog=d.get("p","?"); nome=d.get("id","R")
            except: pass

            proc = database.processa_e_insere(addr, pacote_recebido.num_seq, f"{nome}: {prog}")
            s.sendto(Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pacote_recebido.num_seq).pack(), addr)

            if proc:
                print(f"  -> {nome} ({str_addr}): {prog}")
                pl = str(prog).strip().lower()
                if "100%" in pl or "done" in pl:
                    c = database.get_missao_cache(addr); mid="UNK"
                    if c:
                        try: mid = json.loads(c[1].decode('utf-8')).get('id','UNK')
                        except: pass
                    print(f"[UDP] {mid} concluída por {nome}.")
                    r = {"id": mid, "progresso": 100}
                    p_fim = Pacote.MissionPacket(tipo_msg=TIPO_DADOS_MISSAO, payload=json.dumps(r).encode('utf-8'))
                    enviar_pacote_fiavel(s, addr, p_fim, database)
                    database.marcar_missao_concluida(addr, mid)
                    database.clear_missao_cache(addr); database.limpar_historico_rover(addr)

        # 4. FOTOS
        elif pacote_recebido.tipo_msg == TIPO_DADOS_MISSAO:
            ack = Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pacote_recebido.num_seq)
            s.sendto(ack.pack(), addr)

            if database.processa_e_insere(addr, pacote_recebido.num_seq, "DATA_FRAGMENT"):
                database.adicionar_fragmento_foto(addr, pacote_recebido.payload)
                if not pacote_recebido.has_more_fragments():
                    foto = database.finalizar_foto(addr)
                    try:
                        if b'||END_HEADER||' in foto:
                            h, img = foto.split(b'||END_HEADER||', 1)
                            m = json.loads(h.decode('utf-8'))
                            print(f"[UDP] 📸 FOTO DE {m.get('origem')} ({len(img)} B)!")
                    except: pass

    except Exception as e: print(f"Erro UDP: {e}")

def arranca_servico_udp(db):
    s = abrir_socket("0.0.0.0", 4444)
    if s is None: return
    print(f"Servidor MissionLink (UDP) a escutar na porta 4444")
    while True:
        try:
            d, a = s.recvfrom(1024)
            Thread(target=servico_udp, args=(a, d, s, db)).start()
        except ConnectionResetError:
            # Ignorar erros de rovers que se desligaram abruptamente
            pass
        except Exception as e:
            print(f"Loop UDP: {e}")
    s.close()

# --- SERVIÇO 2: TCP (TELEMETRY STREAM) ---
def lida_cliente_tcp(conn, addr, database):
    str_addr = f"{addr[0]}:{addr[1]}"
    print(f"[TCP] Conexão: {str_addr}")
    try:
        with conn:
            buf = ""
            while True:
                d = conn.recv(1024);
                if not d: break
                buf += d.decode('utf-8')
                while "\n" in buf:
                    m, buf = buf.split("\n", 1)
                    if m.strip():
                        try:
                            dat = json.loads(m); nm = dat.get("id", f"R-{addr[1]}")
                            dat["ip_real"] = str_addr
                            database.atualizar_telemetria(nm, dat)
                        except: pass
    except: pass

def arranca_servico_tcp(db):
    s = socket(AF_INET, SOCK_STREAM); s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    try: s.bind(("0.0.0.0", 5555)); s.listen(5) # 0.0.0.0 para CORE
    except: return
    print(f"Servidor TelemetryStream (TCP) a escutar na porta 5555")
    while True:
        try: c, a = s.accept(); Thread(target=lida_cliente_tcp, args=(c, a, db)).start()
        except: pass

def arranca_monitor(db):
    while True: time.sleep(15); db.show()

def main():
    threads = []
    database = Database()
    database.carregar_missoes_do_ficheiro("missoes.json")

    threads.append(Thread(target=arranca_servico_udp, args=(database,)))
    threads.append(Thread(target=arranca_servico_tcp, args=(database,)))
    threads.append(Thread(target=arranca_monitor, args=(database,))) # Opcional se usar Ground Control

    # --- USA A NOVA FUNÇÃO IMPORTADA DE HTTP.py ---
    threads.append(Thread(target=arranca_api_http, args=(database,)))

    for t in threads: t.start()
    for t in threads: t.join()

if __name__ == "__main__":
    main()