#!/usr/bin/env python
"""Control24 to Reaper.OSC client. Communicate between the daemon
process and an OSC Client/Listener pair, tuned for Reaper DAW.
Other, similar clients can be written to communicate with other
protocols such as MIDI HUI, Mackie etc.
"""

from ReaCommon import (main, trace, ModeManager, ReaVumeter, ReaButtonLed,
                       _ReaDesk, _ReaTrack, _ReaScribStrip, _ReaVpot, _ReaFader, _ReaAutomode, _ReaOscsession,
                       )
import control24map

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

# Timing values in seconds
TIMING_MAIN_LOOP = 10  # 0
TIMING_SERVER_POLL = 2
TIMING_MP_POLL = 1
TIMING_WAIT_OSC_LISTENER = 4
TIMING_OSC_LISTENER_RESTART = 1
TIMING_OSC_CLIENT_RESTART = 1
TIMING_OSC_CLIENT_LOOP = 4
TIMING_SCRIBBLESTRIP_RESTORE = 1
TIMING_FADER_ECHO = 0.1

SESSION = None


# Classes representing Control24
class C24Track(_ReaTrack):
    """Track (channel strip) object to contain
    one each of the elements found in each of the main
    channel strips (tracks)
    Spefically for Control24 desk layout"""

    def __init__(self, desk, track_number):
        super(C24Track, self).__init__(desk, track_number)
        # super gives us the common layout, now we add Pro Control specifics
        # Only channel strip setup specific to Control24 goes here
        if self.track_number < self.desk.real_channels:
            trace(self.log, 'Adding C24 specifics to track instance')
            self.reafader = C24fader(self)
            self.reavpot = C24vpot(self)
            self.reaautomode = C24automode(self.desk, self)

        # Place a VU meter on virtual tracks above 24, these are bus VUs
        if all([
                self.track_number >= self.desk.real_channels,
                self.track_number <= self.desk.real_channels + self.desk.busvus
        ]):
            self.reavumeter = ReaVumeter(self)

        # Place a VU meter on virtual tracks above 24, these are bus VUs
        if all([
                self.track_number >= self.desk.real_channels,
                self.track_number <= self.desk.real_channels + self.desk.busvus
        ]):
            self.vumeter = ReaVumeter(self)

        # Place a scribble strip on main channel strips and virtual strips (2 spares)
        if self.track_number <= self.desk.real_channels or self.track_number in range(
                self.desk.real_channels,
                self.desk.real_channels + self.desk.virtual_channels
        ):
            self.c24scribstrip = C24scribstrip(self)
            # maintain a generic reference too
            self.reascribstrip = self.c24scribstrip


class C24desk(_ReaDesk):
    """Class to represent the desk, state and
    instances to help conversions and behaviour"""
    real_channels = 24
    virtual_channels = 8
    busvus = 1
    deskmodes = {
        'Values': {
            'address': '/track/@/c24scribstrip/volume',

        },
        'Group': {
            'toggle': True
        },
        'Names': {
            'address': '/track/@/c24scribstrip/name',
            'default': True
        },
        'Info': {
            'address': '/track/@/c24scribstrip/pan'
        }
    }

    def __init__(self, parent):
        """ Build a base desk object with the _Readesk class
        then apply the specifics for this device """
        super(C24desk, self).__init__(parent)

        self.mapping_tree = control24map.MAPPING_TREE
        self.reabuttonled = ReaButtonLed(self, None)

        self.modemgr = ModeManager(C24desk.deskmodes)
        # Set up specifics for this device
        self.real_channels = C24desk.real_channels
        self.virtual_channels = C24desk.virtual_channels
        # There are several but only 1 mapped and active at this time
        self.busvus = 1

        self.instantiate_tracks(C24Track)


class C24scribstrip(_ReaScribStrip):
    """Class to hold and convert scribblestrip value representations
    this version specific to the Control24 """

    digits = 4
    defaultaddress = '/track/@/number'
    bank = 0

    def __init__(self, track):
        super(C24scribstrip, self).__init__(
            track,
            C24scribstrip.digits,
            C24scribstrip.bank,
            C24scribstrip.defaultaddress)


# TODO, unless specifics are needed the next few classes can be collapsed by refactoring the
# OSC schema in the OSC mapping files to be consistent

class C24vpot(_ReaVpot):
    """Class for the Control24 Virtual Pots"""
    defaultaddress = '/track/{}/reavpot'

    def __init__(self, track):
        super(C24vpot, self).__init__(track, C24vpot.defaultaddress)


class C24fader(_ReaFader):
    """Class for the Control24 Faders"""
    defaultaddress = '/track/{}/reafader'

    def __init__(self, track):
        super(C24fader, self).__init__(track, C24fader.defaultaddress)


class C24automode(_ReaAutomode):
    """ class to deal with the automation toggle on a track
    with the various LEDs and modes exchanged between DAW and desk"""
    defaultaddress = '/track/{}/reaautomode/{}'

    def __init__(self, desk, track):
        super(C24automode, self).__init__(desk, track, C24automode.defaultaddress)


class C24Oscsession(_ReaOscsession):
    """OSC session specific to Control24"""

    def __init__(self, opts, networks, pipe=None):
        """Contructor to build the client session object"""
        super(C24Oscsession, self).__init__(opts, networks, pipe)
        self.desk = C24desk(self)
        self.mapping_tree = control24map.MAPPING_TREE
        self.start()


# main program if run in standalone mode
if __name__ == '__main__':
    from ReaCommon import start_logging
    main(C24Oscsession)
