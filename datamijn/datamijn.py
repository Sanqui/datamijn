#!/usr/bin/python3

# TODO study
# https://docs.python.org/3/library/collections.abc.html#module-collections.abc
# https://docs.python.org/3/library/numbers.html#module-numbers

import sys
import os.path
from io import BytesIO, BufferedIOBase

from lark import Lark, Transformer
from lark.tree import Tree
import oyaml as yaml
import png

class IOWithBits(BufferedIOBase):
    def read_bit(self):
        if not hasattr(self, '_byte'):
            self._byte = None
            self._bit_number = None
        
        if self._byte == None:
            self._byte = ord(self.read(1))
            self._bit_number = 0
        
        bit = (self._byte >> self._bit_number) & 1
        
        self._bit_number += 1
        if self._bit_number >= 8:
            self._byte = None
            self._bit_number = None
        
        return bit
    
    def read_bits(self, bits):
        if bits == 1:
            return self.read_bit()
        num = 0
        for i in range(bits):
            num |= self.read_bit() << i
        
        return num
    
    def read(self, amount):
        if getattr(self, '_byte', None) != None:
            raise RuntimeError("Attempting to read bytes while not byte-aligned")
        return super().read(amount)

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
    _char = False
    _embed = False
    def __init__(self, value=None, data=None):
        self._value = value
        self._data = data
    
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        raise NotImplementedError()
    
    @classmethod
    def write(self, stream):
        raise NotImplementedError()
        
    @classmethod
    def resolve(self, ctx):
        return self
    
    def _python_value(self):
        return self._value
    
    def __repr__(self):
        if hasattr(self, '_value'):
            return f"{self.__class__.__name__}({self._value})"
        else:
            return f"{self.__class__.__name__}"

class VoidType(Primitive):
    def __init__(self, self_=None):
        pass
    
    @classmethod
    def resolve(self, ctx):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        return self()
    
    @property
    def _typename(self):
        return str(self.__class__.__name__)
    
    @classmethod
    def _python_value(self):
        # XXX
        return f"<{self.__name__}>"
    
    def __eq__(self, other):
        if type(self) == type(other):
            return True
        elif type(self) == other:
            return True
        else:
            return False

class Terminator(VoidType): pass
class Null(Primitive):
    @classmethod
    def resolve(self, ctx):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        return None

class Byte(Primitive, bytes):
    _char = True
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        return self(stream.read(1))

class Short(Primitive, bytes):
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        return self(stream.read(2)[::-1])

class Word(Primitive, bytes):
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        return self(stream.read(4)[::-1])

class B1(Primitive, int):
    _num_bits = 1
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        value = stream.read_bits(self._num_bits)
        #return self(value=value, data=data)
        obj = int.__new__(self, value)
        obj._value = value
        #obj._data = data
        return obj
    
    def __str__(self):
        string = str(int(self))
        return f"{self.__class__.__name__}({string})"

def make_bit_type(num_bits):
    return type(f"B{num_bits}", (B1,), {"_num_bits": num_bits})

class U8(Primitive, int):
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
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
    
    def __str__(self):
        string = str(int(self))
        if self.__class__.__name__ != "U8":
            return f"{self.__class__.__name__}({string})"
        else:
            return string

class U16(Primitive, int):
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
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
    def parse_stream(self, stream, ctx, index=None):
        contents = []
        if callable(self._length):
            length = self._length(ctx[-1])
        else:
            length = self._length
        length = whack__val_from(length)
        
        i = 0
        while True:
            item = self._type.parse_stream(stream, ctx, index=i)
            if self._type._char and len(contents) and (
                 (isinstance(item, str)   and isinstance(contents[-1], str))
              or (isinstance(item, bytes) and isinstance(contents[-1], bytes))):
                contents[-1] += item
            else:
                contents.append(item)
            
            i += 1
            if length:
                if i >= length:
                    break
            elif issubclass(self._type, int):
                if contents[-1] == 0:
                    break
            elif isinstance(contents[-1], Terminator):
                break
            #else:
            #    raise ValueError("Improper terminating condition")
        
        if self._type._char and len(contents) == 1 and (
          isinstance(contents[0], str) or isinstance(contents[0], bytes)):
            contents = contents[0]
        
        if type(contents) == bytes:
            return contents
        else:
            return self(contents)
    
    @classmethod
    def resolve(self, ctx):
        self._type = self._type.resolve(ctx)
        
        return self
    
    def __str__(self):
        if self._type._char:
            string = ""
            for item in self:
                if isinstance(item, str):
                    string += item
                elif isinstance(item, Terminator):
                    pass
                else:
                    string += f"<{str(item)}>"
            
            return string
        else:
            return str(self.contents)
    
    def _python_value(self):
        return [o._python_value() for o in self]

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
    def parse_stream(self, stream, ctx=None, index=None):
        if not ctx: ctx = []
        obj = self()
        ctx.append(obj)
        obj._ctx = ctx
        for name, type_ in self._contents.items():
            obj[name] = type_.parse_stream(stream, ctx, index=index)
        
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
        
        new_types = {}
        
        for name, type_ in self._types.items():
            resolved = type_.resolve(ctx)
            if resolved._embed:
                new_types.update(resolved._types)
            else:
                self._types[name] = resolved
        
        self._types.update(new_types)
        
        for name, type_ in self._contents.items():
            self._contents[name] = type_.resolve(ctx)
        
        return self
    
    def __setitem__(self, key, value):
        while isinstance(key, tuple) and len(key) == 1:
            key = key[0]
        if isinstance(key, tuple):
            if isinstance(key[0], ForeignListAssignment):
                key_name = key[0].name
                is_list = True
            else:
                key_name = key[0]
                is_list = False
            if key_name not in self:
                raise NameError(f"`{key_name}` not in context")
            if is_list:
                if not isinstance(self[key_name], list):
                    raise TypeError(f"Attempting foreign list assignment to a non-list `{key_name}`")
                elif not isinstance(value, list):
                    raise TypeError(f"Attempting foreign list assignment to `{key_name}` with a non-list")
                elif len(self[key_name]) != len(value):
                    raise TypeError(f"Attempting foreign list assignment to `{key_name}` with a list of a different length")
                else:
                    for i in range(len(value)):
                        self[key_name][i][key[1:]] = value[i]
            else:
                self[key[0]][key[1:]] = value
        else:
            super().__setitem__(key, value)
        
    
    def _python_value(self):
        out = {}
        for struct_name, struct in self.items():
            if hasattr(struct, "_python_value"):
                out[str(struct_name)] = struct._python_value()
            else:
                out[str(struct_name)] = struct
        
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
        elif name in self._types:
            return self._types[name]
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
        for context in reversed(ctx):
            if str(self) in context._types:
                return context._types[str(self)].resolve(ctx)
        found = False
        if not found:
            raise NameError(f"Cannot resolve type {self}, TODO context")

def eval_with_ctx(expr, ctx, extra_ctx=None):
    if len(ctx):
        context = {**(ctx[-1]), '_root': ctx[0]}
    else:
        context = {'_root': None}
    context['_terminator'] = Terminator() # XXX ?!
    if extra_ctx:
        context.update(extra_ctx)
    
    return whack__val_from(eval(expr, context))

class Computed(Primitive):
    # _expr
    @classmethod
    def resolve(self, ctx):
        return self

    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        extra_ctx = {
            '_pos': stream.tell(),
            '_i': index
        }
        result = eval_with_ctx(self._expr, ctx, extra_ctx)
        if not isinstance(result, VoidType):
            result = type(f'Computed_{type(result).__name__}', (type(result),), {
                '_type': type(result),
                '_python_value': lambda self: self._type(self)})(result)
        return result

def make_computed(expr):
    return type("Computed", (Computed,), {'_expr': expr})

class Pointer(Primitive):
    def __init__(self, inner, address_expr):
        self.inner = inner
        self.address_expr = address_expr
    
    def resolve(self, ctx):
        self.inner = self.inner.resolve(ctx)
        return self
    
    def parse_stream(self, stream, ctx, index=None):
        address = eval_with_ctx(self.address_expr, ctx)
        pos = stream.tell()
        stream.seek(address)
        obj = self.inner.parse_stream(stream, ctx)
        stream.seek(pos)
        return obj

class StringType(Primitive):
    def __init__(self, string):
        self.string = string
    
    def resolve(self, ctx):
        return self

    def parse_stream(self, stream, ctx, index=None):
        return self.string

class MatchTypeMetaclass(type):
    def __getattr__(self, name):
        if name in self._match_types:
            return self._match_types[name]

class MatchType(Primitive, metaclass=MatchTypeMetaclass):
    
    @classmethod
    def resolve(self, ctx):
        self._type = self._type.resolve(ctx)
        for key, value in self._match.items():
            self._match[key] = value.resolve(ctx)
        
        # minor optimization
        self._ranges = {}
        for key, value in self._match.items():
            if isinstance(key, KeyRange):
                self._ranges[key] = value
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        value = self._type.parse_stream(stream, ctx)
        
        if value in self._match:
            return self._match[value].parse_stream(stream, ctx)
        else:
            for range, rangeval in self._ranges.items():
                if range.from_ <= value < range.to:
                    return rangeval.parse_stream(stream, ctx)
            
            if DefaultKey in self._match:
                return self._match[DefaultKey].parse_stream(stream, ctx)
            else:
                # XXX improve this error
                raise KeyError(f"Parsed value {value}, but not present in match.")
    

def make_type_match(type_, match, char=False):
    match_types = {v.__name__: v for k, v in match.items() if isinstance(v, type) and issubclass(v, Primitive)}
    return type('MatchType', (MatchType,), {'_type': type_, '_match': match, '_match_types': match_types, '_char': char})

class PipeStream(IOWithBits):
    def __init__(self, stream, ctx, type_):
        self._stream = stream
        self._ctx = ctx
        self._type = type_
        
        self._buffer = b""
        
        self._byte = None
        self._bit_number = None
    
    def read(self, num):
        while len(self._buffer) < num:
            result = self._type.parse_stream(self._stream, self._ctx)
            if not isinstance(result, bytes):
                raise TypeError(f"Pipe received {type(result)}.  Only bytes may be passed through a pipe.")
            self._buffer += result
        
        val = self._buffer[:num]
        self._buffer = self._buffer[num:]
        return val
    
    def tell(self):
        return None
    
    @property
    def empty(self):
        return len(self._buffer) == 0 and not self._bit_number

class Pipe(Primitive):
    # _left_type
    # _right_type
    @classmethod
    def resolve(self, ctx):
        self._left_type = self._left_type.resolve(ctx)
        self._right_type = self._right_type.resolve(ctx)
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        pipe_stream = PipeStream(stream, ctx, self._left_type)
        result = self._right_type.parse_stream(pipe_stream, ctx)
        if not pipe_stream.empty:
            raise ValueError("Unaccounted data remaining in pipe.  TODO this should be suppressable")
        return result
        
def make_pipe(left_type, right_type):
    return type(f"{left_type.__name__}Pipe{right_type.__name__}", (Pipe,), {
        "_left_type": left_type,
        "_right_type": right_type})

class ForeignKey(Primitive):
    # _type
    # field_name
    def __init__(self, result, ctx):
        self._result = result
        self._ctx = ctx
    
    @classmethod
    def resolve(self, ctx):
        self._type = self._type.resolve(ctx)
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, index=None):
        result = self._type.parse_stream(stream, ctx)
        
        return self(result, ctx[0])
    
    def __getattr__(self, attr):
        foreign = self._ctx[self._field_name]
        
        try:
            val = foreign[self._result]
        except IndexError:
            raise IndexError(f"Indexing foreign list `{self._field_name}[{self._result}]` failed")
        
        return getattr(val, attr)
    
    def __repr__(self):
        return f"{type(self).__name__}({repr(self._result)}, {repr(self._field_name)})"

def make_foreign_key(type_, field_name):
    return type(f"{type_.__name__}ForeignKey", (ForeignKey,), {
        "_type": type_,
        "_field_name": field_name})

class ForeignListAssignment():
    def __init__(self, name):
        self.name = name
    
class DefaultKey(): pass

class KeyRange():
    def __init__(self, from_, to):
        self.from_ = from_
        self.to = to
    
    def __add__(self, other):
        if isinstance(other, int):
            return self.to - 1 + other
        else:
            return NotImplemented

primitive_types = {
    "b1": B1,
    "u8": U8,
    "u16": U16,
    "u32": U32,
    "byte": Byte,
    "short": Short,
    "word": Word,
    # TODO long
    "Terminator": Terminator,
    "Null": Null,
}

for i in range(2, 33):
    primitive_types[f"b{i}"] = make_bit_type(i)

class TreeToStruct(Transformer):
    def __init__(self, structs_by_name, path):
        self.structs_by_name = structs_by_name
        self.path = path
        self.match_last = -1
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
    
    def stringtype(self, token):
        return StringType(token[0])
    
    def ctx_expr(self, token):
        expr = token[0][1:]
        
        return self._eval_ctx(expr)
    
    def ctx_expr_par(self, token):
        expr = token[0][2:-1]
        
        return self._eval_ctx(expr)
    
    def ctx_name(self, token):
        def ctx_name(ref):
            return lambda this: this[ref]
        
        return ctx_name(token[0].value)
    
    def match_key_int(self, tree):
        return int(tree[0])
    
    def match_key_string(self, tree):
        return str(tree[0])
    
    def match_key_default(self, tree):
        return DefaultKey
    
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
    
    def typename(self, token):
        type_ = token[0]
        if isinstance(type_, str):
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
        
        if len(tree) and isinstance(tree[-1], type) and issubclass(tree[-1], Computed):
            computed_value = tree.pop()
        
        for field in tree:
            if isinstance(field, type) and issubclass(field, Computed):
                raise SyntaxError("Bare non-computed value") # TODO nicer error
            if isinstance(field, type) and issubclass(field, Primitive):
                types[field._name] = field
            elif type(field) == tuple and len(field) == 2:
                struct.append(field)
            else:
                print(tree)
                raise RuntimeError(f"Internal error: unknown container field {field}")
        
        return make_container(dict(struct), types, computed_value)
    
    def type_pipe(self, tree):
        return make_pipe(*tree)
    
    def type_foreign_key(self, tree):
        return make_foreign_key(*tree)
    
    def type_equ(self, tree):
        value = tree[0]
        return make_computed(value)
    
    def type_match(self, tree):
        type = tree[0]
        match = tree[1]
        return make_type_match(type, match)
        
    def type_char_match(self, tree):
        type = tree[0]
        match = tree[1]
        return make_type_match(type, match, char=True)
    
    def field_name(self, f):
        return str(f[0])
    
    def field_name_dot(self, f):
        return (f[0], f[1])
    
    def field_name_array(self, f):
        return (ForeignListAssignment(f[0]), f[1])
    
    def equ_field(self, f):
        name = f[0]
        value = f[1]
        
        return (name, make_computed(value))
    
    def bare_equ_field(self, f):
        value = f[0]
        
        return make_computed(value)
    
    def if_field(self, f):
        cond = self._eval_ctx(f[0][4:])
        
        raise NotImplementedError()
    
    def assert_field(self, f):
        cond = self._eval_ctx(f[0][8:])
        
        raise NotImplementedError()
    
    def type_typename(self, f):
        return f[0]
    
    def type_container(self, f):
        return f[0]
    
    def type_count(self, f):
        count_tree, type_ = f
        if count_tree.children:
            count = count_tree.children[0]
        else:
            count = None
        return make_array(type_, count)
    
    def instance_field(self, f):
        name = f[0]
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
    
    def typedef_field(self, f):
        return f[0]
    
    def typedef(self, f):
        name = f[0].value
        type_ = f[1]
        
        return type(name, (type_,), {"_name": name})
    
    def typedefvoid(self, f):
        name = f[0].value
        
        return type(name, (VoidType,), {"_name": name})
    
    def import_(self, token):
        path = token[0] + ".dm"
        if self.path:
            path = self.path + "/" + path
        
        return parse_definition(open(path), name=token[0], embed=True)
    
    #def start(self, structs):
    #    self.structs_by_name = dict(structs)
    #    
    #    result = make_container(dict(structs))
    #    return result
        
grammar = open(os.path.dirname(__file__)+"/grammar.g").read()

parser = Lark(grammar, parser='lalr')

def parse_definition(definition, name=None, embed=False):
    path = ""
    if type(definition) != str:
        path = os.path.dirname(definition.name)
        definition = definition.read()
    
    definition += "\n"
    
    structs_by_name = {}
    transformer = TreeToStruct(structs_by_name, path)
    struct = transformer.transform(parser.parse(definition))
    
    struct.resolve()
    if name:
        struct._name = name
    if embed:
        struct._embed = embed
    
    return struct

def parse(definition, data):
    struct = parse_definition(definition)
    
    start = struct
    
    if type(data) == bytes:
        type_ = BytesIO
    else:
        type_ = type(data)
    
    data = type(f"{type_.__name__}WithBits", (type_, IOWithBits), {})(data)
    
    result = start.parse_stream(data)

    result._structs = struct
    return result

if __name__ == "__main__":
    from sys import argv

    STRUCTF = argv[1]
    FILEF = argv[2]
    
    result = parse(open(STRUCTF), open(FILEF, "rb"))
    #print(result)
    print(yaml.dump(result._python_value()))
    #print(yaml.dump(result))
