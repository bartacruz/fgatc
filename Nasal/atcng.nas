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
var pilotchannel="sim/multiplay/generic/string[17]";
var serverchannel="sim/multiplay/generic/string[18]";
var servermsgchannel="sim/multiplay/generic/string[16]";
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

var short_callsign=func(callsign){
	var base='a';
	var cs = string.lc(callsign);
    return sprintf("%s %s %s", LETTERS[cs[0] - base[0]],
                             LETTERS[cs[1] - base[0]],
                             LETTERS[cs[2] - base[0]]
                             );
};
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
}

var sendmessage = func(message="",dlg=1){
	var msg = parse_message(message);
	var request = sprintf("req=%s;freq=%.2f;mid=%s",message,frequency,int(rand()*10000));
	if (message=='roger' and last_order != nil){
		request = sprintf("%s;laor=%s",request,last_order['ord']);
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

var check_model = func(node=nil) {
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
			var sc = atcnode.getNode(serverchannel).getPath();
			print("ATCNG listening in " ~ sc);
			atclistener = setlistener(sc, readmessage, 1, 0);
   		} else {
			print("checking ai-plane " ~ callsign);
			if (!contains(_ml,callsign)){
				print("ATCNG adding ai-plane " ~ callsign);
				var nnode=n;
				var aic=nnode.getNode(servermsgchannel).getPath();
				_ml[callsign]=setlistener(aic,readaimessage,0,0);	
			}
		}
	}
}



var readaimessage= func(node=nil){
	var msg = node.getValue();
	if (msg != nil){
		setprop(chataichannel,msg);
	}
}
var readmessage = func(node=nil) {
	var order = node.getValue();
	if (order == nil or order == '') {
		last_order = nil;
		last_order_string=nil;
		return;
	}
	print("readmessage: " ~ order);
	last_order_string=order;
	var aux=sprintf("return %s",order);
	var ff = call(compile,[aux],var err=[]);
	if (!size(err)) {
		var laor = ff();
		if (laor['to'] != callsign){
			print(sprintf("ignoring order for %s",laor['ord']));
		} else {
			last_order = laor;
			if (last_order['rwy']){
				selected_runway=last_order['rwy'];
			}
			if (last_order['ord']=='tuneok') {
				set_comm(last_order['apt'],last_order['atc']);
			}
			print(sprintf("ATCNG incoming order=%s",order));
		}
	}
	var msg = atcnode.getNode(servermsgchannel).getValue();
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
		settimer(atcng.check_model, 5);
	}
}

var messages = {
	roger:'{ack}{qnh}, {cs}',
	repeat:'{apt}, {cs}, say again',
	startup: '{apt}, {cs}, request startup clearance',
	readytaxi: '{apt}, {cs}, ready to taxi',
	holdingshort: '{apt}, {cs}, holding short {rwyof}',
	readytko: '{apt}, {cs}, ready for takeoff',
	transition: '{apt}, {cs} to transition your airspace',
	inbound: '{apt}, {cs} for inbound approach',
	crosswind: '{apt}, {cs}, crosswind for runway {rwy}',
	downwind: '{apt}, {cs}, downwind for runway {rwy}',
	base: '{apt}, {cs}, turning base for runway {rwy}',
	final: '{apt}, {cs}, turning final for runway {rwy}',
	straight: '{apt}, {cs}, straight for runway {rwy}',
	clearrw: '{apt}, {cs}, clear {rwyof}',
	around: '{apt}, {cs}, going around',
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
		} else {
			msg = string.replace(msg,'{ack}','Roger');
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
}
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
		if (last_order == nil or last_order == "")  {
			append(cols,get_dialog_column('startup'));
			append(cols,get_dialog_column('readytaxi'));
		} else {
		 	if (last_order['ord'] == 'startup') {
		 		append(cols,get_dialog_column('readytaxi'));
			} else if (last_order['ord'] == 'taxito' or last_order['ord'] == "lineup" or last_order['ord'] == "holdshort") {
		 		append(cols,get_dialog_column('holdingshort'));
		 		append(cols,get_dialog_column('readytko'));
	     	}
	    }
	} else if (viewnode == 'depart') {

		append(cols,get_dialog_column('startup'));
		append(cols,get_dialog_column('readytaxi'));
		 append(cols,get_dialog_column('holdingshort'));
		 append(cols,get_dialog_column('readytko'));
	} else if (viewnode == 'arrival') {
		append(cols,get_dialog_column('inbound'));
    	append(cols,get_dialog_column('transition'));
    	append(cols,get_dialog_column('downwind'));
    	append(cols,get_dialog_column('crosswind'));
    	append(cols,get_dialog_column('base'));
    	append(cols,get_dialog_column('final'));
    	append(cols,get_dialog_column('straight'));
    	append(cols,get_dialog_column('clearrw'));    	
    }
     return cols;
}

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
        
		me.dialog.addChild("hrule");
		var content = me.dialog.addChild("group");
        content.set("layout", "vbox");
        content.set("halign", "center");
        content.set("default-padding", 5);
		me.columns = atcng.dialog_columns();
		foreach (var column; me.columns) {
			w = content.addChild("button");
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

setlistener("/ai/models/model-added",func settimer(atcng.check_model,1));
setlistener("/instrumentation/comm/frequencies/selected-mhz",atcng.update,1,0);
print("ATCNG started");
