#!/usr/bin/env python
"""Procontrol to Reaper.OSC client. Communicate between the daemon
process and an OSC Client/Listener pair, tuned for Reaper DAW.
Other, similar clients can be written to communicate with other
protocols such as MIDI HUI, Mackie etc.
"""

import binascii
import signal
import sys
import threading
import time

from ctypes import c_ubyte
from multiprocessing.connection import Client
from optparse import OptionError

import OSC

from ReaCommon import (ModeManager, ReaBase, ReaNav, ReaModifiers, _ReaDesk, _ReaTrack, ReaButtonLed,
                       DEFAULTS, FADER_RANGE, NetworkHelper,
                       opts_common, tick, SIGNALS, start_logging, trace)
import procontrolmap

'''
    This file is part of ReaProcontrol. Control Surface Middleware.
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

# Timing values in seconds
TIMING_MAIN_LOOP = 10  # 0
TIMING_SERVER_POLL = 2
TIMING_MP_POLL = 1
TIMING_WAIT_OSC_LISTENER = 4
TIMING_OSC_LISTENER_RESTART = 1
TIMING_OSC_CLIENT_RESTART = 1
TIMING_OSC_CLIENT_LOOP = 4
TIMING_SCRIBBLESTRIP_RESTORE = 4
TIMING_FADER_ECHO = 0.1

SESSION = None


# Globals

# Procontrol functions
# Split command list on repeats of the same starting byte or any instance of the F7 byte




# Housekeeping functions
def signal_handler(sig, stackframe):
    """Exit the client if a signal is received"""
    signals_dict = dict((getattr(signal, n), n)
                        for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    # log.info("procontrolosc shutting down as %s received.", signals_dict[sig])
    if not SESSION is None:
        SESSION.close()
    sys.exit(0)





# Classes representing Procontrol


class ProCdesk(_ReaDesk):
    """Class to represent the desk, state and
    instances to help conversions and behaviour"""
    real_channels = 8
    virtual_channels = 0
    busvus = 1
    deskmodes = {
        'Values': {
            'address': '/track/procscribstrip/volume',

        },
        'Group': {
            'toggle': True
        },
        'Names': {
            'address': '/track/procscribstrip/name',
            'default': True
        },
        'Info': {
            'address': '/track/procscribstrip/pan'
        }
    }

    def __init__(self, parent):
        """ Build a base desk object with the _Readesk class
        then apply the specifics for this device """
        super(_ReaDesk, self).__init__(self, parent)

        self.mapping_tree = procontrolmap.MAPPING_TREE_PROC
        self.reabuttonled = ReaButtonLed(self, None)

        self.modemgr = ModeManager(ProCdesk.deskmodes)
        # Set up specifics for this device
        self.channels = ProCdesk.real_channels
        self.virtual_channels = ProCdesk.virtual_channels

        self.instantiate_tracks(self, ProCtrack)




class ProCTrack(_ReaTrack):
    """Track (channel strip) object to contain
    one each of the elements found in each of the main
    channel strips (tracks)
    Spefically for Pro Control desk layout"""

    def __init__(self, desk, track_number):
        super(_ReaTrack, self).__init__(self, desk, track_number)

        # super gives us the common layout, now we add Pro Control specifics

        # Place a VU meter on virtual tracks above 8, these are bus VUs
        if self.track_number >= self.desk.channels and self.track_number <= self.desk.channels + self.desk.busvus:
            self.vumeter = ReaVumeter(self)

        if self.track_number == 28:
            self.vpot = ReaJpot(self)
            #Allow access from both 'virtual' track 28 AND desk object
            # as it physically belongs there
            self.desk.jpot = self.vpot

        if self.track_number <= self.desk.channels or self.track_number in range(
                self.desk.channels,
                self.channels + self.virtual_Channels
        ):
            self.scribstrip = ProCscribstrip(self)

##### GOT TO HERE



class ProCscribstrip(ReaBase):
    """Class to hold and convert scribblestrip value representations
    this version specific to the Control24 """

    digits = 8
    defaultaddress = '/track/number'
    bank = 0

    def __init__(self, track):
        super(_ReaScribStrip, self).__init__(
            self,
            track,
            ProCscribstrip.digits,
            ProCscribstrip.bank,
            ProCscribstrip.defaultaddress)



class C24jpot(ReaBase):
    # 'DirectionByte': 2,1
    # 'DirectionByteMask': 0x40,
    # 'ValueByte': 3

    def __init__(self, track):
        self.log = track.desk.log
        self.track = track
        self.cmdbytes = (c_ubyte * 30)()
        self.val = 0
        self.dir = 0
        self.velocity = 0
        self.out = 0
        self.scrubout = 0
        # Make the class modeful
        # TODO use the mode manager class
        self.mode = None
        self.modes = {
            'Scrub': {'address': '/scrub', 'default': True},
            # 'Shuttle': { 'address' : '/vkb_midi/0/cc/90'}
            'Shuttle': {'address': '/playrate/rotary'}
            # 'Shuttle': { 'address' : '/action/974/cc/relative'}
        }
        for key, value in self.modes.iteritems():
            value['msg'] = OSC.OSCMessage(value['address'])
            if value.get('default'):
                self.mode = key

    def __str__(self):
        return 'JOGWHEEL Channel:{}, dir:{} val:{} vel: {} out:{} cmdbytes:{}'.format(
            self.track.track_number,
            self.dir,
            self.val,
            self.velocity,
            self.out,
            binascii.hexlify(self.cmdbytes)
        )

    def d_c(self, parsedcmd):
        """desk to computer, switch by button or jog input"""
        addrs = parsedcmd.get('addresses')
        if addrs[1] == "button":
            self._update_from_button(parsedcmd, addrs)
        else:
            self._update_from_move(parsedcmd)

    def _update_from_button(self, parsedcmd, addrs):

        if parsedcmd.get('Value') == 1:
            button = addrs[-1]
            if self.modes.has_key(button):
                self.mode = button
            else:
                self.log.warn('C24jpot no mode for button %s', button)

    def _update_from_move(self, parsedcmd):
        """Update from desk command byte list"""

        cbytes = parsedcmd.get('cmdbytes')
        if cbytes:
            for ind, byt in enumerate(cbytes):
                self.cmdbytes[ind] = ord(byt)

            self.val = self.cmdbytes[2]
            if self.val > 64:
                self.dir = 1
                self.scrubout = 1
            else:
                self.dir = -1
                self.scrubout = 0

            self.velocity = self.cmdbytes[3]
            self.out = 0.5 + (float(self.val - 64) * float(0.05))
            # self.out += float(self.val - 64) * 0.00001

            currmode = self.modes.get(self.mode)
            msg = currmode.get('msg')
            msg.clearData()

            if self.mode == 'Scrub':
                msg.append(self.scrubout)
            else:
                msg.append(self.out)

            trace(log, '%s', self)
            self.track.desk.osc_client_send(msg)


class C24vpot(ReaBase):
    # 'DirectionByte': 2,
    # 'DirectionByteMask': 0x40,
    # 'ValueByte': 3
    scale_dot = [
        (0x40, 0x00, 0x00),  # 1 L
        (0x00, 0x40, 0x00),  # 2
        (0x00, 0x20, 0x00),  # 3
        (0x00, 0x10, 0x00),  # 4
        (0x00, 0x08, 0x00),  # 5
        (0x00, 0x04, 0x00),  # 6
        (0x00, 0x02, 0x00),  # 7
        (0x00, 0x01, 0x00),  # 8 C
        (0x00, 0x00, 0x40),  # 9
        (0x00, 0x00, 0x20),  # 10
        (0x00, 0x00, 0x10),  # 11
        (0x00, 0x00, 0x08),  # 12
        (0x00, 0x00, 0x04),  # 13
        (0x00, 0x00, 0x02),  # 14
        (0x00, 0x00, 0x01),  # 15 R
    ]
    scale_fill = [
        (0x40, 0x7F, 0x00),  # 1 L
        (0x00, 0x7F, 0x00),  # 2
        (0x00, 0x3F, 0x00),  # 3
        (0x00, 0x1F, 0x00),  # 4
        (0x00, 0x0F, 0x00),  # 5
        (0x00, 0x07, 0x00),  # 6
        (0x00, 0x03, 0x00),  # 7
        (0x00, 0x01, 0x00),  # 8 C
        (0x00, 0x01, 0x40),  # 9
        (0x00, 0x01, 0x60),  # 10
        (0x00, 0x01, 0x70),  # 11
        (0x00, 0x01, 0x78),  # 12
        (0x00, 0x01, 0x7C),  # 13
        (0x00, 0x01, 0x7E),  # 14
        (0x00, 0x01, 0x7F),  # 15 R
    ]
    coarse = float(0.03125)
    fine = float(0.005)

    def __init__(self, track):
        self.log = track.desk.log
        self.track = track
        self.pang = 0
        self.panv = 0,
        self.pan = float(0.5)
        self.cmdbytes_d_c = (c_ubyte * 30)()
        self.cmdbytes = (c_ubyte * 8)()
        for ind, byt in enumerate(
                [0xF0, 0x13, 0x00, 0x00, self.track.track_number & 0x3f, ## changed 0x01 to 0x00 fpr Pro control
                 0x00, 0x00, 0xF7]):
            self.cmdbytes[ind] = byt
            self.cmdbytes_d_c[ind] = byt
        self.osc_address = '/track/c24vpot/{}'.format(
            self.track.track_number + 1)
        self.osc_message = OSC.OSCMessage(self.osc_address)

    def __str__(self):
        return 'Channel:{}, Pan:{}, Pang:{}, Panv:{}, b:{} {} CmdBytes:{}'.format(
            self.track.track_number,
            self.pan,
            self.pang,
            self.panv,
            self.cmdbytes[5],
            self.cmdbytes[6],
            binascii.hexlify(self.cmdbytes)
        )

    def d_c(self, parsedcmd):
        """Desk to Computer. Update from desk command byte list"""
        cbytes = parsedcmd.get('cmdbytes')
        for ind, byt in enumerate(cbytes):
            self.cmdbytes_d_c[ind] = ord(byt)
        self.adj_pan(self)
        self.osc_message.clearData()
        self.osc_message.append(self.pan)
        self.update_led()
        self.track.desk.osc_client_send(self.osc_message)

    def c_d(self, addrlist, stuff):
        """Computer to Desk. Update from DAW pan value (0-1)"""
        pan = stuff[0]
        self.pan = pan
        self.update_led()

    def update_led(self):
        """Update the LED display aroudn the vpot"""

        if self.pan > 0 and self.pan < 1:
            self.panv = self.pan - 0.5
            self.pang = int(self.panv * 16) + 7
        elif self.pan == 0:
            self.panv = -0.5
            self.pang = 0
        elif self.pan == 1:
            self.panv = 0.5
            self.pang = 15
        try:
            led = self.led_value(self.pang)
            self.cmdbytes[4], self.cmdbytes[5], self.cmdbytes[6] = led
            self.cmdbytes[4] = self.cmdbytes[4] | (self.track.track_number & 0x3f)
        except IndexError:
            self.log.warn('VPOT LED lookup failure: %s', self)
        self.track.desk.c24_client_send(self.cmdbytes)
        trace(self.log, 'VPOT LED: %s', self)

    @staticmethod
    def led_value(pang):
        return C24vpot.scale_fill[pang]

    @staticmethod
    def adj_pan(vpot):
        """Increment/decrement the pan factor from command bytes"""

        potdir = vpot.cmdbytes_d_c[2] - 64
        potvel = vpot.cmdbytes_d_c[3]
        if vpot.track.desk.c24modifiers.command:
            amt = vpot.fine
        else:
            amt = vpot.coarse
        adj = potdir * amt
        vpot.pan += adj
        if vpot.pan > 1:
            vpot.pan = 1
        if vpot.pan < 0:
            vpot.pan = 0
        return adj


class C24fader(ReaBase):
    """Class to hold and convert fader value representations"""
    faderscale = ReaBase.calc_faderscale()

    def __init__(self, track):
        self.log = track.desk.log
        self.track = track
        self.gain = None
        self.cmdbytes = (c_ubyte * 5)()
        for ind, byt in enumerate(
                [0xB0, self.track.track_number & 0x1F,
                 0x00, self.track.track_number + 0x20, 0x00]):
            self.cmdbytes[ind] = byt
        self.osc_address = '/track/c24fader/{}'.format(
            self.track.track_number + 1)
        self.osc_message = OSC.OSCMessage(self.osc_address)
        self.last_tick = 0.0
        self.touch_status = False

    def __str__(self):
        return 'Channel:{}, Gain:{}, CmdBytes:{}'.format(
            self.track.track_number,
            self.gain,
            binascii.hexlify(self.cmdbytes)
        )

    def d_c(self, parsedcmd):
        """Desk to Computer. Update from desk command byte list"""

        addr = parsedcmd.get('addresses')
        if addr[1] == 'track':
            self._update_from_fadermove(parsedcmd)
        elif addr[1] == 'button':
            self._update_from_touch(parsedcmd)
        else:
            self.log.warn('Unknown command sent to fader class: %s', parsedcmd)

    def c_d(self, addrlist, stuff):
        """Computer to Desk. Update from DAW gain factor (0-1)"""
        gai = stuff[0]
        self.gain = gai
        self.cmdbytes[3] = 0x20 + self.track.track_number
        self.cmdbytes[2], self.cmdbytes[4] = self.calc_cmdbytes(self)
        self.track.desk.c24_client_send(self.cmdbytes)

    def _update_from_fadermove(self, parsedcmd):

        cbytes = parsedcmd.get('cmdbytes')
        t_in = ord(cbytes[1])
        if t_in != self.track.track_number:
            self.log.error('Track from Command Bytes does not match Track object Index: %s %s',
                           binascii.hexlify(cbytes), self)
            return None
        # TODO tidy up here
        if len(cbytes) < 2:
            self.log.warn('c24fader bad signature %s',
                          parsedcmd)
            return None
        if cbytes[3] == '\x00':
            self.log.warn('c24fader bad signature %s',
                          parsedcmd)
            return None
        self.cmdbytes[2] = ord(cbytes[2])
        self.cmdbytes[4] = ord(cbytes[4])
        self.gain = self.calc_gain(self)
        self.osc_message.clearData()
        self.osc_message.append(self.gain)
        self.track.desk.osc_client_send(self.osc_message)
        if tick() - self.last_tick > TIMING_FADER_ECHO:
            self.track.desk.c24_client_send(self.cmdbytes)
        self.last_tick = tick()

    def _update_from_touch(self, parsedcmd):
        val = parsedcmd.get('Value')
        valb = bool(val)
        if self.touch_status and not valb:
            self.track.desk.c24_client_send(self.cmdbytes)
        self.touch_status = valb

    @staticmethod
    def calc_cmdbytes(fdr):
        """Calculate the command bytes from gain factor"""
        gain_from_daw = fdr.gain
        if gain_from_daw > 1:
            gain_from_daw = 1
        gain_tenbits = int(gain_from_daw * FADER_RANGE) - 1
        if gain_tenbits < 0:
            gain_tenbits = 0
        tenb = ReaBase.tenbits(gain_tenbits)
        return c_ubyte(tenb[0]), c_ubyte(tenb[1])

    @staticmethod
    def calc_gain(fdr):
        """Calculate the gain factor from command bytes"""
        volume_from_desk = (fdr.cmdbytes[2], fdr.cmdbytes[4])
        return C24fader.faderscale[volume_from_desk]


class C24buttonled(ReaBase):
    """ class to tidy up chunk of code from main c_d method
    for turning on/off button LED's """
    mapping_osc = {}
    ReaBase.walk(MAPPING_TREE_PROC.get(0x90).get('Children'),
                 '/button', [0x90, 0x00, 0x00], 1, None, mapping_osc)

    def __init__(self, desk, track):
        self.log = desk.log
        self.desk = desk
        self.track = track
        self.cmdbytes = (c_ubyte * 3)()

    def c_d(self, addrlist, stuff):
        addr = '/'.join(addrlist)
        val = stuff[0]
        self.set_btn(addr, val)

    def set_btn(self, addr, val):

        try:
            lkpbtn = C24buttonled.mapping_osc[addr]
            self.log.debug("Button LED: %s", lkpbtn)
            if not self.track is None:
                tbyt = lkpbtn.get('TrackByte')
            else:
                tbyt = None
            # Copy the byte sequence injecting track number
            for ind, byt in enumerate(lkpbtn['cmdbytes']):
                c_byt = c_ubyte(byt)
                if ind == tbyt and not self.track is None:
                    c_byt.value = c_byt.value | self.track.track_number
                # On or Off
                if ind == 2 and val == 1:
                    c_byt.value = c_byt.value | 0x40
                self.cmdbytes[ind] = c_byt
            trace(self.log, "Button LED cmdbytes: %s", binascii.hexlify(self.cmdbytes))
            self.desk.c24_client_send(self.cmdbytes)
        except KeyError:
            self.log.warn("OSCServer LED not found: %s %s", addr, str(val))


class C24automode(ReaBase):
    """ class to deal with the automation toggle on a track
    with the various LEDs and modes exchanged between DAW and desk"""
    automodes = {
        'write': {'state': False, 'cmd': 0x40},
        'touch': {'state': False, 'cmd': 0x20},
        'latch': {'state': False, 'cmd': 0x10},
        'trim': {'state': False, 'cmd': 0x08},
        'read': {'state': False, 'cmd': 0x04}
    }

    def __init__(self, desk, track):
        self.log = desk.log
        self.desk = desk
        self.track = track
        self.cmdbytes = (c_ubyte * 30)()
        for ind, byt in enumerate(
                [0xF0, 0x13, 0x00, 0x20, self.track.track_number & 0x1F, ## changed from 0x01 to 0x00 for pro control
                 0x00, 0xF7]):
            self.cmdbytes[ind] = byt
        self.modes = dict(self.automodes)

    def __str__(self):
        mods = ['{}:{}'.format(key, value.get('state')) for key, value in self.modes.iteritems()]
        return 'C24automode track:{} byt:{} modes:{} '.format(
            self.track.track_number,
            self.cmdbytes[5],
            mods
        )

    def c_d(self, addrlist, stuff):
        mode_in = addrlist[3]
        mode_onoff = bool(stuff[0])
        self.set_mode(mode_in, mode_onoff)
        self.update_led()

    def d_c(self, parsedcmd):
        val = parsedcmd.get('Value')
        if val == 1:
            first = None
            nxt = False
            moved = False
            for key in self.modes.keys():
                if not first:
                    first = key
                mode = self.modes.get(key)
                if mode.get('state'):
                    self.set_mode(key, False)
                    self.daw_mode(key, False)
                    moved = True
                    nxt = True
                elif nxt:
                    self.set_mode(key, True)
                    self.daw_mode(key, True)
                    nxt = False
            if nxt or not moved:
                self.set_mode(first, True)
                self.daw_mode(first, True)
            self.update_led()

    def daw_mode(self, mode_in, onoff):
        addr = '/track/c24automode/{}/{}'.format(
            mode_in,
            self.track.osctrack_number
        )
        msg = OSC.OSCMessage(addr)
        msg.append('{}.0'.format(onoff * 1))
        self.track.desk.osc_client_send(msg)

    def set_mode(self, mode_in, onoff):
        mode = self.modes.get(mode_in)
        mode['state'] = onoff
        bitv = mode.get('cmd')
        curv = self.cmdbytes[5]
        if onoff and curv & bitv == 0:
            curv += bitv
        elif curv & bitv != 0 and not onoff:
            curv -= bitv
        self.cmdbytes[5] = curv

    def update_led(self):
        """Update the LED display by the auto toggle"""

        self.track.desk.c24_client_send(self.cmdbytes)
        self.log.debug('AUTO LED: %s', self)


# Class for the client session
class ProCoscsession(object):
    mapping_tree = MAPPING_TREE_PROC
    # Extract a list of first level command bytes from the mapping tree
    # To use for splitting up multiplexed command sequences
    splitlist = [key for key in mapping_tree.keys() if key != 0x00]

    @staticmethod
    def itsplit(inlist):
        """child method of cmdsplit"""
        current = []
        for item in inlist:
            if ord(item) == 0xF7:
                current.append(item)
                yield current
                current = []
            elif ord(item) in ProCoscsession.splitlist and not current == []:
                yield current
                current = [item]
            else:
                current.append(item)
        yield current

    @staticmethod
    def cmdsplit(inlist):
        """split input list into sublists when the first byte
        is repeated or terminator F7 byte is encountered"""
        if not inlist:
            return None
        elif inlist[0] == 0x00:
            return inlist

        return [subl for subl in ProCoscsession.itsplit(inlist) if subl]

    @staticmethod
    def parsecmd(cmdbytes):
        """take a byte list split from the packet data and find it in the mapping dict tree"""

        # possibly evil but want to catch these for a more fluid
        # debugging session if they occur a lot
        if not isinstance(cmdbytes, list):
            return {'Name': 'Empty'}
        parsedcmd = {}
        parsedcmd["addresses"] = []
        parsedcmd["cmdbytes"] = cmdbytes
        parsedcmd["lkpbytes"] = []
        this_byte_num = 0
        this_byte = ord(cmdbytes[this_byte_num])
        lkp = ProCoscsession.mapping_tree
        level = 0
        while not this_byte_num is None:
            parsedcmd["lkpbytes"].append(this_byte)
            level = level + 1
            lkp = lkp.get(this_byte)
            if not lkp:
                return None
            # Copy this level's dict entries but not the children subdict. i.e. flatten/accumulate
            if "Address" in lkp:
                parsedcmd["addresses"].append('/')
                parsedcmd["addresses"].append(lkp["Address"])
            parsedcmd.update(
                {key: lkp[key] for key in lkp if "Byte" in key or "Class" in key or "SetMode" in key}
            )
            if 'ChildByte' in lkp:
                this_byte_num = lkp['ChildByte']
                try:
                    this_byte = ord(cmdbytes[this_byte_num])
                except IndexError:
                    return None
                if 'ChildByteMask' in lkp:
                    this_byte = this_byte & lkp['ChildByteMask']
                elif 'ChildByteMatch' in lkp:
                    # TODO there is bound to be a neat bitwise way of doing this
                    match_byte = lkp['ChildByteMatch']
                    if this_byte & match_byte == match_byte:
                        this_byte = match_byte
                    else:
                        this_byte = 0x00
                lkp = lkp['Children']
            else:
                this_byte_num = None

        # Done with the recursive Lookup, now we can derive
        # TODO this is primitive right now around value derivation
        if 'TrackByte' in parsedcmd:
            track_byte = ord(cmdbytes[parsedcmd['TrackByte']])
            if 'TrackByteMask' in parsedcmd:
                track_byte = track_byte & parsedcmd['TrackByteMask']
            tracknumber = int(track_byte)
            parsedcmd["TrackNumber"] = tracknumber
            parsedcmd["addresses"].append('/')
            parsedcmd["addresses"].append('{}'.format(tracknumber + 1))
        if 'DirectionByte' in parsedcmd:
            direction_byte = ord(cmdbytes[parsedcmd['DirectionByte']])
            parsedcmd["Direction"] = int(direction_byte) - 64
        if 'ValueByte' in parsedcmd:
            # Not all commands actually have their value byte
            # specifically dials/jpots. Assume this means 0
            try:
                value_byte = ord(cmdbytes[parsedcmd['ValueByte']])
                if 'ValueByteMask' in parsedcmd:
                    value_byte_mask = parsedcmd['ValueByteMask']
                    value_byte = value_byte & value_byte_mask
                    if value_byte == value_byte_mask:
                        parsedcmd["Value"] = 1.0
                    elif value_byte == 0x00:
                        parsedcmd["Value"] = 0.0
            except IndexError:
                value_byte = 0x00
                parsedcmd["Value"] = 0.0

        parsedcmd["address"] = ''.join(parsedcmd["addresses"])
        return parsedcmd

    # Event methods
    def _desk_to_daw(self, c_databytes):

        trace(self.log, binascii.hexlify(c_databytes))
        commands = ProCoscsession.cmdsplit(c_databytes)
        trace(self.log, 'nc: %d', len(commands))
        for cmd in commands:
            parsed_cmd = ProCoscsession.parsecmd(cmd)
            if parsed_cmd:
                address = parsed_cmd.get('address')
                self.log.debug(parsed_cmd)
                # If we have a track number then get the corresponding object
                track_number = parsed_cmd.get("TrackNumber")
                track = self.desk.get_track(track_number)
                # If map indicates a mode is to be set then call the setter
                set_mode = parsed_cmd.get('SetMode')
                if set_mode:
                    self.desk.mode = set_mode

                # CLASS based Desk-Daw, where complex logic is needed so encap. in class
                cmd_class = parsed_cmd.get('CmdClass')
                if cmd_class is not None:
                    # Most class handlers will be within a track
                    # but if not then try the desk object
                    try:
                        inst = getattr(track or self.desk, cmd_class.lower())
                        # Call the desk_to_computer method of the class
                        inst.d_c(parsed_cmd)
                    except AttributeError:
                        self.log.warn(
                            'Looking for mapped cmd_class but it is not found. The map is incorrect. Track: %d Class: %s',
                            track_number,
                            cmd_class
                        )
                    except:
                        self.log.error(
                            'Error looking up cmd_class. Track: %d Class: %s',
                            track_number,
                            cmd_class,
                            exc_info=True
                        )

                # NON CLASS based Desk-DAW or both
                if address.startswith('/button/track/'):
                    # Channel strip buttons.
                    # We will assume the track object is here already
                    osc_msg = OSC.OSCMessage(address)
                    if not osc_msg is None:
                        self.osc_client_send(osc_msg, parsed_cmd['Value'])
                # ANY OTHER buttons
                # If the Reaper.OSC file has something at this address
                elif address.startswith('/button'):
                    osc_msg = OSC.OSCMessage(address)
                    if not osc_msg is None:
                        self.osc_client_send(osc_msg, parsed_cmd['Value'])

    def _daw_to_desk(self, addr, tags, stuff, source):
        """message handler for the OSC listener"""
        trace(self.log, "Received OSC message")
        self.log.debug("OSC Listener received Message: %s %s [%s] %s",
                       source, addr, tags, str(stuff))
        if self.osc_listener_last is None:
            self.osc_listener_last = source
        elif self.osc_listener_last != source:
            self.log.warn('OSC message received from an unexpected source address %s', source)

        # TODO primitive switching needs a proper lookup map
        addrlist = addr.split('/')
        if 'track' in addrlist:
            track_number = int(addrlist[-1]) - 1
            track = self.desk.get_track(track_number)
            addrlist.pop()
            addr = '/'.join(addrlist)
        else:
            track_number = None
            track = None

        # track based addresses must have the 2nd part
        # of the address equal to the attribute name
        # which should be the class name in lowercase
        cmdinst = None
        if addrlist[1] == 'track':
            cmdinst = getattr(track, addrlist[2])
        elif addrlist[1] == 'clock':
            cmdinst = self.desk.c24clock
        elif addrlist[1] == 'button':
            # button LEDs
            if not track is None:
                cmdinst = track.c24buttonled
            else:
                cmdinst = self.desk.c24buttonled
        else:
            msg_string = "%s [%s] %s" % (addr, tags, str(stuff))
            self.log.warn("C24client unhandled osc address: %s", msg_string)
            return
        cmdinst.c_d(addrlist, stuff)

    # Threaded methods
    def _manage_c24_client(self):
        trace(self.log, 'Daemon client thread starting')
        while not self.is_closing:
            if self.standalone:
                # Poll for a connection, in case server is not up
                self.log.debug('Starting MP client connecting to %s', self.server)
                while self.c24_client is None:
                    try:
                        self.c24_client = Client(
                            self.server, authkey=DEFAULTS.get('auth'))
                    except Exception as exc:
                        # Connection refused
                        if exc[0] == 61:
                            self.log.error(
                                'Error trying to connect to procontrold at %s. May not be running. Will try again.',
                                self.server)
                            time.sleep(TIMING_SERVER_POLL)
                        else:
                            self.log.error(
                                'c24 client Unhandled exception', exc_info=True)
                            raise
            else:
                self.c24_client = self.server_pipe
            self.c24_client_is_connected = True

            # Main Loop when connected
            while self.c24_client_is_connected:
                self.log.debug('MP Client waiting for data: %s',
                               self.c24_client.fileno())
                try:
                    datarecv = self.c24_client.recv_bytes()
                    self._desk_to_daw(datarecv)
                except EOFError:
                    self.log.error('MP Client EOFError: Daemon closed communication.')
                    self.c24_client_is_connected = False
                    self.c24_client = None
                    time.sleep(TIMING_SERVER_POLL)
                except Exception:
                    self.log.error("C24 client Uncaught exception", exc_info=True)
                    raise
        # Close down gracefully
        if self.c24_client_is_connected:
            self.c24_client.close()
            self.c24_client_is_connected = False
        self.log.debug('Daemon client thread finished')

    def _manage_osc_listener(self):
        self.log.debug('OSC listener thread starting')
        self.osc_listener = OSC.OSCServer(
            self.listen)
        # Register OSC Listener handler methods
        self.osc_listener.addDefaultHandlers()
        self.osc_listener.addMsgHandler("default", self._daw_to_desk)

        while not self.is_closing:
            self.log.debug('Starting OSC Listener at %s', self.listen)
            try:
                self.osc_listener.serve_forever()
            except Exception as exc:
                if exc[0] == 9:
                    self.log.debug("OSC shutdown error", exc_info=True)
                else:
                    self.log.error("OSC Listener error", exc_info=True)
                # raise
            self.log.debug('OSC Listener stopped')
            time.sleep(TIMING_OSC_LISTENER_RESTART)
        self.log.debug('OSC listener thread finished')

    def _manage_osc_client(self):
        self.log.debug('OSC client thread starting')
        testmsg = OSC.OSCMessage('/print')
        testmsg.append('hello DAW')

        while not self.is_closing:
            self.osc_client = OSC.OSCClient()
            while self.osc_listener is None or self.osc_listener_last is None or not self.osc_listener.running:
                self.log.debug(
                    'Waiting for the OSC listener to get a client. Last seen was: %s', self.osc_listener_last)
                time.sleep(TIMING_WAIT_OSC_LISTENER)
            try:
                self.log.debug('Starting OSC Client connecting to %s',
                               self.connect)
                self.osc_client.connect(self.connect)
                self.osc_client_is_connected = True
            except Exception:
                self.log.error("OSC Client connection error",
                               exc_info=True)
                self.osc_client_is_connected = False
                time.sleep(TIMING_OSC_CLIENT_RESTART)
            while self.osc_client_is_connected and not self.is_closing:
                trace(self.log, "Sending Test message via OSC Client")
                try:
                    self.osc_client.send(testmsg)
                except OSC.OSCClientError:
                    self.log.error("Sending Test message got an error. DAW is no longer responding.")
                    self._disconnect_osc_client()
                except Exception:
                    self.log.error("OSC Client Unhandled exception", exc_info=True)
                    raise
                time.sleep(TIMING_OSC_CLIENT_LOOP)
            time.sleep(TIMING_OSC_CLIENT_RESTART)
        self.log.debug('OSC client thread finished')

    # common methods for disconnects (starting some tidying and DRY)
    def _disconnect_osc_client(self):
        self.osc_client_is_connected = False
        self.osc_listener_last = None
        self.osc_client.close()
        self.osc_client = None

    def osc_client_send(self, osc_msg, simplevalue=None):
        """dry up the calls to osc client send
        that are wrapped in a connection check"""

        if not simplevalue is None:
            osc_msg.append(simplevalue)
        self.log.debug('OSCClient sending: %s', osc_msg)
        if self.osc_client_is_connected:
            try:
                self.osc_client.send(osc_msg)
            except:
                self.log.error("Error sending OSC msg:",
                               exc_info=sys.exc_info())
                self._disconnect_osc_client()
        else:
            self.log.warn(
                "OSC Client not connected but message send request received: %s", osc_msg)

    def c24_client_send(self, cmdbytes):
        """dry up the calls to the MP send that
        are wrapped in a connection check"""

        if self.c24_client_is_connected:
            trace(self.log, "MP send: %s",
                           binascii.hexlify(cmdbytes))
            self.c24_client.send_bytes(cmdbytes)

    # session housekeeping methods
    def __init__(self, opts, networks, pipe=None):
        """Contructor to build the client session object"""
        self.log = start_logging("procontrolosc", opts.logdir, opts.debug)
        trace(self.log, 'Options %s', str(opts))
        self.desk = ProCdesk(self)
        try:
            self.standalone = pipe is None
            if self.standalone:
                self.server = OSC.parseUrlStr(opts.server)[0]
                self.server_pipe = None
                self.log.debug('procontrolosc Starting up in STANDALONE mode')
            else:
                self.server = None
                self.server_pipe = pipe
                self.log.debug('procontrolosc Starting up in SUBPROCESS mode')
            self.listen = OSC.parseUrlStr(opts.listen)[0]
            self.connect = OSC.parseUrlStr(opts.connect)[0]
            self.osc_listener = None
            self.osc_listener_last = None
            self.osc_client = None
            self.osc_client_is_connected = False
            self.c24_client = None
            self.c24_client_is_connected = False
            self.is_closing = False


            # Start a thread to manage the connection to the procontrold
            self.thread_c24_client = threading.Thread(
                target=self._manage_c24_client,
                name='thread_c24_client'
            )
            # self.thread_c24_client.daemon = True
            self.thread_c24_client.start()

            # Start a thread to manage the OSC Listener
            self.thread_osc_listener = threading.Thread(
                target=self._manage_osc_listener,
                name='thread_osc_listener'
            )
            # self.thread_osc_listener.daemon = True
            self.thread_osc_listener.start()

            # Start a thread to manage the OSC Client
            self.thread_osc_client = threading.Thread(
                target=self._manage_osc_client,
                name='thread_osc_client'
            )
            # self.thread_osc_client.daemon = True
            self.thread_osc_client.start()

            self.thread_c24_client.join()
        except:
            self.log.error('Error in procontrol osc client', exc_info=True)
            raise

    def __str__(self):
        """pretty print session state if requested"""
        return 'procontrol osc session: c24client_is_connected:{}'.format(
            self.c24_client_is_connected
        )

    def close(self):
        """Placeholder if we need a shutdown method"""

        self.log.info("C24oscsession closing")
        # For threads under direct control this signals to please end
        self.is_closing = True
        # For others ask nicely
        if not self.osc_listener is None and self.osc_listener.running:
            self.osc_listener.close()
        self.log.info("C24oscsession closed")

    def __del__(self):
        """Placeholder to see if session object destruction is a useful hook"""

        trace(self.log, "C24oscsession del")
        self.close()


# START main program
def main():
    """Main function declares options and initialisation routine for OSC client."""
    global SESSION

    # Find networks on this machine, to determine good defaults
    # and help verify options
    networks = NetworkHelper()

    default_ip = networks.get_default()[1]

    # program options
    oprs = opts_common("procontrolosc Procontrol OSC client")
    default_daemon = networks.ipstr_from_tuple(default_ip, DEFAULTS.get('daemon'))
    oprs.add_option(
        "-s",
        "--server",
        dest="server",
        help="connect to procontrold at given host:port. default %s" % default_daemon)
    default_osc_client24 = networks.ipstr_from_tuple(default_ip, DEFAULTS.get('procontrolosc'))
    oprs.add_option(
        "-l",
        "--listen",
        dest="listen",
        help="accept OSC client from DAW at host:port. default %s" % default_osc_client24)
    default_daw = networks.ipstr_from_tuple(default_ip, DEFAULTS.get('oscDaw'))
    oprs.add_option(
        "-c",
        "--connect",
        dest="connect",
        help="Connect to DAW OSC server at host:port. default %s" % default_daw)

    oprs.set_defaults(listen=default_osc_client24,
                      server=default_daemon, connect=default_daw)

    # Parse and verify options
    # TODO move to argparse and use that to verify
    (opts, _) = oprs.parse_args()
    if not networks.verify_ip(opts.listen.split(':')[0]):
        raise OptionError('No network has the IP address specified.', 'listen')

    # Set up Interrupt signal handler so process can close cleanly
    for sig in SIGNALS:
        signal.signal(sig, signal_handler)

    # Build the session
    if SESSION is None:
        # start logging if main
        SESSION = ProCoscsession(opts, networks)

    # Main Loop once session initiated
    while True:
        time.sleep(TIMING_MAIN_LOOP)


if __name__ == '__main__':
    from ReaCommon import start_logging

    main()
