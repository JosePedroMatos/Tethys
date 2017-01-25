import os
import datetime
import shutil

from django.db import models
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.utils.html import format_html, mark_safe
from django_countries.fields import CountryField
from django.utils.crypto import get_random_string
from django.core.validators import MinValueValidator, MaxValueValidator, MaxLengthValidator
from decimal import Decimal
from django.core.exceptions import ValidationError    
from django.conf import settings
from django.db.models.signals import pre_delete
from django.dispatch.dispatcher import receiver
from djcelery.models import PeriodicTask

# Functions
def seriesChanged(sender, **kwargs):
    if kwargs['instance'].series.count() > 5:
        raise ValidationError("You cannot choose more than 5 series.", code='invalid')

def targetChanged(sender, **kwargs):
    pass

def get_default_encryptionKey():
    # default encryptionKey
    return get_random_string()

# Views

class DataType(models.Model):
    # Table for storing time series' types of data
    
    abbreviation = models.CharField(max_length=16, null=False, blank=False)
    name = models.CharField(max_length=256, null=False, blank=False)
    units = models.CharField(max_length=64, null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    observations = models.TextField(null=True, blank=True)
    
    staticDir = os.path.dirname(os.path.abspath(__file__))
    fs = FileSystemStorage(location=staticDir)
    icon = models.FileField(upload_to='static/timeSeries/seriesIcons/', storage=fs, null=False, blank=False, default='static/timeSeries/seriesIcons/charts.png')
    
    introducedBy = models.ForeignKey(User, null=False, blank=False, on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    
    def iconImage(self):
        return format_html('<img src="/{}"/>', mark_safe(self.icon)) 
    
    def iconImageSmall(self):
        return format_html('<img height="30" width="30" src="/{}"/>', mark_safe(self.icon)) 
    
    def __str__(self):
        return self.name + ' (' + self.units + ')'

class DataProvider(models.Model):
    # Table for storing data providers
    
    abbreviation = models.CharField(max_length=16, null=False, blank=False)
    name = models.CharField(max_length=255, null=False, blank=False, unique=True)
    description = models.TextField(null=True, blank=True)
    email = models.EmailField(null=False, blank=False)
    website = models.URLField(null=True, blank=True)
    country = CountryField(blank_label='(select country)', blank=False, null=True)
    
    staticDir = os.path.dirname(os.path.abspath(__file__))
    fs = FileSystemStorage(location=staticDir)
    icon = models.FileField(upload_to='static/timeSeries/providerIcons/', storage=fs, null=False, blank=False, default='static/timeSeries/providerIcons/noInfoIcon.png')

    introducedBy = models.ForeignKey(User, null=False, blank=False, on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)

    def iconImage(self):
        return format_html('<img height="30" src="/{}"/>', mark_safe(self.icon)) 
    
    def __str__(self):
        return self.abbreviation

class Location(models.Model):
    # Table for storing measurement locations
    
    name = models.CharField(max_length=256, null=False, blank=False)
    lat = models.DecimalField(decimal_places=10, max_digits=15, null=False, blank=False)
    lon = models.DecimalField(decimal_places=10, max_digits=15, null=False, blank=False)
    catchment = models.CharField(max_length=256, null=False, blank=True)
    river = models.CharField(max_length=256, null=False, blank=True)
    country = CountryField(blank_label='(select country)', null=False, blank=True)
    observations = models.TextField(null=True, blank=True)
    
    introducedBy = models.ForeignKey(User, null=False, blank=False, on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return '%s (lat: %.3f, lon: %.3f)' % (self.name, self.lat, self.lon)

class Series(models.Model):
    # Table for storing data series
    
    MINUTE = 'm'
    HOUR = 'h'
    DAY = 'd'
    WEEK = 'w'
    MONTH = 'M'
    YEAR = 'Y'
    TIME_STEP_PERIOD_CHOICES = (
        (MINUTE, 'minutes'),
        (HOUR, 'hours'),
        (DAY, 'days'),
        (WEEK, 'weeks'),
        (MONTH, 'months'),
        (YEAR, 'years'),
    )
    TIME_STEP_PERIOD_TYPE = (
        (MINUTE, 'minute'),
        (HOUR, 'hourly'),
        (DAY, 'daily'),
        (WEEK, 'weekly'),
        (MONTH, 'monthly'),
        (YEAR, 'yearly'),
    )
    TIME_STEP_DICT = dict(TIME_STEP_PERIOD_CHOICES)
    
    name = models.CharField(max_length=255, null=False, blank=False, unique=True)
    location = models.ForeignKey(Location, null=False, blank=False, on_delete=models.PROTECT)
    provider = models.ForeignKey(DataProvider, null=False, blank=False, on_delete=models.PROTECT)
    type = models.ForeignKey(DataType, null=False, blank=False, on_delete=models.PROTECT)
    timeStepUnits = models.CharField(max_length=2, choices=TIME_STEP_PERIOD_CHOICES, default=DAY, null=False, blank=False)
    timeStepPeriod = models.IntegerField(default=1, null=False, blank=False)
    # TODO: Add the quality icon
    quality = models.SmallIntegerField(default=0, null=False, blank=False)
    importCodes = models.CharField(max_length=512, default=None, null=True, blank=False)
    
    metaEncrypted = models.BooleanField(default=False ,null=False, blank=False)
    metaEncryptionKey = models.CharField(max_length=255, default='', null=False, blank=True)
    
    encryptionKey = models.CharField(max_length=255, default=get_default_encryptionKey, null=True, blank=True)
    
    observations = models.TextField(null=True, blank=True)
    
    introducedBy = models.ForeignKey(User, null=False, blank=False, on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Series"

#===============================================================================
# @receiver(pre_delete, sender=Series)
# def series_delete(sender, instance, **kwargs):
#     Value.objects.filter(series=instance).delete()
#===============================================================================

class Value(models.Model):
    # table for storing Values
    
    series = models.ForeignKey(Series, null=False, blank=False)
    date = models.DateTimeField(null=False, blank=False)
    record = models.BinaryField(null=True, blank=False)
    iv = models.CharField(max_length=16, null=True, blank=False)
    recordOpen = models.DecimalField(null=True, blank=False, decimal_places=5, max_digits=15)
    
class Forecast(models.Model):
    # table for storing forecasting objects and associate variables
    LINEAR = 'lin'
    TANSIG = 'tan'
    LOGSIG = 'log'
    TYPE_CHOICES = (
        (LINEAR, 'Linear'),
        (TANSIG, 'Tansig'),
        (LOGSIG, 'Logsig'),
    )
    MSE = 'MSE'
    MAE = 'MAE'
    ERROR_CHOICES = (
        (MSE, 'Mean squared error'),
        (MAE, 'Mean absolute error'),
    )
    SECOND = 'seconds'
    MINUTE = 'minutes'
    HOUR = 'hours'
    DAY = 'days'
    WEEK = 'weeks'
    MONTH = 'months'
    YEAR = 'years'
    PERIOD_CHOICES = (
        (SECOND, 'seconds'),
        (MINUTE, 'minutes'),
        (HOUR, 'hours'),
        (DAY, 'days'),
        (WEEK, 'weeks'),
        (MONTH, 'months'),
        (YEAR, 'years'),
    )
    PERIOD_CHOICES_DICT = dict(PERIOD_CHOICES)
    
    name = models.CharField(max_length=255, null=False, blank=False, unique=True)
    description = models.TextField(null=False, blank=False)
    extraSeries = models.ManyToManyField(Series, verbose_name='extra series', blank=True, related_name='+')
    targetSeries = models.ForeignKey(Series, verbose_name='target series', null=False, blank=False, related_name='forecast_targetSeries')
    staticDir = os.path.dirname(os.path.abspath(__file__))
    fs = FileSystemStorage(location=staticDir)
    forecastFile = models.FileField(upload_to='forecasts/', storage=fs, null=False, blank=False)
    period = models.CharField('period of the series', default = YEAR, max_length=6, choices=PERIOD_CHOICES, null=False, blank=False, help_text='The duration of a cycle (e.g. the hydrological year).')
    referenceDate = models.DateTimeField('reference date for the period', default=datetime.datetime(datetime.date.today().year, 10, 1, 0, 0, 0), null=False, help_text='The beginning of the hydrological year.')
    leadTime = models.PositiveIntegerField('lead time', default = 30, null=False, blank=False, help_text='How far into the future to extend the forecasts.')
    type = models.CharField('type of model', max_length=3, choices=TYPE_CHOICES, default=TANSIG, null=False, blank=False)
    regularize = models.DecimalField('regularize the model', validators=[MinValueValidator(Decimal('0'))], default=0.001, null=False, decimal_places=9, max_digits=11, help_text='Regularization constant to apply. Larger values will produce smoother forecasts.')
    splitBySeason = models.SmallIntegerField('number of seasons', default=3, validators=[MinValueValidator(Decimal('1')), MaxValueValidator(Decimal('6'))], null=False, help_text='Use different models for different seasons.')
    errorFunction = models.CharField('error function', max_length=3, choices=ERROR_CHOICES, default=MSE, null=False, blank=False, help_text='Choose the error function that evaluates how forecasts differ from observations.')
    allowNegative = models.BooleanField('allow negative values', default=False, null=False)
    ready = models.BooleanField('ready to forecast', default=False, null=False)
    nodes = models.SmallIntegerField('Number of nodes', default=4, validators=[MaxValueValidator(Decimal('40'))], null=False, help_text='Set the complexity of the model by choosing the number of hidden nodes in the artificial neural network. Better to keep it simple.')
    dataExpression = models.CharField('input expression', max_length=256, default='cycle, targets, filter(targets)', null=False, blank=False, help_text='The function that transforms inputs to the model.')
    targetExpression = models.CharField('output expression', max_length=256, default='known(targets)', null=False, blank=False, help_text='The function that transforms targets from the original series.')
    population = models.SmallIntegerField('number of models', default=1000, validators=[MinValueValidator(Decimal('20')), MaxValueValidator(Decimal('8000'))], null=False, help_text='The number of models being simultaneously trained.')
    epochs = models.SmallIntegerField('epochs', default=400, validators=[MinValueValidator(Decimal('10')), MaxValueValidator(Decimal('1500'))], null=False, help_text='For how many iterations the models are trained.')
    jobId = models.CharField(max_length=254, null=False, blank=True)
    training = models.SmallIntegerField('Training period percentage', default=50, validators=[MaxValueValidator(Decimal('100')), MinValueValidator(Decimal('0'))], blank=False, null=False, help_text='Percentage of the available periods to be used for training.')
    #===========================================================================
    # trainingDates = models.CharField('Reference dates for training', default='', blank=True, null=False, max_length=2048)
    #===========================================================================
    trainingDates = models.TextField('Reference dates for training', default='', blank=True, null=False)
    weigthRange = models.DecimalField('ANN weight range', validators=[MinValueValidator(Decimal('1')),], default=8, null=False, decimal_places=2, max_digits=11, help_text='Maximum absolute value for the ANN connection weights. Small values may not be adequate to reproduce complex functions. Large values render the optimization difficult.')
    transformWeights = models.BooleanField('Transform solution space', default=True, null=False, help_text='Transform the space in which artifical neural networks'' weights are optimized. May help if model responses are too simple.')
    reduceTraining = models.DecimalField('Training speedup', validators=[MinValueValidator(Decimal('1')), MaxValueValidator(Decimal('100'))], default=1, null=False, decimal_places=2, max_digits=6, help_text='Speedup obtained by clustering an average of n similar training examples together. Accuracy degrades for increasing n.')
    
    psoC0 = models.DecimalField('Inertia', validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('5'))], default=0.5, null=False, decimal_places=6, max_digits=8, help_text='Inertia affecting the change rate and direction of each solution.')
    psoC1 = models.DecimalField('Global attraction', validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('5'))], default=0.0, null=False, decimal_places=6, max_digits=8, help_text='Attraction of solutions to best local candidates.')
    psoC2 = models.DecimalField('Local attraction', validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('5'))], default=0.0, null=False, decimal_places=6, max_digits=8, help_text='Attraction of solutions to best global candidates.')
    psoC3 = models.DecimalField('Random changes', validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('5'))], default=0.04, null=False, decimal_places=6, max_digits=8, help_text='Standard deviation of random changes affecting solutions.')
    forceNonExceedance = models.DecimalField('Force non-exceedance', validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('5'))], default=1, null=False, decimal_places=6, max_digits=8, help_text='Large values help overcoming gaps in the Pareto fronts.')
    
    introducedBy = models.ForeignKey(User, null=False, blank=False, on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)

@receiver(pre_delete, sender=Forecast)
def forecast_delete(sender, instance, **kwargs):
    # Pass false so FileField doesn't save the model.
    instance.forecastFile.delete(False)

class Colormap(models.Model):
    name = models.CharField(max_length=255, null=False, blank=False, unique=True)
    
    # Folder where data files should go (automatic)
    staticDir = os.path.dirname(os.path.abspath(__file__))
    fs = FileSystemStorage(location=staticDir)
    file = models.FileField(upload_to='static/timeSeries/colormaps/', storage=fs, null=False, blank=False)
    
    introducedBy = models.ForeignKey(User, null=False, blank=False, on_delete=models.PROTECT, verbose_name='Introduced by')
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class SatelliteData(models.Model):
    TRMM3B42v7_3h = ('TRMMSatelliteRainfall')  # name of the satellite data class
    TRMM3B42v7_3h_RT =  ('TRMMSatelliteRainfallRT')  # name of the satellite data class
    PRODUCT_CHOICES = (
        (TRMM3B42v7_3h_RT, 'TRMM 3B42 3h realtime'),
        (TRMM3B42v7_3h, 'TRMM 3B42 3h'),
    )

    name = models.CharField(max_length=255, null=False, blank=False, unique=True)
    satellite = models.CharField('Satellite product', max_length=255, default=TRMM3B42v7_3h, choices=PRODUCT_CHOICES, null=False, blank=False, help_text='Choice among supported satellite products.')
    observations = models.TextField(null=True, blank=True)
    startDate = models.DateTimeField('Start date', default=datetime.datetime(2010, 10, 1, 0, 0, 0), null=False, help_text='Start date of data collection.')
    lastRecord = models.DateTimeField('Last record', default=None, null=True, help_text='Date of the last entry on record.')
    
    # information to be filled automatically
    productSite = models.CharField(max_length=255, null=False, blank=False, unique=False, verbose_name='Product site')
    downloadSite = models.CharField(max_length=255, null=False, blank=False, unique=False, verbose_name='Product download site')
    description = models.TextField(null=False, blank=False)
    units = models.CharField(max_length=64, null=False, blank=False)
    timestep = models.CharField(max_length=255, null=False, blank=False, unique=False)
    series = models.ForeignKey(Series, null=True, blank=False)
    jobId = models.CharField(max_length=254, null=True, blank=False)
    
    # Folder where data files should go (automatic)
    fs = FileSystemStorage(location=settings.SATELLITE_STORE)
    dataFolder = models.CharField(max_length=255, null=False, blank=False, unique=False, default=os.path.join(fs.base_location, '__unknown__'))
        
    # Geometry file (.geoJSON)
    staticDir = os.path.dirname(os.path.abspath(__file__))
    fs = FileSystemStorage(location=staticDir)
    geometry = models.FileField(upload_to='static/timeSeries/satelliteData/geometries/', storage=fs, null=False, blank=False)
    jsonGeometry = models.TextField(null=False, blank=True, default='')
    readyGeometry = models.BooleanField('Geometry ready', default=False, null=False)
    location = models.ForeignKey(Location, null=True, blank=False)
    #===========================================================================
    # lon = models.DecimalField(decimal_places=10, max_digits=15, null=True, blank=False, default=None)
    # lat = models.DecimalField(decimal_places=10, max_digits=15, null=True, blank=False, default=None)
    #===========================================================================
    
    # Access
    username = models.CharField(max_length=255, null=True, blank=True, unique=False, verbose_name='Username')
    password = models.CharField(max_length=255, null=True, blank=True, unique=False, verbose_name='Password')
    downloadThreads = models.PositiveIntegerField('Download threads', default = 3, null=False, blank=False, help_text='How many downloads to attempt in parallel.')
    readThreads = models.PositiveIntegerField('Read threads', default = 8, null=False, blank=False, help_text='How many files to interpret in parallel.')
    
    # Colormap
    colormap = models.ForeignKey(Colormap, null=True, blank=False, on_delete=models.PROTECT)
    
    introducedBy = models.ForeignKey(User, null=False, blank=False, on_delete=models.PROTECT, verbose_name='Introduced by')
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Satellite data"

@receiver(pre_delete, sender=SatelliteData)
def satelliteDataforecast_delete(sender, instance, **kwargs):
    try:
        dataFolder = instance.dataFolder
        shutil.rmtree(dataFolder)
    except Exception as ex:
        print(str(ex))
    
    periodicTasks = PeriodicTask.objects.filter(name = instance.name + ' Update')
    if periodicTasks:
        periodicTasks[0].delete()
