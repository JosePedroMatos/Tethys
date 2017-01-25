$(document).ready(function() {
    // Header
    var tmpStr = '';
    for (k0 in data) {
        tmpStr += ' ' + k0 + ' |';
    }
    tmpStr=tmpStr.slice(0, tmpStr.length-1);
    $('#headerText').append(tmpStr + ' ]');
    
    // Errors
    if (errors['noData'].length>0) {
        var tmpStr = 'Some series do not hold any data [ ';
        for (var i0=0; i0<errors['noData'].length; i0++) {
            tmpStr += errors['noData'][i0] + ' | '
        }
        $('#headerText').after('<div id="errors" class="ui-state-error">' + tmpStr.slice(0, tmpStr.length-2) + ']</div>');
    }
    if (errors['noAccess'].length>0) {
        var tmpStr = 'Access authorization to some series is missing [ ';
        for (var i0=0; i0<errors['noAccess'].length; i0++) {
            tmpStr += errors['noAccess'][i0] + ' | '
        }
        $('#headerText').after('<div id="errors" class="ui-state-error">' + tmpStr.slice(0, tmpStr.length-2) + ']</div>');
    }
    if (errors['missing'].length>0) {
        var tmpStr = 'Some series were not found [ ';
        for (var i0=0; i0<errors['missing'].length; i0++) {
            tmpStr += errors['missing'][i0] + ' | '
        }
        $('#headerText').after('<div id="errors" class="ui-state-error">' + tmpStr.slice(0, tmpStr.length-2) + ']</div>');
    }
    
    // Table
    var tmp = $('.summary').children().find('thead').find('tr');
    tmp.append('<th></th>');
	for (var i0=0; i0<fields.length; i0++) {
		tmp.append('<th>' + fields[i0][0] + '</th>');
	}
	tmp.append('<th>Provider</th>');
	tmp.append('<th>Selection</th>');
	
    for (d0 in data) {
    	var tmp = $('.summary').children().find('tbody');
    	tmp.append('<tr>');
    	tmp.append('<td><img src="' + data[d0]['typeIcon'] + '" class="typeIcon"></td>');
    	for (var i0=0; i0<fields.length; i0++) {
    		tmp.append('<td>' + data[d0][fields[i0][1]] + '</td>');
    	}
    	tmp.append('<td><img src="' + data[d0]['providerIcon'] + '" class="providerIcon"><div class="provider">(' + data[d0]['providerAbbreviation'] + ')</div></td>');
    	tmp.append('<td></td>');
    	tmp.append('</tr>');
    	
    	var tmp = $('.summary').children().find('tbody').children('td').last()
    	tmp.append('<input name="series" type="radio" onclick="fSeriesSelect(this);" value="' + data[d0]['name'] + '"></button>');
    }
    
    $("input:button").width(135);
    $("input:button").button();
    
    $("#selectFilter").spinner({step: 0.02,
    	numberFormat: "n",
    	min: 0,
    	max: 1});
    $("#selectFilter").val(0.79);
    
    $("select").width(135);
    $("select").selectmenu();
    $("select").on('selectmenuchange', function() {
    	var tmpForecast = data[$('input[name=series]:checked').val()].forecasts[$("#selectForecast").val()].leadTime;
    	$('#selectHindcast').spinner("value", tmpForecast);
    });
    $(".ui-selectmenu-button span.ui-selectmenu-text").css('padding', '0.2em 0.5em');
    
    $("#selectHindcast").spinner();
    $("#selectHindcast").val(1);
    
    $('#error').hide();
    $('#actions').hide();
    $('#chartLoader').hide();
    $('#table').find('input').first().prop("checked", true).click();
    
    setTimeout(function () {
    	fPlotAvailable();
    },100);
});

function fSeriesSelect(radio) {
    var series = data[radio.value];
    $('#actions').show();
    
    if (Object.keys(series.forecasts).length>0) {
    	$('#forecast').show();
    	$('#hindcast').show();
    	
    	$('#selectForecast').html('');
    	
    	var options = [];
        for (f0 in series.forecasts) {
        	options.push("<option value='" + f0 + "'>" + f0 + "</option>"); 
        }
        $('#selectForecast').append(options.join('')).selectmenu();
        $('#selectForecast').val(f0);
        $("#selectForecast").selectmenu('refresh');
        
        $('#selectHindcast').spinner({
            spin: function(event, ui) {
            	var tmpForecast = data[$('input[name=series]:checked').val()].forecasts[$("#selectForecast").val()].leadTime;
            	if (ui.value > tmpForecast) {
            		$(this).spinner("value", 1);
            		return false;
            	} else if (ui.value < 1) {
            		$(this).spinner("value", tmpForecast);
            		return false;
            	}
            }
    	});
    } else {
    	$('#forecast').hide();
    	$('#hindcast').hide();
    }
}

var forecast;
var observed;
var targets;
var hindcast;
var negativeBands;
var QQ = null;
function showForecast() {
	var tmpForecast = data[$('input[name=series]:checked').val()].forecasts[$("#selectForecast").val()];
	
	if (tmpForecast!=null) {
		forecast = {};
		negativeBands = {};
		QQ = null;
		targets = [];
		var tmpData = {series: $('input[name=series]:checked').val(),
	        	reference: getBoundDates().to.toUTCString()};
    	fClearGraph();
    	$('#QQ,#numeric').html('');
    	$('#error').hide();
    	$('#actions').hide();
        $('#chartLoader').show();
    	
		$.ajax({
	        url : tmpForecast.urlForecast, // the endpoint
	        type : "POST", // http method
	        data : tmpData, // data sent with the post request
	
	        // handle a successful response
	        success : function(json) {
	        	var colors = fGenerateGrays(json.bands.length);
	        	for (var i0=json.bands.length-1; i0>=0; i0--) {
	        		forecast[json.bands[i0]] = [];
	        		for (var i1=0; i1<json.dates.length; i1++) {
	        			forecast[json.bands[i0]].push(new Point(Date.parse(json.dates[i1] + 'Z'), decryptValue(json.values[i0][i1])));
	        		}
	        		display(forecast[json.bands[i0]],  json['timeStepUnits'], json['timeStepPeriod'], null, Math.round(json.bands[json.bands.length-i0-1]*10000)/100 + '%', colors[json.bands.length-1-i0], colors[json.bands.length-1-i0], marker={type: 'forecast'});
	        	}
	        	
	        	// Consider negatives
	        	var colors = fGenerateGrays(json.bands.length);
	        	for (var i0=0; i0<json.bands.length; i0++) {
	        		negativeBands[json.bands[i0]] = [];
	        		for (var i1=0; i1<json.dates.length; i1++) {
	        			var tmp = decryptValue(json.values[i0][i1]);
	        			if (tmp<0) {
	        				negativeBands[json.bands[i0]].push(new Point(Date.parse(json.dates[i1] + 'Z'), tmp));
	        			}
	        		}
	        		display(negativeBands[json.bands[i0]],  json['timeStepUnits'], json['timeStepPeriod'], null, '__dummy__', colors[i0], colors[i0], marker={type: '__dummy__'});
	        	}
	        	
	        	// Targets
	        	for (var i0=0; i0<json.dates.length; i0++) {
	        		if (json.targets[i0]!=null) {
	        			targets.push(new Point(Date.parse(json.dates[i0] + 'Z'), decryptValue(json.targets[i0])));
	        		}
        		}
	        	
	        	// Add data and load legend
	        	if (targets.length>=1) {
	        		var color = '#d35400';
	        		display(targets,  json['timeStepUnits'], json['timeStepPeriod'], null, 'Targets', color, convertHex(color, 0), marker={type: 'targets'});
	        		fPlotAvailable();
		        	
		        	// Turn off data
		        	graph.series[graph.series.length-1].disable()
		        	$('.rickshaw_legend .line:nth-child(1)').addClass('disabled')
		        	graph.update();
	        	} else {
	        		fPlotAvailable();
	        	}
	        	
	        	$('#actions').show();
	            $('#chartLoader').hide();
	        },
	
	        // handle a non-successful response
	        error : function(xhr, errmsg, err) {
	        	$('#error').html("<div class='alert-box alert radius' data-alert>Oops! We have encountered an error: " + err + "</div>"); // add the error to the dom
	            console.log(xhr.status + ": " + xhr.responseText); // provide a bit more info about the error to the console
	            $('#error').show();
	            $('#actions').show();
	            $('#chartLoader').hide();
	            fPlotAvailable();
	        }
	    });
	}
}

function showHindcast() {
	var tmpForecast = data[$('input[name=series]:checked').val()].forecasts[$("#selectForecast").val()];
	
	if (tmpForecast!=null) {
		hindcast = {};
		negativeBands = {};
		QQ = null;
		targets = [];
		var tmpData = {series: $('input[name=series]:checked').val(),
	        	lead: $('#selectHindcast').val(),
	        	from: getBoundDates().from.toUTCString(),
	        	to: getBoundDates().to.toUTCString()};
		fClearGraph();
		$('#QQ,#numeric').html('');
		$('#error').hide();
		$('#actions').hide();
	    $('#chartLoader').show();
		
		$.ajax({
	        url : tmpForecast.urlHindcast, // the endpoint
	        type : "POST", // http method
	        data : tmpData, // data sent with the post request
	
	        // handle a successful response
	        success : function(json) {
	        	// Bands
	        	var colors = fGenerateGrays(json.bands.length);
	        	for (var i0=json.bands.length-1; i0>=0; i0--) {
	        		hindcast[json.bands[i0]] = [];
	        		for (var i1=0; i1<json.dates.length; i1++) {
	        			hindcast[json.bands[i0]].push(new Point(Date.parse(json.dates[i1] + 'Z'), decryptValue(json.values[i0][i1])));
	        		}
	        		display(hindcast[json.bands[i0]],  json['timeStepUnits'], json['timeStepPeriod'], null, Math.round(json.bands[json.bands.length-i0-1]*10000)/100 + '%', colors[json.bands.length-1-i0], colors[json.bands.length-1-i0], marker={type: 'hindcast'});
	        	}
	        	
	        	// Consider negatives
	        	var colors = fGenerateGrays(json.bands.length);
	        	for (var i0=0; i0<json.bands.length; i0++) {
	        		negativeBands[json.bands[i0]] = [];
	        		for (var i1=0; i1<json.dates.length; i1++) {
	        			var tmp = decryptValue(json.values[i0][i1]);
	        			if (tmp<0) {
	        				negativeBands[json.bands[i0]].push(new Point(Date.parse(json.dates[i1] + 'Z'), tmp));
	        			}
	        		}
	        		display(negativeBands[json.bands[i0]],  json['timeStepUnits'], json['timeStepPeriod'], null, '__dummy__', colors[i0], colors[i0], marker={type: '__dummy__'});
	        	}
	        	
	        	// Training
	        	var training = [];
	        	var tmp = Math.max.apply(this, json.values[json.bands.length-1]);
	        	for (var i0=0; i0<json.trainingDates.length; i0++) {
	        		training.push(new Point(Date.parse(json.trainingDates[i0] + 'Z'), tmp));
        		}
	        	var color = '#3333ff';
	        	display(training,  json['timeStepUnits'], json['timeStepPeriod'], null, 'Used for training', convertHex(color, 0.3), convertHex(color, 0.3), marker={type: 'training'});
	        	
	        	// Targets
	        	for (var i0=0; i0<json.dates.length; i0++) {
	        		if (json.targets[i0]!=null) {
	        			targets.push(new Point(Date.parse(json.dates[i0] + 'Z'), decryptValue(json.targets[i0])));
	        		}
        		}
	        	
	        	// Add data and load legend
	        	if (targets.length>=1) {
	        		var color = '#d35400';
	        		display(targets,  json['timeStepUnits'], json['timeStepPeriod'], null, 'Targets', color, convertHex(color, 0), marker={type: 'targets'});
	        		fPlotAvailable();
		        	
		        	// Turn off data
	        		for (var i0=0; i0<Object.keys(data).length; i0++) {
	        			graph.series[graph.series.length-1-i0].disable()
	        			$('.rickshaw_legend .line:nth-child(' + (i0 + 1) + ')').addClass('disabled')
	        		}
		        	
		        	graph.update();
	        	} else {
	        		fPlotAvailable();
	        	}
	        	
	        	// Add QQ plot
	        	drawFigure(json.QQ);
	        	QQ = {'tra': json.QQ.data.data02, 'val':json.QQ.data.data03};
	        	$('#numeric').append(json.traPerformance);
	        	$('#numeric').append(json.valPerformance);
	        	
	        	$('#actions').show();
	            $('#chartLoader').hide();
	        },
	
	        // handle a non-successful response
	        error : function(xhr, errmsg, err) {
	        	$('#error').html("<div class='alert-box alert radius' data-alert>Oops! We have encountered an error: " + xhr.responseJSON.message + "</div>"); // add the error to the dom
	            console.log(xhr.status + ": " + xhr.responseText); // provide a bit more info about the error to the console
	            $('#error').show();
	            $('#actions').show();
	            $('#chartLoader').hide();
	            fPlotAvailable();
	        }
	    });
	}
}

function getBoundDates() {
	var tmp = {from: new Date(graph.x.domain()[0]*1000),
		to: new Date(graph.x.domain()[1]*1000)};
	tmp['fallback'] = new Date(3*tmp.from-2*tmp.to);
	
	return tmp;
}

function getData(from=new Date('1500-01-01'), to=new Date('1999-01-01')) {
	var tmpSeries = $('input[name=series]:checked').val();
	$('#actions').hide();
    $('#chartLoader').show();
	
	if (tmpSeries!=null) {
		var tmpData = {series: tmpSeries,
	        	from: from.toUTCString(),
	        	to: new Date(data[tmpSeries].values[0].x*1000).toUTCString(),
	        	};
		fClearGraph();
		$('#QQ,#numeric').html('');
		QQ = null;
		$.ajax({
	        url : '/timeSeries/getValues/', // the endpoint
	        type : "POST", // http method
	        data : tmpData, // data sent with the post request
	
	        // handle a successful response
	        success : function(json) {
	        	var series = data[tmpSeries];
				if (json.values.length>0) {
					for (var i0=0; i0<series.values.length; i0++) {
						if (series.values[i0].x>json.values[json.values.length-1].x) {
							series.values = series.values.slice(i0, series.values.length);
							break;
						}
					}
					series.values = decryptData(json.values, key=series['key']).concat(series['values']);			
				}
	        	fPlotAvailable();
	        	$('#legend').html('');
	        	addLegend();
	        	$('#actions').show();
	            $('#chartLoader').hide();
	        },
	
	        // handle a non-successful response
	        error : function(xhr,errmsg,err) {
	        	$('#progress').html("<div class='alert-box alert radius' data-alert>Oops! We have encountered an error: "+errmsg+
	                " <a href='#' class='close'>&times;</a></div>"); // add the error to the dom
	            console.log(xhr.status + ": " + xhr.responseText); // provide a bit more info about the error to the console
	            $('#actions').show();
	            $('#chartLoader').hide();
	        }
	    });
	}
}

function mpld3_load_lib(url, callback){
	var s = document.createElement('script');
	s.src = url;
	s.async = true;
	s.onreadystatechange = s.onload = callback;
	s.onerror = function(){console.warn("failed to load library " + url);};
	document.getElementsByTagName("head")[0].appendChild(s);
}

function drawFigure(data) {
	if (typeof (mpld3) !== "undefined" && mpld3._mpld3IsLoaded) {
		// already loaded: just create the figure
		!function(mpld3) {
			mpld3.draw_figure("QQ", data);
		}(mpld3);
	} else if (typeof define === "function" && define.amd) {
		// require.js is available: use it to load d3/mpld3
		require.config({
			paths : {
				d3 : "https://mpld3.github.io/js/d3.v3.min"
			}
		});
		require([ "d3" ], function(d3) {
			window.d3 = d3;
			mpld3_load_lib(
					"https://mpld3.github.io/js/mpld3.v0.2.js",
					function() {
						mpld3.draw_figure("QQ", data);
					});
		});
	} else {
		// require.js not available: dynamically load d3 & mpld3
		mpld3_load_lib(
				"https://mpld3.github.io/js/d3.v3.min.js",
				function() {
					mpld3_load_lib(
							"https://mpld3.github.io/js/mpld3.v0.2.js",
							function() {
								mpld3.draw_figure("QQ", data);
							})
				});
	}
}
