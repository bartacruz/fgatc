var my_callsign = getprop("/sim/multiplay/callsign");
var root="/sim/fgatc";
var orders={};
var messages={};
var requests={};

var controller = nil;
var airport = nil;
var selected_runway = "";

var channel_message ="sim/multiplay/generic/string[16]";
var channel_message2 ="sim/multiplay/generic/string[14]";
var channel_request ="sim/multiplay/generic/string[17]";
var channel_order ="sim/multiplay/generic/string[18]";
var channel_order2 ="sim/multiplay/generic/string[15]";
var channel_oid = "sim/multiplay/generic/string[10]";

var channel_freq ="sim/multiplay/transmission-freq-hz";
var channel_freq_v2 ="sim/multiplay/comm-transmit-frequency-hz";
var channel_atc_message="/sim/messages/atc";
var channel_mp_message="/sim/messages/ai-plane";
var channel_pilot_message="/sim/messages/pilot";

var radio_on=0;
var frequency_1 = nil;
var frequency_2 = nil;

var last_order = nil;

var check_freq = func(freq) {
	return (radio_on and ((freq == frequency_1) or (freq == frequency_2)));
}

var check_models = func(){
	foreach (var n; props.globals.getNode("ai/models", 1).getChildren("multiplayer")) {
		if (!n.getNode("valid").getValue()) {
			continue;
		}
		
		var freq = n.getNode(channel_freq).getValue();
                if (!freq) {
		    freq = n.getNode(channel_freq_v2).getValue();
                }
			
		var callsign = n.getNode("callsign").getValue();
		var order = n.getNode(channel_order).getValue() or "";
		var order2 = n.getNode(channel_order2).getValue() or "";
		order = order ~ order2;
		
		var updated = 0;
				  
		if (!contains(orders,callsign) or orders[callsign] != order) {
			updated = 1;
		    orders[callsign]=order;
		    porder = parse_order(order);
		    if (porder == nil or size(porder) == 0) {
		    	 print(sprintf("[FGATC] Ignoring empty order from %s: %s; %s",callsign,order, porder));
		    } else if (!check_freq(freq)){
		    	print(sprintf("[FGATC] Ignoring order not on my freq: %s; %s and %s: %s",freq,frequency_1,frequency_2, order));
		    } else if (porder['to'] != my_callsign) {
		    	print(sprintf("[FGATC] Ignoring order for other: %s; %s", porder['to'], order));
		    } else {
		    	print(sprintf("[FGATC] New order from %s; %s",callsign,order));
		    	process_order(porder);
		    }
		    
		}
		var request = n.getNode(channel_request).getValue();
		if (request and (!contains(requests,callsign) or requests[callsign] != request)) {
			requests[callsign] = request;
			updated = 1;
		}
		
		var message = n.getNode(channel_message).getValue() or "";
		var message2 = n.getNode(channel_message2).getValue() or "";
		message = message ~ message2;
		if (!contains(messages,callsign) or messages[callsign] != message ) {
		    messages[callsign]=message;
		    if (message == nil or size(message) == 0) {
		    	print(sprintf("[FGATC] Ignoring empty message from %s: %s", callsign, message));	
		    } else if (message and check_freq(freq)){
		    	var model = n.getNode("sim/model/path").getValue();
		    	print(sprintf("[FGATC] New message from %s (%s): %s",callsign,model, message));
		    	if ( find("ATC",model)+1 ) { 
		    		setprop(channel_atc_message,message);
		    	} else {
		    		
		    		setprop(channel_mp_message,message);
		    	}
		    } else {
		    	print(sprintf("[FGATC] Ignoring message on freq %s (mine %s and %s): %s", freq, frequency_1,frequency_2, message));
		    }
		}
	}
}

var set_radio = func(apt=nil,contr=nil) {
	airport = apt;
	setprop(root ~ "/airport", apt == nil ? '':apt);
	controller = contr;
	setprop(root ~ "/controller", controller == nil ? '':controller);
	if (controller) {
		screen.log.write(sprintf("Tunned to %s", controller),0.7, 1.0, 0.7);
	}
}

var set_frequency = func(node) {
	print("[FGATC] Set frequency");
	if ( ! getprop("/systems/electrical/outputs/comm")) {
		radio_on=0;
		set_radio();
		return;
	}
	radio_on=1;
	var f1 = sprintf("%f", getprop("/instrumentation/comm/frequencies/selected-mhz") );
	var comm1 = getprop("/instrumentation/comm/power-btn");
	var f2 = sprintf("%f",getprop("/instrumentation/comm[1]/frequencies/selected-mhz"));
	var comm2 = getprop("/instrumentation/comm[1]/power-btn");
	print(sprintf("[FGATC] Set frequency %s,%s,%s,%s", comm1,f1,comm2,f2));
	
	if (comm1 and f1 != frequency_1) {
		print(sprintf("[FGATC] New frequency on COM1: %s (old: %s)",f1,frequency_1));
		frequency_1 = f1;
		setprop(channel_freq, frequency_1);
		setprop(channel_freq_v2, string.replace(sprintf("%s",f1),'.',''));
		sendmessage('tunein',0);
	}
	if (comm2 and f2 != frequency_2) {
		print(sprintf("[FGATC] New frequency on COM2: %s (old: %s)",f2,frequency_2));
		frequency_2 = f2;
	}
}

var parse_order = func(order=nil) {
	var aux=sprintf("return %s",order);
	var ff = call(compile,[aux],var err=[]);
	if (size(err)) {
		print(sprintf("[FGATC]: ERROR processing order %s: %s", order,err));
		return nil;
	}
	return ff();
}

var process_order = func(order=nil) {
	if (order == nil or order == "") {
		print("[FGATC]: Empty order. returning");
		return;
	}
	last_order = order;
	if (last_order['rwy']){
		selected_runway=last_order['rwy'];
	}
	
	if (last_order['ord']=='tuneok') {
		set_radio(last_order['apt'],last_order['atc']);
	} else {
		print( sprintf("[FGATC] Dummy %s (not sent)",parse_message("roger") ) );
	}
	setprop( channel_oid, sprintf("%s",last_order['oid']));
	#print(sprintf("ATCNG incoming order=%s",order));
	compute_flow();

}

var compute_flow = func() {
	var next="";
	var lao =last_order['ord']; 
	if ( lao == 'startup') {
		next = "readytaxi";
	} else if (lao == 'taxito') {
		if (last_order['short']) {
			next = "holdingshort";
		} else {
			next = "readytko";
		}
	} else if (lao == 'clearland') {
		next = "clearrw";
	} else if (lao == 'soff') {
		next = "goodbye";
	} else if (lao == 'cleartk' or lao == "cleartngo") {
		next = "leaving";
	} else if (lao == 'join' or lao == 'cirrep') {
		var cirw = last_order['cirw'];
		next = cirw;
	} 
	var nn =fgatc.root ~ "/next"; 
	print(sprintf("[FGATC] compute flow. node=%s, next=%s",nn,next));
	setprop(nn,next);
};

##### MESSAGES #####

var messages = {
	roger:'{ack}{qnh}{tuneto}, {cs}',
	repeat:'{apt}, {cs}, say again',
	startup: '{apt}, {cs},{parkn} request startup{atis}',
	readytaxi: '{apt}, {cs},{atis} ready to taxi',
	holdingshort: '{apt}, {cs},{atis} holding short {rwyof}',
	readytko: '{apt}, {cs}, ready for departure',
	leaving: '{apt}, {cs}, leaving airfield',
	transition: '{apt}, {cs} to transition your airspace{atis}',
	inbound: '{apt}, {cs}{atis} for inbound approach',
	crosswind: '{apt}, {cs}, crosswind for runway {rwy}',
	downwind: '{apt}, {cs}, downwind for runway {rwy}',
	base: '{apt}, {cs}, turning base for runway {rwy}',
	final: '{apt}, {cs},{atis} final for runway {rwy}{tngo}',
	straight: '{apt}, {cs},{atis} straight for runway {rwy}',
	clearrw: '{apt}, {cs}, clear {rwyof}',
	around: '{apt}, {cs}, going around',
	goodbye: 'Goodbye',
	withyou: '{apt}, {cs}, with you at {alt} feet, heading {heading}{atis}',
	tunein: '',
	
};

var LETTERS = [
	"alpha", "bravo", "charlie", "delta", "echo",
	"foxtrot", "golf", "hotel", "india", "juliet",
	"kilo", "lima", "mike", "november", "oscar",
	"papa", "quebec", "romeo", "sierra", "tango",
	"uniform", "victor", "whiskey", "xray", "yankee", "zulu"
];

var NUMBERS=['zero','one','two','three','four','five','six','seven','eight','niner'];

var sendmessage = func(message="",dlg=1){
	var msg = parse_message(message);
	var request = sprintf("req=%s;freq=%.2f;mid=%s",message,frequency_1,int(rand()*10000));
	if (message=='roger' and last_order != nil){
		request = sprintf("%s;laor=%s",request,last_order['ord']);
	}
	if (get_option('tngo')) {
		request = sprintf("%s;tngo=1",request);
	}
	if (get_option('atis')) {
		request = sprintf("%s;atis=%s",request, get_option('atis'));
	}
	if (get_option('remain')) {
		request = sprintf("%s;remain=1",request);
	}
	print(sprintf("[FGATC] Sendmessage: %s | %s",request , msg));
	setprop(channel_request,request);
	setprop(channel_message,msg);
	setprop(channel_pilot_message,msg);
	if (dlg) {
		fgatcdialog.dialog.destroy();
	}
};

var repeat = func() {
	print("[FGATC]: repeat");
	fgatc.sendmessage("repeat");
};

# Readback last order
var readback = func() {
	sendmessage("roger");
};

var short_callsign=func(callsign){
	var cs = string.lc(callsign);
	cs = string.replace(cs,"lv-","");
	cs = string.replace(cs,"cx-","");
	return sprintf("%s %s %s", say_char(chr(cs[0])), say_char(chr(cs[1])), say_char(chr(cs[2])) );
};

var say_char = func(c) {
    if (c==nil) {
		return c;
	}
	var ord1 = string.lc( sprintf("%s",c) )[0];
	var base = 'a'[0];
	if (ord1 >= base) {
		return LETTERS[ord1 - base];
	} else if (isnum(c)){
		return say_number(c);
	}
}
var say_number=func(number) {
	if (number==nil) {
		return number;
	}
	var arr=split('',""~(number));
	forindex(n;arr ){
		arr[n]= NUMBERS[arr[n]];
	}
	return string.join(' ', arr);
}

var get_option = func(option=nil) {
	var prop = fgatc.root ~ "/options/" ~ option;
	return getprop(prop);
};

var parse_message = func(tag) {
	if(tag == nil or tag == "") {
		return "";
	}
	var msg = messages[tag];
	if (msg == nil or msg == "") {
		return "";
	}
	# print (sprintf("parse_message. tag=%s, msg=%s",tag,msg));
	var sc = short_callsign(my_callsign);
	msg = string.replace(msg,'{cs}',sc);
	msg = string.replace(msg,'{rwy}',selected_runway);
	msg = string.replace(msg,'{rwyto}', "to runway " ~ selected_runway);
	msg = string.replace(msg,'{rwyof}', "of runway  " ~ selected_runway);
	msg = string.replace(msg,'{apt}',controller);
	msg = string.replace(msg,'{alt}',int(getprop("/position/altitude-ft")));
	msg = string.replace(msg,'{heading}',say_number(int(getprop("/orientation/heading-magnetic-deg"))));
	if (get_option('tngo')) {
		msg = string.replace(msg,'{tngo}', " for touch and go");
	} else {
		msg = string.replace(msg,'{tngo}', "");
	}		
	if (get_option('atis')) {
		msg = string.replace(msg,'{atis}', sprintf(", information %s, ", string.uc(say_char(get_option('atis'))) ) );
	} else {
		msg = string.replace(msg,'{atis}', "");
	}
	if ( getprop("/sim/presets/parkpos") != nil) {
		msg = string.replace(msg,'{parkn}', sprintf(" base %s,", getprop("/sim/presets/parkpos")));
	} else {
		msg = string.replace(msg,'{parkn}', "");
	}
	if (tag == "roger") {
		if(last_order['ord'] == 'taxito') {
			var ack = sprintf("taxi to %s",last_order['rwy']);
			if (last_order['short']) {
				ack ~= " and hold";
			}
			msg = string.replace(msg,'{ack}',ack);
		} else if(last_order['ord'] == 'taxipark') {
			var ack = sprintf("taxi to parking %s",last_order['parkn']);
			msg = string.replace(msg,'{ack}',ack);
		} else if(last_order['ord'] == 'cleartk') {
			msg = string.replace(msg,'{ack}','Cleared for takeoff');
		} else if(last_order['ord'] == 'startup') {
			msg = string.replace(msg,'{ack}','start up approved');
		} else if(last_order['ord'] == 'join') {
			var ack = sprintf("%s for %s at %s",last_order['cirw'],last_order['rwy'],last_order['alt']);
			msg = string.replace(msg,'{ack}',ack);
		} else if(last_order['ord'] == 'cirrep') {
			var ack = sprintf("report on %s",last_order['cirw']);
			if (last_order['number'] != nil and last_order['number'] > 1) {
				var nm =sprintf(" number %s",last_order['number']); 
				ack ~= nm;
			}
			msg = string.replace(msg,'{ack}',ack);
		} else if(last_order['ord'] == 'clearland') {
			var ack = sprintf("clear to land runway %s",last_order['rwy']);
			msg = string.replace(msg,'{ack}',ack);
		} else if(last_order['ord'] == 'cleartngo') {
			var ack = sprintf("clear touch and go runway %s",last_order['rwy']);
			msg = string.replace(msg,'{ack}',ack);
		} else if(last_order['ord'] == 'around') {
			var ack = sprintf("going around, will report on %s for %s",last_order['cirw'],last_order['rwy'] );
			msg = string.replace(msg,'{ack}',ack);
		} else if(last_order['ord'] == 'transition') {
			var ack = sprintf("clear to cross at %s",last_order['alt']);
			msg = string.replace(msg,'{ack}',ack);
		} else if(last_order['ord'] == 'tuneok') {
			msg = string.replace(msg,'{ack}','Roger');
			msg = string.replace(msg,'{tuneto}','');
		} else if(last_order['ord'] == 'straight') {
			var ack = sprintf("straight-in runway %s, report on %s",last_order['rwy'],last_order['cirw']);
			msg = string.replace(msg,'{ack}',ack);
		} else {
			msg = string.replace(msg,'{ack}','Roger');
		}
		if(last_order['atc'] == nil) {
			msg = string.replace(msg,'{tuneto}','');
		} else {
			var tuneto = sprintf(", %s on %s",last_order['atc'], last_order['freq']);
			msg = string.replace(msg,'{tuneto}',tuneto);
		}
		if (last_order['qnh'] != nil) {
			msg = string.replace(msg,'{qnh}', sprintf(" QNH %s",last_order['qnh']));
		} else {
			msg = string.replace(msg,'{qnh}', '');
		}
		msg = string.replace(msg, ",,", ",");
		msg = string.trim(msg,1, func(c) c==",");
	}
	return msg;
};

##### MAIN ######
setlistener("/instrumentation/comm/frequencies/selected-mhz",fgatc.set_frequency,1,0);
setlistener("/instrumentation/comm/power-btn",fgatc.set_frequency,1,0);
setlistener("/instrumentation/comm[1]/frequencies/selected-mhz",fgatc.set_frequency,1,0);
setlistener("/instrumentation/comm[1]/power-btn",fgatc.set_frequency,1,0);
setlistener("/control/switches/master-avionics",fgatc.set_frequency,1,0);

var models_timer = maketimer(1,check_models);
models_timer.start();
print("[FGATC] Started");
