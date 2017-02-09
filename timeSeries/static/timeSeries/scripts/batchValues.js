// Object prototype
function Value(datetime, value) {
	this.Date = datetime;
	this.Value = value;
	this.Status = '';
}

var valuesToUpload = {};
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
									sheetData.push(new Value(date,  parseFloat(worksheet[cellref].v)));
									date = null;
								}
							}
						}
						valuesToUpload[sheetNameList[i0]] = sheetData;
					}
				};
				reader.onloadend = function() {
					// get series data using AJAX
					var seriesNames = Object.keys(valuesToUpload);
					var dataToSend = [];
					for (var i0=0; i0<seriesNames.length; i0++) {
						dataToSend.push({'name': seriesNames[i0],
							'dateIni': date2Str(valuesToUpload[seriesNames[i0]][0].Date/1000),
							'dateEnd': date2Str(valuesToUpload[seriesNames[i0]][valuesToUpload[seriesNames[i0]].length-1].Date/1000)});
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
							//display(sheetData, timeStep, timeStepSize, order=order);
							display(sheetData, 'd', 1, order=order);
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