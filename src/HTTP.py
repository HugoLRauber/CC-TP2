from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import mimetypes
import sys

# Garante que módulos locais de src são importáveis
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class APIHandler(BaseHTTPRequestHandler):

    # Serve ficheiros estáticos da pasta web (HTML/CSS/JS)
    def _serve_file(self, relative_path):
        # Localiza a pasta 'web' ao lado de 'src'
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, 'web', relative_path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            # Define o MIME adequado (HTML, CSS, JS)
            mime_type, _ = mimetypes.guess_type(file_path)
            self.send_header('Content-type', mime_type or 'application/octet-stream')
            self.send_header('Access-Control-Allow-Origin', '*') 
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, f"Ficheiro nao encontrado: {relative_path}")

    def _set_headers(self, status=200):
        # Cabeçalhos comuns (JSON + CORS)
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    # Gestão de GET: páginas web e endpoints de API
    def do_GET(self):
        # Primeiro, tenta servir páginas HTML
        if self.path == '/' or self.path == '/groundcontrol':
            self._serve_file('groundcontrol.html')
            return
        elif self.path == '/navemae':
            self._serve_file('navemae.html')
            return
        # Servir ficheiros estáticos (.html, .css, .js)
        elif self.path.endswith('.html') or self.path.endswith('.css') or self.path.endswith('.js'):
            self._serve_file(self.path.lstrip('/'))
            return

        # 2. Servir API (Dados)
        if not hasattr(self.server, 'database'):
            self._set_headers(500); return

        if self.path == '/api/global':
            self._set_headers(200)
            self.wfile.write(json.dumps(self.server.database.get_estado_completo()).encode('utf-8'))
        
        elif self.path == '/api/telemetria':
            self._set_headers(200)
            self.wfile.write(json.dumps(self.server.database.get_estado_completo().get("frota", {})).encode('utf-8'))
            
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"erro": "Endpoint nao encontrado"}).encode('utf-8'))

    def do_POST(self):
        if self.path == '/api/enviar_missao':
            try:
                length = int(self.headers.get('content-length'))
                body = json.loads(self.rfile.read(length))
                
                body["_db_ref"] = self.server.database
                if hasattr(self.server, 'funcao_envio'):
                    self.server.funcao_envio(body)
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"status": "OK"}).encode('utf-8'))
                else:
                    self._set_headers(500)
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"erro": str(e)}).encode('utf-8'))

    def log_message(self, format, *args): pass

def arranca_api_http(database, rovers_registados, funcao_envio_manual, porta=8080):
    try:
        server = ThreadingHTTPServer(('0.0.0.0', porta), APIHandler)
        server.database = database
        server.funcao_envio = funcao_envio_manual
        print(f" API Híbrida (HTML+JSON) Online na porta {porta}")
        server.serve_forever()
    except OSError as e:
        print(f"[HTTP] Erro: {e}")
