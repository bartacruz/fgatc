var map=null;
var planes={};
var _handler=null;
var _follow=null;
var _route=null;
function initMap(ll) {
	map = L.map('map').setView(ll,13);
	L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png?{foo}', {foo: 'bar'}).addTo(map);	
}
function show_plan(ev) {
	console.debug(ev.target.options);
	get_wps(ev.target.options.title);
}
function updatePlane(fields) {
	marker = planes[fields.callsign];
	if (_follow == fields.callsign) {
		map.panTo([fields.lat,fields.lon]);
		marker.options.icon.iconUrl=static_url + 'images/plane_f-25.png'
	}
	marker.options.angle=fields.heading;
	marker.setLatLng([fields.lat,fields.lon]);	
}
function addPlane(fields) {
	callsign=fields.callsign;
	var planeicon = L.icon({
	    iconUrl: static_url + 'images/plane-25.png',
	    iconSize: [25,25],
	    className: callsign,
	});
	var marker = L.rotatedMarker([fields.lat,fields.lon],{icon:planeicon,title:callsign,angle:fields.heading}).addTo(map);
	marker.on({
		click:show_plan,
	});
	planes[callsign]= marker;
	//console.debug(callsign,marker.getLatLng(),marker);
}
function start() {
	_handler = setInterval(fg_update,2000);
}
function stop() {
	clearInterval(_handler);
}
function update_aircrafts(data,textStatus,jqXHR) {
	//console.debug("update aircraft",data);
	for (i in data.aircrafts) {
		
		var acft= data.aircrafts[i];
		//console.debug(i,acft);
		if (planes[acft.fields.callsign]) {
			updatePlane(acft.fields);
		} else {
			addPlane(acft.fields);
		}
		
	}
}
function update_error(XHR, textStatus, errorThrow) {
	console.debug("ERROR",textStatus,errorThrow);
}
function fg_update(){
	url = '/map/aircrafts/';
	data = {
			center: ""+map.getCenter(),
			bounds: ""+map.getBounds(),
			zoom: map.getZoom(),
			lat: map.getCenter().lat,
			lon: map.getCenter().lng
	};
	//console.debug("update. data=",data);
	$.ajax({
		dataType: "json",
		url: url,
		data: data,
		success: update_aircrafts,
		error: update_error
	});
}
function update_plan(data,textStatus,jqXHR) {
	console.debug("update plan",data);
	var path =[]
	var markers=[]
	for (i in data.waypoints) {
		var wp= data.waypoints[i];
		//console.debug(i,wp);
		var wpicon = L.icon({
		    iconUrl: static_url + 'images/wp.png',
		    className: "wp-"+wp.pk,
		    iconSize:[25,25],
		    iconAnchor:[13,25],
		});
		var pos = [wp.fields.lat,wp.fields.lon]
		var marker = L.marker(pos,{icon:wpicon,title:wp.fields.name}).addTo(map);
		markers.push(marker)
		path.push(pos);
	}
	if (_route){
		_route.setLatLngs(path);
		_route.redraw();
	} else {
		_route = L.polyline(path, {color: 'red', weight:3, lineJoin:'round'}).addTo(map);		
	}
	map.fitBounds(_route.getBounds());
	
}
function get_wps(callsign){
	if (_follow == callsign){
		_follow= null;
	} else {
		url = '/map/flightplan/';
		data = {
			callsign: callsign
		};
	//	console.debug("update. data=",data);
		$.ajax({
			dataType: "json",
			url: url,
			data: data,
			success: update_plan,
			error: update_error
		});
		_follow=callsign;
	}

}
