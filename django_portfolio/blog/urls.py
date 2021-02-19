from django.urls import path
from .views import (
	PostListView, 
	PostDetailView, 
	PostCreateView, 
	PostUpdateView,
	PostDeleteView)
#. = current Dir    eli importtaa ton views.py blog kansiosta
from . import views

urlpatterns = [
	#home = ''
	#views.home = views.py -> func home
	#.as_view() = because it has to be converted to actual view
    path('', PostListView.as_view(), name='blog-home'),
    #<int:pk>  = only accept integer(kukaan ei voi laittaa esim stringiä tähän):PrimaryKey databasesta = 
    #esim : http://127.0.0.1:8000/post/1/
    path('post/<int:pk>/', PostDetailView.as_view(), name='post-detail'),
    path('post/new/', PostCreateView.as_view(), name='post-create'),
    path('post/<int:pk>/update/', PostUpdateView.as_view(), name='post-update'),
    path('post/<int:pk>/delete/', PostDeleteView.as_view(), name='post-delete'),
    path('about/', views.about, name='blog-about'),
]

#template naming millä ajango etsii:
# <app>/<model>_<viewtype>.html
# blog/post_list.html