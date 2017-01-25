from django.shortcuts import render
from django.conf import settings

import json

def index(request):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    return render(request, 'main/index.html', context)

def main(request):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    return render(request, 'main/main.html', context)

def header(request):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
        
    if not request.user.is_authenticated():
        context['user'] = '__noUser__'
    else:
        context['user'] = request.user.first_name
    
    return render(request, 'main/header.html', context)

def logos(request):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    return render(request, 'main/logos.html', context)

def left(request):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    return render(request, 'main/left.html', context)

def close(request):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    return render(request, 'main/close.html', context)