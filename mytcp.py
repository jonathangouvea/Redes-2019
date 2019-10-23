import asyncio
import random
import os
from mytcputils import *

payload_global = b''
seq_no_global = 0
ack_no_global = 0
ack_rand = 0

class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que uma nova conexão for aceita
        """
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)
        global payload_global
        global seq_no_global
        global ack_no_global
        global ack_rand
        if dst_port != self.porta:
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)

        if (flags & FLAGS_SYN) == FLAGS_SYN:
            # A flag SYN estar setada significa que é um cliente tentando estabelecer uma conexão nova
            # TODO: talvez você precise passar mais coisas para o construtor de conexão
            payload_global = b''
            ack_no_global = seq_no + 1
            seq_no_global = seq_no + 1
            seq_no_rand = random.randint(0, 0xffff)
            ack_rand = seq_no_rand + 1
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao)
            make_header(dst_port, src_port, seq_no_rand, seq_no+1, FLAGS_ACK|FLAGS_SYN)
            self.rede.enviar(fix_checksum(make_header(dst_port, src_port, seq_no_rand, seq_no+1, FLAGS_ACK|FLAGS_SYN), dst_addr, src_addr), src_addr)
            # TODO: você precisa fazer o handshake aceitando a conexão. Escolha se você acha melhor
            # fazer aqui mesmo ou dentro da classe Conexao.
            if self.callback:
                self.callback(conexao)
        elif id_conexao in self.conexoes:
            # Passa para a conexão adequada se ela já estiver estabelecida
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))


class Conexao:
    def __init__(self, servidor, id_conexao):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        self.timer = asyncio.get_event_loop().call_later(1, self._exemplo_timer)  # um timer pode ser criado assim; esta linha é só um exemplo e pode ser removida
        #self.timer.cancel()   # é possível cancelar o timer chamando esse método; esta linha é só um exemplo e pode ser removida

    def _exemplo_timer(self):
        # Esta função é só um exemplo e pode ser removida
        print('Este é um exemplo de como fazer um timer')

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        # TODO: trate aqui o recebimento de segmentos provenientes da camada de rede.
        # Chame self.callback(self, dados) para passar dados para a camada de aplicação após
        # garantir que eles não sejam duplicados e que tenham sido recebidos em ordem.
        global payload_global
        global seq_no_global
        global ack_no_global

        src_addr = self.id_conexao[0]
        src_port = self.id_conexao[1]
        dst_addr = self.id_conexao[2]
        dst_port = self.id_conexao[3]
        if len(payload) == 0:
            if (flags & FLAGS_FIN) == FLAGS_FIN:
                self.servidor.rede.enviar(fix_checksum(make_header(dst_port, src_port, seq_no, ack_no_global+1, FLAGS_ACK|FLAGS_SYN), dst_addr, src_addr), src_addr)
                self.callback(self, payload)
            else:
                self.callback(self, payload)
            #print("payload vazio")
        elif seq_no == seq_no_global + len(payload_global):
            payload_global = payload
            seq_no_global = seq_no
            ack_no_global = ack_no_global + len(payload_global)
            self.servidor.rede.enviar(fix_checksum(make_header(dst_port, src_port, seq_no, ack_no_global, FLAGS_ACK|FLAGS_SYN), dst_addr, src_addr), src_addr)
            self.callback(self, payload)



    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    def enviar(self, dados):
        """
        Usado pela camada de aplicação para enviar dados
        """
        global payload_global
        global seq_no_global
        global ack_rand

        src_addr = self.id_conexao[0]
        src_port = self.id_conexao[1]
        dst_addr = self.id_conexao[2]
        dst_port = self.id_conexao[3]

        i = int(len(dados) / MSS)      
        print(i)
        if(i == 1):
            self.servidor.rede.enviar(fix_checksum(make_header(dst_port, src_port, ack_rand, seq_no_global, FLAGS_ACK) + dados, dst_addr, src_addr), src_addr)
        if(i > 1):
            for k in range(i):
                ack_rand = ack_rand+MSS
                self.servidor.rede.enviar(fix_checksum(make_header(dst_port, src_port, ack_rand, seq_no_global+11, FLAGS_ACK) + dados[k*1460:(k+1)*1460], dst_addr, src_addr), src_addr)
        # TODO: implemente aqui o envio de dados.
        # Chame self.servidor.rede.enviar(segmento, dest_addr) para enviar o segmento
        # que você construir para a camada de rede.
        pass

    def fechar(self):
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        global payload_global
        global seq_no_global
        global ack_no_global
        global ack_rand

        src_addr = self.id_conexao[0]
        src_port = self.id_conexao[1]
        dst_addr = self.id_conexao[2]
        dst_port = self.id_conexao[3]
        
        print(seq_no_global)
        print(ack_rand)
        print(len(payload_global))
        self.servidor.rede.enviar(fix_checksum(make_header(dst_port, src_port, ack_rand, ack_rand, FLAGS_FIN), dst_addr, src_addr), src_addr)
        # TODO: implemente aqui o fechamento de conexão
        pass
