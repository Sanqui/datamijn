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
    def new(self, name, **kwargs):
        return type(name, (self,), kwargs)
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        raise NotImplementedError()
    
    @classmethod
    def write(self, stream):
        raise NotImplementedError()
        
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    def _save(self):
        raise NotImplementedError()
    
    def _python_value(self):
        return self._value
    
    def __repr__(self):
        if hasattr(self, '_value'):
            return f"{self.__class__.__name__}({self._value})"
        else:
            return f"{self.__class__.__name__}"

class Tile(Primitive):
    width = 8
    height = 8
    depth = 2
    
    def __init__(self, tile):
        self.tile = tile
    
    def _open_with_path(self, ctx, path):
        output_dir = getattr(ctx[0], "_output_dir", None)
        if not output_dir:
            output_dir = ctx[0]._filepath + "/datamijn_out/"
        filepath = output_dir + "/" + "/".join(path[:-1])
        os.makedirs(filepath, exist_ok=True)
        return open(filepath + f"/{path[-1]}.png", 'wb')

def bits(byte):
    return (
        (byte     ) & 1,
        (byte >> 1) & 1,
        (byte >> 2) & 1,
        (byte >> 3) & 1,
        (byte >> 4) & 1,
        (byte >> 5) & 1,
        (byte >> 6) & 1,
        (byte >> 7) & 1,
    )

class LinearTile(Tile):
    width = 8
    height = 8
    depth = 2
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        tile = []
        assert self.width == 8
        for line in range(self.height):
            line = [0, 0, 0, 0, 0, 0, 0, 0]
            for d in range(self.depth):
                layer = bits(ord(stream.read(1)))
                for x in range(8):
                    line[-x] |= layer[x] << d
            tile.append(line)
        return self(tile)
    
    def _save(self, ctx, path):
        f = self._open_with_path(ctx, path)
        w = png.Writer(self.width, self.height, greyscale=True, bitdepth=self.depth)
        w.write(f, self.tile)
        f.close()

class Tile1BPP(LinearTile):
    depth = 1

class NESTile(LinearTile):
    depth = 2

class PlanarTile(Primitive): pass
class GBTile(Primitive): pass

class VoidType(Primitive):
    def __init__(self, self_=None):
        pass
    
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
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
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        return None

class Byte(Primitive, bytes):
    _char = True
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        return self(stream.read(1))

class Short(Primitive, bytes):
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        return self(stream.read(2)[::-1])

class Word(Primitive, bytes):
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        return self(stream.read(4)[::-1])

class B1(Primitive, int):
    _num_bits = 1
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
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
    def parse_stream(self, stream, ctx, path, index=None):
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
    def parse_stream(self, stream, ctx, path, index=None):
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
    def resolve(self, ctx, path):
        self._type = self._type.resolve(ctx, path)
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        contents = []
        if callable(self._length):
            length = self._length(ctx[-1])
        else:
            length = self._length
        length = whack__val_from(length)
        
        i = 0
        while True:
            item = self._type.parse_stream(stream, ctx, path + [i], index=i)
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

#class ContainerResult(dict):
#    def __getattr__(self, name):
#        if name in self:
#            return self[name]
#        else:
#            raise AttributeError()

class Container(dict, Primitive):
    @classmethod
    def resolve(self, ctx=None, path=None):
        if not ctx: ctx = []
        if not path: path = []
        ctx.append(self)
        
        new_types = {}
        
        for name, type_ in self._types.items():
            resolved = type_.resolve(ctx, path + [name])
            if resolved._embed:
                new_types.update(resolved._types)
            else:
                self._types[name] = resolved
        
        self._types.update(new_types)
        
        contents = []
        
        for name, type_ in self._contents:
            contents.append((name, type_.resolve(ctx, path + [name])))
        
        self._contents = contents
        
        ctx.pop()
        
        return self
    
    
    @classmethod
    def parse_stream(self, stream, ctx=None, path=None, index=None):
        if not ctx: ctx = []
        if not path: path = []
        obj = self()
        ctx.append(obj)
        obj._ctx = ctx
        for name, type_ in self._contents:
            passed_path = path[:]
            if name:
                passed_path += [name]
            result = type_.parse_stream(stream, ctx, passed_path, index=index)
            if name:
                obj[name] = result
        
        if self._computed_value:
            computed_value = self._computed_value.parse_stream(stream, ctx, path + ["_computed_value"])
            if computed_value != None:
                for name, value in obj.items():
                    setattr(computed_value, name, value)
            
            ctx.pop()
            return computed_value
        else:
            ctx.pop()
            return obj
    
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

class LazyType(str):
    def resolve(self, ctx, path):
        # TODO recursive context!
        for context in reversed(ctx):
            if str(self) in context._types:
                return context._types[str(self)].resolve(ctx, path)
        found = False
        if not found:
            context = ".".join(path)
            raise NameError(f"Cannot resolve type {self}, path: {context}")

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
    def resolve(self, ctx, path):
        return self

    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        extra_ctx = {
            '_pos': stream.tell(),
            '_i': index
        }
        result = eval_with_ctx(self._expr, ctx, extra_ctx)
        if not isinstance(result, VoidType) and result != None:
            result = type(f'Computed_{type(result).__name__}', (type(result),), {
                '_type': type(result),
                '_python_value': lambda self: self._type(self)})(result)
        return result

class Pointer(Primitive):
    def __init__(self, inner, address_expr):
        self.inner = inner
        self.address_expr = address_expr
    
    def resolve(self, ctx, path):
        self.inner = self.inner.resolve(ctx, path)
        return self
    
    def parse_stream(self, stream, ctx, path, index=None):
        address = eval_with_ctx(self.address_expr, ctx)
        pos = stream.tell()
        stream.seek(address)
        obj = self.inner.parse_stream(stream, ctx, path)
        stream.seek(pos)
        return obj

class StringType(Primitive):
    def __init__(self, string):
        self.string = string
    
    def resolve(self, ctx, path):
        return self

    def parse_stream(self, stream, ctx, path, index=None):
        return self.string

class MatchTypeMetaclass(type):
    def __getattr__(self, name):
        if name in self._match_types:
            return self._match_types[name]

class MatchType(Primitive, metaclass=MatchTypeMetaclass):
    @classmethod
    def resolve(self, ctx, path):
        self._match_types = {v.__name__: v for k, v in self._match.items() if isinstance(v, type) and issubclass(v, Primitive)}
        self._type = self._type.resolve(ctx, path)
        for key, value in self._match.items():
            self._match[key] = value.resolve(ctx, path + [key])
        
        # minor optimization
        self._ranges = {}
        for key, value in self._match.items():
            if isinstance(key, KeyRange):
                self._ranges[key] = value
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        value = self._type.parse_stream(stream, ctx, path)
        
        if value in self._match:
            return self._match[value].parse_stream(stream, ctx, path + [f"[{value}]"])
        else:
            for range, rangeval in self._ranges.items():
                if range.from_ <= value < range.to:
                    return rangeval.parse_stream(stream, ctx, path + [f"[{range}]"])
            
            if DefaultKey in self._match:
                return self._match[DefaultKey].parse_stream(stream, ctx, path + [f"[_]"])
            else:
                # XXX improve this error
                raise KeyError(f"Parsed value {value}, but not present in match.")

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
            result = self._type.parse_stream(self._stream, self._ctx, [f"({self})"]) # XXX
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
    def resolve(self, ctx, path):
        self._left_type = self._left_type.resolve(ctx, path + ["(left)"])
        self._right_type = self._right_type.resolve(ctx, path + ["(left)"])
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        pipe_stream = PipeStream(stream, ctx, self._left_type)
        result = self._right_type.parse_stream(pipe_stream, ctx, path)
        if not pipe_stream.empty:
            raise ValueError("Unaccounted data remaining in pipe.  TODO this should be suppressable")
        return result

class ForeignKey(Primitive):
    # _type
    # field_name
    def __init__(self, result, ctx):
        self._result = result
        self._ctx = ctx
    
    @classmethod
    def resolve(self, ctx, path):
        self._type = self._type.resolve(ctx, path)
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None):
        result = self._type.parse_stream(stream, ctx, path)
        
        if result == None:
            return None
        
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

class Field(): pass

class SaveField(Field):
    def __init__(self, field_name):
        self._field_name = field_name
    
    def resolve(self, ctx, path):
        return self
    
    def parse_stream(self, stream, ctx, path, index=None):
        foreign = ctx[-1][self._field_name]
        foreign._save(ctx, path + [self._field_name])
    

primitive_types = {
    "b1": B1,
    "u8": U8,
    "u16": U16,
    "u32": U32,
    "byte": Byte,
    "short": Short,
    "word": Word,
    # TODO long
    "Tile1BPP": Tile1BPP,
    "NESTile": NESTile,
    "GBTile": GBTile,
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
            elif isinstance(field, Field):
                struct.append((None, field))
            elif type(field) == tuple and len(field) == 2:
                struct.append(field)
            else:
                print(tree)
                raise RuntimeError(f"Internal error: unknown container field {field}")
        
        return Container.new("Container", _contents=struct, _types=types, _computed_value=computed_value)
    
    def type_pipe(self, tree):
        left_type, right_type = tree
        return Pipe.new(f"{left_type.__name__}Pipe{right_type.__name__}",
            _left_type=left_type, _right_type=right_type)
    
    def type_foreign_key(self, tree):
        type_, field_name = tree
        return ForeignKey.new(f"{type_.__name__}ForeignKey",
            _type=type_, _field_name=field_name)
    
    def type_equ(self, tree):
        value = tree[0]
        return Computed.new("Computed", _expr=value)
    
    def type_match(self, tree):
        type = tree[0]
        match = tree[1]
        return MatchType.new(f"{type}Match", _type=type, _match=match, _char=False)
        
    def type_char_match(self, tree):
        type = tree[0]
        match = tree[1]
        return MatchType.new(f"{type}Match", _type=type, _match=match, _char=True)
    
    def field_name(self, f):
        return str(f[0])
    
    def field_name_dot(self, f):
        return (f[0], f[1])
    
    def field_name_array(self, f):
        return (ForeignListAssignment(f[0]), f[1])
    
    def equ_field(self, f):
        name = f[0]
        value = f[1]
        
        return (name, Computed.new(name, _expr=value))
    
    def bare_equ_field(self, f):
        value = f[0]
        
        return Computed.new("Computed", _expr=value)
    
    def if_field(self, f):
        cond = self._eval_ctx(f[0][4:])
        
        raise NotImplementedError()
    
    def assert_field(self, f):
        cond = self._eval_ctx(f[0][8:])
        
        raise NotImplementedError()
    
    def save_field(self, f):
        field_name = f[0]
        
        return SaveField(field_name)
    
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
        return Array.new(f"{type_}Array[{count if count else ''}]", _type=type_, _length=count)
    
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
    struct._filepath = path
    
    struct.resolve()
    if name:
        struct._name = name
    if embed:
        struct._embed = embed
    
    return struct

def parse(definition, data, output_dir=None):
    struct = parse_definition(definition)
    struct._output_dir = output_dir
    
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
