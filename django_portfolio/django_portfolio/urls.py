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

#urls esimerkiksi profile pic varten (profile.html:  {{ user.profile.image.url }})
from django.conf import settings
from django.conf.urls.static import static

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
    
    #password reset route
    #Allows a user to reset their password by generating a one-time use link that can be used to reset the password, and sending that link to the user’s registered email address.
    #If the email address provided does not exist in the system, this view won’t send an email, but the user won’t receive any error message either. This prevents information leaking to potential attackers.
    path('password-reset/',
        auth_views.PasswordResetView.as_view(template_name='users/password_reset.html'),
        name='password-reset'),
    #kun password on resetoitu succesfully and email has been sent:
    path('password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'),
        name='password_reset_done'),
    #Presents a form for entering a new password.
    #ilman tätä confirmia antaa tälläsen errorin: NoReverseMatch at /password-reset/   : Reverse for 'password_reset_confirm' not found
    #{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}
    #  uidb64 = id encoded in base64
    #   esim:  janne  =   amFubmU=
    #  token = token to check that the password is valid
    path('password-reset-confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(template_name='users/password_reset_confirm.html'),
        name='password_reset_confirm'),

    path('password-reset-complete/',
        auth_views.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'),
        name='password_reset_complete'),

    #include = chops off what ever part of URL has matched until this point and only sends forward the to URLs.py (blog kansiosta)
    path('', include('blog.urls')),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)





