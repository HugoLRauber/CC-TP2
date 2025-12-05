from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

class APIHandler(BaseHTTPRequestHandler):

    # --- CABEÇALHOS CORS (Essencial para o HTML funcionar) ---
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
            self._set_headers(500)
            self.wfile.write(json.dumps({"erro": "Database offline"}).encode('utf-8'))
            return

        # Roteamento
        if self.path == '/api/global':
            self._set_headers(200)
            # Agora chama a versão que limpa rovers inativos automaticamente
            dados = self.server.database.get_estado_completo()
            self.wfile.write(json.dumps(dados).encode('utf-8'))
        
        elif self.path == '/api/telemetria':
            self._set_headers(200)
            dados = self.server.database.get_estado_completo()
            self.wfile.write(json.dumps(dados.get("telemetria", {})).encode('utf-8'))
            
        elif self.path == '/api/rovers_lista':
            self._set_headers(200)
            # Retorna apenas rovers ativos/configurados para o dropdown
            dados = self.server.database.get_estado_completo()
            frota = dados.get("frota", {})
            lista = []
            
            for rid, info in frota.items():
                # Só mostra no dropdown se estiver Online ou Idle (opcional)
                status = info.get("status", "OFFLINE")
                nome = info.get("nome", f"Rover-{rid}")
                lista.append({"id": rid, "nome": nome, "status": status})
                
            self.wfile.write(json.dumps(lista).encode('utf-8'))
        
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"erro": "Endpoint nao encontrado"}).encode('utf-8'))

    # --- ENVIO DE COMANDOS (POST) ---
    def do_POST(self):
        if self.path == '/api/enviar_missao':
            try:
                # Ler tamanho e corpo
                content_len = self.headers.get('content-length')
                if not content_len:
                    raise ValueError("Falta Content-Length")
                    
                length = int(content_len)
                body = self.rfile.read(length)
                message = json.loads(body)
                
                # Injeta referência da DB para a função de envio usar, se necessário
                message["_db_ref"] = self.server.database
                
                # Executa a função de envio da Nave Mãe (injetada no arranque)
                if hasattr(self.server, 'funcao_envio'):
                    sucesso = self.server.funcao_envio(message)
                    
                    if sucesso:
                        self._set_headers(200)
                        self.wfile.write(json.dumps({"status": "Enviado com sucesso"}).encode('utf-8'))
                    else:
                        self._set_headers(400)
                        self.wfile.write(json.dumps({"erro": "Falha ao enviar (Rover desconhecido ou ocupado)"}).encode('utf-8'))
                else:
                    self._set_headers(500)
                    self.wfile.write(json.dumps({"erro": "Funcao de envio nao configurada"}).encode('utf-8'))
                    
            except Exception as e:
                print(f"[API ERROR] POST falhou: {e}")
                self._set_headers(400)
                self.wfile.write(json.dumps({"erro": str(e)}).encode('utf-8'))
        else:
            self._set_headers(404)

    # Silenciar logs de cada pedido para não poluir o terminal da Nave
    def log_message(self, format, *args):
        pass

def arranca_api_http(database, rovers_registados, funcao_envio_manual, porta=8080):
    try:
        # AQUI ESTÁ A GRANDE MUDANÇA: ThreadingHTTPServer
        # Permite tratar múltiplos pedidos HTML/JSON ao mesmo tempo sem bloquear
        server = ThreadingHTTPServer(('0.0.0.0', porta), APIHandler)
        
        server.database = database
        server.rovers_registados = rovers_registados 
        server.funcao_envio = funcao_envio_manual
        
        print(f"✅ API Web (Multi-Threaded) a escutar na porta {porta}")
        server.serve_forever()
    except OSError as e:
        print(f"[HTTP] Erro crítico na porta {porta}: {e}")