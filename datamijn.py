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
    
    def type(self, token):
        name = token[0]
        if name in CONSTRUCT_ALIASES:
            return CONSTRUCT_ALIASES[name]
        else:
            return LazyBound(lambda: self.structs_by_name[name])
    
    def typedef(self, tree):
        return Struct(*tree)
    
    def field(self, f):
        name = f[0].value
        type = f[1]
        
        field = name / type
        field._name = name
        
        return field
        
# https://github.com/yaml/pyyaml/issues/110
# https://github.com/yaml/pyyaml/pull/143        

grammar = open("grammar.g").read()

def container_representer(dumper, data):
    del data['_io']
    return dumper.represent_data(dict(data))
    #return dumper.serialize(dict(data))
yaml.add_representer(Container, container_representer)

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
        structs_by_name[struct._name] = struct
    
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
