# ReaControl24

Control24 digital control surface protocol middleware for Reaper.

This middleware allows you to use the Digidesign Control24 hardware with Reaper. 
It will allow you to establish communication between the Control24 hardware and Reaper.OSC or any other similar DAW with OSC capability.
It will bring the Control24 online and provide 2 way communiation with it, so you can control the DAW by using the Control24 buttons, faders and pots, and the DAW can update the Control24 fader positions, LEDs and displays.
ReaControl24 isn't a Reaper plugin (yet) but is designed to work with Reaper. There is nothing to stop you using it in a wider OSC setup or with a different DAW that supports OSC.

### Installing - OSX, macos, Linux

Ensure the current or default python environment has a 2.7.x interpreter in the current path (enter 'python' at the command line), and install the pre-requisites into user environment using pip or similar

Example pip install

```
pip install -r requirements.txt --user
```

By default all log outputs will be created into the temp location for your platform and user. This will vary according to your platform, so the logfile names are also output to the screen for convenience.

Some older python installations in OSX do cause issues as they pre-date upgrades in the python security/encryption, so please ensure you are at the highest OS level you can be, and if that is not enough, you can find guides online on how to make the changes you need to python, or to install a second python environment just for ReaControl.

### Installing - Windows 10

The pre-requisite installation process for Windows is quite a bit more involved, as the OS does not come supplied with python or packet capture libraries. We have provided an instruction video for this process in the docs subfolder in the repository.

* Download and install latest 64 bit Python 2.7.x - https://www.python.org/downloads
* Download and install Npcap ensuring to tick the WinPcap API-compatible mode which is off by default - https://nmap.org/npcap/
    * Current version of Main Installer: https://nmap.org/npcap/dist/npcap-0.99-r7.exe
* Download the Npcap SDK
    * Current version of SDK Download: https://nmap.org/npcap/dist/npcap-sdk-0.1.zip
* Download and install the c++ compiler for python - https://www.microsoft.com/en-us/download/details.aspx?id=44266
* Download the sources from github for: pypcap - https://github.com/pynetwork/pypcap/releases - currently 1.2.1

(Following is a re-statement of the procedure for 'installation from sources' of pypcap found at - https://github.com/pynetwork/pypcap/blob/master/docs/index.rst)

Choose a folder to work in: The 'install' subfolder of ReaControl24 is a reasonable choice.

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

When complete, to run the daemon, rather than using 'sudo', use an 'Administrator command prompt' and omit the sudo
When supplying a network name, either the name or the GUID will work. If you are struggling to find the right value, use the --help command line switch and the program will list them for you.


## Getting Started

Unzip/Copy the files to your system in a reasonable spot (your REAPER Scripts directory, or just your documents folder for example) where you will be able to run the python programs.
For a quick start, if your DAW and Control24 are on the same LAN, and you intend to run this middleware on your DAW PC:

*Start REAPER DAW and configure the Control Surface OSC Plugin:
    *Reaper > Preferences > Control/OSC/web
    *First time, click 'Add' and select Control Surface Mode 'OSC (Open Sound Control)'
    *Device name: Control24
    *Mode: Configure device IP+local port
    *Device port: 9124
    *Device IP: Your local IP address (not localhost or 0.0.0.0)
    *Local listen port: 9125
    *Local IP: same as Device IP
    *Allow binding...: tick
*Click the 'Pattern Config' selector and you will find an option 'Open config directory'.
*Copy the provided Reaper.OSC file into the directory that reaper opened.
    *For example, on OSX, you could copy using the terminal with
```
cp Control24.ReaperOSC "~/Library/Application Support/REAPER/OSC/Control24.ReaperOSC"
```
    ...or use your file manager to perform the same file copy.
*Going back to the Reaper OSC dialog, click 'Pattern Config' and this time 'Refresh List'
*Click 'Pattern Config' one last time, now you can select the new entry 'Control24'
*Start the daemon process with (yes you DO need sudo, or for windows omit sudo and use Administrator command prompt):
```
sudo python control24d.py
```
*Start the osc client process with:
```
python control24osc.py
```
*Now load up a project in Reaper and try a few controls like faders and pots
*If Reaper moves the faders on the Control24 and vice-versa, you are good to go
*If not, check all the network IP and ports match up, you may need to specify a preferred adapter or address - see below

### Advanced options

Use the --help command line switch for each process and the possibilities will be shown. Addresses and ports can be set for TCP/IP links, and the network interface can be set to state where the Control24 can be found.

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

# How it Works

The Ethernet packets are captured using a Packet Capture utility, sometimes know as a 'network sniffer'.
Only packets for the Control24 are captured, all normal network traffice is ignored.
ReaControl's 'daemon' process then deals with this network traffic, and passes it to its 'client' process.
The 'client' process translates the Control24's binary language to OSC and vice-versa, passing binary messages back to the 'daemon' process which then sends them back as network packets to the Control24.
Finally, the OSC messages are sent as normal TCP/IP packets to the Reaper.OSC extension, which drives the DAW, according to the mappings found in the control file, OR in the Actions list. Return OSC messages are sent back to the 'client' process for the return trip, again as normal TCP/IP packets.

Each component can be on a separate computer, or all on the same one.

Some basic stateful mode handling is provided by the 'client' process to receive text from the DAW and display it on the scribble strips, handle controls which can toggle, and deal with issues like fader command echos.

You will need super user (or elevated Administrator in Windows) privileges to use this software (specifically the daemon process'), as it uses packet capture libraries (libpcap / npcap) to establish network connectivity with the Control24 ethernet interface. All other TCP and UDP traffic is ignored/filtered out, so you should not have any privacy concerns if the source has not been tampered with.

### Compatibility

Although ReaControl24 is written in python, it depends on certain libraries like pypcap, that can vary from platform to platform. Testing of various platforms is ongoing, status at this time is:


|Platform|control24d|control24osc|
|---|---|---|
|macos 10.13.x|Full|Full|
|Windows 10|Full|Full|
|macos < 10.13|May require python upgrade/2nd environment|ditto|
|Rasbpian June 2018|Full|Full|
|Rasbpian prior|OK in theory|OK in theory|
|Other Linux|OK in theory|OK in theory|

Please let us know if you try another, we will update our list or help with any issues.

## Usage

By default, the daemon will attempt to use the first active Ethernet adapter found in the system. It will also set up its listener on the first IP address of that adapter.
The OSC client will do much the same, but it will only use the IP address as it doesn't require the network adapter name.
Log files will be created in a new subdirectory in the users temp directory. This will vary according to your platform and username.

All this can be changed by use of command line parameters. Use the --help switch to get the current definition and defaults.

```
python control24d.py --help
```

To exit either process, press CTRL+C on the keyboard in the shell window, or send the process a SIGINT.
In Windows, close the Command Prompt window where you launched the program.

## Running the tests

By way of an apology, may this bring levity to your day
"Son where we're going, we don't need no tests"

Seriously though, without a dedicated piece of test hardware, this isn't easy. Some effort may be made to emulate traffic in the future!

### Coding standards

50% NOOB, 49% IDIOT, 1% Beer driven lunacy. Any contributors should feel free to laugh and point, as long as the criticism can be usefully applied.
Some improvements have been made since the early days, we strive to be more 'pythonic' and keep things clean!

## Deployment

The daemon process MUST be on a host with an interface in the same LAN segment as the Control24. It will present an IP socket that uses python multiprocessing library. The control24osc process and DAW may reside anywhere that you can route the traffic to.
If you use a dedicated SBC like a Raspberry pi, you may wish to add the startup of the scripts to your system startup commands, so the communication is available right after boot, and you can effectively run the SBC 'headless'.

## Customisation

A starting Reaper.OSC file is provided with some basic mappings to the OSC address schema. Feel free to add to this as required by your preferences or any new good mappings. Please share (by commit to this repo, or just let us know) anything that proves useful.

To make a new mapping, check out the help text in the Default Reaper.OSC file provided by Cockos
Add lines with the token at the start, then followed by the OSC address pattern.

The schema (i.e. the OSC addresses generated by the control24osc.py) is determined by the control24map.py file, each 'address' attribute being appended to the path for the relevant control.
One of the easiest ways to find an address is run the OSC client with the debug switch added, then press the button or control. The address and other information will be appended to the log.

For an entry in the control24map.py, you can use the attribute 'CmdClass' to identify the python class that will define the handler for the control. In this way you can implement more complex logic in a python class over and above the 'duh send this address' default. This is faders, scribble strips etc. are set up already, so that pattern can be followed.

Other attributes determine how the tree is 'walked' according to the binary received from the desk. Byte numbers are zero origin, the first denotes the actual command:
    ChildByte       which byte to look up to find the next child
    ChildByteMask   apply this 8 bit mask before lookup
    TrackByte       which byte to identify the channel strip/track number
    TrackByteMask   apply this mask before determining track
    ValueByte       which byte to identify a simple value
    ValueByteMask   apply this mask before determining value


## Contributing

Get a github account, and join in. That simple.

This is freeware, non warranty, non commercial code to benefit the hungry children and hungrier DAW users of the world. If you pull and don't contribute, you should feel bad. Real bad. 
Please develop here in this repo for the benefit of all. All pull/merge requests will be accepted and best efforts made to make sense of it all when merging. If a fork serves you better, then please feel free, but try to let us pull any good stuff you might come up with.

Welcome to the latest contributors and collaborators! Your help is very much appreciated.

## Versioning

We will attempt to use [SemVer](http://semver.org/) for versioning. For the versions available, see the tags on this repository.

## Authors

* **PhaseWalker18** - *Beer Consumption, code defecation*  (sadly no longer with us)
* **DisruptorMon** - *Slave Driving, cheap beer supply, testing* 

If you are feeling especially thankful for this entering your life, please feel free to send donations to this BTC address: 1BPQvQjcAGuMjBnG25wuoD64i7KmWZRrpN

### Contributors

* **phunkyg** - Current Maintainer
* **lasloos** - Pro Control tester

See also the list of contributors via github for the latest picture.

## License

This project is licensed under the GPLv3 License - see the [COPYING.md](COPYING.md) file for details
All other intellectual property rights remain with the original owners.

## Acknowledgments

* **2mmi** - *Initial Idea, inspiration and saviour of us all
