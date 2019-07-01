import pcap
import threading
import time

from control24common import (NetworkHelper, hexl)

from ReaControl import (c24packet_factory, C24BcastData, C24Header, EthHeader, MacAddress)

from ctypes import c_ubyte


PCAP_FILTER = 'ether src %s and ether[12:2]=0x885f'

MAC = '00:a0:7e:a0:17:fe'
#DEVICE = 'MAINUNIT'
DEVICE = 'CNTRL|24'
VERSION = '1.37'

ADAPTER = 'en0'
TIMING_BCAST = 3

NETWORKS = NetworkHelper()

def packet_handler(timestamp, pkt_data):
    """PCAP Packet Handler: Async method called on packet capture"""
    print(timestamp, hexl(pkt_data))

class SnifferForEmulator(threading.Thread):
    """Thread class to hold the packet sniffer loop
    and ensure it is interruptable"""
    #--MULTI refactor c24session to nethandler
    def __init__(self, network):
        super(SnifferForEmulator, self).__init__()
        self.daemon = True
        self.name = 'thread_sniffer'
        net_name = network.get('pcapname')
        self.pcap_sess = pcap.pcap(
            name=net_name,
            promisc=True,
            immediate=True,
            timeout_ms=50
            )
        filtstr = PCAP_FILTER % NETWORKS.get_mac_address(ADAPTER)
        self.pcap_sess.setfilter(filtstr)
        self.packet_handler = packet_handler

    def run(self):
        """pcap loop, runs until interrupted"""
        try:
            for pkt in self.pcap_sess:
                if not pkt is None:
                    self.packet_handler(*pkt)
        except KeyboardInterrupt:
            print('CTRL+C')

    def send_packet(self, pkt):
        """sesion wrapper around pcap_sendpacket
        so we can pass in session and trap error"""
        print("Sending Packet of {} bytes: {}".format(pkt.pkt_tot_len, hexl(pkt.raw)))
        buf = pkt.to_buffer()
        pcap_status = self.pcap_sess.sendpacket(buf)
        if pcap_status != pkt.pkt_tot_len:
            print("Error sending packet: {}".format( self.pcap_sess.geterr()))
            return False
        else:
            return True

# START main program
def main():
    """Main """

    network = NETWORKS.get(ADAPTER)
    
    #Start the networking up
    thread_pcap_loop = SnifferForEmulator(network)
    thread_pcap_loop.start()

    #make up a broadcast packet like a device
    bcast_packet = c24packet_factory(prm_data_len = 33)()

    bcast_packet.struc.ethheader = EthHeader()
    bcast_packet.struc.ethheader.macsrc = MacAddress.from_buffer_copy(bytearray.fromhex(MAC.replace(':', '')))
    bcast_packet.struc.ethheader.macdest = MacAddress.from_buffer_copy(bytearray.fromhex('FFFFFFFFFFFF'))

    bcast_data = C24BcastData()
    bcast_data.version = VERSION
    bcast_data.device = DEVICE

    bcast_packet.struc.packetdata = (c_ubyte * 33).from_buffer_copy(bcast_data)

    print(bcast_packet)

    while thread_pcap_loop.is_alive():
        time.sleep(TIMING_BCAST)
        thread_pcap_loop.send_packet(bcast_packet)
        print('bcast')

if __name__ == '__main__':
    main()
