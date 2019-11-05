from myiputils import *


class CamadaRede:
    def __init__(self, enlace):
        """
        Inicia a camada de rede. Recebe como argumento uma implementação
        de camada de enlace capaz de localizar os next_hop (por exemplo,
        Ethernet com ARP).
        """
        self.callback = None
        self.enlace = enlace
        self.enlace.registrar_recebedor(self.__raw_recv)
        self.meu_endereco = None
        
        self.tabela = []

    def __raw_recv(self, datagrama):
        dscp, ecn, identification, flags, frag_offset, ttl, proto, \
           src_addr, dst_addr, payload = read_ipv4_header(datagrama)
        if dst_addr == self.meu_endereco:
            # atua como host
            if proto == IPPROTO_TCP and self.callback:
                self.callback(src_addr, dst_addr, payload)
        else:
            # atua como roteador
            next_hop = self._next_hop(dst_addr)
            # TODO: Trate corretamente o campo TTL do datagrama
            self.enlace.enviar(datagrama, next_hop)

    def _calc_dif(self, tabela, dest):
        calculo = []
        for t in tabela:
            ind = 0
            for i in range(len(t)):
                if t[i] == dest[i]: 
                    ind += 1
                else:
                    break
            calculo.append(ind)
        return calculo

    def _calc_dist(self, dest_addr):
        
        dest = dest_addr.split('.')
        dest_str = "{:0>8b}{:0>8b}{:0>8b}{:0>8b}".format(int(dest[0]), int(dest[1]), int(dest[2]), int(dest[3]))
        
        tabela = []
        val_matchs = []
        for t in self.tabela:
            _t = t[0].split('.')
            val_matchs.append(int(_t[3].split('/')[1]))
            _t[3] = _t[3].split('/')[0]
            tabela.append("{:0>8b}{:0>8b}{:0>8b}{:0>8b}".format(int(_t[0]), int(_t[1]), int(_t[2]), int(_t[3])))
        
        calculo = self._calc_dif(tabela, dest_str)
        val = max(calculo)
        
        
        for i in range(len(calculo)):
        
            if tabela[len(calculo) - i - 1] == dest_str:
                return self.tabela[len(calculo) - i - 1][1]
        
            if calculo[len(calculo) - i - 1] == val:
                print("> {0}\n> {1}".format(dest_str, tabela[len(calculo) - i - 1]))
                print("> ", end='')
                print(" "*(calculo[len(calculo) - i - 1]) + "^")
                
                if val_matchs[len(calculo) - i - 1] > val:
                    return None
                
                #if dest_str[calculo[len(calculo) - i - 1]] == '1':
                #    print("{0} -> *{1}*".format(len(calculo) - i - 1, dest_str[calculo[len(calculo) - i - 1]]))
                #    return None
                
                print("MATCH {}".format(self.tabela[len(calculo) - i - 1]))
                return self.tabela[len(calculo) - i - 1][1]
        
        
        return None

    def _next_hop(self, dest_addr):
        # TODO: Use a tabela de encaminhamento para determinar o próximo salto
        # (next_hop) a partir do endereço de destino do datagrama (dest_addr).
        # Retorne o next_hop para o dest_addr fornecido.
        
        print('\n::: DEST_ADDR {}'.format(dest_addr))
        #print(self.tabela)
        return self._calc_dist(dest_addr)
        
        return None

    def definir_endereco_host(self, meu_endereco):
        """
        Define qual o endereço IPv4 (string no formato x.y.z.w) deste host.
        Se recebermos datagramas destinados a outros endereços em vez desse,
        atuaremos como roteador em vez de atuar como host.
        """
        self.meu_endereco = meu_endereco
        print("MEU_ENDERECO {0}".format(self.meu_endereco))

    def definir_tabela_encaminhamento(self, tabela):
        """
        Define a tabela de encaminhamento no formato
        [(cidr0, next_hop0), (cidr1, next_hop1), ...]

        Onde os CIDR são fornecidos no formato 'x.y.z.w/n', e os
        next_hop são fornecidos no formato 'x.y.z.w'.
        """
        for t in tabela:
            self.tabela.append([t[0], t[1]])
        # TODO: Guarde a tabela de encaminhamento. Se julgar conveniente,
        # converta-a em uma estrutura de dados mais eficiente.
        pass

    def registrar_recebedor(self, callback):
        """
        Registra uma função para ser chamada quando dados vierem da camada de rede
        """
        self.callback = callback

    def enviar(self, segmento, dest_addr):
        """
        Envia segmento para dest_addr, onde dest_addr é um endereço IPv4
        (string no formato x.y.z.w).
        """
        
        
        next_hop = self._next_hop(dest_addr)        
        print("DEST_ADDR {0} NEXT_HOP {1}".format(dest_addr, next_hop))
        
        dest = dest_addr.split('.')
        destino = [int(dest[0]), int(dest[1]), int(dest[2]), int(dest[3])]
        val = destino[3] << 24
        val += destino[2] << 16
        val += destino[1] << 8
        val += destino[0] << 0      
          
        val_dst = val
        data_dst_addr = (val).to_bytes(4, 'little')
        
        dest = self.meu_endereco.split('.')
        destino = [int(dest[0]), int(dest[1]), int(dest[2]), int(dest[3])]
        val = destino[3] << 24
        val += destino[2] << 16
        val += destino[1] << 8
        val += destino[0] << 0
        
        data_src_addr = (val).to_bytes(4, 'little')
        
        version = 4
        ihl = 5
        data_version_verihl = ((version << 4) + ihl).to_bytes(1, 'little')
        
        data_total_len = (len(segmento) + 20).to_bytes(2, 'little')
        
        data_identification = (0).to_bytes(2, 'little')
        
        datagrama = \
            data_version_verihl + \
            (0).to_bytes(1, 'little') + \
            data_total_len + \
            data_identification + \
            (0).to_bytes(2, 'little') + \
            (64).to_bytes(1, 'little') + \
            (6).to_bytes(1, 'little')
        
        data_checksum = calc_checksum(datagrama + \
            data_src_addr + \
            data_dst_addr)
        print("Versão original {0}".format(data_checksum))
        
        data_header_checksum = data_checksum.to_bytes(2, 'little')
        
        datagrama = datagrama + \
            data_header_checksum + \
            data_src_addr + \
            data_dst_addr + \
            segmento
            
        #datagrama = ((4 << 4) + 5).to_bytes(1, 'little') + (0).to_bytes(7, 'little') + (64).to_bytes(1, 'little') + (0).to_bytes(7, 'little')  + datagrama
        # TODO: Assumindo que a camada superior é o protocolo TCP, monte o
        # datagrama com o cabeçalho IP, contendo como payload o segmento.
        self.enlace.enviar(datagrama, next_hop)
