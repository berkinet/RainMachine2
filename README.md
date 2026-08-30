# RainMachine2
Indigo plugin for Rain Machine

## Version 1.0.3

Transient RainMachine API timeouts no longer terminate Indigo's concurrent
plugin thread. The affected controller is marked temporarily unavailable while
its last-known watering and program states are preserved. The plugin logs one
concise error, retries after 10 seconds, and logs once when communication
recovers.

Rain Machine Plugin has been developed for Indigo Home Automation version 2022.1 and hopefully beyond. It uses python3<br>

Installation Instructions:<br>
Download the plugin zip file from github<br>
It requires a working python3 installation and the ability to install a new library to enable the plugin.<br>
Open a terminal window (Applications -> Utilities -> Terminal app<br>
type "pip3 install regenmaschine"<br>
type "pip3 freeze | grep regenmaschine" and confirm that 2022.11.2 or greater is installed<br>
Quit Terminal<br>
Unzip plugin and install the plugin by double clicking and allowing it to be installed and enabled in indigo<br>
Create a new indigo device of type RainMachine2 from the new device menu<br>
At top of dialog box after selecting device type, select "Model - HD12" (even if you have HD16 - I don't have either the Mini or Pro models, but this should work on them as well. It may not work on first generation devices or ones that have not had their firmware updated so it is using API 4.6.1 which is needed for the flowmeter. You can check the API version by going to the RainMachine web interface and looking in the "About" section)<br>

On popup dialog choose either local or cloud login.<br>
On local machine you login with the IP address of the RainMachine device (you should be able to get this from the rainmachine itself under "About" or lookup on your router) and the device password<br>
On a cloud device you need to have set up an account with RainMachine company and use your username and password for your https://my.rainmachine.com/login?redirect_uri=/devices account<br>
I do not have a rainmachine cloud account and will not be maintaining this if the company changes their login. Would suggest using local access as best idea<br>
Do not change port unless you have RainMachine running on a different port<br>
Enter password and hit login<br>
If successful, you should see a list of RainMachine devices to chose from<br>
Once selected hit save<br>

Plugin Configuration:<br>
Use Plugins -> RainMachine2 -> Configure to set the polling interval. The
default is 60 seconds and the supported range is 10 to 3600 seconds. A
10-second interval provides more responsive active-zone and remaining-time
updates while retaining the original 60-second behavior for existing
installations.<br>

One-time zone list export:<br>
The repository includes `tools/export_zones.py`, which connects directly to a
local RainMachine and writes a tab-separated list containing each zone number
and name. The password is requested securely and is not placed on the command
line.<br>
Run `python3 tools/export_zones.py RAINMACHINE_IP` to print the list to the
terminal. Use normal shell redirection—such as
`python3 tools/export_zones.py RAINMACHINE_IP > rainmachine-zones.txt`—to save
it. The tool uses the same `aiohttp` and `regenmaschine` packages required by
the plugin.<br>
The installed plugin also provides **Plugins -> RainMachine2 -> Export Zone
List**, directly below **Update Devices**. It writes the zone list directly to
the Indigo event log using the plugin's existing authenticated connection.<br>

You can create either triggers or schedules to start a program, stop a program, start a zone, stop a zone or stop all watering<br>
Ceate a new trigger/schedule with whatever constraints you want for it to run<br>
Under the third tab "Actions", select "Device Actions", select RainMachine2 Controls<br>
In the popup, select the rainmachine device you want to conrtol<br>
Select the program or zone you want to control, for zone start there is a duration, for programs it runs the program as it exists on the rainmachine device<br>
In the details, if you have a flowmeter installed and enabled, it will count the watering and leak clicks and report a combined gallons.<br>
To setup the flow meter you need to use the web interface of the local rainmachine or the cloud based one to enable and set clicks per gallon.<br>

Please don't ask for further features to setup the rainmachine device, change names of zones, list the prior watering, etc. This is already well implemented in the webapp, phone app and on the machine itself. This plugin is just designed to allow you to trigger/schedule starting and stoping of programs and zones from Indigo. If you want more info, go to the device or login to the web interface of the device.<br>
