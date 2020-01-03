#!/usr/bin/python3

# TODO study
# https://docs.python.org/3/library/collections.abc.html#module-collections.abc
# https://docs.python.org/3/library/numbers.html#module-numbers

import sys
import os.path
import math
import operator
from io import BytesIO, BufferedIOBase
from pprint import pprint

from lark import Lark, Transformer
from lark.tree import Tree
import oyaml as yaml
import png

    
from datamijn.dmtypes import *
from datamijn.gfx import Tile, Tile1BPP, NESTile, GBTile, Tileset, Image, \
    Palette, RGBColor
from datamijn.utils import parse_symfile

primitive_types = {
    "B1": B1,
    "U8": U8,
    "U16": U16,
    "U32": U32,
    "Byte": Byte,
    "Short": Short,
    "Word": Word,
    # TODO long
    "I": Index,
    "Pos": Position,
    "RightSize": RightSize,
    "Tile1BPP": Tile1BPP,
    "NESTile": NESTile,
    "GBTile": GBTile,
    "Terminator": Terminator,
    "Null": Null,
    "RGBColor": RGBColor,
}

for i in range(2, 33):
    primitive_types[f"B{i}"] = make_bit_type(i)

class TreeToStruct(Transformer):
    def __init__(self, path):
        self.path = path
        self.match_last = -1
    
    def string(self, token):
        return token[0][1:-1]
    
    def num(self, tree):
        return eval(tree[0]) # this is safe, trust me
    
    def match_key_int(self, tree):
        return DatamijnInt.__new__(DatamijnInt, tree[0])
    
    def match_key_string(self, tree):
        return str(tree[0])
    
    def match_key_default(self, tree):
        return DefaultKey()
    
    def match_key_default_name(self, tree):
        return DefaultKey(tree[0])
    
    def match_key_range(self, tree):
        return KeyRange(*tree)
    
    def match_field(self, tree):
        if len(tree) == 1:
            key = self.match_last + 1
            type_ = tree[0]
        else:
            key = tree[0]
            type_ = tree[1]
        self.match_last = key
        return (key, type_)
    
    def match(self, tree):
        self.match_last = -1
        return dict(tree)
    
    def struct(self, tree):
        fields = []
        return_ = None
        
        if len(tree) and isinstance(tree[-1], type) and issubclass(tree[-1], Return):
            return_ = tree.pop()
        
        for field in tree:
            if isinstance(field, type) and issubclass(field, Return):
                raise SyntaxError("Return must be last in struct") # TODO nicer error
            if isinstance(field, type) and issubclass(field, DatamijnObject):
                fields.append((None, field))
            elif isinstance(field, Field):
                fields.append((None, field))
            elif type(field) == tuple and len(field) == 2:
                fields.append(field)
            else:
                print(tree)
                raise RuntimeError(f"Internal error: unknown struct field {field}")
        
        return Struct.make(None, _fields=fields, _return=return_)
    
    #
    # expr
    #
    
    def expr(self, tree):
        return tree[0]
    
    def expr_pipe(self, tree):
        left_type, right_type = tree
        return Pipe.make(None,
            left=left_type, right=right_type)
    
    def expr_inherit(self, tree):
        left_type, name = tree
        
        # TODO this should be handled in the resolve pass so we can have
        # nicer error messages?
        
        if name in primitive_types:
            right_type = primitive_types[name]
        else:
            raise SyntaxError(f"""Can only inherit from primitive types
Attempted to inherit {left_type.__name__} from {name}""")
        
        return Inheritance.make(None,
            left=left_type, right=right_type)
    
    def expr_attr(self, tree):
        left, name = tree
        return ExprAttr.make(None,
            left=left, _name=name)
    
    def expr_index(self, tree):
        left, index = tree
        return ExprIndex.make(f"({left.__name__})[{index.__name__}]",
            left=left, index=index)
    
    def expr_infix(self, tree):
        OPERATIONS = {
            "+": operator.add,
            "-": operator.sub,
            "*": operator.mul,
            "/": operator.floordiv,
            "%": operator.mod,
            "==": operator.eq,
            "!=": operator.ne,
        }
        left, sign, right = tree
        return ExprOp.make(f"({left.__name__}{sign}{right.__name__})",
            left=left, right=right, _op=OPERATIONS[sign])
    
    def expr_bracket(self, tree):
        return tree[0]
    
    def expr_foreign_key(self, tree):
        type_, field_name = tree
        return ForeignKey.make(f"{type_.__name__}ForeignKey",
            type=type_, _field_name=field_name)
    
    def expr_yield(self, tree):
        type = tree[0]
        return Yield.make("Yield", _type=type)
    
    def expr_match(self, tree):
        type = tree[0]
        match = tree[1]
        return MatchType.make(f"{type.__name__}Match", type=type, _match=match)
        
    def expr_char_match(self, tree):
        type = tree[0]
        match = tree[1]
        return CharMatchType.make(f"{type.__name__}Match", type=type, _match=match)
    
    def expr_name(self, f):
        name = str(f[0])
        if name in primitive_types:
            return primitive_types[name]
        else:
            return ExprName.make(f"{name}", _name=name)
    
    def expr_int(self, f):
        type_ = ExprHex if f[0].startswith("0x") else ExprInt
        num = eval(f[0])
        return type_.make(_int=num)
    
    def expr_string(self, token):
        string = str(token[0])
        return ExprString.make(string, _string=string)
    
    def expr_struct(self, f):
        return f[0]
    
    def expr_count(self, f):
        count_tree, type_ = f
        if count_tree.children:
            count = count_tree.children[0]
        else:
            count = None
        return Array.make(f"[]{type_.__name__}", parsetype=type_, length=count)
    
    def expr_ptr(self, f):
        addr = f[0]
        type_ = f[1]
        return Pointer.make(None, addr=addr, type=type_)
    
    def expr_pipeptr(self, f):
        addr = f[0]
        type_ = f[1]
        return PipePointer.make(f"|@({addr.__name__})({type_.__name__})", addr=addr, type=type_)
    
    def expr_arguments(self, f):
        return [str(x) for x in f]
    
    def expr_funcdef(self, f):
        name = f[0].value
        if len(f) == 3:
            arguments = f[1]
            type_ = f[2]
        else:
            arguments = []
            type_ = f[1]
        
        return Function.make(_name=name, type=type_, _arguments=arguments)
    
    def expr_call(self, f):
        expr = f[0]
        arguments = f[1:]
        
        return Call.make(func=expr, arguments=arguments)
    
    def expr_typedef(self, f):
        name = f[0].value
        type_ = f[1]
        
        return Name.make(_name=name, type=type_)
    
    def expr_typedeftoken(self, f):
        name = f[0].value
        
        return Name.make(_name=name, type=Token)
    
    #
    # field
    #
    
    def field_name(self, f):
        return str(f[0])
    
    def field_name_dot(self, f):
        return (f[0], f[1])
    
    def field_name_array(self, f):
        return (ForeignListAssignment(f[0]), f[1])
    
    def field_name_underscore(self, f):
        return "_"
    
    def field_return(self, f):
        expr = f[0]
        
        return Return.make("Return", expr=expr)
    
    def field_if(self, f):
        expr = f[0]
        true_struct = f[1]
        false_struct = f[2] if len(f) == 3 else []
        
        return (None, If.make("If", _expr=expr, _true_struct=true_struct, _false_struct=false_struct))
    
    def field_assert(self, f):
        cond = f[0][8:]
        
        raise NotImplementedError()
    
    def field_save(self, f):
        field_name = f[0]
        
        return SaveField(field_name)
    
    def field_debug(self, f):
        field_name = f[0]
        
        return DebugField(field_name)
    
    def field_yield(self, f):
        type = f[0]
        
        return (None, Yield.make("Yield", _type=type))
    
    def field_instance(self, f):
        name = f[0]
        type_ = f[1]
        
        return (name, type_)
    
    def field_typedef(self, f):
        return f[0]
    
    def statement_import(self, token):
        path = token[0] + ".dm"
        if self.path:
            path = self.path + "/" + path
        
        return parse_definition(open(path), name=f"!imported_{token[0]}", embed=True)
    
    def statement_symfile(self, token):
        path = token[0] + ".sym"
        if self.path:
            path = self.path + "/" + path
        
        symbols = parse_symfile(open(path))
        
        fields = []
        
        for symbol, addr in symbols.items():
            fields.append((symbol, ExprHex.make(None, _int=addr)))
        
        return ("sym", LenientStruct.make(f"SymfileStruct({token[0]})", _fields=fields, _return=[]))
        
grammar = open(os.path.dirname(__file__)+"/grammar.g").read()

parser = Lark(grammar, parser='lalr')

def parse_definition(definition, name=None, embed=False, stdlib=None):
    path = ""
    if type(definition) != str:
        path = os.path.dirname(definition.name)
        definition = definition.read()
    
    definition += "\n"
    
    transformer = TreeToStruct(path)
    struct = transformer.transform(parser.parse(definition))
    struct._filepath = path
    
    struct.resolve(stdlib=stdlib)
    if name:
        struct.__name__ = name
    if embed:
        struct._embed = embed
    
    return struct

def parse(definition, data, output_dir=None, lenient=False):
    stdlib = parse_definition(open(os.path.dirname(__file__)+"/stdlib.dm").read(), embed=True)
    struct = parse_definition(definition, stdlib=stdlib)
    if output_dir:
        output_dir = str(output_dir)
        if not output_dir.endswith("/"):
            output_dir += "/"
        struct._output_dir = output_dir
    else:
        struct._output_dir = struct._filepath + "/datamijn_out/"
    
    start = struct
    
    if type(data) == bytes:
        type_ = BytesIO
    else:
        type_ = type(data)
    
    data = type(f"{type_.__name__}WithBits", (IOWithBits, type_), {})(data)
    
    result = start.parse_stream(data, lenient=lenient)

    result._structs = struct
    return result

