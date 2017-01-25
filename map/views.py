import os.path
from django.shortcuts import render
from timeSeries.models import DataType, Series, SatelliteData
from django_countries import countries
from django.conf import settings
import json
import pytz
import timeSeries.satelliteData as satelliteData

from django.contrib.auth.decorators import login_required

@login_required
def mainMap(request):
    context = {}
    
    #search available geojsons (only allows for names without special characters)
    geoJSONDict = {};
    for f0 in os.listdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/map/shapes/')):
        geoJSONDict[f0] = [];
        for f1 in os.listdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/map/shapes/' + f0)):
            if f1.endswith('.geojson'):
                geoJSONDict[f0].append(os.path.splitext(f1)[0]);

    #query available series
    seriesDict = {}
    dataTypes = DataType.objects.all()
    for d0 in dataTypes:
        series = Series.objects.filter(type=d0)
        if len(series)>0:
            if str(d0) not in seriesDict.keys():
                seriesDict[str(d0)] = []
            for s0 in series:
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
                       'quality': s0.quality,
                       'timeStepUnits': dict(Series.TIME_STEP_PERIOD_CHOICES)[s0.timeStepUnits],
                       'timeStepPeriod': s0.timeStepPeriod,
                       'metaEncrypted': s0.metaEncrypted,
                       'river': s0.location.river,
                       'country': tmpCountry,
                       'catchment': s0.location.catchment,
                       }
                seriesDict[str(d0)].append(tmp)
    
    #query available raster datasets
    rasterDict = {}
    rasters = SatelliteData.objects.all()
    for r0 in rasters:
        raster = r0.satellite
        dataFolder = r0.dataFolder
        downloadFolder = os.path.join(settings.SATELLITE_DOWNLOAD, raster)
        rasterObj = eval('satelliteData.' + raster + '(dataFolder=dataFolder, downloadFolder=downloadFolder)')
        tmp = []
        for d0 in rasterObj.netCDFDict.keys():
            for d1 in rasterObj.netCDFDict[d0].keys():
                tmp.append((d0, d1))
        tmp.sort(key=lambda x: '%04u-%02u' % x)
        if len(tmp)>0 and r0.lastRecord!=None:
            rasterDict[r0.name]={}
            rasterDict[r0.name]['dates'] = tmp
            rasterDict[r0.name]['raster'] = raster
            rasterDict[r0.name]['description'] = rasterObj.description
            rasterDict[r0.name]['productSite'] = rasterObj.productSite
            rasterDict[r0.name]['name'] = r0.name
            rasterDict[r0.name]['timestep'] = r0.timestep
            rasterDict[r0.name]['units'] = r0.units
            rasterDict[r0.name]['colormap'] = str(r0.colormap.file)
            rasterDict[r0.name]['reference'] = r0.startDate.isoformat() + 'Z'
            rasterDict[r0.name]['lastRecord'] = r0.lastRecord.isoformat() + 'Z'
          
    context['geoJSONs'] = geoJSONDict
    context['series'] = json.dumps(seriesDict)
    context['rasters'] = json.dumps(rasterDict)
    context.update({'LOCAL_JAVASCIPT': settings.LOCAL_JAVASCIPT,
                    'LOCAL_MAP': settings.LOCAL_MAP,})
    return render(request, 'map/mainMap.html', context)
