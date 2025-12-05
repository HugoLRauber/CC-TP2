from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from .udp import enviar_comando_manual

class APIHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self): self._set_headers()

    def do_GET(self):
        db = self.server.database
        if self.path == '/api/global':
            self._set_headers(200)
            self.wfile.write(json.dumps(db.get_estado_completo()).encode('utf-8'))
        elif self.path == '/api/telemetria':
            self._set_headers(200)
            self.wfile.write(json.dumps(db.get_estado_completo().get("telemetria", {})).encode('utf-8'))
        elif self.path == '/api/rovers_lista':
            self._set_headers(200)
            lista = []
            frota = db.get_estado_completo().get("frota", {})
            for rid, info in frota.items():
                lista.append({"id": rid, "nome": info.get("nome", f"Rover-{rid}")})
            self.wfile.write(json.dumps(lista).encode('utf-8'))
        else: self._set_headers(404)

    def do_POST(self):
        if self.path == '/api/enviar_missao':
            try:
                l = int(self.headers.get('content-length'))
                body = json.loads(self.rfile.read(l))
                db = self.server.database
                
                # Chama a função do UDP Service
                sucesso = False
                if body.get("acao") == "CHARGE":
                    sucesso = enviar_comando_manual(db, body.get("target_id"), "CMD:CHARGE")
                elif body.get("acao") == "MISSAO":
                    sucesso = enviar_comando_manual(db, body.get("target_id"), json.dumps(body.get("missao")))
                
                self._set_headers(200 if sucesso else 400)
                self.wfile.write(json.dumps({"status": "ok" if sucesso else "erro"}).encode('utf-8'))
            except: self._set_headers(400)

    def log_message(self, f, *a): pass

def start_http_service(database, porta=8080):
    try:
        server = HTTPServer(('0.0.0.0', porta), APIHandler)
        server.database = database
        print(f"✅ [HTTP] API Online (Porta {porta})")
        server.serve_forever()
    except Exception as e: print(f"❌ Falha HTTP: {e}")