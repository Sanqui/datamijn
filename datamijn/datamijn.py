#!/usr/bin/python3

# TODO study
# https://docs.python.org/3/library/collections.abc.html#module-collections.abc
# https://docs.python.org/3/library/numbers.html#module-numbers

import sys
import os.path
from io import BytesIO

from lark import Lark, Transformer
from lark.tree import Tree
import oyaml as yaml
import png

def whack__val_from(obj):
    if hasattr(obj, "_val"):
        while hasattr(obj, "_val") and obj._val != None:
            obj = obj._val
        return obj
    elif callable(obj):
        return lambda *args, **kvargs: whack__val_from(obj(*args, **kvargs))
    else:
        return obj

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
        self._value = value
        self._data = data
    
    @classmethod
    def parse_stream(self, stream, ctx):
        raise NotImplementedError()
    
    @classmethod
    def write(self, stream):
        raise NotImplementedError()
        
    @classmethod
    def resolve(self, ctx):
        return self
    
    def python_value(self):
        return self._value
    
    def __repr__(self):
        if hasattr(self, '_value'):
            return f"{self.__class__.__name__}({self._value})"
        else:
            return f"{self.__class__.__name__}"

class U8(Primitive, int):
    @classmethod
    def parse_stream(self, stream, ctx):
        address = stream.tell()
        length = 1
        data = stream.read(1)
        data = Data(data=data, address=address, length=length)
        
        value = ord(data.data)
        #return self(value=value, data=data)
        obj = int.__new__(self, value)
        obj._value = value
        obj._data = data
        return obj

class U16(Primitive, int):
    @classmethod
    def parse_stream(self, stream, ctx):
        address = stream.tell()
        length = 2
        data = stream.read(2)
        data = Data(data=data, address=address, length=length)
        
        value = data.data[0] | (data.data[1] << 8)
        #return self(value=value, data=data)
        obj = int.__new__(self, value)
        obj._value = value
        obj._data = data
        return obj

class U32(Primitive):
    pass

class Array(list, Primitive):
    @classmethod
    def parse_stream(self, stream, ctx):
        contents = []
        if callable(self._length):
            length = self._length(ctx[-1])
        else:
            length = self._length
        length = whack__val_from(length)
        for i in range(length):
            contents.append(self._type.parse_stream(stream, ctx))
        
        return self(contents)
    
    @classmethod
    def resolve(self, ctx):
        self._type = self._type.resolve(ctx)
        
        return self
    
    def python_value(self):
        return [o.python_value() for o in self]

def make_array(type_, length):
    return type('Array', (Array,), {'_type': type_, '_length': length})

#class ContainerResult(dict):
#    def __getattr__(self, name):
#        if name in self:
#            return self[name]
#        else:
#            raise AttributeError()

class Container(dict, Primitive):
    @classmethod
    def parse_stream(self, stream, ctx=None):
        if not ctx: ctx = []
        obj = self()
        ctx.append(obj)
        for struct, type_ in self._contents.items():
            obj[struct] = type_.parse_stream(stream, ctx)
        
        if self._computed_value:
            computed_value = self._computed_value.parse_stream(stream, ctx)
            for name, value in obj.items():
                setattr(computed_value, name, value)
            
            ctx.pop()
            return computed_value
        else:
            ctx.pop()
            return obj
    
    @classmethod
    def resolve(self, ctx=None):
        if not ctx: ctx = []
        ctx.append(self)
        for name, type_ in self._contents.items():
            self._contents[name] = type_.resolve(ctx)
        
        return self
        
    def python_value(self):
        out = {}
        for struct_name, struct in self.items():
            out[struct_name] = struct.python_value()
        
        return out
    
    #def __eq__(self, other):
    #    #if super().__eq__(other):
    #    #    return True
    #    elif '_val' in self and self._val == other:
    #        return True
    #    else:
    #        return False
    
    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError()
        #return self._contents[name]
    
    #def __str__(self):
    #    print(f"{self.__name__}")

def make_container(struct, types=None, computed_value=None):
    if not types: types = {}
    return type('Container', (Container,), {'_contents': struct, '_types': types, '_computed_value': computed_value})

class LazyType(str):
    def resolve(self, ctx):
        # TODO recursive context!
        if str(self) in ctx[0]._types:
            return ctx[0]._types[str(self)]
        found = False
        if not found:
            raise NameError(f"Cannot resolve type {self}, TODO context")

def eval_with_ctx(expr, ctx):
    if len(ctx):
        context = {**(ctx[-1]), '_root': ctx[0]}
    else:
        context = {'_root': None}
    
    return whack__val_from(eval(expr, context))

class Computed():
    def __init__(self, expr):
        self.expr = expr
    
    def resolve(self, ctx):
        return self

    def parse_stream(self, stream, ctx):
        result = eval_with_ctx(self.expr, ctx)
        result = type(f'Computed_{type(result).__name__}', (type(result),), {})(result)
        return result

class Pointer():
    def __init__(self, inner, address_expr):
        self.inner = inner
        self.address_expr = address_expr
    
    def resolve(self, ctx):
        self.inner = self.inner.resolve(ctx)
        return self
    
    def parse_stream(self, stream, ctx):
        address = eval_with_ctx(self.address_expr, ctx)
        pos = stream.tell()
        stream.seek(address)
        obj = self.inner.parse_stream(stream, ctx)
        stream.seek(pos)
        return obj

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
        #def _eval_ctx_func(ctx):
        #    try:
        #        result = eval(expr, {**self.structs_by_name, **ctx})
        #    except Exception as ex:
        #        raise type(ex)(f"{ex}\nPath: {ctx._path}")
        #    return result
        return expr
    
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
            val = eval(tree[1], self._enum)
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
    
    def container(self, tree):
        struct = []
        types = {}
        computed_value = None
        
        if len(tree) and isinstance(tree[-1], Computed):
            computed_value = tree.pop()
        
        for field in tree:
            if isinstance(field, Computed):
                raise SyntaxError("Bare non-computed value") # TODO nicer error
            elif isinstance(field, type) and issubclass(field, Primitive):
                types[field._name] = field
            else:
                struct.append(field)
        
        return make_container(dict(struct), types, computed_value)
    
    def type_enum(self, tree):
        pass
    
    def equ_field(self, f):
        name = f[0].value
        value = f[1]
        
        return (name, Computed(value))
    
    def bare_equ_field(self, f):
        value = f[0]
        
        return Computed(value)
    
    def if_field(self, f):
        cond = self._eval_ctx(f[0][4:])
        
        raise NotImplementedError()
    
    def assert_field(self, f):
        cond = self._eval_ctx(f[0][8:])
        
        raise NotImplementedError()
    
    def type_count(self, f):
        count_tree, type_ = f
        count = count_tree.children[0]
        return make_array(type_, count)
    
    def field(self, f):
        name = f[0].value
        params = f[1]
        type_ = f[2]
        
        field = type_
        for param in params.children:
            if param.data == "pointer":
                #pointer = whack__val_from(self._eval_ctx(param.children[0][1:]))
                field = Pointer(field, param.children[0][1:])
            else:
                raise ValueError(f"Unknown param type: {param.data}")
        
        return (name, field)
    
    def def_field(self, f):
        name = f[0].value
        type_ = f[1]
        
        type_._name = name
        return type_
    
    def import_(self, token):
        path = token[0] + ".dm"
        if self.path:
            path = self.path + "/" + path
        
        return parse_definition(open(path))
    
    #def start(self, structs):
    #    self.structs_by_name = dict(structs)
    #    
    #    result = make_container(dict(structs))
    #    return result
        
grammar = open(os.path.dirname(__file__)+"/grammar.g").read()

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
    #print(yaml.dump(result))
