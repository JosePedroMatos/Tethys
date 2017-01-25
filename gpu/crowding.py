'''
Created on 4 juin 2015

@author: Jose Pedro Matos
'''

import numpy as np
import pyopencl as cl
from collections import namedtuple
import pkg_resources

def phenCrowdingNSGAII(*args, **kwargs):
    '''
    Phenotype crowding used in NSGAII
    '''
    
    if 'fronts' in kwargs:
        fronts=kwargs['fronts']
    else:
        fronts=list((range(0, len(args[0])),))
    
    distance=np.zeros_like(args[0])
    for m0 in args:
        if type(fronts)==type([]):
            for l0 in fronts:
                idx=np.array(l0)
                x=m0[idx]
                tmpSortIdx=np.argsort(x)
                tmpSort=x[tmpSortIdx]
                if (tmpSort[-1]-tmpSort[0])!=0:
                    distance[idx[tmpSortIdx[1:-1]]]+=(tmpSort[2:]-tmpSort[:-2])/(tmpSort[-1]-tmpSort[0])
                else:
                    distance[idx[tmpSortIdx[1:-1]]]=0
                distance[idx[tmpSortIdx[0]]]=distance[idx[tmpSortIdx[-1]]]=np.Inf
        else:
            for i0 in np.sort(np.unique(fronts)):
                idx=np.where(fronts==i0)[0]
                x=m0[idx]
                tmpSortIdx=np.argsort(x)
                tmpSort=x[tmpSortIdx]
                if (tmpSort[-1]-tmpSort[0])!=0:
                    distance[idx[tmpSortIdx[1:-1]]]+=(tmpSort[2:]-tmpSort[:-2])/(tmpSort[-1]-tmpSort[0])
                else:
                    distance[idx[tmpSortIdx[1:-1]]]=0
                distance[idx[tmpSortIdx[0]]]=distance[idx[tmpSortIdx[-1]]]=np.Inf
        
    return distance

def genCrowding(nonExceedance, genes, **kwargs):
    '''
    Genotype crowding
    '''
    
    window=0.05
    window=int(len(nonExceedance)*window)
    
    if 'fronts' in kwargs:
        fronts=kwargs['fronts']
    else:
        fronts=list((range(0, len(nonExceedance)),))
    
    results=list()
    for l0 in fronts:
        tmpFront=np.array(l0)
        sortIdxs=np.argsort(nonExceedance[tmpFront])
        tmpGenes=genes[sortIdxs,]
        
        tmpResults=np.zeros((len(l0),len(l0)))
        for i0 in range(len(l0)):
            for i1 in range(i0+1, i0+window):
                if i1>=len(l0):
                    break
                tmpResults[i0,i1]=1.0/(0.1+np.linalg.norm(tmpGenes[i0,]-tmpGenes[i1,], ord=2))
        tmpResults+=tmpResults.T
        results.append(tmpResults)
        
    return results

class crowdingOpenCL(object):
    '''
    classdocs
    '''
    openCL=namedtuple('openCL', ('active','devList','ctx','prg','queue','verbose'), verbose=False, rename=False)
    sizes=dict()
    
    def __init__(self, workGroup=(16, 16), platform=0, deviceType='ALL', verbose=0):
        self.openCL.workGroup=workGroup
        self.openCL.platform=platform
        tmp={'ALL': cl.device_type.ALL, 'CPU': cl.device_type.CPU, 'GPU': cl.device_type.GPU}
        self.openCL.type=tmp[deviceType]
        self.openCL.verbose=verbose
        
        self._prepOpenCL()
    
    def _prepOpenCL(self):
        platform=cl.get_platforms()[self.openCL.platform]
        self.openCL.devList= platform.get_devices(device_type=self.openCL.type)
        self.openCL.ctx = cl.Context(devices=self.openCL.devList)
        with open ("crowding.cl", "r") as kernelFile:
            kernelStr=kernelFile.read()
        self.openCL.prg = cl.Program(self.openCL.ctx, kernelStr).build()
        self.openCL.queue = cl.CommandQueue(self.openCL.ctx)
        
        if self.openCL.verbose!=0:
            print("===============================================================")
            print("Platform name:", platform.name)
            print("Platform profile:", platform.profile)
            print("Platform vendor:", platform.vendor)
            print("Platform version:", platform.version)
            for device in self.openCL.devList:
                print("---------------------------------------------------------------")
                print("    Device name:", device.name)
                print("    Device type:", cl.device_type.to_string(device.type))
                print("    Device memory: ", device.global_mem_size//1024//1024, 'MB')
                print("    Device max clock speed:", device.max_clock_frequency, 'MHz')
                print("    Device compute units:", device.max_compute_units)
                print("    Device max work items:", device.get_info(cl.device_info.MAX_WORK_ITEM_SIZES))
                print("    Device local memory:", device.get_info(cl.device_info.LOCAL_MEM_SIZE)//1024, 'KB')
    
    def _increment(self, base, interval):
        tmp=base%interval
        if tmp==0:
            return (base, 0)
        else:
            return (base+interval-tmp, interval-tmp)
    
    def reshapeData(self, genes):
        self.sizes['originalGenes'], self.sizes['chromosomeLength']=genes.shape
        
        self.sizes['reshaped0'], self.sizes['add0']=self._increment(self.sizes['originalGenes'], self.openCL.workGroup[0])
        self.sizes['reshaped1'], self.sizes['add1']=self._increment(self.sizes['originalGenes'], self.openCL.workGroup[1])
        
        if self.openCL.verbose!=0:
            print('Vertical array adjustment: +%.1f%% (%ux %u items)' % (self.sizes['add0']/self.sizes['originalGenes']*100, self.sizes['reshaped0']//self.openCL.workGroup[0], self.openCL.workGroup[0]))
            print('Horizontal array adjustment: +%.1f%% (%ux %u items)' % (self.sizes['add1']/self.sizes['originalGenes']*100, self.sizes['reshaped1']//self.openCL.workGroup[1], self.openCL.workGroup[1]))
                
    def compute(self, genes, window):
        genesOpenCL=genes.reshape(-1, order = 'C').astype(np.float32)
        
        globalSize=(int(self.sizes['reshaped0']), int(self.sizes['reshaped1']))
        localSize=(int(self.openCL.workGroup[0]), int(self.openCL.workGroup[1]))
        
        mf = cl.mem_flags
        base=np.float32(2)
        chromosomeLength=np.int32(self.sizes['chromosomeLength'])
        lim0=np.int32(self.sizes['originalGenes'])
        lim1=np.int32(self.sizes['originalGenes'])
        genesBuffer = cl.Buffer(self.openCL.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=genesOpenCL)
        outBuffer = cl.Buffer(self.openCL.ctx, mf.WRITE_ONLY, int((self.sizes['originalGenes']**2)*np.int32(1).nbytes))
        
        kernel=self.openCL.prg.genCrowding
        
        kernel(self.openCL.queue, globalSize, localSize,
               base, chromosomeLength, lim0, lim1,
               genesBuffer,
               outBuffer)
        
        crowding = np.empty((self.sizes['originalGenes']**2,)).astype(np.float32)
        cl.enqueue_copy(self.openCL.queue, crowding, outBuffer)
        crowding=np.reshape(crowding, (self.sizes['originalGenes'], -1), order='F')
        
        return crowding
    
class crowdingPhenCorrOpenCl(object):
    '''
    classdocs
    '''
    openCL=namedtuple('openCL', ('active','devList','ctx','prg','queue','verbose'), verbose=False, rename=False)
    sizes=dict()
    
    def __init__(self, workGroup=(16, 16), platform=0, deviceType='ALL', verbose=0):
        self.openCL.workGroup=workGroup
        self.openCL.platform=platform
        tmp={'ALL': cl.device_type.ALL, 'CPU': cl.device_type.CPU, 'GPU': cl.device_type.GPU}
        self.openCL.type=tmp[deviceType]
        self.openCL.verbose=verbose
        
        self._prepOpenCL()
        
    def _prepOpenCL(self):
        platform=cl.get_platforms()[self.openCL.platform]
        self.openCL.devList= platform.get_devices(device_type=self.openCL.type)
        self.openCL.ctx = cl.Context(devices=self.openCL.devList)
        kernelStr=pkg_resources.resource_string(__name__, 'correl.cl')#@UndefinedVariable
        self.openCL.prg = cl.Program(self.openCL.ctx, kernelStr).build()
        self.openCL.queue = cl.CommandQueue(self.openCL.ctx)
        
        if self.openCL.verbose!=0:
            print("===============================================================")
            print("Platform name:", platform.name)
            print("Platform profile:", platform.profile)
            print("Platform vendor:", platform.vendor)
            print("Platform version:", platform.version)
            for device in self.openCL.devList:
                print("---------------------------------------------------------------")
                print("    Device name:", device.name)
                print("    Device type:", cl.device_type.to_string(device.type))
                print("    Device memory: ", device.global_mem_size//1024//1024, 'MB')
                print("    Device max clock speed:", device.max_clock_frequency, 'MHz')
                print("    Device compute units:", device.max_compute_units)
                print("    Device max work items:", device.get_info(cl.device_info.MAX_WORK_ITEM_SIZES))
                print("    Device local memory:", device.get_info(cl.device_info.LOCAL_MEM_SIZE)//1024, 'KB')
                
    def _increment(self, base, interval):
        tmp=base%interval
        if tmp==0:
            return (base, 0)
        else:
            return (base+interval-tmp, interval-tmp)
    
    def reshapeData(self, simulations):
        self.sizes['originalSimulations'], self.sizes['simulationsLength']=simulations.shape
        
        self.sizes['reshaped0'], self.sizes['add0']=self._increment(self.sizes['originalSimulations'], self.openCL.workGroup[0])
        self.sizes['reshaped1'], self.sizes['add1']=self._increment(self.sizes['originalSimulations'], self.openCL.workGroup[1])
        
        if self.openCL.verbose!=0:
            print('Vertical array adjustment: +%.1f%% (%ux %u items)' % (self.sizes['add0']/self.sizes['originalSimulations']*100, self.sizes['reshaped0']//self.openCL.workGroup[0], self.openCL.workGroup[0]))
            print('Horizontal array adjustment: +%.1f%% (%ux %u items)' % (self.sizes['add1']/self.sizes['originalSimulations']*100, self.sizes['reshaped1']//self.openCL.workGroup[1], self.openCL.workGroup[1]))
    
    def compute(self, simulations, window):
        simulationsOpenCL=simulations.reshape(-1, order = 'C').astype(np.float32)
        
        globalSize=(int(self.sizes['reshaped0']), int(self.sizes['reshaped1']))
        localSize=(int(self.openCL.workGroup[0]), int(self.openCL.workGroup[1]))
        
        mf = cl.mem_flags
        base=np.float32(2)
        chromosomeLength=np.int32(self.sizes['simulationsLength'])
        lim0=np.int32(self.sizes['originalSimulations'])
        lim1=np.int32(self.sizes['originalSimulations'])
        window=np.int32(window)
        simulationsBuffer = cl.Buffer(self.openCL.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=simulationsOpenCL)
        outBuffer = cl.Buffer(self.openCL.ctx, mf.WRITE_ONLY, int((self.sizes['originalSimulations']**2)*np.int32(1).nbytes))
        
        kernel=self.openCL.prg.phenCrowding
        
        kernel(self.openCL.queue, globalSize, localSize,
               base, chromosomeLength, window, lim0, lim1,
               simulationsBuffer,
               outBuffer)
        
        crowding = np.zeros((self.sizes['originalSimulations']**2,)).astype(np.float32)
        cl.enqueue_copy(self.openCL.queue, crowding, outBuffer)
        crowding=np.reshape(crowding, (self.sizes['originalSimulations'], -1), order='F')
        
        return crowding