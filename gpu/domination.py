'''
Created on 2 juin 2015

@author: Jose Pedro Matos
'''

import numpy as np
import matplotlib.pyplot as plt

def paretoSorting(x0, x1):
    fronts=list()
    idx=np.lexsort((x1, x0))
    
    fronts.append(list())
    fronts[-1].append(idx[0])
    for i0 in idx[1:]:
        if x1[i0]>=x1[fronts[-1][-1]]:
            fronts.append(list())
            fronts[-1].append(i0)
        else:
            for i1 in range(0,len(fronts)):
                if x1[i0]<x1[fronts[i1][-1]]:
                    fronts[i1].append(i0)
                    break
        
    return (fronts, idx)

def doubleParetoSorting(x0, x1):
    fronts = [[]]
    left = [[]]
    right = [[]]
    idx = np.lexsort((x1, x0))
    
    idxEdge = np.lexsort((-np.square(x0-0.5), x1))
    
    fronts[-1].append(idxEdge[0])
    left[-1].append(x0[idxEdge[0]])
    right[-1].append(x0[idxEdge[0]])
    for i0 in idxEdge[1:]:
        if x0[i0]>=left[-1] and x0[i0]<=right[-1]:
            #add a new front
            fronts.append([])
            left.append([])
            right.append([])
            fronts[-1].append(i0)
            left[-1].append(x0[i0])
            right[-1].append(x0[i0])
        else:
            #check existing fonts
            for i1 in range(len(fronts)):
                if x0[i0]<left[i1] or x0[i0]>right[i1]:
                    if x0[i0]<left[i1]:
                        left[i1] = x0[i0]
                        fronts[i1].insert(0, i0)
                    else:
                        right[i1] = x0[i0]
                        fronts[i1].append(i0)
                    break    
    return (fronts, idx)

def plotFronts(fronts, x0, x1, **kwargs):
    fig=plt.figure()
    ax=plt.gca()
    if 'size' in kwargs:
        ax.scatter(x0, x1, c='k', s=kwargs['size'])
    else:
        ax.plot(x0, x1,'ok')
    for l0 in fronts:
        tmp0=x0[l0]
        tmp1=x1[l0]
        ax.plot(tmp0, tmp1,'-')
        
    if 'annotate' in kwargs and kwargs['annotate']:
        for label, x, y in zip(range(0,len(x0)), x0, x1):
            plt.annotate(
            label, 
            xy = (x, y), xytext = (-10, 10),
            textcoords = 'offset points', ha = 'right', va = 'bottom',
            arrowprops = dict(arrowstyle = '->', connectionstyle = 'arc3, rad=-0.2'))
            
    return fig

def convexSortingApprox(x0, x1):
    ''' does not work well '''
    fronts0=paretoSorting(x0, x1)[0]
    fronts1=paretoSorting(-x0, x1)[0]
    
    minErrIdx=np.argmin(x1)
    minErrNE=x0[minErrIdx]
    
    fronts=[]
    len0=len(fronts0)
    len1=len(fronts1)
    for i0 in range(max(len0, len1)):
        tmpList=[]
        if len0>i0:
            tmp=x0[fronts0[i0]]<=minErrNE
            tmpList.extend(np.array(fronts0[i0])[tmp])
        if len1>i0:
            tmp=x0[fronts1[i0]]>minErrNE
            tmpList.extend(np.array(fronts1[i0])[tmp])
        fronts.append(tmpList)
    return fronts

def convexSorting(x0, x1):
    #===========================================================================
    # fronts, idx=paretoSorting(x0, x1)
    #===========================================================================
    fronts, idx=doubleParetoSorting(x0, x1)
    
    lastChanged=0
    for i0 in range(len(fronts)):
        if len(fronts[i0])>0:
            for i1 in range(lastChanged-1,i0-1,-1):
                tmp=list()
                for l0 in reversed(fronts[i1+1]):
                    if len(fronts[i1])==0 or x0[fronts[i1][-1]]<x0[l0] and x1[fronts[i1][-1]]>x1[l0]:
                        tmp.insert(0,fronts[i1+1].pop())
                if len(tmp)>0:
                    fronts[i1].extend(tmp)
            
            for i1 in range(i0+1, len(fronts)):
                if len(fronts[i1])>0 and x0[fronts[i0][-1]]<x0[fronts[i1][-1]]:
                    fronts[i0].append(fronts[i1].pop())
                    lastChanged=i1
        
        #=======================================================================
        # if i0 in range(len(fronts)-23,len(fronts)-20):
        #     plotFronts(fronts, x0, x1)
        #     plt.show(block=False)     
        #=======================================================================

    for i0 in range(len(fronts)-1,-1,-1):
        if len(fronts[i0])==0:
            fronts.pop(i0)
    
    return (fronts, idx)