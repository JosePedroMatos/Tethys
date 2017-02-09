from django.conf.urls import url
from timeSeries import views

app_name = 'timeSeries'

urlpatterns = [
    url(r'^select/series/(?P<seriesList>.+)/$', views.viewSeries, name='selectTimeSeries'),
    url(r'^deleteValues/series/(?P<seriesName>.+)$', views.deleteTimeSeries, name='deleteTimeSeries'),
    url(r'^upload/series/(?P<seriesName>.+)/uploadTimeSeries/$', views.uploadTimeSeries, name='uploadTimeSeries'),
    url(r'^upload/series/(?P<seriesName>.+)/$', views.upload, name='upload'),
    url(r'^trainForecast/(?P<forecastName>.+)/forecast/$', views.forecast, name='forecast'),
    url(r'^trainForecast/(?P<forecastName>.+)/forecast/getTrainingPeriods/$', views.getTrainingPeriods, name='forecastTrainingPeriods'),
    url(r'^trainForecast/(?P<forecastName>.+)/hindcast/$', views.hindcast, name='hindcast'),
    url(r'^trainForecast/(?P<forecastName>.+)/train/$', views.trainForecastBase, name='train'),
    url(r'^trainForecast/(?P<forecastName>.+)/train/progress/$', views.trainForecastProgress, name='progress'),
    url(r'^trainForecast/(?P<forecastName>.+)/train/cancel/$', views.trainCancel, name='progress'),
    url(r'^satelliteStore/(?P<name>.+)/progress/$', views.storeSatelliteDataProgress, name='updateSatelliteProgress'),
    url(r'^satelliteStore/(?P<name>.+)/$', views.storeSatelliteData, name='storeSatelliteData'),
    url(r'^satelliteUpdate/(?P<name>.+)/$', views.updateSatelliteData, name='updateSatellite'),
    url(r'^satelliteGet/$', views.getSatelliteData, name='getSatellite'),
    url(r'^getValues/$', views.getValues, name='getValues'),
    
    url(r'^admin/location/addBatch/$', views.batchLocations, name='batchLocations'),
    url(r'^admin/location/addBatch/registerBatch/$', views.batchLocationsRegister, name='batchLocationsRegister'),
    url(r'^admin/location/example/$', views.batchLocationsDownloadExample, name='batchLocationsDownloadExample'),
    
    url(r'^admin/series/addBatch/$', views.batchSeries, name='batchSeries'),
    url(r'^admin/series/addBatch/registerBatch/$', views.batchSeriesRegister, name='batchSeriesRegister'),
    url(r'^admin/series/example/$', views.batchSeriesDownloadExample, name='batchSeriesDownloadExample'),
    
    url(r'^admin/values/addBatch/$', views.batchValues, name='batchValues'),
    url(r'^admin/values/addBatch/registerBatch/$', views.batchValuesRegister, name='batchValuesRegister'),
    url(r'^admin/values/example/$', views.batchValuesDownloadExample, name='batchValuesDownloadExample'),
    url(r'^admin/values/addBatch/info/$', views.batchValuesInfo, name='batchValuesInfo'),
]

