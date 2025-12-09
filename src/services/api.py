from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import os

# Adiciona a pasta pai (src) ao caminho para garantir imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tenta importar a função de envio do UDP de forma segura
try:
    from services.udp import enviar_comando_manual
except ImportError:
    try:
        from .udp import enviar_comando_manual
    except ImportError:
        print(" ERRO: Não foi possível importar 'udp.py' no api.py")
        # Função dummy para não crashar
        def enviar_comando_manual(*args): return False

class APIHandler(BaseHTTPRequestHandler):

    # --- CABEÇALHOS CORS (Obrigatório para o HTML funcionar) ---
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        # O '*' permite que o HTML local (file://) aceda ao servidor
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        # Verifica se a base de dados foi injetada corretamente
        if not hasattr(self.server, 'database'):
            self._set_headers(500)
            return

        db = self.server.database

        try:
            if self.path == '/api/global':
                self._set_headers(200)
                # Obtém o estado completo
                dados = db.get_estado_completo()
                self.wfile.write(json.dumps(dados).encode('utf-8'))

            elif self.path == '/api/telemetria':
                self._set_headers(200)
                dados = db.get_estado_completo().get("telemetria", {})
                self.wfile.write(json.dumps(dados).encode('utf-8'))

            elif self.path == '/api/rovers_lista':
                self._set_headers(200)
                lista = []
                frota = db.get_estado_completo().get("frota", {})
                for rid, info in frota.items():
                    nome = info.get("nome", f"Rover-{rid}")
                    lista.append({"id": rid, "nome": nome})
                self.wfile.write(json.dumps(lista).encode('utf-8'))

            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"erro": "Endpoint nao encontrado"}).encode('utf-8'))
        except Exception as e:
            print(f" Erro API GET: {e}")

    def do_POST(self):
        if self.path == '/api/enviar_missao':
            try:
                length = int(self.headers.get('content-length', 0))
                body = json.loads(self.rfile.read(length))
                db = self.server.database

                sucesso = False
                if body.get("acao") == "CHARGE":
                    sucesso = enviar_comando_manual(db, body.get("target_id"), "CMD:CHARGE")
                elif body.get("acao") == "MISSAO":
                    sucesso = enviar_comando_manual(db, body.get("target_id"), json.dumps(body.get("missao")))

                self._set_headers(200 if sucesso else 400)
                self.wfile.write(json.dumps({"status": "ok" if sucesso else "erro"}).encode('utf-8'))
            except Exception as e:
                print(f"❌ Erro API POST: {e}")
                self._set_headers(400)

    # Remove logs chatos do terminal
    def log_message(self, format, *args): pass

def start_http_service(database, porta=8080):
    try:
        server = ThreadingHTTPServer(('0.0.0.0', porta), APIHandler)
        server.database = database
        print(f" [API] Servidor HTTP Online na porta {porta}")
        server.serve_forever()
    except Exception as e:
        print(f" CRÍTICO: Não foi possível iniciar a API na porta {porta}: {e}")
