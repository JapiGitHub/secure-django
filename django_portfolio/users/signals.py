#kun db objecti on tehty save() eli myös toki esim user.post_set.create(...) koska _set tekee saven myös
#signals = run function after joku action. tässä esim User on signalin sender, kun uusi user luodaan
#receiver on se funktio joka tekee tän (decoraattorina tässä)
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile

#kun user luodaan, niin sender lähettää post_save signaalin receiverille/create_profile funktiolle.
#receiver ottaa sen vastaan ja se on/decorate tää create_profile funktio.
#post_save välitti noi argumentit  (sender, instance, created, **kwargs) .. instance= instance of user
@receiver(post_save, sender=User)
# **kwargs = ottaa vastaan kaikki extra keyword arguments funktion loppuun
def create_profile(sender, instance, created, **kwargs):
	#jos user is created -> create user where the user is the instance (eli se mikä nyt on kyseessä/uusi)
	if created:
		Profile.objects.create(user=instance)

#jos profiili tallennettaan muutoksen jälkeen
@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
	instance.profile.save() #instance on jälleen vaan se kyseinen useri. vähän niinku self?