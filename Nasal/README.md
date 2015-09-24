#FG Nasal Script

Nasal script for AI ATC communication.

* Detects COMM frequency changes and tune in to AI ATC in the server. Currently, it only listens for the frequency in COMM1.

* Sends messages to the server on the currently tunned frequency.
 
* Receives ATC orders and MP's messages and places them in the appropriate chat channel. **Note that it only process messages that are sent to the currently tunned frequency!**. ATC messages goes into `/sim/messages/atc` and MP messages into `/sim/messages/ai-plane`

* Includes a dialog for sending messages and helper functions for use in other Nasal scripts.

* Has a [message flow](#message-flow) system that detect the next message to send. 


## Instalation

Place the `atcng.nas` file into FlightGear's root directory or in your local .fgfs/ directory, under `Nasal/`.


## Helper functions

| Helper | Use |
| ------- | ------ |
| atcng.dialog.show() | Opens the messages dialog | 
| atcng.readback()| Sends a readback of the last message received |
| atcng.flow_next()|Sends a message with the next step of the communication flow |

You can bind this helpers to a keystroke or joystick button for an easy communication flow.


## Key Binding

### Keyboard

Replaces the key `'` that used to open an ATC dialog (not used anymore in FG) to show the new ATC Messages dialog. Put the code in a xml file (ie: keys.xml) and start FG with option `--config=<path where file resides>/keys.xml` .
You can put this option into .fgfsrc as well.

Alternatively, you can edit the `keyboard.xml` file of the FG instalation and replace the key definition there, but it will be erased if you update your FG installation.
 
```xml
<?xml version="1.0"?>
<PropertyList>
<input><keyboard>
<key n="39">
  <name>'</name>
  <desc>Display a dialog for sending messages to the tuned-in ATC service (if any)</desc>
  <binding>
    <command>nasal</command>
    <script>atcng.dialog.show()</script>
  </binding>
</key>
```


### Joystick

Having `readback()` and `flow_next()` assigned to joystic buttons, you can make a complete approach communication without opening the messages dialog (except for the first message, of course) . See [Message flow](#message-flow)

* Open the messages dialog and send a 'for inbound approach' message. Close it.
* ATC instructs you to _join_ at a specific circuit leg (ie: crosswind, downwind, straight, etc.)
* Push the _readback_ button. The scripts sends a readback.
* Once you reach the designated leg, push the _flow next_ button. The scripts sends a "reached circuit leg" message (ie: "downwind for 23")
* The ATC will instruct you to report on the next leg
* Push the _readback_ button. The scripts sends a readback.
* Once you reach the next leg, push the _flow next_ button. The scripts sends a "reached circuit leg" message (ie: "turning base for 23")
* and so on...

```xml
<button n="8">
  <desc>Sends a Readback of last ATC message</desc>
  <binding>
     <command>nasal</command>
     <script>atcng.readback();</script>
  </binding>
</button>

<button n="9">
  <desc>Sends next message according to ATC Flow</desc>
  <binding>
    <command>nasal</command>
    <script>atcng.flow_next();</script>
  </binding>
</button>
```

## Message Flow


The script tries to detect a "normal message flow" 

If you are in a circuit, and the ATC instructs you to _report on downwind_, the flow system assumes the next message you'll send is the report that you arrived to the downwind. If you are taking off, the next message will be a "leaving airfield", et cetera.

There's a special tab in the messages dialog (called _Flow_ ) that shows the suggested message to send next. Also, there is a helper function that sends that message to the server which you can bind to a key or joystick button (see [Key Binding](#key-binding) )