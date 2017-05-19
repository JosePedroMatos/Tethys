// Object prototype
function Value(datetime, value) {
	this.x = datetime;
	this.y = value;
	this.Status = '';
}

function addEntry(x, tr) {
	var td = document.createElement('td');
    td.appendChild(document.createTextNode(x));
    tr.appendChild(td);
}

function addComboBox(choice, tr, options) {
	var td = document.createElement('td');
	var combobox = document.createElement('select');
	options.forEach(function (opt) {
		var option = document.createElement('option');
		option.value = opt[0];
		option.innerHTML = opt[1];
		combobox.appendChild(option);
	});

	td.appendChild(combobox);
	tr.appendChild(td);
	
	combobox.value = choice;
}

var palette = new Rickshaw.Color.Palette({ scheme: 'classic9' });

var valuesToUpload = {};
var storedSeries;
function handleExcelFile(e) {
	dataToUpload = [];
	$('#validate').show();
	$('#chartLoader').show();
	$('#seriesCheck').hide();
	$('#chartContainer').hide();
	clearChart();
	
	setTimeout(
			function() {
				var files = e.target.files;
				var reader = new FileReader();
				reader.onload = function(e) {
					// parse the excel file
					var data = e.target.result;

					var workbook = XLSX.read(data, {
						type : 'binary'
					});
					var sheetNameList = workbook.SheetNames;
					for (var i0=0; i0<sheetNameList.length; i0++) {
						var worksheet  = workbook.Sheets[sheetNameList[i0]];
						console.log(worksheet);
						var sheetData = [];
						
						var date = true;
						var cellref;
						for (cellref in worksheet) {
							if (cellref[0] != '!') {
								if (cellref.toString().indexOf('A') === 0) {
									date = worksheet[cellref].v;
									if (typeof worksheet[cellref].v == 'number') {
										date = (worksheet[cellref].v-2)*86400000-2208988800000
									} else {
										date = Date.parse(worksheet[cellref].v.replace(new RegExp('-', 'g'), '/') + ' GMT');
									}
								} else if (cellref.toString().indexOf('B') === 0) {
									sheetData.push(new Value(date/1000,  parseFloat(worksheet[cellref].v)));
									date = null;
								}
							}
						}
						valuesToUpload[sheetNameList[i0]] = sheetData;
					}
				};
				reader.onloadend = function() {
					var seriesNames = Object.keys(valuesToUpload);
					// prepare plot colors
					var colors = [];
					for (var i0=0; i0<seriesNames.length; i0++) {
						colors.push(palette.color());
					}
					
					// get series data using AJAX
					var dataToSend = [];
					for (var i0=0; i0<seriesNames.length; i0++) {
						dataToSend.push({'name': seriesNames[i0],
							'dateIni': date2Str(valuesToUpload[seriesNames[i0]][0].x),
							'dateEnd': date2Str(valuesToUpload[seriesNames[i0]][valuesToUpload[seriesNames[i0]].length-1].x)});
					}
					$.ajax({
						url : "info/",
						type : "POST",
						data : {
							series: JSON.stringify(dataToSend),
						},
				
						// handle a successful response
						success : function(json) {
							console.log(json);
							storedSeries = json.info;
							
							/*$('#seriesCheck').html('');
							
							var table = document.createElement('table');
							$('#seriesCheck').append(table);
							var tableHead = document.createElement('thead');
							table.appendChild(tableHead);
							var tableBody = document.createElement('tbody');
							table.appendChild(tableBody);
							
							// Table header
							var header = ['Name', 'From', 'To', 'Number of records (new/existing)', 'Action', 'Status'];
							var tr = document.createElement('tr');
							tableHead.appendChild(tr);
							for (i0 = 0; i0 < header.length; i0++) {
						        var th = document.createElement('th')
						        th.appendChild(document.createTextNode(header[i0]));
						        tr.appendChild(th);
						    }
							
							// Table rows
							for (i0 = 0; i0 < storedSeries.length; i0++) {
						        var tr = document.createElement('tr');
						        
						        addEntry(storedSeries[i0].name, tr);
						        addEntry(storedSeries[i0].dateIni, tr);
						        addEntry(storedSeries[i0].dateEnd, tr);
						        if ("undefined" === typeof storedSeries[i0].timeStep) {						        	
						        	addEntry(valuesToUpload[storedSeries[i0].name].length + '/0', tr);
							        addComboBox(0, tr, operations.error);
							        addEntry('!Error: The series does not exist in the database.', tr);
						        } else {
						        	if (storedSeries[i0].values.length==0) {
						        		addEntry(valuesToUpload[storedSeries[i0].name].length + '/' + storedSeries[i0].values.length, tr);
								        addComboBox(1, tr, operations.simple);
								        addEntry('', tr);
						        	} else {
						        		addEntry(valuesToUpload[storedSeries[i0].name].length + '/' + storedSeries[i0].values.length, tr);
								        addComboBox(2, tr, operations.warning);
								        addEntry('!Warning: Values exist already in this period.', tr);
						        	}
						        }
						        
						        tableBody.appendChild(tr);
						    }  
							
							$('#seriesCheck').find('table').DataTable({
								"createdRow": function(row, data, dataIndex) {
									if (data[data.length-1].indexOf('!Warning: ') === 0) {
										$(row).css('background', '#ffefb4');
									} else if (data[data.length-1].indexOf('Success: ') === 0 && data[data.length-1] != '') {
										$(row).css('background', '#ffbfb4');
									}
								},
								"order": [[ 5, "desc" ]],
							});
							$('#seriesCheck').find('input').css('float', 'right');
							*/
							createTable();
							
							$('#seriesCheck').find('table').DataTable({
								"createdRow": function(row, data, dataIndex) {
									if (data[data.length-1].indexOf('!Warning: ') === 0) {
										$(row).css('background', '#ffefb4');
									} else if (data[data.length-1].indexOf('Success: ') === 0 && data[data.length-1] != '') {
										$(row).css('background', '#ffbfb4');
									}
								},
								"order": [[ 5, "desc" ]],
							});
							
							$('#chartContainer').show();
							
							var ctr = 0;
							for (var i0=0; i0<storedSeries.length; i0++) {
								// Display existing data.
								if ('values' in storedSeries[i0] && storedSeries[i0].values.length>0) {
									var decryptedData = decryptData(storedSeries[i0].values, key=hashPassword(storedSeries[i0].encryptionKey));
									display(decryptedData, timeStep=storedSeries[i0].timeStep, timeStepSize=storedSeries[i0].timeStepSize,
											order=ctr, name=storedSeries[i0].name + ' (existing)', strokeColor=colors[i0], fillColor=null, fillAlpha=0.2);
									ctr++;
								}
								// Display new data
								if ('timeStep' in storedSeries[i0] && 'timeStepSize' in storedSeries[i0]) {
									display(valuesToUpload[seriesNames[i0]], timeStep=storedSeries[i0].timeStep, timeStepSize=storedSeries[i0].timeStepSize,
											order=ctr, name=storedSeries[i0].name + ' (new)', strokeColor=colors[i0], fillColor=null, fillAlpha=0.8);
									ctr++;
								}
							}	
							// Add legend;
							addLegend();
								
							var existing = $('#legend').find('span:contains("(existing)")').parent().find('.swatch')
							
							existing.each(function(i,x) {
								var color = $(x).css("background-color").replace('rgb(', '').replace(' ', '').replace(')', '');
								$(x).css("border-width", 2);
								$(x).css("border-color", 'rgb(' + color + ')');
								color = color.split(',');
								$(x).css("background-color", 'rgb(' + parseInt(255-(255-color[0])/5) + ',' + parseInt(255-(255-color[1])/5) + ',' + parseInt(255-(255-color[2])/5) + ')');
								});
							
							$('#chartLoader').hide();
							$('#seriesCheck').show();
							$('#upload').show();
						},
			
						// handle a non-successful response
						error : function(xhr,errmsg,err) {
							console.log(xhr.status + ": " + xhr.responseText); // provide a bit more info about the error to the console
							$('#chartLoader').hide();
						}
					});
				};

				reader.readAsBinaryString(files[0]);
			}, 0);
}

function upload(event) {
	event.preventDefault();
	
	$('#chartLoader').show();
	$('#seriesCheck').hide();
	$('#chartContainer').hide();
	$('#upload').hide();
	
	// prepare data to upload
	var toUpload = {};
	for (var k0 in valuesToUpload) {
		var encryptionKey = null;
		var encryptedData = null;
		var action = $('#seriesCheck').find('*').filter(function() {
			return $(this).text() === k0;
		}).parent().find('select').val();
		
		if (action!=0) {
			for (var i1=0; i1<storedSeries.length; i1++) {
				if (storedSeries[i1].name===k0) {
					encryptionKey = storedSeries[i1].encryptionKey;
					break;
				}
			}
			toUpload[k0] = {};
			toUpload[k0].action = action;
			toUpload[k0].values = encryptData(valuesToUpload[k0], encrypt=hashPassword(encryptionKey));
		} else {
			toUpload[k0] = {};
			toUpload[k0].action = action;
			toUpload[k0].values = null;
		}
	}
		
	
	/*for (var k0 in valuesToUpload) {
		var tmp = valuesToUpload[k0];
		
		valuesToUpload[k0] = {};
		valuesToUpload[k0].action = $('#seriesCheck').find('*').filter(function() {
			return $(this).text() === k0;
		}).parent().find('select').val();
		if (valuesToUpload[k0].action!=0) {
			for (var i1=0; i1<tmp.length; i1++) {
				tmp[i1].x = date2Str(tmp[i1].x);
			}
			valuesToUpload[k0].values = tmp;
		} else {
			valuesToUpload[k0].values = [];
		}
	}*/
	
	// send data
	$.ajax({
		url : "registerBatch/",
		type : "POST",
		data : {
			values: JSON.stringify(toUpload),
		},

		// handle a successful response
		success : function(json) {
			var success = json.success;
			var warnings = json.warnings;
			var errors = json.errors;
			
			createTable();
			
			for (var i0=0; i0<success.length; i0++) {
				var tmp = success;
				$('#seriesCheck').find('*').filter(function() {
					return $(this).text() === tmp[i0][0];
				}).parent().find('td').last().text(tmp[i0][1])
			}
			for (var i0=0; i0<warnings.length; i0++) {
				var tmp = warnings;
				$('#seriesCheck').find('*').filter(function() {
					return $(this).text() === tmp[i0][0];
				}).parent().find('td').last().text(tmp[i0][1])
			}
			for (var i0=0; i0<errors.length; i0++) {
				var tmp = errors;
				$('#seriesCheck').find('*').filter(function() {
					return $(this).text() === tmp[i0][0];
				}).parent().find('td').last().text(tmp[i0][1])
			}
			
			$('#seriesCheck').find('table').DataTable({
				"createdRow": function(row, data, dataIndex) {
					if (data[data.length-1].indexOf('!Warning: ') === 0) {
						$(row).css('background', '#ffefb4');
					} else if (data[data.length-1].indexOf('Success: ') === -1) {
						$(row).css('background', '#ffbfb4');
					}
				},
				"order": [[ 5, "asc" ]],
			});
			
			$('#seriesCheck').find('select').prop('disabled', 'disabled');
			
			$('#chartLoader').hide();
			$('#seriesCheck').show();
			$('#chartContainer').hide();
			$('#upload').hide();
			
		},

		// handle a non-successful response
		error : function(xhr,errmsg,err) {
			console.log(xhr.status + ": " + xhr.responseText); // provide a bit more info about the error to the console
			$('#chartLoader').hide();
		}
	});
}

function createTable() {
	$('#seriesCheck').html('');
	
	var table = document.createElement('table');
	$('#seriesCheck').append(table);
	var tableHead = document.createElement('thead');
	table.appendChild(tableHead);
	var tableBody = document.createElement('tbody');
	table.appendChild(tableBody);
	
	// Table header
	var header = ['Name', 'From', 'To', 'Number of records (new/existing)', 'Action', 'Status'];
	var tr = document.createElement('tr');
	tableHead.appendChild(tr);
	for (i0 = 0; i0 < header.length; i0++) {
        var th = document.createElement('th')
        th.appendChild(document.createTextNode(header[i0]));
        tr.appendChild(th);
    }
	
	// Table rows
	for (i0 = 0; i0 < storedSeries.length; i0++) {
        var tr = document.createElement('tr');
        
        addEntry(storedSeries[i0].name, tr);
        addEntry(storedSeries[i0].dateIni, tr);
        addEntry(storedSeries[i0].dateEnd, tr);
        if ("undefined" === typeof storedSeries[i0].timeStep) {						        	
        	addEntry(valuesToUpload[storedSeries[i0].name].length + '/0', tr);
	        addComboBox(0, tr, operations.error);
	        addEntry('!Error: The series does not exist in the database.', tr);
        } else {
        	if (storedSeries[i0].values.length==0) {
        		addEntry(valuesToUpload[storedSeries[i0].name].length + '/' + storedSeries[i0].values.length, tr);
		        addComboBox(1, tr, operations.simple);
		        addEntry('', tr);
        	} else {
        		addEntry(valuesToUpload[storedSeries[i0].name].length + '/' + storedSeries[i0].values.length, tr);
		        addComboBox(2, tr, operations.warning);
		        addEntry('!Warning: Values exist already in this period.', tr);
        	}
        }
        
        tableBody.appendChild(tr);
    }  
	
	//$('#seriesCheck').find('input').css('float', 'right');
}