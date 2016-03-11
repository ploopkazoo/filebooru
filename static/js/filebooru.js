$(document).ready(function(){
	$("#publicbox").change(function(){
		if ($("#publicbox").is(":checked")) {
			$("#sharingbox").fadeOut("fast");
		} else {
			$("#sharingbox").fadeIn("fast");
		}
	})
})
