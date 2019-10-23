import asyncio
from mytcputils import *
import random

g_payload = b''
g_ack_no = 0
g_seq_no = 0
g_ack_rand = 0

class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)
        
        #self.servidor = CamadaRedeLinux()

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que uma nova conexão for aceita
        """
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)
            
        global g_payload
        global g_ack_no
        global g_seq_no
        global g_ack_rand

        if dst_port != self.porta:
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)
        
        if (flags & FLAGS_SYN) == FLAGS_SYN:
            g_payload = b''
            g_ack_no = seq_no + 1
            g_seq_no = g_ack_no
            num_random = random.randint(0, 0xffff)
            g_ack_rand = num_random + 1
        
        
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao)
            flag_ack = (FLAGS_SYN|FLAGS_ACK)
            self.rede.enviar(fix_checksum(make_header(dst_port, src_port, num_random, g_ack_no, flag_ack), dst_addr, src_addr), src_addr)
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
        global g_payload
        global g_ack_no
        global g_seq_no
    
        if len(payload) == 0:
            if (flags & FLAGS_FIN) == FLAGS_FIN:
                self.servidor.rede.enviar(fix_checksum(make_header(self.id_conexao[3], self.id_conexao[1], seq_no, g_ack_no+1, FLAGS_ACK|FLAGS_SYN), self.id_conexao[2], self.id_conexao[0]), self.id_conexao[0])
                #self.enviar(b'', flags=FLAGS_ACK|FLAGS_SYN)
                self.callback(self, payload)
            else:
                self.callback(self, payload)
    
        elif seq_no == g_seq_no + len(g_payload):
            g_payload = payload
            g_seq_no = seq_no
            g_ack_no += len(g_payload)
            
            self.servidor.rede.enviar(fix_checksum(make_header(self.id_conexao[3], self.id_conexao[1], seq_no, g_ack_no, FLAGS_ACK|FLAGS_SYN), self.id_conexao[2], self.id_conexao[0]), self.id_conexao[0])
            #self.enviar(b'', flags=FLAGS_ACK|FLAGS_SYN)
            self.callback(self, payload)
            
        # TODO: trate aqui o recebimento de segmentos provenientes da camada de rede.
        # Chame self.callback(self, dados) para passar dados para a camada de aplicação após
        # garantir que eles não sejam duplicados e que tenham sido recebidos em ordem.
        print('recebido payload: %r' % payload)

    # Os métodos abaixo fazem parte da API

    def registrar_recebedor(self, callback):
        """
        Usado pela camada de aplicação para registrar uma função para ser chamada
        sempre que dados forem corretamente recebidos
        """
        self.callback = callback

    def enviar(self, dados, flags=FLAGS_ACK):
        """
        Usado pela camada de aplicação para enviar dados
        """
        
        global g_payload
        global g_ack_no
        global g_seq_no
        global g_ack_rand
        
        tam = int(len(dados)/MSS)
        if tam == 0:
            self.servidor.rede.enviar(fix_checksum(make_header(self.id_conexao[3], self.id_conexao[1], g_ack_rand, g_seq_no, flags), self.id_conexao[2], self.id_conexao[0]), self.id_conexao[0])
            
        elif tam == 1:
            self.servidor.rede.enviar(fix_checksum(make_header(self.id_conexao[3], self.id_conexao[1], g_ack_rand, g_seq_no, flags) + dados, self.id_conexao[2], self.id_conexao[0]), self.id_conexao[0])
            
        else:
            for i in range(tam):
                g_ack_rand += MSS
                self.servidor.rede.enviar(fix_checksum(make_header(self.id_conexao[3], self.id_conexao[1], g_ack_rand, g_seq_no + 11, flags) + dados[i*MSS:(i+1)*MSS], self.id_conexao[2], self.id_conexao[0]), self.id_conexao[0])
        # TODO: implemente aqui o envio de dados.
        # Chame self.servidor.rede.enviar(segmento, dest_addr) para enviar o segmento
        # que você construir para a camada de rede.
        pass

    def fechar(self):
        self.enviar(b'', flags=FLAGS_FIN)
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        pass
