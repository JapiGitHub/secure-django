from django.db import models
from django.contrib.auth.models import User 

#default users model doesnt have field for profile pics. so we have to
#extend user model and create new profile model that has 1:1 ratio to user.       user = models.OneToOneField(User)
#one user will have one profile and one profile will be associated with one user.
#aina kun teemme muutoksia modelsseihin, niin pitää muistaa tehdä makeMigr ja migration

#inherits models.Model
class Profile(models.Model):
	#1:1 ratio. one user per profile.  CASCADE = jos user poistetaan, niin poista myös profiili, mutta jos 
	#poistat profiilin, niin useria EI poisteta.
	user = models.OneToOneField(User, on_delete=models.CASCADE)
	#tähän voisi lisätä bio, city, mitä vaan mitä haluat profiilissa olevan
	#profilepic.  muista pip install Pillow (kuvan käsittelyyn tarvitaan toi)
	image = models.ImageField(default='default.jpg', upload_to='profile_pics')

	#dunder\double underscore   tarvitaan jotta tiedetään miten haluamme profile objectin printattavan.
	#jos EMME lisää tätä DUnderia, niin print(Profile) = profileObject, mutta ei mitään tietoa, nyt siihen tulee  nimi+" "+Profile
	#anytime you use print() you’re also calling the __str__ method on whatever object you’re trying to print.
	def __str__(self):
		return f'{self.user.username} Profile'