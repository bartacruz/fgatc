"""
Django settings for fgserver project.
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

#METAR_URL='http://weather.noaa.gov/pub/data/observations/metar/stations'
METAR_URL='https://tgftp.nws.noaa.gov/data/observations/metar/stations'
METAR_UPDATE = 60*60 # in seconds
MESSAGES_FILE = '/opt/git/fgatc/multiplaymgr.cxx'
DEFAULT_CONTROLLERS = {
        50:'fgserver.atc.controllers.Controller', # ATIS
        51: 'fgserver.atc.controllers.Controller', # UNICOM
        52: 'fgserver.atc.controllers.Controller', # Clearance Delivery
        53: 'fgserver.atc.controllers.Ground', # Ground Control
        54: 'fgserver.atc.controllers.Tower', # Tower
        55: 'fgserver.atc.controllers.Approach', #Approach
        56: 'fgserver.atc.controllers.Departure', #Departure
        }
BROKER_URL = 'django://'

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Port that server listens
FGATC_SERVER_PORT=5100

FGATC_AI_INTERVAL=0.1
FGATC_UPDATE_RATE=2

# Relay to FG multipĺayer servers
FGATC_RELAY_ENABLED=True
FGATC_RELAY_SERVER = ('217.78.131.42',5000)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '2iqo)@&ls#f#@$8-r)=t%h3u4ri$t$q4ec2h*pc^k=k5v%8_e%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
) 

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'channels',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'fgserver',
    'fgserver.ai',
    'fgserver.atc',
    'fgserver.map',
    'fgserver.tracker',
    
)

MIDDLEWARE = (
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'fgserver.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fgserver.wsgi.application'

# Channels configuration (websocket updates for the map)
ASGI_APPLICATION = "fgserver.routing.application"
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'fgatc',
        'USER': 'fgatc',
        'PASSWORD': '********',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'
STATIC_ROOT='/var/www/fgatc/static/'


# TODO: Switch to memcached?
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake'
    },
    'positions': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'positions'
    },
    'aircrafts': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'aircrafts'
    },
    'circuits': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'circuits'
    },
    'controllers': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'controllers'
    },
          
    'airports': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'airports'
    },
}
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
        'console':{
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'debugfile':{
           'class':'logging.handlers.WatchedFileHandler',
            'filename': '/opt/log/fgatc.log',
            'formatter': 'verbose',
        },
    },
   'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'fgserver': {
            'handlers': ['console', 'debugfile'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django': {
            'handlers': ['console','debugfile'],
            'level': 'ERROR',
            'propagate': True,
        },

    },
    'formatters': {
        'verbose': {
            'format' : "[%(asctime)s] %(levelname)s %(message)s",
            'datefmt' : "%Y-%m-%d %H:%M:%S"
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
}

