import logging
import logging.handlers
import sys


LEVEL = logging.INFO

DEFAULT_LOGGING = {
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] - slp - %(levelname)s -- %(message)s',  # noqa: E501
            'datefmt': '%Y-%m-%d %H:%M:%S'}
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'stream': sys.stdout
        },
        'logfile': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename': 'debug.log',
            'maxBytes': 10485760,
            'backupCount': 20,
            'encoding': 'utf8'
        },
        'remote': {
            'level': 'INFO',
            'class': 'logging.handlers.SocketHandler',
            'formatter': 'default',
            'host': '0.0.0.0',
            'port': logging.handlers.DEFAULT_TCP_LOGGING_PORT
        }
    },
    'root': {
        'level': LEVEL,
        'handlers': ['console', 'logfile', 'remote']
    },
    'disable_existing_loggers': False
}
