function round(val,dec){
 	try {
 	   return parseFloat(val).toFixed(dec);
 	} catch (e) {
 		return val;
 	}
};
	 
$.widget("fgatc.bench", {
	options: $.extend(this.options,{
		
	}),
	 _create: function() {
	 	this.selected = null;
	 	$("#bench").on('stateplane',$.proxy(this.update_plane,this));
		$(".planes-list").on("click",".plane-item",$.proxy(this.select_plane,this));
	 },
	 update_plane: function(event,plane) {
	 	var planes= $(this.element).find(".planes-list");
	 	var le = planes.find("div[callsign='"+plane.callsign+"']");
	 	if (!le.length) {
	 		planes.append("<div class='dropdown-item plane-item' callsign='"+plane.callsign+"'>"+plane.callsign+"</div>");
	 	}
	 	if (!this.selected) {
	 		this.select(plane.callsign);
	 	}
	 	if (this.selected == plane.callsign) {
	 		this.fill_plane(plane);
	 	}
	 	
	 },
	 select_plane: function(event) {
		var callsign = $(event.target).attr("callsign");
		this.reset_bench();
		this.select(callsign);

	 },
	 select: function(callsign) {
	 	this.selected = callsign;
	 	$(this.element).find(".selected-callsign").html(callsign);
	 },
	 fill_plane: function(plane) {
	 	//console.debug("plane:",plane);
	 	$("#bench .properties .lat").html(round(plane.position[0],5));
	 	$("#bench .properties .lon").html(round(plane.position[1],5));
	 	$("#bench .properties .altitude").html(parseInt(plane.altitude));
	 	$("#bench .properties .speed").html(parseInt(plane.speed));
	 	$("#bench .properties .vertical-speed").html(round(plane.vertical_speed,1));
	 	$("#bench .properties .turn-rate").html(round(plane.turn_rate,2));
	 	$("#bench .properties .yaw").html(round(plane.course,1));
	 	$("#bench .properties .pitch").html(round(plane.pitch,1));
	 	$("#bench .properties .roll").html(round(plane.roll,3));
	 	$("#bench .properties .waypoint-name").html(plane.waypoint_name);
	 	$("#bench .properties .waypoint-heading").html(round(plane.waypoint_heading,1));
	 	$("#bench .properties .waypoint-distance").html(round(plane.waypoint_distance,1));
	 	$("#bench .properties .state").html(plane.state);
	 	
	 	$("#bench .comms .request").html(plane.request);
	 	$("#bench .comms .message").html(plane.message);
	 	for (c in plane.clearances) {
	 		if (plane.clearances[c]) {
	 			$("#bench .clearances .c-"+c).addClass("active");
	 		} else {
	 			$("#bench .clearances .c-"+c).removeClass("active");
	 		}
	 	}
	 	if (plane.clearances.runway) {
	 		$("#bench .clearances .c-runway").html((""+plane.clearances.runway).padStart("2","0"));
	 	}
	 	
	 	
	 },
	 reset_bench: function() {
		//console.debug("plane:",plane);
		$("#bench .properties .lat").html("");
		$("#bench .properties .lon").html("");
		$("#bench .properties .altitude").html("");
		$("#bench .properties .speed").html("");
		$("#bench .properties .vertical-speed").html("round(plane.vertical_speed,1");
		$("#bench .properties .turn-rate").html("");
		$("#bench .properties .yaw").html("");
		$("#bench .properties .pitch").html("");
		$("#bench .properties .roll").html("");
		$("#bench .properties .waypoint-name").html("");
		$("#bench .properties .waypoint-heading").html("");
		$("#bench .properties .waypoint-distance").html("");
		$("#bench .properties .state").html("");
		
		$("#bench .comms .request").html("");
		$("#bench .comms .message").html("");
		$("#bench .clearances").removeClass("active");
	},
});


$(document).ready(function() {
	$("#bench").bench();
	var url = "ws://" + window.location.host+ "/stateplanes";
	fgbench = new WebSocket(url);
	fgbench.onopen = function(event) {
    	console.debug("BENCH onopen",this,event);
    }
	fgbench.onmessage = function(event) {
    	var message=JSON.parse(event.data);
    	//console.debug("BENCH onmessage:",message);
    	$("#bench").trigger('stateplane',[message.data]);
    	
    }
	fgbench.onclose = function(event) {
		console.debug("BENCH onclose:",event);
	};
	fgbench.onerror = function(event) {
		console.debug("BENCH onerror:",event);
	}
});