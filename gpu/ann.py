'''
Created in June 2015

@author: Jose Pedro Matos
'''

import numpy as np
import pyopencl as cl
from collections import namedtuple
from scipy.special import expit
import pkg_resources

class Weights:
    def __init__(self, wHL=None, bHL=None, wOL=None, bOL=None):
        self.wHL = wHL
        self.bHL = bHL
        self.wOL = wOL
        self.bOL = bOL
        
class ann:
    openCL = namedtuple('openCL', ('active','devList','ctx','prg','queue', 'workGroup', 'platform', 'type'), verbose=False, rename=False)
    KERNELS = {'lin': 'annLinear.cl',
               'tan': 'annTansig.cl',
               'log': 'annLogsig.cl'}
    
    def __init__(self, data, nodes=10, openCL=False, workGroup=(16, 16), platform=0, deviceType='ALL', verbose=0, activationFunction='tan', lowerThreshold=-999):
        self.data=data
        self.nodes=nodes
        self.openCL.active=openCL
        self.openCL.workGroup=workGroup
        self.openCL.platform=platform
        tmp={'ALL': cl.device_type.ALL, 'CPU': cl.device_type.CPU, 'GPU': cl.device_type.GPU}  # @UndefinedVariable
        self.openCL.type=tmp[deviceType]
        self.activationFuns=(activationFunction, 'lin')
        self.verbose = verbose
        self.setWeights()
        self.lowerThreshold = lowerThreshold
        
        if self.openCL.active:
            self._prepOpenCL()
    
    def __str__(self):
        return 'ANN model\nNodes: %u' % (self.nodes) + \
            '\nOpenCL:\n ' + str(self.openCL.devList) + \
            '\nwHL:\n' + np.array_str(self.weights.wHL) + \
            '\nbHL:\n' + np.array_str(self.weights.bHL) + \
            '\nwOL:\n' + np.array_str(self.weights.wOL) + \
            '\nbOL:\n' + np.array_str(self.weights.bOL)
    
    def _activate(self, X, layer):
        if self.activationFuns[layer]=='log':
            return expit(X)
        elif self.activationFuns[layer]=='tan':
            return 2 / (1 + np.exp(-2*X)) - 1
        else:
            return X
    
    def _prepOpenCL(self):
        platform=cl.get_platforms()[self.openCL.platform]
        self.openCL.devList= platform.get_devices(device_type=self.openCL.type)
        self.openCL.ctx = cl.Context(devices=self.openCL.devList)
        kernelStr=pkg_resources.resource_string(__name__, self.KERNELS[self.activationFuns[0]]) #@UndefinedVariable
        self.openCL.prg = cl.Program(self.openCL.ctx, kernelStr.decode('UTF-8')).build()
        self.openCL.queue = cl.CommandQueue(self.openCL.ctx)
        
        if self.verbose>0:
            print("===============================================================")
            print("Platform name:", platform.name)
            print("Platform profile:", platform.profile)
            print("Platform vendor:", platform.vendor)
            print("Platform version:", platform.version)
            for device in self.openCL.devList:
                print("---------------------------------------------------------------")
                print("    Device name:", device.name)
                print("    Device type:", cl.device_type.to_string(device.type))  # @UndefinedVariable
                print("    Device memory: ", device.global_mem_size//1024//1024, 'MB')
                print("    Device max clock speed:", device.max_clock_frequency, 'MHz')
                print("    Device compute units:", device.max_compute_units)
                print("    Device max work items:", device.get_info(cl.device_info.MAX_WORK_ITEM_SIZES))  # @UndefinedVariable
                print("    Device local memory:", device.get_info(cl.device_info.LOCAL_MEM_SIZE)//1024, 'KB')  # @UndefinedVariable
        
    def getWeightLen(self):
        return (self.data.shape[1]+2)*self.nodes+1
    
    def getWeightsToRegularize(self):
        tmp=np.zeros(self.getWeightLen(), dtype=np.bool)
        tmp[:self.data.shape[1]*self.nodes]=True
        tmp[-self.nodes-1:-1]=True
        return tmp
    
    def setWeights(self, weights=None):
        if weights is None:
            weights=np.random.normal(loc=0, scale=1, size=self.getWeightLen())
            #weights=np.linspace(1, self.getWeightLen(), self.getWeightLen())
        
        if len(weights.shape)==1:
            weights=np.expand_dims(weights, axis=0)
        
        self.weightsOpenCL=np.reshape(weights, (-1,))
        
        tmp=self.data.shape[1]*self.nodes
        wHL=np.reshape(weights[:, :tmp], (-1, self.data.shape[1], self.nodes))
        bHL=np.reshape(weights[:, tmp:tmp+self.nodes], (-1, self.nodes))
        tmp+=self.nodes
        wOL=np.reshape(weights[:, tmp:tmp+self.nodes].T, (self.nodes, -1))
        bOL=np.reshape(weights[:, -1], (-1, 1))
        self.weights=Weights(wHL, bHL, wOL, bOL)
        self.weightsOpenCL=weights
    
    def compute(self, X=[]):
        if len(X)==0:
            X=self.data
        else:
            pass
        
        originalLength=X.shape[0]
        originalWidth=self.weightsOpenCL.shape[0]
        
        if not self.openCL.active:
            raise Exception('openCL not active')
            #===================================================================
            # networks=self.weights.wHL.shape[0]
            # phiOL=np.empty((X.shape[0], networks))
            # for i0 in range(networks):
            #     aHL=X.dot(self.weights.wHL[i0,:,:])+np.tile(self.weights.bHL[i0,],(X.shape[0],1))
            #     phiHL=self._activate(aHL,0)
            #     aOL=phiHL.dot(self.weights.wOL[:,i0])+self.weights.bOL[i0,]
            #     phiOL[:,i0]=self._activate(aOL,1)
            #===================================================================
        else:
            remData=np.remainder(X.shape[0],self.openCL.workGroup[0])
            if remData != 0:
                X=np.vstack((X, np.zeros((self.openCL.workGroup[0]-remData, X.shape[1]))))
            else:
                remData=self.openCL.workGroup[0]
            
            remNetwork=np.remainder(self.weightsOpenCL.shape[0],self.openCL.workGroup[1])
            if remNetwork != 0:
                weights=np.vstack((self.weightsOpenCL, np.zeros((self.openCL.workGroup[1]-remNetwork, self.weightsOpenCL.shape[1]))))
            else:
                weights=self.weightsOpenCL
                remNetwork=self.openCL.workGroup[1]
            
            XOpenCL=X.reshape(-1, order = 'C').astype(np.float32)
            weightsOpenCL=weights.reshape(-1, order = 'C').astype(np.float32)
            
            mf = cl.mem_flags
            inputs=np.int32(X.shape[1])
            nodes=np.int32(self.nodes)
            dataSize=np.int32(X.shape[0])
            weightSize=np.int32(self.weightsOpenCL.shape[1])
            dataBuffer = cl.Buffer(self.openCL.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=XOpenCL)
            weightsBuffer = cl.Buffer(self.openCL.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=weightsOpenCL)
            outBuffer = cl.Buffer(self.openCL.ctx, mf.WRITE_ONLY, int(XOpenCL.nbytes/inputs*weights.shape[0]))
            
            kernel=self.openCL.prg.ann
            globalSize=(int(X.shape[0]), int(weights.shape[0]))
            localSize=(int(self.openCL.workGroup[0]), int(self.openCL.workGroup[1]))
                
            kernel(self.openCL.queue, globalSize, localSize, inputs, nodes, dataSize, weightSize, dataBuffer, outBuffer, weightsBuffer, cl.LocalMemory(self.weightsOpenCL[0,].nbytes*localSize[1]))
            
            phiOL = np.empty((np.prod(globalSize),)).astype(np.float32)
            cl.enqueue_copy(self.openCL.queue, phiOL, outBuffer)
            phiOL=np.reshape(phiOL, globalSize, order='F')[:originalLength,:originalWidth]
        
            if self.lowerThreshold!=-999:
                phiOL[phiOL<self.lowerThreshold] = self.lowerThreshold
        
        return phiOL