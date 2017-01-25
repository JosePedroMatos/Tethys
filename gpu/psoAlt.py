# coding: utf-8
'''
Created on 21/09/2015

@author: Jose Pedro Matos
'''
import numpy as np
import time
from .optAlgorithm import OptAlgorithm

class PSOAlt(OptAlgorithm):
    '''
    PSO
    '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # define required options
        if not 'pBins' in self.opt:
            self.opt['pBins']=10
        if not 'inertia' in self.opt:
            self.opt['inertia']=0.5
        if not 'c1' in self.opt:
            self.opt['c1']=0.6
        if not 'c2' in self.opt:
            self.opt['c2']=0.3
        if not 'c3' in self.opt:
            self.opt['c3']=0.001
        
        if self.opt['c3']==0:
            self.opt['c3']=1E-5

        # define required variables
        self.pBestIdxs=np.arange(self.opt['population'], dtype=np.int32)
        self.gBestIdxs=np.arange(self.opt['population'], dtype=np.int32)
        self.velocities=np.zeros((self.opt['population'],self.opt['nVars']))
        tmp=np.hstack((-np.Inf, np.linspace(0,1, num=self.opt['pBins'])))
        self.pBins=np.vstack((tmp[0:-1],tmp[1:]))
    
    def best(self, fit):
        sortedIdxs=np.argsort(fit[:,0])
        
        # for global best the fitness domain is split in 3 regions
        nRegions=3
        globalIdxsList=np.array_split(sortedIdxs, nRegions)
        binBorders=np.arange(0,nRegions+1)/nRegions
        binBorders[-1]=np.inf
        for i0 in range(nRegions):
            tmpIdxs=np.where(np.logical_and(fit[:,0]>=binBorders[i0], fit[:,0]<binBorders[i0+1]))[0]
            if len(tmpIdxs)!=0:
                if i0==0:
                    tmp=np.array((0.0, np.min(fit[tmpIdxs,1])))
                elif i0==1:
                    tmp=fit[tmpIdxs[np.argmin(fit[tmpIdxs,1])],]
                else:
                    tmp=np.array((1.0, np.min(self.fit[tmpIdxs,1])))
                dist=self.euclideanDist(tmp, self.fit[tmpIdxs,])
                self.gBestIdxs[globalIdxsList[i0]]=tmpIdxs[np.argmin(dist)]
        
        # for particle best the fitness domain is split in n regions
        for i0 in range(self.opt['pBins']):
            tmpIdxs=np.where(np.logical_and(fit[:,0]>self.pBins[0, i0], fit[:,0]<=self.pBins[1, i0]))[0]
            if len(tmpIdxs)!=0:
                self.pBestIdxs[tmpIdxs]=tmpIdxs[np.argmin(fit[tmpIdxs,1])]
        tmpIdxs=np.where(fit[:,0]>=self.pBins[1, self.opt['pBins']-1])[0]
        if len(tmpIdxs)!=0:
            self.pBestIdxs[tmpIdxs]=tmpIdxs[np.argmin(fit[tmpIdxs,1])]
        
    def euclideanDist(self, rRef, pList):
        dist=np.zeros(pList.shape[0])

        for i0 in range(len(rRef)):
            dist+=(pList[:,i0]-rRef[i0])**2
        return dist**0.5
    
    def newPop(self, fit, population):
        start=time.time()
        
        # prepare best entries
        self.best(fit)
        pBest=self.population[self.pBestIdxs,]
        gBest=self.population[self.gBestIdxs,]
        #=======================================================================
        # self.toPlot={'local best': fit[np.unique(self.pBestIdxs),],
        #              'global best': fit[np.unique(self.gBestIdxs),],
        #              }
        #=======================================================================
        
        # calculate velocities
        tmpRnd1 = np.random.uniform(low=0.0, high=self.opt['c1'], size=(self.opt['population'],1)).repeat(self.opt['nVars'],1)
        tmpRnd2 = np.random.uniform(low=0.0, high=self.opt['c2'], size=(self.opt['population'],1)).repeat(self.opt['nVars'],1)
        tmpRnd3 = np.random.normal(loc=0.0, scale=self.opt['c3'], size=(self.opt['population'], self.opt['nVars']))
            
        candidateVelocities=(self.opt['inertia']*self.velocities+ 
                             tmpRnd1 * (pBest-self.population) + 
                             tmpRnd2 * (gBest-self.population) +
                             tmpRnd3)
                  
        # calculate positions
        tmpCandidates, toReflect=self.enforceBounds(self.population + candidateVelocities)
        candidateVelocities[toReflect,]=-candidateVelocities[toReflect,]
        
        self.jointVelocities=np.vstack((self.velocities, candidateVelocities))
        
        self.timing['newPop']=(time.time()-start)
        return tmpCandidates
    
    def selection(self, fit, frontLvls, crowdDist, population):
        '''Selection method for PSO'''
        start=time.time()
        
        toKeepIdxs=list()
        available=self.opt['population']-len(toKeepIdxs)
        refFront=0
        while available>0:
            frontIdxs=np.where(frontLvls==refFront)[0]
            if len(frontIdxs)<=available:
                toKeepIdxs.extend(frontIdxs)
            else:
                sortedPhenotype=frontIdxs[np.lexsort((fit[frontIdxs,0],crowdDist[frontIdxs,0]))[::-1]]
                toKeepIdxs.extend(sortedPhenotype[:available])
            available=self.opt['population']-len(toKeepIdxs)
            refFront+=1
        
        toKeepIdxs=np.array(toKeepIdxs)
                         
        # update particle velocities
        self.velocities=self.jointVelocities[toKeepIdxs,]
        
        # update messages
        # self.messaging['updated']='%.2f%%' % (100*np.mean(toKeepIdxs>=self.opt['population']))
             
        self.timing['selection']=(time.time()-start)
        return toKeepIdxs