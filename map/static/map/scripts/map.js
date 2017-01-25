// Prepare Map layer
var layer;
var map;
$(document).ready(function () {
	layer=new ol.layer.Tile({
		source: new ol.source.OSM({
		}),
	});
	map = new ol.Map({
		target: 'map',
		layers: [layer,],
		view: new ol.View({
			projection: 'EPSG:4326',
			center: [0, 0],
			zoom: 4,
			minZoom: 2,
			extent: [-25,-40, 65, 40],
		}),
		loadTilesWhileInteracting: true,
	});
});

// Prepare WebGL
var zoomChangeRequest = 0;
var zoomRecenter;
var spriteScale;
var extent = [];
var drag = false;
var intersected;

var scene;
var camera;
var renderer;
var raycaster;
var mouse;
$(document).ready(function () {
	scene = new THREE.Scene();
	camera = new THREE.OrthographicCamera(window.innerWidth/-2, window.innerWidth/2, window.innerHeight/2, window.innerHeight/-2, 100, -100);
	camera.position.set(0, 0, 1);

	//Add renderer
	renderer = new THREE.WebGLRenderer( { alpha: true,  canvas: $('canvas#webGL')[0]} );
	renderer.setSize( window.innerWidth, window.innerHeight );
	renderer.setClearColor( 0x000000, 0 );
	renderer.sortObjects = true;
	document.body.appendChild( renderer.domElement );
	
	//Add lighting
	scene.add(new THREE.AmbientLight(0xf5f5f5));
	
	//Add raycaster
	raycaster = new THREE.Raycaster();
	mouse = new THREE.Vector2();
	
	//Set handles and disables
	$(document).on('keydown', function(e){
	    if (e.keyCode === 0 || e.keyCode === 32) {
	        $('#map').css('z-index', 99);
	        $('#rasterPannel').css('z-index',-1)
	        drag = true;
	    }
	});

	$(document).on('keyup', function(e){
	    if (e.keyCode != 0 || e.keyCode != 32) {
	        $('#map').css('z-index', -1);
	        $('#rasterPannel').css('z-index', 99)
	        drag = false;
	        fSetExtent();
	    }
	});
	
	window.addEventListener('resize', onWindowResize, false);
	
	// handle zoom requests
	$('canvas#webGL').mousewheel(fZoomRequest);
	
	$('#webGL').contextmenu(function() {
	    return false;
	});

	$('#map').contextmenu(function() {
	    return false;
	});
	
	$('canvas#webGL').mousemove(function (event) {
		// calculate mouse position in normalized device coordinates
		// (-1 to +1) for both components
		mouse.x = ( event.clientX / window.innerWidth ) * 2 - 1;
		mouse.y = - ( event.clientY / window.innerHeight ) * 2 + 1;
	});
	
	$('#webGL').click(function() {
	    raycaster.setFromCamera( mouse, camera );
	    raycaster.ray.origin.z = 0;
	    
	    var intersects = raycaster.intersectObjects(scene.children);
	    var i0 = 0;
	    if (intersects) {
	    	if (intersects.length>=1 && intersects[i0].object.callback!=null) {
	    		intersects[i0].object.callback();
	    	};
	    };
	});
		
	//Start WebGL
	render();
	fSetExtent();
	spriteScale = fResizeSprites();
	
	setTimeout(function() {
		$('.dg').css('font', 'small Verdana, Arial, sans-serif');
	}, 100);
});

function fZoomRequest(event) {
	zoomRecenter = [];
		
	var tmpExtent = fGetExtent();
	var perX = event.pageX/window.innerWidth-1/2;
	var perY = -event.pageY/window.innerHeight+1/2;
		
	zoomRecenter.push((tmpExtent[2]+tmpExtent[0])/2+perX*(tmpExtent[2]-tmpExtent[0])); //lat
	zoomRecenter.push((tmpExtent[3]+tmpExtent[1])/2+perY*(tmpExtent[3]-tmpExtent[1])); //lon
	zoomRecenter.push(perX);
	zoomRecenter.push(perY);
		
	zoomChangeRequest = event.deltaY;
}

function onWindowResize() {
	camera.aspect = window.innerWidth / window.innerHeight;
	camera.left = window.innerWidth/-2;
	camera.right = window.innerWidth/2;
	camera.top = window.innerHeight/2;
	camera.bottom = window.innerHeight/-2;
	camera.updateProjectionMatrix();
	renderer.setSize(window.innerWidth, window.innerHeight);
}

function fGetExtent() {
    var extent = [camera.position.x+camera.left/camera.zoom,
              camera.position.y+camera.bottom/camera.zoom,
              camera.position.x+camera.right/camera.zoom,
              camera.position.y+camera.top/camera.zoom];
    return extent;
};

function fSetExtent() {
    camera.zoom = 1/map.getView().getZoom();
    var extent = map.getView().calculateExtent(map.getSize());
    
	camera.left = (extent[0]-camera.position.x)*camera.zoom;
    camera.bottom = (extent[1]-camera.position.y)*camera.zoom;
    camera.right = (extent[2]-camera.position.x)*camera.zoom;
    camera.top = (extent[3]-camera.position.y)*camera.zoom;
    
    camera.updateProjectionMatrix();
    
    return [camera.position.x+camera.left/camera.zoom,
           camera.position.y+camera.bottom/camera.zoom,
           camera.position.x+camera.right/camera.zoom,
           camera.position.y+camera.top/camera.zoom];
};

function equalArrays(a, b) {
	if (a.length!=b.length) {
		return false;
	};
		
	for (i0 = 0; i0 < a.length; i0++) {
		if (a[i0]!=b[i0]) {
			return false;
		}
	};
		
	return true;
};

function fResizeSprites() {
	var extent = fGetExtent();
	var degPerPixel = (extent[2]-extent[0])/window.innerWidth;
	var spriteScale = degPerPixel*40;
	for (k0 in seriesControllers) {
		if (k0 != "undefined" && seriesControllers[k0].webGLObject != null) {
			seriesControllers[k0].webGLObject.scale.set(spriteScale, spriteScale, 0);
		}
	}
	return spriteScale;
}

function render() {
    if (zoomChangeRequest != 0) {
    	//zoom change request
    	map.getView().setZoom(map.getView().getZoom() + zoomChangeRequest);
    	zoomChangeRequest = 0;
    	
    	var tmpExtent = map.getView().calculateExtent(map.getSize());

    	var tmpX = zoomRecenter[0]-zoomRecenter[2]*(tmpExtent[2]-tmpExtent[0]);
    	var tmpY = zoomRecenter[1]-zoomRecenter[3]*(tmpExtent[3]-tmpExtent[1]);

    	map.getView().setCenter([tmpX, tmpY]);
    	tmpExtent = map.getView().calculateExtent(map.getSize());

    	camera.position.x = map.getView().getCenter()[0];
		camera.position.y = map.getView().getCenter()[1];
		
		extent = fSetExtent();
        
		// change sprite scales
		spriteScale = fResizeSprites();
		
    } else if (!equalArrays(extent, fGetExtent())) {
    	if (!drag) {
    		camera.position.x = map.getView().getCenter()[0];
    		camera.position.y = map.getView().getCenter()[1];
    		
    		extent = fSetExtent();
    		
    		// extent change request
    		map.getView().fit(
    			fGetExtent(), 
                map.getSize(), 
                {padding: [0,0,0,0]}
                );
    	}
    	
    }
    
    // update raster
    if (rasterInfo.name!=null){
    	try {
    		var tmp = closerTimedate($('#dateSlider').slider('value'), rasterDates);
    		$('#dateSlider').slider('value', tmp);
    		updateDateText();
    		
	    	tmpDateProduct = $('#dateSlider').slider('value') + '__' + rasterInfo.name;
	        if (dateProduct != tmpDateProduct) {
	        	dateProduct = tmpDateProduct;
	        	updateRaster($('#dateSlider').slider('value'));
	        	var a = 1;
		    }
		} catch (ex) {
			//console.log(ex);
		}
    }
    
    // raycaster
	raycaster.setFromCamera( mouse, camera );
	raycaster.ray.origin.z = 0;
	
	var intersects = raycaster.intersectObjects( scene.children );
	if (intersects.length > 0) {
		if (intersected!=intersects[0].object && intersects[0].object.type=='Sprite') {
			if (intersected) {
				intersected.material.color = intersected.color;
				intersected.scale.set(spriteScale, spriteScale, 0);
			}

			intersected = intersects[0].object;
			intersected.color = intersected.material.color;
			intersected.material.color = new THREE.Color("rgb(127, 78, 27)");
			intersected.scale.set(spriteScale/40*50, spriteScale/40*50, 0);
		}
	} else {
		if (intersected) {
			intersected.material.color = intersected.color;
			intersected.scale.set(spriteScale, spriteScale, 0);
		}
		intersected = null;
	}
    
    requestAnimationFrame(render);
    renderer.clear();
    renderer.render(scene, camera);
}


function closerTimedate(d0, a0) {
	var closest = a0.reduce(function (prev, curr) {
		return (Math.abs(curr - d0) < Math.abs(prev - d0) ? curr : prev);
	});
	return closest;
}

function updateRaster(date, colormap) {
	try {
		var idx = $.inArray(date, rasterDates);
		var tmpData = rasterDateController[idx];
		
		for (var k0 in rasterElementController) {
			rasterElementController[k0].visible = false;
		}
		if (tmpData!=null) {
			var min = parseFloat($('#rasterMin').val());
			var max = parseFloat($('#rasterMax').val());
			var range = max-min;
			for (var i0=0; i0<tmpData.idxs.length; i0++) {
				var tmp = tmpData.values[i0];
				if (tmp!=-999) {
					
					var idx = Math.round((tmp-min)/range*(rasterInfo.colormap.length-1));
					if (idx>=0) {
						rasterElementController[tmpData.idxs[i0]].material.color = rasterInfo.colormap[Math.min(idx, rasterInfo.colormap.length-1)];
						rasterElementController[tmpData.idxs[i0]].visible = true;
					}
				}
			}
		}
	} catch (ex) {
		//dateProduct = '__';
	} 
}

function createDateArray(name) {
	// create an array of datetimes covering the raster dataset's timespan
	
	var ref = new Date(rasterDict[name].reference);
	var tmp = rasterDict[name].timestep.replace('(','').replace(')','').split(' ');
	var timeStepSize = parseFloat(tmp[0]);
	var timeStep = tmp[1];
	
	var dateIni = rasterDict[name].dates[0];
	dateIni = new Date(Date.UTC(dateIni[0], dateIni[1]-1, 1))
	var dateEnd = new Date(rasterDict[name].lastRecord);
	//var dateEnd = rasterDict[name].dates[rasterDict[name].dates.length-1];
	//dateEnd = new Date(Date.UTC(dateEnd[0], dateEnd[1], 1))
	
	// find first date
	var ctr = -1;
	while (timeStepDelta(ref, timeStep, ctr*timeStepSize)>dateIni) {
		ctr = ctr * 2;
	}
	while (timeStepDelta(ref, timeStep, ctr*timeStepSize)<dateIni) {
		ctr = ctr + 1;
	}
	var dateIni = timeStepDelta(ref, timeStep, ctr*timeStepSize);
	
	var dates = [];
	tmp = timeStepDelta(ref, timeStep, ctr*timeStepSize);
	while (tmp<dateEnd) {
		dates.push(tmp);
		ctr = ctr + 1;
		tmp = timeStepDelta(ref, timeStep, ctr*timeStepSize);
	}
	
	return dates;
}

function timeStepDelta(t0, timeStep, timeStepSize) {
	t0 = new Date(t0);
	var t1 = new Date(t0.getTime());
	var t2 = new Date(t0.getTime());
	switch(timeStep) {
		case 'seconds':
	        t1.setTime(t0.getTime() + timeStepSize*1000); break;
	    case 'minutes':
	        t1.setTime(t0.getTime() + timeStepSize*60000); break;
	    case 'hours':
	        t1.setTime(t0.getTime() + timeStepSize*3600000); break;
	    case 'days':
	    	t1.setDate(t0.getDate() + timeStepSize); break;
	  	case 'weeks':
	    	t1.setDate(t0.getDate() + timeStepSize*7); break;
	  	case 'months':
	    	t1.setMonth(t0.getMonth() + timeStepSize); break;
	    case 'years':
	    	t1.setFullYear(t0.getFullYear() + timeStepSize); break;
	    default:
	    	t1 = null;
	        console.log('timeStep Unknown [' + timeStep + ']... please edit template.');
	}
	return t1.getTime();
}

function requestRasterData(name) {
	console.log(name);
	// retrieves raster data from the server
	var rangeIni = 31*86400*1000;
	var rangeEnd = 5*86400*1000;
	var tmpDateIni = new Date($("#dateSlider").slider("value")).getTime()-rangeIni;
	var tmpDateEnd = new Date($("#dateSlider").slider("value")).getTime()+rangeEnd;

	var dates = getDatetimesToDownload(name, tmpDateIni, tmpDateEnd, false);
	if (dates.length>0 && rasterDownloadAvailable) {
		rasterDownloadAvailable = false;
		$.ajax({
	        url : '/timeSeries/satelliteGet/' , // the endpoint
	        type : "POST", // http method
	        data : {data: JSON.stringify({datetimes: dates, info: false, name: name})},
	        // handle a successful response
	        success : function(json) {
	        	data = JSON.parse(json);
	        	
	        	// populate rasterDateController array
	        	for (var i0=0; i0<data.dates.length; i0++) {
	        		var date = new Date(data.dates[i0]).getTime();
	        		var idx = $.inArray(date, rasterDates);
	        		
	        		for (var i1=data.data[i0].values.length-1; i1>=0; i1--) {
	        			if (data.data[i0].values[i1]==-999) {
	        				data.data[i0].values.splice(i1, 1);
	        				data.data[i0].idxs.splice(i1, 1);
	        			}
	        		}
	        		
	        		rasterDateController[idx] = data.data[i0];
	        		
	        		var tmp = Math.min.apply(Math, data.data[i0].values);
	        		if (rasterInfo.min == null || tmp<rasterInfo.min) {
	        			rasterInfo.min = tmp;
	        		}
	        		var tmp = Math.max.apply(Math, data.data[i0].values);
	        		if (rasterInfo.max == null || tmp>rasterInfo.max) {
	        			rasterInfo.max = tmp;
	        		}
	        	}
	        	
	        	// update min max
	        	$('#rasterMin')[0].value = Math.floor(rasterInfo.min*100)/100;
	            $('#rasterMax')[0].value = Math.ceil(rasterInfo.max*100)/100;
	            
	            setTimeout(function() {
	            	dateProduct = '__';
	            	updateRaster($('#dateSlider').slider('value'));
	            	$('#loading').hide();
	            }, 500);
	            rasterDownloadAvailable = true;
	        },
	
	        // handle a non-successful response
	        error : function(xhr,errmsg,err) {
	        	console.log(errmsg);
	        	$('#loading').hide();
	        	rasterDownloadAvailable = true;
	        }
	    });
	}
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

function getDatetimesToDownload(name, dateIni, dateEnd, all) {
	var dates;
	if (all) {
		dates = createDateArray(name);
	} else {
		dates = rasterDates;
	}
	
	var idxIni = $.inArray(closerTimedate(dateIni, dates), dates);
	var idxEnd = $.inArray(closerTimedate(dateEnd, dates), dates);
	
	var toDownload = [];
	if (all) {
		for (var i0=idxIni; i0<=idxEnd; i0++) {
			toDownload.push(new Date(dates[i0]).toISOString());
		}
	} else {
		for (var i0=idxIni; i0<=idxEnd; i0++) {
			if (rasterDateController[i0]==null) {
				toDownload.push(new Date(dates[i0]).toISOString());
			}
		}
	}
	
	return toDownload;
}

function prepareRasterDisplay(name) {
	// retrieves raster data from the server
	var rangeIni = 31*86400*1000;
	var rangeEnd = 5*86400*1000;
	var tmpDateIni = new Date($("#dateSlider").slider("value")).getTime()-rangeIni;
	var tmpDateEnd = new Date($("#dateSlider").slider("value")).getTime()+rangeEnd;

	var dates = getDatetimesToDownload(name, tmpDateIni, tmpDateEnd, true);
	
	if (rasterDownloadAvailable) {
		rasterDownloadAvailable = false;
		$.ajax({
	        url : '/timeSeries/satelliteGet/' , // the endpoint
	        type : "POST", // http method
	        data : {data: JSON.stringify({datetimes: dates, info: true, name: name})},
	        // handle a successful response
	        success : function(json) {
	        	data = JSON.parse(json);
	        	
	        	// create arrays based on dates
				rasterDates = createDateArray(data.name);
				rasterDateController = new Array(rasterDates.length);
				
				// update the raster pannel
	        	var context = $('#colormap')[0].getContext('2d');
	        	rasterInfo.colormap = [];
	        	var imageObj = new Image();
	            imageObj.onload = function() {
	            	var canvas = $('#colormap')[0];
	            	context.drawImage(this, 0, 0, this.width, this.height, 0, 0, canvas.width, canvas.height);
	            	
	            	// get colors from the colormap
	                for (var i0=0; i0<100; i0++) {
	                	var tmp = context.getImageData(Math.round(canvas.width/100*i0), 0, 1, 1).data;
	                	rasterInfo.colormap.push({r: tmp[0]/255, g: tmp[1]/255, b: tmp[2]/255});
	                }
	            }
	            imageObj.src = '/' + rasterDict[rasterInfo.name].colormap;
				
				// create pixels in WebGL
	        	createWebGLSquares(data.lat, data.lon, data.idxs);
	        	
	        	// populate rasterDateController array
	        	for (var i0=0; i0<data.dates.length; i0++) {
	        		var date = new Date(data.dates[i0]).getTime();
	        		var idx = $.inArray(date, rasterDates);
	        		
	        		for (var i1=data.data[i0].values.length-1; i1>=0; i1--) {
	        			if (data.data[i0].values[i1]==-999) {
	        				data.data[i0].values.splice(i1, 1);
	        				data.data[i0].idxs.splice(i1, 1);
	        			}
	        			
	        		}
	        		
	        		rasterDateController[idx] = data.data[i0];
	        		
	        		var tmp = Math.min.apply(Math, data.data[i0].values);
	        		if (rasterInfo.min == null || tmp<rasterInfo.min) {
	        			rasterInfo.min = tmp;
	        		}
	        		var tmp = Math.max.apply(Math, data.data[i0].values);
	        		if (rasterInfo.max == null || tmp>rasterInfo.max) {
	        			rasterInfo.max = tmp;
	        		}
	        	}
	        	$('#rasterMin')[0].value = Math.floor(rasterInfo.min*100)/100;
	            $('#rasterMax')[0].value = Math.ceil(rasterInfo.max*100)/100;
	            $('#rasterUnits')[0].value = rasterDict[rasterInfo.name].units;
	            
	            setTimeout(function() {
	            	dateProduct = '__';
	            	updateRaster($('#dateSlider').slider('value'));
	            	$('#loading').hide();
	            }, 500);
	            rasterDownloadAvailable = true;
	        },
	
	        // handle a non-successful response
	        error : function(xhr,errmsg,err) {
	        	console.log(errmsg);
	        	$('#loading').hide();
	        	rasterDownloadAvailable = true;
	        }
		});
	}
}

function createWebGLSquares(lat, lon, idxs) {
	var dLat = Math.abs(lat[1]-lat[0])/2;
	var dLon = Math.abs(lon[1]-lon[0])/2;
	
	var mesh = drawSquare(0-dLon, 0-dLat, 0+dLon, 0+dLat);
	//scene.add(mesh);
    //renderer.render(scene, camera);
	
	// remove old objects
	for (var key in rasterElementController) {
		scene.remove(rasterElementController[key]);
	}
	
	rasterElementController = {};
	var ctr = 0;
	for (var i0=0; i0<lat.length; i0++) {
		for (var i1=0; i1<lon.length; i1++) {
			if ($.inArray(ctr, idxs) != -1) {
				var clone = new THREE.Mesh(mesh.geometry, mesh.material.clone());
				clone.renderOrder = 9999;
				clone.position.x += lon[i1];
				clone.position.y += lat[i0];
				//clone.visible = false;
				scene.add(clone);
				rasterElementController[ctr] = clone;
			}
			ctr++;
		}
	}
}

function drawSquare(x1, y1, x2, y2) { 
    var square = new THREE.Geometry(); 

    //set 4 points
    square.vertices.push(new THREE.Vector3(x1, y2, 0));
    square.vertices.push(new THREE.Vector3(x1, y1, 0));
    square.vertices.push(new THREE.Vector3(x2, y1, 0));
    square.vertices.push(new THREE.Vector3(x2, y2, 0));

    //push 1 triangle
    square.faces.push(new THREE.Face3(0, 1, 2));

    //push another triangle
    square.faces.push(new THREE.Face3(0, 2, 3));

    //create mesh
    return new THREE.Mesh(square, new THREE.MeshBasicMaterial({wireframe: false}));;
}

function updateDateText() {
	var options = {year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"};
	var language = window.navigator.userLanguage || window.navigator.language;
	
	var tmp = new Date($("#dateSlider").slider("value")).toISOString().replace('T', ' ').replace('.000Z', '');
	$("#dateText").val(tmp);
	//$("#dateText").val(new Date($("#dateSlider").slider("value")).toLocaleTimeString(language, options));
}

function moveSlider(direction) {
	var datetime = $('#dateSlider').slider('value');
	var idx = $.inArray(datetime, rasterDates);
	var tmp  = null;
	if (rasterDateController[idx] != null) {
		if (direction=='next') {
			tmp = closerTimedate(rasterDates[Math.min(idx+1, rasterDates.length-1)], rasterDates);
			$('#dateSlider').slider('value', tmp);
			updateDateText()
		} else if (direction=='previous') {
			tmp = closerTimedate(rasterDates[Math.max(0, idx-1)], rasterDates);
			$('#dateSlider').slider('value', tmp);
			updateDateText()
		} else {
			console.log('Unknown direction: ' + direction);
		};
	} else {
		requestRasterData(rasterInfo.name);
	};
}
// Prepare the webGL gui
var text;
var gui;

// TODO: to remove
$.ajaxSetup({
	cache:false,
	beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        }
        $('#loading').show();
    }
});

// Prepare sortable dat-gui
$(document).ready(function() {
	setTimeout(function() {
		$('li.cr').parent('ul').sortable({
			revert: true,	     
  			start: function(event, ui) {
  				$( event.originalEvent.target ).one('click', function(e){ e.stopImmediatePropagation(); } );
  	        },
            update: function(event, ui) {
                $('li.cr').parent('ul').children().not('.title').each(function(i, elm) {
                	$elm = $(elm); // cache the jquery object
                	$elm.attr('renderOrder', $elm.index());
                        
                	var webGLObject = geoJSONControllers[$elm.attr('id')].webGLObject;
                	if (webGLObject != null) {
                		for (var i0=0; i0<webGLObject.children.length; i0++) {
                			webGLObject.children[i0].renderOrder = 999-$elm.attr('renderOrder');
                		}
                	}
                });
            },
		});
	}, 100);
});

$(document).ready(function () {
	text = new FizzyText();
	gui = new dat.GUI();
	
	// Add layers
	var layerFolder = gui.addFolder('Layers');
	for (var geoJSONFolder in geoJSONDict) {
		// Add folder;
		var folder = layerFolder.addFolder(geoJSONFolder);
		var renderOrder = 1;
		for (var geoJSONName in geoJSONDict[geoJSONFolder]) {
			// Add entry;
			var key = geoJSONFolder + '_' + geoJSONName;
			var controller = folder.add(text, geoJSONName);
			controller.path = geoJSONDict[geoJSONFolder][geoJSONName];
			controller.loaded = false;
			controller.key = key;
			$(controller.domElement).closest('li').attr('id', key);
			$(controller.domElement).closest('li').attr("renderOrder", renderOrder);
			$(controller.domElement).closest('li').attr('title', 'This is an example description.');
			renderOrder++;
			controller.webGLObject = null;
			controller.onChange(function(value) {
				var key = this.key;
				if (value) {
					if (this.loaded) {
						this.webGLObject.visible = true;
					} else {
						function fWrapDrawThreeGeo(data, key) {
							$('#loading').hide();
							geoJSONControllers[key].webGLObject = drawThreeGeo(data, 180, 'plane', {
								color: 'black',
								transparent: false
							});
							for (var i0=0; i0<geoJSONControllers[key].webGLObject.children.length; i0++) {
								geoJSONControllers[key].webGLObject.children[i0].renderOrder = 999-$('#' + key).attr('renderOrder');
                            }
		  				}
		  				$.getJSON(this.path, function(data) {fWrapDrawThreeGeo(data, key);}); 
		  				this.loaded = true;
		  			}
		  		} else {
		  			this.webGLObject.visible = false;
		  		}
			});
		  	geoJSONControllers[key] = controller;
	  	}
	}
	
	function fDisplaySprite(obj) {
		if (obj.loaded) {
			obj.webGLObject.visible = true;
		} else {
			// add to webGL
			var map = new THREE.TextureLoader().load( obj.data.typeIcon );
			var material = new THREE.SpriteMaterial({
				map: map,
				});
			var sprite = new THREE.Sprite( material ); 
			
			var position = new THREE.Vector3(obj.data.lon, obj.data.lat, 0);
			sprite.position.add(position);
			sprite.scale.set( spriteScale, spriteScale, 1 );
			sprite.key = obj.key;
			sprite.callback = function() {
				$('#hidden').attr('href', '/timeSeries/select/series/' +  seriesControllers[this.key].data.name).trigger("click");
			};
			scene.add( sprite );
			
			obj.webGLObject = sprite;
            
			obj.loaded = true;
		}
	}
	
	// Add series
	var layerFolder = gui.addFolder('Time series');
	for (k0 in seriesDict) {
		// Add folder;
		var folder = layerFolder.addFolder(k0);
		$("li:contains('" + k0 + "')").filter('.title').prepend('<img class="datGuiIcon" src="' + seriesDict[k0][0].typeIcon + 
				'" alt="' + k0 + '" style="width:20px; height:20px;">');
		
		var showKey = k0 + '_showAll';
		var showController = folder.add(text, showKey).name('Show');
		showController.seriesList = [];
		showController.onChange(function(value) {
			if (value) {
				for (var i0=0; i0<this.seriesList.length; i0++) {
					fDisplaySprite(this.seriesList[i0]);
				}
			} else {
				for (var i0=0; i0<this.seriesList.length; i0++) {
					this.seriesList[i0].webGLObject.visible = false;
				}
			}
			
		});
		
		
		var folderItems = folder.addFolder('Items');
		for (var i0=0; i0<seriesDict[k0].length; i0++) {
			// Add entry;
			var key = seriesDict[k0][i0].name;
			var controller = folderItems.add(text, key);
			controller.key = key;
			controller.data = seriesDict[k0][i0];
			controller.loaded = false;
			controller.webGLObject = null;
			controller.onChange(function(value) {
				var key = this.key;
				if (this.webGLObject === null) {
					fDisplaySprite(this);
					this.webGLObject.visible = false;
				}
				if (value) {
					this.webGLObject.material.color = new THREE.Color("rgb(127, 78, 27)");
		  		} else {
		  			this.webGLObject.material.color = new THREE.Color(0xffffff);
		  		}
			});
			seriesControllers[key] = controller;
			showController.seriesList.push(controller);
		}
	}
	seriesControllers[showKey] = showController;
	
	// Add rasters
	var rasterFolder = gui.addFolder('Rasters');
	for (k0 in rasterDict) {
		// Add folder;
		var folder;
		if (!(rasterDict[k0].raster in gui.__folders.Rasters.__folders)) {
			rasterFolder.addFolder(rasterDict[k0].raster);
		};
		folder = gui.__folders.Rasters.__folders[rasterDict[k0].raster];
		var key = rasterDict[k0].name;
		var controller = folder.add(text, rasterDict[k0].name);
		controller.loaded = false;
		controller.key = key;
		$(controller.domElement).closest('li').attr('id', key);
		$(controller.domElement).closest('li').attr('title', rasterDict[k0].description);
		controller.webGLObject = null;
		controller.onChange(function(value) {
			var key = this.key;
			var rasterCheckboxes = $('li:contains("Rasters").title').parent().find('input:checkbox');
			if (value) {
				// select
				$('#rasterPannel').show();
				rasterInfo.name = key;
				rasterInfo.min = 999999;
				rasterInfo.max = -999999;
				
				// deselect all others
				rasterCheckboxes.each(function () {
					if (this.checked) {
						if ($(this).closest('li').attr('id')!=key) {
							this.checked = false;
						};
					};
				})
					
				// set time slider
		        var max = new Date(Date.UTC(rasterDict[key].dates[rasterDict[key].dates.length-1][0], rasterDict[key].dates[rasterDict[key].dates.length-1][1], -1, 24, 59, 59)).getTime();
		        var options = {year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit"};
		        $("#dateSlider").slider({
		        	value: max,
		            min: new Date(Date.UTC(rasterDict[key].dates[0][0], rasterDict[key].dates[0][1], 1, 0, 0, 0)).getTime(),
		            max: max,
		            stop: function( event, ui ) {
		            	updateDateText();
		                requestRasterData(key);
		            }
		         });
					
		        // set display
		        prepareRasterDisplay(key);
					
	  			this.loaded = true;
	  			$('#rasterPannel').show();
	  		} else {
	  			// unselect
	  			if (!rasterCheckboxes.is(':checked')) {
	  				// if none is selected
	  				$('#rasterPannel').hide();
	  				for (var k0 in rasterElementController) {
	  					rasterElementController[k0].visible = false;
	  				}
	  			}
	  		}
		});
		rasterControllers[key] = controller;
	}
	
});