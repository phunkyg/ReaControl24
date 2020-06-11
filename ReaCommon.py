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
from multiprocessing.connection import Client

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
    'oscport': 9124,
    'oscDaw': 9125,
    'auth': 'be_in-control',
    'loglevel': 'INFO',   # 'TRACE' here will activate deep debugging
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


def start_logging(name, logdir, debug=False, tostdout=True):
    """Configure logging for the program
    :rtype:
    """
    # Set logging
    logformat = DEFAULTS.get('logformat')
    loghead = ''.join(c for c in logformat if c not in '$()%')
    # Get the root logger and set up outputs for stderr
    # and a log file in the CWD
    if not os.path.exists(logdir):
        original_umask = None
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
    is_trace = DEFAULTS.get('loglevel') == "TRACE"
    if debug and not is_trace:
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

    # If param set then send to screen too
    if tostdout:
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
    if key in obj:
        return obj[key]
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


class ReaException(Exception):
    """Custom exception to use when there is an internal problem"""
    pass


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
        pat = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\\.)" +\
              "{3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]):[0-9]+$"
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
        return num >> 3, (num & 7) << 4

    @staticmethod
    def calc_faderscale():
        """Return a dict that converts tenbit 7 bit pair into gain factor 0-1"""
        fader_range = 2 ** 10
        fader_step = 1 / float(fader_range)
        return {ReaBase.tenbits(num): num * fader_step for num in range(0, fader_range)}




class ReaNav(ReaBase):
    """Class to manage the desk navigation section
    and cursor keys with 3 modes going to different
    OSC addresses"""
    # TODO look up the addresses instead of double coding them here
    # probably from the existing MAPPING_OSC
    navmodes = {
        'Nav': {
            'address': '/button/command/Window+ZoomPresets+Navigation/Nav',
            'osc_address': '/reanav/scroll/',
            'default': True
        },
        'Zoom': {
            'address': '/button/command/Window+ZoomPresets+Navigation/Zoom',
            'osc_address': '/reanav/zoom/'
        },
        'SelAdj': {
            'address': '/button/command/Window+ZoomPresets+Navigation/SelAdj',
            'osc_address': '/reanav/fxcursor/'
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

    def c_d(self, addrlist, stuff):
        """Respond to anything coming from the DAW"""
        self.log.warn('ReaNav does not yet implement c_d. Recieved %s', str(addrlist))
        pass

    def update(self):
        """Update button LEDs"""
        for key, val in self.modemgr.modes.iteritems():
            addr = val.get('address')
            butval = int(key == self.modemgr.mode)
            self.desk.reabuttonled.set_btn(addr, butval)


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
        self.desk.daemon_client_send(self.cmdbytes)

    def d_c(self, parsedcmd):
        """Toggle the mode"""
        if parsedcmd.get('Value') == 1.0:
            self.modemgr.toggle_mode()
            self._set_things()
            self.desk.daemon_client_send(self.ledbytes)
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

    @staticmethod
    def walk(node, path, byts, cbyt, tbyt, outp):
        """Walk the mapping tree picking off the LED
        buttons, and inverting the sequence.
        Basically because too lazy to hand write a second
        map and keep them in step"""
        mybyts = list(byts)
        for key, item in node.items():
            addr = item.get('Address', '')
            # assume track token will be followed by track number
            if addr == 'track':
                addr += '/@'
            kids = item.get('Children')
            kbyt = item.get('ChildByte')
            if tbyt is None:
                tbyt = item.get('TrackByte')
            led = item.get('LED')
            tog = item.get('Toggle')
            if kids is not None:
                kidbyts = list(mybyts)
                kidbyts[cbyt] = key
                ReaButtonLed.walk(kids, path + '/' + addr, kidbyts, kbyt, tbyt, outp)
            else:
                if addr != '' and led:
                    leafbyts = list(mybyts)
                    leafbyts[cbyt] = key
                    opr = {
                        'cmdbytes': leafbyts
                    }
                    if tog:
                        opr['Toggle'] = tog
                    if tbyt is not None:
                        opr['TrackByte'] = tbyt
                    outp[path + '/' + addr] = opr

    def __init__(self, desk, track):
        if track is None:
            self.log = desk.log
        else:
            self.log = track.log
        self.desk = desk
        self.track = track
        self.cmdbytes = (c_ubyte * 3)()
        self.states = {}
        self.mapping_osc = {}
        ReaButtonLed.walk(desk.mapping_tree.get(0x90).get('Children'),
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
        # First transform entirely numeric address elements to @
        lkpaddr = '/'.join(['@' if unicode(ad).isnumeric() else ad for ad in addr.split('/')])
        try:
            lkpbtn = self.mapping_osc[lkpaddr]
            self.log.debug("Button LED: %s %s", lkpaddr, lkpbtn)
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
                    if ind == tbyt and self.track is not None:
                        c_byt.value = c_byt.value | self.track.track_number
                    # On or Off
                    if ind == 2 and vals == 1:
                        c_byt.value = c_byt.value | 0x40
                    self.cmdbytes[ind] = c_byt
                self.log.debug("Button LED cmdbytes: %s", binascii.hexlify(self.cmdbytes))
                self.desk.daemon_client_send(self.cmdbytes)
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
        spkr = int(addrlist[-1])
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
                self.track.desk.daemon_client_send(self.cmdbytes)

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

    def __init__(self, parent):
        """ Base init only builds common elements """
        # passthrough methods
        self.osc_client_send = parent.osc_client_send
        self.daemon_client_send = parent.daemon_client_send
        self.log = parent.log
        # Set up the child track objects

        """ Currently standardised Properties"""
        self.clock = ReaClock(self)
        self.reanav = ReaNav(self)
        self.reamodifiers = ReaModifiers(self)

        """ Abstract Properties """
        # The mapping tree for this device
        self.mapping_tree = None
        # This desk will need a ModeManager object but will have a specific
        # set of deskmodes depending on the device
        self.modemgr = None
        # How many channel strips does this device have
        self.real_channels = None
        # How many viruital channel device have in the address space above real channels
        self.virtual_channels = None
        # How manuy BUS VU led banks does this device have
        self.busvus = None
        # List of Track objects
        self.tracks = []
        # Button LED class depends on the mapping tree so must be done by inheritor
        self.reabuttonled = None

    def set_mode(self, mode):
        """set the global desk mode"""
        self.log.debug('Desk mode set: %s', mode)
        self.modemgr.set_mode(mode)
        for track in self.tracks:
            track.modemgr.set_mode(mode)
            attr = getattr(track, 'reascribstrip', None)
            if attr:
                track.reascribstrip.restore_desk_display()

    def get_track(self, track):
        """Safely access both the main tracks and any virtual
        ones in the address space above real tracks """
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
                scrib.c_d(['reascribstrip', 'long'], [piece])

    def instantiate_tracks(self, track_class):
        """Build the tracks list out of the supplied class
        and to the length specified"""
        self.log.debug('Desk instantiating tracks with class: %s', track_class.__name__)
        self.tracks = [track_class(self, track_number)
                       for track_number in range(0, self.real_channels + self.virtual_channels)]


class _ReaTrack(ReaBase):
    """Track (channel strip) object to contain
    one each of the bits found in each of the main tracks"""

    def __init__(self, desk, track_number):
        self.desk = desk
        self.log = desk.log
        self.track_number = track_number
        self.osctrack_number = track_number + 1
        self.modemgr = ModeManager(self.desk.modemgr.modes)

        # Only channel strip setup common to all devices goes here
        if self.track_number < self.desk.real_channels:
            self.reavumeter = ReaVumeter(self)

        # Moved this so all track types have button led obj
        # TODO discover if this is needed
        self.reabuttonled = ReaButtonLed(self.desk, self)

        # Assuming 28 is always the virtual track for all jpots
        if self.track_number == 28:
            self.reavpot = ReaJpot(self)
            # Allow access from both 'virtual' track 28 AND desk object
            # as it physically belongs there
            self.desk.jpot = self.reavpot


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

    def __init__(self, track, digits, bank, defaultaddress='/track/@/number'):
        self.track = track
        self.log = track.desk.log
        self.restore_timer = None
        self.digits = digits
        self.bank = bank
        self.mode = track.modemgr.get_data()
        defaulttext = '{num:02d}'.format(num=self.track.osctrack_number)
        self.dtext = defaulttext

        self.numbytes = self.digits + 7
        self.cmdbytes = (c_ubyte * self.numbytes)()

        self.last_update = time.time()

        # Set up the byte array for initial popn
        bytes = [0xf0, 0x13, 0x01, 0x40, self.track.track_number, 0x00] + ([0x00] * self.digits) + [0xf7]
        # Copy to the ctypes bytes
        for ind, byt in enumerate(bytes):
            self.cmdbytes[ind] = byt

        # Initialise the text dictionary with a default element
        # It should get overwritten once this OSC address is
        # populated by the DAW.
        addrdef = defaultaddress.replace('@', str(self.track.osctrack_number))
        self.text = {addrdef: defaulttext}

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
        self.cmdbytes[6:self.digits + 6] = [ord(thischar) for thischar in self.dtext]
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
            fmtstring = '{txt: <' + str(self.digits) + '}'
            self.dtext = fmtstring.format(txt=dtext[:self.digits])
        else:
            # send all spaces to blank it out
            self.dtext = ' ' * self.digits

    def c_d(self, addrlist, stuff):
        """Update from DAW text"""
        # quick hack to turn numbers in track address back to @
        # so it matches the desk modes address.
        # TODO - messy!
        for addr in addrlist:
            if unicode(addr).isnumeric():
                addr = '@'
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


class ReaJpot(ReaBase):
    """Class for Jog wheel, a special type of vpot"""

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
            'Scrub': {'address': '/jpot/scrub', 'default': True},
            'Shuttle': {'address': '/jpot/playrate/rotary'}
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

            self.log.debug('%s', self)
            self.track.desk.osc_client_send(msg)


class _ReaVpot(ReaBase):
    """Class for the Virtual Pots"""
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

    def __init__(self, track, address='/track/{}/vpot'):
        self.log = track.desk.log
        self.track = track
        # TODO allow mode switch between dot and fill display
        self.scale = _ReaVpot.scale_fill
        self.pang = 0
        self.panv = 0,
        self.pan = float(0.5)
        self.cmdbytes_d_c = (c_ubyte * 30)()
        self.cmdbytes = (c_ubyte * 8)()
        for ind, byt in enumerate(
                [0xF0, 0x13, 0x01, 0x00, self.track.track_number & 0x3f,
                 0x00, 0x00, 0xF7]):
            self.cmdbytes[ind] = byt
            self.cmdbytes_d_c[ind] = byt
        self.osc_address = address.format(
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
            self.log.debug('VPOT LED lookup failure: %s', self)
        self.track.desk.daemon_client_send(self.cmdbytes)
        self.log.debug('VPOT LED: %s', self)

    def led_value(self, pang):
        """Look up the value to send to the pot LEDs"""
        return self.scale[pang]

    @staticmethod
    def adj_pan(vpot):
        """Increment/decrement the pan factor from command bytes"""
        potdir = vpot.cmdbytes_d_c[2] - 64
        potvel = vpot.cmdbytes_d_c[3]
        if vpot.track.desk.reamodifiers.command:
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


class _ReaFader(ReaBase):
    """Class to hold and convert fader value representations"""
    # TODO move this into this class
    faderscale = ReaBase.calc_faderscale()

    def __init__(self, track, address='/track/{}/fader'):
        self.log = track.desk.log
        self.track = track
        self.gain = None
        self.cmdbytes = (c_ubyte * 5)()
        for ind, byt in enumerate(
                [0xB0, self.track.track_number & 0x1F,
                 0x00, self.track.track_number + 0x20, 0x00]):
            self.cmdbytes[ind] = byt
        self.osc_address = address.format(
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

    def c_d(self, _, stuff):
        """Computer to Desk. Update from DAW gain factor (0-1)"""
        gai = stuff[0]
        self.gain = gai
        self.cmdbytes[3] = 0x20 + self.track.track_number
        self.cmdbytes[2], self.cmdbytes[4] = self.calc_cmdbytes(self)
        self.track.desk.daemon_client_send(self.cmdbytes)

    def _update_from_fadermove(self, parsedcmd):
        cbytes = parsedcmd.get('cmdbytes')
        t_in = ord(cbytes[1])
        if t_in != self.track.track_number:
            self.log.error('Track from Command Bytes does not match Track object Index: %s %s',
                           binascii.hexlify(cbytes), self)
            return None
        # TODO tidy up here
        if len(cbytes) < 2:
            self.log.warn('ReaFader bad signature %s',
                          parsedcmd)
            return None
        if cbytes[3] == '\x00':
            self.log.warn('ReaFader bad signature %s',
                          parsedcmd)
            return None
        self.cmdbytes[2] = ord(cbytes[2])
        self.cmdbytes[4] = ord(cbytes[4])
        self.gain = self.calc_gain(self)
        self.osc_message.clearData()
        self.osc_message.append(self.gain)
        self.track.desk.osc_client_send(self.osc_message)
        if tick() - self.last_tick > TIMING_FADER_ECHO:
            self.track.desk.daemon_client_send(self.cmdbytes)
        self.last_tick = tick()

    def _update_from_touch(self, parsedcmd):
        val = parsedcmd.get('Value')
        valb = bool(val)
        if self.touch_status and not valb:
            self.track.desk.daemon_client_send(self.cmdbytes)
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
        return _ReaFader.faderscale[volume_from_desk]


class _ReaAutomode(ReaBase):
    """ class to deal with the automation toggle on a track
    with the various LEDs and modes exchanged between DAW and desk"""
    automodes = {
        'write': {'state': False, 'cmd': 0x40},
        'touch': {'state': False, 'cmd': 0x20},
        'latch': {'state': False, 'cmd': 0x10},
        'trim': {'state': False, 'cmd': 0x08},
        'read': {'state': False, 'cmd': 0x04}
    }

    def __init__(self, desk, track, address='/track/{}/automode/{}'):
        self.log = desk.log
        self.desk = desk
        self.track = track
        self.address = address
        self.cmdbytes = (c_ubyte * 30)()
        for ind, byt in enumerate(
                [0xF0, 0x13, 0x01, 0x20, self.track.track_number & 0x1F,
                 0x00, 0xF7]):
            self.cmdbytes[ind] = byt
        self.modes = dict(_ReaAutomode.automodes)

    def __str__(self):
        mods = ['{}:{}'.format(key, value.get('state')) for key, value in self.modes.iteritems()]
        return 'ReaAutomode track:{} byt:{} modes:{} '.format(
            self.track.track_number,
            self.cmdbytes[5],
            mods
        )

    def c_d(self, addrlist, stuff):
        """computer to desk handler"""
        mode_in = addrlist[-1]
        mode_onoff = bool(stuff[0])
        self.set_mode(mode_in, mode_onoff)
        self.update_led()

    def d_c(self, parsedcmd):
        """deskt to computer handler"""
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
        """send the current mode to the DAW"""
        addr = self.address.format(
            mode_in,
            self.track.osctrack_number
        )
        msg = OSC.OSCMessage(addr)
        msg.append('{}.0'.format(onoff * 1))
        self.track.desk.osc_client_send(msg)

    def set_mode(self, mode_in, onoff):
        """set the current mode state"""
        mode = self.modes.get(mode_in)
        if not mode:
            raise ReaException('Automation mode does not exist: %s', mode_in)
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
        self.track.desk.daemon_client_send(self.cmdbytes)
        self.log.debug('AUTO LED: %s', self)


class _ReaOscsession(object):
    """Class for the entire client session"""

    # Extract a list of first level command bytes from the mapping tree
    # To use for splitting up multiplexed command sequences

    @staticmethod
    def itsplit(inlist):
        """child method of cmdsplit"""
        current = []
        for item in inlist:
            # Weird one - sometimes FF appears at the end of buttons
            # TODO make sure this is OK/valid to include like a terminator
            if ord(item) in [0xF7, 0xFF]:
                current.append(item)
                yield current
                current = []
            # TODO made the change here need to confirm
            # did have the side effect above re 0xFF
            elif ord(item) & 0x80 == 0x80 and not current == []:
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

        return [subl for subl in _ReaOscsession.itsplit(inlist) if subl]

    def parsecmd(self, cmdbytes):
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
        lkp = self.desk.mapping_tree
        level = 0
        while this_byte_num is not None:
            parsedcmd["lkpbytes"].append(this_byte)
            level = level + 1
            lkp = lkp.get(this_byte)
            if not lkp:
                self.log.warn(
                    'Level %d byte not found in MAPPING_TREE: %02x. New mapping needed for sequence %s',
                    level,
                    this_byte,
                    cmdbytes
                )
                return None
            # Copy this level's dict entries but not the children subdict. i.e. flatten/accumulate
            if "Address" in lkp:
                parsedcmd["addresses"].append('/')
                parsedcmd["addresses"].append(lkp["Address"])
            parsedcmd.update(
                {key: lkp[key] for key in lkp if any([
                    "Byte" in key,
                    "Class" in key,
                    "SetMode" in key,
                    "Toggle" in key
                ])}
            )
            if 'ChildByte' in lkp:
                this_byte_num = lkp['ChildByte']
                try:
                    this_byte = ord(cmdbytes[this_byte_num])
                except IndexError:
                    self.log.warn('Parsecmd: byte not found. Possible malformed command: %s')
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
        # parsedcmd should be some sort of data class
        if 'TrackByte' in parsedcmd:
            track_byte = ord(cmdbytes[parsedcmd['TrackByte']])
            if 'TrackByteMask' in parsedcmd:
                track_byte = track_byte & parsedcmd['TrackByteMask']
            tracknumber = int(track_byte)
            parsedcmd["TrackNumber"] = tracknumber
            # Find the index of the 'track' address token
            # insert the track index number after it
            ind = next(ind for ind, adr in enumerate(parsedcmd["addresses"]) if adr == 'track')
            parsedcmd["addresses"].insert(ind+1, '/')
            parsedcmd["addresses"].insert(ind+2, '{}'.format(tracknumber + 1))
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
        commands = _ReaOscsession.cmdsplit(c_databytes)
        trace(self.log, 'nc: %d', len(commands))
        for cmd in commands:
            parsed_cmd = _ReaOscsession.parsecmd(self, cmd)
            if parsed_cmd:
                address = parsed_cmd.get('address')
                self.log.debug(parsed_cmd)
                # If we have a track number then get the corresponding object
                track_number = parsed_cmd.get("TrackNumber")
                track = self.desk.get_track(track_number)
                # If map indicates a mode is to be set then call the setter
                set_mode = parsed_cmd.get('SetMode')
                if set_mode:
                    # Suspect commented out line was a bug preventing
                    # proper desk wide scriblle updates.
                    # should have been calling set mode function not setting object.
                    # @phunkyg 29/09/18
                    self.desk.set_mode(set_mode)
                    # self.desk.mode = set_mode

                # CLASS based Desk-Daw, where complex logic is needed so encap. in class
                cmd_class = parsed_cmd.get('CmdClass')
                if cmd_class is not None:
                    # Most class handlers will be within a track
                    # but if not then try the desk object
                    try:
                        inst = getattr(track or self.desk, cmd_class.lower(), None)
                        if not inst:
                            self.log.warn(
                                'Looking for mapped cmd_class but not found. The map is incorrect. Track: %s Class: %s',
                                str(track_number),
                                cmd_class
                            )
                        # Call the desk_to_computer method of the class
                        inst.d_c(parsed_cmd)
                    except Exception:
                        self.log.error(
                            'Error doing d_c in cmd_class. Track: %s Class: %s',
                            str(track_number),
                            cmd_class,
                            exc_info=True
                        )
                else:
                    # NON CLASS based Desk-DAW i.e. basic buttons
                    if 'button' in parsed_cmd.get('addresses'):
                        osc_msg = OSC.OSCMessage(address)
                        if osc_msg is not None:
                            self.osc_client_send(osc_msg, parsed_cmd.get('Value'))

    def _daw_to_desk(self, addr, tags, stuff, source):
        """message handler for the OSC listener
        each token from the OSC message is used to redirect the message content
        to the right cmdclass object in the desk model"""
        self.log.debug("OSC Listener received Message: %s %s [%s] %s",
                       source, addr, tags, str(stuff))

        if self.osc_listener_last is None:
            self.osc_listener_last = source
        elif self.osc_listener_last != source:
            self.log.warn('OSC message received from an unexpected source address %s', source)

        try:
            cmdinst = None
            track_number = None
            track = None
            addrlist = addr.split('/')

            # First address token magic values are used to direct actions through to the right object
            track_addr_ind = next((ind for ind, adr in enumerate(addrlist) if adr == 'track'), None)
            if track_addr_ind:
                # track based addresses must have the
                # next address token be the @ parameter
                # for the track number
                track_number = int(addrlist[track_addr_ind+1]) - 1
                track = self.desk.get_track(track_number)
                if track is None:
                    raise ReaException('No track object {}'.format(track_number))

                if 'button' in addrlist:
                    # track buttons are a special case and have a magic token
                    attribute_name = 'reabuttonled'
                else:
                    # otherwise the address token following the track number
                    # references the attribute within the track
                    # so by convention the class name in lowercase
                    attribute_name = addrlist[track_addr_ind+2]

                cmdinst = getattr(track, attribute_name, None)
                if cmdinst is None:
                    raise ReaException('Track {} has no cmdclass {}'.format(track_number, attribute_name))
            elif addrlist[1] == "action":
                # Placeholder for spot to handle action address from daw
                pass
            else:
                # addresses not containing track token assumed to target a desk cmdclass
                attribute_name = addrlist[1]
                # allow the button magic address to mean the reabuttonled class
                if attribute_name == 'button':
                    attribute_name = 'reabuttonled'
                cmdinst = getattr(self.desk, attribute_name, None)
                if cmdinst is None:
                    raise ReaException('Desk has no cmdclass {}'.format(attribute_name))

            # if we have located a cmd class instance then pass the OSC message to it
            cmdinst.c_d(addrlist, stuff)

        except ReaException:
            self.log.warn('Internal Reacontrol Error responding to daw_to_desk OSC message', exc_info=True)
        except Exception:
            self.log.error('Unhandled Error responding to daw_to_desk OSC message', exc_info=True)

    # Threaded methods
    def _manage_daemon_client(self):
        trace(self.log, 'Daemon client thread starting')
        while not self.is_closing:
            if self.standalone:
                # Poll for a connection, in case server is not up
                self.log.debug(
                    'Starting multiprocess client connecting to %s',
                    self.server)
                while self.daemon_client is None:
                    try:
                        self.daemon_client = Client(
                            self.server, authkey=DEFAULTS.get('auth'))
                    except Exception as exc:
                        # Connection refused
                        if exc[0] == 61:
                            self.log.error(
                                'Error trying to connect to daemon at %s. May not be running. Will try again.',
                                self.server)
                            time.sleep(TIMING_SERVER_POLL)
                        else:
                            self.log.error(
                                'Deamon client Unhandled exception', exc_info=True)
                            raise
            else:
                self.daemon_client = self.server_pipe
            self.daemon_client_is_connected = True

            # Main Loop when connected
            while self.daemon_client_is_connected:
                self.log.debug('multiprocess Client waiting for data: %s',
                               self.daemon_client.fileno())
                try:
                    datarecv = self.daemon_client.recv_bytes()
                    self._desk_to_daw(datarecv)
                except EOFError:
                    self.log.error('multiprocess Client EOFError: Daemon closed communication.')
                    self.daemon_client_is_connected = False
                    self.daemon_client = None
                    time.sleep(TIMING_SERVER_POLL)
                except Exception:
                    self.log.error("Daemon client Uncaught exception", exc_info=True)
                    raise
        # Close down gracefully
        if self.daemon_client_is_connected:
            self.daemon_client.close()
            self.daemon_client_is_connected = False
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
                    'Waiting for the OSC listener to get a client %s', self.osc_listener_last)
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
                self.log.debug("Sending Test message via OSC Client")
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
            except Exception:
                self.log.error("Error sending OSC msg:",
                               exc_info=sys.exc_info())
                self._disconnect_osc_client()
        else:
            self.log.debug(
                "OSC Client not connected but message send request received: %s", osc_msg)

    def daemon_client_send(self, cmdbytes):
        """dry up the calls to the MP send that
        are wrapped in a connection check"""
        if self.daemon_client_is_connected:
            trace(self.log, "multiprocess send: %s",
                  binascii.hexlify(cmdbytes))
            self.daemon_client.send_bytes(cmdbytes)

    # session housekeeping methods
    def __init__(self, opts, networks, pipe=None):
        """Contructor to build the client session object"""
        self.log = start_logging("ReaOscsession", opts.logdir, opts.debug)
        try:
            self.standalone = pipe is None
            if self.standalone:
                self.server = OSC.parseUrlStr(opts.server)[0]
                self.server_pipe = None
                self.log.debug('ReaOscsession Starting up in STANDALONE mode')
            else:
                self.server = None
                self.server_pipe = pipe
                self.log.debug('ReaOscsession Starting up in SUBPROCESS mode')
            self.listen = OSC.parseUrlStr(opts.listen)[0]
            self.connect = OSC.parseUrlStr(opts.connect)[0]
            self.osc_listener = None
            self.osc_listener_last = None
            self.osc_client = None
            self.osc_client_is_connected = False
            self.daemon_client = None
            self.daemon_client_is_connected = False
            self.is_closing = False
        except Exception:
            self.log.error('Error during init of OSC session', exc_info=True)
            raise

    def start(self):
        """start the session - like part 2 of init"""
        try:
            # Start a thread to manage the connection to the control24d
            self.thread_daemon_client = threading.Thread(
                target=self._manage_daemon_client,
                name='thread_daemon_client'
            )
            self.thread_daemon_client.daemon = True
            self.thread_daemon_client.start()

            # Start a thread to manage the OSC Listener
            self.thread_osc_listener = threading.Thread(
                target=self._manage_osc_listener,
                name='thread_osc_listener'
            )
            self.thread_osc_listener.daemon = True
            self.thread_osc_listener.start()

            # Start a thread to manage the OSC Client
            self.thread_osc_client = threading.Thread(
                target=self._manage_osc_client,
                name='thread_osc_client'
            )
            self.thread_osc_client.daemon = True
            self.thread_osc_client.start()

            # Have to join a thread now or the whole subprocess will end and shut down all threads
            self.thread_daemon_client.join()

        except Exception:
            self.log.error('Error caught by Outer error trap for OSC client session threads:', exc_info=True)
            raise


    def __str__(self):
        """pretty print session state if requested"""
        return 'osc session: daemon_client_is_connected:{}'.format(
            self.daemon_client_is_connected
        )

    def close(self):
        """Placeholder if we need a shutdown method"""
        self.log.info("ReaOscsession closing")
        # For threads under direct control this signals to please end
        self.is_closing = True
        # For others ask nicely
        if not self.osc_listener is None and self.osc_listener.running:
            self.osc_listener.close()
        self.log.info("ReaOscsession closed")

    def __del__(self):
        """Placeholder to see if session object destruction is a useful hook"""
        trace(self.log, "ReaOscsession del")
        self.close()


def signal_handler(sig, stackframe):
    """Exit the client if a signal is received"""
    signals_dict = dict((getattr(signal, n), n)
                        for n in dir(signal) if n.startswith('SIG') and '_' not in n)
    # log.info("procontrolosc shutting down as %s received.", signals_dict[sig])
    if not SESSION is None:
        SESSION.close()
    sys.exit(0)


# main program if run in standalone mode
def main(sessionclass):
    """Main function declares options and initialisation routine for OSC client."""
    global SESSION

    # Find networks on this machine, to determine good defaults
    # and help verify options
    networks = NetworkHelper()

    default_ip = networks.get_default()[1]

    # program options
    oprs = opts_common("ReaControl OSC client")
    default_daemon = networks.ipstr_from_tuple(default_ip, DEFAULTS.get('daemon'))
    oprs.add_option(
        "-s",
        "--server",
        dest="server",
        help="connect to daemon at given host:port. default %s" % default_daemon)
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
        help="Connect to DAW OSC server at host:port. default %s" % default_daw)

    oprs.set_defaults(listen=default_osc_client,
                      server=default_daemon, connect=default_daw)

    # Parse and verify options
    # TODO move to argparse and use that to verify
    (opts, _) = oprs.parse_args()
    if not networks.verify_ip(opts.listen.split(':')[0]):
        raise optparse.OptionError('No network has the IP address specified.', 'listen')

    # Set up Interrupt signal handler so process can close cleanly
    # if an external signal is received
    if sys.platform.startswith('win'):
        # TODO test these in Winders
        signals = [signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGABRT]
    else:
        # TODO check other un*x variants
        # OSC (Mojave) responding to these 2
        signals = [signal.SIGTERM, signal.SIGHUP]

    for sig in signals:
        signal.signal(sig, signal_handler)

    # Build the session
    if SESSION is None:
        # start logging if main
        SESSION = sessionclass(opts, networks)

    # Main Loop once session initiated
    while True:
        time.sleep(TIMING_MAIN_LOOP)
