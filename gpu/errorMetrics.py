# coding: utf-8
'''
Created on 06/06/2015

@author: Jose Pedro Matos
'''

import numpy as np
import pyopencl as cl
from collections import namedtuple
import pkg_resources

class errorMetrics(object):
    openCL=namedtuple('openCL', ('active','devList','ctx','prg','queue','verbose'), verbose=False, rename=False)
    sizes=dict()
    
    def __init__(self, targets, stride=100, workGroup=(16, 16), platform=0, deviceType='ALL', verbose=0, errorFunction='MAE'):
        self.targets = targets
        self.stride=stride
        self.openCL.workGroup=workGroup
        self.openCL.platform=platform
        tmp={'ALL': cl.device_type.ALL, 'CPU': cl.device_type.CPU, 'GPU': cl.device_type.GPU}   #@UndefinedVariable 
        self.openCL.type=tmp[deviceType]
        self.openCL.verbose=verbose
        self.errorFunction = errorFunction
        
        self._prepOpenCL()
    
    def _prepOpenCL(self):
        platform=cl.get_platforms()[self.openCL.platform]
        self.openCL.devList= platform.get_devices(device_type=self.openCL.type)
        self.openCL.ctx = cl.Context(devices=self.openCL.devList)
        if self.errorFunction=='MAE':
            kernelFile = 'evalMAE.cl'
        else:
            kernelFile = 'evalMSE.cl'
        kernelStr=pkg_resources.resource_string(__name__, kernelFile)    #@UndefinedVariable
        self.openCL.prg = cl.Program(self.openCL.ctx, kernelStr.decode('UTF-8')).build()
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
                print("    Device type:", cl.device_type.to_string(device.type))    #@UndefinedVariable
                print("    Device memory: ", device.global_mem_size//1024//1024, 'MB')
                print("    Device max clock speed:", device.max_clock_frequency, 'MHz')
                print("    Device compute units:", device.max_compute_units)
                print("    Device max work items:", device.get_info(cl.device_info.MAX_WORK_ITEM_SIZES))    #@UndefinedVariable
                print("    Device local memory:", device.get_info(cl.device_info.LOCAL_MEM_SIZE)//1024, 'KB')   #@UndefinedVariable
          
    def _increment(self, base, interval):
        tmp=base%interval
        if tmp==0:
            return (base, 0)
        else:
            return (base+interval-tmp, interval-tmp)
    
    def reshapeData(self, simulations):
        self.sizes['originalObs'], self.sizes['originalPop']=simulations.shape
        
        tmp0, tmp1=self._increment(self.sizes['originalObs'], self.openCL.workGroup[0]*self.stride)
        tmpGroups=tmp0//self.stride
        self.stride-=int(np.floor(tmp1/tmpGroups))
        
        self.sizes['reshapedObs'], self.sizes['addObs']=self._increment(self.sizes['originalObs'], self.openCL.workGroup[0]*self.stride)
        self.sizes['reshapedPop'], self.sizes['addPop']=self._increment(self.sizes['originalPop'], self.openCL.workGroup[1])
        
        
        self.targets=self.targets.reshape(-1, order = 'C').astype(np.float32)
        
        if self.openCL.verbose!=0:
            print('Vertical array adjustment: +%.1f%% (%u stride, %ux %u items)' % (self.sizes['addObs']/self.sizes['originalObs']*100, self.stride, self.sizes['reshapedObs']//self.stride//self.openCL.workGroup[0], self.openCL.workGroup[0]))
            print('Horizontal array adjustment: +%.1f%% (%ux %u items)' % (self.sizes['addPop']/self.sizes['originalPop']*100, self.sizes['reshapedPop']//self.openCL.workGroup[1], self.openCL.workGroup[1]))
            
    def compute(self, simulations):
        simOpenCL=simulations.reshape(-1, order = 'F').astype(np.float32)
        
        globalSize=(int(np.int32(self.sizes['reshapedObs'])//self.stride), int(self.sizes['reshapedPop']))
        localSize=(int(self.openCL.workGroup[0]), int(self.openCL.workGroup[1]))
        
        mf = cl.mem_flags
        stride=np.int32(self.stride)
        length=np.int32(simulations.shape[0])
        lim0=np.int32(np.ceil(self.sizes['originalObs']/self.stride))
        lim1=np.int32(self.sizes['originalPop'])
        observedBuffer = cl.Buffer(self.openCL.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=self.targets)
        simulatedBuffer = cl.Buffer(self.openCL.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=simOpenCL)
        outErrorBuffer = cl.Buffer(self.openCL.ctx, mf.WRITE_ONLY, int(np.prod(globalSize)*np.int32(1).nbytes))
        outNonExceedanceBuffer = cl.Buffer(self.openCL.ctx, mf.WRITE_ONLY, int(np.prod(globalSize)*np.int32(1).nbytes))
        
        kernel=self.openCL.prg.eval

        kernel(self.openCL.queue, globalSize, localSize,
               stride, length, lim0, lim1,
               observedBuffer, simulatedBuffer,
               outErrorBuffer, outNonExceedanceBuffer)
        
        error = np.empty((np.prod(globalSize),)).astype(np.float32)
        cl.enqueue_copy(self.openCL.queue, error, outErrorBuffer)
        error=np.reshape(error, globalSize, order='F')[:int(self.sizes['reshapedObs']/self.stride),:int(self.sizes['originalPop'])]
        errorMetric=np.sum(error,0)/self.sizes['originalObs']
        
        nonExceedance = np.empty((np.prod(globalSize),)).astype(np.int32)
        cl.enqueue_copy(self.openCL.queue, nonExceedance, outNonExceedanceBuffer)
        nonExceedance=np.reshape(nonExceedance, globalSize, order='F')[:int(self.sizes['reshapedObs']/self.stride),:int(self.sizes['originalPop'])]
        nonExceedanceFraction=(np.sum(nonExceedance,0))/self.sizes['originalObs']

        return (errorMetric, nonExceedanceFraction)
        