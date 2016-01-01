#Django Application

The Django app contains the administration interface and an interactive map.

## Instalation

* Create a database in your favorite django-supported engine.
* Copy `settings-dist.py` to `settings.py` and edit the file to suit your needs (mostly DB configuration and application paths)
* Run the database creation scripts. 
```
$ python manage.py syncdb
$ python manage.py migrate
```

## Starting

### Command Line
You can run the Django app from command line with 

```
$ python manage.py runserver

```

### WSGI
Example Apache conf with virtualenv. Code resides in `/opt/git/fgatc`, virtualenv in `/opt/virtual_fgatc`, static files in `/var/www/fgatc/static` (don´t forget to run `python manage.py collectstatic`!).

```
WSGIPythonPath /opt/git/fgatc:/opt/virtual_fg/lib/python2.7/site-packages
<VirtualHost *:80>
ServerAdmin you@yourmailserver.com
ServerName fgatc

WSGIScriptAlias / /opt/git/fgatc/fgserver/wsgi.py

Alias /static/ /var/www/fgatc/static/
</VirtualHost>
<Directory /var/www/fgatc/static>
Require all granted
</Directory>

<Directory /opt/git/fgatc/fgserver>
<Files wsgi.py>
Require all granted
</Files>
</Directory>

```

# Use

Point your browser to localhost:8000

There are 2 urls to access the application:

* /admin to access the administration application. To log in, use the user you created during the database creation (syncdb)
 (or where you had configure it to run) 
* /map to access the interactive map.
