from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class APIHandler(BaseHTTPRequestHandler):

    # --- CABEÇALHOS CORS (Para o HTML funcionar) ---
    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    # --- LEITURA DE DADOS (GET) ---
    def do_GET(self):
        # Verificar se a DB está ligada
        if not hasattr(self.server, 'database'):
            self._set_headers(500); return

        if self.path == '/api/global':
            self._set_headers(200)
            self.wfile.write(json.dumps(self.server.database.get_estado_completo()).encode('utf-8'))
        
        elif self.path == '/api/telemetria':
            self._set_headers(200)
            dados = self.server.database.get_estado_completo()
            self.wfile.write(json.dumps(dados.get("telemetria", {})).encode('utf-8'))
            
        elif self.path == '/api/rovers_lista':
            # Endpoint especial para o dropdown do HTML
            self._set_headers(200)
            telemetria = self.server.database.telemetria_rovers
            lista = []
            # Constrói a lista baseada nos rovers que já enviaram dados
            for nome, info in telemetria.items():
                # Tenta descobrir o IP e Porta
                ip_str = info.get("ip_real", "127.0.0.1:0")
                try:
                    ip, porta = ip_str.split(':')
                    # Assumimos que a porta UDP é próxima da TCP ou fixa
                    # Para simplificar, enviamos o ID/Nome como identificador
                    lista.append({"id": nome, "ip": ip, "porta": porta})
                except: pass
            self.wfile.write(json.dumps(lista).encode('utf-8'))
            
        else:
            self._set_headers(404)

    # --- ENVIO DE COMANDOS (POST) ---
    def do_POST(self):
        if self.path == '/api/enviar_missao':
            try:
                length = int(self.headers.get('content-length'))
                body = self.rfile.read(length)
                message = json.loads(body)
                
                # Executa a função de envio da Nave Mãe
                if hasattr(self.server, 'funcao_envio'):
                    sucesso = self.server.funcao_envio(message) # {target_id: "...", missao: {...}}
                    
                    if sucesso:
                        self._set_headers(200)
                        self.wfile.write(json.dumps({"status": "Enviado"}).encode('utf-8'))
                    else:
                        self._set_headers(400)
                        self.wfile.write(json.dumps({"erro": "Falha ao enviar (Rover desconhecido?)"}).encode('utf-8'))
                else:
                    self._set_headers(500)
            except Exception as e:
                print(f"Erro POST: {e}")
                self._set_headers(400)

    def log_message(self, format, *args):
        pass

def arranca_api_http(database, funcao_envio_manual, porta=8080):
    try:
        server = HTTPServer(('0.0.0.0', porta), APIHandler)
        server.database = database
        server.funcao_envio = funcao_envio_manual
        print(f"✅ API Web (REST) a escutar na porta {porta}")
        server.serve_forever()
    except OSError as e:
        print(f"[HTTP] Erro porta {porta}: {e}")