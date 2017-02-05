# coding: utf-8
'''
Created on 21/09/2015

@author: Jose Pedro Matos
'''
import numpy as np
import matplotlib.pyplot as plt
import time
import warnings
import mpld3
from .domination import convexSorting
from .crowding import phenCrowdingNSGAII
from multiprocessing import Process, Queue
from celery import current_task
from timeSeries.models import Forecast
from gpu.functions import predictiveQQ, processBands, metrics, plot

class OptAlgorithm(object):
    '''
    Abstract class for algorithm definition
    '''

    def __init__(self, data, targets, nVars, evalFun, errorObj, population=1000, epochs=100,
                 bands=[0.001, 0.01, 0.025, 0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 0.975, 0.99, 0.999],
                 bandWidth=0.025, minModels=5, displayEach=10, taskInfo={'message': ''}, transformWeights=False, debug=False,
                 forceNonExceedance=0, multiQQ=1, normalization=None, **kwargs):
        self.trained = False

        # handling of key arguments
        self.trainData = data
        self.targets = targets
        self.evalFun = evalFun
        self.errorObj = errorObj
        self.opt = {}
        self.opt['nVars'] = nVars
        self.opt['population'] = population
        self.opt['epochs'] = epochs
        self.opt['bands'] = bands
        self.opt['bandWidth'] = bandWidth
        self.opt['minModels'] = minModels
        self.opt['displayEach'] = displayEach
        self.opt['transformWeights'] = transformWeights
        self.opt['debug'] = debug
        self.opt['forceNonExceedance'] = forceNonExceedance
        self.opt['multiQQ'] = multiQQ
        self.opt['normalization'] = normalization
        self.timing = {}
        self.normalize = {}
        self.taskInfo = taskInfo
        self.fig = None
        self.plotAx = None
        self.plotCounter = 0
        self.toPlot = {}
        
        # addition of generic arguments to options
        self.opt.update(kwargs)
    
        # set needed variables (if missing)
        if not 'bounds' in self.opt:
            self.opt['bounds']=np.vstack((-5*np.ones(self.opt['nVars']),
                                              5*np.ones(self.opt['nVars'])))
        if not 'crowdingWindow' in self.opt:
            self.opt['crowdingWindow']=0.1
        if not 'crowdingFraction' in self.opt:
            self.opt['crowdingFraction']=1.0
        if not 'plotCases' in self.opt:
            self.opt['plotCases']=100
        if not 'plotLinks' in self.opt:
            self.opt['plotLinks']=False
        
        if self.opt['plotCases']>self.opt['population']:
            self.opt['plotCases']=self.opt['population']
        
        self.bandBounds = self.__establishBandBounds__()
    
    def __establishBandBounds__(self):
        # establish bounds
        bounds = np.zeros((2, len(self.opt['bands'])))
        widths = np.zeros_like(self.opt['bands'])
        for i0 in range(0, int(len(self.opt['bands'])/2)):
            if i0==0:
                widths[i0] = min((self.opt['bandWidth'], self.opt['bands'][0]))
            else:
                widths[i0] = min((self.opt['bandWidth'], self.opt['bands'][i0]-self.opt['bands'][i0-1]))
        for tmpI0 in range(0, int(len(self.opt['bands'])/2)):
            i0 = len(self.opt['bands'])-1-tmpI0
            if i0==len(self.opt['bands'])-1:
                widths[i0] = min((self.opt['bandWidth'], 1-self.opt['bands'][i0]))
            else:
                widths[i0] = min((self.opt['bandWidth'], self.opt['bands'][i0+1]-self.opt['bands'][i0]))    
        
        # correct widths by removing overlaps
        for i0 in range(int(len(self.opt['bands'])/2), 0, -1):
            x = self.opt['bands'][i0-1]+widths[i0-1]-(self.opt['bands'][i0]-widths[i0])
            if x>0:
                if widths[i0]>x:
                    widths[i0] -= x
                else:
                    fx = 1-x/(widths[i0-1]+widths[i0])
                    widths[i0] *= fx
                    widths[i0-1] *= fx
        for i0 in range(int(len(self.opt['bands'])/2), len(self.opt['bands'])-1):
            x = self.opt['bands'][i0]+widths[i0]-(self.opt['bands'][i0+1]-widths[i0+1])
            if x>0:
                if widths[i0]>x:
                    widths[i0] -= x
                else:
                    fx = 1-x/(widths[i0]+widths[i0+1])
                    widths[i0] *= fx
                    widths[i0+1] *= fx
        
        
        # save
        bounds[0,] = self.opt['bands']-widths
        bounds[1,] = self.opt['bands']+widths

        return bounds
    
    def predict(self, data=None, bands=None):
        # run simulations
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if data!=None:
                if self.opt['transformWeights']:
                    simulations = self.evalFun(self._fWeights(self.population), data=data)
                else:
                    simulations = self.evalFun(self.population, data=data)
            else:
                simulations = self.simulations
            #===================================================================
            # if self.opt['lowerThreshold']!=None:
            #     simulations[simulations<self.opt['lowerThreshold']] = self.opt['lowerThreshold']
            #===================================================================
        
        # average results
        averaged = np.empty((simulations.shape[0], self.bandBounds.shape[1]))*np.nan
        for i0 in range(self.bandBounds.shape[1]):
            tmpValidNE = np.where(np.logical_and(self.fit[:,0]>=self.bandBounds[0,i0], self.fit[:,0]<=self.bandBounds[1,i0]))[0] 
            
            if len(tmpValidNE)>self.opt['minModels']:
                averaged[:,i0] = np.mean(simulations[:,tmpValidNE], axis=1)
                #===============================================================
                # tmpValidEr = self.fit[tmpValidNE,1]
                # sortIdxs = np.argsort(tmpValidEr)
                # threshIdxs = np.where(tmpValidEr<=(np.median(tmpValidEr)+np.min(tmpValidEr))/2)[0]
                # if len(threshIdxs)<self.opt['minModels']:
                #     idxs = sortIdxs[:self.opt['minModels']]
                # else:
                #     idxs = threshIdxs
                # averaged[:,i0] = np.mean(simulations[:,tmpValidNE[idxs]], axis=1)
                #===============================================================
        return averaged
   
    def start(self):
        if not self.trained:
            self.__initPopulation__()
        
        self.simulations, self.fit=self.__eval__(self.population)
        self.frontLvls=self.__domination__(self.fit)[1]
    
        # QQ plot
        bands = processBands(self.predict(), self.opt['bands'])
        uniform, pValues = predictiveQQ(bands, self.targets, self.opt['bands'])
        mUniform = []
        mPValues = []
        for i0 in range(self.opt['multiQQ']):
            tmp = range(int(np.floor(i0/self.opt['multiQQ']*self.trainData.shape[0])), int(np.floor((i0+1)/self.opt['multiQQ']*self.trainData.shape[0])))
            tmp0, tmp1 = predictiveQQ(bands[tmp,:], self.targets[tmp], self.opt['bands'])
            mUniform.append(tmp0)
            mPValues.append(tmp1)
            
        # Performance
        alpha, xi, pi = metrics(uniform, pValues, bands, self.bandBounds)
        
        # Update Tethys
        tmpMessages = []
        tmpMessages.append('&nbsp&nbsp&nbsp&nbsp&nbsp&nbspEpoch %05u: ' % (0))
        tmpMessages.append('&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbspmetrics: &#945:%f, &#958:%f, &#960:%f' % (alpha, xi, pi))
        self._updateInfo(state='PROGRESS', message=tmpMessages, plot=self._plotD3(uniform, pValues, bands))
        
        if self.opt['debug']:
            plotQueue = Queue()
            p = Process(target=plot, args=(plotQueue,))
            p.start()
            self.rejected = []
            self._plotWrapper(plotQueue, bands, uniform, pValues, alpha, xi, pi, 0, mUniform, mPValues)
    
        # Compute
        for i0 in range(self.opt['epochs']):
            self.__iteration__()
            
            # Check cancellation
            if 'forecastName' in self.opt.keys():
                forecasts = Forecast.objects.filter(name=self.opt['forecastName'])
                if forecasts:
                    forecast=forecasts[0]
                    if forecast.jobId=='':
                        raise Exception('Cancelled by user...')
            
            # Display
            if (np.mod(i0+1, self.opt['displayEach'])==0 and i0!=0) or i0==self.opt['epochs']-1:
                # QQ plot
                bands = processBands(self.predict(), self.opt['bands'])
                uniform, pValues = predictiveQQ(bands, self.targets, self.opt['bands'])
                mUniform = []
                mPValues = []
                for i1 in range(self.opt['multiQQ']):
                    tmp = range(int(np.floor(i1/self.opt['multiQQ']*self.trainData.shape[0])), int(np.floor((i1+1)/self.opt['multiQQ']*self.trainData.shape[0])))
                    tmp0, tmp1 = predictiveQQ(bands[tmp,:], self.targets[tmp], self.opt['bands'])
                    mUniform.append(tmp0)
                    mPValues.append(tmp1)
                
                # Performance
                alpha, xi, pi = metrics(uniform, pValues, bands, self.bandBounds)
                
                # Output times
                tmpKeys=sorted(self.timing.keys())
                tmpToPrint=''
                for key in tmpKeys:
                    if key == 'total':
                        tmpToPrint+=key + ': %.2e' % (self.timing['total']) + 's; '
                    else:
                        if self.timing['total']!=0:
                            tmpToPrint+=key + ': %.2f' % (self.timing[key]/self.timing['total']*100) + '%; '
                        else:
                            tmpToPrint+=key + ': %.2f' % (0) + '%; '
                
                
                tmpMessages = []
                print('Epoch %5u: ' % (i0) + tmpToPrint[:-2])
                tmpMessages.append('&nbsp&nbsp&nbsp&nbsp&nbsp&nbspEpoch %05u: ' % (i0+1) + tmpToPrint[:-2])
                
                print('    metrics: alpha:%f, xi:%f, pi:%f' % (alpha, xi, pi))
                tmpMessages.append('&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbspmetrics: &#945:%f, &#958:%f, &#960:%f' % (alpha, xi, pi))
                
                # Update Tethys
                self._updateInfo(state='PROGRESS', message=tmpMessages, plot=self._plotD3(uniform, pValues, bands))
                
                # Debug plot
                if self.opt['debug']:
                    self._plotWrapper(plotQueue, bands, uniform, pValues, alpha, xi, pi, i0, mUniform, mPValues)
                
        self.trained = True
        if self.opt['debug']:
            plotQueue.put(False)
            p.join()
        
        # export results
        #=======================================================================
        # if self.opt['transformWeights']:
        #     self.population = self._fWeightsInv(self.population)
        #=======================================================================

        result = {'parameters': self.population, 'normalization': self.normalize,'fitness': self.fit}
        
        # plot
        if self.opt['plotResult']:
            self._plot()
            
        return result    
    
    def _plotWrapper(self, queue, bands, uniform, pValues, alpha, xi, pi, epoch, mUniform, mPValues):
        tmpBest = np.argmin(self.fit[:,1])
        best = self.simulations[:, tmpBest]
        
        tmp = np.array(self.getBands())
        tmp = 1-2*tmp[0:int(tmp.shape[0]/2)]
        
        data = {'fig': self.fig, 
                'plotAx': self.plotAx,
                'targets': self.targets,
                'best': best,
                'bands': bands,
                'fit': self.fit,
                'frontLvls': self.frontLvls,
                'uniform': uniform,
                'pValues': pValues,
                'rejected': self.rejected,
                'alpha': alpha,
                'xi': xi,
                'pi': pi,
                'epoch': epoch,
                'mUniform': mUniform,
                'mPValues': mPValues,
                'normalization': self.opt['normalization'],
                'bandSize': tmp[::-1],
                }

        queue.put(data)
    
    def _plotD3(self, uniform, pValues, bands):
        fig = plt.figure(figsize=(13.5, 4.2))
        plotAx=[]
        plotAx.append(fig.add_subplot(1, 3, 1))
        plotAx.append(fig.add_subplot(1, 3, 2))
        plotAx.append(fig.add_subplot(1, 3, 3))
        
        # Pareto front
        if 'rejected' in self.__dict__.keys():
            plotAx[0].plot(self.rejected[:,0], self.rejected[:,1], 'o', color = '0.75', label='rejected')
        plotAx[0].plot(self.fit[:,0], self.fit[:,1], 'ok', label='kept')
        plotAx[0].plot(self.fit[self.frontLvls==0,0], self.fit[self.frontLvls==0,1], 'or', label='chosen')
        symbols = ['oy', 'om']
        for i0, k0 in enumerate(self.toPlot.keys()):
            plotAx[0].plot(self.toPlot[k0][:,0], self.toPlot[k0][:,1], symbols[i0 % len(symbols)], label=k0)
        plotAx[0].set_xlim((0,1))
        self.__updateYLim__(self.fit[:,1], plotAx[1])
        plotAx[0].grid(True)
        plotAx[0].legend(fontsize=10, numpoints=1, title='')
        plotAx[0].set_xlabel('Non-exceedance (% of observations under the simulated values)')
        plotAx[0].set_ylabel('Log10(error function) (z-scored values)')
         
        # QQ
        plotAx[1].plot([0, 1], [0, 1], '--k')
        tmp = np.unique(np.linspace(0, len(uniform)-1, 200, dtype=np.int))
        plotAx[1].plot(uniform[tmp], pValues[tmp], '-r', label='Observations')
        plotAx[1].set_xlim((0,1))
        plotAx[1].set_ylim((0,1))
        plotAx[1].grid(True)
        plotAx[1].set_xlabel('Theoretical quantile of U[0,1]')
        plotAx[1].set_ylabel('Quantile of the observed p-value')
        
        # Series
        x = range(len(self.targets[self.opt['plotIdxs']]))
        colors = [str(d0) for d0 in np.linspace(0, 1, int(np.floor(bands.shape[1]/2)))]
        for i0 in range(int(np.floor(bands.shape[1]/2))-1,-1,-1):
            plotAx[2].fill_between(x, bands[self.opt['plotIdxs'],i0], bands[self.opt['plotIdxs'],bands.shape[1]-1-i0], facecolor='black', linewidth=0.0, alpha='0.2')
            
            #===================================================================
            # plotAx[2].fill_between(x, bands[self.opt['plotIdxs'],i0], bands[self.opt['plotIdxs'],bands.shape[1]-1-i0], facecolor=colors[i0], linewidth=0.0)
            #===================================================================
            #===================================================================
            # 
            # if 0==i0:
            #     plotAx[2].fill_between(x, bands[self.opt['plotIdxs'],i0], bands[self.opt['plotIdxs'],bands.shape[1]-1-i0], facecolor='black', linewidth=0.0)
            # else:
            #     plotAx[2].fill_between(x, bands[self.opt['plotIdxs'],i0], bands[self.opt['plotIdxs'],bands.shape[1]-1-i0], facecolor='white', linewidth=0.0, alpha='0.5')
            #===================================================================
        plotAx[2].plot(self.targets[self.opt['plotIdxs']], '-r')
        plotAx[2].grid(True)
        plotAx[2].set_xlim(0, len(self.opt['plotIdxs'])-1)
        plotAx[2].set_xlabel('Two extreme training periods')
        plotAx[2].set_ylabel('Z-scored targets and simulations')
        
        plotDict = mpld3.fig_to_dict(fig)
        plt.close(fig)
        return plotDict
        
    def _updateInfo(self, state='PROGRESS', message=None, plot=None):
        try:
            self.taskInfo['message'].extend(message)
            if plot!=None:
                self.taskInfo['plot'] = plot
                self.taskInfo['plotCounter'] = self.plotCounter
                self.plotCounter = self.plotCounter + 1
            current_task.update_state(state='PROGRESS', meta=self.taskInfo)
        except Exception:
            pass
    
    def __updateYLim__(self, data, axis):
        axis.set_ylim((np.floor(np.min(data)-0.25), np.ceil(np.max(data)+1)))

    def __initPopulation__(self):
        self.population=np.random.uniform(0, 1, (self.opt['population'], self.opt['nVars']))
    
        tmpMin=np.tile(self.opt['bounds'][0,], (self.opt['population'], 1))
        tmpMax=np.tile(self.opt['bounds'][1,], (self.opt['population'], 1))
    
        self.population=self.population*(tmpMax-tmpMin)+tmpMin

    def __iteration__(self):
        start=time.time()
        
        # generate new candidates
        newPopulation=self.newPop(self.fit, self.population)
        
        # evaluate solutions
        newSimulations, newFit=self.__eval__(newPopulation)
        jointPopulation=np.vstack((self.population, newPopulation))
        jointFit=np.vstack((self.fit, newFit))
        jointSimulations=np.hstack((self.simulations, newSimulations))
        
        # domination
        jointFrontLvls=self.__domination__(jointFit)[1]
        
        # crowding
        jointCrowdDist=self.__crowding__(jointSimulations, jointFit, jointFrontLvls)
        
        # select the population 
        toKeepIdxs=self.selection(jointFit, jointFrontLvls, jointCrowdDist, jointPopulation)
        tmp = np.ones(jointFit.shape[0], dtype=np.bool)
        tmp[toKeepIdxs] = False
        self.rejected = jointFit[tmp,]
        self.fit=jointFit[toKeepIdxs,]
        self.simulations=jointSimulations[:,toKeepIdxs]
        self.population=jointPopulation[toKeepIdxs,]
        
        self.frontLvls=jointFrontLvls[toKeepIdxs,]
        
        self.timing['total']=(time.time()-start)
        
    def __eval__(self, population):
        
        # evaluate function
        start=time.time()
        if self.opt['transformWeights']:
            simulations = self.evalFun(self._fWeights(population))
        else:
            simulations = self.evalFun(population)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            #===================================================================
            # if self.opt['lowerThreshold']!=None:
            #     simulations[simulations<self.opt['lowerThreshold']] = self.opt['lowerThreshold']
            #===================================================================
        self.timing['run']=(time.time()-start)
        
        # compute errors
        start=time.time()
        self.errorObj.reshapeData(simulations)
        error, quantile=self.errorObj.compute(simulations)
        self.timing['eval']=(time.time()-start)
        
        # compute regularization
        if 'regFun' in self.opt:
            start=time.time()
            if self.opt['transformWeights']:
                reg = self.opt['regFun'](self._fWeightsInv(population))
            else:
                reg = self.opt['regFun'](population)
            error+=reg
            self.timing['reg']=(time.time()-start)
        
        # transform
        error = np.log10(error)
        
        fit=np.transpose(np.vstack((quantile, error)))
        return (simulations, fit)
    
    def __crowding__(self, simulations, fit, frontLvls):
        '''Phenotype crowding based on correlations with neighboring series [1 - high crowding; 0 - low crowding]'''
        
        # crowding NSGAII
        start=time.time()
        phenotype=phenCrowdingNSGAII(fit[:,0], fit[:,1], fronts=frontLvls)
        self.timing['crowdingNSGAII']=(time.time()-start)
        
        return np.vstack((phenotype, phenotype)).T
        
    def __domination__(self, fit):
        start=time.time()
        if ('forceNonExceedance' in self.opt):
            tmpMin=fit[np.argmin(fit[:,1]), 0]
            tmpDiff=np.abs(fit[:, 0]-tmpMin)
            fronts=convexSorting(fit[:,0], fit[:,1]+self.opt['forceNonExceedance']*tmpDiff)
        else:
            fronts=convexSorting(fit[:,0], fit[:,1])
            
        frontLvl=self.opt['population']*np.ones((fit.shape[0],))
        for i0 in range(len(fronts)):
            frontLvl[fronts[i0]]=i0
            
        self.timing['domination']=(time.time()-start)
        return (fronts, frontLvl)
    
    def newPop(self, fit, population):
        """abstract method"""
        pass
    
    def selection(self, fit, frontLvls, crowdDist):
        """abstract method"""
        pass
    
    def closestPareto(self, fit, population, frontLvls):
        """distance to the Pareto front"""
        inParetoFront=np.where(frontLvls==0)[0]
        
        tmp0=np.tile(fit[inParetoFront,0],(population.shape[0],1)) - np.tile(fit[:,0],(len(inParetoFront),1)).T
        tmp1=np.tile(fit[inParetoFront,1],(population.shape[0],1)) - np.tile(fit[:,1],(len(inParetoFront),1)).T
        tmp0=tmp0-np.min(tmp0)
        tmp1=tmp1-np.min(tmp1)
        tmp0Max=np.max(tmp0)
        tmp1Max=np.max(tmp1)
        if tmp0Max==0:
            tmp0[:]=0.0
        else:
            tmp0=tmp0/tmp0Max
        if tmp1Max==0:
            tmp1[:]=0.0
        else:
            tmp1=tmp1/tmp1Max
        dist=np.sqrt(np.square(tmp0)+np.square(tmp1))
        
        closest=inParetoFront[np.argsort(dist, axis=1)]
        distance=np.sort(dist, axis=1)
        
        return (closest, distance)
    
    def enforceBounds(self, newPopulation):
            
        boundedPopulation=np.max(np.dstack((newPopulation, np.tile(self.opt['bounds'][0,], (self.opt['population'],1)))), axis=2)
        boundedPopulation=np.min(np.dstack((boundedPopulation, np.tile(self.opt['bounds'][1,], (self.opt['population'],1)))), axis=2)
        changed=np.sum(np.abs(boundedPopulation),1)!=np.sum(np.abs(newPopulation),1)
        
        return (boundedPopulation, changed)
  
    def getBands(self):
        return self.opt['bands']
    
    def getPopulation(self):
        return self.population
    
    def setPopulation(self, population):
        self.trained = True
        self.population = population
        
    def _fWeights(self, pop):
        return np.power(pop/4,5)
        
    def _fWeightsInv(self, pop):
        return 4*np.copysign(np.power(np.abs(pop), 1/5), pop)