var airport=nil;
var frequency = nil;
var controller=nil;
var callsign = getprop("/sim/multiplay/callsign");
var root="/sim/atcng";
var freq_node= root ~ "/" ~ "frequency";
var aptname_node= root ~ "/" ~ "aptname";
var aptcode_node= root ~ "/" ~ "aptcode";
var controller_node= root ~ "/" ~ "controller";
var chatchannel="/sim/messages/pilot";
var chataichannel="/sim/messages/ai-plane";
var atcchannel="/sim/messages/atc";
var freqchannel="sim/multiplay/transmission-freq-hz";
var oidnode="sim/multiplay/generic/string[10]";
var pilotchannel="sim/multiplay/generic/string[17]";
var serverchannel="sim/multiplay/generic/string[18]";
var serverchannel2="sim/multiplay/generic/string[15]";
var servermsgchannel="sim/multiplay/generic/string[16]";
var servermsgchannel2="sim/multiplay/generic/string[14]";
var atcnode=nil;
var atclistener = nil;
var selected_runway="";
var last_order=nil;
var last_order_string=nil;
var viewnode = "depart";
var CONFIG_DLG = 0;

var LETTERS = [
"alpha", "bravo", "charlie", "delta", "echo",
"foxtrot", "golf", "hotel", "india", "juliet",
"kilo", "lima", "mike", "november", "oscar",
"papa", "quebec", "romeo", "sierra", "tango",
"uniform", "victor", "whiskey", "xray", "yankee", "zulu"
];

var NUMBERS=['zero','one','two','three','four','five','six','seven','eight','niner'];

# Readback last order

var readback = func() {
	atcng.sendmessage("roger");
};




var short_callsign=func(callsign){
	var base='a';
	var cs = string.lc(callsign);
    return sprintf("%s %s %s", LETTERS[cs[0] - base[0]],
                             LETTERS[cs[1] - base[0]],
                             LETTERS[cs[2] - base[0]]
                             );
};
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
var get_controller=func() {
	return getprop(controller_node);
}
var set_controller=func(cont) {
	controller = cont;
	setprop(controller_node,controller);
}
var get_freq=func() {
	return getprop(freq_node);
}
var set_freq=func(freq) {
	frequency = freq;
	setprop(freq_node,freq);
	setprop(freqchannel,freq);
}
var sendmessage = func(message="",dlg=1){
	var msg = parse_message(message);
	var request = sprintf("req=%s;freq=%.2f;mid=%s",message,frequency,int(rand()*10000));
	if (message=='roger' and last_order != nil){
		request = sprintf("%s;laor=%s",request,last_order['ord']);
	}
	if (get_option('tngo')) {
		request = sprintf("%s;tngo=1",request);
	}
	if (get_option('remain')) {
		request = sprintf("%s;remain=1",request);
	}
	print(sprintf("Sendmessage: %s | %s",request , msg));
	setprop(pilotchannel,request);
	setprop(chatchannel,msg);
	if (dlg) {
		dialog.destroy();
	}
};
var repeat = func() {
	print("ATCNg: repeat");
	atcng.sendmessage("repeat");
}
var _ml={};
var orderlisteners={};
var chatlisteners={};

var _add_model=func(path) {
	var mporders = sprintf("%s/%s",path,serverchannel);
	var mpchat = sprintf("%s/%s",path,servermsgchannel);
	
	print(sprintf("Adding listener for new MP plane %s",path));
	orderlisteners[path]=setlistener(mporders, atcng.readorder, 0, 0);
	chatlisteners[path]=setlistener(mpchat, atcng.readmessage, 0, 0);
}

var model_added = func(node) {
	print(sprintf("entering model added with %s",node));
	debug.dump(node);
	var path = node.getValue();
	print("orderlisteners before:");
	debug.dump(orderlisteners);
	if (contains(orderlisteners,path)) {
		print(sprintf("removing old order listener for new MP plane %s",path));
    	removelistener(orderlisteners[path]);
    	delete(orderlisteners,path);
    	print("orderlisteners after:");
    	debug.dump(orderlisteners);
	
	}
	print(sprintf("chatlisteners before: %s", chatlisteners));
	debug.dump(chatlisteners);
	if (contains(chatlisteners,path)) {
		print(sprintf("removing old chat listener for new MP plane %s",path));
    	removelistener(chatlisteners[path]);
    	delete(chatlisteners,path);
    	print(sprintf("chatlisteners after: %s", chatlisteners));
		debug.dump(chatlisteners);
	}
	#var valid = getprop(path,'valid');
	#print("valid=");
	#debug.dump(valid);
	#if (valid) {
		#var mpnode = props.globals.getNode(path);
		#settimer(func{atcng._add_model(mpnode)},1);
		atcng._add_model(path);
		debug.dump(orderlisteners);
		debug.dump(chatlisteners);
	#} else {
	#	print(sprintf("ignoring invalid model %s",path));
	#}
} 

var model_removed = func(node) {
	print(sprintf("entering model removed with %s",node));
	debug.dump(node);
	var path = node.getValue();
	debug.dump(orderlisteners);
	if (contains(orderlisteners,path)) {
		print(sprintf("removing old order listener for new MP plane %s",path));
    	removelistener(orderlisteners[path]);
    	delete(orderlisteners,path);
	}
	debug.dump(chatlisteners);
	if (contains(chatlisteners,path)) {
		print(sprintf("removing old chat listener for new MP plane %s",path));
    	removelistener(chatlisteners[path]);
    	delete(chatlisteners,path);
	}
} 
var check_models = func() {
	print("Starting check_models");
	foreach (var n; props.globals.getNode("ai/models", 1).getChildren("multiplayer")) {
		print(sprintf("Discovered MP plane %s.",n.getPath()));
		atcng._add_model(n.getPath());
	}
}
var check_model = func(node=nil) {
	print("Starting check_model");
	var ainodes=[];
	foreach (var n; props.globals.getNode("ai/models", 1).getChildren("multiplayer")) {
		debug.dump(n);
		if ((var valid = n.getNode("valid")) == nil or (!valid.getValue())) {
        	print("check_model: continue 1");
        	continue;
        }
        if ((var callsign = n.getNode("callsign")) == nil or !(callsign = callsign.getValue())) {
            print("check_model: continue 2");
        	continue;
        }
        var callsign =  n.getNode("callsign").getValue();
        var model =  n.getNode("sim/model/path").getValue();
        var freq =  n.getNode(freqchannel).getValue();
        if (airport==nil and model == "ATC" and freq == frequency) {
        	print(sprintf("ATC controller for %s found in %s",frequency,n.getPath()));
        	atcnode = n;
        	if (contains(_ml, callsign)) {
        		print(sprintf("removing AI plane of new ATC %s",callsign));
        		removelistener(_ml[callsign]);
        		delete(_ml,callsign);
        	}
			var sc = atcnode.getNode(serverchannel).getPath();
			print("ATCNG listening in " ~ sc);
			atclistener = setlistener(sc, atcng.readmessage, 0, 0);
   		} else {
			print("checking ai-plane " ~ callsign);
			if (!contains(_ml,callsign) and (atcnode == nil or n.getPath() != atcnode.getPath()) and freq == frequency){
				print("ATCNG adding ai-plane " ~ callsign);
				var nnode=n;
				var aic=nnode.getNode(servermsgchannel).getPath();
				_ml[callsign]=setlistener(aic,readaimessage,0,0);
				append(ainodes,aic);
					
			}
		} 
	}
	print(sprintf("check_model end. atc=%s, ml=%s",atcnode,size(ainodes)));
	
}

var readorder = func(node=nil) {
	print("INCOME ORDER");
	var model_path=string.join("/",split("/",node.getPath())[0:3]);
	var model_freq= getprop(model_path,freqchannel);
	if (frequency != model_freq) {
		print(sprintf("my freq=%s, sender's freq=%s",frequency,model_freq));
		print(sprintf("Wrong frequency %s . Ignoring message: %s",model_freq,order));
		return;
	}

	var order = node.getValue();
	if (order == nil or order == '') {
		print("readorder: Empty order. returning");
		return;
	}
	var order2 = getprop(model_path,serverchannel2);
	if (order2 != nil and order2 != "") {
		print("Concatenating order and order2");
		order= order ~ order2;
	}
	print("readorder: " ~ order);
	last_order_string=order;
	var aux=sprintf("return %s",order);
	var ff = call(compile,[aux],var err=[]);
	if (!size(err)) {
		var laor = ff();
		if (laor['to'] != callsign){
			print(sprintf("ignoring order for %s",laor['ord']));
		} else if (last_order != nil and laor['oid'] == last_order['oid']) {
			print("Order already received");
		} else {
			last_order = laor;
			print(sprintf("ATCNG laor=%s",last_order));
			if (last_order['rwy']){
				selected_runway=last_order['rwy'];
			}
			if (last_order['ord']=='tuneok') {
				set_comm(last_order['apt'],last_order['atc']);
			}
			setprop(oidnode,sprintf("%s",last_order['oid']));
			print(sprintf("ATCNG incoming order=%s",order));
			compute_flow(laor);
		}
	}
}

var readmessage = func(node=nil) {
	print("INCOME MESSAGE");
	var model_path=string.join("/",split("/",node.getPath())[0:3]);
	var model_freq= getprop(model_path,freqchannel);
	var msg = node.getValue();
	if (frequency != model_freq) {
		print(sprintf("my freq=%s, sender's freq=%s",frequency,model_freq));
		print(sprintf("Wrong frequency %s . Ignoring message: %s",model_freq,msg));
		return;
	}
	
	var msg2 = getprop(model_path,servermsgchannel2);
	if (msg2 != nil and msg2 != "") {
		print("Concatenating msg and msg2");
		msg= msg ~ msg2;
	}
	
	if (msg != nil and msg != '') {
		print(sprintf("ATCNG incoming message=%s",msg));
		setprop(atcchannel,msg);
	}
}

var set_comm = func(icao,controller) {
	airport=findAirportsByICAO(icao)[0];
	set_controller(controller);
	setprop(aptcode_node, airport.id);
	setprop(aptname_node, airport.name);
	print("ATCNG set_comm " ~ controller);
	screen.log.write(sprintf("Tunned to %s", controller),0.7, 1.0, 0.7);
					
};
var update = func {
	var frq = getprop("/instrumentation/comm/frequencies/selected-mhz");
	print("FREQ=",frq);
	if (frq != frequency) {
		airport=nil;
		if (atclistener) {
			print("Removing old listener");
			removelistener(atclistener);
			atclistener=nil;
		}	
		set_freq(frq);
		sendmessage('tunein',0);
		# settimer(atcng.check_model, 5);
	}
}

var messages = {
	roger:'{ack}{qnh}{tuneto}, {cs}',
	repeat:'{apt}, {cs}, say again',
	startup: '{apt}, {cs}, request startup clearance',
	readytaxi: '{apt}, {cs}, ready to taxi',
	holdingshort: '{apt}, {cs}, holding short {rwyof}',
	readytko: '{apt}, {cs}, ready for takeoff',
	leaving: '{apt}, {cs}, leaving airfield',
	transition: '{apt}, {cs} to transition your airspace',
	inbound: '{apt}, {cs} for inbound approach',
	crosswind: '{apt}, {cs}, crosswind for runway {rwy}',
	downwind: '{apt}, {cs}, downwind for runway {rwy}',
	base: '{apt}, {cs}, turning base for runway {rwy}',
	final: '{apt}, {cs}, final for runway {rwy}{tngo}',
	straight: '{apt}, {cs}, straight for runway {rwy}',
	clearrw: '{apt}, {cs}, clear {rwyof}',
	around: '{apt}, {cs}, going around',
	withyou: '{apt}, {cs}, with you at {alt} feet, heading {heading}',
	tunein: '',
	
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
	var sc = short_callsign(callsign);
	msg = string.replace(msg,'{cs}',sc);
	msg = string.replace(msg,'{rwy}',selected_runway);
	msg = string.replace(msg,'{rwyto}', "to runway " ~ selected_runway);
	msg = string.replace(msg,'{rwyof}', "of runway  " ~ selected_runway);
	msg = string.replace(msg,'{apt}',get_controller());
	msg = string.replace(msg,'{alt}',int(getprop("/position/altitude-ft")));
	msg = string.replace(msg,'{heading}',say_number(int(getprop("/orientation/heading-magnetic-deg"))));
	if (get_option('tngo')) {
		msg = string.replace(msg,'{tngo}', " for touch and go");
	} else {
		msg = string.replace(msg,'{tngo}', "");
	}		
	if (tag == "roger") {
		if(last_order['ord'] == 'taxito') {
			var ack = sprintf("taxi to %s",last_order['rwy']);
			if (last_order['short']) {
				ack ~= " and hold";
			}
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
			if (last_order['number'] > 1) {
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
	}
	return msg;
};

##### Dialog
var reset = func() {
	update();
	dialog.destroy();
};

var flow_next = func() {
	var next = getprop(atcng.root ~ "/next");
	if (next != "") {
		atcng.sendmessage(next);
	}
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
	} else if (lao == 'cleartk' or lao == "cleartngo") {
		next = "leaving";
	} else if (lao == 'join' or lao == 'cirrep') {
		var cirw = last_order['cirw'];
		next = cirw;
	} 
	var nn =atcng.root ~ "/next"; 
	print(sprintf("compute flow. node=%s, next=%s",nn,next));
	setprop(nn,next);
};
var get_dialog_column=func(tag){
	var legend= parse_message(tag);	
	var col ={ type: "button", legend: legend, code: tag, halign: "right", callback: "atcng.sendmessage" };
	return col;
}

var dialog_columns=func(){
	var cols = [];
	# print (sprintf("dialog_cols. view=%s, last_order=%s",viewnode,last_order));
	if (last_order != nil and last_order != "") {
		append(cols,get_dialog_column('roger'));
	}
	if (viewnode == 'flow') {
		var next = getprop(atcng.root ~ "/next");
		if (next) {
			append(cols,get_dialog_column(next));
	    }
	} else if (viewnode == 'depart') {

		append(cols,get_dialog_column('startup'));
		append(cols,get_dialog_column('readytaxi'));
		append(cols,get_dialog_column('holdingshort'));
		append(cols,get_dialog_column('readytko'));
		append(cols,get_dialog_column('leaving'));
	} else if (viewnode == 'arrival') {
		append(cols,get_dialog_column('inbound'));
    	append(cols,get_dialog_column('downwind'));
    	append(cols,get_dialog_column('crosswind'));
    	append(cols,get_dialog_column('base'));
    	append(cols,get_dialog_column('final'));
    	append(cols,get_dialog_column('straight'));
    	append(cols,get_dialog_column('clearrw'));
    	append(cols,get_dialog_column('around'));    	
    } else if (viewnode == 'approach') {
    	append(cols,get_dialog_column('transition'));
    	append(cols,get_dialog_column('withyou'));
    } else if (viewnode == 'options') {
		append(cols,{ type: "checkbox", label: "Remain in the pattern", code: "remain", halign: "left", callback: "atcng.set_option", property: atcng.root ~ "/options/remain" });
		append(cols,{ type: "checkbox", label: "Touch and go", code: "tngo", halign: "left", callback: "atcng.set_option", property: atcng.root ~ "/options/tngo" });
		
    }
     return cols;
}

var set_option = func(option=nil) {
	var prop = atcng.root ~ "/options/" ~ option;
	setprop(prop,!getprop(prop));
	#print(sprintf("Updating %s to %s",prop,s));
};

var get_option = func(option=nil) {
	var prop = atcng.root ~ "/options/" ~ option;
	return getprop(prop);
};

var setview = func(view = nil) {
	print("setview" ~ view);
	viewnode = view;
	me.dialog.destroy();
	me.dialog.create();
}
var dialog = {
#################################################################
    init : func (x = nil, y = nil) {
        me.x = x;
        me.y = y;
        me.bg = [0, 0, 0, 0.3];    # background color
        me.fg = [[1.0, 1.0, 1.0, 1.0]];
        #
        # "private"
        me.title = "ATC NG";
        me.basenode = props.globals.getNode("/sim/atcng/dialog");
        me.dialog = nil;
        me.namenode = props.Node.new({"dialog-name" : me.title });
        me.listeners = [];
    },
#################################################################
    create : func {
        if (me.dialog != nil)
            me.close();

        me.dialog = gui.Widget.new();
        me.dialog.set("name", me.title);
        if (me.x != nil)
            me.dialog.set("x", me.x);
        if (me.y != nil)
            me.dialog.set("y", me.y);

        me.dialog.set("layout", "vbox");
        me.dialog.set("default-padding", 0);
        var titlebar = me.dialog.addChild("group");
        titlebar.set("layout", "hbox");
        titlebar.addChild("empty").set("stretch", 1);
        titlebar.addChild("text").set("label", "ATC Comm");
        titlebar.addChild("empty").set("stretch", 1);
        
		var w = titlebar.addChild("button");
		w.set("pref-width", 16);
        w.set("pref-height", 16);
        w.set("legend", "");
        w.set("default", 0);
        w.setBinding("nasal", "atcng.dialog.destroy(); ");
        w.setBinding("dialog-close");

        var options = me.dialog.addChild("group");
		options.set("layout", "hbox");
        options.set("halign", "center");
        options.set("default-padding", 5);
		b1 = options.addChild("button");
		b1.node.setValues({ type: "button", legend: "Reset", code: "reset", halign: "right", callback: "atcng.reset" });
        b1.setBinding("nasal", 'atcng.reset()');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Flow", code: "flow", halign: "right", callback: "atcng.setview" });
        b2.setBinding("nasal", 'atcng.setview("flow")');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Depart", code: "depart", halign: "right", callback: "atcng.setview" });
        b2.setBinding("nasal", 'atcng.setview("depart")');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Arrival", code: "arrive", halign: "right", callback: "atcng.setview" });
        b2.setBinding("nasal", 'atcng.setview("arrival")');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Approach", code: "approach", halign: "right", callback: "atcng.setview" });
        b2.setBinding("nasal", 'atcng.setview("approach")');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Options", code: "options", halign: "right", callback: "atcng.setview" });
        b2.setBinding("nasal", 'atcng.setview("options")');		
        
		me.dialog.addChild("hrule");
		var content = me.dialog.addChild("group");
        content.set("layout", "vbox");
        content.set("halign", "center");
        content.set("default-padding", 5);
		me.columns = atcng.dialog_columns();
		foreach (var column; me.columns) {
			w = content.addChild(column.type);
			w.node.setValues(column);
            w.setBinding("nasal", column.callback ~ "(\"" ~ column.code ~ "\");");
		}
		fgcommand("dialog-new", me.dialog.prop());
        fgcommand("dialog-show", me.namenode);
	},
#################################################################
    close : func {
        fgcommand("dialog-close", me.namenode);
    },
#################################################################
    destroy : func {
        CONFIG_DLG = 0;
        me.close();
        foreach(var l; me.listeners)
            removelistener(l);
        delete(gui.dialog, "\"" ~ me.title ~ "\"");
    },
    
#################################################################
    show : func {
    	if (atcng.airport == nil) {
    		print("Not tunned to an ATC.");
    		return;
    	}
        if (!CONFIG_DLG) {
            CONFIG_DLG = 1;
            me.init();
            me.create();
        }

	}
};
var multiupdate=func(a=nil,b=nil,c=nil) {
	print("MULTIUPDATE");
	debug.dump(a);
	debug.dump(b);
	debug.dump(c);
}
#setlistener("/sim/signals/multiplayer-updated", multiupdate);
# setlistener("/ai/models/model-added",func settimer(atcng.check_model,1));
#check_models();
setlistener("/ai/models/model-added",atcng.model_added,1,1);
setlistener("/ai/models/model-removed",atcng.model_removed,0,1);
setlistener("/instrumentation/comm/frequencies/selected-mhz",atcng.update,1,0);
print("ATCNG started");
