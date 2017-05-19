'''
Created on May 19, 2017

@author: zepedro
'''
import binascii
import warnings
import operator

import dateutil.parser

import numpy as np

from timeSeries.models import Series, Value
from django.db.models import Q
from functools import reduce

def uploadValues(seriesName, values, action=2):
    #actions: [[0, 'Do not upload'],[1, 'Upload'],[2, 'Upload (keep existing)'],[3, 'Upload (overwrite existing)'],[4, 'Upload (delete existing)']]
    
    if action==0:
        return None
    
    warnings.filterwarnings('ignore', '.*Invalid utf8 character string.*',)
    
    seriesObj = Series.objects.get(name=seriesName)
    toInput = list()
    if action==1:
        # simple upload
        ctr = 0
        for i0, d0 in enumerate(values):
            ctr += 1
            toInput.append(Value(series=seriesObj, date=d0['date'][:-1], record=binascii.a2b_base64(d0['value'])))
            if i0 % 1000==0 and i0!=0:
                Value.objects.bulk_create(toInput)
                toInput = list()
        Value.objects.bulk_create(toInput)
        
        return ctr
    
    elif action==2:
        # keep existing
        result = Value.objects.filter(series=seriesObj.id).filter(date__gte=values[0]['date']).filter(date__lte=values[-1]['date']).order_by('date')
        dates = np.array([x.date for x in result])
        
        for i0 in range(len(values)-1, -1, -1):
            if dateutil.parser.parse(values[i0]['date']) in dates:
                values.pop(i0)
        
        return uploadValues(seriesName, values, action=1)
    
    elif action==3:
        # overwrite existing
        dates = np.array([dateutil.parser.parse(x['date']) for x in values])
        Value.objects.filter(series=seriesObj.id).filter(date__gte=values[0]['date']).filter(date__lte=values[-1]['date']).filter(reduce(operator.or_, (Q(date=x) for x in dates))).delete()
        
        return uploadValues(seriesName, values, action=1)

    elif action==4:
        # delete existing
        Value.objects.filter(series=seriesObj.id).filter(date__gte=values[0]['date']).filter(date__lte=values[-1]['date']).delete()
            
        return uploadValues(seriesName, values, action=1)
            
    return 0
    
    
    
        
        
    
    
    
    
    
    