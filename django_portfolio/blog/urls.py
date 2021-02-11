from django.urls import path
#. = current Dir    eli importtaa ton views.py blog kansiosta
from . import views

urlpatterns = [
	#home = ''
	#views.home = views.py -> func home
    path('', views.home, name='blog-home'),
    path('about/', views.about, name='blog-about'),

]