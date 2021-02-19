from django.shortcuts import render
#@login_required decorator oli function based viewseissä, mutta class basedeihin tarvii tän
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
	ListView, 
	DetailView, 
	CreateView,
	UpdateView,
	DeleteView)
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
#function based views:
#  url patterns -> directed to views (functions) -> function handles the logic for the routes and render template
#class based views:
#  list views,  (esim listaa kaikki postaukset allekkain)
#  detail views, (tarkempi näkymä yhdestä postista)
#  create views, 
#  update views, 
#  delete views, etc
#class basedissa just setting some variables, mutta 
#function basedissa viewssa had to actually render a function ja tarkalleen kertoa miten renderoida

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

#class based view: 
class PostListView(ListView):
	model = Post
	
	#default template naming millä ajango etsii:
	# <app>/<model>_<viewtype>.html
	# blog/post_list.html
	# template_name voi määrittää sen erikseen ettei yritä etsiä tota post_list.html
	template_name = 'blog/home.html'

	#function based  context {'posts': Post.objects.all()}  =?  class based  context_object_name = 'posts'
	context_object_name = 'posts'

	#date_posted 	oldest to newest
	#-dated_posted  newest up
	ordering = ['-date_posted']

class PostDetailView(DetailView):
	model = Post
	# <app>/<model>_<viewtype>.html = blog/post_detail.html

#LoginRequiredMixin  : jos yrität mennä logged out tekemään uutta postausta, ni se menee login sivulle joka muistaa seuraavan stepin: 
#http://127.0.0.1:8000/login/?next=/post/new/
class PostCreateView(LoginRequiredMixin, CreateView):
	model = Post
	fields = ['title', 'content']

	#jotta saadaan author lisättyä: (muuten tulee NULL virhe kun authoria ei ole )
	def form_valid(self, form):
		#that form u ar trying to submit, before u do that, take that instance and set tha author to current logged in user
		form.instance.author = self.request.user
		#run the form valid method on our parent class. se ois ajettu muutenkin
		#mutta kun overridaamme, niin tää author pitää asettaa ennen
		return super().form_valid(form)

class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
	model = Post
	fields = ['title', 'content']

	#jotta saadaan author lisättyä: (muuten tulee NULL virhe kun authoria ei ole )
	def form_valid(self, form):
		#that form u ar trying to submit, before u do that, take that instance and set tha author to current logged in user
		form.instance.author = self.request.user
		#run the form valid method on our parent class. se ois ajettu muutenkin
		#mutta kun overridaamme, niin tää author pitää asettaa ennen
		return super().form_valid(form)

	#UserPassesTestMixin runs test_func jotta näkee onko user oikea muokkaamaan postausta. eli logged in user pääsee
	#muokkaamaan VAIN omia postauksia, eikä kaikkien userien tietenkään.
	#override UserPassesTestMixin test_func
	#https://docs.djangoproject.com/en/3.1/topics/auth/default/
	def test_func(self):
		post = self.get_object()
		if self.request.user == post.author:
			return True
		return False

class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
	model = Post
	#jos delete onnistuu, niin ohjaa meidät home sivulle
	success_url = '/'

	#checkkaa, että user yrittää poistaa vain omia viestejä
	def test_func(self):
		post = self.get_object()
		if self.request.user == post.author:
			return True
		return False


def about(request):
	return render(request, 'blog/about.html', {'title':'About'})
