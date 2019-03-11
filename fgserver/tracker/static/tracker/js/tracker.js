var BASE_URL = 'https://fgtracker.ml/modules/fgtracker/interface.php';

function get_flights(callsign,callback) {
	var data = {
			action:"flights",
			callsign: callsign
	}
	$.ajax({
		url : BASE_URL,
		data: data,
		success: callback
	})
}