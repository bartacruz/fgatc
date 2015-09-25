#FlightGear AI ATC and Aircraft multiplayer server

A complete FlightGear multiplayer server with AI ATC, AI Planes, interactive map. Messages are sent and received only in the tunned frequency. 

**In beta stage**. Fully functional, but with many bugs.

The project contains:
* Nasal script that detects COMM frequency and tune in to AI ATC in the server. 
  Includes a dialog for sending messages.

* Multiplayer server that
  * relays positions of near planes.
  
  * creates AI traffic that can be configured with the Django admin app
  
  * creates AI ATCs on demand and react to player's messages
    
  For instance, you can send a message like 

> San Francisco Tower, Ready to taxi, YOURCALLSIGN 

  and the AI ATC that you are tunned in will respond with something like 
 
> YOURCALLSIGN, Taxi to runway 28 and hold short
 

* Django admin app for configuration and administration of airports, aircrafts and AI traffic.
  
* An interactive map (made with Leaflet), that shows current multiplayer and AI traffic.


## Requirements

* Python (tested with v2.7)
* Django (tested with v1.6)

  `pip install django==1.6.11`
* Python database driver for your DB of choice (psycopg2, python-mysql,etc)  
* [Geographiclib] (https://pypi.python.org/pypi/geographiclib)

  Install with `pip install geographiclib`  
* [Metar] (http://sourceforge.net/projects/python-metar/)

  Download sources and install with `python setup.py install`
* NumPy 

  `pip install scipy`
* [SciPy] (http://www.scipy.org/)

  Install with `pip install scipy`
* South 

  Install with `pip install south`
* Django Admin Bootstrapped (optional)

  Install with `pip install django-admin-bootstrapped==1.6.3`

  **Make sure you install the 1.6.3 version.** 
  

Most of this packages (except python-metar) comes with all major Linux distributions. 
Try installing them with Apt, Yum, etc.

If you want to create a virtualenv, use the `requirements.txt` file to install all the dependencies.

## Install


0. Make sure you have all the requirements installed.
1. Grab the code and place it in some directory (D'oh!).
2. Create a database.
3. Edit settings.py to suit your needs (mostly db configuration)
4. Generate the tables with

	```
	$ python manage.py syncdb 
	$ python manage.py migrate
	s```

5. Install the [Nasal script](Nasal/)

There is a neat script in `fgserver/tools/airport_importer.py` that imports ALL the airports, whith runway and comm information, into the database from FlightGear's apt-dat.gz (or any X-Plane v810 airport file)

## Usage

1. Run the Django app: `$ python manage.py runserver`
2. Point to your host, port 8000 (i.e.: <http://localhost:8000>) and do some admin stuff like:
  * Create airports and runways
  * Create AI Aircrafts.
3. Run the server: `$ python server.py`
4. Start Flightgear and use the server address as a multiplayer server. The default port is 5100. Tune the radio to some controller's frequency.
  Now you can use the menu with the key `'` and communicate with the ATC controllers.
5. Access the interactive map in `/map/` (i.e.: <http://localhost:8000/map/>). 
  With no other parameters, it will show the SABE airport area (Buenos Aires, Argentina). 
  You can use the `icao` parameter to customize the startup location of the map. (i.e.: <http://localhost:8000/map/?icao=KSFO>) 

## Planned/ToDo
[x] Enhance METAR loading and caching.
[x] List of pilots on map (and click-to-pan to the pilot, of course!) 
[ ] Enhance AI tower's traffic management. 
[ ] Create more AI traffic types (currently there's only a _left circuit_ )
[ ] Implement ground routes directions using Dijkstra's shortest path algorithm.
[ ] Relay positions to FlightGear's official MP servers.
[ ] Enhance map interactions
[ ] Implement [RAAS] (http://wiki.flightgear.org/Runway_Awareness_and_Advisory_System)
[ ] ATIS service
[ ] Transponder code
[ ] Use [OpenRadar] (http://wiki.flightgear.org/OpenRadar) aliases for ATC responses


## NOTE
As you *may* have noticed, English is not my mother's tongue. If your eyes are bleeding for my spelling and/or grammar mistakes, feel free to edit this file (or any other) and make any corrections you like! 