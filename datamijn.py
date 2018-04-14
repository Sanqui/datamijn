#!/usr/bin/python3

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

class TreeToStruct(Transformer):
    def __init__(self, structs_by_name):
        self.structs_by_name = structs_by_name
    
    def eval(self, token):
        return eval(token[0])
    
    def ctx_value(self, token):
        def ctx_value(ref):
            return lambda this: this[ref]
        
        return ctx_value(token[0].value)
    
    def type(self, token):
        name = token[0]
        if name in CONSTRUCT_ALIASES:
            return CONSTRUCT_ALIASES[name]
        else:
            return LazyBound(lambda: self.structs_by_name[name])
    
    def enum(self, tree):
        return dict(tree)
    
    def enum_field(self, tree):
        return (tree[0].value, tree[1])
    
    def typedef(self, tree):
        return Struct(*tree)
    
    def enum_type(self, tree):
        return Enum(tree[0], **tree[1])
    
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
            type_ = type_[count]
        
        if pointer != None:
            field = name / Pointer(pointer, type_)
        else:
            field = name / type_
        
        return field
    
    def field_array(self, f):
        name = f[0].value
        count = eval(f[1].value)
        type = f[2]
        
        field = name / type[count]
        
        return field
        
grammar = open("grammar.g").read()

def container_representer(dumper, data):
    del data['_io']
    return dumper.represent_data(dict(data))
yaml.add_representer(Container, container_representer)
def list_container_representer(dumper, data):
    return dumper.represent_data(list(data))
yaml.add_representer(ListContainer, list_container_representer)
# TODO improve
def enum_integer_string_representer(dumper, data):
    return dumper.represent_data(str(data))
yaml.add_representer(EnumIntegerString, enum_integer_string_representer)

def parse(definition, data):
    # XXX the parser should be done outside - but
    # we need to pass structs_by_name as a part
    # of a hack
    structs_by_name = {}
    parser = Lark(grammar, parser='lalr', transformer=TreeToStruct(structs_by_name))
    if type(definition) != str:
        definition = definition.read()
    
    definition += "\n"
    
    tree = parser.parse(definition)

    if type(tree) == Tree:
        structs = tree.children
    else:
        structs = [tree]

    for struct in structs:
        structs_by_name[struct.name] = struct
    
    start = None
    if "_start" in structs_by_name:
        start = structs_by_name["_start"]
    else:
        start = Struct(*structs)
    
    if type(data) != bytes:
        result = start.parse_stream(data)
    else:
        result = start.parse(data)

    return result

if __name__ == "__main__":
    from sys import argv

    STRUCTF = argv[1]
    FILEF = argv[2]
    
    result = parse(open(STRUCTF), open(FILEF, "rb"))
    print(yaml.dump(result, sort_keys=False))
