#!/usr/bin/python3
import sys
import os.path
from io import BytesIO

from lark import Lark, Transformer
from lark.tree import Tree
import oyaml as yaml
import png

class Token(str):
    def __repr__(self):
        return f"Token({self})"

class Data():
    def __init__(self, data, address, length):
        self.data = data
        self.address = address
        self.length = length

class Primitive():
    def __init__(self, value=None, data=None):
        self.value = value
        self.data = data
    
    @classmethod
    def parse_stream(self, stream):
        raise NotImplementedError()
    
    @classmethod
    def write(self, stream):
        raise NotImplementedError()
        
    @classmethod
    def resolve(self, ctx):
        return
    
    def python_value(self):
        return self.value
    
    def __repr__(self):
        print(f"Primitive({repr(self.name)})")

class U8(Primitive):
    @classmethod
    def parse_stream(self, stream):
        address = stream.tell()
        length = 1
        data = stream.read(1)
        data = Data(data=data, address=address, length=length)
        
        value = ord(data.data)
        return self(value=value, data=data)

class U16(Primitive):
    @classmethod
    def parse_stream(self, stream):
        address = stream.tell()
        length = 2
        data = stream.read(2)
        data = Data(data=data, address=address, length=length)
        
        value = data.data[0] | (data.data[1] << 8)
        return self(value=value, data=data)

class U32(Primitive):
    pass

class Container(Primitive):
    @classmethod
    def parse_stream(self, stream):
        contents = {}
        for struct, type_ in self.contents.items():
            contents[struct] = type_.parse_stream(stream)
        
        return make_container(contents)()
    
    @classmethod
    def resolve(self, ctx=None):
        if not ctx: ctx = []
        ctx.append(self)
        for name, type_ in self.contents.items():
            if isinstance(type_, LazyType):
                if str(type_) in ctx[0].contents:
                    self.contents[name] = ctx[0].contents[type_]
                    found = True
                if not found:
                    raise ValueError(f"Cannot resolve type {type_}, TODO context")
            else:
                type_.resolve(ctx)
    
    def python_value(self):
        out = {}
        for struct_name, struct in self.contents.items():
            out[struct_name] = struct.python_value()
        
        return out
    
    def __str__(self):
        print(f"Primitive({repr(self.name)})")

class LazyType(str):
    pass

def make_container(struct):
    return type('runtime_generated_container', (Container,), {'contents': struct})

primitive_types = {
    "u8": U8,
    "u16": U16,
    "u32": U32
}

class TreeToStruct(Transformer):
    def __init__(self, structs_by_name, path):
        self.structs_by_name = structs_by_name
        self.path = path
        self.enum_last = -1
        # XXX yes this is sadly an in-memory dupe
        self._enum = {}
        self.ifcounter = 0
    
    def _eval_ctx(self, expr):
        def _eval_ctx_func(ctx):
            try:
                result = eval(expr, {**self.structs_by_name, **ctx})
            except Exception as ex:
                raise type(ex)(f"{ex}\nPath: {ctx._path}")
            return result
        return _eval_ctx_func
    
    def string(self, token):
        return token[0][1:-1]
    
    def eval(self, token):
        return eval(token[0])
    
    def ctx_expr(self, token):
        expr = token[0][1:]
        
        return self._eval_ctx(expr)
    
    #def 
    
    def ctx_name(self, token):
        def ctx_name(ref):
            return lambda this: this[ref]
        
        return ctx_name(token[0].value)
    
    def enum_token(self, token):
        return Token(token[0])
    
    def enum_str(self, token):
        return token[0]
        
    def enum_field(self, tree):
        if len(tree) == 1:
            val = self.enum_last + 1
        else:
            val = tree[1](self._enum)
        self._enum[tree[0]] = val
        self.enum_last = val
        return (tree[0], val)
    
    def enum(self, tree):
        self._enum = {}
        self.enum_last = -1
        return dict(tree)
    
    def type(self, token):
        type_ = token[0]
        if isinstance(type_, type) and issubclass(type_, Container):
            return type_
        elif isinstance(type_, str):
            if type_ in primitive_types:
                return primitive_types[type_]
            elif type_ in "u1 u2 u3 u4 u5 u6 u7".split():
                raise NotImplementedError()
                #return BitsInteger(int(name[1]))
            else:
                return LazyType(type_)
        else:
            raise ValueError(f"Unknown type {type_}")
            raise NotImplementedError()
    
    def typedef(self, tree):
        struct = []
        
        for field in tree:
            struct.append(field)
        
        return make_container(dict(struct))
    
    def type_enum(self, tree):
        raise NotImplementedError()
    
    def equ_field(self, f):
        raise NotImplementedError()
    
    def if_field(self, f):
        cond = self._eval_ctx(f[0][4:])
        
        raise NotImplementedError()
    
    def assert_field(self, f):
        cond = self._eval_ctx(f[0][8:])
        
        raise NotImplementedError()
    
    def type_count(self, f):
        raise NotImplementedError()
    
    def field(self, f):
        name = f[0].value
        params = f[1]
        for param in params.children:
            if param.data == "pointer":
                #pointer = whack__val_from(self._eval_ctx(param.children[0][1:]))
                raise NotImplementedError()
            else:
                raise ValueError(f"Unknown param type: {param.data}")
        type_ = f[2]
        
        field = type_
        
        return (name, field)
    
    def import_(self, token):
        path = token[0] + ".dm"
        if self.path:
            path = self.path + "/" + path
        
        return parse_definition(open(path))
    
    def start(self, structs):
        self.structs_by_name = dict(structs)
        
        result = make_container(dict(structs))
        return result
        
grammar = open(sys.path[0]+"/grammar.g").read()

parser = Lark(grammar, parser='lalr')

def parse_definition(definition):
    path = ""
    if type(definition) != str:
        path = os.path.dirname(definition.name)
        definition = definition.read()
    
    definition += "\n"
    
    structs_by_name = {}
    transformer = TreeToStruct(structs_by_name, path)
    struct = transformer.transform(parser.parse(definition))
    
    struct.resolve()
    
    return struct

def parse(definition, data):
    struct = parse_definition(definition)
    
    if '_start' in struct.contents:
        start = struct.contents['_start']
    else:
        start = struct
    
    if type(data) == bytes:
        data = BytesIO(data)
    
    result = start.parse_stream(data)

    result._structs = struct
    return result

if __name__ == "__main__":
    from sys import argv

    STRUCTF = argv[1]
    FILEF = argv[2]
    
    result = parse(open(STRUCTF), open(FILEF, "rb"))
    #print(result)
    print(yaml.dump(result.python_value()))
