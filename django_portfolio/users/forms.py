from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

#inherits from usercreatoinform
class UserRegisterForm(UserCreationForm):
	#default tarkistaa, että on oikea maili. muut usernamet jne tulee inheritancen kautta usercreationformista
	email = forms.EmailField() 

	#Meta: nested namespace  for configurations and keeps tje confs in one place. wihtin the confs, the model that is goin to be 
	#affected is the User model.. form.save() -> seivaa sen tonne User modeliin
	#password kahteen kertaan, koska user kirjoittaa sen kahteen kertaan ja se testataan että ne täsmää
	class Meta:
		#model that interacts with this is User, koska se sinne lisätään. when this form validates it creates new user
		model = User
		#fields that are shown in our form AND the order that they are shown
		fields = ['username', 'email', 'password1', 'password2']