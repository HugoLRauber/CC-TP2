import socket
import threading
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import Pacote
from Pacote import (TIPO_DADOS_MISSAO, TIPO_ACK, TIPO_PROGRESSO, FLAG_MORE_FRAGMENTS)

def print_log(texto):
    # Log simples alinhado no terminal
    sys.stdout.write(f"\r{texto:<80}\n")
    sys.stdout.flush()

def enviar_comando_manual(database, target_id, payload_str):
    # Envia comando/JSON para um rover via UDP com confirmação por ACK
    target_id = int(target_id)
    conf = database.config_rovers.get(target_id)
    
    if conf:
        addr = (conf["ip"], conf["porta_udp"])
        nome_destino = conf["nome"]
    else:
        addr = ("10.0.0.10", 6000 + target_id)
        nome_destino = f"Rover-{target_id}"

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    seq = database.get_novo_id_missao()
    pct = Pacote.MissionPacket(
        tipo_msg=TIPO_DADOS_MISSAO, 
        num_seq=seq, 
        payload=payload_str.encode('utf-8')
    )
    
    evento_ack = database.preparar_espera_ack(addr, seq)
    max_tentativas = 5
    
    try: 
        print_log(f"[ENVIO] Para {nome_destino} ({addr}) | Cmd: '{payload_str}' | Seq: {seq}")
        
        for tentativa in range(1, max_tentativas + 1):
            s.sendto(pct.pack(), addr)
            
            if evento_ack.wait(timeout=3.0):
                print_log(f"[ACK-RX] {nome_destino} confirmou recepcao do Seq {seq}!")
                return True
            
            if tentativa < max_tentativas:
                print_log(f"[TIMEOUT] {nome_destino} nao respondeu. A retransmitir ({tentativa}/{max_tentativas})...")
        
        print_log(f"[ERRO] {nome_destino} incontactavel apos {max_tentativas} tentativas.")
        return False
            
    except Exception as e: 
        print_log(f"Erro Envio: {e}")
        return False
    finally: 
        database.limpar_espera_ack(addr, seq)
        s.close()

def processar_pacote(addr, dados, s, db):
    try:
        pct = Pacote.MissionPacket.unpack(dados)
        rid = addr[1] - 6000
        nome = db.resolver_nome_rover(rid)

        if pct.tipo_msg == TIPO_ACK:
            db.notificar_ack_recebido(addr, pct.ack_num)
            return

        # Responde com ACK para confirmar receção
        ack = Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pct.num_seq)
        s.sendto(ack.pack(), addr)

        if pct.tipo_msg == TIPO_DADOS_MISSAO:
            payload = pct.payload
            if b"FOTO:" in payload:
                try:
                    partes = payload.split(b":", 2)
                    if len(partes) >= 3:
                        mid_str = partes[1].decode('utf-8')
                        dados_reais = partes[2]
                        tamanho_frag = len(dados_reais)
                        
                        is_more = (pct.flags & FLAG_MORE_FRAGMENTS)
                        flag_val = 1 if is_more else 0
                        flag_str = f"MORE_FRAGS ({flag_val})"

                        print_log(f"[FOTO] [{nome}] Frag '{mid_str}' | Seq {pct.num_seq} | {tamanho_frag}B | {flag_str}")
                        print_log(f"   [ACK-TX] [{nome}] Confirmei fragmento {pct.num_seq}")

                        if flag_val == 0:
                            print_log(f"[FIM] [{nome}] Foto '{mid_str}' recebida com sucesso!")
                except: pass
            return

        if pct.tipo_msg == TIPO_PROGRESSO:
            msg = pct.payload.decode('utf-8')
            updates = {}

            # Deteta handshake inicial de ligação
            is_handshake = "DESCONECTADO" in msg

            # Verifica duplicados
            if not db.processa_e_insere(addr, pct.num_seq, f"{nome}: {msg}"):
                # Se for Handshake duplicado, mostramos para ver a insistencia
                if is_handshake:
                    print_log(f"[HANDSHAKE-RETRY] [{nome}] Rover insiste na conexao (Seq {pct.num_seq})")
                    print_log(f"   [ACK-TX] Reenviei confirmacao de conexao para {nome}")
                
                # Se nao for handshake nem progresso, mostra duplicado normal
                elif "PROGRESS" not in msg:
                    print_log(f"[DUPLICADO] [{nome}] Seq {pct.num_seq} ignorado.")
                return

            # --- PROCESSAMENTO DE MENSAGENS NOVAS ---
            
            if is_handshake:
                print_log(f"[HANDSHAKE] [{nome}] Pedido de conexao recebido! (Seq {pct.num_seq})")
                print_log(f"   [ACK-TX] Aceitei conexao de {nome}")
                updates["status"] = "DESCONECTADO"

            elif "COMPLETED" in msg:
                print_log(f"[MISSAO] [{nome}] {msg}")
                print_log(f"   [ACK-TX] Confirmei FIM de missao")
                updates["status"] = "IDLE"; updates["progresso"] = 0
                try:
                    tarefa = msg.split("COMPLETED: ")[1].strip()
                    db.registar_conclusao(nome, tarefa)
                except: pass

            elif "STARTED" in msg:
                print_log(f"[MISSAO] [{nome}] {msg}")
                print_log(f"   [ACK-TX] Confirmei INICIO de missao")
                updates["status"] = "EM_MISSAO"; updates["progresso"] = 0

            elif "PROGRESS:" in msg:
                try:
                    parts = msg.split("PROGRESS: ")[1].strip().split(" ")
                    val = int(parts[0])
                    updates["progresso"] = val; updates["status"] = "EM_MISSAO"
                    if len(parts) > 1 and "POS:" in parts[1]:
                        coords_str = parts[1].replace("POS:", "")
                        cx, cy = coords_str.split(",")
                        updates["pos"] = [int(cx), int(cy)]
                except: pass

            else:
                # Outras mensagens (IDLE, CHARGING)
                print_log(f"   [ACK-TX] [{nome}] Confirmei estado: '{msg}'")
                if "IDLE" in msg: updates["status"] = "IDLE"
                elif "CHARGING" in msg: updates["status"] = "CHARGING"

            if updates: db.atualizar_telemetria(nome, updates)

    except Exception as e: print_log(f"Erro UDP: {e}")

def start_udp_service(database):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", 4444))
        print_log("[UDP] MissionLink Online")
        while True:
            d, a = s.recvfrom(4096)
            threading.Thread(target=processar_pacote, args=(a, d, s, database)).start()
    except Exception as e: print_log(f"Erro UDP: {e}")
    finally: s.close()
