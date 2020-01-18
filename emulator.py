import pcap
import threading
import time

from control24common import (NetworkHelper, hexl, COMMANDS)

from ReaControl import (c24packet_factory, C24BcastData, C24Header, EthHeader, MacAddress)

from ctypes import c_ubyte


PCAP_FILTER = 'ether src %s and ether[12:2]=0x885f'

MAC = '00:a0:7e:a0:17:fe'
#DEVICE = 'MAINUNIT'
DEVICE = 'MAINUNIT'
VERSION = '1.37'

ADAPTER = 'en0'
TIMING_BCAST = 3
TIMING_INIT = 10

NETWORKS = NetworkHelper()

STATE = 0

C_CNT = 0
S_CNT = 0

THREAD_PCAP_LOOP = None
ACK_PACKET = None
PC_MAC = None

def log(msg, *args):
    print(msg % args)

def packet_handler(timestamp, pkt_data):
    """PCAP Packet Handler: Async method called on packet capture"""
    global STATE, ACK_PACKET, C_CNT, PC_MAC
    # build a dynamic class and load the data into it
    pcl = c24packet_factory(prm_tot_len=len(pkt_data))
    packet = pcl()
    packet = pcl.from_buffer_copy(pkt_data)
    # Detailed traffic logging
    log('Packet Received: %s', str(packet))
    C_CNT = packet.struc.c24header.sendcounter

    # check for a state transition
    if STATE == 0:
        if packet.struc.c24header.c24cmd == COMMANDS["online"]:
            log("Received ONLINE command, going ONLINE")
            STATE = 1
            PC_MAC = packet.struc.ethheader.macsrc
            ACK_PACKET = make_ack_packet()
    elif STATE == 1:
        ACK_PACKET.struc.c24header.sendcounter = C_CNT
        log("sending ACK for cmd %d", C_CNT)
        log(str(ACK_PACKET))
        THREAD_PCAP_LOOP.send_packet(ACK_PACKET)



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

def make_bcast_packet():
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
    return bcast_packet

def make_ack_packet():
    global PC_MAC
    ack_packet = c24packet_factory(prm_data_len=0)()
    ack_packet.struc.ethheader = EthHeader()
    ack_packet.struc.ethheader.macsrc = MacAddress.from_buffer_copy(bytearray.fromhex(MAC.replace(':', '')))
    ack_packet.struc.ethheader.macdest = MacAddress.from_buffer_copy(PC_MAC)

    ack_packet.struc.c24header.c24cmd = COMMANDS["ack"]

    return ack_packet


# START main program
def main():
    """Main """
    global ACK_PACKET, THREAD_PCAP_LOOP

    network = NETWORKS.get(ADAPTER)
    
    #Start the networking up
    THREAD_PCAP_LOOP = SnifferForEmulator(network)
    THREAD_PCAP_LOOP.start()

    bcast_packet = make_bcast_packet()



    while THREAD_PCAP_LOOP.is_alive():
        # Send broacasts and wait for init
        if STATE == 0:
            time.sleep(TIMING_BCAST)
            THREAD_PCAP_LOOP.send_packet(bcast_packet)
        elif STATE == 1:
            time.sleep(TIMING_INIT)

if __name__ == '__main__':
    main()
