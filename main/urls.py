from django.conf.urls import url
from django.conf import settings
from . import views
from django.views import static
import django.contrib.auth.views

app_name = 'main'

urlpatterns = [
    url(r'^main.html$', views.main, name='main'),
    url(r'^left.html$', views.left, name='left'),
    url(r'^header.html$', views.header, name='header'),
    url(r'^logos.html$', views.logos, name='logos'),
    url(r'^close/$', views.close, name='close'),
    url(r'^static/(?P<path>.*)$', static.serve, {'document_root': settings.STATIC_ROOT}),
    url(r'^$', views.index, name='index'),
    url(r'^accounts/login/', django.contrib.auth.views.login, name='login')
]