'''
Created on 29 Oct 2016

Responsible for checking and including default database entries into Tethys.
'''
import os
from Crypto.Random import random
from timeSeries.models import DataProvider, DataType, Colormap
from django.contrib.auth.models import User
from django.core.files import File

def prepareTethys():
    try:
        staticDir = os.path.dirname(os.path.abspath(__file__))
        
        # Add tethys user (no special privileges)
        tmp = User.objects.filter(username='tethys')
        if len(tmp)==0:
            key = random.getrandbits(64*8)
            user = User.objects.create_user('tethys', 'tethys@some.url', 'SomePassword' + str(random.getrandbits(256)))
            user.save()
        else:
            user = tmp[0]
        
        # Add satellite aggregation data type
        tmp = DataType.objects.filter(abbreviation='Sat', name='Satellite data aggregation')
        if len(tmp)==0:
            with open(os.path.normpath(os.path.join(staticDir, '..', 'extra', 'icons', 'satellite.png')), 'rb') as f:
                dataType = DataType(abbreviation='Sat',
                                    name='Satellite data aggregation',
                                    units='undefined',
                                    description='Automatic data type created to define the sum of satellite data.',
                                    observations='Units for this data type are not defined. They depend on the units of each specific satellite data product.',
                                    introducedBy=user,
                                    )
                dataType.icon.save('satellite.png', File(f), save=True)
                dataType.save()
    
        # Add local data provider
        tmp = DataProvider.objects.filter(name='Tethys')
        if len(tmp)==0:
            with open(os.path.normpath(os.path.join(staticDir, '..', 'extra', 'icons', 'tethys.png')), 'rb') as f:
                dataProvider = DataProvider(abbreviation='Tethys',
                                    name='Tethys',
                                    description='Automatic data provider created to define series produced locally.',
                                    email='tethys@some.url',
                                    introducedBy=user,
                                    )
                dataProvider.icon.save('tethys.png', File(f), save=True)
                dataProvider.save()
    
        # Add discharge data type
        tmp = DataType.objects.filter(abbreviation='Q', name='Discharge')
        if len(tmp)==0:
            with open(os.path.normpath(os.path.join(staticDir, '..', 'extra', 'icons', 'river.png')), 'rb') as f:
                dataType = DataType(abbreviation='Q',
                                    name='Discharge',
                                    units='m3/s',
                                    description='River discharge in m3/s',
                                    observations=None,
                                    introducedBy=user,
                                    )
                dataType.icon.save('discharge.png', File(f), save=True)
                dataType.save()
                
        # Add water level data type
        tmp = DataType.objects.filter(abbreviation='h', name='Water level')
        if len(tmp)==0:
            with open(os.path.normpath(os.path.join(staticDir, '..', 'extra', 'icons', 'waterLevel.png')), 'rb') as f:
                dataType = DataType(abbreviation='h',
                                    name='Water Level',
                                    units='m',
                                    description='Water level in m (relative to the talweg)',
                                    observations=None,
                                    introducedBy=user,
                                    )
                dataType.icon.save('waterLevel.png', File(f), save=True)
                dataType.save()
                
        # Add colormap parula
        tmp = Colormap.objects.filter(name='parula')
        if len(tmp)==0:
            with open(os.path.normpath(os.path.join(staticDir, '..', 'extra', 'icons', 'colormap_parula.png')), 'rb') as f:
                colormap = Colormap(name='parula',
                                    introducedBy=user,
                                    )
                colormap.file.save('parula.png', File(f), save=True)
                colormap.save()
                
        # Add colormap jet
        tmp = Colormap.objects.filter(name='jet')
        if len(tmp)==0:
            with open(os.path.normpath(os.path.join(staticDir, '..', 'extra', 'icons', 'colormap_jet.png')), 'rb') as f:
                colormap = Colormap(name='jet',
                                    introducedBy=user,
                                    )
                colormap.file.save('colormap_jet.png', File(f), save=True)
                colormap.save()
                
        # Add colormap hot
        tmp = Colormap.objects.filter(name='hot')
        if len(tmp)==0:
            with open(os.path.normpath(os.path.join(staticDir, '..', 'extra', 'icons', 'colormap_hot.png')), 'rb') as f:
                colormap = Colormap(name='hot',
                                    introducedBy=user,
                                    )
                colormap.file.save('colormap_hot.png', File(f), save=True)
                colormap.save()
        
        # Add colormap hsv
        tmp = Colormap.objects.filter(name='hsv')
        if len(tmp)==0:
            with open(os.path.normpath(os.path.join(staticDir, '..', 'extra', 'icons', 'colormap_hsv.png')), 'rb') as f:
                colormap = Colormap(name='hsv',
                                    introducedBy=user,
                                    )
                colormap.file.save('colormap_hsv.png', File(f), save=True)
                colormap.save()
                
    except Exception as ex:
        print(str(ex))
        