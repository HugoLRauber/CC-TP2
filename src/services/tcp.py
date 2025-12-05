import socket
import json
import threading
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def tratar_cliente(conn, addr, database):
    try:
        buffer = ""
        while True:
            data = conn.recv(1024)
            if not data: break
            buffer += data.decode('utf-8')
            while "\n" in buffer:
                msg, buffer = buffer.split("\n", 1)
                if msg.strip():
                    try:
                        js = json.loads(msg)
                        rid = js.get("id")
                        if rid:
                            js["ip_real"] = f"{addr[0]}:{addr[1]}"
                            database.atualizar_telemetria(rid, js)
                            print(f"📊 [TCP] Rover {rid}: {js.get('bat')}%")
                    except: pass
    except: pass
    finally: conn.close()

def start_tcp_service(database):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", 6000))
        s.listen(5)
        print("✅ [TCP] TelemetryStream Online (Porta 6000)")
        while True:
            c, a = s.accept()
            threading.Thread(target=tratar_cliente, args=(c, a, database)).start()
    except Exception as e: print(f"❌ Falha TCP: {e}")