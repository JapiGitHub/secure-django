from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'

    #django recommends to do this this way estääkseen ongelmia
    def ready(self):
    	import users.signals