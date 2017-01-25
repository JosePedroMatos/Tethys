function s2ab(s) {
	var buf = new ArrayBuffer(s.length);
	var view = new Uint8Array(buf);
	for (var i=0; i!=s.length; ++i) view[i] = s.charCodeAt(i) & 0xFF;
	return buf;
}

function datenum(v, date1904) {
	if(date1904) v+=1462;
	var epoch = Date.parse(v);
	return (epoch - new Date(Date.UTC(1899, 11, 30))) / (24 * 60 * 60 * 1000);
}

function getXLSX() {
	var wb = fPrepareXLSX();
	var wopts = {bookType: 'xlsx', bookSST: false, cellDates: false, type:'binary'};
	var wbout = XLSX.write(wb, wopts);
	var wbOutBlob = new Blob([s2ab(wbout)], {type:"application/octet-stream"});
	saveAs(wbOutBlob, 'Tethys data (' + $('input[name=series]:checked').val() + ').xlsx')
};

// start workbook
function fPrepareXLSX() {
	var wb = { SheetNames:[], Sheets:{} };
	var sheet;
	tmpSheetName = '__unknown__';
	var range;
	for (var i0=0; i0<graphData.length; i0++) {
		if (!graphData[i0].disabled && graphData[i0].marker.type!='__dummy__') {
			if (tmpSheetName != graphData[i0].marker.type) {
				tmpSheetName = graphData[i0].marker.type;
				wb.SheetNames.push(tmpSheetName);
				wb.Sheets[tmpSheetName] = {};
				sheet = wb.Sheets[graphData[i0].marker.type];
				range = {s: {c:0, r:0}, e: {c:0, r:0 }};
				// dates
				var cell = {v: 'Date', t: 's'};
				var cell_ref = XLSX.utils.encode_cell({c:0,r:0});
				sheet[cell_ref] = cell;
				for (var i1=0; i1<graphData[i0].data.length; i1++) {
					var tmp = i1+1;
					if(range.s.r > tmp) range.s.r = tmp;
					if(range.e.r < tmp) range.e.r = tmp;
					
					var cell = {v: new Date(graphData[i0].data[i1].x*1000)};
					if(cell.v == null) continue;	
					
					if(typeof cell.v === 'number') cell.t = 'n';
					else if(typeof cell.v === 'boolean') cell.t = 'b';
					else if(cell.v instanceof Date) {
						cell.t = 'n'; cell.z = XLSX.SSF._table[14];
						cell.v = datenum(cell.v);
					}
					else cell.t = 's';
					
					var cell_ref = XLSX.utils.encode_cell({c:0,r:i1+1});
					sheet[cell_ref] = cell;
				}
			}
			
			// values
			range.e.c++;
			var cell = {v: graphData[i0].name, t:'s'};
			var cell_ref = XLSX.utils.encode_cell({c:range.e.c,r:0});
			sheet[cell_ref] = cell;
			for (var i1=0; i1<graphData[i0].data.length; i1++) {
				var tmp = i1+1;
				if(range.s.r > tmp) range.s.r = tmp;
				if(range.e.r < tmp) range.e.r = tmp;
				
				var cell = {v: graphData[i0].data[i1].y};
				if(cell.v == null) continue;	
				
				if(typeof cell.v === 'number') cell.t = 'n';
				else if(typeof cell.v === 'boolean') cell.t = 'b';
				else if(cell.v instanceof Date) {
					cell.t = 'n'; cell.z = XLSX.SSF._table[14];
					cell.v = datenum(cell.v);
				}
				else cell.t = 's';
				
				var cell_ref = XLSX.utils.encode_cell({c:range.e.c,r:i1+1});
				sheet[cell_ref] = cell;
			}
			if(range.s.c < 10000000) sheet['!ref'] = XLSX.utils.encode_range(range);
		}
	}
	
	// QQ plot
	if (QQ!=null) {
		tmpSheetName = 'Training QQ plot';
		wb.SheetNames.push(tmpSheetName);
		wb.Sheets[tmpSheetName] = {};
		sheet = wb.Sheets[tmpSheetName];
		range = {s: {c:0, r:0}, e: {c:1, r:0 }};
		// Training
		//range.e.c++;
		var cell = {v: 'Theoretical quantile', t:'s'};
		var cell_ref = XLSX.utils.encode_cell({c:range.s.c,r:0});
		sheet[cell_ref] = cell;
		var cell = {v: 'Observed p-value', t:'s'};
		var cell_ref = XLSX.utils.encode_cell({c:range.e.c,r:0});
		sheet[cell_ref] = cell;
		for (var i1=0; i1<QQ.tra.length; i1++) {
			var tmp = i1+1;
			if(range.s.r > tmp) range.s.r = tmp;
			if(range.e.r < tmp) range.e.r = tmp;
			
			var cell = {v: QQ.tra[i1][0], t:'n'};
			var cell_ref = XLSX.utils.encode_cell({c:range.s.c,r:i1+1});
			sheet[cell_ref] = cell;
			
			var cell = {v: QQ.tra[i1][1], t:'n'};
			var cell_ref = XLSX.utils.encode_cell({c:range.e.c,r:i1+1});
			sheet[cell_ref] = cell;
		}
		if(range.s.c < 10000000) sheet['!ref'] = XLSX.utils.encode_range(range);
		
		tmpSheetName = 'Validation QQ plot';
		wb.SheetNames.push(tmpSheetName);
		wb.Sheets[tmpSheetName] = {};
		sheet = wb.Sheets[tmpSheetName];
		range = {s: {c:0, r:0}, e: {c:1, r:0 }};
		// Training
		//range.e.c++;
		var cell = {v: 'Theoretical quantile', t:'s'};
		var cell_ref = XLSX.utils.encode_cell({c:range.s.c,r:0});
		sheet[cell_ref] = cell;
		var cell = {v: 'Observed p-value', t:'s'};
		var cell_ref = XLSX.utils.encode_cell({c:range.e.c,r:0});
		sheet[cell_ref] = cell;
		for (var i1=0; i1<QQ.val.length; i1++) {
			var tmp = i1+1;
			if(range.s.r > tmp) range.s.r = tmp;
			if(range.e.r < tmp) range.e.r = tmp;
			
			var cell = {v: QQ.val[i1][0], t:'n'};
			var cell_ref = XLSX.utils.encode_cell({c:range.s.c,r:i1+1});
			sheet[cell_ref] = cell;
			
			var cell = {v: QQ.val[i1][1], t:'n'};
			var cell_ref = XLSX.utils.encode_cell({c:range.e.c,r:i1+1});
			sheet[cell_ref] = cell;
		}
		if(range.s.c < 10000000) sheet['!ref'] = XLSX.utils.encode_range(range);
	}
	
	return wb;
};