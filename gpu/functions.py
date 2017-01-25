'''
Created on 10 nov. 2016

@author: José Pedro Matos
'''
import time
import warnings
import numpy as np
import matplotlib.pyplot as plt
import mpld3
from mpld3 import utils, plugins

from queue import Empty
from scipy.interpolate.interpolate import interp1d

def plot(queue):
    fig = plt.figure(figsize=(10, 10))
    plotAx=[]
    plotAx.append(fig.add_subplot(2, 1, 2))
    plotAx.append(fig.add_subplot(2, 2, 1))
    plotAx.append(fig.add_subplot(2, 2, 2))
    
    plt.show(block=False)
    
    while True:
        try:
            data = queue.get(block=False)
        except Empty:
            plt.pause(0.5)
            time.sleep(0.5)
            continue
        
        if data==False:
            break
        else:
            for a0 in plotAx:
                for i0 in range(len(a0.lines)):
                    a0.lines.pop(0)
         
            # Pareto front
            if len(data['rejected'])>0:
                plotAx[1].plot(data['rejected'][:,0], data['rejected'][:,1], 'ok', label='rejected')
            plotAx[1].plot(data['fit'][:,0], data['fit'][:,1], 'or', label='kept')
            plotAx[1].plot(data['fit'][data['frontLvls']==0,0], data['fit'][data['frontLvls']==0,1], 'ob', label='chosen')
            plotAx[1].set_xlim((0,1))
            updateYLim(data['fit'][:,1], plotAx[1])
            plotAx[1].grid()
            plotAx[1].legend(fontsize=10, numpoints=1)
             
            # Fitness
            plotAx[0].plot(data['targets'], 'ob', label='Observations')
            for i0 in range(data['bands'].shape[1]):
                if i0 == 0:
                    plotAx[0].plot(data['bands'][:, i0], '--r', alpha=0.5, label='Bands', linewidth=1)
                else:
                    plotAx[0].plot(data['bands'][:, i0], '--r', alpha=0.5, linewidth=1)
            plotAx[0].plot(data['best'], '-r', label='Best', linewidth=2)
            plotAx[0].set_xlim((0, len(data['targets'])))
            updateYLim(data['targets'],  plotAx[0])
            plotAx[0].grid()
            plotAx[0].legend(fontsize=10, numpoints=1)
             
            # QQ
            plotAx[2].plot([0, 1], [0, 1], '--k')
            plotAx[2].plot(data['uniform'], data['pValues'], '-r', label='Observations')
            plotAx[2].grid()

    plt.clf()

def updateYLim(data, axis):
        axis.set_ylim((np.floor(np.min(data)-0.25), np.ceil(np.max(data)+1)))

def predictiveQQ(simulations, targets, bands):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
    bands = toCustomLogSpace(np.array(bands)[::-1])
    pValues = np.empty_like(targets)
    for i0 in range(pValues.shape[0]):
        sims, idxs = np.unique(simulations[i0,:],return_index=True)
        try:
            pValues[i0] = interp1d(sims, bands[idxs], kind='linear', assume_sorted=True)(targets[i0])
        except np.linalg.linalg.LinAlgError as ex:
            pValues[i0] = np.nan
        except ValueError as ex:
            # TODO: handle better extrapolations
            if targets[i0]<sims[0]:
                pValues[i0] = bands[0]+(bands[0]-bands[1])/(sims[0]-sims[1])*(targets[i0]-sims[0])
            else:
                pValues[i0] = bands[-1]+(bands[-1]-bands[-2])/(sims[-1]-sims[-2])*(targets[i0]-sims[-1])
    pValues = fromCustomLogSpace(pValues)
    pValues[pValues<0] = 0
    pValues[pValues>1] = 1
    
    pValues = np.sort(1-pValues[np.logical_not(np.isnan(pValues))])
    return (np.linspace(0,1, pValues.shape[0]), pValues)

def toCustomLogSpace(x):
        y = np.empty_like(x)
        tmp = x<0.5
        y[tmp] = np.log(x[tmp])-np.log(0.5)
        tmp = np.logical_not(tmp)
        y[tmp] = -np.log(1-x[tmp])+np.log(0.5)
        return y
        
def fromCustomLogSpace(y):
    x = np.empty_like(y)
    tmp = y<0
    x[tmp] = np.exp(y[tmp]+np.log(0.5))
    tmp = np.logical_not(tmp)
    x[tmp] = 1-np.exp(-y[tmp]+np.log(0.5))
    return x

def processBands(simulations, bands):
    bands = np.array(bands)
    
    for i0 in range(simulations.shape[0]):
        tmpBase = simulations[i0,:]
        tmp = ~np.isnan(tmpBase)
        tmpBase[tmp] = np.sort(tmpBase[tmp])
        if np.sum(tmp)>=2:
            tmp = tmpBase[-1]
            for i1 in range(len(tmpBase)-2, 0, -1):
                if np.isnan(tmp):
                    tmp = tmpBase[i1]
                else:
                    if ~np.isnan(tmpBase[i1]):
                        if np.round(tmp,6)<=np.round(tmpBase[i1],6):
                            tmpBase[i1] = np.nan
                        else:
                            tmp = tmpBase[i1]
            tmp = ~np.isnan(tmpBase)
            if np.sum(tmp)>1:
                simulations[i0,:] = np.interp(bands, bands[tmp], tmpBase[tmp])
            else:
                simulations[i0,:] = np.nan
        else:
            simulations[i0,:] = np.nan
    return simulations
    
def metrics(uniform, pValues, simulations, bandBounds):
    # alpha
    alpha = 1-2*np.mean(np.abs(pValues-uniform));
    # xi
    xi = np.zeros_like(pValues)
    xi[np.logical_or(pValues==1, pValues==0)] = 1
    xi = 1-np.mean(xi)
    # piRel
    bandProb = bandBounds[1,:]-bandBounds[0,:]
    expected = np.sum(simulations * np.tile(bandProb,(simulations.shape[0],1)), axis=1)
    expected2 = np.sum(np.square(simulations) * np.tile(bandProb,(simulations.shape[0],1)), axis=1)
    piRel = np.mean(np.abs(expected)/np.sqrt(expected2-np.square(expected)))
    return (alpha, xi, piRel)

def plotQQ(tra, val, bands):
    fig = plt.figure(figsize=(4.5, 4.2))
    #===========================================================================
    # fig.patch.set_facecolor('black')
    #===========================================================================
    plotAx=[]
    plotAx.append(fig.add_subplot(1, 1, 1))
     
    # QQ
    plotAx[0].plot([0, 1], [0, 1], '--k')
    if len(tra[0])>0:
        tmp = np.unique(np.linspace(0, len(tra[0])-1, 200, dtype=np.int))
        plotAx[0].plot(tra[0][tmp], tra[1][tmp], '-b', label='Training')
    if len(val[0])>0:
        tmp = np.unique(np.linspace(0, len(val[0])-1, 200, dtype=np.int))
        plotAx[0].plot(val[0][tmp], val[1][tmp], '-r', label='Validation')
    plotAx[0].set_xlim((0,1))
    plotAx[0].set_ylim((0,1))
    plotAx[0].grid(True)
    plotAx[0].set_xlabel('Theoretical quantile of U[0,1]')
    plotAx[0].set_ylabel('Quantile of the observed p-value')
    plotAx[0].legend(fontsize=10, numpoints=1, title='')
    
    #===========================================================================
    # for text in l.get_texts():
    #     text.set_color("white")
    # #===========================================================================
    # # plotAx[0].spines['bottom'].set_color('white')
    # # plotAx[0].spines['top'].set_color('white') 
    # # plotAx[0].spines['right'].set_color('white')
    # # plotAx[0].spines['left'].set_color('white')
    # #===========================================================================
    # plotAx[0].tick_params(axis='x', colors='white')
    # plotAx[0].tick_params(axis='y', colors='white')
    # plotAx[0].yaxis.label.set_color('white')
    # plotAx[0].xaxis.label.set_color('white')
    # plotAx[0].set_axis_bgcolor('black')
    #===========================================================================
    
    plotDict = mpld3.fig_to_dict(fig)
    plt.close(fig)
    return plotDict

class ClickInfo(plugins.PluginBase):
    """Plugin for getting info on click"""
    
    JAVASCRIPT = """
    mpld3.register_plugin("clickinfo", ClickInfo);
    ClickInfo.prototype = Object.create(mpld3.Plugin.prototype);
    ClickInfo.prototype.constructor = ClickInfo;
    ClickInfo.prototype.requiredProps = ["id", "state", "styles", "marker"];
    function ClickInfo(fig, props){
        mpld3.Plugin.call(this, fig, props);
    };
    
    ClickInfo.prototype.draw = function(){
        var obj = mpld3.get_element(this.props.id);
        var state = this.props.state;
        var styles = this.props.styles;
        var marker = this.props.marker;
        
        function update(object, styles, state) {
            if (state) {
                d3.select(object).style('fill', styles[state].fill);
            } else {
                d3.select(object).style('fill', styles[state].fill);
            }
        }
        
        var info = this.props.info;
        obj.elements().on("mousedown",
            function(d, i){
                state = !state;
                console.log(marker);
                update(this, styles, state);
            }
        );
    }
    """
    def __init__(self, points, state, styles, marker):
        self.dict_ = {'type': 'clickinfo',
                      'id': utils.get_id(points),
                      'state': state,
                      'styles': styles,
                      'marker': marker}