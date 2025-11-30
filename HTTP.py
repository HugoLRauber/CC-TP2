from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class APIHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        if not hasattr(self.server, 'database'):
            self._set_headers(500); return

        dados_completos = self.server.database.get_estado_completo()

        if self.path == '/api/global':
            self._set_headers(200)
            self.wfile.write(json.dumps(dados_completos).encode('utf-8'))
        
        elif self.path == '/api/telemetria':
            self._set_headers(200)
            # Retorna o dicionário "telemetria" que criámos no database.py
            self.wfile.write(json.dumps(dados_completos.get("telemetria", {})).encode('utf-8'))
            
        elif self.path == '/api/rovers_lista':
            self._set_headers(200)
            # Gera lista baseada na telemetria ativa ou config
            lista = []
            frota = dados_completos.get("frota", {})
            for rid, info in frota.items():
                lista.append({"id": rid, "nome": info.get("nome", f"Rover-{rid}")})
            self.wfile.write(json.dumps(lista).encode('utf-8'))
        else:
            self._set_headers(404)

    def do_POST(self):
        if self.path == '/api/enviar_missao':
            try:
                length = int(self.headers.get('content-length'))
                body = self.rfile.read(length)
                message = json.loads(body)
                
                # Injeta DB
                message["_db_ref"] = self.server.database
                
                if hasattr(self.server, 'funcao_envio'):
                    sucesso = self.server.funcao_envio(message)
                    if sucesso:
                        self._set_headers(200)
                        self.wfile.write(json.dumps({"status": "Enviado"}).encode('utf-8'))
                    else:
                        self._set_headers(400)
                        self.wfile.write(json.dumps({"erro": "Falha envio"}).encode('utf-8'))
            except Exception as e:
                print(f"Erro POST: {e}")
                self._set_headers(400)

    def log_message(self, format, *args): pass

def arranca_api_http(database, rovers_registados, funcao_envio_manual, porta=8080):
    try:
        server = HTTPServer(('0.0.0.0', porta), APIHandler)
        server.database = database
        server.rovers_registados = rovers_registados 
        server.funcao_envio = funcao_envio_manual
        print(f"✅ API Web (REST) a escutar na porta {porta}")
        server.serve_forever()
    except OSError as e:
        print(f"[HTTP] Erro porta {porta}: {e}")