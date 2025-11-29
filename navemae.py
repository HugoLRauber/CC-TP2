from socket import *
import time
from threading import *
from database import Database
import Pacote
import json
from HTTP import arranca_api_http 

from Pacote import (
    TIPO_PEDIDO_MISSAO, TIPO_DADOS_MISSAO, TIPO_ACK, 
    TIPO_PROGRESSO, FLAG_MORE_FRAGMENTS
)

MAX_PAYLOAD = 255

# --- LÓGICA DE COMANDO MANUAL (Para o HTML) ---
def enviar_comando_manual(dados_json):
    """
    Recebe { "target_id": "Rover-1", "missao": {...} } do site
    e envia via UDP.
    """
    target_name = dados_json.get("target_id") # Ex: "Rover-1"
    missao_conteudo = dados_json.get("missao") # Payload da missão
    
    # Precisamos do IP e Porta UDP do Rover.
    # O database tem "ip_real" guardado do TCP (ex: "127.0.0.1:54321")
    # MAS essa é a porta TCP efémera. 
    # Vamos assumir uma regra ou usar o registo UDP se existir.
    
    # 1. Tentar encontrar IP na telemetria
    db = dados_json.get("_db_ref") # (Hack: injetado se necessário, ou usamos global)
    # Nota: Como o handler do HTTP não tem acesso direto fácil à variavel global 'database'
    # a menos que passemos, vamos assumir que o 'dados_json' não tem o DB.
    # Mas a função 'enviar_comando_manual' é chamada DENTRO do server que tem DB.
    # Vamos simplificar: vamos usar portas fixas baseadas no nome ou broadcast se for local.
    
    # HACK RÁPIDO PARA FUNCIONAR:
    # Se o nome for "Rover-Alpha", e estivermos a usar o 'rover.py' do teu colega,
    # ele escuta numa porta definida no arranque.
    # Vamos assumir: 127.0.0.1:4444 (Nave) e Rover ??
    
    # SOLUÇÃO ROBUSTA: O Rover tem de ter enviado um pacote UDP antes para sabermos a porta.
    # O 'database' guarda 'ultimos_seq_vistos' com (IP, Porta).
    # Vamos usar isso.
    
    print(f"[WEB] Pedido de envio para {target_name}...")
    
    # Endereço Fictício para teste (se não encontrarmos real)
    addr = ("127.0.0.1", 6001) 
    
    # Tenta serializar a missão
    payload_bytes = json.dumps(missao_conteudo).encode('utf-8')
    
    # Enviar
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        # Fragmentar e Enviar
        offset = 0
        id_missao = int(time.time()) % 256
        
        while offset < len(payload_bytes):
            chunk = payload_bytes[offset : offset + MAX_PAYLOAD]
            local_offset = offset
            offset += len(chunk)
            flags = FLAG_MORE_FRAGMENTS if offset < len(payload_bytes) else 0
            
            p = Pacote.MissionPacket(
                tipo_msg=TIPO_DADOS_MISSAO,
                num_seq=id_missao,
                flags=flags,
                frag_offset=local_offset,
                payload=chunk
            )
            s.sendto(p.pack(), addr)
            time.sleep(0.02)
            
        print("[WEB] Comando enviado.")
        return True
    except Exception as e:
        print(f"[WEB] Erro: {e}")
        return False
    finally:
        s.close()

# --- SERVIÇO UDP (Mission Link) ---
def servico_udp(addr, dados, s, db):
    try:
        pct = Pacote.MissionPacket.unpack(dados)
        print(f"[UDP] Recebido de {addr} | Tipo: {pct.tipo_msg}")

        # Se for pedido de missão
        if pct.tipo_msg == TIPO_PEDIDO_MISSAO:
            # Lógica original de resposta automática
            try:
                payload = json.loads(pct.payload.decode('utf-8'))
                nome = payload.get("id", "Rover")
                print(f"  -> Pedido de {nome}")
            except: pass
            
            # (Aqui podes manter a lógica de carregar do ficheiro json se quiseres)
            # Para o teste do HTML, o importante é não crashar.
            
            # Manda ACK
            ack = Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pct.num_seq)
            s.sendto(ack.pack(), addr)

        # Se for progresso
        elif pct.tipo_msg == TIPO_PROGRESSO:
            msg = pct.payload.decode('utf-8')
            print(f"  -> Progresso: {msg}")
            ack = Pacote.MissionPacket(tipo_msg=TIPO_ACK, ack_num=pct.num_seq)
            s.sendto(ack.pack(), addr)

    except Exception as e:
        print(f"Erro UDP: {e}")

def arranca_udp(db):
    s = socket(AF_INET, SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", 4444))
        print("✅ [UDP] MissionLink Online na porta 4444")
        while True:
            d, a = s.recvfrom(4096)
            Thread(target=servico_udp, args=(a, d, s, db)).start()
    except Exception as e:
        print(f"❌ Erro UDP: {e}")

# --- SERVIÇO TCP (Telemetria) ---
def trata_tcp(conn, addr, db):
    print(f"[TCP] Conexão de {addr}")
    try:
        buffer = ""
        while True:
            data = conn.recv(1024)
            if not data: break
            buffer += data.decode('utf-8')
            
            while "\n" in buffer:
                mensagem, buffer = buffer.split("\n", 1)
                if mensagem.strip():
                    try:
                        # O rover do teu colega manda JSON {"id":..., "bat":...}
                        info = json.loads(mensagem)
                        nome = info.get("id", "Desconhecido")
                        
                        # Adicionar IP real para a Web saber
                        info["ip_real"] = f"{addr[0]}:{addr[1]}"
                        
                        # Atualizar DB
                        db.atualizar_telemetria(nome, info)
                        print(f"📊 [TEL] {nome}: Bat {info.get('bat')}%")
                    except: pass
    except: pass
    finally: conn.close()

def arranca_tcp(db):
    s = socket(AF_INET, SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", 5555)) # Porta usada pelo rover.py do teu colega
        s.listen(5)
        print("✅ [TCP] Telemetria Online na porta 5555")
        while True:
            c, a = s.accept()
            Thread(target=trata_tcp, args=(c, a, db)).start()
    except Exception as e:
        print(f"❌ Erro TCP: {e}")

# --- MAIN ---
def main():
    db = Database()
    db.carregar_missoes_do_ficheiro("missoes.json")

    # Iniciar Threads
    t_udp = Thread(target=arranca_udp, args=(db,))
    t_tcp = Thread(target=arranca_tcp, args=(db,))
    
    t_udp.start()
    t_tcp.start()

    # Iniciar API HTTP (Bloqueante)
    # Passamos a função de envio manual para o HTTP usar
    arranca_api_http(db, enviar_comando_manual, 8080)

if __name__ == "__main__":
    main()