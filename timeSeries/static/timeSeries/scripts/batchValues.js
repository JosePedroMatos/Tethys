// Object prototype
function Value(datetime, value) {
	this.x = datetime;
	this.y = value;
	this.Status = '';
}

var palette = new Rickshaw.Color.Palette({ scheme: 'classic9' });

var valuesToUpload = {};
var storedSeries;
function handleExcelFile(e) {
	dataToUpload = [];
	setTimeout(
			function() {
				var files = e.target.files;
				var reader = new FileReader();
				reader.onload = function(e) {
					// parse the excel file
					$('#validate').show();
					$('#excelLoader').show();
					$('#dataTableWrapper').hide();

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
							
							$('#seriesCheck').html('');
							for (var i0=0; i0<storedSeries.length; i0++) {
								// Display existing data.
								if ('values' in storedSeries[i0] && storedSeries[i0].values.length>0) {
									var decryptedData = decryptData(storedSeries[i0].values, key=hashPassword(storedSeries[i0].encryptionKey));
									display(decryptedData, timeStep=storedSeries[i0].timeStep, timeStepSize=storedSeries[i0].timeStepSize,
											order=i0, name=storedSeries[i0].name + ' (existing)', strokeColor=colors[i0], fillColor=null, fillAlpha=0.2);
								}
								// Display new data
								if ('timeStep' in storedSeries[i0] && 'timeStepSize' in storedSeries[i0]) {
									display(valuesToUpload[seriesNames[i0]], timeStep=storedSeries[i0].timeStep, timeStepSize=storedSeries[i0].timeStepSize,
											order=i0+seriesNames.length, name=storedSeries[i0].name + ' (new)', strokeColor=colors[i0], fillColor=null, fillAlpha=0.8);
								}
								
								// Add legend;
								addLegend();
								
								// Display checkboxes and warnings
								var container = $('#seriesCheck');
								if (!('timeStep' in storedSeries[i0]) || !('timeStepSize' in storedSeries[i0])) {
									var tmpDiv = $('<div>').appendTo(container);
									$('<input />', { type: 'checkbox', id: 'cb'+ i0, value: storedSeries[i0].name, disabled:true}).appendTo(tmpDiv);
									$('<label />', { 'for': 'cb' + i0, text: '(Values will not be uploaded, the corresponding series was not found in the database).' }).appendTo(tmpDiv);
								} else if ('values' in storedSeries[i0] && storedSeries[i0].values.length>0) {
									var tmpDiv = $('<div>').appendTo(container);
									$('<input />', { type: 'checkbox', id: 'cb'+ i0, value: storedSeries[i0].name, disabled:false }).appendTo(tmpDiv);
									$('<label />', { 'for': 'cb' + i0, text: '(' + valuesToUpload[seriesNames[i0]].length + ' values to upload, ' + storedSeries[i0].values.length + ' existing values will be replaced).' }).appendTo(tmpDiv);
								} else {
									var tmpDiv = $('<div>').appendTo(container);
									$('<input />', { type: 'checkbox', id: 'cb'+ i0, value: storedSeries[i0].name, disabled:false, checked:"checked" }).appendTo(tmpDiv);
									$('<label />', { 'for': 'cb' + i0, text: '(' + valuesToUpload[seriesNames[i0]].length + ' values to upload, no problems detected).' }).appendTo(tmpDiv);
								}
							}
						},
			
						// handle a non-successful response
						error : function(xhr,errmsg,err) {
							console.log(xhr.status + ": " + xhr.responseText); // provide a bit more info about the error to the console
							$('#excelLoader').hide();
						}
					});
				};

				reader.readAsBinaryString(files[0]);
			}, 0);
}