# coding: utf-8
'''
Created on 24/02/2016

@author: Jose Pedro Matos
'''

import datetime as dt
import numpy as np
import pickle
import re
import json
import dateutil.parser
import matplotlib.pyplot as plt

from celery import current_task
from dateutil.relativedelta import relativedelta
from gpu.ann import ann
from gpu.errorMetrics import errorMetrics
from gpu.psoAlt import PSOAlt
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.interpolate import interp1d
from sklearn.cluster import MiniBatchKMeans
from gpu.functions import processBands, predictiveQQ, metrics

def fSecond(ref, shift):
    return ref.astype(dt.datetime)+dt.timedelta(seconds=shift)

def fMinute(ref, shift):
    return ref.astype(dt.datetime)+dt.timedelta(minutes=shift)

def fHour(ref, shift):
    return ref.astype(dt.datetime)+dt.timedelta(hours=shift)

def fDay(ref, shift):
    return ref.astype(dt.datetime)+dt.timedelta(days=shift)

def fWeek(ref, shift):
    return ref.astype(dt.datetime)+dt.timedelta(days=7*shift)

def fMonth(ref, shift):
    return ref.replace(year=ref.year+np.int(ref.month+shift/12), month=np.mod(ref.month+shift,12))

def fYear(ref, shift):
    return ref.replace(year=ref.year+shift)

def fGenerateLeads(maxLead, number=None, maxGap=20):
    if number == None:
        number = np.ceil(np.sqrt(maxLead))
    tmp = np.unique(np.round(np.power(1.5, np.linspace(0, np.log(maxLead)/np.log(1.5), number+1))))
    leads = [1,]
    for i0 in range(1,len(tmp)):
        if (tmp[i0]-tmp[i0-1]>maxGap):
            leads.extend(np.round(np.linspace(tmp[i0-1], maxLead, np.ceil((maxLead-tmp[i0-1])/maxGap)+1)[1:]))
            break
        else:
            leads.append(tmp[i0])
    return [int(i0) for i0 in leads]
    
def getDateList(dateFrom, dateTo, years=0, months=0, weeks=0, days=0, hours=0, minutes=0, seconds=0):
    if years!=0:
        tmp = relativedelta(dateTo, dateFrom).years
        dates = []
        for i0 in np.arange(0, tmp):
            dates.append(dateFrom+relativedelta(years=+i0))
        return dates
    
    if months!=0:
        tmp = relativedelta(dateTo, dateFrom).months
        dates = []
        for i0 in np.arange(0, tmp):
            dates.append(dateFrom+relativedelta(months=+i0))
        return dates
    
    return [d0.astype(object) for d0 in np.arange(dateFrom, 
                                                  dateTo+dt.timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds), 
                                                  dt.timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)
                                                  )]
    
    pass

def getResampledTime(datesDesired, datesExpected, dates, values, maxMissing=0.15):
    '''
    Resamples one series to another's time step.
    
    datesDesired: the dates of the final series (after resampling).
    datesExpected: the dates that should be present in the series to be resampled.
    dates: the dates actually present in the series to be resampled.
    values: the values that correspond to the present dates.
    maxMissing: the maximum fraction of missing values for the resampling value to be accepted as valid.
    '''
    
    datesDesired = np.array(datesDesired, dtype='datetime64[s]')
    datesDesired = datesDesired[np.logical_and(datesDesired>=np.array(datesExpected[0], dtype='datetime64[s]'), datesDesired<=np.array(datesExpected[-1], dtype='datetime64[s]'))]
    
    valuesDesired = np.empty_like(datesDesired, dtype=np.double)*np.NaN
    
    datesExpected = np.array(datesExpected, dtype='datetime64[s]')
        
    i0 = 0
    i1 = 0
    i2 = 0
    while i0<len(datesDesired):
        ctr = 0
        while datesExpected[i1]<datesDesired[i0]:
            ctr += 1
            i1 += 1
            
        tmpSubset = []
        while dates[i2]<datesDesired[i0]:
            tmpSubset.append(values[i2])
            i2 += 1
        if len(tmpSubset)>ctr*(1-maxMissing):
            valuesDesired[i0] = np.nansum(tmpSubset)
         
        i0 += 1
    
    datesDesired = datesDesired[np.logical_not(np.isnan(valuesDesired))]
    valuesDesired = valuesDesired[np.logical_not(np.isnan(valuesDesired))]
    
    return (datesDesired, valuesDesired)

class Data(object):
    __PERIOD__ = {'seconds': fSecond,
                  'minutes': fMinute,
                  'hours': fHour,
                  'days': fDay,
                  'weeks': fWeek,
                  'months': fMonth,
                  'years': fYear,
                  }
    
    __CUSTOMFUNCTIONS__ = [{('targets', 'lead(targets)'),
                            ('extra', 'lead(extra'),
                            (']', '])'),
                            },
                           
                           {('known(lead', '('),
                            },
                           
                           {('lead(', 's.fLead(l,'),
                            ('filter(','s.fmFilter('),
                            ('targets', 's.values'),
                            ('extra', 's.extra', ''),
                            ('cycle', 's.cycle(s.xPeriodic)[:,0], s.cycle(s.xPeriodic)[:,1]'),
                            ('sum(', 's.fSum(l,'),
                            ('known', ''),
                            ('log(', 'np.log('),
                            ('rand', 'np.random.randn(s.values.shape[0])'),
                            ('leadtime', 'l'),
                           }]
    
    def __init__(self, data, extra=None, refTime=dt.datetime(2000, 1, 1, 0, 0, 0), period='years', timeStepUnit='days', timeStepSize=1):
        self.refTime = refTime
        self.fPeriod = self.__PERIOD__[period]
        self.fTimeJump = self.__PERIOD__[timeStepUnit]
        self.period = period
        self.normalization = {}
        self.fData = None
        self.timeStepUnit = timeStepUnit
        self.timeStepSize = timeStepSize
    
        # join times from data and extra
        allDates = data[0]
        if extra != None:
            for e0 in extra:
                if (len(e0[0])==0):
                    raise Exception('No data available in the requested period.')
                else:
                    allDates = np.hstack((allDates, e0[0]))
        allDates = np.unique(allDates)
        
        # find a reference before records start
        firstRecord = np.min(allDates)
        dJump = -2
        while np.datetime64(self.fPeriod(self.refTime, dJump))>firstRecord:
            dJump*=2
        tmp = dJump
        dJump = 2
        while np.datetime64(self.fPeriod(self.refTime, tmp + dJump*2))<firstRecord:
            dJump *= 2
        dJump += tmp
        self.startReference = dJump
        
        # build straight time vector
        tmpDates = [firstRecord,]
        for i0 in range(1,len(allDates)):
            tmp = np.datetime64(self.fTimeJump(allDates[i0-1], timeStepSize))
            i1 = 1
            while tmp<allDates[i0]:
                tmpDates.append(tmp)
                i1 += 1
                tmp = np.datetime64(self.fTimeJump(allDates[i0-1], timeStepSize*i1))
            tmpDates.append(allDates[i0])
        self.dates = np.array(tmpDates, dtype='datetime64[s]')
        
        # add information derived from the reference and the period
        self.upDateGroupAndPeriod()
        
        # prepare target and extra arrays
        self.values = np.empty_like(self.dates, dtype=np.double)*np.nan
        self.values[self.__ismember__(data[0], self.dates)] = data[1]
        self.extra = []
        if extra != None:
            for i0 in range(len(extra)):
                self.extra.append(np.empty(self.dates.shape[0], dtype=np.double)*np.nan)
                self.extra[-1][self.__ismember__(extra[i0][0], self.dates)] = extra[i0][1]
        
        self.splitTra = np.ones_like(self.dates, dtype=np.bool)
        self.splitVal = np.zeros_like(self.dates, dtype=np.bool)
     
    def upDateGroupAndPeriod(self):
        self.splitGroup = np.empty(self.dates.shape, dtype=np.int)
        self.xPeriodic = np.empty(self.dates.shape)
        dJump = self.startReference
        for i0 in range(len(self.dates)):
            while np.datetime64(self.fPeriod(self.refTime, dJump+1))<=self.dates[i0]:
                dJump+=1
            self.splitGroup[i0] = dJump
            self.xPeriodic[i0] = ((self.dates[i0]-np.datetime64(self.fPeriod(self.refTime, dJump))) / 
                                  (np.datetime64(self.fPeriod(self.refTime, dJump+1))-np.datetime64(self.fPeriod(self.refTime, dJump))))    
        self.xPeriodic = np.mod(self.xPeriodic, 1) + (self.xPeriodic==1).astype(float)
        
    def cycle(self, x):
        return np.transpose(np.array((np.sin(x*2*np.pi), np.cos(x*2*np.pi))))
    
    def split(self, valFraction, minValidFraction=0.50, trainingDatesStr=''):
        # Generate training and validation groups
        
        groups = list(np.unique(self.splitGroup))
        rejectedGroups = []
        
        if trainingDatesStr!='':
            # Specified training dates
            trainingDates = []
            tmp = json.loads(trainingDatesStr)
            for k0 in tmp.keys():
                if tmp[k0]:
                    trainingDates.append(dateutil.parser.parse(k0))
            trainingDates.sort()
            trainingDates = np.array(trainingDates, dtype='datetime64[ms]')
            
            self.splitVal = groups
            self.splitTra = []
            for d0 in trainingDates:
                tmp = np.where(d0==self.dates)[0]
                if len(tmp)>0:
                    tmp = tmp[0]
                    self.splitTra.append(self.splitGroup[tmp])
                    tmp = np.where(self.splitVal==self.splitTra[-1])[0][0]
                    self.splitVal.pop(tmp)
            while len(self.splitTra)<2:
                self.splitTra.append(self.splitVal.pop(-1))
            self.idxTra = np.zeros_like(self.splitGroup, dtype=np.bool)
            for i0 in self.splitTra:
                self.idxTra[np.where(self.splitGroup==i0)[0]]=True
            self.idxVal = np.logical_not(self.idxTra)
        else:
            # Only take as valid periods with 25% of data or more
            tmpNaN = [self.values,]
            tmpNaN.extend(self.extra)
            tmpNaN = np.transpose(np.isnan(np.sum(np.vstack(tmpNaN),axis=0)))
            for i0 in range(len(groups)-1,-1,-1):
                idx = np.where(self.splitGroup==groups[i0])[0]
                if np.mean(tmpNaN[idx])>1-minValidFraction:
                    rejectedGroups.append(groups.pop(i0))
            
            np.random.shuffle(groups)
            np.random.shuffle(rejectedGroups)
            groups.extend(rejectedGroups)
            traSize = np.int(len(groups)*(1-valFraction))
            self.idxVal = np.zeros_like(self.splitGroup, dtype=np.bool)
            for i0 in groups[traSize:]:
                self.idxVal[np.where(self.splitGroup==i0)[0]]=True
            self.idxTra = np.logical_not(self.idxVal)
            self.splitTra = groups[:traSize]
            self.splitVal = groups[traSize:]
        
    def setSeasons(self, nSeasons, gamma=0.001, timeCoef=1):
        # build an ordered matrix for each season
        groups = np.unique(self.splitGroup)
        times = np.unique(self.xPeriodic)
        ordered = np.empty((len(groups), len(times)))*np.nan
            # prepare matrix
        for i0 in range(len(groups)):
            tmp = self.xPeriodic[self.splitGroup==groups[i0]] 
            ordered[i0, self.__ismember__(tmp, times)] = self.values[self.splitGroup==groups[i0]] 
            # fill missing with the average
        tmp = np.nanmean(ordered, axis=0)
        tmp[np.isnan(tmp)]=np.nanmean(tmp)
        for i0 in range(len(times)):
            ordered[np.isnan(ordered[:,i0]),i0] = tmp[i0]
        
        # focus on training
        tmp = np.zeros_like(groups, dtype=np.bool)
        for i0, g0 in enumerate(groups):
            if g0 in self.splitTra:
                tmp[i0] = g0
        ordered = ordered[tmp,:]
        
        # normalize
        ordered = (ordered-np.min(ordered))/(np.max(ordered)-np.min(ordered))

        # apply PCA
        pca = PCA(n_components=5)
        pca.fit(ordered)
        tmp = len(np.where(np.cumsum(pca.explained_variance_ratio_)<=0.8)[0]) + 1
        pcaData = pca.components_[:tmp,:]*np.transpose(np.tile(pca.explained_variance_ratio_[:tmp]/pca.explained_variance_ratio_[0],(ordered.shape[1],1)))
        
        # apply clustering
        toCluster = np.hstack((self.cycle(times)*timeCoef,np.transpose(pcaData)))
        kMeans = KMeans(n_clusters=nSeasons)
        kMeans.fit(toCluster)
        tmpSeasons = kMeans.predict(toCluster)
        
        # smooth clusters
        tmpIdxs = np.hstack((times, times[-1]+times, times[-1]*2+times))
        tmpClusters = np.hstack((tmpSeasons, tmpSeasons, tmpSeasons))
        tmpSmoothSeasons = np.zeros((nSeasons, len(times)))
        for i0 in range(nSeasons):
            centers = tmpIdxs[np.where(tmpClusters==i0)[0]]
            for c0 in centers:
                tmp = c0-tmpIdxs
                rbf=np.exp(-1/gamma*np.square(tmp));
                tmpSmoothSeasons[i0,:]=tmpSmoothSeasons[i0,:]+rbf[len(times):2*len(times)]
        tmp = 1/np.sum(tmpSmoothSeasons, axis=0)
        tmpSmoothSeasons = tmpSmoothSeasons*np.tile(tmp,(nSeasons,1))
        tmpSmoothSeasons = np.hstack((tmpSmoothSeasons[:,-2:], tmpSmoothSeasons, tmpSmoothSeasons[:,:1]))
        tmpSmoothTimes = np.hstack((times[-2:]-1, times, times[:1]+1))
        
        # prepare interpolation functions
        self.fSeasonCoef=[]
        self.fSeasonCoefData=[]
        for i0 in range(nSeasons):
            tmp = tmpSmoothSeasons[i0,:]
            tmp[tmp<0.001]=0
            tmp[tmp>0.999]=1
            self.fSeasonCoefData.append((tmpSmoothTimes, tmp))
            self.fSeasonCoef.append(interp1d(tmpSmoothTimes, tmp, kind='linear'))

    def __returnValidTrain__(self, X, y):
        return ~np.isnan(np.sum(np.vstack((X,y)),axis=0))
    
    def __returnValidForecast__(self, X):
        return ~np.isnan(np.sum(X,axis=0))
    
    def getSeasonCoefs(self, season=0):
        return (self.fSeasonCoef[season](self.xPeriodic), np.where(self.fSeasonCoef[season](self.xPeriodic)!=0)[0])
    
    def getTraDates(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxTra)
        tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
        return self.dates[tmpTarget1]
        
    def getValDates(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxVal)
        tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
        return self.dates[tmpTarget1]
    
    def getForDates(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidForecast__(self.X), self.idxVal)
        if season==None:
            return self.dates[tmpTarget0]
        else:
            tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
            return self.dates[tmpTarget1]
    
    def getTraX(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxTra)
        tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
        return (self.X[:, tmpTarget1],
                self.fSeasonCoef[season](self.xPeriodic)[tmpTarget1],
                np.where(self.fSeasonCoef[season](self.xPeriodic)[tmpTarget0]!=0)[0])
    
    def getTraY(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxTra)
        tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
        return (self.y[tmpTarget1],
                self.fSeasonCoef[season](self.xPeriodic)[tmpTarget1],
                np.where(self.fSeasonCoef[season](self.xPeriodic)[tmpTarget0]!=0)[0])
    
    def getTraIdxs(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxTra)
        tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
        return np.arange(len(tmpTarget1))[tmpTarget1]

    def getValX(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxVal)
        tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
        return (self.X[:, tmpTarget1],
                self.fSeasonCoef[season](self.xPeriodic)[tmpTarget1],
                np.where(self.fSeasonCoef[season](self.xPeriodic)[tmpTarget0]!=0)[0])

    def getValY(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxVal)
        tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
        return (self.y[tmpTarget1],
                self.fSeasonCoef[season](self.xPeriodic)[tmpTarget1],
                np.where(self.fSeasonCoef[season](self.xPeriodic)[tmpTarget0]!=0)[0])

    def getValIdxs(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxVal)
        tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
        return np.arange(len(tmpTarget1))[tmpTarget1]

    def getForX(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidForecast__(self.X), self.idxVal)
        if season==None:
            tmpTarget1 = tmpTarget0
            return self.X[:, tmpTarget0]
        else:
            tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
            return (self.X[:, tmpTarget1],
                    self.fSeasonCoef[season](self.xPeriodic)[tmpTarget1],
                    np.where(self.fSeasonCoef[season](self.xPeriodic)[tmpTarget0]!=0)[0])

    def getForY(self, season=0):
        tmpTarget0 = np.logical_and(self.__returnValidForecast__(self.X), self.idxVal)
        if season==None:
            return self.y[tmpTarget0]
        else:
            tmpTarget1 = np.logical_and(tmpTarget0, self.fSeasonCoef[season](self.xPeriodic)!=0)
            return (self.y[tmpTarget1],
                    self.fSeasonCoef[season](self.xPeriodic)[tmpTarget1],
                    np.where(self.fSeasonCoef[season](self.xPeriodic)[tmpTarget0]!=0)[0])

    def __ismember__(self, a, b):
        bind = {}
        for i, elt in enumerate(b):
            if elt not in bind:
                bind[elt] = i
        return [bind.get(itm, None) for itm in a]
    
    def fmFilter(self, x, beta=0.79352):
        tmp = np.array(x)
        for i0 in range(1,x.shape[0]):
            if not np.isinf(tmp[i0]):
                tmp0 = tmp[i0-1]+(1-beta)*(tmp[i0]-tmp[i0-1])
                if not np.isnan(tmp0):
                    tmp[i0] = tmp0
            else:
                tmp[i0] = tmp0
        return tmp
    
    def fLead(self, lead, x, override=None):
        lead = int(lead)
        if override != None:
            lead = override
        
        tmp = np.empty_like(x)*np.nan
        if lead==0:
            return x
        if lead>0:
            tmp[lead:]=x[:-lead]
        else:
            tmp[:lead]=x[-lead:]
        return tmp
    
    def fSum(self, lead, x, override=None):
        lead = int(lead)
        if override != None:
            lead = override
        
        tmpX = x.copy()
        if lead==0:
            return tmpX
        nanIdx = np.where(np.isnan(tmpX))[0]
        tmpX[nanIdx] = 0
        if lead>0:
            tmpX = np.cumsum(tmpX)
            tmp = np.empty_like(tmpX)*np.nan
            tmp[lead:]=tmpX[lead:]-tmpX[:-lead]
        elif lead<0:
            tmpX = np.cumsum(tmpX)
            tmp = np.empty_like(tmpX)*np.nan
            tmp[:-lead]=tmpX[:-lead]-tmpX[lead:]
        toErase = []
        if lead>0:
            for i0 in range(nanIdx.shape[0]):
                toErase.append(nanIdx[i0]+range(int(lead)+1))
        else:
            for i0 in range(nanIdx.shape[0]):
                toErase.append(nanIdx[i0]+range(0,int(lead)-1,-1))
        if len(toErase)>0:
            toErase = np.unique(np.hstack(toErase))
            toErase = toErase[toErase>=0]
            toErase = toErase[toErase<tmpX.shape[0]]
            tmp[toErase] = np.NaN
        return tmp
    
    def prepareInputs(self, lead):
        self.X = self.fData(self, lead)
    
    def prepareTargets(self, lead):
        tmp = self.values.copy()
        self.y = self.fTarget(self, lead)
        self.values = tmp
    
    def parseInputFunction(self, dataFunctionStr):
        # Remove non-recognized characters
        dataFunctionStr = dataFunctionStr.replace(' ','')
        allowed = [s0[0] for s0 in self.__CUSTOMFUNCTIONS__[2]]
        toKeep = []
        i0 = 0
        for s0 in allowed:
            while s0 in dataFunctionStr:
                dataFunctionStr = dataFunctionStr.replace(s0, '#' + str(i0) + '#', 1)
                toKeep.append(s0)
                i0 += 1
        if len(re.findall('[a-zA-Z]', dataFunctionStr))>0:
            raise Exception('Some keywords in the data parsing function are not allowed. Code halted. The allowed keywords are: ' + str(allowed))
        dataFunctionStr = re.sub('[a-zA-Z]','', dataFunctionStr)
        
        for i0, s0 in enumerate(toKeep):
            dataFunctionStr = dataFunctionStr.replace('#' + str(i0) + '#', s0, 1)
        
        # Perform the substitutions
        for s0 in self.__CUSTOMFUNCTIONS__:
            for s1 in s0:
                dataFunctionStr = dataFunctionStr.replace(s1[0], s1[1])
        
        # Parse the expression
        self.fDataStr = 'lambda s, l: np.vstack((' + dataFunctionStr + ',))'
        self.fData = eval(self.fDataStr)
    
    def parseTargetFunction(self, targetFunctionStr):
        # Remove non-recognized characters
        targetFunctionStr = targetFunctionStr.replace(' ','')
        allowed = [s0[0] for s0 in self.__CUSTOMFUNCTIONS__[2]]
        toKeep = []
        i0 = 0
        for s0 in allowed:
            while s0 in targetFunctionStr:
                targetFunctionStr = targetFunctionStr.replace(s0, '#' + str(i0) + '#', 1)
                toKeep.append(s0)
                i0 += 1
        if len(re.findall('[a-zA-Z]', targetFunctionStr))>0:
            raise Exception('Some keywords in the data parsing function are not allowed. Code halted. The allowed keywords are: ' + str(allowed))
        targetFunctionStr = re.sub('[a-zA-Z]','', targetFunctionStr)
        
        for i0, s0 in enumerate(toKeep):
            targetFunctionStr = targetFunctionStr.replace('#' + str(i0) + '#', s0, 1)
        
        # Perform the substitutions
        for s0 in self.__CUSTOMFUNCTIONS__:
            for s1 in s0:
                targetFunctionStr = targetFunctionStr.replace(s1[0], s1[1])
        
        self.fTargetStr = 'lambda s, l: ' + targetFunctionStr
        self.fTarget = eval(self.fTargetStr)
    
    def setNormalization(self):
        # get valid training data
        tmpTarget0 = np.logical_and(self.__returnValidTrain__(self.X, self.y), self.idxTra)
        X = self.X[:, tmpTarget0]
        y = self.y[tmpTarget0]
        # retrieve normalization constants
        self.normalization['X']={'mean': np.mean(X, axis=1, keepdims=True), 'std': np.std(X, axis=1, keepdims=True)}
        self.normalization['y']={'mean': np.mean(y, axis=0, keepdims=True), 'std': np.std(y, axis=0, keepdims=True)}
        # accounting for constant inputs
        tmp = self.normalization['X']['std']==0
        self.normalization['X']['std'][tmp] = 1
        tmp = self.normalization['y']['std']==0
        self.normalization['y']['std'][tmp] = 1
    
    def normalize(self, X=[], y=[]):
        result = []
        if len(X)!=0:
            result.append((X-self.__shapeToData(X, self.normalization['X']['mean']))/self.__shapeToData(X, self.normalization['X']['std']))
        if len(y)!=0:
            result.append((y-self.__shapeToData(y, self.normalization['y']['mean']))/self.__shapeToData(y, self.normalization['y']['std']))
        return result
        
    def denormalize(self, X=[], y=[]):
        result = list()
        if len(X)!=0:
            result.append((X*self.__shapeToData(X, self.normalization['X']['std']))+self.__shapeToData(X, self.normalization['X']['mean']))
        if len(y)!=0:
            result.append((y*self.__shapeToData(y, self.normalization['y']['std']))+self.__shapeToData(y, self.normalization['y']['mean']))
        return result

    def __shapeToData(self, data, x):
        tmp = x.shape 
        axis = np.where(np.array(tmp)==1)[0]
        if len(axis)==len(tmp):
            return np.tile(x, data.shape)
        if len(axis)>0:
            return np.repeat(x, data.shape[axis[0]], axis=axis[0])
        else:
            return None
      
    def getZeroThreshold(self):
        return (0-self.normalization['y']['mean'])/self.normalization['y']['std']
    
class Manager(object):
    #queue =     
    def __init__(self, data=None, dataFunction='cycle,(targets ,filter(targets)', targetFunction='known(targets)', extra=None,
                 nodes=4, epochs = 250, population = 1000, regularization=0.05, errorFunction='MSE',
                 seasons=1, leads=(1, 5, 10,), refTime=dt.datetime(2000, 1, 1, 0, 0, 0), period='years', timeStepUnit='days', timeStepSize=1,
                 valFraction=0.3, displayEach=100, openClPlatform=0, openClDevice='GPU', forecast=False, activationFunction='tan', weigthRange=8, 
                 transformWeights=False, allowNegative=True, reduceTraining=1, trainingDates='', **kwargs):

        if data!=None:
            # handling of arguments
            self.opt={}
            self.opt['seasons'] = seasons
            self.opt['leads'] = np.sort(leads)
            self.opt['period'] = period
            self.opt['nodes'] = nodes
            self.opt['regularization'] = regularization
            self.opt['valFraction'] = valFraction
            self.opt['population'] = population
            self.opt['epochs'] = epochs
            self.opt['timeStepUnit'] = timeStepUnit
            self.opt['timeStepSize'] = timeStepSize
            self.opt['refTime'] = refTime
            self.opt['period'] = period
            self.opt['displayEach'] = displayEach
            self.opt['openClPlatform'] = openClPlatform
            self.opt['openClDevice'] = openClDevice
            self.opt['activationFunction'] = activationFunction
            self.opt['weigthRange'] = weigthRange
            self.opt['errorFunction'] = errorFunction
            self.opt['transformWeights'] = transformWeights
            self.opt['allowNegative'] = allowNegative
            self.opt['reduceTraining'] = reduceTraining
            self.opt['trainingDates'] = trainingDates
            
            # addition of generic arguments to options
            self.opt.update(kwargs)
            self.kwargs = kwargs
            
            if not forecast:
                # create training data
                self.data=Data(data, extra, refTime=self.opt['refTime'], period=self.opt['period'], timeStepUnit=self.opt['timeStepUnit'], timeStepSize=self.opt['timeStepSize'])
        
                # prepare target modifying function
                self.data.parseTargetFunction(targetFunction)
        
                # prepare data creation function
                self.data.parseInputFunction(dataFunction)
                
                # split in training and validation
                self.data.split(self.opt['valFraction'], trainingDatesStr=self.opt['trainingDates'])
                
                # split in seasons
                # TODO: understand how the splitting depends on the input preparation
                self.data.setSeasons(self.opt['seasons'])
                
                # set normalization
                tmp = (self.opt['leads'][-1]/2).round(0)
                if tmp==0:
                    tmp = 1
                self.data.prepareInputs(tmp)
                self.data.prepareTargets(tmp)
                self.data.setNormalization()
                self.data.X = []
    
    def train(self):
        self.__readyModels__=[]
        tmpCounter = 1
        taskInfo = {'message': []}
        for lead in self.opt['leads']:
            result=[]
            for season in range(self.opt['seasons']):
                try:
                    if len(taskInfo['message'])>0:
                        taskInfo['message'].append('')
                    taskInfo['message'].append('Training new set: leadtime:%2u, Season:%2u' % (lead, season+1))
                    current_task.update_state(state='PROGRESS', meta=taskInfo)
                except Exception:
                    pass
                
                self.data.prepareInputs(lead)
                self.data.prepareTargets(lead)
                XTrain = self.data.getTraX(season=season)[0]
                yTrain = self.data.getTraY(season=season)[0]
                
            
                XTrain, yTrain = self.data.normalize(XTrain, yTrain)
            
                # get highest and lowest target periods
                idxsTrain =self.data.getTraIdxs(season=season)
                groups = self.data.splitGroup[idxsTrain]
                tmpUnique = np.unique(groups)
                tmpMax = np.zeros_like(tmpUnique)
                for i0, idx0 in enumerate(tmpUnique):
                    tmp = np.where(groups==idx0)[0]
                    tmpMax[i0] = np.max(yTrain[tmp])
                tmp = np.argsort(tmpMax)[[0, len(tmpMax)-1]]
                plotIdxs = []
                for i0 in tmpUnique[tmp]:
                    plotIdxs.extend(np.where(groups==i0)[0].tolist())
            
                # transpose for optimization
                XTrain = np.transpose(XTrain)
                yTrain = np.transpose(yTrain)
                
                #===============================================================
                # # Reduce set
                # if self.opt['reduceTraining']!=1:
                #     nClusters = round(yTrain.shape[0]/self.opt['reduceTraining'])
                #     patterns = np.hstack((np.expand_dims(yTrain, 1), XTrain))
                #     kMeans = MiniBatchKMeans(n_clusters=nClusters)
                #     clusters = kMeans.fit_predict(patterns)
                #     self.weights = []
                #     chosen = []
                #     for i0 in range(len(clusters)):
                #         idxs = np.where(clusters==i0)[0]
                #         if len(idxs)>0:
                #             dists = kMeans.transform(patterns[idxs, :])
                #             chosen.append(idxs[np.argmin(dists[:,i0])])
                #             self.weights.append(dists.shape[0])
                #     self.weights = np.array(self.weights)/len(yTrain)
                #     yTrain = yTrain[chosen]
                #     XTrain = XTrain[chosen, :]
                # else:
                #     self.weights = np.ones_like(yTrain)/len(yTrain)
                #===============================================================
                 
                # start ann object
                if self.opt['allowNegative']:
                    self.opt['lowerThreshold'] = -999
                else:
                    self.opt['lowerThreshold'] = self.data.getZeroThreshold()
                #--------------------------------------------- workGroup=(64, 4)
                self.annToOptimize=ann(XTrain, nodes=self.opt['nodes'], openCL=True, workGroup=(64, 4), deviceType=self.opt['openClDevice'],
                                       platform=self.opt['openClPlatform'], activationFunction=self.opt['activationFunction'], verbose=0,
                                       lowerThreshold=self.opt['lowerThreshold'])
                
                # start error object
                #--------------------------------- stride=512, workGroup=(1, 16)
                self.errorOpenCL=errorMetrics(yTrain, stride=128, workGroup=(4, 32), deviceType=self.opt['openClDevice'], platform=self.opt['openClPlatform'], verbose=0, errorFunction=self.opt['errorFunction'])
                
                # prepare model
                print('Starting model ' + str(tmpCounter)  + '/' + str(self.opt['seasons']*len(self.opt['leads'])) + ' (lead:' + str(lead) + ', season:' + str(season) + ')')
                tmpCounter += 1
                model=PSOAlt(XTrain, yTrain, self.annToOptimize.getWeightLen(), evalFun=self.evalFun,
                             errorObj=self.errorOpenCL, regFun=self.regFun, displayEach=self.opt['displayEach'],
                             population=self.opt['population'], epochs=self.opt['epochs'], plotResult=False,
                             taskInfo=taskInfo, transformWeights=self.opt['transformWeights'],
                             bounds=self.opt['weigthRange']*np.vstack((-1*np.ones(self.annToOptimize.getWeightLen()),
                                                                       1*np.ones(self.annToOptimize.getWeightLen()))),
                             plotIdxs=plotIdxs, 
                             **self.kwargs)
                model.start()
                
                if False:
                    plt.figure()
                    plt.plot(self.data.getTraDates(season), self.data.getTraY(season)[0],'.r')
                    plt.plot(self.data.getTraDates(season),
                             self.processBands(
                                               model.predict(self.data.getTraX(season)[0]),
                                               np.array(model.opt['bands'])),
                             '.k')
                result.append(model)
            self.__readyModels__.append(result)
    
    def forecast(self, date, data, extra=None, num=999, leadTargets=None):
        # prepare input data
        if len(data)>0:
            X=Data(data, extra, refTime=self.opt['refTime'], period=self.opt['period'], timeStepUnit=self.opt['timeStepUnit'], timeStepSize=self.opt['timeStepSize'])
            X.fTarget = eval(self.data.fTargetStr)
            X.fData = eval(self.data.fDataStr)
            X.fSeasonCoef = self.data.fSeasonCoef
            X.normalization = self.data.normalization
        else:
            X = self.data
            
        # extend input data
        maxDate = X.fTimeJump(date, self.opt['timeStepSize']*max(self.opt['leads']).astype(float))
        tmp = 0
        tmpDates = []
        while X.fTimeJump(X.dates[-1], tmp*self.opt['timeStepSize'])<maxDate:
            tmp+=1
            tmpDates.append(np.datetime64(X.fTimeJump(X.dates[-1], tmp*self.opt['timeStepSize'])))
        if len(tmpDates)>0:
            X.values = np.hstack((X.values, np.empty(tmp)*np.NaN))
            X.dates = np.hstack((X.dates, tmpDates))
            if X.extra!=None:
                for i0 in range(len(X.extra)):
                    X.extra[i0] = np.hstack((X.extra[i0], np.empty(tmp)*np.NaN))
        
        # update data
        X.upDateGroupAndPeriod()
        
        # run models
        leadSimulations = []
        simTargets = []
        for i0 in range(len(self.opt['leads'])):
            X.prepareTargets(self.opt['leads'][i0])
            X.prepareInputs(self.opt['leads'][i0])
            X.split(1)
            wholePeriod = np.zeros((1,len(self.__readyModels__[i0][0].opt['bands'])))
            notChanged = True
            tmpTarget = np.NaN
            for season in range(self.opt['seasons']):
                toPredict, seasonCoefs = X.getForX(season)[0:2]
                refIdx = np.where(X.getForDates(season)==X.fTimeJump(date, self.opt['timeStepSize']*self.opt['leads'][i0].astype(float)))[0]
                toPredict = X.normalize(toPredict[:,refIdx])[0]
                if toPredict.shape[1]!=0:
                    tmp = self.__readyModels__[i0][season].predict(np.transpose(toPredict))
                    tmp = X.denormalize(y = tmp)[0]
                    wholePeriod[0, :] = wholePeriod[0,:]+tmp*np.transpose(np.tile(seasonCoefs[refIdx], (tmp.shape[1],1)))
                    notChanged = False
                    tmpTarget = X.getForY(season)[0][refIdx]
            if notChanged:
                wholePeriod[:,:] = np.NaN
            leadSimulations.append(wholePeriod)
            simTargets.append(tmpTarget)
        
        # sort bands and interpolate where needed
        bands = np.array(self.__readyModels__[0][0].getBands())
        for i0, s0 in enumerate(leadSimulations):
            s0 = processBands(s0, bands)
        
        # choose target leads
        if leadTargets==None:
            leadTargets = np.unique(np.round(np.hstack((np.linspace(np.min(self.opt['leads']), np.max(self.opt['leads']), num=num), self.opt['leads']))))
        
        # interpolate results in the leadtime space
        forecasts = np.empty((len(leadTargets)+1, leadSimulations[0].shape[1]))*np.nan
        tmp = np.array(leadSimulations).squeeze()
        if len(tmp.shape)==1:
            tmp = np.expand_dims(tmp, 0)
        Y = np.concatenate((
            np.repeat(np.expand_dims(X.fTarget(X, 0)[np.where(X.dates==date)[0]],1), 16, 1),
            tmp
            ))
        x = np.concatenate(((0,), self.opt['leads']))
        xNew = np.concatenate(((0,), leadTargets))
        for i0 in range(Y.shape[1]):
            f = interp1d(x, Y[:, i0], kind='linear') #linear, slinear, quadratic, cubic 
            forecasts[:, i0] = f(xNew)
        simTargets.insert(0, X.fTarget(X, 0)[np.where(X.dates==date)[0]])
        f = interp1d(x, np.hstack(simTargets), kind='linear') #linear, slinear, quadratic, cubic 
        simTargets = f(xNew)  
          
        # associate days
        dates = [np.datetime64(date),]
        for l0 in leadTargets:
            dates.append(np.datetime64(X.fTimeJump(date, l0*self.opt['timeStepSize'])))
        dates = np.array(dates)
        
        # verify validity
        tmp = np.logical_not(np.isnan(np.sum(forecasts, axis=1)))
        dates = dates[tmp]
        forecasts = forecasts[tmp, :]
        simTargets = simTargets[tmp]
        
        return {'dates': dates, 'simulations': forecasts, 'bands': bands, 'targets': simTargets}
    
    def hindcast(self, data, lead, extra=[], bands=None, dateFrom=None):
        # prepare input data
        if dateFrom==None:
            dateFrom = data[0][0]
        if len(data)>0:
            X=Data(data, extra, refTime=self.opt['refTime'], period=self.opt['period'], timeStepUnit=self.opt['timeStepUnit'], timeStepSize=self.opt['timeStepSize'])
            X.fTarget = eval(self.data.fTargetStr)
            X.fData = eval(self.data.fDataStr)
            X.fSeasonCoef = self.data.fSeasonCoef
            X.normalization = self.data.normalization
        else:
            X = self.data
        
        # choose relevant leads
        tmp=lead-self.opt['leads']
        tmpZeroIdx = np.where(tmp==0)[0]
        if len(tmpZeroIdx)>0:
            toCompute=[tmpZeroIdx[0],]
        else:
            toCompute=[np.where(tmp==np.min(tmp[tmp>0]))[0][0],
                       np.where(tmp==np.max(tmp[tmp<0]))[0][0]]
            
        # run models
        leadSimulations = []
        leadTargets = []
        leadDates = []
        dates = None
        for i0 in toCompute:
            X.prepareTargets(self.opt['leads'][i0])
            X.prepareInputs(self.opt['leads'][i0])
            X.split(1)
            if dates==None:
                dates = X.getForDates(None).copy()
            wholePeriod = np.zeros((X.getForX(None).shape[1], len(self.__readyModels__[i0][0].opt['bands'])))
            notChanged = np.ones(wholePeriod.shape[0], dtype=np.bool)
            tmpTarget = np.empty((wholePeriod.shape[0],))*np.NaN
            for season in range(self.opt['seasons']):
                toPredict, seasonCoefs, seasonIdxs = X.getForX(season)
                toPredict = X.normalize(toPredict)[0]
                
                tmp = self.__readyModels__[i0][season].predict(np.transpose(toPredict))
                tmp = X.denormalize(y = tmp)[0]
                wholePeriod[seasonIdxs, :] = wholePeriod[seasonIdxs, :]+tmp*np.transpose(np.tile(seasonCoefs, (tmp.shape[1], 1)))
                toPredict, seasonCoefs, seasonIdxs = X.getForY(season)
                tmpTarget[seasonIdxs] = toPredict
                notChanged[seasonIdxs] = False
            wholePeriod[notChanged, :] = np.NaN
            leadSimulations.append(wholePeriod)
            leadTargets.append(tmpTarget)
            leadDates.append(X.getForDates(None))
        
        # sort bands and interpolate where needed
        bands = np.array(self.__readyModels__[0][0].getBands())
        for i0, s0 in enumerate(leadSimulations):
            s0 = processBands(s0, bands)
                        
        # interpolate results in the lead space
        if len(leadSimulations)==1:
            leadSimulations = leadSimulations[0]
            leadTargets = leadTargets[0]
        else:
            translation = np.abs(lead-self.opt['leads'][toCompute])
            weights = 1-translation/np.sum(translation)
            tmp0 = np.zeros_like(leadSimulations[0])
            tmp1 = np.zeros_like(leadTargets[0])
            tmp3 = np.ones_like(leadTargets[0], dtype=np.bool)
            idx = []
            idx0 = np.array([np.NaN if i0==None else i0 for i0 in X.__ismember__(leadDates[1], leadDates[0])])
            idx.append(idx0[np.logical_not(np.isnan(idx0))].astype(np.int))
            idx1 = np.array([np.NaN if i0==None else i0 for i0 in X.__ismember__(leadDates[0], leadDates[1])])
            idx.append(idx1[np.logical_not(np.isnan(idx1))].astype(np.int))
            tmp3[idx[0]] = False
            for i0, w0 in enumerate(weights):
                tmp0[idx[0], :] += leadSimulations[i0][idx[i0], :]*w0
                tmp1[idx[0]] += leadTargets[i0][idx[i0]]*w0
            leadSimulations = tmp0
            leadTargets = tmp1
            leadSimulations[tmp3, :] = np.NaN
            leadTargets[tmp3] = np.NaN
            
        # verify validity
        tmp = np.logical_and(np.logical_not(np.isnan(np.sum(leadSimulations, axis=1))), dates>=dateFrom)
        dates = dates[tmp]
        leadSimulations = leadSimulations[tmp, :]
        leadTargets = leadTargets[tmp]
        
        # compute training and validation
        traDates = self.data.dates[self.data.idxTra]
        traIdxs = [i0 for i0 in self.data.__ismember__(traDates, dates) if i0!=None]
        valDates = self.data.dates[self.data.idxVal]
        valIdxs = [i0 for i0 in self.data.__ismember__(valDates, dates) if i0!=None]
        
        # analyze performance
        traQQ = predictiveQQ(leadSimulations[traIdxs,], leadTargets[traIdxs], bands)
        traPerformance = metrics(traQQ[0], traQQ[1], leadSimulations[traIdxs,], self.__readyModels__[0][0].bandBounds)
        
        valQQ = predictiveQQ(leadSimulations[valIdxs,], leadTargets[valIdxs], bands)
        valPerformance = metrics(valQQ[0], valQQ[1], leadSimulations[valIdxs,], self.__readyModels__[0][0].bandBounds)
        
        return {'dates': dates, 'simulations': leadSimulations, 'bands': bands, 'targets': leadTargets,
                 'traDates': dates[traIdxs], 'traPerformance': traPerformance, 'valPerformance': valPerformance,
                 'traQQ': traQQ, 'valQQ': valQQ}
    
    def evalFun(self, x, data=[]):
        # error
        self.annToOptimize.setWeights(x)
        if len(data)==0:
            tmp = self.annToOptimize.compute()
        else:
            tmp = self.annToOptimize.compute(data)
        return tmp

    def regFun(self, w):
        # regularization
        if len(w.shape)==1:
            w = np.expand_dims(w, 0)
        # reg = np.sqrt(np.sum(np.square(w[:, np.where(annToOptimize.getWeightsToRegularize())[0]]), axis=1)) #L2
        reg = np.sum(np.abs(w[:, np.where(self.annToOptimize.getWeightsToRegularize())[0]]), axis=1) # L1
        return self.opt['regularization']*reg
    
    def getTrainingDates(self):
        return {'dates': self.data.dates[self.data.idxTra], 'logical': self.data.idxTra}
    
    def getSeasons(self, num=100):
        seasons = np.empty((num, len(self.data.fSeasonCoef)))
        for i0, f0 in enumerate(self.data.fSeasonCoef):
            seasons[:,i0] = f0(np.linspace(0, 1, num))
        return seasons
    
    def getPerformance(self, lead, train=False):
        idx = np.where(self.opt['leads']==lead)[0]
        
        self.data.prepareInputs(lead)
        wholePeriod = np.zeros((self.data.X.shape[1],len(self.__readyModels__[idx][0].opt['bands'])))
        fullTargets = np.zeros(self.data.X.shape[1])
        valid = np.zeros(self.data.X.shape[1], dtype=np.bool)
        for season in range(self.opt['seasons']):
            if train:
                toPredict, seasonCoefs, seasonIdxs = self.data.getTraX(season)
                targets = self.data.getTraY(season)[0]
            else:
                toPredict, seasonCoefs, seasonIdxs = self.data.getValX(season)
                targets = self.data.getValY(season)[0]
            toPredict = self.data.normalize(toPredict)[0]
            
            tmp = self.__readyModels__[idx][season].predict(np.transpose(toPredict))
            tmp = self.data.denormalize(y = tmp)[0]
            wholePeriod[seasonIdxs,:] = wholePeriod[seasonIdxs,:]+tmp*np.transpose(np.tile(seasonCoefs, (tmp.shape[1],1)))
            fullTargets[seasonIdxs] = fullTargets[seasonIdxs]+targets*seasonCoefs
            valid[seasonIdxs] = 1
            
        tmpSimulations = self.__readyModels__[idx][0].processBands(wholePeriod[valid, :])
        uniform, pValues = self.__readyModels__[idx][0].predictiveQQ(tmpSimulations, targets=fullTargets[valid])
        alpha, xi, piRel = self.__readyModels__[idx][0].metrics(uniform, pValues, tmpSimulations)
        return {'pValues':pValues, 'uniform':uniform, 'alpha':alpha, 'xi':xi, 'pi':piRel}
    
    def save(self, filePath):
        self.data.fData = None
        self.data.fTarget = None
        self.data.fSeasonCoef = None
        
        toSave = self.__dict__
        toSave.pop('annToOptimize')
        toSave.pop('errorOpenCL')
        
        print(self.__readyModels__[0][0].__dict__.keys())
        for i0 in range(len(self.__readyModels__)):
            for i1 in range(len(self.__readyModels__[i0])):
                self.__readyModels__[i0][i1].__dict__.pop('simulations')
                self.__readyModels__[i0][i1].__dict__.pop('velocities')
                self.__readyModels__[i0][i1].__dict__.pop('jointVelocities')
                self.__readyModels__[i0][i1].__dict__.pop('trainData')
                self.__readyModels__[i0][i1].__dict__.pop('targets')
                self.__readyModels__[i0][i1].__dict__.pop('frontLvls')
                self.__readyModels__[i0][i1].__dict__.pop('gBestIdxs')
                self.__readyModels__[i0][i1].__dict__.pop('pBestIdxs')
        print(self.__readyModels__[0][0].__dict__.keys())
        
        with open(filePath, 'wb') as file:
            pickle.dump(toSave, file)
            
        self.data.fData = eval(self.data.fDataStr)
        self.data.fSeasonCoef = [interp1d(x0, y0, kind='linear') for x0, y0 in self.data.fSeasonCoefData]
              
    def load(self, filePath, openClPlatform=None, openClDevice=None):
        with open(filePath, 'rb') as file:
            tmp = pickle.load(file)
            self.__dict__.update(tmp)
        self.data.fData = eval(self.data.fDataStr)
        self.data.fTarget = eval(self.data.fTargetStr)
        self.data.fSeasonCoef = [interp1d(x0, y0, kind='linear') for x0, y0 in self.data.fSeasonCoefData]
        
        # initialize openCL objects
        XTrain = np.transpose(self.data.getTraX(season=0)[0])
        #=======================================================================
        # yTrain = np.transpose(self.data.getTraY(season=0)[0])
        #=======================================================================
        
        if openClPlatform!=None:
            self.opt['openClPlatform'] = openClPlatform
        if openClDevice!=None:
            self.opt['openClDevice'] = openClDevice
        #=======================================================================
        # self.annToOptimize=ann(XTrain, nodes=self.opt['nodes'], openCL=True, workGroup=(64, 4), platform=self.opt['openClPlatform'], deviceType=self.opt['openClDevice'], activationFunction=self.opt['activationFunction'])
        # self.errorOpenCL=errorMetrics(yTrain, stride=512, workGroup=(1, 16), platform=self.opt['openClPlatform'], deviceType=self.opt['openClDevice'], verbose=0)
        #=======================================================================
        # start ann object
        self.annToOptimize=ann(XTrain, nodes=self.opt['nodes'], openCL=True, workGroup=(64, 4), deviceType=self.opt['openClDevice'],
                               platform=self.opt['openClPlatform'], activationFunction=self.opt['activationFunction'], verbose=0,
                               lowerThreshold=self.opt['lowerThreshold'])        
        
        # start error object
        #=======================================================================
        # self.errorOpenCL=errorMetrics(yTrain, self.weights, stride=512, workGroup=(1, 16), deviceType=self.opt['openClDevice'], platform=self.opt['openClPlatform'], verbose=0, errorFunction=self.opt['errorFunction'])
        #=======================================================================
        
        # bind evalFunction
        for l0 in self.__readyModels__:
            for s0 in l0:
                s0.evalFun=self.evalFun
