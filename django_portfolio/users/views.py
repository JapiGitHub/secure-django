from django.shortcuts import render, redirect
#messages.debug/info/success/warning/error
#flash messages on kivoja, koska ne näkyy vain kerran. esim home sivulla näkyy onnistuneen rekisteröinnin
#jälkeen "account created!", mut jos päivitat sen home sivun, ni viesti katoaa
from django.contrib import messages

#formit on classeja mitkä convertoituu html:ksi
#tätä ei enää tarvittu kun teimme UserRegisterFormin mikää inheritoi tämän ja lisäksi myös siinä on email jne.
#from django.contrib.auth.forms import UserCreationForm

from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm

from django.contrib.auth.decorators import login_required



def register(request):
	# POST viittaa http request tyyppiin (POST vs GET).     register.html : <form method="POST">
	if request.method == 'POST':
		form = UserRegisterForm(request.POST)
		# post data on todnäk tosta meidän regestration formista, mutta ei pakosti, eli se pitää tarkistaa
		#is_valid() = backend testing: passwords match, ei käytössä oleva username etc printtaa myös error messages
		if form.is_valid():
			#save() makes the actual user, hashes the passwd etc.
			form.save()
			#form.cleaned_data = dictionary. converted to python types from form and validated tossa ylempänä
			username = form.cleaned_data.get('username')
			#muista lisätä base templateen tuki messagessille
			messages.success(request, f'Your account has been created! You are now able to log in.')
			#redirect  lähettää userin nyt onnistuneen rekisteröinnin jälkeen blog-home sivulle
			#blog/urls.py : path('', views.home, name='blog-home'),
			return redirect('login')
	else:
		form = UserRegisterForm()
	return render(request, 'users/register.html', {'form': form})


@login_required
def profile(request):
	if request.method == 'POST':
		#..Form(instance=request.user)  =  tällä saadaan täyttämään muokattavat kentät tämän hetken arvoilla, esim username ja email kohtiin. populate forms with the current users info  
		#jos instancet on väärin, niin saattaa tehdä vaan uusia usereita vanhan päivittämisen sijaan. admin sivulta on helppo tarkistaa.
		u_form = UserUpdateForm(request.POST, instance=request.user) #request.POST = pass the POST data.  instance = username ja email
		p_form = ProfileUpdateForm(request.POST,
									request.FILES,
									instance=request.user.profile) #request.FILES = kuvatiedosto.   instance = current avatar image
		if u_form.is_valid() and p_form.is_valid():
			u_form.save()
			p_form.save()
			messages.success(request, f'Your account has been updated!')
			#tässä kannattaa tehdä redirect jotta ei tuu sitä "jos päivität ni haluatko uudestaan submit tiedot?" 
			#= post get redirect pattern: redirect aiheuttaa, ettei lähetetäkkään enää POST vaan GET -> no weird message
			return redirect('profile')
	else:
		u_form = UserUpdateForm(instance=request.user) #username ja email
		p_form = ProfileUpdateForm(instance=request.user.profile) #current avatar image
	
	context = {
		'u_form': u_form,
		'p_form': p_form
	}
	return render(request, 'users/profile.html', context)