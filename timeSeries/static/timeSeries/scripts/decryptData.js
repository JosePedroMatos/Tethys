function hashPassword(password) {
	// Define and hash password
	// TODO: interact with the server for passwords
	if (password==null) {
		return null;
	} else {
		return forge.md.sha256.create().update(password).digest().getBytes();
	}
	
};

function Point(x, y) {
	this.x = x/1000;
	this.y = y;
};

// Define dencryption function
function decryptValue(data, key=null) {
	var strData = '';
	            
	if (key) {
		// TODO: interact with the server for passwords
					
		// decrypt data
		var decipher = forge.cipher.createDecipher('AES-ECB', key);
		decipher.start();
		decipher.update(forge.util.createBuffer(forge.util.decode64(data)));
		decipher.finish();
		strData = (JSON.parse(decipher.output.getBytes()));	
	} else {
		strData = data;
	}
	return parseFloat(strData);
};

function decryptData(data, key=null) {
	var decryptedData = [];
	for (var i0=0; i0<data.length; i0++) {
		decryptedData.push(new Point(Date.parse(data[i0].x + 'Z'), decryptValue(data[i0].y, key)));
	};
	return decryptedData;
};