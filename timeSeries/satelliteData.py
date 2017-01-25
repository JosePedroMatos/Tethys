'''
Created on Jun 16, 2016

@author: Jose Pedro Matos
'''
import datetime as dt
import numpy as np
import matplotlib.pyplot as plt
import os
import warnings
import ntpath
import tempfile
import gzip
import shutil
import sys
import re
import geojson
import json
import struct

from urllib import request
from multiprocessing.dummy import Pool as ThreadPool
from netCDF4 import Dataset, num2date, date2num #@UnresolvedImport
from dateutil.relativedelta import relativedelta
from astropy.io.ascii.tests.test_connect import files
from celery import current_task

class SatelliteData(object):
    '''
    classdocs
    '''
    filePrefix = 'unknown'
    precision = np.single
    significantDigits = None
    downloadFailThreshold = 50000
    
    productSite = 'unknown'
    downloadSite = 'unknown'
    description = 'none'
    timestep = {}
    units = 'unknown'

    def __init__(self, dataFolder, downloadFolder, username=None, password=None):
        '''
        Constructor
        '''
        self.downloadFolder = downloadFolder
        self.dataFolder = dataFolder
        self.username = None
        self.password = None
        
        if not os.path.isdir(self.dataFolder):
            os.makedirs(self.dataFolder)
        if not os.path.isdir(self.downloadFolder):
            os.makedirs(self.downloadFolder)
    
        self._listData()
    
    

    def downloadList(self, dateIni, dateEnd):
        '''
        abstract method
        
        Returns a tuple defining files to be downloaded. It should contain:
            a list of file names on disk and
            a list of urls for download.
        '''
        pass
    
    def downloadedDates(self, fileType):
        '''
        abstract method
        
        Returns a tuple containing:
            a list of files in folder that are have a given extension and
            a list of dates corresponding to each file
        '''   
        pass
    
    def importData(self, fileName):
        '''
        abstract method
        
        Returns:
        '''   
        pass

    

    def getData(self, dateIni, dateEnd):
        # load data
        self.process(dateIni=dateIni, dateEnd=dateEnd, download=False, read=False)

        # export data
        if 'loaded' in self.__dict__.keys():
            return self.loaded
        else:
            return {}
    
    def getDataForJSON(self, dateIni, dateEnd, returnData=True, returnInfo=True):
        # get data
        data = self.getData(dateIni, dateEnd)
        idxs = np.where((np.nansum(data['data']+1, axis=0)!=0).ravel())[0]
        idxsList = idxs.tolist()

        # trim data
        if len(data)>0: 
            data['dates'] = [dt.isoformat() for dt in data['dates']]
            data['missing'] = data['missing'].tolist()
            
            if returnInfo:
                data['lon'] = data['lon'].tolist()
                data['lat'] = data['lat'].tolist()
                data['idxs'] = idxsList
            else:
                data.pop('lon', None)
                data.pop('lat', None)
                data.pop('idxs', None)
            
            if returnData:
                tmp = []
                for i0 in range(data['data'].shape[0]):
                    tmpValidData = data['data'][i0,:,:].ravel()[idxsList]
                    tmpValidData[np.isnan(tmpValidData)] = -999;
                    tmpPositiveIdxs = np.where(tmpValidData!=0)[0]
                    tmp.append({'idxs': idxs[tmpPositiveIdxs].tolist(), 'values': tmpValidData[tmpPositiveIdxs].tolist()})
                data['data'] = tmp
            else:
                data.pop('data', None)
            
            return data
        else:
            return {}

    def download(self, dateIni, dateEnd):
              
        # Call data-specific method to define file names and download urls
        fileList, urlList = self.downloadList(dateIni, dateEnd)
    
        # File list
        toDownload = []
        for i0 in range(len(fileList)):
            if not os.path.isfile(fileList[i0]):
                toDownload.append((fileList[i0], urlList[i0]))
        
        ctr = 0
        failed = []
        notFound = []
        while ctr==0 or (ctr < 4 and len(failed)>0):
            # Download files
            downloadSizes = []
            if len(toDownload)>0:
                pool = ThreadPool(self.downloadThreads)
                toDownloadSplit = [toDownload[i0:i0+self.downloadThreads] for i0 in range(0, len(toDownload), self.downloadThreads)]
                tmpBarLen = len(toDownloadSplit)
                if ctr==0:
                    print('Downloading files:')
                else:
                    warnings.warn(str(len(failed)) + ' failed download(s)...', UserWarning)
                    print('Reattempting failed downloads (' + str(ctr) + '):')
                    
                for i0, l0 in enumerate(toDownloadSplit):
                    self._printProgress(i0, tmpBarLen, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
                    try:
                        current_task.update_state(state='PROGRESS', meta={'message': ('warning', 'Downloading files (%s to %s)' % (os.path.split(l0[0][1])[1], os.path.split(l0[-1][1])[1])),
                                                                          'state': 'PROGRESS'})
                    except Exception:
                        pass
                    tmp = pool.map(self._downloadFile, l0)
                    downloadSizes.extend(tmp)
                self._printProgress(tmpBarLen, tmpBarLen, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
                pool.close()
                pool.join()
            
            # Check sizes and delete failed ones
            failed = []
            for i0, s0 in enumerate(downloadSizes):
                if s0<0:
                    if os.path.isfile(toDownload[i0][0]):
                        os.remove(toDownload[i0][0])
                    notFound.append((toDownload[i0][0], toDownload[i0][1]))
                elif s0<self.downloadFailThreshold:
                    if os.path.isfile(toDownload[i0][0]):
                        os.remove(toDownload[i0][0])
                    failed.append((toDownload[i0][0], toDownload[i0][1]))
            
            toDownload = failed
            ctr += 1
        
        if len(failed)>0:
            warnings.warn('permanently failed download(s). Re-run the download method and consider reducing the number of threads:\n' + str([f0 for f0 in failed[0]]), UserWarning)
    
        if len(notFound)>0:
            warnings.warn('download file(s) not found. The files may not be available yet:\n' + str([f0 for f0 in notFound[0]]), UserWarning)
    
        # return halt signal
        if len(urlList)>0 and len(notFound)==len(urlList):
            return True
        else:
            return False
    
    def readDownloads(self, dates, geometryFile=None, geometryStr=''):
        '''
        Reads the downloaded files using methods specific to the subclasses   
        '''
        
        # retrieve a list of filenames and dates
        filePaths, fileDates = self.downloadedDates()
        
        # find which dates are covered by files
        existingFiles = []
        existingDates = []
        for d0 in dates:
            if d0 in fileDates:
                idx = fileDates.index(d0)
                existingFiles.append(filePaths[idx])
                existingDates.append(fileDates[idx])
        
        # create a temporary folder
        self.tmpFolder = tempfile.mkdtemp(prefix='tmp__', dir=self.dataFolder)
        
        try:
            # Interpret first file in the list and create the downloaded dictionary
            self.downloaded = {}
            self.downloaded['dates'] = dates
            tmpData, self.downloaded['lat'], self.downloaded['lon']=self.importData(existingFiles[0])
            
            # Ensure that records fall within the [-180, 180] and [-90, 90] ranges
            self.downloaded['lon'] = np.mod(self.downloaded['lon'], 360)
            self.downloaded['lon'] = np.mod(self.downloaded['lon'] + 360, 360)
            self.downloaded['lon'][self.downloaded['lon']>180] = self.downloaded['lon'][self.downloaded['lon']>180]-360
        
            self.downloaded['lat'] = np.mod(self.downloaded['lat'], 180)
            self.downloaded['lat'] = np.mod(self.downloaded['lat'] + 180, 180)
            self.downloaded['lat'][self.downloaded['lat']>90] = self.downloaded['lat'][self.downloaded['lat']>90]-180
            
            # Store data
            self.downloaded['data']=np.empty((len(dates), tmpData.shape[1], tmpData.shape[2]), dtype=self.precision)
            self.downloaded['data'][:] = np.nan
            self.downloaded['missing'] = np.ones((len(dates),), dtype=np.bool)   
                        
            self.downloaded['data'][0, :,:]=tmpData
            self.downloaded['missing'][0] = False
                
            # Interpret all the remaining files
            existingFiles.pop(0)
            existingDates.pop(0)
            
            threads = self.readThreads
            with ThreadPool(threads) as pool:
                toInterpretSplit = [existingFiles[i0:i0+threads] for i0 in range(0, len(existingFiles), threads)]
                tmpBarLen = len(toInterpretSplit)
                imported = []
                if tmpBarLen>0:
                    print('Reading files:')
                    for i0, l0 in enumerate(toInterpretSplit):
                        self._printProgress(i0, tmpBarLen, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
                        try:
                            current_task.update_state(state='PROGRESS', meta={'message': ('warning', 'Reading files (%s to %s)' % (os.path.split(l0[0])[1], os.path.split(l0[-1])[1])),
                                                                              'state': 'PROGRESS'})
                        except Exception:
                            pass
                        imported.extend(pool.map(self.importData, l0))
                    self._printProgress(tmpBarLen, tmpBarLen, prefix = 'Progress:', suffix = 'Complete', barLength = 50)

        except Exception as ex:
            raise(ex)
        finally:
            #===================================================================
            # os.rmdir(self.tmpFolder)
            #===================================================================
            shutil.rmtree(self.tmpFolder)
        
        # store interpretations
        for i0, t0 in enumerate(imported):
            idx = dates.index(existingDates[i0])
            self.downloaded['data'][idx, :,:] = t0[0]
            self.downloaded['missing'][idx] = False
            
        # define indexes
        if geometryStr!='':
            self.setGeometryInfo(geometryStr)
        elif 'geometryInfo' not in self.__dict__.keys():
            self.geometryInfo = self._getGeometyIdxs(lat=self.downloaded['lat'], lon=self.downloaded['lon'], filePath=geometryFile)
        
        # crop data
        self.downloaded['lat'] = self.geometryInfo['lat']
        self.downloaded['lon'] = self.geometryInfo['lon']
        tmp = np.empty((len(dates), self.geometryInfo['lat'].shape[0], self.geometryInfo['lon'].shape[0]), dtype=self.precision)
        tmp[:]  = np.nan
        tmp[:, self.geometryInfo['idxReduced'][0], self.geometryInfo['idxReduced'][1]] = self.downloaded['data'][:, self.geometryInfo['idxOriginal'][0], self.geometryInfo['idxOriginal'][1]]
        self.downloaded['data'] = tmp
    
    def update(self, download=True, downloadThreads=3, readThreads=1, geometryFile=None, geometryStr=''):
        year = max(self.netCDFDict.keys())
        month = max(self.netCDFDict[year].keys())
        lastRecord = self.store(dateIni=dt.datetime(year, month, 1), dateEnd=dt.datetime.now(), download=True, downloadThreads=downloadThreads, readThreads=readThreads, geometryFile=geometryFile, geometryStr=geometryStr)
        
        return lastRecord
    
    def store(self, dateIni=dt.datetime(1998, 1, 1, 0), dateEnd=dt.datetime.now(), download=True, downloadThreads=3, readThreads=1, geometryFile=None, geometryStr=''):
        
        self.downloadThreads = downloadThreads
        self.readThreads = readThreads
        
        dates = self.filePeriod(dateIni=dateIni, dateEnd=dateEnd)
        
        monthIdxs = np.array(self._splitByMonth(dates))
        tmp = [np.where(monthIdxs==m0)[0][0] for m0 in np.unique(monthIdxs)]
        sortedIdxs = sorted(range(len(tmp)), key=lambda i0: tmp[i0])
        
        tmpPeriods = len(sortedIdxs)
        for i0, m0 in enumerate(sortedIdxs):
            
            tmp = np.where(monthIdxs==m0)[0]
            monthDates = np.array(dates)[tmp]
            dateIni = np.min(monthDates)
            dateEnd = np.max(monthDates)
            
            print('Storing %02u/%04u...' % (dateIni.month, dateIni.year))
            try:
                current_task.update_state(state='PROGRESS', meta={'message': ('warning', 'Storing data: %02u.%04u' % (dateIni.month, dateIni.year)),
                                                                  'progress': i0/tmpPeriods,
                                                                  'state': 'PROGRESS'})
            except Exception:
                pass
            halt = self.process(dateIni=dateIni, dateEnd=dateEnd, download=download, geometryFile=geometryFile, geometryStr=geometryStr)
            if not halt:
                self.save()
            
            lastRecord = self.loaded['dates'][np.where(False==self.loaded['missing'])[0][-1]]
            
            self.__dict__.pop('loaded', None)
            if 'downloaded' in self.__dict__.keys():
                self.__dict__.pop('downloaded', None)
                
            self._listData()
        
        return lastRecord
    
    def process(self, dateIni=dt.datetime(1998, 1, 1, 0), dateEnd=dt.datetime.now(), download=True, read=True, geometryFile=None, geometryStr=''):
        '''
        Reads the downloaded files and processes them by interpolating missing data and aggregating it to the desired timestep.
        '''
        
        # Load existing NetCDFs (to self.loaded)
        self.load(dateIni, dateEnd)
        
        # Download if needed
        if download:
            halt = self.download(dateIni=dateIni, dateEnd=dateEnd)
            if halt:
                return halt
        
        # Process downloads
        if read:
            dateList = self._notProcessed(self.filePeriod(dateIni=dateIni, dateEnd=dateEnd))
            if len(dateList)>0:
                self.readDownloads(dateList, geometryFile=geometryFile, geometryStr=geometryStr)
            
            # Check if loaded and downloaded are compatible
            if 'loaded' in self.__dict__:
                lat = self.loaded['lat']
                lon = self.loaded['lon']
                if 'downloaded' in self.__dict__:
                    if not (lat==self.downloaded['lat']).all() or not (lon==self.downloaded['lon']).all():
                        raise Exception('Stored and downloaded coordinates do not match.')
            else:
                lat = self.downloaded['lat']
                lon = self.downloaded['lon']
            
            #===================================================================
            # # Interpolates the missing values in the matrix. The interpolation is made just on the time dimension
            # # Loop through all x - axis 0 of the matrix
            # if 'downloaded' in self.__dict__:
            #     tmplat = self.downloaded['data'].shape[1]
            #     print('Interpolating missing data:')
            #     for i0 in range(self.downloaded['data'].shape[1]):
            #         self._printProgress(i0, tmplat, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
            #         # Loop through all y - axis 1 of the matrix
            #         for i1 in range(self.downloaded['data'].shape[2]):
            #             # Temporary array with all precipitation values (z axis) for a given lat and lon (x and y axis)
            #             tmp = np.squeeze(self.downloaded['data'][:, i0, i1])
            #             nans = np.isnan(tmp)
            #             tmpNanSum = np.sum(nans)
            #             if tmpNanSum>0 and tmpNanSum!=nans.shape[0]:
            #                 # Creates an array with the size of the temporary but with values that correspond to the axis [0,1,2..., n]
            #                 idx = np.arange(len(tmp))
            #                 valid = np.logical_not(nans)
            #                 # The interpolate function requires the index of the points to interpolate (idx[nans]),
            #                 # the index of the points with valid values (idx[valid]) and
            #                 # the valid values tha will be used to interpolate (tmp[valid])
            #                 self.downloaded['data'][nans, i0, i1]=np.interp(idx[nans], idx[valid], tmp[valid])
            #     self._printProgress(tmplat, tmplat, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
            #===================================================================
            
            # Join downloads and stored data (loaded)
            if 'loaded' not in self.__dict__.keys():
                dates = self.filePeriod(dateIni=dateIni, dateEnd=dateEnd)
                self.loaded = {}
                self.loaded['lat'] = lat
                self.loaded['lon'] = lon
                self.loaded['dates'] = dates
                self.loaded['data'] = np.empty((len(dates), len(lat), len(lon)), dtype=self.precision)
                self.loaded['data'][:] = np.nan                                 
                self.loaded['missing'] = np.ones((len(dates),), dtype=np.bool)
                
            if 'downloaded' in self.__dict__.keys():
                idxsLoaded = self.ismember(self.downloaded['dates'], self.loaded['dates'])
                idxsDownloaded = self.ismember(self.loaded['dates'], self.downloaded['dates']) 
                self.loaded['data'][idxsLoaded, :, :] = self.downloaded['data'][idxsDownloaded, :, :]
                self.loaded['missing'][idxsLoaded] = self.downloaded['missing'][idxsDownloaded]
    
    def plot(self):
        mean=np.flipud(np.nanmean(self.loaded['data'], 0)*365*8)
        ax = plt.matshow(mean)
        plt.colorbar(ax)
        plt.show(block=True)    
    
    def save(self, overwriteAll=False, overwriteIncomplete=True):
        '''
        Splits the data in blocks of 1 month and stores them in NetCDF files
        '''
        tmpDates = np.array(self.loaded['dates'])
        
        monthIdxs = np.array(self._splitByMonth(self.loaded['dates']))
        uniqueMonthIdxs = np.unique(monthIdxs)
        
        print('Saving NetCDFs:')
        tmpPeriods = len(uniqueMonthIdxs)
        for c0, i0 in enumerate(uniqueMonthIdxs):
            self._printProgress(c0, tmpPeriods, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
            
            tmp = np.where(monthIdxs==i0)[0]
            monthDates = tmpDates[tmp]
            
            if not overwriteAll:
                if monthDates[0].year in self.netCDFDict.keys() and monthDates[0].month in self.netCDFDict[ monthDates[0].year].keys():
                    if self.netCDFDict[monthDates[0].year][monthDates[0].month][1]==True:
                        # prevents complete files from being overwritten
                        continue
                    else:
                        # incomplete file
                        if not overwriteIncomplete:
                            # prevents overwriting
                            continue
                
            monthData = self.loaded['data'][tmp, :, :]
            monthMissing = self.loaded['missing'][tmp]
            rootgrp = Dataset(os.path.join(self.dataFolder, self.filePrefix + '_%04d.%02d.nc' % (monthDates[0].year, monthDates[0].month)), 'w', format='NETCDF4', clobber=True)
            
            time = rootgrp.createDimension('time', None)
            lat = rootgrp.createDimension('lat', monthData.shape[1])
            lon = rootgrp.createDimension('lon', monthData.shape[2])
            
            times = rootgrp.createVariable('time', np.double, dimensions=('time',), zlib=True)
            lats = rootgrp.createVariable('lat', np.double, dimensions=('lat',), zlib=True)
            lons = rootgrp.createVariable('lon', np.double, dimensions=('lon',), zlib=True)
            precips = rootgrp.createVariable('precipitation', self.precision, dimensions=('time', 'lat', 'lon'), zlib=True, least_significant_digit=self.significantDigits)  
            missing = rootgrp.createVariable('missing', np.int8, dimensions=('time'), zlib=True)          
            
            rootgrp.description = 'Rainfall data (' + self.filePrefix + ')'
            rootgrp.history = 'Created the ' + str(dt.datetime.now())
            lats.units = 'degrees of the center of the pixel (WGS84)'
            lons.units = 'degrees of the center of the pixel (WGS84)'
            times.units = "hours since 0001-01-01 00:00:00.0"
            times.calendar = 'standard'
            precips.units = 'mm of rain accumulated over a 3-hour interval centered on the time reference [-1.5, +1.5]'
            
            # Check completeness
            monthDates[0] + relativedelta(months=1)
            tmp = self.filePeriod(dateIni=monthDates[-1] - relativedelta(months=1), dateEnd=monthDates[0] + relativedelta(months=1))
            tmp = [dt0 for dt0 in tmp if dt0.month==monthDates[0].month and dt0.year==monthDates[0].year]
            if len(self.ismember(tmp, monthDates)) == len(tmp):
                # The month is complete
                if np.all(np.logical_not(monthMissing)):
                    rootgrp.complete = 1
                else:
                    rootgrp.complete = 0
            else:
                # The month is not complete
                rootgrp.complete = 0
            
            if rootgrp.complete==0:
                warnings.warn('    netCDF not complete (' + self.filePrefix + '_%04d.%02d.nc' % (monthDates[0].year, monthDates[0].month) + ').', UserWarning)
            
            lats[:] = self.loaded['lat']   
            lons[:] = self.loaded['lon']
            times[:] = date2num(monthDates, units=times.units, calendar=times.calendar)
            precips[:, :, :] = monthData
            missing[:] = monthMissing
            
            rootgrp.close()
            
        self._printProgress(tmpPeriods, tmpPeriods, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
    
    def load(self, dateIni=dt.datetime(1998, 1, 1, 0), dateEnd=dt.datetime.now()):
        '''
        Loads the data from 1-month NetCDF files into a numpy array
        '''
        dates = self.filePeriod(dateIni=dateIni, dateEnd=dateEnd)

        yearMonth = list(set([(dt.year, dt.month) for dt in dates]))
         
        print('Attempting to load NetCDFs:')
        tmpPeriods = len(yearMonth)
        data = None
        for i0, t0 in enumerate(yearMonth):
            self._printProgress(i0, tmpPeriods, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
            if t0[0] in self.netCDFDict.keys() and t0[1] in self.netCDFDict[t0[0]].keys():
                tmp = self._loadNetCDF(os.path.join(self.dataFolder, self.netCDFDict[t0[0]][t0[1]][0]))
                self.netCDFDict[t0[0]][t0[1]][1] = tmp['complete']
                if 'loaded' not in self.__dict__:
                    self.loaded = {}
                    self.loaded['dates'] = dates
                    
                    self.loaded['lat'] = tmp['lat']
                    self.loaded['lon'] = tmp['lon']
                    self.loaded['data'] = np.empty((len(dates), len(self.loaded['lat']), len(self.loaded['lon'])), dtype=self.precision)
                    self.loaded['data'][:] = np.nan
                    self.loaded['missing'] = np.ones((len(dates),), dtype=np.bool)        
                idxsLoaded = np.array(self.ismember(tmp['dates'], self.loaded['dates']))
                idxsTmp = np.array(self.ismember(self.loaded['dates'], tmp['dates']))               
                self.loaded['data'][idxsLoaded, :, :] = tmp['data'][idxsTmp, :, :]
                self.loaded['missing'][idxsLoaded] = tmp['missing'][idxsTmp]
        self._printProgress(tmpPeriods, tmpPeriods, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
    
    def getGeometryInfo(self):
        if 'geometryInfo' not in self.__dict__.keys():
            return ''
        else:
            tmp = {}
            tmp['lat'] = self.geometryInfo['lat'].tolist()
            tmp['lon'] = self.geometryInfo['lon'].tolist()
            tmp['idxOriginal'] = (self.geometryInfo['idxOriginal'][0].tolist(), self.geometryInfo['idxOriginal'][1].tolist())
            tmp['idxReduced'] = (self.geometryInfo['idxReduced'][0].tolist(), self.geometryInfo['idxReduced'][1].tolist())
            return json.dumps(tmp)
    
    def setGeometryInfo(self, jsonStr):
        if jsonStr != '':
            tmp = json.loads(jsonStr)
            tmp['lat'] = np.array(tmp['lat'])
            tmp['lon'] = np.array(tmp['lon'])
            tmp['idxOriginal'] = (np.array(tmp['idxOriginal'][0]), np.array(tmp['idxOriginal'][1]))
            tmp['idxReduced'] = (np.array(tmp['idxReduced'][0]), np.array(tmp['idxReduced'][1]))
            self.geometryInfo = tmp
    
    def filePeriod(self, dateIni=dt.datetime(1998, 1, 1, 0), dateEnd=dt.datetime.now()):
        # Define the period of time to retrieve files and creates a list of dates
        return [d0.astype(object) for d0 in np.arange(dateIni, dateEnd+dt.timedelta(**self.timestep), dt.timedelta(**self.timestep))]

    def aggregate(self, dates, geometryStr=None, missingTolerance=0.1):
        missingMax = round(len(json.loads(geometryStr)['lat'])*len(json.loads(geometryStr)['lon'])-len(json.loads(geometryStr)['idxReduced'][0])*(1-missingTolerance))
        
        values = np.empty_like(dates, dtype=np.double)*np.NaN
        print('Aggregating:')
        tmpPeriods = len(dates)
        openFileName = None
        for i0, d0 in enumerate(dates):
            year = d0.year
            month = d0.month
            if np.mod(i0,1000)==0:
                self._printProgress(i0, tmpPeriods, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
                try:
                    current_task.update_state(state='PROGRESS', meta={'message': ('warning', 'Aggregating %02u.%04u' % (month, year)),
                                                                      'progress': i0/tmpPeriods,
                                                                      'state': 'PROGRESS'})
                except Exception as ex:
                    print(str(ex))
            if year in self.netCDFDict.keys() and month in self.netCDFDict[year].keys():
                if openFileName != self.netCDFDict[year][month][0]:
                    openFileName = self.netCDFDict[year][month][0]
                    openFileData = self._loadNetCDF(os.path.join(self.dataFolder, openFileName))
                    
                idx = np.array(self.ismember((dates[i0],), openFileData['dates']))
                if np.sum(np.isnan(openFileData['data'][idx, :, :]))<=missingMax:
                    values[i0] = np.nanmean(openFileData['data'][idx, :, :])
                else:
                    values[i0] = np.NaN
                
        self._printProgress(tmpPeriods, tmpPeriods, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
        
        return values

    def _getGeometyIdxs(self, lat, lon, filePath=None):
        
        if filePath!=None:
            # load geometry
            with open(filePath, 'r') as myfile:
                geojsonStr=myfile.read()
            obj = geojson.loads(geojsonStr)
            
            # compute logical matrix of valid pixels
            chosenPixels = np.zeros((len(lat), len(lon)),dtype=np.bool)
            for f0 in obj['features']:
                if f0['type'] != 'Feature':
                    continue
                
                if f0['geometry']['type'] == 'Polygon':
                    g0 = f0['geometry']['coordinates']
                    tmp = self._intersection(lon, lat, [i0[0] for i0 in g0[0]], [i0[1] for i0 in g0[0]])
                    if len(g0)>1:
                        for i0 in range(1, len(g0)):
                            tmp = np.logical_and(tmp, np.logical_not(self._intersection(lon, lat, [i0[0] for i0 in g0[i0]], [i0[1] for i0 in g0[i0]])))
                    chosenPixels = np.logical_or(chosenPixels, tmp)
                    
                elif f0['geometry']['type'] == 'MultiPolygon':
                    tmp = np.zeros((len(lat), len(lon)),dtype=np.bool)
                    for g0 in f0['geometry']['coordinates']:
                        tmp = np.logical_or(tmp, self._intersection(lon, lat, [i0[0] for i0 in g0[0]], [i0[1] for i0 in g0[0]]))
                        if len(g0)>1:
                            for i0 in range(1, len(g0)):
                                tmp = np.logical_and(tmp, np.logical_not(self._intersection(lon, lat, [i0[0] for i0 in g0[i0]], [i0[1] for i0 in g0[i0]])))
                    chosenPixels = np.logical_or(chosenPixels, tmp)
                    
            #=======================================================================
            # plt.imshow(np.flipud(chosenPixels), cmap='Greys',  interpolation='nearest')
            #=======================================================================
            
            # get indexes to retrieve information
            geometryInfo = {}
            tmp = np.where(chosenPixels!=0)
            geometryInfo['lat'] = lat[np.min(tmp[0]):np.max(tmp[0])+1]
            geometryInfo['lon'] = lon[np.min(tmp[1]):np.max(tmp[1])+1]
            geometryInfo['idxOriginal'] = np.where(chosenPixels)
            geometryInfo['idxReduced'] = np.where(chosenPixels[np.min(tmp[0]):np.max(tmp[0])+1, np.min(tmp[1]):np.max(tmp[1])+1])
        else:
            geometryInfo = {}
            geometryInfo['lat'] = lat
            geometryInfo['lon'] = lon
            tmpLat = np.repeat(np.expand_dims(range(len(lat)), 1), len(lon), axis=1)
            tmpLon = np.repeat(np.expand_dims(range(len(lon)), 0), len(lat), axis=0)
            geometryInfo['idxOriginal'] = (tmpLat.ravel(), tmpLon.ravel())
            geometryInfo['idxReduced'] = geometryInfo['idxOriginal']
        
        return geometryInfo
    
    def _intersection(self, pointsX, pointsY, borderX, borderY):
        print('Processing geometry:')
        
        pixels = len(pointsX) * len(pointsY)
        segments = len(borderX)-1
        
        maxBorderY = max(borderY)
        maxBorderX = max(borderX)
        minBorderY = min(borderY)
        minBorderX = min(borderX)
        
        #=======================================================================
        # # Make sure all data is computed within the same range
        # pointsX = np.mod(pointsX, 360)
        # pointsX = np.mod(pointsX + 360, 360)
        # pointsX[pointsX>180] = pointsX[pointsX>180]-360
        # 
        # pointsY = np.mod(pointsY, 180)
        # pointsY = np.mod(pointsY + 180, 180)
        # pointsY[pointsY>90] = pointsY[pointsY>90]-180
        #=======================================================================
        
        # Defining matrices for calculation
        pointsX = np.expand_dims(pointsX, 1)
        pointsY = np.expand_dims(pointsY, 0)
        
        pixelBaseX = np.repeat(pointsX, pointsY.shape[1], axis=1).ravel()
        pixelBaseY = np.repeat(pointsY, pointsX.shape[0], axis=0).ravel()
        
        validBoolX = np.logical_and(pixelBaseX<=maxBorderX, pixelBaseX>=minBorderX)
        validBoolY = np.logical_and(pixelBaseY<=maxBorderY, pixelBaseY>=minBorderY)
        validBool = np.logical_and(validBoolX, validBoolY)
        
        L = np.zeros((pixels, segments), dtype=np.bool)
        #=======================================================================
        # R = np.empty((np.sum(validBool), segments))
        #=======================================================================
        pixelRedX = pixelBaseX[validBool]
        pixelRedY = pixelBaseY[validBool]
        x2 = 9999
        y2 = 9999
        #=======================================================================
        # a = (pixelBaseX*y2-pixelBaseY*x2)
        # d = (pixelBaseX-x2)
        # e = (pixelBaseY-y2)
        #=======================================================================
        a = (pixelRedX*y2-pixelRedY*x2)
        d = (pixelRedX-x2)
        e = (pixelRedY-y2)
        for i0 in range(segments):
            # TODO: extend to cases where the border goes beyond [-180, 180]
            if np.mod(i0, 20)==0:
                self._printProgress(i0, segments-1, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
                try:
                    current_task.update_state(state='PROGRESS', meta={'message': ('warning', 'Computing geometry'),
                                                                      'progress': i0/(segments-1),
                                                                      'state': 'PROGRESS'})
                except Exception:
                    pass
            x3 = borderX[i0]
            y3 = borderY[i0]
            x4 = borderX[i0+1]
            y4 = borderY[i0+1]
            
            # Computing intersection coordinates
            b = (x3*y4-y3*x4)
            c = d*(y3-y4)-e*(x3-x4)
            
            px = (a*(x3-x4)-d*b)/c
            py = (a*(y3-y4)-e*b)/c
            
            # Bounding intersections to the real lines
            #===================================================================
            # lx = np.logical_and(
            #                     px>=pixelBaseX,
            #                     np.logical_or(
            #                                   np.logical_and(px<=x3+1E-6, px>=x4-1E-6),
            #                                   np.logical_and(px<=x4+1E-6, px>=x3-1E-6)))
            # ly = np.logical_and(
            #                     py>=pixelBaseY,
            #                     np.logical_or(
            #                                   np.logical_and(py<=y3+1E-6, py>=y4-1E-6),
            #                                   np.logical_and(py<=y4+1E-6, py>=y3-1E-6)))
            #===================================================================
            lx = np.logical_and(
                                px>=pixelRedX,
                                np.logical_or(
                                              np.logical_and(px<=x3+1E-6, px>=x4-1E-6),
                                              np.logical_and(px<=x4+1E-6, px>=x3-1E-6)))
            ly = np.logical_and(
                                py>=pixelRedY,
                                np.logical_or(
                                              np.logical_and(py<=y3+1E-6, py>=y4-1E-6),
                                              np.logical_and(py<=y4+1E-6, py>=y3-1E-6)))
            #===================================================================
            # L[:,i0] = np.logical_and(lx, ly)
            #===================================================================
            L[validBool,i0] = np.logical_and(lx, ly)
        L = np.mod(np.sum(L, 1), 2)==1
        L = np.reshape(L, (pointsY.shape[1], pointsX.shape[0]), order='F')
            
        self._printProgress(segments-1, segments-1, prefix = 'Progress:', suffix = 'Complete', barLength = 50)
        
        return L

    def _listData(self):
        # List and pre-process available netCDF files 
        self.netCDFDict = {}
        for f0 in os.listdir(self.dataFolder):
            tmp = re.match('^' + self.filePrefix + '_([\d]{4}).([\d]{2}).nc$', f0)
            if tmp != None:
                tmp = (tmp.group(0), int(tmp.group(1)), int(tmp.group(2)))
                if tmp[1] not in self.netCDFDict.keys(): 
                    self.netCDFDict[tmp[1]] = {}
                self.netCDFDict[tmp[1]][tmp[2]] = [tmp[0], True]
                
    def _downloadFile(self, toDownload):
        '''
        Downloads the file from the url and saves it in the directory folderPath with the name fileName.
        '''
        fileName, url = toDownload
        
        # Opens the web page and creates a file in the folder folderPAth and with the name fileName
        try:
#===============================================================================
#             passman = request.HTTPPasswordMgrWithDefaultRealm()
#             passman.add_password(self.realm, url, self.username, self.password)
# 
#             authhandler = request.HTTPBasicAuthHandler(passman)
#             opener = request.build_opener(authhandler)
#             request.install_opener(opener)
#===============================================================================
            u = request.urlopen(url)
            
            f = open(fileName, 'wb')
    
            block_sz = 8192
            while True:
                buffer = u.read(block_sz)
                if not buffer:
                    break
            
                f.write(buffer)
            
            # Closes the file
            f.close()
            u.close()
            
            return os.path.getsize(fileName)
            
        except Exception as ex:
            warnings.warn(str(ex), UserWarning)
            
            return -1
    
    def _printProgress (self, iteration, total, prefix = '', suffix = '', decimals = 2, barLength = 100):
        '''
        Call in a loop to create terminal progress bar
        @params:
            iteration   - Required  : current iteration (Int)
            total       - Required  : total iterations (Int)
            prefix      - Optional  : prefix string (Str)
            suffix      - Optional  : suffix string (Str)
            decimals    - Optional  : number of decimals in percent complete (Int) 
            barLength   - Optional  : character length of bar (Int) 
        '''
        if total>0:
            filledLength    = int(round(barLength * iteration / float(total)))
            percents        = round(100.00 * (iteration / float(total)), decimals)
            bar             = '#' * filledLength + '-' * (barLength - filledLength)
            sys.stdout.write('%s [%s] %s%s %s\r' % (prefix, bar, percents, '%', suffix)),
            sys.stdout.flush()
            if iteration == total:
                print("\n")
    
    def _sumChunksMatrix(self, matrix, chunkSize, axis=-1):
        '''
        Sums sequences of values along a given axis.
        The chunkSize defines the size of the sequence to sum.
        '''
        shape = matrix.shape
        if axis < 0:
            axis += matrix.ndim
        shape = shape[:axis] + (-1, chunkSize) + shape[axis+1:]
        x = matrix.reshape(shape)
        return x.sum(axis=axis+1)

    def ismember(self, a, b):
        bind = {}
        for i, elt in enumerate(b):
            if elt not in bind:
                bind[elt] = i
        return [bind.get(itm, None) for itm in a if itm in bind.keys()]

    def _findLastNetCDF(self):
        tmp0 = max(self.netCDFDict.keys())
        tmp1 = max(self.netCDFDict[tmp0].keys())

        return (tmp0, tmp1, self.netCDFDict[tmp0][tmp1])

    def _notProcessed(self, dateRange):
        tmpDateMonth = [(dt.year, dt.month) for dt in dateRange]
        
        for i0 in range(len(dateRange)-1,-1,-1):
            tmp = dateRange[i0]
            if tmp.year in self.netCDFDict.keys():
                if tmp.month in self.netCDFDict[tmp.year].keys():
                    if self.netCDFDict[tmp.year][tmp.month][1]:
                        # the file is complete
                        dateRange.pop(i0)
                    else:
                        # the file is not complete
                        if 'loaded' in self.__dict__:
                            if not self.loaded['missing'][self.loaded['dates'].index(dateRange[i0])]:
                                # this value is not missing
                                dateRange.pop(i0)
                        else:
                            dateRange.pop(i0)
        
        return dateRange

    def _splitByMonth(self, dateRange):
        tmpDateMonth = [(dt.year, dt.month) for dt in dateRange]
        
        uniqueMonths = list(set(tmpDateMonth))
        tmpTuple = None
        idxs = []
        for s0 in tmpDateMonth:
            if s0 != tmpTuple:
                tmpIdx = uniqueMonths.index(s0)
                tmpTuple = s0
            idxs.append(tmpIdx)
        
        return idxs

    def _loadNetCDF(self, path, data=True):
        rootgrp = Dataset(path, 'r', format="NETCDF4")
        
        out = {}
        tmp = rootgrp.variables['time']
        out['dates'] = num2date(tmp[:], tmp.units, tmp.calendar)
        out['lat'] = rootgrp.variables['lat'][:]
        out['lon']= rootgrp.variables['lon'][:]
        out['complete'] = rootgrp.complete == 1
        out['missing'] = rootgrp.variables['missing'][:]
        if data:
            out['data'] = rootgrp.variables['precipitation'][:,:,:]
        
        rootgrp.close()
        
        return out

class TRMMSatelliteRainfall(SatelliteData):
    '''
    Data downloaded from:
        http://mirador.gsfc.nasa.gov/cgi-bin/mirador/presentNavigation.pl?tree=project&&dataGroup=Gridded&project=TRMM&dataset=3B42:%203-Hour%200.25%20x%200.25%20degree%20merged%20TRMM%20and%20other%20satellite%20estimates&version=007
    '''
    filePrefix = 'trmm3B42v7'
    precision = np.single
    significantDigits = 2
    downloadFailThreshold = 50000
    
    productSite = 'http://trmm.gsfc.nasa.gov/'
    downloadSite = 'http://mirador.gsfc.nasa.gov/cgi-bin/mirador/presentNavigation.pl?tree=project&&dataGroup=Gridded&project=TRMM&dataset=3B42:%203-Hour%200.25%20x%200.25%20degree%20merged%20TRMM%20and%20other%20satellite%20estimates&version=007'
    description = 'Tropical Rainfall Measuring Mission, TMPA 3B42 version 7. Accumulated rainfall over 3h intervals in mm. Grid of 0.25x0.25 deg.'
    realm = 'http://disc2.gesdisc.eosdis.nasa.gov/'
    timestep = {}
    timestep['hours'] = 3
    units = 'mm/3h'
    fileExtension = '.gz'
    
    def downloadList(self, dateIni=dt.datetime(1998, 1, 1, 0), dateEnd=dt.datetime.now()):
        '''
        implementation for TRMM 3B42 data
        
        returns a tuple containing a list of dates, a numpy 3D matrix with all the data, and numpy arrays with the pixel latitudes and longitudes
        '''
        
        urlFormat0="http://disc2.gesdisc.eosdis.nasa.gov/daac-bin/OTF/HTTP_services.cgi?FILENAME=%2Fs4pa%2FTRMM_L3%2FTRMM_3B42%2F{1}%2F{2}%2F3B42.{0}.7.HDF.Z&FORMAT=L2d6aXA&LABEL=3B42.{0}.7.nc.gz&SHORTNAME=TRMM_3B42&SERVICE=HDF_TO_NetCDF&VERSION=1.02&DATASET_VERSION=007"
        urlFormat1="http://disc2.gesdisc.eosdis.nasa.gov/daac-bin/OTF/HTTP_services.cgi?FILENAME=%2Fs4pa%2FTRMM_L3%2FTRMM_3B42%2F{1}%2F{2}%2F3B42.{0}.7A.HDF.Z&FORMAT=L2d6aXA&LABEL=3B42.{0}.7.nc.gz&SHORTNAME=TRMM_3B42&SERVICE=HDF_TO_NetCDF&VERSION=1.02&DATASET_VERSION=007"
        
        # Dates and urls to download
        dateList = self._notProcessed(self.filePeriod(dateIni=dateIni, dateEnd=dateEnd))
        dateList = [dt0.strftime('%Y%m%d.%H') for dt0 in dateList]
        
        urlList=[]
        for date in dateList:
            year, dayOfYear = self._fDayYear(date)
            if int(date[0:4]) < 2000 or year>2010:
                urlList.append(urlFormat0.format(date, year, dayOfYear))
            elif year==2010 and (int(dayOfYear)>273 or date=='20101001.00'):
                urlList.append(urlFormat0.format(date, year, dayOfYear))
            else:
                urlList.append(urlFormat1.format(date, year, dayOfYear))

        # File list
        fileList = [os.path.join(self.downloadFolder, '3B42.' + d0 + '.7.nc.gz') for d0 in dateList]       
        
        return (fileList, urlList)
         
    def downloadedDates(self):
        '''
        Provides a list of files in folder that are have a given extension.
        '''   
        # Reads the content of the data folder.
        # Returns the list of the files with the file type defined.
        filesFolder=os.listdir(self.downloadFolder)
        fileList=[]
        dateList=[]
        for f0 in filesFolder:
            if os.path.splitext(f0)[1] == self.fileExtension:
                fileList.append(os.path.join(self.downloadFolder, f0))
                dateList.append(dt.datetime.strptime(f0[5:16],'%Y%m%d.%H'))
                
        return (fileList, dateList)
    
    def importData(self, fileName):
        '''
        Imports the data of the files into python.
        '''
               
        # Defines the folder in which the temporary files are produced 
        tmpFolder = self.tmpFolder
        
        # SAFELY create a new file by providing a random name with tmp in the name and extension nc
        # The tempfile.mkstemp creates the file and returns an handle
        # This is a strange because is not the file but a reference to it (understood by the operative system) that is used to do any operation in it, using the file name probably won't work
        fOutIdx, fOutPath = tempfile.mkstemp(suffix='.nc', prefix='tmp', dir=tmpFolder)
        # Opens the temporary file and returns the descriptor that can be use to do things with the open file
        fOut = os.fdopen(fOutIdx, 'wb+')
        
        # Open the gz file and copy the nc file to the temporary file
        # Using the with ... as ... ensures that the gzip file opened is automatically closed in the end
        # The lenght=-1 specifies the buffer length, using a negative number makes the copy all at once instead of chunks
        # For large files these may lead to a uncontrolled memory consumption
        with gzip.open(fileName, 'rb') as fIn:
            shutil.copyfileobj(fIn, fOut, length=-1)
        fOut.close()
        
        # Reads the file fOut as a netcdf file, refering to it as rootgrp
        # Dataset returns an object with the dimensions and variables of the netcdf file, not the data in it
        rootgrp = Dataset(fOutPath, "r")
      
        data = rootgrp.variables['pcp'][:, :, :]
        longitudes = rootgrp.variables['longitude'][:]
        latitudes = rootgrp.variables['latitude'][:]
      
        # Replace missing values with nan
        data[data<=-999]=np.nan
       
        # Delete the temporary file
        rootgrp.close()
        ctr = 0
        while ctr<9:
            try:
                os.remove(fOutPath)
            except Exception as ex:
                pass
            ctr += 1
        if ctr==10:
            os.remove(fOutPath)
        
        return (data, latitudes, longitudes)
    
    def _fDayYear(self, url):
        '''
        This function returns the day of the year in 0-365 format and the year 
        '''
        # This is to correct that the date that the hour 00 is named on day n but day of the year n-1
        # This affects the year when in the 1st of january and the day when changing between days
        # First convert string to date and then, if hour=00 decrease one minute to make it return the previous day      
        tmpDate = dt.datetime.strptime(url, '%Y%m%d.%H')
        if url[-2:]=='00':
            tmpDiff = dt.timedelta(minutes=1)
            tmpDate -= tmpDiff
    
        return (tmpDate.year, '{dayYear:03d}'.format(dayYear=tmpDate.timetuple().tm_yday))

class TRMMSatelliteRainfallRT(SatelliteData):
    '''
    Data downloaded from:
        ftp://trmmopen.gsfc.nasa.gov/pub/merged/mergeIRMicro/
    '''
    filePrefix = 'trmm3B42v7RT'
    precision = np.single
    significantDigits = 2
    downloadFailThreshold = 50000
    
    productSite = 'http://trmm.gsfc.nasa.gov/'
    downloadSite = 'ftp://trmmopen.gsfc.nasa.gov/pub/merged/mergeIRMicro/'
    description = 'Tropical Rainfall Measuring Mission, TMPA 3B42 version 7 real-time. Accumulated rainfall over 3h intervals in mm. Grid of 0.25x0.25 deg.'
    realm = 'ftp://trmmopen.gsfc.nasa.gov/'
    timestep = {}
    timestep['hours'] = 3
    units = 'mm/3h'
    fileExtension = '.gz'
    
    def downloadList(self, dateIni=dt.datetime(1998, 1, 1, 0), dateEnd=dt.datetime.now()):
        '''
        implementation for TRMM 3B42 data
        
        returns a tuple containing a list of dates, a numpy 3D matrix with all the data, and numpy arrays with the pixel latitudes and longitudes
        '''
        
        urlFormat0 = "ftp://trmmopen.gsfc.nasa.gov/pub/merged/mergeIRMicro/{year}/{month:02d}/3B42RT.{datestr}.7R2.bin.gz"
        urlFormat1 = "ftp://trmmopen.gsfc.nasa.gov/pub/merged/mergeIRMicro/{year}/{month:02d}/3B42RT.{datestr}.7.bin.gz"
        urlFormat2 = "ftp://trmmopen.gsfc.nasa.gov/pub/merged/mergeIRMicro/{year}/3B42RT.{datestr}.7.bin.gz"
        
        # Dates and urls to download
        dateList = self._notProcessed(self.filePeriod(dateIni=dateIni, dateEnd=dateEnd))
        
        urlList=[]
        for date in dateList:
            year = date.year
            month = date.month
            if year<2012:
                urlList.append(urlFormat0.format(year=year, month=date.month, datestr=date.strftime('%Y%m%d%H')))
            elif year>2012:
                if year<2014:
                    urlList.append(urlFormat1.format(year=year, month=date.month, datestr=date.strftime('%Y%m%d%H')))
                else:
                    urlList.append(urlFormat2.format(year=year, datestr=date.strftime('%Y%m%d%H')))
            else:
                if date<dt.datetime(2012, 11, 7, 6):
                    urlList.append(urlFormat0.format(year=year, month=date.month, datestr=date.strftime('%Y%m%d%H')))
                else:
                    urlList.append(urlFormat1.format(year=year, month=date.month, datestr=date.strftime('%Y%m%d%H')))
                    
        # File list
        fileList = [os.path.join(self.downloadFolder, '3B42RT.' + d0.strftime('%Y%m%d%H') + '.7.bin.gz') for d0 in dateList]       
        
        return (fileList, urlList)
         
    def downloadedDates(self):
        '''
        Provides a list of files in folder that are have a given extension.
        '''   
        # Reads the content of the data folder.
        # Returns the list of the files with the file type defined.
        filesFolder=os.listdir(self.downloadFolder)
        fileList=[]
        dateList=[]
        for f0 in filesFolder:
            if os.path.splitext(f0)[1] == self.fileExtension:
                fileList.append(os.path.join(self.downloadFolder, f0))
                dateList.append(dt.datetime.strptime(f0[7:17],'%Y%m%d%H'))
                
        return (fileList, dateList)
    
    def importData(self, fileName):
        '''
        Imports the data of the files into python.
        '''
        
        with gzip.open(fileName, 'rb') as fIn:
            fIn.seek(2880)
            data = np.frombuffer(fIn.read(1382400), dtype=np.dtype('>i2')).astype(np.double)
         
        # Replace missing values with nan
        data[data==-31999]=np.nan
       
        # Reshape and scale to mm
        data = data.reshape((1, 480, 1440))/100*3
        longitudes = np.linspace(0.125, 360-0.125, 1440)
        latitudes = -np.linspace(-60+0.125, 60-0.125, 480)
        
        return (data, latitudes, longitudes)
        
    def _readBytes(self, fIn):
        return(struct.unpack('>h', fIn.read(2))[0])