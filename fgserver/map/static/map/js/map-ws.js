
var fgatcws=null;

var _map_start=map_start; // backup method before override
function map_start(){
	var url = "ws://" + window.location.host+ "/aircrafts";
	fgatcws = new WebSocket(url);
	fgatcws.onopen = function(event) {
    	console.debug("onopen",this,event);
    	ws_update_pos();
    }
	fgatcws.onmessage = function(event) {
    	var message=JSON.parse(event.data);
    	//console.debug("onmessage:",message);
    	update_aircrafts(message.data);
    }
	map.on({moveend:ws_update_pos});
	fgatcws.onclose = function(event) {
		console.debug("onclose:",event);
	};
	fgatcws.onerror = function(event) {
		console.debug("onerror:",event);
	}
}
function ws_update_pos() {
	fgatcws.send(JSON.stringify({
		lat: map.getCenter().lat,
		lon: map.getCenter().lng,
		zoom:map.getZoom(),
		
		}));
}

