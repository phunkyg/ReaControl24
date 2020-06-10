#!/usr/bin/env python
"""Procontrol to Reaper.OSC client. Communicate between the daemon
process and an OSC Client/Listener pair, tuned for Reaper DAW.
Other, similar clients can be written to communicate with other
protocols such as MIDI HUI, Mackie etc.
"""

from ReaCommon import (main, ModeManager, ReaVumeter, ReaButtonLed,
                       _ReaDesk, _ReaTrack, _ReaScribStrip, _ReaVpot, _ReaFader, _ReaAutomode, _ReaOscsession,
                       )
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


# Classes representing Procontrol
class ProCTrack(_ReaTrack):
    """Track (channel strip) object to contain
    one each of the elements found in each of the main
    channel strips (tracks)
    Spefically for Pro Control desk layout"""

    def __init__(self, desk, track_number):
        super(ProCTrack, self).__init__(desk, track_number)

        # super gives us the common layout, now we add Pro Control specifics
        # Only channel strip setup specific to Control24 goes here
        if self.track_number < self.desk.real_channels:
            self.log.debug('Adding ProC specifics to track instance')
            self.reafader = ProCfader(self)
            self.reavpot = ProCvpot(self)
            self.reaautomode = ProCautomode(self.desk, self)

        # Place a VU meter on virtual tracks above 8, these are bus VUs
        if all([
            self.track_number >= self.desk.real_channels,
            self.track_number <= self.desk.real_channels + self.desk.busvus
        ]):
            self.reavumeter = ReaVumeter(self)

        # Place a scribble strip on main channel strips
        if self.track_number <= self.desk.real_channels:
            self.procscribstrip = ProCscribstrip(self)
            self.reascribstrip = self.procscribstrip


class ProCdesk(_ReaDesk):
    """Class to represent the desk, state and
    instances to help conversions and behaviour"""
    real_channels = 8
    virtual_channels = 1
    busvus = 1
    deskmodes = {
        'Values': {
            'address': '/track/@/procscribstrip/volume',

        },
        'Group': {
            'toggle': True
        },
        'Names': {
            'address': '/track/@/procscribstrip/name',
            'default': True
        },
        'Info': {
            'address': '/track/@/procscribstrip/pan'
        }
    }

    def __init__(self, parent):
        """ Build a base desk object with the _Readesk class
        then apply the specifics for this device """
        super(ProCdesk, self).__init__(parent)

        self.mapping_tree = procontrolmap.MAPPING_TREE_PROC
        self.reabuttonled = ReaButtonLed(self, None)

        self.modemgr = ModeManager(ProCdesk.deskmodes)
        # Set up specifics for this device
        self.real_channels = ProCdesk.real_channels
        self.virtual_channels = ProCdesk.virtual_channels
        self.busvus = 1

        self.instantiate_tracks(ProCTrack)


class ProCscribstrip(_ReaScribStrip):
    """Class to hold and convert scribblestrip value representations
    this version specific to the Control24 """

    digits = 8
    defaultaddress = '/track/@/number'
    bank = 0

    def __init__(self, track):
        super(ProCscribstrip, self).__init__(
            track,
            ProCscribstrip.digits,
            ProCscribstrip.bank,
            ProCscribstrip.defaultaddress)
        # Pro Control scribs have this byte set to 0 not 1
        self.cmdbytes[2] = 0x00


# TODO, unless specifics are needed the next few classes can be collapsed by refactoring the
# OSC schema in the OSC mapping files to be consistent

class ProCvpot(_ReaVpot):
    """Class for the Pro Control Virtual Pots"""
    defaultaddress = '/track/{}/reavpot'

    def __init__(self, track):
        super(ProCvpot, self).__init__(track, ProCvpot.defaultaddress)


class ProCfader(_ReaFader):
    """Class for the Pro Control Faders"""
    defaultaddress = '/track/{}/reafader'

    def __init__(self, track):
        super(ProCfader, self).__init__(track, ProCfader.defaultaddress)


class ProCautomode(_ReaAutomode):
    """ class to deal with the automation toggle on a track
    with the various LEDs and modes exchanged between DAW and desk"""
    defaultaddress = '/track/{}/reaautomode/{}'

    def __init__(self, desk, track):
        super(ProCautomode, self).__init__(desk, track, ProCautomode.defaultaddress)


class ProCoscsession(_ReaOscsession):
    """OSC session specific to ProControl"""

    def __init__(self, opts, networks, pipe=None):
        """Contructor to build the client session object"""
        super(ProCoscsession, self).__init__(opts, networks, pipe)
        self.desk = ProCdesk(self)
        self.mapping_tree = procontrolmap.MAPPING_TREE_PROC
        self.start()


# main program if run in standalone mode
if __name__ == '__main__':
    from ReaCommon import start_logging
    main(ProCoscsession)
