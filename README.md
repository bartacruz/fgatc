# fgatc
FlightGear AI ATC and Aircraft multiplayer server
**In early-alpha stage**

The project contains:
* Nasal script that detects COMM frequency and tune in to AI ATC in the server. 
  Includes a dialog for sending messages

* Multiplayer server that 
  * creates AI ATCs on demand and react to player's messages
    For instance, you can send a message like 
    > San Francisco Tower, Ready to taxi, YOURCALLSIGN 
    and the AI ATC that you are tunned in will respond with something like 
    > YOURCALLSIGN, Taxi to runway 28 and hold short
  * Also creates AI traffic that can be configured with the Django admin app

* Django admin app for configuration and administration of airports, aircrafts and AI traffic.
  
* An interactive map (made with Leaflet), that shows current multiplayer and AI traffic.


## Requirements

* Python (tested with v2.7)
* Django (tested with v1.6)
  `pip install django==1.6.11`
* Python database driver for your DB of choice (psycopg2, python-mysql,etc)  
* Geographiclib <https://pypi.python.org/pypi/geographiclib>
  Install with `pip install geographiclib`  
* Metar <http://sourceforge.net/projects/python-metar/>
  Download sources and install with `python setup.py install`
* NumPy 
  `pip install scipy`
* SciPy <http://www.scipy.org/>
  Install with `pip install scipy`
* South 
  Install with `pip install south`
* Django Admin Bootstrapped (optional)
  Install with `pip install django-admin-bootstrapped==1.6.3`
  Make sure you install the 1.6.3 version. 
  

Most of this packages (except python-metar) comes with all major Linux distributions. 
Try installing them with Apt, Yum, etc.

## Install

0. Make sure you have all the requirements installed.
1. Grab the code and place it in some directory (D'oh!).
2. Create a database.
3. Edit settings.py to suit your needs (mostly db configuration)
4. Generate the tables with
	$ python manage.py syncdb 
	$ python manage.py migrate

There's a neat Nasal script in the Nasal directory that does all the magic in the FlightGear side. 
You can install it in your FlightGear root directory or in your local .fgfs/ directory, under `Nasal/`.

There is also another neat script in `fgserver/tools/airport_importer.py` that imports ALL the airports 
and runway information into the database from FlightGear's apt-dat.gz (or any X-Plane v810 airport file)

## Usage
1. Run the Django app: `$ python manage.py runserver`
2. Point to your host, port 8000 (i.e.: <http://localhost:8000>) and do some admin stuff like:
  * Create airports and runways
  * Create AI Aircrafts.
3. Run the server: `$ python server.py`
4. Start Flightgear and use the server address as a multiplayer server.
  Now you can use the menu with the key `'` and communicate with the towers.
5. Access the interactive map in `/map/` (i.e.: <http://localhost:8000/map/>). 
  With no other parameters, it will show the SABE area (Buenos Aires). 
  Use the `icao` parameter to customize the startup location of the map. (i.e.: <http://localhost:8000/map/?icao=KSFO>) 

** NOTE **: As you *may* have noticed, English is not my mother's tongue. If your eyes are bleeding for my spelling and/or grammar mistakes, feel free to edit this file (or any other) and make any corrections you like! 