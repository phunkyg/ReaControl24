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

from ReaCommon import (ModeManager, ReaBase, ReaNav, ReaModifiers, _ReaDesk, _ReaTrack, _ReaScribStrip,
                       _ReaVpot, _ReaFader, _ReaAutomode, _ReaOscsession, ReaButtonLed,
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




class ProCscribstrip(_ReaScribStrip):
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
        #TODO haven't got to doing anything fancy different right now
        # just making sure the 8 (or n) digit capability is retained

#TODO, unless specifics are needed the next few classes can be collapsed by refactoring the
#OSC schema in the OSC mapping files to be consistent

class ProCvpot(_ReaVpot):
    """Class for the Pro Control Virtual Pots"""
    defaultaddress = '/track/vpot/{}'

    def __init__(self, track):
        super(_ReaVpot, self).__init__(self, track, ProCvpot.defaultaddress)


class ProCfader(_ReaFader):
    """Class for the Pro Control Faders"""
    defaultaddress = '/track/fader/{}'

    def __init__(self, track):
        super(_ReaFader, self).__init__(self, track, ProCfader.defaultaddress)

class ProCautomode(_ReaAutomode):
    """ class to deal with the automation toggle on a track
    with the various LEDs and modes exchanged between DAW and desk"""
    defaultaddress = '/track/automode/{}/{}'

    def __init__(self, desk, track):
        super(_ReaAutomode, self).__init__(self, track, ProCautomode.defaultaddress)


class ProCoscsession(_ReaOscsession):
    """OSC session specific to ProControl"""

    def __init__(self, opts, networks, pipe=None):
        """Contructor to build the client session object"""
        """ Build a base desk object with the _Readesk class
        then apply the specifics for this device """
        self.desk = ProCdesk(self)
        self.mapping_tree = procontrolmap.MAPPING_TREE
        super(_ReaOscsession, self).__init__(self, opts, networks, pipe)



# START main program if run in standalone mode
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
