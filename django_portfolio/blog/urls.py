from django.urls import path
from .views import (
	PostListView, 
	PostDetailView, 
	PostCreateView, 
	PostUpdateView,
	PostDeleteView,
	UserPostListView)
#. = current Dir    eli importtaa ton views.py blog kansiosta
from . import views

urlpatterns = [
	#home = ''
	#views.home = views.py -> func home
	#.as_view() = because it has to be converted to actual view
    path('', PostListView.as_view(), name='blog-home'),
    #path('', views.homeViews, name='blog-home'),
    #path('base/', PostSideListView.as_view(), name='blog-base'),
    path('user/<str:username>', UserPostListView.as_view(), name='user-posts'),
    #<int:pk>  = only accept integer(kukaan ei voi laittaa esim stringiä tähän):PrimaryKey databasesta = 
    #esim : http://127.0.0.1:8000/post/1/
    path('post/<int:pk>/', PostDetailView.as_view(), name='post-detail'),
    path('post/new/', PostCreateView.as_view(), name='post-create'),
    path('post/<int:pk>/update/', PostUpdateView.as_view(), name='post-update'),
    path('post/<int:pk>/delete/', PostDeleteView.as_view(), name='post-delete'),
    path('about/', views.about, name='blog-about'),
    path('to-do/', views.to_do, name='blog-to-do'),
    path('gitlog/', views.gitlog, name='blog-gitlog'),
    path('admin/', views.admin, name='admin'),
    path('ctf/', views.ctf, name='blog-ctf'),
]

#template naming millä ajango etsii:
# <app>/<model>_<viewtype>.html
# blog/post_list.html
