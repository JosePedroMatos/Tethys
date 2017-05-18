function fTest() {
	if (graph) {
		graph.window.xMin = (graph.window.xMin + graph.window.xMax)/2;
		graph.update();
		
		var values = [graph.window.xMin, graph.window.xMax];
	
	    if (graph.window.xMin == undefined || isNaN(graph.window.xMin)) {
	        values[0] = graph.dataDomain()[0];
	    }
	    if (graph.window.xMax == undefined || isNaN(graph.window.xMax)) {
	        values[1] = graph.dataDomain()[1];
	    }
	
		$(slider.element).slider('option', 'values', values);
		console.log($(slider.element).slider('option', 'values'));
	}
}

// prepare graph
var graph = null;
var graphData = [];

var slider;
var previewSlider;
var xAxis;
var yAxis;
var legend;
var shelving;
var palette

function clearChart() {
	$('#chart').html('');
	$('#slider').html('');
	$('#legend').html('');
	graph = null;
	graphData = [];
	
	palette = new Rickshaw.Color.Palette({ scheme: 'classic9' });
}

function Point(x, y) {
	this.x = x/1000;
	this.y = y;
};
		
function convertHex(hex, opacity){
	hex = hex.replace('#','');
	r = parseInt(hex.substring(0,2), 16);
	g = parseInt(hex.substring(2,4), 16);
	b = parseInt(hex.substring(4,6), 16);
			
	result = 'rgba('+r+','+g+','+b+','+opacity+')';
	return result;
}

function timeStepDelta(t0, timeStep, timeStepSize) {
	t0 = new Date(t0);
	var t1 = new Date(t0.getTime());
	var t2 = new Date(t0.getTime());
	switch(timeStep) {
		case 'second':
	        t1.setTime(t0.getTime() + timeStepSize*1000);
	        t2.setTime(t0.getTime() + timeStepSize*1000*1.25); break;
	    case 'minute':
	        t1.setTime(t0.getTime() + timeStepSize*60000);
	        t2.setTime(t0.getTime() + timeStepSize*60000*1.25); break;
	    case 'hourly':
	        t1.setTime(t0.getTime() + timeStepSize*3600000);
	        t2.setTime(t0.getTime() + timeStepSize*3600000*1.25); break;
	    case 'daily':
	    	t1.setDate(t0.getDate() + timeStepSize);
	    	t2.setDate(t0.getDate() + timeStepSize);
	    	t2.setTime(t2.getTime() + 2*3600000); break;	// add two hours
	    case 'weekly':
	    	t1.setDate(t0.getDate() + timeStepSize*7);
	    	t2.setDate(t0.getDate() + timeStepSize*7+2); break; // add two days
	    case 'monthly':
	    	t1.setMonth(t0.getMonth() + timeStepSize);
	    	t2.setMonth(t0.getMonth() + timeStepSize); 
	    	t2.setDate(t2.getDate() + 2); break; break; // add two days
	    case 'yearly':
	    	t1.setFullYear(t0.getFullYear() + timeStepSize);
	    	t2.setFullYear(t0.getFullYear() + timeStepSize);
	    	t2.setDate(t2.getDate() + 2); break; break; // add two days
	    default:
	    	t1 = null;
	        console.log('timeStep Unknown [' + timeStep + ']... please edit template.');
	}
	return [t1.getTime(), t2.getTime()];
}

//sort data
function sortData(data) {
	data.sort(function(a,b) {
		return a.x - b.x;
	});
	return data;
};

// fill missing data
function fillMissing(data, timeStep, timeStepSize) {
	var dataForDisplayFilled = [];
	dataForDisplayFilled.push(new Point(data[0].x*1000, data[0].y));
	for (var i0=1; i0<data.length; i0++) {
		var tmpRef0 = data[i0-1].x*1000;
		var tmpRef1 = data[i0].x*1000;
	
		var tmp = timeStepDelta(tmpRef0, timeStep, timeStepSize);
		while (tmpRef1>tmp[1]) {
			// add null point
			tmpRef0 = tmp[0];
			dataForDisplayFilled.push(new Point(tmpRef0, null));
			tmp = timeStepDelta(tmpRef0, timeStep, timeStepSize);
		}
		dataForDisplayFilled.push(new Point(tmpRef1, data[i0].y));
	}
	return dataForDisplayFilled;
};

function startChart(strokeColor, fillColor) {
	graph = new Rickshaw.Graph({
		element: document.querySelector("#chart"),
		stroke: true,
		unstack : true,
		renderer: 'area',
		//interpolation: 'step-before',
		interpolation: 'linear',
		series: graphData,
		min: 'auto',
	});
	return graph;
}

function display(dataForDisplay, timeStep, timeStepSize, order=null, name='unknown', strokeColor=null, fillColor=null, fillAlpha=0.8, marker={type: 'data'}) {
	if (dataForDisplay.length==0) {
		return false;
	}
	if (strokeColor===null) {
		strokeColor = palette.color();
	}
	if (fillColor===null) {
		fillColor = convertHex(strokeColor, fillAlpha);
	}
	
	if (graph===null) {
		graphData.push({data: fillMissing(sortData(dataForDisplay), timeStep, timeStepSize),
			color: fillColor,
			stroke: strokeColor,
			name: name,
			marker: marker,
		});
		graph = startChart(strokeColor, fillColor);
	} else {
		if (order===null || graphData.length<order) {
			graphData.push({
				color: fillColor,
				stroke: strokeColor,
				data: fillMissing(sortData(dataForDisplay), timeStep, timeStepSize),
				name: name,
				marker: marker,
			});
		} else {
			graphData[order] = {
				color: fillColor,
				stroke: strokeColor,
				data: fillMissing(sortData(dataForDisplay), timeStep, timeStepSize),
				name: name,
				marker: marker,
			};
		}
		graph.update();
	}
				
	xAxis = new Rickshaw.Graph.Axis.X({
	    graph: graph,
	    ticks: 5,
	    tickFormat: function(x){
	    	var d = new Date(x * 1000);
        	return d.getFullYear() + '/' + (d.getMonth()+1) + '/' + d.getDate() + ' ' + d.getHours() + ':' + d.getMinutes();
        }
	});
				
	yAxis = new Rickshaw.Graph.Axis.Y({
		graph: graph,
	});
	
	slider = new Rickshaw.Graph.RangeSlider({
		graph: graph,
		element: document.querySelector('#slider'),
	});
	
	/*previewSlider = new Rickshaw.Graph.RangeSlider.Preview({
	graph: graph,
	element: document.querySelector('#slider'),
	});*/
	
	graph.render();
	xAxis.render();
	yAxis.render();
};

function addLegend(shelving=true) {
	$('#legend').html('');
	
	legend = new Rickshaw.Graph.Legend( {
		graph: graph,
		element: document.getElementById('legend')
	});
	if (shelving) {
		shelving = new Rickshaw.Graph.Behavior.Series.Toggle( {
			graph: graph,
			legend: legend
		});
	}
	var tmp = $('#legend').find('.swatch');
	for (var i0=0; i0<graph.series.length; i0++) {
		if (graph.series[i0].name=='__dummy__') {
			tmp.eq(graph.series.length-i0-1).parent('li').remove();
		} else {
			if (graph.series[i0].color != graph.series[i0].stroke) {
				tmp.eq(graph.series.length-i0-1).css('background-color', eval(graph.series[i0].color));
			}
		}
	}
}

function fClearGraph() {
	$('#chartContainer').html(
			'<div id="chart"></div><div id="slider"></div><div id="legend"></div>'
			);
	graph = null;
	graphData = [];
}

function fPlotAvailable() {
	palette = new Rickshaw.Color.Palette({ scheme: 'classic9' });
	palette.color(); palette.color(); palette.color();
	
	for (var i0=0; i0<valid.length; i0++) {
		var series = data[valid[i0]];
		//display(series['values'], series['timeStepUnits'], series['timeStepPeriod'], order=series['order'], name=series['name']);
		var color = palette.color();
		display(series['values'], series['timeStepUnits'], series['timeStepPeriod'], order=null, name=series['name'], color, convertHex(color, 0), marker={type: 'data'});
	}
	addLegend();
}

function fFilter() {
	var series = data[$('input[name=series]:checked').val()];
	var beta = $("#selectFilter").val();
	var color = palette.color();
	
	var filledData = fillMissing(sortData(series.values), series.timeStepUnits, series.timeStepPeriod);
	
	var betaInt = beta;
	var lastValid;
	for (var i0=1; i0<filledData.length; i0++) {
		if (filledData[i0].y != null) {
			if (filledData[i0-1].y != null) {
				// all ok
				filledData[i0].y = filledData[i0-1].y+(1-beta)*(filledData[i0].y-filledData[i0-1].y);
			} else {
				// restart
				filledData[i0].y = lastValid+(1-betaInt)*(filledData[i0].y-lastValid);
			}
			lastValid = filledData[i0].y;
			betaInt = beta;
		} else {
			// missing
			betaInt *= beta;
		}
	}
	
	display(filledData, series.timeStepUnits, series.timeStepPeriod, order=null, name='filter(' + series['name'] +', ' + beta + ')', color, convertHex(color, 0), marker={type: 'filter'});
	addLegend();
}

function fGenerateGrays(number) {
	var colors = [];
	for (var i0=0; i0<number/2; i0++) {
		tmp = Math.round((i0+1)/(number/2)*255);
		colors.push(rgbToHex(tmp, tmp, tmp));
	}
	for (var i0=number/2-2; i0>=0; i0--) {
		colors.push(colors[i0]);
	}
	colors.push(rgbToHex(0, 0, 0));
	return colors;
}

function rgba(r, g, b, a) {
	return rgbToHex(r, g, b);
}

function rgbToHex(r, g, b) {
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}