function hashPassword(password) {
	// Define and hash password
	// TODO: interact with the server for passwords
	return forge.md.sha256.create().update(password).digest().getBytes();
};

function encryptValue(value, encrypt=null) {
// Define encryption function
	var strData =  JSON.stringify(value);
	
	if (encrypt !=null) {		
		// encrypt data
		var cipher = forge.cipher.createCipher('AES-ECB', encrypt);
		cipher.start();
		cipher.update(forge.util.createBuffer(strData));
		cipher.finish();
		var encrypted = cipher.output.getBytes();
		var strData = forge.util.encode64(encrypted);
	};
	
	return strData;
};

function date2Str(x){
	var d = new Date(x * 1000);
	return d.toISOString().replace('Z', '');
}

function encryptData(data, encrypt=null) {
	var encryptedData = [];
	for (var i0=0; i0<data.length; i0++) {
		encryptedData.push({date: date2Str(data[i0].x), value: encryptValue(data[i0].y, encrypt)});
	};
	return encryptedData;
};

// AJAX for posting
function uploadData() {
	$.ajax({
		url : "upload/", // the endpoint
		type : "POST", // http method
		data : {
			series: $('#id_series').val(),
			date : $('#id_date').val(),
			record : encryptData($('#id_record').val()),
		}, // data sent with the post request
	
		// handle a successful response
		success : function(json) {
			$('#id_your_name').val(''); // remove the value from the input
			console.log('Python result: ' + json['result']);
			console.log(json);
			console.log('success'); // another sanity check
		},
	
		// handle a non-successful response
		error : function(xhr,errmsg,err) {
			$('#results').html("<div class='alert-box alert radius' data-alert>Oops! We have encountered an error: " + errmsg + 
					" <a href='#' class='close'>&times;</a></div>"); // add the error to the dom
			console.log(xhr.status + ": " + xhr.responseText); // provide a bit more info about the error to the console
		}
	});
};