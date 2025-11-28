from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class APIHandler(BaseHTTPRequestHandler):

    def _set_headers(self, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # CORS para browsers
        self.end_headers()

    def do_GET(self):
        """
        Gere os pedidos HTTP (GET) com base no Endpoint (Path).
        """
        # Obter acesso seguro aos dados da thread principal
        if hasattr(self.server, 'database'):
            dados_completos = self.server.database.get_estado_completo()
        else:
            self._set_headers(500)
            self.wfile.write(json.dumps({"erro": "Database nao ligada"}).encode('utf-8'))
            return

        # --- ROUTING (DEFINIÇÃO DE ENDPOINTS) ---

        # Endpoint 1: Estado Global (Dashboard Completo)
        if self.path == '/api/global':
            self._set_headers(200)
            self.wfile.write(json.dumps(dados_completos).encode('utf-8'))

        # Endpoint 2: Apenas Telemetria (Lista de Rovers)
        elif self.path == '/api/telemetria':
            self._set_headers(200)
            subset = dados_completos.get("telemetria", {})
            self.wfile.write(json.dumps(subset).encode('utf-8'))

        # Endpoint 3: Apenas Histórico de Missões
        elif self.path == '/api/missoes':
            self._set_headers(200)
            subset = {
                "concluidas": dados_completos.get("missoes_concluidas", {}),
                "historico_log": dados_completos.get("historico", [])
            }
            self.wfile.write(json.dumps(subset).encode('utf-8'))

        # Endpoint Raiz (Ajuda)
        elif self.path == '/':
            self._set_headers(200)
            ajuda = {
                "mensagem": "API de Observacao Nave-Mae Online",
                "endpoints_disponiveis": [
                    "/api/global",
                    "/api/telemetria",
                    "/api/missoes"
                ]
            }
            self.wfile.write(json.dumps(ajuda).encode('utf-8'))

        # 404 Not Found
        else:
            self._set_headers(404)
            erro = {"erro": "Endpoint nao encontrado", "path": self.path}
            self.wfile.write(json.dumps(erro).encode('utf-8'))

    # Desligar logs automáticos no terminal da Nave-Mãe
    def log_message(self, format, *args):
        pass

def arranca_api_http(database, porta=8080):
    try:
        server = HTTPServer(('0.0.0.0', porta), APIHandler)
        # Injeção de dependência da Database no Servidor
        server.database = database
        print(f"API de Observação (REST) a escutar na porta {porta}")
        print(f" > Endpoint principal: http://127.0.0.1:{porta}/api/global")
        server.serve_forever()
    except OSError as e:
        print(f"[HTTP] Erro porta {porta}: {e}")