from django.shortcuts import render
#from .xx    .=samassa folderissa kuin tämä tiedosto
from .models import Post

#dummy data jos haluat testata ilman model/databasea
#home(request) pitää olla context = { 'posts':posts}  jotta se linkkaa ton oikein
'''
posts = [
	{
		'author': 'Janne K',
		'title': 'otsikkooo',
		'content': 'lorem ipsum mofo',
		'date_posted': '10.2.2021'
	},
	{
		'author': 'Janne K',
		'title': 'otsikko2',
		'content': 'pelkkää p**** tilalla',
		'date_posted': '10.2.2021'
	}

]
'''


def home(request):
	#context = dictionary mikä ottaa ton posts listan vastaan (sis dictionaryja postauksista)
	#key = 'posts'   ja value on se lista niistä postauksista
	context = {
		'posts': Post.objects.all()
	}
	#return HttpResponse('<h1>home lol</h1>')   näin voit kirjoittaa suoraan HTML:ää
	#return render(request, 'tähän se tiedosto tuolta templates kansion alta')   näin voit käyttää templateja
	#toki pinnan alla view aina returnaa joko HttpResponsen  tai  exception/error, mutta render vaa tekee tosta näppärämpää, kuin
	#kuin että load, render and pass it to HttpResponse
	#render(x,x,context) kolmas argumentti context = you can pass information to home.html
	return render(request, 'blog/home.html', context)

def about(request):
	return render(request, 'blog/about.html', {'title':'About'})