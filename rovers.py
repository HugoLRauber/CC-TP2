from socket import *
import sys
import Pacote
from TP2.Pacote import TIPO_PEDIDO_MISSAO

def main():
    s : socket = socket(AF_INET, SOCK_DGRAM)
    #s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

    if len(sys.argv) == 4:
        endereco : str = sys.argv[1]
        porta : int = int(sys.argv[2])
        mensagem : str = sys.argv[3]
    else:
        print("numero de argumento invalido")
        exit(1)

    print(f"Vou enviar mensagem para {endereco}:{porta}")
    s.sendto(mensagem.encode('utf-8'), (endereco,porta))

    dados, addr = s.recvfrom(1000)
    print(f"Recebi uma mensagem do {addr}: {dados.decode('utf-8')}")
    
    s.close()

    payload_pedido = "QUERO_MISSAO".encode('utf-8')

    pacote_pedido = Pacote.MissionPacket(
        num_seq = 1,
        tipo_msg = TIPO_PEDIDO_MISSAO,
        payload = payload_pedido
    )

    bytes_rede = pacote_pedido.pack()
    s.sendto(bytes_rede, (endereco, porta))

if __name__ == "__main__":
    main()