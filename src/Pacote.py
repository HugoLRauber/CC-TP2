import struct

# Constantes
TIPO_PEDIDO_MISSAO = 1
TIPO_DADOS_MISSAO = 2
TIPO_ACK = 3
TIPO_PROGRESSO = 4
FLAG_MORE_FRAGMENTS = 1

# !BHHBHH = 1 Byte Tipo, 2 Bytes Seq, 2 Bytes Ack, 1 Byte Flags, 2 Bytes Offset, 2 Bytes Tamanho
FORMATO_CABECALHO = "!BHHBHH"
TAMANHO_CABECALHO = struct.calcsize(FORMATO_CABECALHO)

class MissionPacket:
    def __init__(self, tipo_msg=0, num_seq=0, ack_num=0, flags=0, frag_offset=0, payload=b''):
        self.tipo_msg = tipo_msg
        self.num_seq = num_seq
        self.ack_num = ack_num
        self.flags = flags
        self.frag_offset = frag_offset
        self.payload = payload

    def pack(self):
        tamanho_payload = len(self.payload)
        if tamanho_payload > 1400: 
            raise ValueError("Payload muito grande para UDP!")

        cabecalho = struct.pack(
            FORMATO_CABECALHO,
            self.tipo_msg,
            self.num_seq,
            self.ack_num,
            self.flags,
            self.frag_offset,
            tamanho_payload
        )
        return cabecalho + self.payload

    @classmethod
    def unpack(cls, dados_bytes):
        if len(dados_bytes) < TAMANHO_CABECALHO:
            raise ValueError("Pacote incompleto")

        cabecalho_bytes = dados_bytes[:TAMANHO_CABECALHO]
        tipo_msg, num_seq, ack_num, flags, frag_offset, tamanho_payload = struct.unpack(
            FORMATO_CABECALHO, cabecalho_bytes
        )

        payload = dados_bytes[TAMANHO_CABECALHO : TAMANHO_CABECALHO + tamanho_payload]
        return cls(tipo_msg, num_seq, ack_num, flags, frag_offset, payload)