"""django_portfolio URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
#import as  koska kun importtaat viewssejä, niin on hyvä merkta ne, että mitä ne on as ____. näin ne nimet ei ole päällekkäin. esim alempi user_views vs auth_views
from django.contrib.auth import views as auth_views
from django.urls import path, include
from users import views as user_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', user_views.register, name='register'),
    path('profile/', user_views.profile, name='profile'),
    #login and logout are class based views
    #template_name määrittää sijainnin mistä se etsii tota. defaulttina etsisi  registration/login.html
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    #jos jätät logouttiin tyhjäksi   as_view(),  niin logout toimii, mutta näyttää admin sivun logouttia xD
    path('logout/', auth_views.LogoutView.as_view(template_name='users/logout.html'), name='logout'),
    #include = chops off what ever part of URL has matched until this point and only sends forward the to URLs.py (blog kansiosta)
    path('', include('blog.urls')),
    
]
