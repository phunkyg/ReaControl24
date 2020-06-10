#!/usr/bin/env python
"""control24 mixing desk daemon.
Daemon process to serve further client processes
that can choose to implement a protocol with DAWs etc.
"""

import signal
import sys
import threading
import time
import logging
from ctypes import (POINTER, BigEndianStructure, Structure, Union,
                    addressof, c_char, c_ubyte, c_uint16,
                    c_uint32, cast, create_string_buffer, string_at)
#--MULTI can retire listener
#from multiprocessing.connection import AuthenticationError, Listener
from multiprocessing import Process, Pipe
from optparse import OptionError

import pcap

from ReaCommon import (DEFAULTS, COMMANDS, NetworkHelper, hexl,
                       opts_common, tick, fix_ownership,
                       start_logging, trace)

#--MULTI can we import the client scripts?
import control24osc as control24_client
import procontrolosc as procontrol_client

'''
    This file is part of ReaControl24. Control Surface Middleware.
    Copyright (C) 2018  PhaseWalker

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

# c_types versions, should replace above

C_PROTOCOL = (c_ubyte * 2)(0x88, 0x5F)


# Timing values in seconds
TIMING_KEEP_ALIVE = 10          # Delta time before a KA to desk is considered due
TIMING_KEEP_ALIVE_LOOP = 1      # How often to check if a KA is due
TIMING_BEFORE_ACKT = 0.0008     # Delta between packet arriving and ACK being sent
TIMING_MAIN_LOOP = 6            # Loop time for main, which does nothing
TIMING_SHUTDOWN_ACTIONS = 0.5   # bit of wait time when shuttind down
TIMING_SNIFFER_TIMEOUT = 1000   # milliseconds passed to the pcap timeout
TIMING_LISTENER_POLL = 2        # Poll time for MP Listener to wait for data
TIMING_LISTENER_RECONNECT = 1   # Pause before a reconnect attempt is made
TIMING_WAIT_DESC_ACK = 0.1      # Wait period for desk to ACK after send, before warning is logged
TIMING_BACKOFF = 0.3            # Time to pause sending data to desk after a retry packet is recvd

# Control Constants

# START Globals

# --MULTI - use a dict to contain multiple sessions. Add a NETHANDLER global
#SESSION = None
NETHANDLER = None

# PCAP settings
PCAP_ERRBUF_SIZE = 256
PCAP_SNAPLEN = 1038
PCAP_PROMISC = 1
PCAP_PACKET_LIMIT = -1  # infinite
PCAP_POLL_DELAY = 5
PCAP_FILTER = '(ether dst %s or broadcast) and ether[12:2]=0x885f'

# END Globals

# START functions



def compare_ctype_array(arr1, arr2):
    """Iterate and compare byte by byte all bytes in 2 ctype arrays"""
    return all(ai1 == ai2 for ai1, ai2 in zip(arr1, arr2))


# END functions

# START classes

# C Structure classes for packet capture and decoding
class MacAddress(Structure):
    """ctypes structure to let us get the vendor
    portion from the mac address more easily"""
    _fields_ = [("vendor", c_ubyte * 3), ("device", c_ubyte * 3)]

    _vendor = (c_ubyte * 3)(0x00, 0xA0, 0x7E)
    _broadcast = (c_ubyte * 3)(0xFF, 0xFF, 0xFF)

    def is_vendor(self):
        """does the address match the vendor bytes"""
        return compare_ctype_array(self.vendor, MacAddress._vendor)

    def is_broadcast(self):
        """does the address match broadcast bytes"""
        return compare_ctype_array(self.vendor, MacAddress._broadcast)

    def __str__(self):
        return hexl(self)


class EthHeader(Structure):
    """ctypes structure for the Ethernet layer
    fields. Length 14"""
    _fields_ = [
        ("macdest", MacAddress),
        ("macsrc", MacAddress),
        ("protocol", c_ubyte * 2)
        ]
    def __init__(self):
        super(EthHeader, self).__init__()
        self.protocol = (c_ubyte * 2)(0x88, 0x5F)

    def __str__(self):
        return 'to:{} from:{} {} prot:{}'.format(
            hexl(self.macdest),
            hexl(self.macsrc.vendor),
            hexl(self.macsrc.device),
            hexl(self.protocol)
        )

    def is_broadcast(self):
        """Is this a broadcast packet i.e. destination is broadcast"""
        return self.macdest.is_broadcast()

class C24Header(BigEndianStructure):
    """ctypes structure to contain C24 header fields
    that seem to appear common to all packets.
    Length 14"""
    _pack_ = 1
    _fields_ = [
        ("numbytes", c_uint16),     # 16 0x00 0x10
        ("unknown1", c_ubyte * 2),  # 0x00 0x00
        ("sendcounter", c_uint32),
        ("cmdcounter", c_uint32),
        ("retry", c_uint16),
        ("c24cmd", c_ubyte),
        ("numcommands", c_ubyte)
    ]

    def __str__(self):
        cmd = COMMANDS.get(self.c24cmd) or hex(self.c24cmd)
        return 'bytes:{} c_cnt:{} s_cnt:{} retry:{} cmd:{} nc:{}'.format(
            self.numbytes,
            self.cmdcounter,
            self.sendcounter,
            self.retry,
            cmd,
            self.numcommands
        )

    def is_retry(self):
        """Is this a retry packet i.e. there is data in the retry field"""
        return self.retry != 0


class C24BcastData(BigEndianStructure):
    """class to cast c24 packet data to if it is a brodcast packet.
    to get the details out of it"""
    _pack_ = 1
    _fields_ = [
        ("unknown1", c_ubyte * 15),
        ("version", c_char * 9),
        ("device", c_char * 9)
        ]

    def __str__(self):
        return 'BCAST d:{} v:{} u1:{}'.format(
            self.device,
            self.version,
            hexl(self.unknown1)
        )


def c24packet_factory(prm_tot_len=None, prm_data_len=None):
    """dynamically build and return a packet class with the variable length
    length packet data element in place. pkt_length is full length
    including the 30 bytes of headers"""
    # Provide option to specify data or total length
    # and derive all 3 lengths into the packet class def
    if prm_tot_len is None and not prm_data_len is None:
        req_data_len = prm_data_len
        req_tot_len = prm_data_len + 30
    elif prm_data_len is None and not prm_tot_len is None:
        req_data_len = prm_tot_len - 30
        req_tot_len = prm_tot_len
    req_byt_len = req_data_len + 16

    class C24Variable(BigEndianStructure):
        """both headers and the variable data section"""
        _pack_ = 1
        _fields_ = [
            ("ethheader", EthHeader),
            ("c24header", C24Header),
            ("packetdata", c_ubyte * req_data_len)]

    class C24Packet(Union):
        """allow addressing of the whole packet as a raw byte array"""
        _pack_ = 1
        _fields_ = [
            ("raw", c_ubyte * req_tot_len),
            ("struc", C24Variable)
        ]
        pkt_data_len = req_data_len
        pkt_tot_len = req_tot_len
        pkt_byt_len = req_byt_len

        def __init__(self):
            super(C24Packet, self).__init__()
            self.struc.c24header.numbytes = self.pkt_byt_len

        def __str__(self):
            return '{} {} {}'.format(
                str(self.struc.ethheader),
                str(self.struc.c24header),
                hexl(self.struc.packetdata)
            )

        def to_buffer(self):
            """Provide the raw packet contents as a string buffer"""
            memaddr = addressof(self)
            sendbuf = string_at(memaddr, self.pkt_tot_len)
            return sendbuf

        def is_broadcast(self):
            """Is this a broadcast packet i.e. is the ethernet header saying that"""
            return self.struc.ethheader.macdest.is_broadcast()

        def is_retry(self):
            """Is this a retry packet i.e. is the C24 header saying that"""
            return self.struc.c24header.is_retry()

    return C24Packet




class KeepAlive(threading.Thread):
    """Thread class to hold the keep alive loop"""
    def __init__(self, session):
        """set up the thread and copy session refs needed"""
        super(KeepAlive, self).__init__()
        self.daemon = True
        self.session = session
        self.name = '{}_thread_keepalive'.format(self.session.session_name)

    def run(self):
        """keep alive loop"""
        log = logging.getLogger(__name__)
        while not self.session.is_closing:
            if self.session.parent.is_capturing and self.session.mac_device is not None:
                delta = tick() - self.session.pcap_last_sent
                if delta >= TIMING_KEEP_ALIVE:
                    log.trace('%s KeepAlive TO DEVICE', self.session.session_name)
                    self.session.send_packet(self.session.prepare_keepalive())
            time.sleep(TIMING_KEEP_ALIVE_LOOP)


class ManageListener(threading.Thread):
    """Thread class to manage the multiprocessing listener"""
    #multiprocessing parameters
    cmd_buffer_length = 314
    max_cmds_in_packet = 48

    def __init__(self, session):
        """set up the thread and copy session refs needed"""
        super(ManageListener, self).__init__()
        self.daemon = True
        self.session = session
        self.name = '{}_thread_listener'.format(self.session.session_name)
        #--MULTI pretty sure this is redundant
        #self.mp_listener = self.session.mp_listener
        self.mp_conn = self.session.parent_conn

    def run(self):
        """listener management loop"""
        log = logging.getLogger(__name__)
        recvbuffer = create_string_buffer(self.cmd_buffer_length)
        log.info('%s Pipe Listener waiting for first data from pid %d',
                    self.name, self.session.client_process.pid)
        # Loop to manage connect/disconnect events
        while not self.session.is_closing:
            try:
                while self.session.client_is_connected and not self.session.is_closing:
                    buffsz = 0
                    if self.mp_conn.poll(TIMING_LISTENER_POLL):
                        incrsz = self.mp_conn.recv_bytes_into(
                            recvbuffer, buffsz)
                        buffsz += incrsz
                        ncmds = 1
                        while all([
                                self.mp_conn.poll(),
                                ncmds < self.max_cmds_in_packet,
                                buffsz < self.cmd_buffer_length - 30
                            ]):
                            incrsz = self.mp_conn.recv_bytes_into(
                                recvbuffer, buffsz)
                            buffsz += incrsz
                            ncmds += 1
                        self.session.receive_handler(recvbuffer.raw, ncmds, buffsz)

            except Exception:
                log.error("%s Pipe Listener exception", self.name, exc_info=True)
                raise

        # close down gracefully
        self.session.client_conn.close()
        self.session.parent_conn.close()

    def mpsend(self, pkt_data):
        """If a client is connected then send the data to it.
        trap if this sees that the client went away meanwhile"""
        log = logging.getLogger(__name__)
        try:
            self.session.client_conn.send_bytes(pkt_data)
        except (IOError, EOFError):
            # Client broke the pipe?
            log.info('%s MP Listener broken pipe',
                        self.name)
            self.session.client_is_connected = False
            self.session.client_conn.close()
            self.session.parent_conn.close()


class Sniffer(threading.Thread):
    """Thread class to hold the packet sniffer loop
    and ensure it is interruptable"""
    #--MULTI refactor c24session to nethandler
    def __init__(self, nethandler):
        super(Sniffer, self).__init__()
        self.daemon = True
        self.name = 'thread_sniffer'
        self.nethandler = nethandler
        network = self.nethandler.network.get('pcapname')
        # Set up the pcas session
        self.nethandler.pcap_sess = self.nethandler.fpcapt.pcap(
            name=network,
            promisc=False,
            immediate=False,
            timeout_ms=TIMING_SNIFFER_TIMEOUT
            )
        filtstr = PCAP_FILTER % self.nethandler.mac_computer_str
        self.nethandler.pcap_sess.setfilter(filtstr)
        # experiment!
        #self.nethandler.pcap_sess.setnonblock()
        # Store as a few attributes
        self.nethandler.is_capturing = False
        self.pcap_sess = self.nethandler.pcap_sess
        self.packet_handler = self.nethandler.packet_handler

    def run(self):
        """pcap loop, runs until interrupted. blocks the main
        program for graceful exit"""
        log = logging.getLogger(__name__)
        log.debug('Capture Starting')
        self.nethandler.is_capturing = True
        # Capture, allowing timeouts to loop so is_closing
        # can be observed every timeout interval
        while not self.nethandler.is_closing:
            trace(log, 'sniffer loop')
            pkts = self.pcap_sess.readpkts()
            for pkt in pkts:
                self.packet_handler(*pkt)
        self.nethandler.is_capturing = False
        log.debug('Capture Finished')


#--MULTI New Listener class
# currently a full copy/paste of C24Session
class NetworkHandler(object):
    """Class to handle incoming network traffic, start
    sessions and dispatch traffic to them if needed"""

    c24cmds = COMMANDS
    # callbacks / event handlers (threaded)
    def packet_handler(self, timestamp, pkt_data):
        """PCAP Packet Handler: Async method called on packet capture"""
        log = logging.getLogger(__name__)
        broadcast = False
        pkt_len = len(pkt_data)
        # build a dynamic class and load the data into it
        pcl = c24packet_factory(prm_tot_len=pkt_len)
        packet = pcl()
        packet = pcl.from_buffer_copy(pkt_data)
        #Detailed traffic logging
        trace(log, 'Packet Received: %s', str(packet))
        # Decode any broadcast packets
        if packet.is_broadcast():
            broadcast = True
            pbp = POINTER(C24BcastData)
            bcast_data = cast(packet.struc.packetdata, pbp).contents
            trace(log, '%s', str(bcast_data))
        #--MULTI check sessions and create if new
        src_mac = packet.struc.ethheader.macsrc
        src_session = self.sessions.get(str(src_mac))
        if src_session is None and src_mac.is_vendor():
            if broadcast:
                #--MULTI not sure if params are right yet
                self.num_sessions += 1
                src_session = DeviceSession(self, self.num_sessions, src_mac, bcast_data)
                self.sessions[str(src_mac)] = src_session
            else:
                log.warn('Dropping Non broadcast packet from new device! %s', str(src_mac))
                return
        #--MULTI despatch packet to sessions' handler
        src_session.packet_handler(packet)

    # session instance methods
    def send_packet(self, pkt):
        """sesion wrapper around pcap_sendpacket
        so we can pass in session and trap error"""
        log = logging.getLogger(__name__)
        trace(log, "Sending Packet of %d bytes: %s", pkt.pkt_tot_len, hexl(pkt.raw))
        buf = pkt.to_buffer()
        pcap_status = self.pcap_sess.sendpacket(buf)
        if pcap_status != pkt.pkt_tot_len:
            log.warn("Error sending packet: %s", self.pcap_sess.geterr())
            return False
        else:
            return True
        #--MULTI move to session
        #else:
        #    self.pcap_last_sent = tick()
        #    self.pcap_last_packet = pkt

    def __init__(self, opts, networks):
        """Constructor to build the network handler object"""
        log = start_logging(__name__, opts.logdir, opts.debug)
        log.info('Network Handler Started')
        log.debug('Options %s', str(opts))
        #--MULTI add a Sessions dict
        self.sessions = {}
        self.num_sessions = 0
        self.thru_params = (opts, networks)
        # Create variables for a session
        self.network = networks.get(opts.network)
        self.listen_address = networks.ipstr_to_tuple(opts.listen)
        self.pcap_error_buffer = create_string_buffer(PCAP_ERRBUF_SIZE) # pcap error buffer
        self.fpcapt = pcap
        self.pcap_sess = None
        self.sniffer = None
        self.is_capturing = False
        self.is_closing = False
        self.mac_computer_str = self.network.get('mac')
        self.mac_computer = MacAddress.from_buffer_copy(bytearray.fromhex(self.mac_computer_str.replace(':', '')))
        self.thread_pcap_loop = Sniffer(self)
        self.thread_pcap_loop.start()
        #self.thread_pcap_loop.join()
        #self.is_closing = True
        #self.close()

    def __str__(self):
        """pretty print handler state if requested"""
        return 'control24 network handler: is_capturing:{} num_sessions:{}'.format(
            self.is_capturing, self.num_sessions)

    def close(self):
        """Quit the handler gracefully if possible"""
        log = logging.getLogger(__name__)
        log.info("NetworkHandler closing")
        #--MULTI call a close for each session
        for mac, sess in self.sessions.iteritems():
            log.info("Closing DeviceSession for %s", mac)
            sess.close()
        # For threads under direct control this signals to please end
        self.is_closing = True
        # Join threads to ensure they close (none)
        self.thread_pcap_loop.join()
        # PCAP thread has its own KeyboardInterrupt handler
        log.info("NetworkHandler closed")

    def __del__(self):
        """Placeholder to see if session object destruction is a useful hook"""
        log = logging.getLogger(__name__)
        trace(log, "NetworkHandler del")
        self.close()

# Main sesssion class
class DeviceSession(object):
    """Class to contain all session details with a control surface device.
    Now handler multiple sessions!"""

    c24cmds = COMMANDS
    # callbacks / event handlers (threaded)
    def packet_handler(self, packet):
        """Device Session Packet Handler. If packet was for
        this device then it will have been dispatched to here"""
        log = logging.getLogger(__name__)
        if not packet.is_broadcast():
            # Look first to see if this is an ACK
            if packet.struc.c24header.c24cmd == COMMANDS['ack']:
                trace(log, '%s ACK FROM DEVICE', self.session_name)
                if not self.backoff.is_alive():
                    self.sendlock.set()
            elif packet.struc.c24header.numcommands > 0:
                # At this point an ACK is pending so lock all sending
                self.sendlock.clear()
                # Check to see if this is retry
                if packet.is_retry():
                    self.current_retry_desk = retry = packet.struc.c24header.retry
                    log.warn('%s Retry packets from desk: %d', self.session_name, retry)
                    # Try a send lock if desk is panicking, back off for a
                    # bit of time to let 'er breathe
                    self.sendlock.clear()
                    self.backoff = threading.Timer(TIMING_BACKOFF, self._backoff)
                    self.backoff.start()
                # It is a genuine packet of commands so go ahead and process it
                cmdnumber = packet.struc.c24header.sendcounter
                trace(log, '%s RECEIVED %d', self.session_name, cmdnumber)
                # this counter changes to the value the DESK sends to us so we can ACK it
                self.cmdcounter = cmdnumber
                # forward it to the client
                self.parent_conn.send_bytes(packet.struc.packetdata)
                trace(log, '%s ACK TO DEVICE: %d', self.session_name, self.cmdcounter)
                time.sleep(TIMING_BEFORE_ACKT)
                self.send_packet(self._prepare_ackt())
                if not self.backoff.is_alive():
                    self.sendlock.set()
            else:  # It is not an ack and no number of commands on it, something we haven't seen before?
                log.warn('%s Unhandled data from device :%02x', self.session_name, packet.struc.packetdata[0])
                trace(log, '%s     unhandled: %s', self.session_name, hexl(packet.raw))

    def receive_handler(self, buff, ncmds, buffsz):
        """Receive Handler. TODO a better description"""
        log = logging.getLogger(__name__)
        log.debug('MP recv: c:%d s:%d d:%s', ncmds, buffsz,
                  hexl(buff[:buffsz]))
        pkt_data_len = buffsz  # len(buff)
        pkt_data = (c_ubyte * pkt_data_len).from_buffer_copy(buff)
        totalwait = 0.0
        while not self.sendlock.wait(TIMING_WAIT_DESC_ACK):
            totalwait += TIMING_WAIT_DESC_ACK
            log.warn('Waiting for DESK ACK %d', totalwait)
            #TODO implement daw-desk retry packets
        trace(log, 'TODESK CMD %d', self.sendcounter)
        if self.mac_device is not None:
            packet = self._prepare_packetr(pkt_data, pkt_data_len, ncmds)
            self.send_packet(packet)
            self.sendlock.clear()
        else:
            log.warn(
                'MP received but no desk to send to. Establish a session. %s',
                hexl(pkt_data))

    # session instance methods
    def send_packet(self, pkt):
        """pass packet back to the network handler"""
        ok = self.parent.send_packet(pkt)
        if ok:
            self.pcap_last_sent = tick()
            self.pcap_last_packet = pkt

    def _prepare_packetr(self, pkt_data, pkt_data_len, ncmds, parity=None, c24cmd=None):
        """session wrapper around C24Packet"""
        if parity is None:
            parity = (c_ubyte * 2)()
        pcp = c24packet_factory(prm_data_len=pkt_data_len)()
        pcp.struc.ethheader = self.ethheader
        pcp.struc.c24header.unknown1 = parity
        if c24cmd:
            pcp.struc.c24header.c24cmd = c24cmd
        if pkt_data_len > 0:
            pcp.struc.packetdata = pkt_data
        pcp.struc.c24header.numcommands = ncmds
        if c24cmd == self.c24cmds['ack']:
            pcp.struc.c24header.cmdcounter = self.cmdcounter
        else:
            # This counter increments by number of commands we are sending in this/each packet
            self.sendcounter += ncmds
            pcp.struc.c24header.sendcounter = self.sendcounter
        return pcp

    def prepare_keepalive(self):
        """session wrapper around keepalive packet"""
        keepalivedata = (c_ubyte * 1)()
        keepalive = self._prepare_packetr(keepalivedata, 1, 1)
        return keepalive

    def _prepare_ackt(self):
        """session wrapper around ackt packet"""
        ack = self._prepare_packetr(None, 0, 0, c24cmd=self.c24cmds['ack'])
        return ack

    def _backoff(self):
        log = logging.getLogger(__name__)
        trace(log, '%s backoff complete', self.session_name)
        self.sendlock.set()

    #--MULTI new process launcher
    def start_client(self):
        """start the appropriate client for the device"""
        log = logging.getLogger(__name__)
        device = self.bcast_data.device
        if device == 'CNTRL|24':
            target = control24_client.C24Oscsession
            self.is_supported_device = True
        elif device == 'MAINUNIT':
            target = procontrol_client.ProCoscsession
            self.is_supported_device = True
        else:
            log.error('No client code for this device ')   
            self.is_supported_device = False
            self.close()

        if self.is_supported_device:
            self.client_process = Process(target=target, args=self.client_args)
            self.client_process.daemon = True
            try:
                self.client_process.start()
            except RuntimeError:
                pass
                #log.warning("Client process already started. Normal when debugging.")
                
        
        #while not self.client_process.is_alive():
        #    time.sleep(1)
        
        self.client_is_connected = True

    def new_port(self):
        daw_string = self.parent.thru_params[0].connect
        daw_tuple = NetworkHelper.ipstr_to_tuple(daw_string)
        daw_port = daw_tuple[1] + (self.session_number - 1)
        self.daw_address = (daw_tuple[0], daw_port)

    def init_device(self):
        # initialise the desk by sending the init command
        # and wiping the clock display
        init1 = self._prepare_packetr(None, 0, 0, c24cmd=COMMANDS['online'])
        init2data = (c_ubyte * 15)(0xF0, 0x13, 0x01, 0x30, 0x19, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xf7)
        init2 = self._prepare_packetr(init2data, 15, 1, (c_ubyte * 2)(0x02, 0x44))
        self.send_packet(init1)
        self.send_packet(init2)

    def __init__(self, parent, number, device_mac, bcast_data):
        """Constructor to build the device session object"""
        log = logging.getLogger(__name__)
        # Create variables for a session
        #--MULTI new session things
        self.parent = parent
        self.session_number = number
        self.daw_address = None
        self.new_port()
        self.mac_device = MacAddress.from_buffer_copy(device_mac)
        self.bcast_data = bcast_data
        log.info('Device detected: %s %s at %s',
            bcast_data.device,
            bcast_data.version,
            hexl(self.mac_device)
        )
        self.session_name = 'device session {} {}'.format(self.session_number, self.bcast_data.device)
        self.client_process = None
        self.parent_conn, self.client_conn = Pipe()
        self.client_is_connected = False
        # Build up client arguments. Could be cleaned up in future
        # but this for the moment retains the Subprocess or standalone pattern
        self.client_args = (self.parent.thru_params[0], self.parent.network, self.client_conn)
        self.is_closing = False
        self.is_supported_device = False
        self.last_sent = tick()
        self.last_packet = None
        self.current_retry_desk = 0
        # desk-to-daw (cmdcounter) and daw-to-desk (sendcounter)
        self.cmdcounter = 0
        self.sendcounter = 1
        self.sendlock = threading.Event()
        self.sendlock.set()
        self.backoff = threading.Timer(TIMING_BACKOFF, self._backoff)
        # build a re-usable Ethernet Header for sending packets
        self.ethheader = EthHeader()
        self.ethheader.macsrc = MacAddress.from_buffer_copy(self.parent.mac_computer)
        self.ethheader.macdest = self.mac_device
        trace(log, str(self.ethheader))
        # Turn the device online
        self.init_device()        
        # Start the client process
        self.start_client()
        # Start a thread to listen to the process pipe
        self.thread_listener = ManageListener(self)
        self.thread_listener.start()
        # Start a thread to keep sending packets to desk to keep alive
        self.thread_keepalive = KeepAlive(self)
        self.thread_keepalive.start()

    def __str__(self):
        """pretty print device session state if requested"""
        return '{} : client_is_connected:{}'.format(
            self.session_name, self.client_is_connected)

    def close(self):
        """Quit the device session gracefully if possible"""
        log = logging.getLogger(__name__)
        log.info("%s closing", self.session_name)
        # For threads under direct control this signals to please end
        self.is_closing = True
        # Join threads until they finish
        log.debug('%s Waiting for thread shutdown', self.session_name)
        self.thread_keepalive.join()
        self.thread_listener.join()
        # Close the pipe to indicate to the subprocess it should end
        self.client_conn.close()
        while self.client_process.is_alive():
            log.debug('%s waiting for client process shutdown', self.session_name)
            time.sleep(TIMING_SHUTDOWN_ACTIONS)

        # PCAP thread has its own KeyboardInterrupt handle
        log.info("%s closed", self.session_name)

    def __del__(self):
        """Placeholder to see if device session object destruction is a useful hook"""
        log = logging.getLogger(__name__)
        trace(log, "%s del", self.session_name)
        self.close()


class ReaQuit(Exception):
    """Custom exception to use when there is an internal problem"""
    pass
# END classes


# functions for main
def signal_handler(sig, stackframe):
    """Exit the daemon if a signal is received"""
    log = logging.getLogger(__name__)
    signals_dict = dict((getattr(signal, n), n) for n in dir(signal)
                        if n.startswith('SIG') and '_' not in n)
    signame = signals_dict[sig]
    log.info("Signal Handler %s received.", signame)
    raise ReaQuit(signame)


def signal_dumpo(sig, stackframe):
    """Signal info dumper for debugging"""
    log = logging.getLogger(__name__)
    log.debug(str(stackframe))

# START main program
def main():
    """Main function declares options and initialisation routine for daemon."""
    #--MULTI - globalise NETHANDLER
    global NETHANDLER

    # Find networks on this machine, to determine good defaults
    # and help verify options
    networks = NetworkHelper()

    # See if this system has simple defaults we can use
    default_iface, default_ip = networks.get_default()

    # program options
    oprs = opts_common("ReaControl Communication Daemon")
    oprs.add_option(
        "-n",
        "--network",
        dest="network",
        help="Ethernet interface to the same network as the Desk. Default = %s" %
        default_iface)
    # default_listener = networks.ipstr_from_tuple(default_ip, DEFAULTS.get('daemon'))
    # oprs.add_option(
    #     "-l",
    #     "--listen",
    #     dest="listen",
    #     help="listen on given host:port. Default = %s" % default_listener)
    # TODO did this to get it going but 9124 port will also need an auto-increment or alternative range
    default_osc_client = networks.ipstr_from_tuple(default_ip, DEFAULTS.get('oscport'))
    oprs.add_option(
        "-l",
        "--listen",
        dest="listen",
        help="accept OSC client from DAW at host:port. default %s" % default_osc_client)
    default_daw = networks.ipstr_from_tuple(default_ip, DEFAULTS.get('oscDaw'))
    oprs.add_option(
        "-c",
        "--connect",
        dest="connect",
        help="Connect to DAW OSC server at host:baseport. Baseport will increment for subsequent devices. default %s" % default_daw)
    oprs.set_defaults(network=default_iface)
    #oprs.set_defaults(listen=default_listener)
    oprs.set_defaults(listen=default_osc_client)
    oprs.set_defaults(connect=default_daw)

    # Parse and verify options
    # TODO move to argparse and use that to verify
    (opts, __) = oprs.parse_args()
    if not networks.get(opts.network):
        print(networks)
        raise OptionError(
            'Specified network does not exist. Known networks are listed to the output.',
            'network'
            )
    if not networks.verify_ip(opts.listen.split(':')[0]):
        raise OptionError('No network has the IP address specified.', 'listen')
    if not networks.is_valid_ipstr(opts.connect):
        raise OptionError('Not a valid ipv4 address and port ', 'connect')

    # DEBUG signal dumper
    #
    # all_sigs = dict((getattr(signal, n), n) for n in dir(signal)
    #                     if n.startswith('SIG') and '_' not in n and n not in ['SIGKILL', 'SIGINT', 'SIGSTOP'])
    #
    # for sig in all_sigs:
    #     print sig
    #     signal.signal(sig, signal_dumpo)
    #
    # The problem with using signal.pause is SIGCHLD is raised by the launch
    # of subprocess
    # using the ReaQuit instead when we get a signal per the below lists
    # END DEBUG


    # Set up Interrupt signal handler so process can close cleanly
    # if an external signal is received
    if sys.platform.startswith('win'):
        # TODO test these in Winders
        signals = [signal.SIGTERM, signal.SIGHUP,  signal.SIGABRT]
    else:
        # TODO check other un*x variants
        # OSC (Mojave) responding to these 2
        signals = [signal.SIGTERM, signal.SIGHUP]

    for sig in signals:
        signal.signal(sig, signal_handler)

    # session independent netowrk listener/dispatcher thread
    # Begins then drops through to the wait below.
    # This allows signal capture as well as
    # Keyboard interrupt CTRL+C
    if NETHANDLER is None:
        NETHANDLER = NetworkHandler(opts, networks)

    # Idle until one of the quit conditions is met

    try:
        while True:
            time.sleep(TIMING_MAIN_LOOP)
    except ReaQuit:
        print '**ReaQuit'
    except KeyboardInterrupt:
        print '**KeyboardInterrupt'
    except Exception:
        print '**UnhandledException'
        raise

    print '**Closing'
    NETHANDLER.close()


if __name__ == '__main__':
    main()
