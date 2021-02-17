from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile

#inherits from usercreatoinform
class UserRegisterForm(UserCreationForm):
	#default tarkistaa, että on oikea maili. muut usernamet jne tulee inheritancen kautta usercreationformista
	email = forms.EmailField() 

	#Meta: nested namespace  for configurations and keeps the confs in one place. wihtin the confs, the model that is goin to be 
	#affected is the User model.. form.save() -> seivaa sen tonne User modeliin
	#password kahteen kertaan, koska user kirjoittaa sen kahteen kertaan ja se testataan että ne täsmää
	class Meta:
		#model that interacts with this is User, koska se sinne lisätään. when this form validates it creates new user
		model = User
		#fields that are shown in our form AND the order that they are shown
		fields = ['username', 'email', 'password1', 'password2']

#model form = works with specidif database model . esim form joka updateee user modelin
#inherits from forms.ModelForm
class UserUpdateForm(forms.ModelForm):
	email = forms.EmailField() 

	class Meta:
		model = User
		fields = ['username', 'email']
		#huom! tähän ei saa profile picturea, koska se on eri modulessa. user vs profile module on erillään. kts class ProfileUpdateForm(forms.ModelForm):   alempana

class ProfileUpdateForm(forms.ModelForm):
	class Meta:
		model = Profile 
		fields = ['image']