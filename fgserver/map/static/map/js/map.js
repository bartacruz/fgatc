var map=null;
var planes={};
var _handler=null;
var _follow=null;
var _route=null;
var _route_markers=null;
var _spot=null;
var callsigns=[];
var taxiways = {};

function showcords(a,b,c){
	$('#lat').html(a.latlng.lat);
	$('#lon').html(a.latlng.lng);
	var pos = [a.latlng.lat,a.latlng.lng]
	if (_spot == null) {
		var wpicon = L.icon({
		    iconUrl: static_url + 'images/wp.png',
		    className: "spot",
		    iconSize:[25,25],
		    iconAnchor:[13,25],
		});
		
		_spot = L.marker(pos,{icon:wpicon,title:"spot"}).addTo(map);
	} else {
		_spot.setLatLng(pos);
	}
}
function edit_osm() {
	var lat = $('#lat').html();
	var lon = $('#lon').html();
	var zoom=16;
	var url="http://www.openstreetmap.org/edit#map="+zoom+"/"+lat+"/"+lon;
	var win = window.open(url, '_blank');
	if (win) {
		win.focus();
	}
}
function initMap(ll) {
	map = L.map('map').setView(ll,13);
	map.on({click:showcords,});
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
function addPlane(fields,airport) {
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

function map_start() {
	_handler = setInterval(fg_update,2000);
}
function map_stop() {
	clearInterval(_handler);
}

function pan_callsign(a,b,c) {
	var cs = $( this ).text();
	var plane = planes[cs];
	console.debug('pan callsign', cs, plane );
	map.panTo([plane._latlng.lat,plane._latlng.lng]);
	
}

function update_aircrafts_XHR(data,textStatus,jqXHR) {
	update_aircrafts(data.aircrafts)
}
var _airports = {};

function update_airports(airports) {
	
	for (i in airports) {
		var airport= airports[i];
		var fields = airport.fields;
		if (!_airports[fields.icao]) {
			console.debug("update airport",airport, airports);	
			callsign=airport.fields.icao;
			var planeicon = L.icon({
		    	iconUrl: static_url + 'images/atc.png',
		    	iconSize: [25,25],
	    		className: callsign,
			});
			var marker = L.marker([fields.lat,fields.lon],{icon:planeicon,title:callsign}).addTo(map);
			marker.on({
				click: get_airport,
			});
			_airports[callsign]= marker;
			//console.debug(callsign,marker.getLatLng(),marker);
		}
	}
}
function update_aircrafts(aircrafts) {
	//console.debug("update aircraft",data);
	var ceeses=[]
	var cslist=$('#aircraft_list');
	for (i in aircrafts) {
		var acft= aircrafts[i];
		//console.debug(i,acft);
		if (planes[acft.fields.callsign]) {
			updatePlane(acft.fields);
			ceeses.push(callsigns.pop(acft.fields.callsign));
		} else {
			addPlane(acft.fields);
			ceeses.push(acft.fields.callsign);
			cslist.append("<a class='dropdown-item cs_li' id='cs_"+acft.fields.callsign+"' href='#'>"+acft.fields.callsign+"</a>");
		}
	}
	for (i in callsigns) {
		$('#cs_'+callsigns[i]).remove();
	}
	callsigns = ceeses;
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
		success: update_aircrafts_XHR,
		error: update_error
	});
}
function show_runway(data,textStatus,jqXHR) {
	console.debug("show_runway",data);
	_runway = L.polyline(data.boundaries, {color: 'blue', weight:3, lineJoin:'round'}).addTo(map);
	rstart = data.start;
	var wpicon = L.icon({
	    iconUrl: static_url + 'images/wp.png',
	    className: "runway-start",
	    iconSize:[25,25],
	    iconAnchor:[13,25],
	});
	var pos = [rstart[0],rstart[1]];
	var marker = L.marker(pos,{icon:wpicon,title:'Runway Start'}).addTo(map);
}
function update_plan(data,textStatus,jqXHR) {
	//console.debug("update plan",data);
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
var _taxiways={};
function show_airport(data,textStatus,jqXHR) {
	console.debug("airport",data);
	for (var i in data.taxiways) {
		var way = data.taxiways[i];
		var path =[];
		for (var j in way.nodes) {
			node = way.nodes[j];
			path.push([node.lat,node.lon]);
		}
		console.debug(way.name, path);
		var line = L.polyline(path, {color: 'yellow', weight:4, lineJoin:'round'}).addTo(map)
		_taxiways[way.name] = line;
	}
}
function get_airport(ev) {
	var icao = ev.target.options.title;
	url = '/map/airport/';
	data = {
		icao: icao
	};
	$.ajax({
		dataType: "json",
		url: url,
		data: data,
		success: show_airport,
		error: update_error
	});
	get_runway(ev);
}
function get_runway(ev) {
	var icao = ev.target.options.title;
	url = '/map/runway/';
		data = {
			icao: icao
		};
	//	console.debug("update. data=",data);
		$.ajax({
			dataType: "json",
			url: url,
			data: data,
			success: show_runway,
			error: update_error
		});
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
