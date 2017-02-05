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
    fig = plt.figure(figsize=(9, 9))
    plotAx=[]
    plotAx.append(fig.add_subplot(2, 2, 3))
    plotAx.append(fig.add_subplot(2, 2, 1))
    plotAx.append(fig.add_subplot(2, 2, 4))
    plotAx.append(fig.add_subplot(2, 2, 2))
    plotAx.append(plotAx[-1].twinx())
    
    plt.show(block=False)
    
    blank = True
    hKept = None
    hAlpha = None
    hPi = None
    
    running = True
    while running:
        try:
            data = queue.get(block=False)
        except Empty:
            plt.pause(0.001)
            time.sleep(0.1)
            continue
        
        if data==False:
            plotAx[1].set_ylim([np.min(hKept.get_ydata()), np.max(hKept.get_ydata())])
            plotAx[3].set_ylim([np.min(hAlpha.get_ydata()), np.max(hAlpha.get_ydata())])
            plotAx[4].set_ylim([np.min(hPi.get_ydata()), np.max(hPi.get_ydata())])
                
            plt.show(block=False)
            running = False
        else:  
            # Pareto front
            if blank: 
                if len(data['rejected'])==0:
                    data['rejected'] = data['fit'][data['frontLvls']==np.max(data['frontLvls']), :]
                hRejected, = plotAx[1].plot(data['rejected'][:, 0], data['rejected'][:, 1], 'ok', label='rejected')
                hKept, = plotAx[1].plot(data['fit'][:, 0], data['fit'][:, 1], 'or', label='kept')
                hChosen, = plotAx[1].plot(data['fit'][data['frontLvls']==0, 0], data['fit'][data['frontLvls']==0, 1], 'ob', label='chosen')
                plotAx[1].set_xlim((0, 1))
                updateYLim(data['fit'][:,1], plotAx[1])
                plotAx[1].grid()
                plotAx[1].legend(fontsize=10, numpoints=1)
                plotAx[1].set_xlabel(r'Exceedance, $\eta$')
                plotAx[1].set_ylabel(r'Error metric, $\epsilon$=log$_{10}$(MSE)')
            else:
                hRejected.set_xdata(data['rejected'][:, 0])
                hRejected.set_ydata(data['rejected'][:, 1])
                hKept.set_xdata(data['fit'][:, 0])
                hKept.set_ydata(data['fit'][:, 1])
                hChosen.set_xdata(data['fit'][data['frontLvls']==0, 0])
                hChosen.set_ydata(data['fit'][data['frontLvls']==0, 1])
                
                tmp = plotAx[1].get_ylim()
                if np.min(hChosen.get_ydata())<tmp[0]:
                    plotAx[1].set_ylim((np.min(hChosen.get_ydata()), tmp[1]))
                
            # Data
            if blank:
                if data['normalization']!=None:
                    mean = data['normalization']['mean']
                    std =  data['normalization']['std']
                else:
                    mean = 0
                    std = 1
                
                colors = np.repeat(np.expand_dims(1-np.linspace(0.1, 1, int(np.floor(data['bands'].shape[1]/2))), 1), 3, axis=1)
                x = np.arange(data['bands'].shape[0])
                legendList = []
                for i0 in range(int(np.floor(data['bands'].shape[1]/2))-1, -1, -1):
                    plotAx[0].fill_between(x, data['bands'][:,i0]*std+mean, data['bands'][:,data['bands'].shape[1]-1-i0]*std+mean, facecolor=colors[i0,], linewidth=0, alpha='1', zorder=i0)
                    legendList.append(plt.Rectangle((0, 0), 1, 1, fc=colors[i0,], linewidth=0))
                plotAx[0].plot(data['targets']*std+mean, 'or', label='Observations', zorder=data['bands'].shape[1], alpha=0.8)
                plotAx[0].set_xlim((0, len(data['targets'])))
                updateYLim(data['targets']*std+mean,  plotAx[0])
                
                x0 = plotAx[0].get_xlim()
                x0 = x0[0] + (x0[-1]-x0[0]) * np.linspace(0, 1, len(data['mUniform'])*2+1)[range(1,len(data['mUniform'])*2,2)]
                for i0 in range(len(data['mUniform'])):
                    plotAx[0].plot([x0[i0]]*2, plotAx[0].get_ylim(), '-', zorder=99)
                
                plotAx[0].grid()
                plotAx[0].set_xlabel('$\mathregular{i^{th}}$ observation')
                plotAx[0].set_ylabel('y')
                
                bandLabels = [str(b0*100) + '%' for b0 in data['bandSize']]
                plotAx[0].legend(legendList, bandLabels, fontsize=10, numpoints=1, loc=2)
            else:
                for i0 in range(len(plotAx[0].collections)):
                    plotAx[0].collections.pop(0)
                for i0 in range(int(np.floor(data['bands'].shape[1]/2))-1, -1, -1):
                    plotAx[0].fill_between(x, data['bands'][:,i0]*std+mean, data['bands'][:,data['bands'].shape[1]-1-i0]*std+mean, facecolor=colors[i0,], linewidth=0, alpha='1', zorder=i0)
             
            # QQ
            if blank:
                plotAx[2].plot([0, 1], [0, 1], '--k')
                hQQOverall, = plotAx[2].plot(data['uniform'], data['pValues'], '-k', label='Observations', linewidth=2)
                hQQList = []
                for i0 in range(len(data['mUniform'])):
                    hQQList.append(plotAx[2].plot(data['mUniform'][i0], data['mPValues'][i0], '-', label=str(i0), linewidth=1)[0])
                plotAx[2].grid()
                plotAx[2].set_xlabel('Theoretical quantile of U[0,1]')
                plotAx[2].set_ylabel('Quantile of the observed $p$-value')
                plotAx[2].legend(fontsize=10, numpoints=1, loc=2)
            else:
                #===============================================================
                # hQQOverall.set_xdata(data['uniform'])
                #===============================================================
                hQQOverall.set_ydata(data['pValues'])
                for i0, h0 in enumerate(hQQList):
                    #===========================================================
                    # h0.set_xdata(data['mUniform'][i0])
                    #===========================================================
                    h0.set_ydata(data['mPValues'][i0])
                    
            # Performance
            if blank:
                hAlpha, = plotAx[3].plot(data['epoch'], data['alpha'],'.-k', label=r'$\alpha$')
                hXi, = plotAx[3].plot(data['epoch'], data['xi'],'.-r', label=r'$\xi$')
                hPi, = plotAx[4].plot(data['epoch'], data['pi'],'.-b', label=r'$\pi$')
                
                plotAx[3].grid()
                
                plotAx[3].legend(fontsize=10, numpoints=1, loc=2)
                plotAx[4].legend(fontsize=10, numpoints=1, loc=4)
            else:
                tmp = hAlpha.get_xdata()
                hAlpha.set_xdata(np.append(tmp, data['epoch']))
                hXi.set_xdata(np.append(tmp, data['epoch']))
                hPi.set_xdata(np.append(tmp, data['epoch']))
                
                hAlpha.set_ydata(np.append(hAlpha.get_ydata(), data['alpha']))
                hXi.set_ydata(np.append(hXi.get_ydata(), data['xi']))
                hPi.set_ydata(np.append(hPi.get_ydata(), data['pi']))
                 
                plotAx[3].set_xlim((-1,data['epoch']+1))
                plotAx[4].set_xlim((-1,data['epoch']+1))
                
                if len(tmp)>5:
                    plotAx[3].set_ylim((np.min(hAlpha.get_ydata()[5:]),1))
                    plotAx[4].set_ylim((np.min(hPi.get_ydata()[5:]),np.max(hPi.get_ydata()[-10:])))
                else:
                    plotAx[3].set_ylim((np.min(hAlpha.get_ydata()),1))
                    plotAx[4].set_ylim((np.min(hPi.get_ydata()),np.max(hPi.get_ydata())))
                
                
            blank = False
            
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
            # TODO: handle extrapolations better
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
    #===========================================================================
    # bands = np.array(bands)
    #===========================================================================
    bands = toCustomLogSpace(np.array(bands))
      
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
    
    #===========================================================================
    # bands = toCustomLogSpace(np.array(bands))
    #   
    # for i0 in range(simulations.shape[0]):
    #     tmpBase = simulations[i0,:]
    #     tmp = ~np.isnan(tmpBase)
    #     if np.sum(tmp)>1:
    #         simulations[i0,:] = np.interp(bands, bands[tmp], tmpBase[tmp])
    #     else:
    #         simulations[i0,:] = np.nan
    #===========================================================================
    
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
    #===========================================================================
    # piRel = np.mean(np.abs(expected)/np.sqrt(expected2-np.square(expected)))
    #===========================================================================
    pi = np.mean(1/np.sqrt(expected2-np.square(expected)))
    return (alpha, xi, pi)

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