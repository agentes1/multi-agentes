{
    'name': 'API Notifier',
    'version': '1.0',
    'depends': ['base', 'bus', 'web'],
    'installable': True,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'api_notifier/static/src/js/notification_listener.js',
        ],
    },
}
