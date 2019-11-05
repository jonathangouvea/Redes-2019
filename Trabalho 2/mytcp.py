import asyncio
from mytcputils import *
import random
import time

class Servidor:
    def __init__(self, rede, porta):
        self.rede = rede
        self.porta = porta
        self.conexoes = {}
        self.callback = None
        self.rede.registrar_recebedor(self._rdt_rcv)
        
        #self.servidor = CamadaRedeLinux()

    def registrar_monitor_de_conexoes_aceitas(self, callback):
        self.callback = callback

    def _rdt_rcv(self, src_addr, dst_addr, segment):
        src_port, dst_port, seq_no, ack_no, \
            flags, window_size, checksum, urg_ptr = read_header(segment)

        if dst_port != self.porta:
            # Ignora segmentos que não são destinados à porta do nosso servidor
            return

        payload = segment[4*(flags>>12):]
        id_conexao = (src_addr, src_port, dst_addr, dst_port)
        
        if (flags & FLAGS_SYN) == FLAGS_SYN:
            aleatorio = random.randint(0, 0xffff)        
            flag_ack = (FLAGS_SYN|FLAGS_ACK)
            
            conexao = self.conexoes[id_conexao] = Conexao(self, id_conexao, aleatorio, seq_no + 1)
            
            self.rede.enviar(fix_checksum(make_header(dst_port, src_port, aleatorio, seq_no + 1, flag_ack), dst_addr, src_addr), src_addr)
            if self.callback:
                self.callback(conexao)
        elif id_conexao in self.conexoes:
            self.conexoes[id_conexao]._rdt_rcv(seq_no, ack_no, flags, payload)
            if (flags & FLAGS_FIN) == FLAGS_FIN:
                self.conexoes.pop(id_conexao)
        else:
            print('%s:%d -> %s:%d (pacote associado a conexão desconhecida)' %
                  (src_addr, src_port, dst_addr, dst_port))


class Conexao:
    def __init__(self, servidor, id_conexao, seq_no, ack_no):
        self.servidor = servidor
        self.id_conexao = id_conexao
        self.callback = None
        
        self.timeout = 2
        self.seq_no = seq_no
        self.ack_no = ack_no
        self.send_base = seq_no
        
        self.recebidos = []
        
        self.SampleRTT = 0.3
        self.EstimatedRTT = None
        self.DevRTT = None
        
        self.tempoEnvio = 0
        self.tempoRecebido = 0
        
        self.timer = None
        self.retransmitiu = False
        
        self.janela = 1
        
    def _retransmitir(self):
        #print("@@@ RETRANSMITIDO SEND_BASE {0} ACK_NO {1}".format(self.send_base, self.ack_no))
        
        self.fix_header(self.send_base, self.ack_no, flags=FLAGS_ACK, dados = self.recebidos[0][0])
        
        #self.servidor.rede.enviar(self.recebidos[0], self.id_conexao[0])
        self.timer = asyncio.get_event_loop().call_later(self.timeout, self._retransmitir)
        self.retransmitiu = True
        self.janela /= 2
        
    def simple_header(self, seq_no, ack_no, dados, flags):
        return fix_checksum(make_header(self.id_conexao[3], self.id_conexao[1], seq_no, ack_no, flags) + dados, self.id_conexao[2], self.id_conexao[0])
        
    def fix_header(self, seq_no, ack_no, dados=b'', flags=FLAGS_ACK):
        self.servidor.rede.enviar(self.simple_header(seq_no, ack_no, dados, flags), self.id_conexao[0])

    def _rdt_rcv(self, seq_no, ack_no, flags, payload):
        #print(">>> LOCAL:\t SEQ_NO {0} ACK_NO {1} LEN_RECEBIDOS {5}\t GLOBAL:\t SEQ_NO {2} ACK_NO {3} SEND_BASE {4}".format(seq_no, ack_no, self.seq_no, self.ack_no, self.send_base, len(self.recebidos)))
    
        if seq_no == self.ack_no:
        
            if self.tempoEnvio > 0:
                if self.timer:
                    self.timer.cancel()
                    self.timer = None
                
                if not self.retransmitiu:
                    self.tempoRecebido = time.time()
                    self.SampleRTT = self.tempoRecebido - self.tempoEnvio
                    if self.EstimatedRTT:
                        self.calcTimeoutInterval()
                    else:
                        self.calcTimeoutInicial()
                    
                print("TIMEOUT {0:.3f} S {1:.3f} E {2:.3f} D {3:.3f}".format(self.timeout,self.SampleRTT, self.EstimatedRTT, self.DevRTT))
        
            if ack_no > self.send_base:
                #print("!!! SEND_BASE atualizada! {0} -> {1}".format(self.send_base, ack_no))
                i = 0
                for r in self.recebidos:
                    if r[1] < ack_no:
                        i += 1
                        
                self.recebidos = self.recebidos[i:]
                #print("!!! RECEBIDOS cortado em {0}".format(i))
                
                self.send_base = ack_no
                if len(self.recebidos) > 0:
                    if not self.timer:
                        self.timer = asyncio.get_event_loop().call_later(self.timeout, self._retransmitir)
                else:
                    if self.timer:
                        self.timer.cancel()
                        self.timer = None
        
            self.retransmitiu = False
            self.ack_no += len(payload)
            
            if len(payload) == 0:
                if (flags & FLAGS_FIN) == FLAGS_FIN:
                    self.ack_no = self.ack_no + 1
                    self.fix_header(self.seq_no, self.ack_no, flags = FLAGS_ACK|FLAGS_FIN)
            else:
                self.janela += 1
                self.fix_header(self.seq_no, self.ack_no, flags = FLAGS_ACK)
            
            self.callback(self, payload)
        
        
            
        #print('recebido payload: %r' % payload)


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
        tam = int(len(dados)/MSS)

        for i in range(tam):
            self.seq_no += MSS
            
            self.fix_header(self.seq_no - MSS + 1, self.ack_no, flags=flags, dados = dados[i*MSS:(i+1)*MSS])
            self.recebidos.append([dados[i*MSS:(i+1)*MSS], self.seq_no - MSS + 1])
            
            if not self.timer:
                self.tempoEnvio = time.time()
                self.timer = asyncio.get_event_loop().call_later(self.timeout, self._retransmitir)

    def fechar(self):
        #self.enviar(b'', flags=FLAGS_FIN)
        self.fix_header(self.seq_no + 1, self.ack_no, flags=FLAGS_FIN, dados = b'')
        """
        Usado pela camada de aplicação para fechar a conexão
        """
        pass
        
    def calcTimeoutInicial(self):
        self.EstimatedRTT = self.SampleRTT
        self.DevRTT = self.SampleRTT/2
        self.timeout = self.EstimatedRTT + self.DevRTT*4
       
    def calcTimeoutInterval(self):
        self.EstimatedRTT = (1 - 0.125)*(self.EstimatedRTT) + (0.125)*self.SampleRTT
        self.DevRTT = (1 - 0.25)*self.DevRTT + 0.25*abs(self.SampleRTT - self.EstimatedRTT)
        self.timeout = self.EstimatedRTT + self.DevRTT*4
