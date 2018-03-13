# ReaControl24

Control24 digital control surface protocol middleware.

This middleware will allow you to establish communication between the Control24 hardware and Reaper.OSC or any other similar DAW with OSC capability.
It will bring the Control24 online and provide 2 way binary communiation with it (daemon process).
It will translate between the binary protocol of the desk and OSC messages to exchange with the DAW (client process).

Some basic stateful mode handling is provided to receive text from the DAW and display it on the scribble strips, and deal with issues like fader command echos.

You will need super user (or elevated Administrator in Windows) privileges to use this software, as it uses libpcap packet capture library to establish network connectivity with the Control24 ethernet interface. All other TCP and UDP traffic is ignored/filtered out, so you should not have any privacy concerns if the source has not been tampered with.


### Installing - OSX, macos, Linux

Ensure the current or default python environment has a 2.x interpreter in the current path, and install the pre-requisites into user environment using pip or similar

Example pip install

```
pip install -r requirements.txt --user
```

By default all log outputs will be created into a subdirectory below wherever you install the files, so choose somewhere that this can happen without issues

### Installing - Windows 10

The installation process for Windows is quite a bit more involved, as the OS does not come supplied with several requirements:

* Download and install Python 2.7.x - https://www.python.org/downloads
* Download and install Npcap ensuring to tick the WinPcap API-compatible mode which is off by default - https://nmap.org/npcap/
* Download and install the c++ compiler for python - https://www.microsoft.com/en-us/download/details.aspx?id=44266
* Download the sources from github for: pypcap - https://github.com/pynetwork/pypcap/releases - currently 1.2.0

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
When supplying a network name, either the name or the GUID will work


## Getting Started

Copy the files to your system in a reasonable spot (your REAPER Scripts directory for example) where you will be able to run the python programs and log files can be created.
For a quick start, if your DAW and Control24 are on the same LAN, and you intend to run this middleware on your DAW PC:

Copy the provided Reaper.OSC file into the correct directory on your system for such files. You will find a convenient button in the reaper dialogs to find this for you when configuring the csurf plugin.

Start REAPER DAW and configure the Control Surface OSC Plugin. Use your local IP address (not localhost or 0.0.0.0)
Set ports as client 9124 and listener 9125.

Start the deamon process with (yes you DO need sudo, or for windows omit sudo and use Administrator command prompt):

```
sudo python control24d.py
```

Start the osc client process with:

```
python control24osc.py
```

### Prerequisites

```
Python 2.7.x
netifaces
pyOSC
pypcap (build from source)

OSC capable DAW such as Reaper 5.x
```

Also, the winpcapy library (re-distributed here for now, until a repostiory is found):

```
winpcapy.py, Authored by (c) Massimo Ciani 2009
```

### Compatibility

Although ReaControl24 is written in python, it depends on certain libraries like pypcap, that are usually wrappers around C libraries. These can vary from platform to platform. Testing of various platforms is ongoing, status at this time is:


|Platform|control24d|control24osc|
|---|---|---|
|macos 10.13.x|Full|Full|
|macos < 10.13|OK in theory|OK in theory|
|Rasbpian ?|Full|Full|
|Other Linux|OK in theory|OK in theory|
|Windows 10|In Progress (DEV_Compatibility branch)|Full|


## Usage

By default, the daemon will attempt to use the first active Ethernet adapter found in the system. It will also set up its listener on the IP address of that adapter.
The OSC client will do much the same, but it will only use the IP address as it doesn't require the network adapter name.
Log files will be created in a 'logs' subdirectory relative to where the processes are ran from.

All this can be changed by use of command line parameters. Use the --help switch to get the current definition and defaults.

```
python control24d.py --help
```

To exit either process, press CTRL+C on the keyboard in the shell window, or send the process a SIGINT.
In Windows, close the Command Prompt window where you launched the program.

## Running the tests

By way of an apology, may this bring levity to your day
"Son where we're going, we don't need no tests"

### Coding standards

50% NOOB, 49% IDIOT, 1% Beer driven lunacy. Any contributors should feel free to laugh and point, as long as the criticism can be usefully applied.

## Deployment

The daemon process MUST be on a host with an interface in the same LAN segment as the Control24. It will present an IP socket that uses python multiprocessing library. The control24osc process and DAW may reside anywhere that you can route the traffic to.

## Customisation

A starting Reaper.OSC file is provided with some basic mappings to the OSC address schema. Feel free to add to this as required by your preferences or any new good mappings. Please share (by commit to this repo) anything that proves useful.

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

This is freeware, non warranty, non commercial code to benefit the hungry children and hungrier DAW users of the world. If you pull and don't contribute, you should feel bad. Real bad. 
Please develop here in this repo for the benefit of all. All pull and merge requests will be accepted and best efforts made to make sense of it all when merging.

Welcome to the latest contributors and collaborators! Your help is very much appreciated.

## Versioning

We will attempt to use [SemVer](http://semver.org/) for versioning. For the versions available, see the tags on this repository.

## Authors

* **PhaseWalker18** - *Beer Consumption, code defecation*
* **DisruptorMon** - *Slave Driving, cheap beer supply, testing* 

If you are feeling especially thankful for this entering your life, please feel free to send donations to this BTC address: 1BPQvQjcAGuMjBnG25wuoD64i7KmWZRrpnN

See also the list of contributors via github.

## License

This project is licensed under the GPLv3 License - see the [COPYING.md](COPYING.md) file for details
All other intellectual property rights remain with the original owners.

## Acknowledgments

* **2mmi** - *Initial Idea, inspiration and saviour of us all

