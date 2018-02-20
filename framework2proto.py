#!/usr/local/bin/python3

import re, subprocess, sys

if len(sys.argv) < 2:
    print('''
This utility generates a protobuf file from an Objective C framework. It was developed against 
CloudKit/CloudKitDaemon, but may work with other libraries that are built the same way.
''')
    print("Usage:\n\t",sys.argv[0],"MachOBinary\n")
    exit(-1)

fn = sys.argv[1]
lines = subprocess.check_output(['objdump', '-macho', '-objc-meta-data', '-disassemble', fn]).splitlines()
# lines = open('CloudKitDaemon.s','rb').read().splitlines()
it = iter(lines)
line = next(it)

DEBUG=False

r_field = r'.*\tmovq\t_OBJC_IVAR_\$_([A-Za-z]+)\._([A-Za-z]+)\('

types = {
    '_PBDataWriterWriteInt': 'int32',
    '_PBDataWriterWriteSint': 'sint32',
    '_PBDataWriterWriteSfixed': 'sfixed32',
    '_PBDataWriterWriteFixed': 'fixed32',
    '_PBDataWriterWriteStringField': 'string',
    '_PBDataWriterWriteSubmessage': '-',
    '_PBDataWriterWriteDataField': 'bytes',
    '_PBDataWriterWriteBOOLField': 'bool',
    '_PBDataWriterWriteUint': 'uint32',
    '_PBDataWriterWriteFloatField': 'float',
    '_PBDataWriterWriteDoubleField': 'double',
}

def dprint(*args):
    if DEBUG:
        print(*args)

schema = {}
objc = {}
arrays = {}

try:
    while True:
        m = re.match(b'^-\[([A-z]+) writeTo:\]:$',line)
        if m:
            typ = m.group(1).decode('ascii')
            current = schema[typ] = {}
            dprint(typ)
            field,key = None,None
            optional = "optional "
            while True:
                line = line.decode('utf8')
                m = re.match(r_field,line)
                if m:
                    a,field = m.groups()
                    assert a == typ
                    key = None
                    optional = "optional "
                elif re.match(r'.*testq\t%rsi, %rsi',line):
                    optional = "optional "
                # this is %esi for the float/double case
                elif re.match(r'.*\tmovl\t\$(\d+), %(edx|esi)',line):
                    m = re.match(r'.*\tmovl\t\$(\d+), %(edx|esi)',line)
                    key = m.group(1)
                # this is jmp when there is a tail-call optimization
                elif re.match(r'.*(callq|jmp)',line):
                    m = re.match(r'.* ## symbol stub for: (_PBDataWriter[A-Za-z]+)',line)
                    if m:
                        assert key not in current
                        # This is subtle, but for repeated ints and doubles (from a c array)
                        # there is a incq %rbx on the next line. This doesn't catch all NSMutableArray cases.
                        line = next(it).strip()
                        if b"incq\t%rbx" in line:
                            optional = "repeated "
                        current[key] = (field,types[m.group(1)],optional)
                        dprint('XXX', typ,types[m.group(1)],field,'=',key,optional)
                        field,key = None,None
                        continue # we peeked at the next line so we skip back to the top
                    elif field:
                        dprint("STRAY",line)
                        # assert False
                line = next(it).strip()
                if line.startswith(b'-'):
                    break	
                #dprint(line)
        elif re.match(b' *isa .* _OBJC_METACLASS_\$_([A-Za-z]+)',line):
            m = re.match(b' *isa .* _OBJC_METACLASS_\$_([A-Za-z]+)',line)
            typ = m.group(1).decode('utf8')
            current = objc[typ] = {}
            dprint('ZZZ',typ)
            props = False
            name = None
            while True:
                line = next(it)
                parts = line.strip().decode('utf8').split()
                if parts[0].startswith('0') or parts[0] == 'Meta':
                    break
                # dprint(parts)
                if parts[0] == 'name':
                    name = parts[2]
                if parts[0] == 'attributes':
                    m = re.match(r'T@"(.*?)"',parts[2])
                    if m:
                        dprint(typ,name,m.group(1))
                        current[name] = m.group(1)
        elif re.match(b'_([A-Za-z]+)ReadFrom:',line):
            # experimental - try to determine NSMutableArray types
            typ = re.match(b'_([A-Za-z]+)ReadFrom:',line).group(1).decode('utf8')
            refs = {}
            clazz = None
            while True:
                line = next(it).rstrip()
                if not line.startswith(b" "):
                    break
                line = line.decode('utf8')
                parts = line.split('\t')
                m = re.match(r'.*%rax ## Objc selector ref: add([A-Za-z]+):',line)
                if m:
                    key = m.group(1)
                    key = key[0].lower()+key[1:]
                    dprint('*',key)
                    line = next(it).rstrip().decode('utf8')
                    parts = line.split('\t')
                    if parts[2] == 'movq':
                        dest = parts[3].split(', ')[1]
                        dprint(typ,key,dest)
                        refs[dest] = key

                m = re.match(r'.* ## Objc class ref: (_OBJC_CLASS_\$_)?([A-Za-z]+)',line)
                if m:
                    dprint('clazz',m.group(2))
                    clazz = m.group(2)
                if parts[0].startswith('j'):
                    dprint('clear',parts)
                    clazz = None # naive basic block detection.
                if parts[2] == 'movq':
                    a,b = parts[3].split(', ')
                    if a in refs:
                        dprint(line)
                        # assert clazz != None
                        arrays[(typ,refs[a])] = clazz
                        # some of these drop the 's'
                        if not refs[a].endswith('s'):
                            arrays[(typ,refs[a]+'s')] = clazz
                        dprint('ADD',typ,refs[a],clazz)
        else:
            line = next(it).rstrip()
except StopIteration:
    pass

from pprint import pprint
for k,v in sorted(schema.items()):
    print(f"message {k} {{")
    for k2,v2 in v.items():
        f,t,o = v2
        if t == '-':
            oo = objc[k]
            t = oo.get(f,t)
        if t.startswith('NS'):
            o = 'repeated '
            t = arrays.get((k,f),t)
        print(f'    {o}{t} {f} = {k2};')
    print("}\n")
dprint(arrays)
