from django.shortcuts import render, redirect
#messages.debug/info/success/warning/error
#flash messages on kivoja, koska ne näkyy vain kerran. esim home sivulla näkyy onnistuneen rekisteröinnin
#jälkeen "account created!", mut jos päivitat sen home sivun, ni viesti katoaa
from django.contrib import messages


#formit on classeja mitkä convertoituu html:ksi
from django.contrib.auth.forms import UserCreationForm

def register(request):
	# POST viittaa http request tyyppiin (POST vs GET).     register.html : <form method="POST">
	if request.method == 'POST':
		form = UserCreationForm(request.POST)
		# post data on todnäk tosta meidän regestration formista, mutta ei pakosti, eli se pitää tarkistaa
		#is_valid() = backend testing: passwords match, ei käytössä oleva username etc printtaa myös error messages
		if form.is_valid():
			#save() makes the actual user, hashes the passwd etc.
			form.save()
			#form.cleaned_data = dictionary. converted to python types from form and validated tossa ylempänä
			username = form.cleaned_data.get('username')
			#muista lisätä base templateen tuki messagessille
			messages.success(request, f'Account created for {username}!')
			#redirect  lähettää userin nyt onnistuneen rekisteröinnin jälkeen blog-home sivulle
			#blog/urls.py : path('', views.home, name='blog-home'),
			return redirect('blog-home')
	else:
		form = UserCreationForm()
	return render(request, 'users/register.html', {'form': form})