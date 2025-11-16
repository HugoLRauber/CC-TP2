import struct

TIPO_PEDIDO_MISSAO = 1
TIPO_DADOS_MISSAO = 2
TIPO_ACK = 3
TIPO_PROGRESSO = 4
FLAG_MORE_FRAGMENTS = 1

FORMATO_CABECALHO = "!BBBBBB"
TAMANHO_CABECALHO = struct.calcsize(FORMATO_CABECALHO)

class MissionPacket:
    def __init__(self,  tipo_msg=0, num_seq=0, ack_num = 0, flags=0, frag_offset=0, payload=b''):
        self.tipo_msg = tipo_msg
        self.num_seq = num_seq
        self.ack_num = ack_num
        self.flags = flags
        self.frag_offset = frag_offset
        self.payload = payload


    def pack(self):
        tamanho_payload = len(self.payload)

        if tamanho_payload > 255:
            raise ValueError("Payload excede os 255 bytes!")

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

    # 3. Atualizar o unpack
    @classmethod
    def unpack(cls, dados_bytes):
        cabecalho_bytes = dados_bytes[:TAMANHO_CABECALHO]

        tipo_msg, num_seq, ack_num, flags, frag_offset, tamanho_payload = struct.unpack(
            FORMATO_CABECALHO,
            cabecalho_bytes
        )

        inicio_payload = TAMANHO_CABECALHO
        fim_payload = inicio_payload + tamanho_payload
        payload = dados_bytes[inicio_payload:fim_payload]

        return cls(tipo_msg, num_seq, ack_num, flags, frag_offset, payload)

    # 4. (Opcional) Funções 'helper' para as flags
    def has_more_fragments(self):
        # Verifica se o bit de "more fragments" está ativo
        return (self.flags & FLAG_MORE_FRAGMENTS) == FLAG_MORE_FRAGMENTS