from django.shortcuts import render
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.conf import settings
from django_countries import countries
from timeSeries.models import Series, Value, Forecast, SatelliteData, Location, DataProvider, DataType, User
from .decoder import decode
#===============================================================================
# from django.utils.safestring import mark_safe
#===============================================================================
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse
from celery import task, current_task
from celery.result import AsyncResult
from djcelery.models import PeriodicTask, IntervalSchedule
from gpu.manager import Manager, getResampledTime, getDateList, fGenerateLeads, fSecond, fMinute, fHour, fDay, fWeek, fMonth, fYear
from . import satelliteData #@UnusedImport
from django.core.exceptions import ObjectDoesNotExist
from django_countries import countries

import binascii
import json
import warnings
import os
import datetime as dt
import dateutil.parser
import sys

import numpy as np
import matplotlib.pyplot as plt
import mpld3
from gpu.functions import plotQQ, ClickInfo


def viewSeries(request, seriesList):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
               }
    seriesDict = {}
    errorsDict = {'missing': list(),
                  'noAccess': list(),
                  'noData': list(),
                  }
    
    seriesList=seriesList.split('/')
    
    # find recent dates
    recentDates = []
    for seriesName in seriesList:
        tmpResult = Series.objects.filter(name=seriesName)
        if len(tmpResult)>0:
            s0 = tmpResult[0]
            recentDates.append(Value.objects.filter(series=s0.id).order_by('date').last().date)
    recentDate = max(recentDates)
    recentDate = recentDate.replace(year=recentDate.year-2)
    
    # retrieve series' info
    for seriesName in seriesList:
        tmpResult = Series.objects.filter(name=seriesName)
        if len(tmpResult)>0:
            s0 = tmpResult[0]
            result = Value.objects.filter(series=s0.id).order_by('date')
            if tmpResult[0].encryptionKey==None:
                values = [{'x':obj.date.isoformat(), 'y':str(obj.recordOpen)} for obj in result.filter(date__gte=recentDate)]
            else:
                values = [{'x':obj.date.isoformat(), 'y':binascii.b2a_base64(obj.record).decode("utf-8")} for obj in result.filter(date__gte=recentDate)]
            
            forecasts = {}
            for f0 in Forecast.objects.filter(targetSeries=s0.id).filter(ready=True):
                forecasts[f0.name] = {}
                forecasts[f0.name]['urlForecast'] = '/timeSeries' + reverse('forecast', 'timeSeries.urls', kwargs={'forecastName': f0.name})
                forecasts[f0.name]['urlHindcast'] = '/timeSeries' + reverse('hindcast', 'timeSeries.urls', kwargs={'forecastName': f0.name})
                forecasts[f0.name]['description'] = f0.description
                forecasts[f0.name]['leadTime'] = f0.leadTime
                forecasts[f0.name]['seasons'] = f0.splitBySeason
            
            if s0.location.country in dict(countries):
                tmpCountry = dict(countries)[s0.location.country]
            else:
                tmpCountry = ''
            tmp = {'id': s0.id,
                'name': s0.name,
                'type': s0.type.name,
                'provider': s0.provider.name,
                'providerAbbreviation': s0.provider.abbreviation,
                'providerIcon': '/' + str(s0.provider.icon),
                'providerWebpage': s0.provider.website,
                'units': s0.type.units,
                'typeIcon': '/' + str(s0.type.icon),
                'lat': float(s0.location.lat),
                'lon': float(s0.location.lon),
                'location': s0.location.name,
                'quality': s0.quality,
                'timeStepUnits': dict(Series.TIME_STEP_PERIOD_TYPE)[s0.timeStepUnits],
                'timeStepPeriod': s0.timeStepPeriod,
                'encryptionKey': s0.encryptionKey,
                'metaEncrypted': s0.metaEncrypted,
                'river': s0.location.river,
                'country': tmpCountry,
                'catchment': s0.location.catchment,
                'values': values,
                'records': len(result),
                'forecasts': forecasts,
                }
               
            if len(result)==0:
                errorsDict['noData'].append(seriesName)
                tmp.update({'minDate': '',
                            'maxDate': ''})  
            else:
                tmp.update({'minDate': result.first().date.isoformat(),
                            'maxDate': result.last().date.isoformat()})     
            seriesDict[str(s0)] = tmp
        else:
            errorsDict['missing'].append(seriesName)
        
    context['series'] = json.dumps(seriesDict)
    context['errors'] = json.dumps(errorsDict)
    
    # fields
    fields = (('Id', 'name'),
              ('Location', 'location'),
              ('River', 'river'),
              ('Catchment', 'catchment'),
              ('Type', 'type'),
              ('Units', 'units'),
              ('Time step', 'timeStepUnits'),
              ('Records', 'records'),
              ('From', 'minDate'),
              ('To', 'maxDate'),
              )
    context['fields'] = json.dumps(fields)
    
    return render(request, 'timeSeries/viewSeries.html', context)

def deleteTimeSeries(request, seriesName):
    series = Series.objects.filter(name=seriesName)
    if len(series)==0:
        context = {'message': ('error', 'The series ' + seriesName + ' has not been found in the database.')}
    else:
        tmp = Value.objects.filter(series=series).count()
        if tmp>0:
            Value.objects.filter(series=series).delete()
            context = {'message': ('success', str(tmp) + ' records successfully deleted.')}
        else:
            context = {'message': ('warning', 'No data to be deleted.')}

    return HttpResponse(
                        json.dumps(context),
                        content_type="application/json"
                        )
    
def upload(request, seriesName):
    series = Series.objects.filter(name=seriesName)
    if series:
        provider = series[0].provider
        location = series[0].location
        seriesType = series[0].type        
        
        result = Value.objects.filter(series=series[0].id).order_by('date')
        values = [{'x':obj.date.isoformat(), 'y':binascii.b2a_base64(obj.record).decode("utf-8")} for obj in result]
        
        context = {'LANG': request.LANGUAGE_CODE,
                   'series': series[0].name,
                   'encryptionKey': series[0].encryptionKey,
                   'metaEncrypted': series[0].metaEncrypted,
                   'timeStep': dict(Series.TIME_STEP_PERIOD_TYPE)[series[0].timeStepUnits],
                   'timeStepPeriod': series[0].timeStepPeriod,
                   'provider': str(provider),
                   'type': str(seriesType),
                   'units': seriesType.units,
                   'location': str(location),
                   'data': json.dumps(values),
                   'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
                   }
        return render(request, 'timeSeries/uploadValues.html', context)
    else:
        return HttpResponseNotFound('Series [' + seriesName + '] not found...')

def uploadTimeSeries(request, seriesName):
    # TODO: check provider pass
    
    # TODO: check duplicated values
    
    data = json.loads(request.POST.get('toUpload'))
    seriesObj = Series.objects.get(name=seriesName)
    
    warnings.filterwarnings('ignore', '.*Invalid utf8 character string.*',)
    
    toInput = list()
    for i0, d0 in enumerate(data):
        toInput.append(Value(series=seriesObj, date=d0['date'][:-1], record=binascii.a2b_base64(d0['value'])))
        if i0 % 1000==0 and i0!=0:
            Value.objects.bulk_create(toInput)
            toInput = list()
    Value.objects.bulk_create(toInput)
    
    context = {'message': 'done!'}
    return HttpResponse(
                        json.dumps(context),
                        content_type="application/json"
                        )

def seriesData(request):
    context = {}
    if request.method == 'POST':
        seriesObj = Series.objects.get(name=request.POST.get('series'))
        provider = seriesObj.provider
        location = seriesObj.location
        seriesType = seriesObj.type
        context = {'location': str(location),
                   'provider': str(provider),
                   'type': str(seriesType),
                   'units': seriesType.units,
                   'timeStepUnits': dict(Series.TIME_STEP_PERIOD_CHOICES)[seriesObj.timeStepUnits],
                   'timeStepPeriod': seriesObj.timeStepPeriod,
                   'metaEncrypted': seriesObj.metaEncrypted,
                   'encryptionKey': seriesObj.encryptionKey,
                   'name': seriesObj.name,
                   }
        return HttpResponse(
                            json.dumps(context),
                            content_type="application/json" 
        )

def getValues(request):
    context = {}
    if request.method == 'POST':
        s0 = Series.objects.get(name=request.POST.get('series'))
        dateFrom = dt.datetime.strptime(request.POST.get('from'), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo = None)
        dateTo = dt.datetime.strptime(request.POST.get('to'), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo = None)
        result = Value.objects.filter(series=s0, date__gte=dateFrom, date__lt=dateTo).order_by('date')
        if not result:
            tmp = Value.objects.filter(series=s0, date__lt=dateFrom)
            if tmp:
                tmp = tmp.latest('date')
                reference = tmp.date
                dateFrom = reference.replace(year=reference.year-1)
                result = Value.objects.filter(series=s0).filter(date__gte=dateFrom, date__lt=dateTo).order_by('date')
        if s0.encryptionKey==None:
            values = [{'x':obj.date.isoformat(), 'y':str(obj.recordOpen)} for obj in result]
        else:
            values = [{'x':obj.date.isoformat(), 'y':binascii.b2a_base64(obj.record).decode("utf-8")} for obj in result]
        
        context = {'values': values}
    return JsonResponse(context)
    
def fJumpDateFun (period):
    tmp = {'seconds': fSecond,
              'minutes': fMinute,
              'hours': fHour,
              'days': fDay,
              'weeks': fWeek,
              'months': fMonth,
              'years': fYear,
              }
    return tmp[period]

def fGetForecastData(forecastName, fromDate=None, toDate=None):
    forecast = Forecast.objects.filter(name=forecastName)
    timeStepUnits = forecast[0].targetSeries.TIME_STEP_DICT[forecast[0].targetSeries.timeStepUnits]
    timeStepPeriod = forecast[0].targetSeries.timeStepPeriod
    forecastTimeDelta = {timeStepUnits: timeStepPeriod}
    
    if fromDate==None:
        fromDate = Value.objects.filter(series=forecast[0].targetSeries.id).earliest('date').date
    if toDate==None:
        toDate = Value.objects.filter(series=forecast[0].targetSeries.id).latest('date').date
    
    if forecast:
        records = Value.objects.filter(series=forecast[0].targetSeries.id, date__gte=fromDate, date__lte=toDate).order_by('date')
        
        if forecast[0].targetSeries.encryptionKey==None:
            values = [float(r0.recordOpen) for r0 in records]
        else:
            values = decode([r0.record for r0 in records], forecast[0].targetSeries.encryptionKey)
        
        dates = [str(r0.date) for r0 in records]
        
        target = (dates, values)
        
        extra = []
        datesDesired = None
        fromDateExtra = fromDate.replace(year=fromDate.year-1)
        toDateExtra = toDate.replace(year=toDate.year+1)
        for s0 in forecast[0].extraSeries.filter().order_by('id'):
            timeStepUnits = s0.TIME_STEP_DICT[s0.timeStepUnits]
            timeStepPeriod = s0.timeStepPeriod
            extraTimeDelta = {timeStepUnits: timeStepPeriod}
            if datesDesired==None and extraTimeDelta!=forecastTimeDelta:
                datesDesired = getDateList(fromDate, toDate, **forecastTimeDelta)
            
            records = Value.objects.filter(series=s0).filter(date__gte=fromDateExtra).filter(date__lte=toDateExtra).order_by('date')
            
            if s0.encryptionKey==None:
                values = [float(r0.recordOpen) for r0 in records]
            else:
                values = decode([r0.record for r0 in records], s0.encryptionKey)
            dates = [r0.date for r0 in records]
            
            if extraTimeDelta!=forecastTimeDelta:
                datesExpected = getDateList(max(fromDateExtra, dates[0].replace(year=dates[0].year-1)), min(toDateExtra, dates[-1].replace(year=dates[-1].year+1)), **extraTimeDelta)
                dates, values = getResampledTime(datesDesired, datesExpected, dates, values)
            dates = [str(d0) for d0 in dates]

            extra.append((dates, [str(v0) for v0 in values]))
        if len(extra)==0:
            extra=None
            
        return (target, extra)
    else:
        return False

def trainForecastBase(request, forecastName):
    forecasts = Forecast.objects.filter(name=forecastName)
    if forecasts:
        forecast = forecasts[0]
        
        if forecast.jobId == '':
            if forecast.forecastFile.name != '' and os.path.isfile(forecast.forecastFile.path):
                os.remove(forecast.forecastFile.path)
            forecast.forecastFile.save(forecastName + '.gpu', ContentFile('dummy content'))
            
            info = {'leadTime': forecast.leadTime,
                    'seasons': forecast.splitBySeason,
                    'nodes': forecast.nodes,
                    'dataFunction': forecast.dataExpression,
                    'targetFunction': forecast.targetExpression,
                    'population': forecast.population,
                    'epochs': forecast.epochs,
                    'regularization': float(forecast.regularize),
                    'filePath': forecast.forecastFile.path,
                    'name': forecast.name,
                    'referenceDate': forecast.referenceDate.isoformat(),
                    'activationFunction': forecast.type,
                    'valFraction': 1-forecast.training/100,
                    'timeStepUnit': forecast.targetSeries.TIME_STEP_DICT[forecast.targetSeries.timeStepUnits],
                    'timeStepSize': forecast.targetSeries.timeStepPeriod,
                    'weigthRange': float(forecast.weigthRange),
                    'errorFunction': forecast.errorFunction,
                    'transformWeights': forecast.transformWeights,
                    'allowNegative': forecast.allowNegative,
                    'reduceTraining': float(forecast.reduceTraining),
                    'inertia': float(forecast.psoC0),
                    'c1': float(forecast.psoC1),
                    'c2': float(forecast.psoC2),
                    'c3': float(forecast.psoC3),
                    'forceNonExceedance': float(forecast.forceNonExceedance),
                    'trainingDates': forecast.trainingDates,
                    }
    
            target, extra = fGetForecastData(forecastName)
            
            #===================================================================
            # jobId = 1
            # forecasts.update(ready=False, jobId=jobId)
            # trainWrapper(info, target, extra)
            #===================================================================
            
            jobId = trainWrapper.delay(info, target, extra).id
            forecasts.update(ready=False, jobId=jobId)
            
        else:
            jobId=forecast.jobId
        
        context = {'LANG': request.LANGUAGE_CODE,
                   'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
                    'name': forecast.name,
                    'jobId': jobId,
                   }
        
        return render(request, 'timeSeries/trainProgress.html', context)
    else:
        return HttpResponseNotFound('Forecast [' + forecastName + '] not found...')

@task(name='train')
def trainWrapper(info, data, extra):
    try:
        data = [np.array([np.datetime64(s0) for s0 in data[0]]), data[1]]
        if extra!=None:
            for i0 in range(len(extra)):
                extra[i0] = [np.array([np.datetime64(s0) for s0 in extra[i0][0]]), extra[i0][1]]
         
        man = Manager(data, extra=extra,
                      dataFunction=info['dataFunction'], targetFunction=info['targetFunction'], 
                      nodes=info['nodes'], seasons=info['seasons'], population=info['population'],
                      epochs=info['epochs'], regularization=info['regularization'], refTime=dateutil.parser.parse(info['referenceDate']),
                      leads=fGenerateLeads(info['leadTime']), displayEach=25,
                      openClPlatform=settings.OPENCL_PLATFORM, openClDevice=settings.OPENCL_DEVICE,
                      activationFunction=info['activationFunction'], valFraction=info['valFraction'],
                      timeStepUnit=info['timeStepUnit'], timeStepSize=info['timeStepSize'], weigthRange=info['weigthRange'],
                      errorFunction=info['errorFunction'], transformWeights=info['transformWeights'],
                      allowNegative=info['allowNegative'],
                      reduceTraining=info['reduceTraining'], forecastName=info['name'],
                      inertia=info['inertia'], c1=info['c1'], c2=info['c2'], c3=info['c3'],
                      forceNonExceedance=info['forceNonExceedance'], trainingDates=info['trainingDates'],
                      )
         
        man.train()
        man.save(info['filePath'])
        Forecast.objects.filter(name=info['name']).update(ready=True, jobId='')
        return 'DONE'
    except Exception as ex:
        Forecast.objects.filter(name=info['name']).update(ready=False, jobId='')
        raise(ex)

#===============================================================================
# def trainForecastRun(request, forecastName):
#     forecast = Forecast.objects.filter(name=forecastName)
#     if forecast:
#         forecast.update(ready=False)
#         
#         if forecast[0].forecastFile.name != '' and os.path.isfile(forecast[0].forecastFile.path):
#             os.remove(forecast[0].forecastFile.path)
#         forecast[0].forecastFile.save(forecastName + '.gpu', ContentFile('dummy content'))
#         
#         info = {'leadTime': forecast[0].leadTime,
#                 'seasons': forecast[0].splitBySeason,
#                 'nodes': forecast[0].nodes,
#                 'dataFunction': forecast[0].dataExpression,
#                 'targetFunction': forecast[0].targetExpression,
#                 'population': forecast[0].population,
#                 'epochs': forecast[0].epochs,
#                 'regularization': float(forecast[0].regularize),
#                 'filePath': forecast[0].forecastFile.path,
#                 'name': forecast[0].name,
#                 'referenceDate': forecast[0].referenceDate.isoformat(),
#                 'activationFunction': forecast[0].type,
#                 'valFraction': 1-forecast[0].training/100,
#                 'timeStepUnit': forecast[0].targetSeries.TIME_STEP_DICT[forecast[0].targetSeries.timeStepUnits],
#                 'timeStepSize': forecast[0].targetSeries.timeStepPeriod,
#                 'weigthRange': float(forecast[0].weigthRange),
#                 'errorFunction': forecast[0].errorFunction,
#                 'transformWeights': forecast[0].transformWeights,
#                 'allowNegative': forecast[0].allowNegative,
#                 'reduceTraining': float(forecast[0].reduceTraining),
#                 }
# 
#         target, extra = fGetForecastData(forecastName)
#         
#         #=======================================================================
#         # trainWrapper(info, target, extra)
#         # context = {'job': 1}
#         #=======================================================================
#          
#         job = trainWrapper.delay(info, target, extra)
#         context = {'job': job.id}
# 
#         return JsonResponse(context)
#===============================================================================

def trainForecastProgress(request, forecastName):
    try:
        forecast = Forecast.objects.get(name=forecastName)
        jobId = forecast.jobId
        plotCounter = request.POST.get('plotCounter')
        if jobId=='':
            jobId = request.POST.get('jobId')
            if jobId =='':
                jobId = None
            
        if jobId==None:
            context = {'state': 'UNKNOWN'}
        else:      
            job = AsyncResult(jobId)
            if job.state=='PENDING':
                context = {'jobId': jobId,
                           'state': 'PENDING',
                           }
            elif job.state=='SUCCESS' and job.result=='DONE':
                context = {'jobId': jobId,
                           'state': 'DONE',
                           }
            elif job.state=='PROGRESS':
                context = job.result
                if 'plot' in context.keys() and int(plotCounter)==context['plotCounter']:
                    context.pop('plot')
                    context.pop('plotCounter')
                context['jobId'] = jobId
                context['state'] = 'PROGRESS'
            elif job.state=='FAILURE':
                raise Exception
    except Exception as ex:
        print(str(ex))
        context = {'message': ('error', str(ex))}
    
    return JsonResponse(context)

def trainCancel(request, forecastName):
    forecasts = Forecast.objects.filter(name=forecastName)
    forecasts.update(ready=False, jobId='')
    return JsonResponse({'success': 'SUCCESS'})
        
    raise(Exception)

def forecast(request, forecastName):
    errorMsg = ''
    forecast = Forecast.objects.filter(name=forecastName)
    if forecast:
        tmp = dt.datetime.strptime(request.POST.get('reference'), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo = None)
        
        try:
            larger = Value.objects.filter(series=forecast[0].targetSeries.id).filter(date__gte=tmp).earliest('date').date
        except ObjectDoesNotExist:
            larger = Value.objects.filter(series=forecast[0].targetSeries.id).latest('date').date
        
        if larger!=tmp:
            try:
                smaller = Value.objects.filter(series=forecast[0].targetSeries.id).filter(date__lte=tmp).latest('date').date
            except ObjectDoesNotExist:
                smaller = Value.objects.filter(series=forecast[0].targetSeries.id).earliest('date').date
            
            interval = (smaller, larger)
            if np.argmin(np.abs(np.array(interval)-tmp))==0:
                reference = smaller
            else:
                reference = larger
        else:
            reference = larger
    
        fJumpFun = fJumpDateFun(forecast[0].period)      
        target, extra = fGetForecastData(forecastName, fJumpFun(reference,-2), reference)
        
        target = [np.array([np.datetime64(s0) for s0 in target[0]]), target[1]]
        if extra!=None:
            for i0 in range(len(extra)):
                extra[i0] = [np.array([np.datetime64(s0) for s0 in extra[i0][0]]), extra[i0][1]]
        
        man = Manager(target, extra=extra, forecast=True)
        man.load(forecast[0].forecastFile.path, openClPlatform=settings.OPENCL_PLATFORM, openClDevice=settings.OPENCL_DEVICE)
        res = man.forecast(np.datetime64(reference), data=target, extra=extra)
        selectBands = (1,3,5,7,8,10,12,14)
        res['bands'] = res['bands'][selectBands,]
        res['simulations'] = res['simulations'][:,selectBands]
        
        if sys.platform=='linux':
            tmpDates = [str(d0)[0:-5] for d0 in res['dates']]
        else:
            tmpDates = [str(d0) for d0 in res['dates']]
        context = {'bands': res['bands'].tolist(),
                   'dates': tmpDates,
                   'values': np.transpose(res['simulations']).tolist(),
                   'targets': [None if np.isnan(t0) else t0 for t0 in res['targets'].tolist()],
                   'timeStepUnits': dict(Series.TIME_STEP_PERIOD_TYPE)[forecast[0].targetSeries.timeStepUnits],
                   'timeStepPeriod': forecast[0].targetSeries.timeStepPeriod,
                   'error': errorMsg,
                   }
        
        return JsonResponse(context)

def getTrainingPeriods(request, forecastName):
    context = {}
    
    forecasts = Forecast.objects.filter(name=forecastName)
    if forecasts:
        forecast = forecasts[0]
        trainingDates = forecast.trainingDates
        
        data, extra = fGetForecastData(forecastName)
        data = [np.array([np.datetime64(s0) for s0 in data[0]]), data[1]]
        if extra!=None:
            for i0 in range(len(extra)):
                extra[i0] = [np.array([np.datetime64(s0) for s0 in extra[i0][0]]), extra[i0][1]]
        
        man = Manager(data, extra=extra,
                  dataFunction=forecast.dataExpression, targetFunction=forecast.targetExpression, 
                  nodes=forecast.nodes, seasons=forecast.splitBySeason, population=forecast.population,
                  epochs=forecast.epochs, regularization=forecast.regularize, refTime=forecast.referenceDate,
                  leads=fGenerateLeads(forecast.leadTime), displayEach=25,
                  openClPlatform=settings.OPENCL_PLATFORM, openClDevice=settings.OPENCL_DEVICE,
                  activationFunction=forecast.type, valFraction=1-forecast.training/100,
                  timeStepUnit=forecast.targetSeries.TIME_STEP_DICT[forecast.targetSeries.timeStepUnits],
                  timeStepSize=forecast.targetSeries.timeStepPeriod, weigthRange=float(forecast.weigthRange),
                  errorFunction=forecast.errorFunction, transformWeights=forecast.transformWeights,
                  allowNegative=forecast.allowNegative, reduceTraining=forecast.reduceTraining, forecastName=forecast.name,
                  inertia=forecast.psoC0, c1=forecast.psoC1, c2=forecast.psoC2, c3=forecast.psoC2,
                  forceNonExceedance=forecast.forceNonExceedance, trainingDates=trainingDates,
                  )
        
        groups = man.data.splitGroup
        dateGroups = []
        dataGroups =[]
        dataPos = []
        groupNumbers = np.unique(groups)
        validGroups = []
        for g0 in groupNumbers:
            idxs = groups==g0
            values = man.data.values[idxs]
            tmp = np.logical_not(np.isnan(values))
            if np.sum(tmp)>0:
                dataGroups.append(values[tmp])
                dateGroups.append(man.data.dates[idxs][tmp])
                dataPos.append(g0)
                validGroups.append(g0)
        dataPos = np.array(dataPos)
        tmp = [d0[-1]-d0[0] for d0 in dateGroups]
        widths = []
        for w0 in tmp:
            widths.append(w0/max(tmp))
        
        fig = plt.figure(figsize=(12, 3))
        plotAx = fig.add_subplot(1, 1, 1)
        violinParts = plotAx.violinplot(dataGroups, dataPos, points=40, widths=widths, showmeans=False, showextrema=False, showmedians=False)
        
        training = []
        for i0, g0 in enumerate(validGroups):
            if g0 in man.data.splitTra:
                training.append(True)
            else:
                training.append(False)
                
                #===============================================================
                # val[2].append(dateGroups[i0][0].astype(dt.datetime).strftime('%Y.%m.%d %H:%M:%S') + '-' + dateGroups[i0][-1].astype(dt.datetime).strftime('%Y.%m.%d %H:%M:%S'))
                #===============================================================
        
        #=======================================================================
        # pointsVal = plotAx.scatter(val[0], val[1], s=40, alpha=0.8, color='#f5dd5d', label='Validation')
        # pointsTra = plotAx.scatter(tra[0], tra[1], s=80, alpha=0.8, color='#be7429', label='Training')
        #=======================================================================
        
        # TODO: Change so that it works also with sub-daily
        # FIX: Correct the split into periods
        plotAx.get_xaxis().set_ticks([])
        plotAx.set_xlim([dataPos[0]-1,dataPos[-1]+1])
        
        for i0, p0 in enumerate(violinParts['bodies']):
            if training[i0]:
                p0.set_facecolor('#417690')
            else:
                p0.set_facecolor('#f8f8f8')
            p0.set_alpha(1);
    
    styles = {True: {'fill': '#417690'},
             False: {'fill': '#f8f8f8'}}
    for i0, p0 in enumerate(violinParts['bodies']):
        #=======================================================================
        # tmp = dateGroups[i0][0].astype(dt.datetime).strftime('%Y.%m.%d %H:%M:%S') + ' - ' + dateGroups[i0][-1].astype(dt.datetime).strftime('%Y.%m.%d %H:%M:%S')
        #=======================================================================
        marker = dateGroups[i0][0].astype(dt.datetime).strftime('%Y.%m.%d %H:%M:%S')
        mpld3.plugins.connect(fig, ClickInfo(p0, training[i0], styles, marker))
    
    #===========================================================================
    # mpld3.plugins.connect(fig, ClickInfo(pointsVal))
    # mpld3.plugins.connect(fig, ClickInfo(pointsTra))
    # mpld3.plugins.connect(fig, mpld3.plugins.PointLabelTooltip(pointsVal, val[2]))
    # mpld3.plugins.connect(fig, mpld3.plugins.PointLabelTooltip(pointsTra, tra[2]))
    #===========================================================================
    
    plotDict = mpld3.fig_to_dict(fig)
    plt.close(fig)
    return JsonResponse({'plot': plotDict})
    
    #===========================================================================
    # return HttpResponse(mpld3.fig_to_html(fig))
    #===========================================================================

    #===========================================================================
    # return JsonResponse(context)
    #===========================================================================

def hindcast(request, forecastName):
    forecast = Forecast.objects.filter(name=forecastName)
    if forecast:
        if request.POST['lead'][0]=='null':
            lead = forecast[0].leadTime
        else:
            lead = float(request.POST['lead'])
        dateFrom = dt.datetime.strptime(request.POST.get('from'), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo = None)
        dateTo = dt.datetime.strptime(request.POST.get('to'), "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo = None)
            
        fJumpFun = fJumpDateFun(forecast[0].period)
        dateFromExtended = fJumpFun(dateFrom, -2)   
        target, extra = fGetForecastData(forecastName, fromDate=dateFromExtended, toDate=dateTo)
        
        target = [np.array([np.datetime64(s0) for s0 in target[0]]), target[1]]
        if extra!=None:
            for i0 in range(len(extra)):
                extra[i0] = [np.array([np.datetime64(s0) for s0 in extra[i0][0]]), extra[i0][1]]
        
        man = Manager(target, extra=extra, forecast=True)
        man.load(forecast[0].forecastFile.path, openClPlatform=settings.OPENCL_PLATFORM, openClDevice=settings.OPENCL_DEVICE)
        
        try:
            res = man.hindcast(data=target, lead=lead, extra=extra, dateFrom=dateFrom)
            #===================================================================
            # toKeep = res['dates']>=dateFrom
            # res['dates'] = res['dates'][toKeep]
            # res['simulations'] = res['simulations'][toKeep,]
            # res['targets'] = res['targets'][toKeep]
            #===================================================================
            
            jsonQQ = plotQQ(res['traQQ'], res['valQQ'], res['bands'])
            
            selectBands = (1,3,5,7,8,10,12,14)
            res['bands'] = res['bands'][selectBands,]
            res['simulations'] = res['simulations'][:,selectBands]
            
            #===================================================================
            # {'dates': dates, 'simulations': leadSimulations, 'bands': bands, 'targets': leadTargets,
            #      'traDates': traDates, 'traPerformance': traPerformance, 'valPerformance': valPerformance,
            #      'traQQ': traQQ, 'valQQ': valQQ}
            #===================================================================
            
            #===================================================================
            # trainingDates = man.data.dates[man.data.idxTra]
            # trainingDates = trainingDates[np.logical_and(trainingDates>=np.datetime64(dateFrom), trainingDates<=np.datetime64(dateTo))]
            #===================================================================
            
            
            if sys.platform=='linux':
                tmpDates = [str(d0)[0:-5] for d0 in res['dates']]
                tmpTrainingDates = [str(d0)[0:-5] for d0 in res['traDates']]
            else:
                tmpDates = [str(d0) for d0 in res['dates']]
                tmpTrainingDates = [str(d0) for d0 in res['traDates']]
            context = {'bands': res['bands'].tolist(),
                        'dates': tmpDates,
                        'values': np.transpose(res['simulations']).tolist(),
                        'targets': [None if np.isnan(t0) else t0 for t0 in res['targets'].tolist()],
                        'timeStepUnits': dict(Series.TIME_STEP_PERIOD_TYPE)[forecast[0].targetSeries.timeStepUnits],
                        'timeStepPeriod': forecast[0].targetSeries.timeStepPeriod,
                        'trainingDates': tmpTrainingDates,
                        'QQ': jsonQQ,
                        'traPerformance': '<p>Training  : &#945:%f, &#958:%f, &#960:%f</p>' % res['traPerformance'],
                        'valPerformance': '<p>Validation: &#945:%f, &#958:%f, &#960:%f</p>' % res['valPerformance'],
                        }
            return JsonResponse(context)
        except Exception as ex:
            return JsonResponse({'status':'false','message': str(ex)}, status=500)

@task(name='storeSatelliteData')
def storeSatelliteDataWrapper(name):
    try:
        current_task.update_state(state='PROGRESS', meta={'message': ('warning', 'Starting...'),
                                                          'progress': 0,
                                                          'state': 'PROGRESS'})
    except Exception:
        pass
    
    satelliteObj = SatelliteData.objects.get(name=name)
    satellite = satelliteObj.satellite
    dateIni = satelliteObj.startDate
    dateEnd = dt.datetime.now()
    geometryFile = satelliteObj.geometry.path
    dataFolder = satelliteObj.dataFolder    #@UnusedVariable
    downloadFolder = os.path.join(settings.SATELLITE_DOWNLOAD, satellite)   #@UnusedVariable
    jsonGeometry = satelliteObj.jsonGeometry
    username = satelliteObj.username    #@UnusedVariable
    password = satelliteObj.password    #@UnusedVariable
    downloadThreads = satelliteObj.downloadThreads
    readThreads = satelliteObj.readThreads

    satelliteInstance = eval('satelliteData.' + satellite + '(dataFolder=dataFolder, downloadFolder=downloadFolder, username=username, password=password)')
    satelliteObj.lastRecord = satelliteInstance.store(dateIni=dateIni, dateEnd=dateEnd, geometryFile=geometryFile, geometryStr=jsonGeometry, downloadThreads=downloadThreads, readThreads=readThreads)
    
    # Handle geometry
    if not satelliteObj.readyGeometry or satelliteObj.jsonGeometry=='':
        satelliteObj.jsonGeometry = satelliteInstance.getGeometryInfo()
        satelliteObj.readyGeometry = True
    
    user = User.objects.get(username='tethys')
    
    # Introduce associated location
    locations = Location.objects.filter(name='sat_' + name)
    if locations:
        location = locations[0]
    else:
        tmp = json.loads(satelliteObj.jsonGeometry)
        location = Location(name='sat_' + name,
                            lat=np.mean(np.array(tmp['lat'])[tmp['idxReduced'][0]]),
                            lon=np.mean(np.array(tmp['lon'])[tmp['idxReduced'][1]]),
                            observations='Generated automatically from satellite data aggregation.',
                            introducedBy=user,
                            )
        location.save()
        
    satelliteObj.location = location
        
    # Introduce associated series
    serieS = Series.objects.filter(name='sat_' + name)
    if serieS:
        series = serieS[0]
    else:
        timestepDict = {'minutes': 'm',
                        'hours': 'h',
                        'days': 'd',
                        'weeks': 'w',
                        'months': 'M',
                        'years': 'Y'}
        timeStepUnits=timestepDict[list(satelliteInstance.timestep.keys())[0]]
        timeStepPeriod=satelliteInstance.timestep[list(satelliteInstance.timestep.keys())[0]]
        series = Series(name='sat_' + name,
                        location=satelliteObj.location,
                        provider=DataProvider.objects.get(name='tethys'),
                        type=DataType.objects.get(name='Satellite data aggregation'),
                        timeStepUnits=timeStepUnits,
                        timeStepPeriod=timeStepPeriod,
                        encryptionKey=None,
                        observations='Generated automatically from satellite data aggregation.',
                        introducedBy=user,
                        )
        series.save()
    satelliteObj.series = series
        
        
    # Erase and re-introduce associated values
    Value.objects.filter(series=series).delete()
    print('Values deleted')
    aggregateSatelliteData(satelliteObj, satelliteInstance)
    print('Values inserted')
    
    # Update satellite entry
    satelliteObj.jobId = None
    satelliteObj.save()
    
    return 'DONE'

def storeSatelliteDataProgress(request, name):
    try:
        satelliteObj = SatelliteData.objects.get(name=name)
        jobId = satelliteObj.jobId
        if jobId==None:
            jobId = request.POST.get('jobId')
            if jobId =='':
                jobId = None
            
        if jobId==None:
            context = {'state': 'UNKNOWN'}
        else:      
            job = AsyncResult(jobId)
            data = job.result or job.state
            if data=='PENDING':
                context = {'jobId': jobId,
                           'state': 'PENDING',
                           'message': ('warning', 'Please be patient. Waiting on other processes in queue...')}
            elif data=='DONE' or ('state' in data.keys() and data['state']=='DONE'):
                context = {'jobId': jobId,
                           'state': 'DONE',
                           'message': ('success', 'The process is complete.')}
            else:
                context = data
                context['jobId'] = jobId
    except Exception as ex:
        print(str(ex))
        context = {'message': ('error', str(ex))}
    
    return JsonResponse(context)

def storeSatelliteData(request, name):
    # reviews all the history of the satellite product
    
    satelliteObj = SatelliteData.objects.filter(name=name)
    if not satelliteObj:
        context = {'message': ('error', 'The satellite data "' + name + '" has not been found in the database.')}
    else:
        job = storeSatelliteDataWrapper.delay(name)
        satelliteObj[0].jobId = job.id
        satelliteObj[0].save()
        
        #=======================================================================
        # storeSatelliteDataWrapper(name)
        # satelliteObj = SatelliteData.objects.filter(name=name)
        # satelliteObj[0].jobId = None
        #=======================================================================
        
        context = {'jobId': satelliteObj[0].jobId,
                   'message': ('warning', 'Starting data preparation...'),
                   'state': 'PROGRESS'}
        
        # Add celery periodic task
        intervalSchedules = IntervalSchedule.objects.filter(period='hours', every='2')
        if intervalSchedules:
            intervalSchedule = intervalSchedules[0]
        else:
            intervalSchedule = IntervalSchedule(period='hours', every='2')
            intervalSchedule.save()
        
        periodicTasks = PeriodicTask.objects.filter(name=name + ' Update')
        if not periodicTasks:
            periodicTask = PeriodicTask(name=name + ' Update', task='updateSatelliteData', interval=intervalSchedule, args='["' + name + '"]')
            periodicTask.save()
            
    return JsonResponse(context)

@task(name='updateSatelliteData')
def updateSatelliteDataWrapper(name):
    try:
        current_task.update_state(state='PROGRESS', meta={'message': ('warning', 'Starting...'),
                                                          'progress': 0,
                                                          'state': 'PROGRESS'})
    except Exception:
        pass

    satelliteObj = SatelliteData.objects.get(name=name)
    satellite = satelliteObj.satellite
    geometryFile = satelliteObj.geometry.path
    dataFolder = satelliteObj.dataFolder    #@UnusedVariable
    downloadFolder = os.path.join(settings.SATELLITE_DOWNLOAD, satellite)   #@UnusedVariable
    jsonGeometry = satelliteObj.jsonGeometry
    username = satelliteObj.username    #@UnusedVariable
    password = satelliteObj.password    #@UnusedVariable
    downloadThreads = satelliteObj.downloadThreads
    readThreads = satelliteObj.readThreads

    satelliteInstance = eval('satelliteData.' + satellite + '(dataFolder=dataFolder, downloadFolder=downloadFolder, username=username, password=password)')
    satelliteObj.lastRecord = satelliteInstance.update(geometryFile=geometryFile, geometryStr=jsonGeometry, downloadThreads=downloadThreads, readThreads=readThreads)
        
    # Introduce new values
    aggregateSatelliteData(satelliteObj, satelliteInstance)
    
    # Update satellite entry
    satelliteObj.jobId = None
    satelliteObj.save()
    
    return 'DONE'

def updateSatelliteData(request, name):
    # only looks for recent data
    
    satelliteObj = SatelliteData.objects.filter(name=name)
    if len(satelliteObj)==0:
        context = {'message': ('error', 'The satellite data "' + name + '" has not been found in the database.')}
    else:
        job = storeSatelliteDataWrapper.delay(name)
        satelliteObj[0].jobId = job.id
        satelliteObj[0].save()
        
        #=======================================================================
        # storeSatelliteDataWrapper(name)
        # satelliteObj = SatelliteData.objects.filter(name=name)
        # satelliteObj[0].jobId = None
        #=======================================================================
        
        satelliteObj[0].save()
        context = {'jobId': satelliteObj[0].jobId,
                   'message': ('warning', 'Starting data update...'),
                   'state': 'PROGRESS'}

    return JsonResponse(context)
    
def getSatelliteData(request):
    # Get satellite data for display from the database
    
    data = json.loads(request.POST.get('data'))
    
    name = data['name']
    info = data['info']
    datetimes = data['datetimes']
    
    satelliteObj = SatelliteData.objects.get(name=name)
    
    satellite = satelliteObj.satellite
    dataFolder = satelliteObj.dataFolder    #@UnusedVariable
    downloadFolder = os.path.join(settings.SATELLITE_DOWNLOAD, satellite)   #@UnusedVariable
    
    satelliteInstance = eval('satelliteData.' + satellite + '(dataFolder=dataFolder, downloadFolder=downloadFolder)')
    if info:
        data = satelliteInstance.getDataForJSON(dateIni=dateutil.parser.parse(datetimes[0]), dateEnd=dateutil.parser.parse(datetimes[-1]))
    else:
        data = satelliteInstance.getDataForJSON(dateIni=dateutil.parser.parse(datetimes[0]), dateEnd=dateutil.parser.parse(datetimes[-1]), returnInfo=False)
    data['name'] = name

    data['dates'] = [s0 + '.000Z' for s0 in data['dates']]
    
    for i0 in range(len(data['dates'])-1,-1,-1):
        if data['dates'][i0] not in datetimes:
            data['data'].pop(i0)
            data['dates'].pop(i0)
    
    return HttpResponse(
                        json.dumps(json.dumps(data)),
                        content_type="application/json"
                        )
    
def aggregateSatelliteData(satelliteObj, satelliteInstance):
    
    series = Series.objects.get(name='sat_' + satelliteObj.name)
    
    # Get the list of already aggregated records
    storedDates = [v0.date for v0 in Value.objects.filter(series=series).order_by('date')]
        
    # Get the list of all possible records
    possibleDates = satelliteInstance.filePeriod(dateIni=satelliteObj.startDate, dateEnd=satelliteObj.lastRecord)
    
    # Create missing list
    tmp0 = np.array(satelliteInstance.ismember(storedDates, possibleDates))
    tmp1 = np.ones(len(possibleDates), dtype=np.bool)
    if tmp0.size>0:
        tmp1[tmp0] = False
    tmp0 = np.array(possibleDates)
    missingDates = tmp0[tmp1].tolist()
    
    # retrieve values
    records = satelliteInstance.aggregate(missingDates, geometryStr=satelliteObj.jsonGeometry)
    
    # store values
    toInput = []
    tmpPeriods = len(records);
    for i0, d0 in enumerate(records):
        if not np.isnan(d0):
            toInput.append(Value(series=series, date=missingDates[i0], recordOpen=d0))
        if i0 % 1000==0 and i0!=0:
            try:
                current_task.update_state(state='PROGRESS', meta={'message': ('warning', 'Saving to the database'),
                                                                          'progress': i0/tmpPeriods,
                                                                          'state': 'PROGRESS'})
            except Exception:
                pass
            Value.objects.bulk_create(toInput)
            toInput = []
    Value.objects.bulk_create(toInput)
    
    
    
    
    
    
    
    
def batchLocations(request):
    context = {'LANG': request.LANGUAGE_CODE,
               'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,}
    return render(request, 'timeSeries/batchLocations.html', context)

def batchLocationsRegister(request):
    currentUser = request.user
    locations = json.loads(request.POST.get('elements'))
    tmpCountries = {v: k for k, v in dict(countries).items()}
    
    errors = []
    warnings = []
    success = []
    for i0, l0 in enumerate(locations):
        data = {}
        try:
            data['introducedBy'] = User.objects.get(id=currentUser.id)
            data['name'] = l0['Name']
            data['lat'] = float(l0['Latitude'])
            data['lon'] = float(l0['Longitude'])
            if l0['Catchment']!=None:
                data['catchment'] = l0['Catchment']
            if l0['River']!=None:
                data['river'] = l0['River']
            if l0['Country']!=None:
                data['country'] = tmpCountries[l0['Country']]
            if l0['Observations']!=None:
                data['observations'] = l0['Observations']
            newLocation = Location(**data)
            newLocation.save()
            
            success.append((i0, "Success"))
        except Exception as ex:
            if ex.args[0]==1062:
                # duplicate entry
                warnings.append((i0, ex.args[1]))
            else:
                errors.append((i0, str(ex)))
    context = {'warnings': warnings,
               'errors': errors,
               'success': success,
               }
    return HttpResponse(
                        json.dumps(context),
                        content_type="application/json"
                        )

def batchDownloadExample(request):
    file = open(os.path.join(os.path.dirname(__file__), 'static', 'timeSeries', 'examples', 'locations.xlsx'), 'rb')
    response = HttpResponse(content=file)
    response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response['Content-Disposition'] = 'attachment; filename="AddFromExcelLocationsExample.xlsx"'
    return response