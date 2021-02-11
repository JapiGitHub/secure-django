from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

# Create your models here.

#ei users/authors modelia, koska se tulee eri kautta
#posts model/database pitää tehdä
#model = databasesta saatu object

class Post(models.Model):
	#CharField = lyhyet stringit
	#TextField = piktät tekstit
	title = models.CharField(max_length=100)
	content = models.TextField()
	#models.DateTimeField(auto_now=True)       :last modified
	#models.DateTimeField(auto_now_add=True)   :created, mutta et voi muuttaa tota enää sit
	#models.DateTimeField(default=timezone.now):ottaa huomioon kirjoittajan timezonen? huom timezone.now on 
	#funktio, mutta emme laita timezone.now() sulkuja, koska emme halua ajaa sitä funktiota nyt. haluamme
	#vain osoittaa että default on se funktio
	date_posted = models.DateTimeField(default=timezone.now)
	#many to one -relatioship = userilla voi olla monta postausta, mutta postauksella vain 1 useri -> foreign key
	#on_delete=CASCADE  : jos user poistetaan, niin poista myös postaukset siltä
	#mutta jos poistat postauksen, niin useria ei tietenkään poisteta!
	author = models.ForeignKey(User, on_delete=models.CASCADE)
	#muutosten jälkeen, muista tehdä manage.py migrate

	def __str__(self):
		return self.title