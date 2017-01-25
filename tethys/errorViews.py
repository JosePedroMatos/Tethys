'''
Created on 30/05/2016

@author: Ze Pedro
'''
from django.shortcuts import render_to_response
from django.conf import settings

def badRequest400(request, exception):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    if request.path.startswith('/admin/'):
        template_name='400.html'
    else:
        template_name='main/400.html'
    return page_not_found(request, exception, template_name=template_name, context=context)

def forbidden403(request, exception):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    if request.path.startswith('/admin/'):
        template_name='403.html'
    else:
        template_name='main/403.html'
    return render_to_response(template_name=template_name, context=context)
    
def notFound404(request, exception):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    if request.path.startswith('/admin/'):
        template_name='404.html'
    else:
        template_name='main/404.html'
    return render_to_response(template_name=template_name, context=context)
    
def serverError500(request):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    
    if request.path.startswith('/admin/'):
        template_name='500.html'
    else:
        template_name='main/500.html'
    return render_to_response(template_name=template_name, context=context)