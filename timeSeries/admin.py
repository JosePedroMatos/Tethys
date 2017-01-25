from django.contrib import admin
from .models import DataType, DataProvider, Location, Series, Value, Forecast, SatelliteData, Colormap
from django.utils.html import format_html, mark_safe
from .satelliteData import TRMMSatelliteRainfall, TRMMSatelliteRainfallRT
from django.conf import settings

import warnings
import datetime as dt

import os

class AdminAutoRecord(admin.ModelAdmin):
    def save_model(self, request, obj, form, change): 
        obj.introducedBy = request.user
        obj.save()
 
    def save_formset(self, request, form, formset, change): 
        if formset.model == DataType:
            instances = formset.save(commit=False)
            for instance in instances:
                instance.introducedBy = request.user
                instance.save()
        else:
            formset.save()

class DataTypeAdmin(AdminAutoRecord):
    readonly_fields = ('iconImage',)
    
    fieldsets = [
        ('Base information', {'fields': (('name', 'abbreviation', 'units', ), 'description'), 'description': 'Base information that characterizes the type of data.'}),
        ('Display information', {'fields': (('iconImage', 'icon', ),), 'description': 'Figure file that will represent the series in the map. Should be a .png with 60x60px size.'}),
        ('Extra information', {'fields': ('observations', ), 'description': 'Additional informations about the data type.', 'classes': ('collapse', )})
    ]
    
    list_display = ('iconImageSmall', 'name', 'description', 'units')
    search_fields = ['name', 'description', 'observations']
    list_filter = ('units', 'created')
  
class DataProviderAdmin(AdminAutoRecord):
    readonly_fields = ('iconImage',)
    
    fieldsets = [
        ('Base information', {'fields': (('name', 'abbreviation', 'country'), ('email', 'website'), 'description'), 'description': 'Base information that characterizes the data provider.'}),
        ('Display information', {'fields': (('iconImage', 'icon', ),), 'description': 'Logo of the data provider. Should be a .png file.'}),
    ]
    
    list_display = ('iconImage', 'name', 'description', 'website')
    search_fields = ['name', 'description']
    list_filter = ('created', )

class LocationAdmin(AdminAutoRecord):
    fieldsets = [
        ('Base information', {'fields': (('name', 'lat', 'lon', ),), 'description': 'Base information that characterizes the location.'}),
        ('Additional information', {'fields': (('catchment', 'river', 'country',),), 'description': 'Additional information that should be used to characterize the location.'}),
        ('Extra information', {'fields': ('observations', ), 'description': 'Additional informations about the location.', 'classes': ('collapse', )})
    ]
    
    list_display = ('name', 'lat', 'lon', 'country', 'catchment', 'river')
    search_fields = ('name', 'country', 'catchment', 'river', 'lat', 'lon', 'observations')
    list_filter = ('catchment', 'river', 'created', 'country')

class SeriesAdmin(AdminAutoRecord):
    readonly_fields = ['country', 'catchment', 'river', 'encryptionKey']
    def get_readonly_fields(self, request, obj=None):
        # encryptions and metaEncryptions can only be changed if the model is being created or there are no values associated with it.
        if obj:
            if len(Value.objects.filter(series_id=obj.id)[:1])==1:
                return self.readonly_fields + ['metaEncrypted',]
        return self.readonly_fields
    
    fieldsets = [
        ('Base information', {'fields': (('name', 'location', 'provider',),('type', 'timeStepUnits', 'timeStepPeriod'),), 'description': 'Base information that characterizes the data series.'}),
        ('Data and encryption', {'fields': (('encryptionKey', 'metaEncrypted'),), 'description': 'Data upload functionality and information about the encryption of the data. Can only be edited in "empty" series.'}),
        ('Additional information', {'fields': (('catchment', 'river', 'country',),), 'description': 'Additional information that should be used to characterize the series.'}),
        ('Extra information', {'fields': ('observations', ), 'description': 'Additional informations about the series.', 'classes': ('collapse', )})
    ]
    
    list_display = ('name', 'location', 'tYpe', 'timeStep', 'records', 'first', 'last', 'metaEncrypted', 'pRovider')
    search_fields = ('name', 'location__name', 'provider__name')
    list_filter = ('provider', 'type', 'timeStepUnits', 'metaEncrypted', 'location__catchment', 'location__river', 'location__country')
    
    def pRovider(self, instance):
        return format_html('<img height="30" src="/{}"/> ({})', mark_safe(instance.provider.icon), mark_safe(instance.provider.abbreviation))
    
    def tYpe(self, instance):
        return format_html('<img height="30" width="30" src="/{}"/> ({})', mark_safe(instance.type.icon), mark_safe(instance.type.name))
    
    def timeStep(self, instance):
        return str(instance.timeStepPeriod) + ' ' + instance.timeStepUnits
    
    def country(self, instance):
        return instance.location.country.name
    
    def catchment(self, instance):
        return instance.location.catchment
    
    def river(self, instance):
        return instance.location.river
    
    def records(self, instance):
        return Value.objects.filter(series=instance).count()

    def first(self, instance):
        tmp = Value.objects.filter(series=instance).order_by('date').first()
        if tmp:
            return tmp.date
        else:
            return ''
    
    def last(self, instance):
        tmp = Value.objects.filter(series=instance).order_by('date').last()
        if tmp:
            return tmp.date
        else:
            return ''

class ForecastAdmin(AdminAutoRecord):
    readonly_fields = ('ready', 'location', 'variable', 'timeStep')
    filter_horizontal = ('extraSeries',)
    
    fieldsets = [
        ('Base information', {'fields': (('name',),
                                         ('targetSeries', 'variable', 'timeStep', 'location', 'ready',),),
                              'description': 'Base information characterizing the forecast and its target series.'}),
        ('Series to include', {'fields': (('targetExpression',),
                                          ('dataExpression',),
                                          ('extraSeries',),),
                               'description': 'Choice of the target series and the additonal series that should be used as covariates.'}),
        ('Main parameters', {'fields': (('leadTime', 'splitBySeason',),
                                        ('period', 'referenceDate',)),
                             'description': 'Main parameters to define the forecast.'}),
        ('Training parameters', {'fields': (
                                         ('type', 'nodes',),
                                         ('population','epochs',),
                                         ('errorFunction',  'regularize', 'allowNegative',),
                                         ('weigthRange', 'transformWeights',),
                                         ('training', 'trainingDates'),
                                         ),
                                 'description': 'Parameters defining the GPU algorithm behavior.',
                                 'classes': ('collapse', )}),
        ('Optimization parameters', {'fields': (
                                         ('psoC0', 'psoC1',),
                                         ('psoC2', 'psoC3',),
                                         ('forceNonExceedance',),
                                         ),
                                     'description': 'Particle Swarm Optimization multi-objective algorithm parameters.',
                                     'classes': ('collapse', )}),
    ]

    list_display = ('name', 'targetSeries', 'variable', 'type', 'leadTime', 'ready', 'location')
    search_fields = ('name', 'description', 'introducedBy', 'series', 'location')

    list_filter = ('ready',)

    def location(self, instance):
        return str(instance.targetSeries.location)

    def variable(self, instance):
        return str(instance.targetSeries.type)
    
    def timeStep(self, instance):
        return dict(Series.TIME_STEP_PERIOD_CHOICES)[instance.targetSeries.timeStepUnits] + ' (' + str(instance.targetSeries.timeStepPeriod) + ')'
           
    variable.short_description = 'prediction'
    
    def save_model(self, request, obj, form, change):
        if change:
                obj.ready = False
                try:
                    obj.forecastFile.storage.delete(obj.forecastFile.path)
                except PermissionError as ex:
                    warnings.warn(str(ex))
                except ValueError as ex:
                    pass
        super(ForecastAdmin, self).save_model(request, obj, form, change)
    
class ColormapAdmin(AdminAutoRecord):        
    fieldsets = [
        ('Base information', {'fields': (('name',),
                                         ('file',)
                                         ),
                              'description': 'Base information characterizing the colormap.'}),
    ]

    list_display = ('name',)
    search_fields = ('name', 'introducedBy')
    
class SatelliteDataAdmin(AdminAutoRecord):
    readonly_fields = ('units', 'timestep', 'productSite', 'downloadSite', 'description', 'readyGeometry', 'lastRecord', 'location', 'series')
        
    fieldsets = [
        ('Base information', {'fields': (('name', 'satellite', 'startDate', 'lastRecord'),
                                         ('geometry', 'readyGeometry', 'location'),
                                         ('series', 'colormap'),
                                         ),
                              'description': 'Base information characterizing the Satellite data.'}),
        ('Additional information', {'fields': (('units', 'timestep'),
                                               ('productSite'),
                                               ('downloadSite'),
                                               ('username', 'password'),
                                               ('downloadThreads', 'readThreads'),
                                               ('description'),
                                               ),
                                    'description': 'Additional information characterizing the Satellite product.'}),
        ('Extra parameters', {'fields': (('observations',),
                                         ), 
                              'description': 'Additional information.', 'classes': ('collapse', )})
    ]

    list_display = ('name', 'satellite', 'timestep', 'units', 'lastRecord', 'startDate')
    search_fields = ('name', 'satellite', 'description', 'introducedBy', 'lastRecord')
    list_filter = ('lastRecord', 'satellite', 'units')

    #-------------------------------------------------- list_filter = ('ready',)

    def timestepStr(self, instance):
        return str(instance.timestep)
        
    def save_model(self, request, obj, form, change):
        
        downloadFolder = os.path.join(settings.SATELLITE_DOWNLOAD, obj.satellite)
        satelliteObj = eval(obj.satellite + '(dataFolder=obj.dataFolder, downloadFolder=downloadFolder)')
        
        # properties from the satellite data class
        obj.productSite = satelliteObj.productSite
        obj.downloadSite = satelliteObj.downloadSite
        obj.description = satelliteObj.description
        obj.timestep = str(satelliteObj.timestep[list(satelliteObj.timestep.keys())[0]]) + ' (' + list(satelliteObj.timestep.keys())[0] + ')'
        obj.units = satelliteObj.units
        
        # introduced by
        obj.introducedBy = request.user
        
        # change dataFolder
        tmp = os.path.split(obj.dataFolder)
        if tmp[-1]=='__unknown__':
            obj.dataFolder = os.path.join(tmp[0], obj.satellite, obj.name)
            ctr = 1
            while len(SatelliteData.objects.filter(dataFolder=obj.dataFolder))>0:
                obj.dataFolder = obj.dataFolder + ' %02d' % (ctr,)
                ctr += 1
            
        # change start time
        #=======================================================================
        # obj.startDate = obj.startDate.replace(tzinfo=None)
        #=======================================================================
        
        obj.save()
            
admin.site.register(DataType, DataTypeAdmin)
admin.site.register(DataProvider, DataProviderAdmin)
admin.site.register(Location, LocationAdmin)
admin.site.register(Series, SeriesAdmin)
admin.site.register(Forecast, ForecastAdmin)
admin.site.register(Colormap, ColormapAdmin)
admin.site.register(SatelliteData, SatelliteDataAdmin)