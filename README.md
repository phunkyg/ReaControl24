# Welcome to DEV_OtherDevices!

If you are here then you are probably have a device other than a Control24.
This is an experimental new version with many new features, that has been overhauled to provide support for:

* ProControl
    * So far just the main unit
* Other devices - contact PhunkyG for more info on getting your device supported!


# ReaControl

Legacy Digidesign control surface protocol middleware for Reaper.

This middleware allows you to use the Legacy Digidesign control surface hardware with Reaper, including Control24 and ProControl. 
(From here on in, they will be called a 'Desk' for speed)
It will allow you to establish communication between the desk and Reaper.OSC or any other similar DAW with OSC capability.
It will bring the Desk online and provide 2 way communiation with it, so you can control the DAW by using the device buttons, faders and pots, and the DAW can update the desk fader positions, LEDs and displays.


### Installing - OSX, macos, Linux

Ensure the current or default python environment has a 2.7.x interpreter in the current path (enter 'python' at the command line to check), and install the pre-requisites into user environment using pip or similar

Example pip install command line:

```
pip install -r requirements.txt --user
```

By default all log outputs will be created into the *logs* subdirectory below wherever you unpack/install the files, so choose somewhere that this can happen without issues.

### Installing - Windows 10

The pre-requisite installation process for Windows is quite a bit more involved, as the OS does not come supplied with python or packet capture libraries. We have provided an instruction video for this process [in the docs repository](https://github.com/phunkyg/ReaControl-docs)

* Download and install latest 64 bit Python 2.7.x
    * General Download Page: https://www.python.org/downloads
    * Windows 64 bit 2.7.13 Web Installer: https://www.python.org/ftp/python/2.7.13/python-2.7.13.amd64.msi
    * It is recommended to install python in the system drive, in a subfolder e.g. C:\python
    * In the installer options, at a minimum ensure that the following are set:
        * Install pip
        * Install for all users
* Download and install Npcap 
    * Home Page: https://nmap.org/npcap/
    * Current version of Main Installer: https://nmap.org/npcap/dist/npcap-0.99-r8.exe
    * Make sure to tick the _WinPcap API-compatible mode_ which is off by default
    * Don't install the loopback adapter unless you want it for another need
* Download the Npcap SDK
    * Current version of SDK Download: https://nmap.org/npcap/dist/npcap-sdk-1.01.zip
* Download and install the c++ compiler for python: https://www.microsoft.com/en-us/download/details.aspx?id=44266
* Download the sources from github for: pypcap (currently 1.2.1): https://github.com/pynetwork/pypcap/releases - 

(Following is a re-statement of the procedure for 'installation from sources' of pypcap found at - https://github.com/pynetwork/pypcap/blob/master/docs/index.rst)

Choose a folder to work in: Creating an 'install' subfolder under where you unpacked this repo (ReaControl) is a reasonable choice.

* Unzip the pypcap download into the chosen install folder. 
    * Check if the zip made 2 folders called 'pypcap-1.2.0' or similar, one within the other. If so, move the inner one down a level so it sits under 'install'
* Unzip the npcap sdk download. Again see if this results in an inner folder and if so, move it down.
* Rename the folder for this: "wpdpack"
* Start a windows command prompt from the start menu or run "cmd"
* use the CD command to get to the pypcap sources directory you just unzipped, then run the command as follows:

```
C:\Users\Public\Downloads\ReaControl24\install\pypcap-1.2.0> python setup.py install
```

* a lot of output will scroll up the screen, but towards the end should be shown:

```
Installed c:\python27\lib\site-packages\pypcap-1.2.0-py2.7-win-amd64.egg
```

* Now return to the main installation instructions to perform this command: 

```
pip install -r requirements.txt -U
```

When complete, to run the daemon, rather than using 'sudo', use an 'Administrator command prompt' and omit the sudo from the command line.
When supplying a network name, either the name (as it appears in the Windows network control panel settings) or the GUID will work. If you are struggling to find the right value, use the -n command line switch with a junk/bad value and the program will fail, but will list all your network adapter GUID and Names for you.


## Getting Started

Copy the files to your system in a reasonable spot (your REAPER Scripts directory for example) where you will be able to run the python programs and log files can be created.

For a quick start, if your DAW and Desk are on the same LAN, and you intend to run this middleware on your DAW computer:

* Set up Reaper.OSC for your environment. See the additional guide below for details.
* For windows start an Administrator command prompt, for other OS a normal terminal will do and use 'sudo' to prefix the commands. 
* Run the *daemon process*
```
sudo python ReaControl.py
```

* You should see a little feedback in each window as each component connects to the others
* If you have problems:
    * try adding the debug switch (-d) to the command lines to get much more feedback
    * The Log files will also contain a detailed CSV version of what you see
    * If your network addresses and ports aren't right, try supplying the network switch on the daemon process (-n) with a rubbish name. This will dump a list of valid networks to help you choose.
```
sudo python ReaControl.py -n NO_NETWORK
```
    * You can then use the network name or GUID to identify where your desk is connected, e.g:
```
sudo python ReaControl.py -n en1
```
    

### How to set up Reaper.OSC

Setting up Reaper.OSC is detailed in the Reaper documentation, but here is a quick guide to the required steps for ReaControl:

* Start Reaper
* Go to the *Preferences* dialog
* Scroll the left-hand side panel to the bottom and locate *Control/OSC/web*
* In the right-hand panel click *Add*
* Set the *Control surface mode* drop-down box to *OSC (Open Sound Control)*
* Click the *Pattern Config* drop-down box and choose *(open config directory)*
* Finder or Windows Explorer will now open at the OSC config files directory for your system
* Copy or move the *<desk_name>.ReaperOSC* file that matches your desk (or all of them!) provided with ReaControl into this directory
* Return to the Reaper OSC dialog (which should still be open) and again Click the *Pattern Config* drop-down box. Choose *(refresh list)*
* Click the *Pattern Config* drop-down box a final time, this time you should see and choose the entry that matches your desk e.g. *Control24*
* Complete the rest of the configuration in the dialog. The settings below are an example and may vary for your environment:
    * *Device Name* = any suitable name e.g. "ReaControl"
    * *Mode* = Configure device IP + local port
    * *Device Port* = 9124
    * *Device IP* = The IP address of the computer running ReaControl client process e.g: 192.168.1.10
    * *Local listen port* = 9125
    * *Local IP* = The IP address of the Reaper computer on the same network or the same computer e.g: 192.168.1.10
    * *Allow binding...learn* = Tick/Yes
    * *If outgoing packets..... values* = The defaults are fine
* Click OK to save the Reaper.OSC configuration. Your new entry should appear in the list


### Advanced options

Use the --help command line switch for each process and the possibilities will be shown. Addresses and ports can be set for TCP/IP links, and the network interface can be set to state where the Desk can be found.

### Prerequisites

```
Python 2.7.x
netifaces
pyOSC
pypcap (build from source)

OSC capable DAW such as Reaper 5.x
```

For Windows:

```
Npcap
Npcap SDK
Microsoft C++ compiler for Python
```

### Known Issues

Some older python installations in OSX do cause issues as they pre-date upgrades in the python security/encryption, so please ensure you are at the highest OS level you can be, and if that is not enough, you can find guides online on how to make the changes you need to python, or to install a second python environment just for ReaControl.


### Compatibility

Although ReaControl is written in python, it depends on certain libraries like pypcap, that can vary from platform to platform. Testing of various platforms is ongoing, status at this time is:


|Platform|Reacontrol|OSC clients|
|---|---|---|
|macos 10.14.x|Full|Full|
|Windows 10|Full|Full|
|macos < 10.13|May require python upgrade/2nd environment|ditto|
|Rasbpian June 2018|Full|Full|
|Rasbpian prior|OK in theory|OK in theory|
|Other Linux|OK in theory|OK in theory|

Please let us know if you try another, we will update our list or help with any issues.

## Usage

By default, the daemon will attempt to use the first active Ethernet adapter found in the system. It will also set up its listener on the first IP address of that adapter.
The OSC client will do much the same, but it will only use the IP address as it doesn't require the network adapter name.
Log files will be created in a 'logs' subdirectory relative to where the processes are ran from.

All this can be changed by use of command line parameters. Use the --help switch to get the current definition and defaults.

```
python ReaControl.py --help
```

To exit either process, press CTRL+C on the keyboard in the shell window, or send the process a SIGINT.
In Windows, close the Command Prompt window where you launched the program.

## Running the tests

By way of an apology, may this bring levity to your day
"Son where we're going, we don't need no tests"

Seriously though, without a dedicated piece of test hardware, this isn't easy.

Some small inroads have been made in this area:

* The file emulator.py will act like a pseduo desk and accounce itself to ReaControl. Once connected it will toggle a mute button every few seconds


If you are frequently testing OSC mapping file edits, it is very useful to symlink your OSC files instead of copying them, e.g.

```
$ ln -s /Users/you/Documents/ReaControl24/Control24.ReaperOSC /Users/you/Library/Application\ Support/REAPER/OSC/Control24.ReaperOSC
$ ln -s /Users/you/Documents/ReaControl24/ProControl.ReaperOSC /Users/you/Library/Application\ Support/REAPER/OSC/ProControl.ReaperOSC
```


### Coding standards

50% NOOB, 49% IDIOT, 1% Beer driven lunacy. Any contributors should feel free to laugh and point, as long as the criticism can be usefully applied.
Some improvements have been made since the early days, we strive to be more 'pythonic' and keep things clean!

Latest code uses a class pattern for OSC client code. The 'ReaCommon.py' file contains the base classes, then the device specific .py file adds any specifics.
This helps where the implementation is pretty much the same for some controls and small diffferences are needed.

## Deployment

At a minimum you can connect the desk to a spare LAN port on your DAW PC. You can connect both Desk and DAW through a switch or bridge. Anything like a gateway or router is unlikely to allow the traffic, in such cases a Pi or other small linux SBC is a good idea then the OSC traffic can be routed to the DAW PC.

The ReaControl.py daemon process MUST be on a host with an interface in the same LAN segment as the Desk. It will self-launch the right client process and manage the subprocesses. The daemon process and DAW may reside anywhere that you can route the traffic between (VPN etc), but it might be VERY difficult to route traffic between the Desk and ReaControl.
If you use a dedicated SBC like a Raspberry pi, you may wish to add the startup of the scripts to your system startup commands, so the communication is available right after boot, and you can effectively run the SBC 'headless'.

## How it Works

The Ethernet packets are captured using a Packet Capture utility, called pcap, sometimes know as a 'network sniffer'.
Only packets for the Desk are captured, **all other normal (TCP and UDP) network traffic is ignored** by use of a capture filter.
This takes the place of a 'Network Driver', which you often find comes on a disk with these kinds of devices and you have to install it, giving it very low level access to your PC.
ReaControl requires your to give it permission every time you run it, so it is as secure if not more so than a driver.
ReaControl's 'daemon' process then deals with this network traffic, and passes it to its 'client' process.
The 'client' process translates the Desk's midi-like binary language to OSC and vice-versa, passing binary messages back to the 'daemon' process which then sends them back as network packets to the Desk.
Finally, the OSC messages are sent as normal TCP/IP packets to the Reaper.OSC extension, which drives the DAW, according to the mappings found in the control file, OR in the Actions list. Return OSC messages are sent back to the 'client' process for the return trip, again as normal TCP/IP packets.

Each component can be on a separate computer, or all on the same one.

Some basic stateful mode handling is provided by the 'client' process to receive text from the DAW and display it on the scribble strips, handle controls which can toggle, and deal with issues like fader command echos.

You will need super user (or elevated Administrator in Windows) privileges to use this software (specifically the daemon process'), as it uses packet capture libraries (libpcap / npcap) to establish network connectivity with the Desk ethernet interface. All other TCP and UDP traffic is ignored/filtered out, so you should not have any privacy concerns if the source has not been tampered with.


## Customisation

A starting Reaper.OSC file is provided with some basic mappings to the OSC address schema. Feel free to add to this as required by your preferences or any new good mappings. Please share (by commit to this repo, or just let us know) anything that proves useful.

To make a new mapping, check out the help text in the Default Reaper.OSC file provided by Cockos
Add lines with the token at the start, then followed by the OSC address pattern.

The schema (i.e. the OSC addresses generated by the osc clients) is determined by the <desk>map.py file for each device model, each 'address' attribute being appended to the path for the relevant control.
One of the easiest ways to find an address is run the OSC client with the debug switch added, then press the button or control. The address and other information will be appended to the log.

For an entry in the <desk>map.py, you can use the attribute 'CmdClass' to identify the python class that will define the handler for the control. In this way you can implement more complex logic in a python class over and above the 'duh send this address' default. This is faders, scribble strips etc. are set up already, so that pattern can be followed.

Other attributes determine how the tree is 'walked' according to the binary received from the desk. Byte numbers are zero origin, the first denotes the actual command:
    ChildByte       which byte to look up to find the next child
    ChildByteMask   apply this 8 bit mask before lookup. It must then be equal (same bits set)
    ChildByteMatch  the byte has to have the same bits set as the match byte. It can have more bits set but not fewer 
    (You can either Mask or Match but not both!)
    TrackByte       which byte to identify the channel strip/track number
    TrackByteMask   apply this mask before determining track
    ValueByte       which byte to identify a simple value
    ValueByteMask   apply this mask before determining value


## Contributing

Get a github account, and join in. That simple.
There is some chatter on the Reaper Forums too, but when working, testing or contributing then GitHub is the way to go.

This is freeware, non warranty, non commercial code to benefit the hungry children and hungrier DAW users of the world. If you pull and don't contribute, you should feel bad. Real bad. 
Please develop here in this repo for the benefit of all. All pull/merge requests will be accepted and best efforts made to make sense of it all when merging. If a fork serves you better, then please feel free, but try to let us pull any good stuff you might come up with.

Welcome to the latest contributors and collaborators! Your help is very much appreciated.

## Versioning

We will attempt to use [SemVer](http://semver.org/) for versioning. For the versions available, see the tags on this repository.

## Authors

* **PhaseWalker18** - *Beer Consumption, code defecation*  (sadly no longer with us)
* **DisruptorMon** - *Slave Driving, cheap beer supply, testing* 

If you are feeling especially thankful for this entering your life, please feel free to send donations to this BTC address which goes to PhaseWalker's legacy: 1BPQvQjcAGuMjBnG25wuoD64i7KmWZRrpN

### Contributors

* **phunkyg** - Current Maintainer
* **lasloos** - Pro Control tester

See also the list of contributors via github for the latest picture. Thanks to everyone who gets involved. If you want to see your name here just shout up!

## License

This project is licensed under the GPLv3 License - see the [COPYING.md](COPYING.md) file for details
All other intellectual property rights remain with the original owners.

## Acknowledgments

* **2mmi** - *Initial Idea, inspiration and saviour of us all


### OSC SChema

# This is a draft section that will be updated as we discover more of the map

Notes:
    Channel Strips are referred to as 'track'

/track/@                        Reference to a track object with next token being the number
    /<classattribute>           Reference to a CmdClass within a track object                      
        reabuttonled            CmdClass controlling LED buttons
        etc

/clock

/<classattribute>               Reference to CmdClasses in the desk object
    clock                       Reference the the ReaClock i.e. the clock display
    reabuttonled                CmdClass controlling LED buttons that aren't in a track

/action                         Numbered action - not yet implemented