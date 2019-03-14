'''
Created on 23 de abr. de 2017

@author: julio
'''
import re
def parse_line(line):
    ll=' { 100, "surface-positions/left-aileron-pos-norm",  simgear::props::FLOAT, TT_SHORT_FLOAT_NORM,  V1_1_PROP_ID, NULL },'
    rr="100: {'node': 'surface-positions/left-aileron-pos-norm', 'type':'FLOAT'},"
    pattern = re.compile(r' { (\d*),\s*"(.*)",\s*simgear::props::(\w*),')
    match = pattern.match(line)
    if match:
        print "%s: {'node': '%s', 'type':'%s'}" % (match.group(1),match.group(2),match.group(3))
        