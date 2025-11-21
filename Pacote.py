import struct

# Tipos de Mensagem
TIPO_PEDIDO_MISSAO = 1
TIPO_DADOS_MISSAO = 2
TIPO_ACK = 3
TIPO_PROGRESSO = 4
FLAG_MORE_FRAGMENTS = 1

# Formato: !BBBBHH (8 bytes total)
# B=Tipo, B=Seq, B=Ack, B=Flags, H=Offset(2B), H=Tamanho(2B)
FORMATO_CABECALHO = "!BBBBHH"
TAMANHO_CABECALHO = struct.calcsize(FORMATO_CABECALHO)

class MissionPacket:
    def __init__(self, tipo_msg=0, num_seq=0, ack_num=0, flags=0, frag_offset=0, payload=b''):
        self.tipo_msg = tipo_msg
        self.num_seq = num_seq
        self.ack_num = ack_num
        self.flags = flags
        self.frag_offset = frag_offset
        self.payload = payload

        # Limite seguro para payload (H suporta até 65535)
        if len(payload) > 65535:
            raise ValueError(f"Payload excede 65KB ({len(payload)})")

    def pack(self):
        tamanho_payload = len(self.payload)
        # Garantir que campos de 1 byte estão no limite
        if self.num_seq > 255: self.num_seq %= 256
        if self.ack_num > 255: self.ack_num %= 256

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
            raise ValueError("Pacote demasiado pequeno")

        cabecalho_bytes = dados_bytes[:TAMANHO_CABECALHO]

        tipo_msg, num_seq, ack_num, flags, frag_offset, tamanho_payload = struct.unpack(
            FORMATO_CABECALHO,
            cabecalho_bytes
        )

        inicio_payload = TAMANHO_CABECALHO
        fim_payload = inicio_payload + tamanho_payload
        payload = dados_bytes[inicio_payload:fim_payload]

        return cls(tipo_msg, num_seq, ack_num, flags, frag_offset, payload)

    def has_more_fragments(self):
        return (self.flags & FLAG_MORE_FRAGMENTS) == FLAG_MORE_FRAGMENTS