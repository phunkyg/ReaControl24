"""ReaControl common functions and default settings"""

import binascii
import datetime
import logging
import optparse
import os
import time
import sys
import signal
import re
import threading
from ctypes import c_ubyte

import netifaces
import OSC

if sys.platform.startswith('win'):
    import _winreg as wr  # pylint: disable=E0401

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

DEFAULTS = {
    'ip': '0.0.0.0',
    'daemon': 9124,
    'control24osc': 9124,
    'oscDaw': 9125,
    'auth': 'be_in-control',
    'loglevel': 'INFO',
    'interface': 'en0',
    'logdir': './logs',
    'logformat': '%(asctime)s\t%(name)s\t%(levelname)s\t' +
                 '%(threadName)s\t%(funcName)s\t%(lineno)d\t%(message)s',
    'timing_scribble_restore': 1
}

COMMANDS = {
    'ack': 0xA0,
    'online': 0xE2
}

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

SIGNALS = [signal.SIGINT, signal.SIGABRT, signal.SIGTERM]

CHANNELS = 24
FADER_RANGE = 2 ** 10
FADER_STEP = 1 / float(FADER_RANGE)


def tick():
    """Wrapper for a common definition of execution seconds"""
    return time.time()


def fix_ownership(path):
    """Change the owner of the file to SUDO_UID"""

    uid = os.environ.get('SUDO_UID')
    gid = os.environ.get('SUDO_GID')
    if uid is not None:
        os.chown(path, int(uid), int(gid))


def trace(logger, msg, *args, **kwargs):
    if logger.isEnabledFor(5):
        logger.log(5, msg, *args, **kwargs)


def start_logging(name, logdir, debug=False):
    """Configure logging for the program
    :rtype:
    """
    # Set logging
    logformat = DEFAULTS.get('logformat')
    loghead = ''.join(c for c in logformat if c not in '$()%')
    # Get the root logger and set up outputs for stderr
    # and a log file in the CWD
    if not os.path.exists(logdir):
        try:
            original_umask = os.umask(0)
            os.makedirs(logdir, 0o666)
            fix_ownership(logdir)
        finally:
            os.umask(original_umask)

    root_logger = logging.getLogger(name)
    # We always want independent loggers
    root_logger.propagate = False
    # Add a custom level for TRACE
    logging.addLevelName(5, "TRACE")
    logging.trace = trace
    logging.Logger.trace = trace
    isTrace = DEFAULTS.get('loglevel') == "TRACE"
    if debug and not isTrace:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(DEFAULTS.get('loglevel'))
    log_f = logging.FileHandler('{}/{}.log.{:%d_%m.%H_%M}.csv'.format(
        logdir,
        name,
        datetime.datetime.now()))
    root_logger.addHandler(log_f)
    # First line be the header
    root_logger.info(loghead)
    # Subsequent lines get formatted
    log_formatter = logging.Formatter(logformat)
    log_f.setFormatter(log_formatter)

    # for now only the main process will log to the terminal
    if name == '__main__':
        log_s = logging.StreamHandler()
        root_logger.addHandler(log_s)
    return root_logger


def opts_common(desc):
    """Set up an opts object with options we use everywhere"""
    fulldesc = desc + """
        part of ReaControl24  Copyright (c)2018 Phase Walker 
        This program comes with ABSOLUTELY NO WARRANTY;
        This is free software, and you are welcome to redistribute it
        under certain conditions; see COPYING.md for details."""
    oprs = optparse.OptionParser(description=fulldesc)
    oprs.add_option(
        "-d",
        "--debug",
        dest="debug",
        action="store_true",
        help="logger should use debug level. default = off / INFO level")
    logdir = DEFAULTS.get('logdir')
    oprs.add_option(
        "-o",
        "--logdir",
        dest="logdir",
        help="logger should create dir and files here. default = %s" % logdir)
    oprs.set_defaults(debug=False, logdir=logdir)
    return oprs


def findintree(obj, key):
    # TODO see if this will save having to
    # code button addresses twice
    if key in obj: return obj[key]
    for _, v in obj.items():
        if isinstance(v, dict):
            item = findintree(v, key)
            if item is not None:
                return item


def hexl(inp):
    """Convert to hex string using binascii but
    then pretty it up by spacing the groups"""
    shex = binascii.hexlify(inp)
    return ' '.join([shex[i:i + 2] for i in range(0, len(shex), 2)])


class NetworkHelper(object):
    """class to contain network related helpful methods
    and such to be re-used where needed"""

    def __init__(self):
        self.networks = NetworkHelper.list_networks()

    def __str__(self):
        """return a nice list"""
        return '\n'.join(['{} {}'.format(
            key,
            data.get('name') or '')
            for key, data in self.networks.iteritems()])

    def get_default(self):
        """return the name and first ip of whichever adapter
        is marked as default"""
        default = [key for key, data in self.networks.iteritems() if data.has_key('default')]
        if default:
            def_net = default[0]
            def_ip = self.networks[def_net].get('ip')[0].get('addr')
            return def_net, def_ip
        return None

    def get(self, name):
        """get the full entry for a network by name
        but also look by friendly name if not an adapter name"""
        if self.networks.has_key(name):
            return self.networks[name]
        results = [key for key, data in self.networks.iteritems() if data.get('name') == name]
        if results:
            return self.networks[results[0]]
        return None

    def verify_ip(self, ipstr):
        """search for an adapter that has the ip address supplied"""
        for key, data in self.networks.iteritems():
            if data.has_key('ip'):
                for ipaddr in data['ip']:
                    if ipaddr.get('addr') == ipstr:
                        return key
        return None

    @staticmethod
    def get_ip_address(ifname):
        """Use netifaces to retrieve ip address, but handle if it doesn't exist"""
        try:
            addr_l = netifaces.ifaddresses(ifname)[netifaces.AF_INET]
            return [{k: v.encode('ascii', 'ignore')
                     for k, v in addr.iteritems()}
                    for addr in addr_l]
        except KeyError:
            return None

    @staticmethod
    def get_mac_address(ifname):
        """Use netifaces to retrieve mac address, but handle if it doesn't exist"""
        try:
            addr_l = netifaces.ifaddresses(ifname)[netifaces.AF_LINK]
            addr = addr_l[0].get('addr')
            return addr.encode('ascii', 'ignore')
        except KeyError:
            return None

    @staticmethod
    def list_networks_win(networks):
        """Windows shim for list_networks. Also go to the registry to
        get a friendly name"""
        reg = wr.ConnectRegistry(None, wr.HKEY_LOCAL_MACHINE)
        reg_key = wr.OpenKey(
            reg,
            r'SYSTEM\CurrentControlSet\Control\Network\{4D36E972-E325-11CE-BFC1-08002BE10318}'
        )
        for key, val in networks.iteritems():
            val['pcapname'] = '\\Device\\NPF_{}'.format(key)
            net_regkey = r'{}\Connection'.format(key)
            try:
                net_key = wr.OpenKey(reg_key, net_regkey)
                # Probably need to filter on MediaSubType here to only ask for ethernet
                net_name = wr.QueryValueEx(net_key, 'Name')[0]
                if net_name:
                    val['name'] = net_name
            except WindowsError:  # pylint: disable=E0602
                pass
        wr.CloseKey(reg_key)
        return networks

    @staticmethod
    def list_networks():
        """Gather networks info via netifaces library"""
        default_not_found = True
        names = [a.encode('ascii', 'ignore') for a in netifaces.interfaces()]
        results = {}
        for interface in names:
            inner = {
                'pcapname': interface,
                'mac': NetworkHelper.get_mac_address(interface)
            }
            # ip
            ips = NetworkHelper.get_ip_address(interface)
            if ips:
                inner['ip'] = ips
                if default_not_found and any([ip.has_key('addr') and not ip.has_key('peer') for ip in ips]):
                    default_not_found = False
                    inner['default'] = True
            results[interface] = inner
        if sys.platform.startswith('win'):
            return NetworkHelper.list_networks_win(results)
        return results

    @staticmethod
    def ipstr_to_tuple(ipstr):
        ipsplit = ipstr.split(':')
        return (ipsplit[0], int(ipsplit[1]))

    @staticmethod
    def ipstr_from_tuple(ipaddr, ipport):
        """from ip and port provide a string with ip:port"""
        return '{}:{}'.format(ipaddr, ipport)

    @staticmethod
    def is_valid_ipstr(ipstr):
        """check if a string conforms to the expected ipv4 and port format"""
        pat = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]):[0-9]+$"
        return bool(re.findall(pat, ipstr))


# Helper classes to apply standard functionality to Rea classes
class ModeManager(object):
    """Mode managers encapsulate stateful mode switching and toggling
    functionality. Instantiate one into another class to provide
    that functionality"""

    def __init__(self, modesdict):
        """Build a mode manager from a dict containing the possible modes
        each with a value of a child dict containing any required data items.
        If the data contains a key 'default' then that will set the initial mode
        otherwise one will be chosen arbitrarily
        """
        # Only accept a dict as the constructor parameter
        if not isinstance(modesdict, dict):
            raise ValueError(
                "A dict of modes, with subdict of data for each with address was expected."
            )
        self.modes = dict(modesdict)
        self.modeslist = list(modesdict.keys())
        self.numberofmodes = len(self.modeslist)
        # Iterate to find the default and also
        # build / init anything needed along the way:
        #  - Create an OSC message for any address
        self.mode = None
        first = None
        for key, value in self.modes.iteritems():
            if first is None:
                first = key
            # Construct an OSC message for each address
            if value.has_key('address'):
                value['msg'] = OSC.OSCMessage(value['address'])
            if value.get('default'):
                self.mode = key
        if self.mode is None:
            self.mode = first

    def set_mode(self, mode):
        """directly set the mode to the key requested"""
        if self.is_valid_mode(mode):
            self.mode = mode
        else:
            self.modes[mode] = {'Address': mode}
            raise IndexError("That mode does not exist.")

    def is_valid_mode(self, mode):
        """Boolean test to ensure mode is currently in the
        list of valid modes"""
        return self.modes.has_key(mode)

    def toggle_mode(self):
        """set the mode to the next one in order of the original
        dict passed"""
        thiskeyindex = self.modeslist.index(self.mode)
        if thiskeyindex < self.numberofmodes - 1:
            self.mode = self.modeslist[thiskeyindex + 1]
        else:
            self.mode = self.modeslist[0]

    def get_data(self):
        """return the whole data dict for the current mode"""
        return self.modes.get(self.mode)

    def get(self, key):
        """ pass through method to current mode data dict get"""
        return self.modes.get(self.mode).get(key)

    def get_msg(self):
        """return only the OSC message for the current mode"""
        currmode = self.get_data()
        msg = currmode.get('msg')
        if msg:
            msg.clearData()
            return msg
        else:
            return None


'''
 OSC Classes used in multiple device OSC handlers.
'''


class ReaBase(object):
    """base class to make available standard functions"""

    @staticmethod
    def initbytes(bytelist):
        """load the command byte array with
        a list of initial values"""
        cmdlength = len(bytelist)
        retbytes = (c_ubyte * cmdlength)()
        for ind, byt in enumerate(bytelist):
            retbytes[ind] = byt
        return retbytes

    @staticmethod
    def parsedcmd_simplebutton(parsedcmd):
        """from a parsedcmd, extract the last address and value"""
        # TODO investigate if a parsed command class is the way to go instead
        return parsedcmd.get('addresses')[-1], parsedcmd.get('Value')

    @staticmethod
    def tenbits(num):
        """Return 7 bits in one byte and 3 in the next for an integer provided"""
        num = num & 0x3FF
        return (num >> 3, (num & 7) << 4)

    @staticmethod
    def calc_faderscale():
        """Return a dict that converts tenbit 7 bit pair into gain factor 0-1"""
        fader_range = 2 ** 10
        fader_step = 1 / float(fader_range)
        return {ReaBase.tenbits(num): num * fader_step for num in range(0, fader_range)}

    @staticmethod
    def walk(node, path, byts, cbyt, tbyt, outp):
        """Walk the mapping tree picking off the LED
        buttons, and inverting the sequence.
        Basically because too lazy to hand write a second
        map and keep them in step"""
        mybyts = list(byts)
        for key, item in node.items():
            addr = item.get('Address', '')
            kids = item.get('Children')
            kbyt = item.get('ChildByte')
            if tbyt is None:
                tbyt = item.get('TrackByte')
            led = item.get('LED')
            tog = item.get('Toggle')
            if not kids is None:
                kidbyts = list(mybyts)
                kidbyts[cbyt] = key
                ReaBase.walk(kids, path + '/' + addr, kidbyts, kbyt, tbyt, outp)
            else:
                if addr != '' and led:
                    leafbyts = list(mybyts)
                    leafbyts[cbyt] = key
                    opr = {
                        'cmdbytes': leafbyts
                    }
                    if tog:
                        opr['Toggle'] = tog
                    if not tbyt is None:
                        opr['TrackByte'] = tbyt
                    outp[path + '/' + addr] = opr


class ReaNav(ReaBase):
    """Class to manage the desk navigation section
    and cursor keys with 3 modes going to different
    OSC addresses"""
    # TODO look up the addresses instead of double coding them here
    # probably from the existing MAPPING_OSC
    navmodes = {
        'Nav': {
            'address': '/button/command/Window+ZoomPresets+Navigation/Nav',
            'osc_address': '/scroll/',
            'default': True
        },
        'Zoom': {
            'address': '/button/command/Window+ZoomPresets+Navigation/Zoom',
            'osc_address': '/zoom/'
        },
        'SelAdj': {
            'address': '/button/command/Window+ZoomPresets+Navigation/SelAdj',
            'osc_address': '/fxcursor/'
        }
    }

    def __init__(self, desk):
        self.log = desk.log
        self.desk = desk
        # Global / full desk level modes and modifiers
        self.modemgr = ModeManager(self.navmodes)
        # TODO look how we can deal with arrival of a desk
        # and the need to initialise things like the NAV
        # button controlled by this class

    def d_c(self, parsedcmd):
        """Respond to desk buttons mapped to this class"""
        button, val = self.parsedcmd_simplebutton(parsedcmd)
        if self.modemgr.is_valid_mode(button):
            if val == 1:
                self.modemgr.set_mode(button)
                self.update()
        else:  # remainder is the cursors mapped to class
            addr = self.modemgr.get('osc_address') + button
            msg = OSC.OSCMessage(addr)
            self.desk.osc_client_send(msg, val)

    def update(self):
        """Update button LEDs"""
        for key, val in self.modemgr.modes.iteritems():
            addr = val.get('address')
            butval = int(key == self.modemgr.mode)
            self.desk.c24buttonled.set_btn(addr, butval)


class ReaModifiers(ReaBase):
    """Class to hold current state of press and release modifier
    keys"""

    def __init__(self, desk):
        self.log = desk.log
        self.desk = desk
        self.shift = False
        self.option = False
        self.control = False
        self.command = False

    def d_c(self, parsedcmd):
        """Respond to whichever button is mapped to the
        class and set the attribute state accordingly"""
        button, val = self.parsedcmd_simplebutton(parsedcmd)
        button = button.lower()
        if hasattr(self, button):
            setattr(self, button, bool(val))


class ReaClock(ReaBase):
    """Class to hold and convert clock display value representations"""

    # 8 segments
    # Displays seems to all be 0xf0, 0x13, 0x01
    # 0xf0, 0x13, 0x01 = Displays
    # 0x30, 0x19       = Clock display
    # 0xFF             = DOT byte
    # 0x00 x 8         = Display bytes
    # 0xf7             = terminator
    # seven segment display decoding, seven bits (128 not used)
    # 631
    # 4268421
    # TTBBBT
    # RR LLM

    sevenseg = {
        '0': 0b1111110,
        '1': 0b0110000,
        '2': 0b1101101,
        '3': 0b1111001,
        '4': 0b0110011,
        '5': 0b1011011,
        '6': 0b1011111,
        '7': 0b1110000,
        '8': 0b1111111,
        '9': 0b1111011,
        '-': 0b0000001,
        ' ': 0,
        'L': 0x0E,
        'h': 0x17,
        'o': 0x1D,
        'b': 0x1F,
        'H': 0x37,
        'J': 0x38,
        'Y': 0x3B,
        'd': 0x3D,
        'U': 0x3E,
        'R': 0x46,
        'F': 0x47,
        'C': 0x4E,
        'E': 0x4F,
        'S': 0b1011011,
        'P': 0x67,
        'Z': 0b1101101,
        'A': 0x77
    }

    clockbytes = [0xf0, 0x13, 0x01, 0x30, 0x19, 0x00, 0x01,
                  0x46, 0x4f, 0x67, 0x77, 0x4f, 0x46, 0x01, 0xf7]
    ledbytes = [0xF0, 0x13, 0x01, 0x20, 0x19, 0x00, 0xF7]

    clockmodes = {
        'time': {
            'address': '/clock/time',
            'dots': 0b0010101,
            'LED': 0x40,
            'formatter': '_fmt_time'
        },
        'frames': {
            'address': ' /clock/frames',
            'dots': 0b0101010,
            'LED': 0x20,
            'formatter': '_fmt_time'
        },
        'samples': {
            'address': ' /clock/samples',
            'dots': 0x00,
            'LED': 0x10,
            'formatter': '_fmt_default'
        },
        'beat': {
            'address': ' /clock/beat',
            'dots': 0b0010100,
            'LED': 0x08,
            'default': True,
            'formatter': '_fmt_beat'
        }
    }

    @staticmethod
    def _xform_txt(text):
        """transform the input text to seven segment encoding"""
        psn = len(text) - 1
        opr = 0
        while opr < 8 and psn >= 0:
            this_chr = ReaClock.sevenseg.get(text[psn])
            psn -= 1
            if not this_chr is None:
                yield this_chr
                opr += 1
        while opr < 8:
            yield 0x00
            opr += 1

    @staticmethod
    def _fmt_beat(text):
        """formatter for beat text"""
        if text[-5] == '.':
            return ''.join([text[:-4], ' ', text[-4:], ' '])
        else:
            return ''.join([text, ' '])

    @staticmethod
    def _fmt_time(text):
        """formatter for time text"""
        return text[-13:]

    @staticmethod
    def _fmt_default(text):
        return ''.join([text, ' '])

    def __init__(self, desk):
        self.log = desk.log
        self.desk = desk
        self.text = {}
        self.op_list = None
        self.byt_list = None
        self.modemgr = ModeManager(self.clockmodes)
        self.cmdbytes = self.initbytes(self.clockbytes)
        self.ledbytes = self.initbytes(self.ledbytes)
        self._set_things()

    def __str__(self):
        return 'Text:{}, CmdBytes:{}'.format(
            self.text,
            binascii.hexlify(self.cmdbytes)
        )

    def _set_things(self):
        self.cmdbytes[5] = self.modemgr.get('dots')
        self.ledbytes[5] = self.modemgr.get('LED')
        self.formatter = getattr(self, self.modemgr.get('formatter'))

    def _update(self):
        # Apply whichever formatter function is indicated

        optext = self.formatter(self.text[self.modemgr.mode])
        # For now, display whatever mode we last gotfrom the daw
        self.op_list = self._xform_txt(optext)
        self.byt_list = list(self.op_list)
        self.cmdbytes[6:14] = [byt for byt in self.byt_list]
        self.desk.c24_client_send(self.cmdbytes)

    def d_c(self, parsedcmd):
        """Toggle the mode"""
        if parsedcmd.get('Value') == 1.0:
            self.modemgr.toggle_mode()
            self._set_things()
            self.desk.c24_client_send(self.ledbytes)
            self._update()

    def c_d(self, addrlist, stuff):
        """Update from DAW text"""
        mode = addrlist[2]
        self.text[mode] = stuff[0]
        # for speed we simply ignore any osc message that isn't
        # for the current mode.
        if mode == self.modemgr.mode:
            self._update()


class ReaButtonLed(ReaBase):
    """ class to tidy up chunk of code from main c_d method
    for turning on/off button LED's """

    def __init__(self, desk, track):
        self.log = desk.log
        self.desk = desk
        self.track = track
        self.cmdbytes = (c_ubyte * 3)()
        self.states = {}
        self.mapping_osc = {}
        ReaBase.walk(desk.mapping_tree.get(0x90).get('Children'),
                     '/button', [0x90, 0x00, 0x00], 1, None, self.mapping_osc)

    def c_d(self, addrlist, stuff):
        """computer to desk handler"""
        addr = '/'.join(addrlist)
        val = stuff[0]
        self.set_btn(addr, val)

    def d_c(self, parsedcmd):
        """desk to computer handler"""
        addr = parsedcmd.get('address')
        val = parsedcmd.get('Value')
        valr = self.set_btn(addr, val)
        if not valr is None:
            osc_msg = OSC.OSCMessage(addr)
            self.desk.osc_client_send(osc_msg, valr)

    def set_btn(self, addr, val):
        """set button value"""
        try:
            lkpbtn = self.mapping_osc[addr]
            self.log.debug("Button LED: %s", lkpbtn)
            if not self.track is None:
                tbyt = lkpbtn.get('TrackByte')
            else:
                tbyt = None
            tog = lkpbtn.get('Toggle')
            if (tog and val == 1) or not tog:
                if tog:
                    vals = self.toggle_state(addr)
                else:
                    vals = val
                # Copy the byte sequence injecting track number
                for ind, byt in enumerate(lkpbtn['cmdbytes']):
                    c_byt = c_ubyte(byt)
                    if ind == tbyt and not self.track is None:
                        c_byt.value = c_byt.value | self.track.track_number
                    # On or Off
                    if ind == 2 and vals == 1:
                        c_byt.value = c_byt.value | 0x40
                    self.cmdbytes[ind] = c_byt
                self.log.debug("Button LED cmdbytes: %s", binascii.hexlify(self.cmdbytes))
                self.desk.c24_client_send(self.cmdbytes)
                return vals
        except KeyError:
            self.log.warn("OSCServer LED not found: %s %s", addr, str(val))
        return None

    def toggle_state(self, addr):
        """toggle between on and off states"""
        state = self.states.get('addr') or 0.0
        if state == 0.0:
            state = 1.0
        else:
            state = 0.0
        self.states[addr] = state
        return state


class ReaVumeter(ReaBase):
    """Class to hold and convert VU meter value representations"""

    # 0xf0, 0x13, 0x01 = display
    # 0x10 - VUs
    # 0-23 Left
    # 32-55  Right
    # 24-> bus left  - need to check this against procontrol
    # 56-> bus right - need to check this against procontrol
    # 0x00 MSB
    # 0x00 LSB
    # 0xf7 terminator
    meterscale = [
        (0, 0),
        (0, 1),
        (0, 3),
        (0, 7),
        (0, 15),
        (0, 31),
        (0, 63),
        (0, 127),
        (1, 127),
        (3, 127),
        (7, 127),
        (15, 127),
        (31, 127),
        (63, 127),
        (127, 127)
    ]

    def __init__(self, track):
        self.log = track.desk.log
        self.track = track
        self.vu_val = {'postfader': [(0, 0), (0, 0)], 'prefader': [
            (0, 0), (0, 0)]}
        self.mode = 'postfader'
        self.cmdbytes = (c_ubyte * 8)()

        for ind, byt in enumerate([0xf0, 0x13, 0x01, 0x10, track.track_number, 0x7f, 0x7f, 0xf7]):
            self.cmdbytes[ind] = byt

    def __str__(self):
        return 'vu_val:{}, mode: {}, CmdBytes:{}'.format(
            self.vu_val,
            self.mode,
            binascii.hexlify(self.cmdbytes)
        )

    def c_d(self, addrlist, stuff):
        """Update from DAW value"""
        spkr = int(addrlist[3])
        val = stuff[0]
        mode = 'postfader'

        self.mode = mode
        this_val = self.vu_val.get(mode)
        if not this_val is None:
            new_val = self._xform_vu(val)  # take a copy before change
            if new_val != this_val[spkr]:
                this_val[spkr] = new_val
                # For now, display whatever mode we last gotfrom the daw
                self.cmdbytes[4] = 32 * spkr + self.track.track_number
                self.cmdbytes[5], self.cmdbytes[6] = this_val[0]
                self.track.desk.c24_client_send(self.cmdbytes)

    @staticmethod
    def _xform_vu(val):
        return ReaVumeter.meterscale[int(val * 15)]


'''
 OSC Abstract Base Classes used in multiple device OSC handlers
 but with local / specific versions for the device
'''


class _ReaDesk(ReaBase):
    """Class to represent the desk, state and
    instances to help conversions and behaviour
    This base class must be inherited and made
    specific to the device
    """

    def __init__(
            self,
            parent  # type: ReaOscSession
    ):
        """ Base init only builds common elements """
        # passthrough methods
        self.osc_client_send = parent.osc_client_send
        self.daemon_client_send = parent.c24_client_send
        self.log = parent.log
        # Set up the child track objects

        """ Currently standardised Properties"""
        self.reaclock = ReaClock(self)
        self.reanav = ReaNav(self)
        self.reamodifiers = ReaModifiers(self)

        """ Abstract Properties """
        # The mapping tree for this device
        self.mapping_tree = None  # type: Dict
        # This desk will need a ModeManager object but will have a specific
        # set of deskmodes depending on the device
        self.modemgr = None  # type: ModeManager
        # How many channel strips does this device have
        self.channels = None  # type: int
        # How many viruital channel device have in the address space above real channels
        self.virtual_channels = None  # type: int
        # How manuy BUS VU led banks does this device have
        self.busvus = None  # type: int
        # List of Track objects
        self.tracks = []  # type: List[ReaTrack]
        # Button LED class depends on the mapping tree so must be done by inheritor
        self.reabuttonled = None  # type: ReaButtonLed

    def set_mode(self, mode):
        """set the global desk mode"""
        self.debug('Desk mode set: %s', mode)
        self.modemgr.set_mode(mode)
        for track in self.tracks:
            track.modemgr.set_mode(mode)
            if hasattr(track, 'reascribstrip'):
                track.reascribstrip.restore_desk_display()

    def get_track(self, track):
        """Safely access both the main tracks and any virtual
        ones in the address above real tracks """
        if track is None:
            return None
        try:
            return self.tracks[track]
        except IndexError:
            self.log.warn("No track object exists on this desk with index %d", track)
            return None

    def long_scribble(self, longtext):
        """write a long message using ALL the scribble strips
        as a long alphanumeric display"""
        for track_number, track in enumerate(self.tracks):
            if hasattr(track, 'reascribstrip'):
                scrib = track.reascribstrip
                psn = track_number * scrib.size
                piece = longtext[psn:psn + scrib.size]
                scrib.c_d(['rea4scribstrip', 'long'], [piece])

    def instantiate_tracks(self, track_class, number):
        """Build the tracks list out of the supplied class
        and to the length specified"""
        # Set up the child track objects
        # At the moment all are created equal
        self.tracks = [track_class(self, track_number)
                       for track_number in range(0, self.channels + self.virtual_channels)]


class _ReaTrack(ReaBase):
    """Track (channel strip) object to contain
    one each of the bits found in each of the 24 main tracks"""

    def __init__(self, desk, track_number):
        self.desk = desk
        self.log = desk.log
        self.track_number = track_number
        self.osctrack_number = track_number + 1
        self.modemgr = ModeManager(self.desk.modemgr.modes)

        # Only channel strip setup common to all devices goes here
        if self.track_number < self.desk.channels:
            self.fader = ReaFader(self)
            self.vpot = ReaVpot(self)
            self.vumeter = ReaVumeter(self)
            self.buttonled = ReaButtonLed(self.desk, self)
            self.automode = ReaAutoMode(self.desk, self)


class _ReaScribStrip(ReaBase):
    """Class to hold and convert scribblestrip value representations
    This abstract class to hold common elements but specifics
    like number of chars and multiple banks belong to the
    device specific classes"""
    # TODO original control 24 notes - need updating
    # 0xf0, 0x13, 0x01 = Displays
    # 0x40      = Scribble strip
    # 0x00             = track/strip
    # 0x00      = ?
    # 0x00, 0x00, 0x00, 0x00 = 4 'ascii' chars to display
    # 0xf7             = terminator

    def __init__(self, track, digits, bank, defaultaddress='/track/number'):
        self.track = track
        self.log = track.desk.log
        self.digits = digits
        self.bank = bank
        self.mode = track.modemgr.get_data()
        defaulttext = '{num:02d}'.format(num=self.track.osctrack_number)
        self.dtext = defaulttext

        self.numbytes = self.digits + 7;
        self.cmdbytes = (c_ubyte * self.numbytes)()


        self.last_update = time.time()

        # Set up the byte array for initial popn
        bytes = [0xf0, 0x13, 0x01, 0x40, self.track.track_number] + ([0x00] * self.digits) + [0xf7]
        # Copy to the ctypes bytes
        for ind, byt in enumerate(bytes):
            self.cmdbytes[ind] = byt

        # Initialise the text dictionary with a default element
        # It should get overwritten once this OSC address is
        # populated by the DAW.
        self.text = {defaultaddress: defaulttext}

        # Set up timer details for temporary values display returning
        # to the current mode display after a few seconds
        self.timing_restore = float(DEFAULTS.get('timing_scribble_restore'))
        self.make_timer()

    def __str__(self):
        return 'Channel:{}, Bank:{}, Text:{}, CmdBytes:{}'.format(
            self.track,
            self.bank,
            self.text,
            binascii.hexlify(self.cmdbytes)
        )

    def make_timer(self):
        """ Set up the timer thread object """
        self.restore_timer = threading.Timer(
            self.timing_restore, self.restore_desk_display)

    def set_current_display(self):
        """ Given the current state do the text transform
        and send the data to the desk scribble strip """
        self.transform_text()
        self.cmdbytes[6:self.digits+6] = [ord(thischar) for thischar in self.dtext]
        trace(self.log, 'ScribbleStrip mode state: %s = %s',
                self.mode, self.dtext)
        # Trigger the update to be sent from the daemon to the desk
        self.track.desk.daemon_client_send(self.cmdbytes)

    def restore_desk_display(self):
        """ To be called in a delayed fashion
        to restore channel bar display to desk default"""
        # TODO currently the mode is owned by the track class
        # but it mightbe more appropriate to move it into this class
        # for multiple banks etc.
        self.mode = self.track.desk.modemgr.get_data().get('address')
        self.set_current_display()

    def transform_text(self):
        """ Change the raw text sent from the daw at the
         current mode (address) into a suitable string """
        dtext = self.text.get(self.mode)
        if dtext is not None:
            # The desk has neat single characters with a dot and small numeral,
            # Which is nice because 1 char is saved
            # but only 1-9, so 0 (46) is left as a dot
            dpp = dtext.find('.')
            if dpp == 3:
                nco = ord(dtext[dpp + 1])
                if nco != 48:
                    little = chr(nco - 26)
                    dtext = dtext[:dpp] + little + dtext[dpp + 1:]
            fmtstring = '{txt: <'+str(self.digits)+'}'
            self.dtext = fmtstring.format(txt=dtext[:self.digits])
        else:
            # send all spaces to blank it out
            self.dtext = ' ' * self.digits

    def c_d(self, addrlist, stuff):
        """Update from DAW text"""
        address = '/'.join(addrlist)
        textvalue = stuff[0]
        self.text[address] = textvalue
        if address == self.mode:
            self.set_current_display()
        else:
            # We got something that wasn't the current mode
            # so at the moment just store it
            # and display that temporarily
            # What comes here is therefore controlled
            # by the OSC mapping
            self.mode = address
            self.set_current_display()
            if self.restore_timer.isAlive:
                self.restore_timer.cancel()
            self.make_timer()
            self.restore_timer.start()
