#!/usr/bin/python3
import sys
import os.path

from lark import Lark, Transformer
from lark.tree import Tree
from construct import *
from construct.lib.containers import Container
import yaml

CONSTRUCT_ALIASES = {
    "u8": Int8ul,
    "u16": Int16ul,
    "u32": Int32ul
}

class AttrDict(dict):
    def __getattr__(self, attr):
        return self[attr]

class Token(str):
    pass

class Char(str):
    pass

class EnumElement():
    def __init__(self, intvalue, value):
        self.intvalue = intvalue
        self.value = value
    
    def __repr__(self):
        return f"EnumElement({self.intvalue}, {repr(self.value)})"
    
    def __eq__(self, other):
        #if isinstance(other, EnumElement):
        #    return self.intvalue == other.intvalue and self.value == other.value
        #else:
            return self.value == other

# XXX killing writing here
class TypedEnum(Enum):
    def __init__(self, subcon, mapping):
        super(Enum, self).__init__(subcon)
        #for enum in merge:
        #    for enumentry in enum:
        #        mapping[enumentry.name] = enumentry.value
        self.charmapping = {k:v for k,v in mapping.items() if type(k)==Char}
        self.tokenmapping = {k:v for k,v in mapping.items() if type(k)==Token}
        self.decmapping = {v:EnumElement(v,k) for k,v in mapping.items()}
        self.ksymapping = {v:k for k,v in mapping.items()}
    
    def __getattr__(self, name):
        if name in self.tokenmapping:
            return self.decmapping[self.tokenmapping[name]]
        raise AttributeError
    
    def __getitem__(self, name):
        if name in self.charmapping:
            return self.decmapping[self.charmapping[name]]
        raise KeyError

class JoiningArray(Array):
    def _parse(self, stream, context, path):
        count = self.count
        if callable(count):
            count = count(context)
        if not 0 <= count:
            raise RangeError("invalid count %s" % (count,))
        obj = ListContainer()
        last_element = None
        for i in range(count):
            context._index = i
            e = self.subcon._parsereport(stream, context, path)
            if type(e) == EnumElement:
                #print(type(e), e.value, e.intvalue)
                e = e.value
            if type(last_element) in (Char, str) and type(e) == Char:
                last_element += e
            else:
                if last_element != None:
                    obj.append(last_element)
                last_element = e
        obj.append(last_element)
        return obj

class TreeToStruct(Transformer):
    def __init__(self, structs_by_name, path):
        self.structs_by_name = structs_by_name
        self.path = path
        self.enum_last = -1
        self.embed_counter = 0
    
    def eval(self, token):
        return eval(token[0])
    
    def ctx_value(self, token):
        def ctx_value(ref):
            return lambda this: this[ref]
        
        return ctx_value(token[0].value)
    
    def import_(self, token):
        path = self.path + "/" + token[0] + ".dm"
        self.structs_by_name.update(parse_definition(open(path))[1])
    
    def type(self, token):
        name = token[0]
        if name in CONSTRUCT_ALIASES:
            return CONSTRUCT_ALIASES[name]
        elif name in "u1 u2 u3 u4 u5 u6 u7".split():
            return BitsInteger(int(name[1]))
        else:
            return LazyBound(lambda: self.structs_by_name[name])
    
    def string(self, token):
        return Char(token[0][1:-1])
    
    def name(self, token):
        return token[0]
    
    def enum_name(self, token):
        return Token(token[0])
    
    def enum_char(self, token):
        return Char(token[0])
    
    def enum(self, tree):
        self.enum_last = -1
        return dict(tree)
    
    def enum_field(self, tree):
        if len(tree) == 1:
            val = self.enum_last + 1
        else:
            val = tree[1]
        self.enum_last = val
        return (tree[0], val)
    
    def typedef(self, tree):
        struct = []
        bitstruct = []
        for field in tree:
            f = field
            while hasattr(f, 'subcon'):
                f = f.subcon
            if isinstance(f, BitsInteger):
                bitstruct.append(field)
            else:
                struct.append(field)
        if struct and bitstruct:
            raise ValueError("Cannot mix bit and byte fields within struct")
        if struct:
            return Struct(*struct)
        elif bitstruct:
            return BitsSwapped(BitStruct(*bitstruct))
        else:
            return Struct()
    
    def enum_type(self, tree):
        return TypedEnum(tree[0], tree[1])
    
    def field(self, f):
        name = f[0].value
        params = f[1]
        count = None
        pointer = None
        for param in params.children:
            if param.data == "count":
                count = param.children[0]
            elif param.data == "pointer":
                pointer = param.children[0]
            else:
                raise ValueError(f"Unknown param type: {param.data}")
        type_ = f[2]
        if count != None:
            type_ = JoiningArray(count, type_)
        
        if pointer != None:
            field = name / Pointer(pointer, type_)
        else:
            field = name / type_
        
        return field
        
grammar = open(sys.path[0]+"/grammar.g").read()

def container_representer(dumper, data):
    del data['_io']
    del data['_structs']
    return dumper.represent_data(dict(data))
yaml.add_representer(Container, container_representer)
def list_container_representer(dumper, data):
    return dumper.represent_data(list(data))
yaml.add_representer(ListContainer, list_container_representer)
# TODO improve
def enum_element_representer(dumper, data):
    return dumper.represent_data(str(data.value))
yaml.add_representer(EnumElement, enum_element_representer)
parser = Lark(grammar, parser='lalr')

def parse_definition(definition):
    path = ""
    if type(definition) != str:
        path = os.path.dirname(definition.name)
        definition = definition.read()
    
    definition += "\n"
    
    structs_by_name = {}
    transformer = TreeToStruct(structs_by_name, path)
    tree = transformer.transform(parser.parse(definition))

    if type(tree) == Tree:
        structs = tree.children
    else:
        structs = [tree]
    
    for struct in structs:
        if struct:
            structs_by_name[struct.name] = struct
    
    return structs, structs_by_name

def parse(definition, data):
    structs, structs_by_name = parse_definition(definition)
    
    start = None
    if "_start" in structs_by_name:
        start = structs_by_name["_start"]
    else:
        start = Struct(*structs)
    
    if type(data) != bytes:
        result = start.parse_stream(data)
    else:
        result = start.parse(data)
    
    result._structs = AttrDict(structs_by_name)

    return result

if __name__ == "__main__":
    from sys import argv

    STRUCTF = argv[1]
    FILEF = argv[2]
    
    result = parse(open(STRUCTF), open(FILEF, "rb"))
    #print(result)
    print(yaml.dump(result, sort_keys=False))
