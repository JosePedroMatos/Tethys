// Initial variables
var headerHeight = null;
var footerHeight = null;
var resizing = false;

// setting the middle div's height
fSetHeigth = function() {        		
	$("#divMiddleWrap").css({'top': $("#divHeaderFrame").height() + 'px', 'bottom': $("#divFooterFrame").height() + 'px'});
}

// toggling header
fToggleHeader = function() {
	if ($("#divHeaderFrame").height()==0) {
		$("#divHeaderFrame").height(headerHeight);
		$("#hideFrameHeader").css({'transform': 'translateY(50%)', 'cursor': 'n-resize'});
	} else {
		$("#divHeaderFrame").height(0);
		$("#hideFrameHeader").show();
		$("#hideFrameHeader").css({'transform': 'translateY(100%)', 'cursor': 's-resize'});
	}
	fSetHeigth();
}

// toggling footer
fToggleFooter = function() {
	if ($("#divFooterFrame").height()==0) {
		$("#divFooterFrame").height(footerHeight);
		$("#hideFrameFooter").css({'transform': 'translateY(-50%)', 'cursor': 's-resize'});
	} else {
		$("#divFooterFrame").height(0);
		$("#hideFrameFooter").show();
		$("#hideFrameFooter").css({'transform': 'translateY(-100%)', 'cursor': 'n-resize'});
	}
	fSetHeigth();
}

// Set middle divs' widths
fSetWidth = function() {
	var remainingSpaceTmp = $("#divLeftFrame").parent().width() - $("#divLeftFrame").outerWidth(),
    divTwo = $("#divMainFrame"),
    divTwoWidth = (remainingSpaceTmp - (divTwo.outerWidth() - divTwo.width())) / $("#divLeftFrame").parent().width() * 100 + "%";
    divTwo.width(divTwoWidth);
}	

//resizing middle divs' widths when the window changes
$(window).on('resize', function(){
	fSetWidth();
});

// change de url of the central iFrames
fLoadMidDiv = function(iFrame1, iFrame2) {
	$("#divMiddleWrap").hide();
	if (iFrame2!=null) {
		$('#mainFrame').attr('src',iFrame2);
		$('#leftFrame').attr('src',iFrame1);   
	} else {
		$("#divLeftFrame").css({"min-width": "0px"});
		$('#divLeftFrame').width(0);
		$('#mainFrame').attr('src',iFrame1);
	}
	fSetWidth();
	$("#divMiddleWrap").show();
};

// Load the home iframes
fLoadHome = function() {
	parent.fLoadMidDiv('left.html', 'main.html');
}

fLoadInNewTab = function(url) {
	var win = window.open(url, '_blank');
	if(win){
	    //Browser has allowed it to be opened
	    win.focus();
	}else{
	    //Broswer has blocked it
	    alert('Please allow popups for this site');
	}
}

fMainJumpTo = function(id) {
	//var src = parent.mainFrame.src.split("#");
	//parent.mainFrame.src = src[0] + "#" + id;
	parent.mainFrame.src = '/main.html' + "#" + id;
}

fLogin = function() {
	$('#hidden').attr('href', '/accounts/login/?next=/close/');
	$('#hidden').trigger('click');
}
