"""Main Mapping dictionary tree and other reference tables"""
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
MAPPING_TREE_PROC = {
    0xB0: {
        'Address': 'track',
        'ChildByte': 1,
        'ChildByteMask': 0x40,
        'TrackByte': 1,
        'TrackByteMask': 0x1F,
        'Children': {
            0x00: {
                'Address': 'c24fader',
                'CmdClass': 'C24fader'
            },
            0x40: {
                'Address': 'c24vpot',
                'CmdClass': 'C24vpot'
            }
        }
    },  # END L1 Dials/Faders
    0x90: {
        'Address': 'button',
        'ChildByte': 2,
        'ChildByteMatch': 0x08,  #bits for 8 switches channel strips or command button, 16 is DSP section
        'ValueByte': 2,
        'ValueByteMask': 0x40,   #bit for 64 switches on/off value
        'Children': {
            0x18: {},
            0x08: {  ## Command (not channel strip) buttons
                'Address': 'command',
                'ChildByte': 2,
                'ChildByteMask': 0x3F,  ## Ignore all bits from 0x40 upward when choosing next child
                'Children': {
                    0x08: {
                        'Address': 'utility_misc_meterselect_automationenable',
                        'ChildByte': 1,
                        'Children': {
                            0x00: {
                                'Address': 'CLR_F1',
                                'Zone': 'topleft',
                                'LED': True
                            },
                            0x02: {
                                'Address': 'F2',
                                'Zone': 'topleft',
                                'LED': True
                            },
                            0x04: {
                                'Address': 'F3',
                                'Zone': 'topleft',
                                'LED': True
                            },
                            0x06: {
                                'Address': 'F4',
                                'Zone': 'topleft',
                                'LED': True
                            },
                            0x01: {
                                'Address': 'master_rec',
                                'Zone': 'topleft',
                                'LED': True
                            },
                            0x03: {
                                'Address': 'ins_bypass',
                                'Zone': 'topleft',
                                'LED': True
                            },
                            0x05: {
                                'Address': 'in_edit',
                                'Zone': 'topleft',
                                'LED': True
                            },
                            0x07: {
                                'Address': 'default',
                                'Zone': 'topleft',
                                'LED': True
                            },
                            0x08: {
                                'Address': 'pan',
                                'Zone': 'select_assign',  ##not sure this is correct zone
                                'LED': True
                            },
                            0x09: {
                                'Address': 'mon_phase',
                                'Zone': 'select_assign',  ##not sure this is correct zone
                                'LED': True
                            },
                            0x0a: {
                                'Address': 'Input',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x0b: {
                                'Address': 'Output',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x0c: {
                                'Address': 'Assign',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x0d: {
                                'Address': 'SendMute',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x0e: {
                                'Address': 'send_AF',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x10: {
                                'Address': 'send_BG',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x12: {
                                'Address': 'send_CH',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x0f: {
                                'Address': 'send_DI',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x11: {
                                'Address': 'send_EJ',
                                'Zone': 'select_assign',
                                'LED': True
                            },
                            0x13: {
                                'Address': 'Flip',
                                'Zone': 'Sends',
                                'LED': True
                            },
                            0x14: {
                                'Address': 'SoloClear',
                                'Zone': 'centreleft',
                                'LED': True
                            },
                            0x15: {
                                'Address': 'auto_suspend',
                                'Zone': 'centreleft',
                                'LED': True
                            },
                            0x16: {
                                'Address': 'display_mode',
                                'Zone': 'centreleft',
                                'LED': True
                            },
                            0x17: {
                                'Address': 'Write',
                                'Zone': 'automation_mode',
                                'LED': True
                            },
                            0x19: {
                                'Address': 'Touch',
                                'Zone': 'automation_mode',
                                'LED': True
                            },
                            0x1b: {
                                'Address': 'Latch',
                                'Zone': 'automation_mode',
                                'LED': True
                            },
                            0x1d: {
                                'Address': 'Trim',
                                'Zone': 'automation_mode',
                                'LED': True
                            },
                            0x1f: {
                                'Address': 'Read',
                                'Zone': 'automation_mode',
                                'LED': True
                            },
                            0x21: {
                                'Address': 'Off',
                                'Zone': 'automation_mode',
                                'LED': True
                            },
                            0x18: {
                                'Address': 'Vol',
                                'Zone': 'automation_enable',
                                'LED': True
                            },
                            0x1a: {
                                'Address': 'Pan',
                                'Zone': 'automation_enable',
                                'LED': True
                            },
                            0x1c: {
                                'Address': 'Mute',
                                'Zone': 'automation_enable',
                                'LED': True
                            },
                            0x1e: {
                                'Address': 'send_lvl',
                                'Zone': 'automation_enable',
                                'LED': True
                            },
                            0x20: {
                                'Address': 'send_mute',
                                'Zone': 'automation_enable',
                                'LED': True
                            },
                            0x22: {
                                'Address': 'Plugin',
                                'Zone': 'automation_enable',
                                'LED': True
                            },
                            0x23: {
                                'Address': 'ShiftAdd',
                                'Zone': 'Modifiers',
                                'CmdClass': 'ReaModifiers'
                            },
                            0x24: {
                                'Address': 'OptionAltAll',
                                'Zone': 'Modifiers',
                                'CmdClass': 'ReaModifiers'
                            },
                            0x25: {
                                'Address': 'ControlClutch',
                                'Zone': 'Modifiers',
                                'CmdClass': 'ReaModifiers'
                            },
                            0x26: {
                                'Address': 'CommandCtl',
                                'Zone': 'Modifiers',
                                'CmdClass': 'ReaModifiers'
                            },
                        }
                    },
                    0x0d: {
                        'Address': 'DSPEdit1',
                        'ChildByte': 1,
                        'Children': {
                            0x00: {
                                'Address': 'select_auto',
                                'Zone': 'DspEditAssign1',
                                'LED': True
                            },
                            0x01: {
                                'Address': 'assign_enable',
                                'Zone': 'DspEditAssign1',
                                'LED': True
                            },
                            0x02: {
                                'Address': 'bypass_in_out',
                                'Zone': 'DspEditAssign1',
                                'LED': True
                            }
                        }
                    },
                    0x15: {
                        'Address': 'DSPEdit+Groups',
                        'ChildByte': 1,
                        'Children': {
                            0x00: {  # oddly placed, clock mode
                                'Address': 'CounterMode',
                                'Zone': 'Counter',
                                'CmdClass': 'ReaClock'
                            },
                            0x01: {
                                'Address': 'Info',
                                'Zone': 'DSPEdit',
                                'LED': True
                            },
                            0x02: {
                                'Address': 'Inserts_Param',
                                'Zone': 'DSPEdit',
                                'LED': True
                            },
                            0x03: {
                                'Address': 'Sends',
                                'Zone': 'DSPEdit',
                                'LED': True
                            },
                            0x04: {
                                'Address': 'Create',
                                'Zone': 'Groups',
                                'LED': True
                            },
                            0x05: {
                                'Address': 'Enable',
                                'Zone': 'Groups',
                                'LED': True
                            },
                            0x06: {
                                'Address': 'Edit/Bypass',
                                'Zone': 'Groups',
                                'LED': True
                            },
                            0x07: {
                                'Address': 'Select',
                                'Zone': 'Groups',
                                'LED': True
                            },
                            0x08: {
                                'Address': 'Suspend',
                                'Zone': 'Groups',
                                'LED': True
                            },
                            0x09: {
                                'Address': 'Compare',
                                'Zone': 'Groups',
                                'LED': True
                            },
                            0x0a: {
                                'Address': 'MasterBypass',
                                'Zone': 'DSPEdit',
                                'LED': True
                            }
                        }
                    },
                    0x16: {
                        'Address': 'ControlRoom',
                        'ChildByte': 1,
                        'Children': {
                            0x00: {  # oddly placed, clock mode
                                'Address': 'MixToAux',
                                'Zone': 'ControlRoom',
                                'LED': True
                            },
                            0x01: {
                                'Address': 'StereoMix',
                                'Zone': 'ControlRoom',
                                'LED': True
                            },
                            0x02: {
                                'Address': 'SRC1_3-4',
                                'Zone': 'ControlRoom',
                                'LED': True
                            },
                            0x03: {
                                'Address': 'SRC2_5-6',
                                'Zone': 'ControlRoom',
                                'LED': True
                            },
                            0x04: {
                                'Address': 'SRC3',
                                'Zone': 'ControlRoom',
                                'LED': True
                            },
                            0x05: {
                                'Address': 'Mono',
                                'Zone': 'ControlRoom',
                                'LED': True
                            },
                            0x06: {
                                'Address': 'Dim',
                                'Zone': 'ControlRoom',
                                'LED': True
                            },
                            0x07: {
                                'Address': 'Mute',
                                'Zone': 'ControlRoom',
                                'LED': True
                            }
                        }
                    },
                    0x17: {
                        'Address': 'CannelMatrix',
                        'ChildByte': 1,
                        'Children': {
                            0x00: {
                                'Address': 'GoTo',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x01: {
                                'Address': '1_A',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x02: {
                                'Address': '2_B',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x03: {
                                'Address': '3_C',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x04: {
                                'Address': '4_D',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x05: {
                                'Address': '5_E',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x06: {
                                'Address': '6_F',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x07: {
                                'Address': '7_G',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x08: {
                                'Address': '8_H',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x09: {
                                'Address': '9_I',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x0a: {
                                'Address': '10_J',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x0b: {
                                'Address': '11_K',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x0c: {
                                'Address': '12_L',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x0d: {
                                'Address': '13_M',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x0e: {
                                'Address': '14_N',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x0f: {
                                'Address': '15_O',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x10: {
                                'Address': '16_P',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x11: {
                                'Address': '17_Q',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x12: {
                                'Address': '18_R',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x13: {
                                'Address': '19_S',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x14: {
                                'Address': '20_T',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x15: {
                                'Address': '21_U',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x16: {
                                'Address': '22_V',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x17: {
                                'Address': '23_W',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x18: {
                                'Address': '24_X',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x19: {
                                'Address': '25_Y',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x1a: {
                                'Address': '26_Z',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x1b: {
                                'Address': '27_Shift',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x1c: {
                                'Address': '28_CapLock',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x1d: {
                                'Address': '29_#',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x1e: {
                                'Address': '30_&',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x1f: {
                                'Address': '31_Delete',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x20: {
                                'Address': '32_Space',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x21: {
                                'Address': 'Alpha',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            ## 0x22 missing (no button)
                            0x23: {  ## out of Group (utility???)
                                'Address': 'MasterFaders',
                                'Zone': 'Faders',
                                'LED': True
                            },
                            0x24: {
                                'Address': 'Select',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x25: {
                                'Address': 'Mute',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x26: {
                                'Address': 'Solo',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x27: {
                                'Address': 'RecReady',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x28: {
                                'Address': 'Snapshot',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x29: {
                                'Address': 'ClearAll',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x2a: {
                                'Address': 'Parameter_Pages',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x2b: {
                                'Address': 'View',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x2c: {
                                'Address': 'BankA_1-32',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x2d: {
                                'Address': 'BankB_32-64',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x2e: {
                                'Address': 'BankC_65-96',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x2f: {
                                'Address': 'BankD_97-128',
                                'Zone': 'CannelMatrix',
                                'LED': True
                            },
                            0x30: {  ## More of a Utility Key for exiting on screen dialogs
                                'Address': 'Esc/Cancel',
                                'Zone': 'Utility',
                                'LED': True
                            }
                        }
                    },
                    0x19: {
                        'Address': 'Window+ZoomPresets+Navigation',
                        'ChildByte': 1,
                        'Children': {
                            0x00: {
                                'Address': 'Mix',
                                'Zone': 'Window',
                                'LED': True
                            },
                            0x01: {
                                'Address': 'Edit-Bypass',
                                'Zone': 'Window',
                                'LED': True
                            },
                            0x02: {
                                'Address': 'Status',
                                'Zone': 'Window',
                                'LED': True
                            },
                            0x03: {
                                'Address': 'Trans',
                                'Zone': 'Window',
                                'LED': True
                            },
                            0x04: {
                                'Address': 'PlugIn',
                                'Zone': 'Window',
                                'LED': True
                            },
                            0x05: {
                                'Address': 'Mem-Loc',
                                'Zone': 'Window',
                                'LED': True
                            },
                            0x06: {
                                'Address': 'Undo',
                                'Zone': 'Utility',
                                'LED': True
                            },
                            0x07: {
                                'Address': 'Save',
                                'Zone': 'Utility',
                                'LED': True
                            }
                        }
                    },
                    0x1A: {
                        'ChildByte': 1,
                        'Children': {
                            0x00: {
                                'Address': '0'
                            },
                            0x01: {
                                'Address': '1'
                            },
                            0x02: {
                                'Address': '2'
                            },
                            0x03: {
                                'Address': '3'
                            },
                            0x04: {
                                'Address': '4'
                            },
                            0x05: {
                                'Address': '5'
                            },
                            0x06: {
                                'Address': '6'
                            },
                            0x07: {
                                'Address': '7'
                            },
                            0x08: {
                                'Address': '8'
                            },
                            0x09: {
                                'Address': '9'
                            },
                            0x0a: {
                                'Address': 'Clear'
                            },
                            0x0b: {
                                'Address': '='
                            },
                            0x0c: {
                                'Address': '/'
                            },
                            0x0d: {
                                'Address': '*'
                            },
                            0x0e: {
                                'Address': '-'
                            },
                            0x0f: {
                                'Address': '+'
                            },
                            0x10: {
                                'Address': '.'
                            },
                            0x11: {
                                'Address': 'Enter'
                            }
                        }
                    },
                    0x1B: {
                        'Address': 'EditMode+Function+Banks',
                        'ChildByte': 1,
                        'Children': {
                            0x00: {
                                'Address': 'Shuffle',
                                'Zone': 'Edit Mode',
                                'LED': True
                            },
                            0x01: {
                                'Address': 'Slip',
                                'Zone': 'Edit Mode',
                                'LED': True
                            },
                            0x02: {
                                'Address': 'Spot',
                                'Zone': 'Edit Mode',
                                'LED': True
                            },
                            0x03: {
                                'Address': 'Grid',
                                'Zone': 'Edit Mode',
                                'LED': True
                            },
                            0x04: {
                                'Address': 'Cut',
                                'Zone': 'Edit Function'
                            },
                            0x05: {
                                'Address': 'Copy',
                                'Zone': 'Edit Function'
                            },
                            0x06: {
                                'Address': 'Paste',
                                'Zone': 'Edit Function'
                            },
                            0x07: {
                                'Address': 'Delete',
                                'Zone': 'Edit Function'
                            },
                            0x08: {
                                'Address': 'Separate',
                                'Zone': 'Edit Function'
                            },
                            0x09: {
                                'Address': 'Capture',
                                'Zone': 'Edit Function'
                            },
                            0x0a: {
                                'Address': 'Left',
                                'Zone': 'Bank'
                            },
                            0x0b: {
                                'Address': 'Nudge',
                                'Zone': 'Bank',
                                'LED': True
                            },
                            0x0c: {
                                'Address': 'Right',
                                'Zone': 'Bank'
                            },
                            0x0d: {
                                'Address': 'Trim',
                                'Zone': 'Edit Tools',
                                'LED': True
                            },
                            0x0e: {
                                'Address': 'Select',
                                'Zone': 'Edit Tools',
                                'LED': True
                            },
                            0x0f: {
                                'Address': 'Grab',
                                'Zone': 'Edit Tools',
                                'LED': True
                            },
                            0x10: {
                                'Address': 'Pencil',
                                'Zone': 'Edit Tools',
                                'LED': True
                            }
                        }
                    },
                    0x1C: {
                        'Address': 'Transport',  # was zone
                        'ChildByte': 1,
                        'Children': {
                            0x00: {
                                'Address': 'Audition',
                                'LED': True
                            },
                            0x01: {
                                'Address': 'Pre Roll',
                                'LED': True
                            },
                            0x02: {
                                'Address': 'In',
                                'LED': True
                            },
                            0x03: {
                                'Address': 'Out',
                                'LED': True
                            },
                            0x04: {
                                'Address': 'Post Roll',
                                'LED': True
                            },
                            0x05: {
                                'Address': 'Online',
                                'LED': True
                            },
                            0x06: {
                                'Address': 'Go To Start',
                                'LED': True
                            },
                            0x07: {
                                'Address': 'Go To End',
                                'LED': True
                            },
                            0x08: {
                                'Address': 'Ext Trans',
                                'LED': True
                            },
                            0x09: {
                                'Address': 'LoopPlay',
                                'LED': True
                            },
                            0x0a: {
                                'Address': 'Loop Record',
                                'LED': True
                            },
                            0x0b: {
                                'Address': 'Quick Punch',
                                'LED': True
                            },
                            0x0c: {  # oddly placed
                                'Address': 'Talkback',
                                'Zone': 'Utility'
                            },
                            0x0d: {
                                'Address': 'Rewind',
                                'LED': True
                            },
                            0x0e: {
                                'Address': 'Forward',
                                'LED': True
                            },
                            0x0f: {
                                'Address': 'Stop',
                                'LED': True
                            },
                            0x10: {
                                'Address': 'Play',
                                'LED': True
                            },
                            0x11: {
                                'Address': 'Record',
                                'LED': True
                            },
                            0x12: {
                                'Address': 'Scrub',
                                'LED': True,
                                'CmdClass': 'C24jpot'
                            },
                            0x13: {
                                'Address': 'Shuttle',
                                'LED': True,
                                'CmdClass': 'C24jpot'
                            }
                        }

                    }
                }
            },  # END Command Buttons
            0x00: {
                'Address': 'track',
                'TrackByte': 2,
                'TrackByteMask': 0x1F,
                'ChildByte': 1,
                'Children': {
                    0x00: {
                        'Address': 'RecArm',
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x04: {
                        'Address': 'pre_post_assign_mute',  ## changed
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x01: {
                        'Address': 'Pan_Send',
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x02: {
                        'Address': 'EQ',
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x03: {
                        'Address': 'Dynamics',
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x0A: {
                        'Address': 'Inserts',
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x05: {
                        'Address': 'c24automode',
                        'Zone': 'Channel',
                        'CmdClass': 'C24automode'  ## this button has 5 leds (WR,TC,LT,TM,RD)
                    },
                    0x06: {
                        'Address': 'ChannelSelect',
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x07: {
                        'Address': 'Solo',
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x08: {
                        'Address': 'Mute',
                        'Zone': 'Channel',
                        'LED': True
                    },
                    0x09: {
                        'Address': 'Touch',
                        'Zone': 'Faders',
                        'CmdClass': 'C24fader'
                    },
                    0x0B: {
                        'Address': 'Peak',
                        'Zone': 'Analogue Section',
                        'LED': True
                    },
                    0x0C: {
                        'Address': 'Source Toggle',
                        'Zone': 'Analogue Section'
                    },
                    0x0D: {  # not in sm map
                        'Address': 'Roll Off',
                        'Zone': 'Analogue Section'
                    }
                }
            }  # END Channel Strip Buttons
        }
    },  # END L1 Button
    0xF0: {
        'Address': 'led',
        'ChildByte': 3,
        'Children': {
            0x30: {
                'Address': 'TimeCodeMessageID'
            },
            0x40: {
                'Address': 'DisplayMessageID'
            },
            0x20: {
                'Address': 'LedMessageID'
            },
            0x10: {
                'Address': 'MeterMessageID'
            },
            0x00: {
                'Address': 'TurnKnobLedMessageID'
            }
        }
    },  # END L1 LED
    0xFF: {
        'Address': 'automation_LED_CounterMode_LED',
        'ChildByte': 1,
        'Children': {
            0xFE: {
                'Address': 'AutomationLED',
                'ChildByte': 2,
                'Children': {
                    0xF0: {'Address': 'Read'},
                    0xF1: {'Address': 'TM'},
                    0xF2: {'Address': 'Latch'},
                    0xF3: {'Address': 'Touch'},
                    0xF4: {'Address': 'Write'},
                    0xF5: {'Address': 'Off'}
                }
            },

            0xFF: {
                'Address': 'CounterModeLED',
                'ChildByte': 2,
                'Children': {
                    0xF0: {'Address': 'Hours_ms'},
                    0xF1: {'Address': 'Hours_Frames'},
                    0xF2: {'Address': 'Feet_Frames'},
                    0xF3: {'Address': 'Bars_beat'},
                    0xF4: {'Address': 'Off'}
                }
            },
            0x00: {
                'Address': 'UnknownNullFoundAfterFader'
            }
        }
    },  # END L1 AutomationLED/CounterModeLED
    0x00: {
        'Address': 'Null'
    },  # END L1 Null
    0xD0: {
        'Address': 'Ackt'
    }  # END L1 Ackt
}
