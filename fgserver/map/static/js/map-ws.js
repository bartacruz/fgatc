
var updater = {
    socket: null,

    start: function() {
        var url = "ws://" + location.host.split(":")[0] + ":8888/ws";
        updater.socket = new WebSocket(url);
        updater.socket.onopen = function(event) {
        	console.debug("onopen",this,event);
        	ws_update_pos();
        }
        updater.socket.onmessage = function(event) {
        	
        	var message=JSON.parse(event.data);
        	//console.debug("onmessage:",message);
        	update_aircrafts(message.data);
        }
    },
};
var _map_start=map_start; // backup method before override
function map_start(){
	updater.start();
	map.on({moveend:ws_update_pos});
}
function ws_update_pos() {
	updater.socket.send(JSON.stringify({
		lat: map.getCenter().lat,
		lon: map.getCenter().lng,
		zoom:map.getZoom(),
		
		}));
}

