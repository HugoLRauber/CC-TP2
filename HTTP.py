from http.server import BaseHTTPRequestHandler, HTTPServer
import json

# Classe que define como responder aos pedidos HTTP
class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Configurar cabeçalhos de resposta (200 OK, JSON)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # Opcional: Permite acesso de browsers
        self.end_headers()

        # 2. Aceder à base de dados
        # A database foi "injetada" dentro do objeto server na função arranca_api_http
        if hasattr(self.server, 'database'):
            dados = self.server.database.get_estado_completo()
        else:
            dados = {"erro": "Database nao ligada ao servidor HTTP"}

        # 3. Enviar JSON
        try:
            mensagem = json.dumps(dados)
            self.wfile.write(mensagem.encode('utf-8'))
        except Exception as e:
            print(f"[HTTP] Erro ao enviar resposta: {e}")

    # Desligar logs de acesso padrão para não poluir o terminal da Nave-Mãe
    def log_message(self, format, *args):
        pass

def arranca_api_http(database, porta=8080):
    """
    Inicia o servidor HTTP.
    Recebe a instância da database para partilhar dados.
    """
    try:
        # Criar servidor
        server = HTTPServer(('0.0.0.0', porta), APIHandler)

        # INJEÇÃO DE DEPENDÊNCIA:
        # Guardamos a referência da database dentro do servidor para o Handler usar
        server.database = database

        print(f"API de Observação (HTTP) a escutar na porta {porta}")
        server.serve_forever()

    except OSError as e:
        print(f"[HTTP] Erro crítico ao abrir porta {porta}: {e}")
    except Exception as e:
        print(f"[HTTP] Erro genérico: {e}")