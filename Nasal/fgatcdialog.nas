var CONFIG_DLG = 0;
var viewnode="depart";

##### Dialog
var reset = func() {
	update();
	dialog.destroy();
};

var flow_next = func() {
	var next = getprop(fgatc.root ~ "/next");
	if (next != nil and next != "") {
		fgatc.sendmessage(next);
	}
}

var get_dialog_column=func(tag){
	var legend= fgatc.parse_message(tag);	
	var col ={ type: "button", legend: legend, code: tag, halign: "right", callback: "fgatc.sendmessage" };
	return col;
}

var dialog_columns=func(){
	var cols = [];
	if (fgatc.last_order != nil and fgatc.last_order != "") {
		append(cols,get_dialog_column('roger'));
	}
	if (viewnode == 'flow') {
		var next = getprop(fgatc.root ~ "/next");
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
		append(cols,{ type: "checkbox", label: "Remain in the pattern", code: "remain", halign: "left", callback: "fgatcdialog.set_option", property: fgatc.root ~ "/options/remain" });
		append(cols,{ type: "checkbox", label: "Touch and go", code: "tngo", halign: "left", callback: "fgatcdialog.set_option", property: fgatc.root ~ "/options/tngo" });
		
    }
     return cols;
}

var set_option = func(option=nil) {
	var prop = fgatc.root ~ "/options/" ~ option;
	setprop(prop,!getprop(prop));
	#print(sprintf("Updating %s to %s",prop,s));
};

var get_option = func(option=nil) {
	var prop = fgatc.root ~ "/options/" ~ option;
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
        me.basenode = props.globals.getNode("/sim/fgatc/dialog");
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
        w.setBinding("nasal", "fgatcdialog.dialog.destroy(); ");
        w.setBinding("dialog-close");

        var options = me.dialog.addChild("group");
		options.set("layout", "hbox");
        options.set("halign", "center");
        options.set("default-padding", 5);
		b1 = options.addChild("button");
		b1.node.setValues({ type: "button", legend: "Reset", code: "reset", halign: "right", callback: "fgatcdialog.reset" });
        b1.setBinding("nasal", 'fgatcdialog.reset()');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Flow", code: "flow", halign: "right", callback: "fgatcdialog.setview" });
        b2.setBinding("nasal", 'fgatcdialog.setview("flow")');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Depart", code: "depart", halign: "right", callback: "fgatcdialog.setview" });
        b2.setBinding("nasal", 'fgatcdialog.setview("depart")');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Arrival", code: "arrive", halign: "right", callback: "fgatcdialog.setview" });
        b2.setBinding("nasal", 'fgatcdialog.setview("arrival")');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Approach", code: "approach", halign: "right", callback: "fgatcdialog.setview" });
        b2.setBinding("nasal", 'fgatcdialog.setview("approach")');		
        b2 = options.addChild("button");
		b2.node.setValues({ type: "button", legend: "Options", code: "options", halign: "right", callback: "fgatcdialog.setview" });
        b2.setBinding("nasal", 'fgatcdialog.setview("options")');		
        
		me.dialog.addChild("hrule");
		var content = me.dialog.addChild("group");
        content.set("layout", "vbox");
        content.set("halign", "center");
        content.set("default-padding", 5);
		me.columns = fgatcdialog.dialog_columns();
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
    	if (fgatc.airport == nil) {
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
