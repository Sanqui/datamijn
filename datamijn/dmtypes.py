import operator
from io import BytesIO, BufferedIOBase
from datamijn.utils import UPPERCASE, full_type_name, ResolveError, ParseError

class IOWithBits(BufferedIOBase):
    def __init__(self, *args, **kvargs):
        super().__init__(*args, **kvargs)
        self._byte = None
        self._bit_number = None
        
    def read_bit(self):
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
        if self._byte != None:
            raise RuntimeError("Attempting to read bytes while not byte-aligned")
        return super().read(amount)

class Token(str):
    def __repr__(self):
        return f"Token({self})"

class Data():
    def __init__(self, data, address, length):
        self.data = data
        self.address = address
        self.length = length

class Primitive():
    _size = None
    _char = False
    _embed = False
    _forms = None
    _final = False
    _yields = False
    _final_type = None
    
    def __init__(self, value=None, data=None):
        self._value = value
        self._data = data
    
    @classmethod
    def size(self):
        if self._size != None:
            return int(self._size)
        else:
            raise NotImplementedError()
    
    @classmethod
    def new(self, name, bases=[], **kwargs):
        return type(name, (self, *bases), kwargs)
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        raise NotImplementedError()
    
    @classmethod
    def write(self, stream):
        raise NotImplementedError()
        
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def infer_type(self):
        if self._final_type != None and self._final_type != self:
            if issubclass(self._final_type, Primitive):
                return self._final_type.infer_type()
            else:
                return self._final_type
        else:
            return self
    
    @classmethod
    def _or_type(self, other):
        print("default _or_type")
        return None
    
    def _save(self, ctx, path):
        raise NotImplementedError()
    
    def __repr__(self):
        if hasattr(self, '_value'):
            return f"{self.__class__.__name__}({repr(self._value)})"
        else:
            return f"{self.__class__.__name__}"
    
class PipedPrimitive(Primitive):
    @classmethod
    def parse_left(self, left, ctx, path, index=None):
        raise NotImplementedError()

class VoidType(Primitive):
    _size = 0
    def __init__(self, self_=None):
        pass
    
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return self()
    
    @property
    def _typename(self):
        return str(self.__class__.__name__)
    
    def __str__(self):
        return f"<{type(self).__name__}>"
    
    def __eq__(self, other):
        if type(self) == type(other):
            return True
        elif type(self) == other:
            return True
        else:
            return False

class Terminator(VoidType): pass
class Null(Primitive):
    _size = 0
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return None

class Byte(Primitive, bytes):
    _size = 1
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        read = stream.read(1)
        if len(read) != self._size:
            raise ParseError(path, "Failed to read stream")
        return self(read)
    
    @classmethod
    def _mul_type(self, other):
        if issubclass(other, int):
            return bytes

class Short(Primitive, bytes):
    _size = 2
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        read = stream.read(2)[::-1]
        if len(read) != self._size:
            raise ParseError(path, "Failed to read stream")
        return self(read)

class Word(Primitive, bytes):
    _size = 4
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        read = stream.read(4)[::-1]
        if len(read) != self._size:
            raise ParseError(path, "Failed to read stream")
        return self(read)

class B1(Primitive, int):
    _size = 1/8
    _num_bits = 1
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        value = stream.read_bits(self._num_bits)
        #return self(value=value, data=data)
        obj = int.__new__(self, value)
        obj._value = value
        #obj._data = data
        return obj

def make_bit_type(num_bits):
    return type(f"B{num_bits}", (B1,), {"_num_bits": num_bits})

class U8(Primitive, int):
    _size = 1
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
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
    _size = 2
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
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
    _size = 4
    pass

class Array(Primitive):
    # _type
    # _length
    _concat = False
    _bytestring = False
    
    ARRAY_CLASSES = {
    }
    
    @classmethod
    def resolve(self, ctx, path):
        if self._length != None and not isinstance(self._length, int):
            self._length = self._length.resolve(ctx, path)
            if self._length._final:
                self._length = self._length.parse_stream(None, None, path)
        self._type = self._type.resolve(ctx, path)
        
        match = None
        for elem_types, new_class in self.ARRAY_CLASSES.items():
            match = None
            cur_type = self
            for elem_type in elem_types:
                if hasattr(cur_type.infer_type(), "_type") \
                  and issubclass(cur_type.infer_type()._type.infer_type(), elem_type):
                    cur_type = cur_type._type
                    match = new_class
                else:
                    match = None
            if match:
                break
        
        length_name = ""
        if self._length and isinstance(self._length, int):
            length_name = str(self._length)
        elif self._length:
            length_name = self._length.__name__
        
        if match:
            name = f"[{length_name}]{self._type.__name__}{match.__name__}"
        else:
            match = ListArray
            name = f"[{length_name}]{self._type.__name__}"
        
        new = match.new(name, _type=self._type, _length=self._length)
        new._yields = self._type._yields
        #final = self._type.infer_type()
        #new._final_type = Array.new(f"[]{final.__name__}", _type=final)
        #new._final_type.resolve(ctx, path + ["(final)"])
        return new
        
    
    @classmethod
    def size(self):
        if isinstance(self._length, int):
            return self._length * self._type.infer_type().size()
        else:
            return None
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        contents = []
        if isinstance(self._length, type) and issubclass(self._type, Primitive):
            length = self._length.parse_stream(stream, ctx, path, **kwargs)
        else:
            length = self._length
        
        if self._length != None and self._type == Byte:
            # Speed optimization for byte arrays!
            return stream.read(length)
        
        i = 0
        while True:
            item = self._type.parse_stream(stream, ctx, path + [i], index=i, **kwargs)
            
            if self._concat and len(contents) \
              and type(contents[-1]) == type(item) \
              and isinstance(item, str):
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
        
        # XXX This sucks, but it's the price for computed values.
        # Hopefully we can get rid of it one day
        #if issubclass(self._type, Container) and self._type._return != None and len(contents) > 0:
        #    self._type = type(contents[0])
        #self._type = self._type.infer_type()
        
        if self._bytestring or len(contents) and isinstance(contents[0], bytes):
            return b"".join(contents)
        else:
            return self(contents)
    
    @classmethod
    def _or_type(self, other):
        if issubclass(other, Array):
            return self._type._or_type(other._type)
        return None
    
    def __or__(self, other):
        if len(self) != len(other):
            raise TypeError(f"Piped arrays must be of matching length ({len(self)} != {len(other)})")
        
        newlist = []
        for item0, item1 in zip(self, other):
            newlist.append(item0 | item1)
        
        newlist = type(self)(newlist)
        
        # XXX :(
        if len(newlist) > 0:
            newlist._type = type(newlist[0])
        
        return newlist
        
    def _save(self, ctx, path):
        for i, elem in enumerate(self):
            elem._save(ctx, path + [i])

class ListArray(list, Array):
    def __add__(self, other):
        if not isinstance(other, ListArray):
            return NotImplemented
        
        return type(self)(list(self) + list(other))

class String(ListArray):
    _concat = True
    
    def __str__(self):
        string = ""
        for item in self:
            if isinstance(item, str):
                string += item
            elif isinstance(item, Terminator):
                pass
            else:
                string += f"<{repr(item)}>"
        
        return string

class ByteString(bytes, Array):
    _concat = True
    _bytestring = True
    
class Container(dict, Primitive):
    @classmethod
    def resolve(self, ctx=None, path=None, stdlib=None):
        if not ctx: ctx = []
        if not path: path = []
        ctx.append(self)
        
        if stdlib:
            self._types["!stdlib"] = stdlib
        
        new_types = {}
        
        for name, type_ in self._types.items():
            if name[0] not in UPPERCASE + "!":
                raise ResolveError(path, f"{name}: Type names must start with an uppercase letter.")
            resolved = type_.resolve(ctx + [new_types], path + [name])
            if resolved._embed:
                new_types.update(resolved._types)
            else:
                self._types[name] = resolved
        
        self._types.update(new_types)
        
        contents = []
        contents_dict = {}
        
        for name, type_ in self._contents:
            if name and isinstance(name, str) and name[0] in UPPERCASE:
                raise ResolveError(path, f"{name}: Field names must start with a lowercase letter.")
            resolved = type_.resolve(ctx, path + [name])
            
            if name and name in contents_dict and contents_dict[name].infer_type() != resolved.infer_type():
                raise ResolveError(path, f"Field {name} is redefined with a different type.\n{full_type_name(contents_dict[name].infer_type())} != {full_type_name(resolved.infer_type())}")
            
            if resolved._yields:
                self._yields = True
            
            contents.append((name, resolved))
            contents_dict[name] = resolved
        
        self._contents = contents
        
        if self._return:
            self._return = self._return.resolve(ctx, path + ["_return"])
            self._final_type = self._return.infer_type()
        
        ctx.pop()
        
        return self
    
    @classmethod
    def size(self):
        size = 0
        for name, type_ in self._contents:
            size += type_.size()
        
        return size
    
    @classmethod
    def parse_stream(self, stream, ctx=None, path=None, index=None, **kwargs):
        if not ctx: ctx = []
        if not path: path = []
        obj = self()
        ctx.append(obj)
        obj._ctx = ctx
        for name, type_ in self._contents:
            passed_path = path[:]
            if name:
                passed_path += [name]
            result = type_.parse_stream(stream, ctx, passed_path, index=index, **kwargs)
            if name:
                obj[name] = result
            elif isinstance(result, Container) and result._embed:
                obj.update(result)
        
        if self._return:
            value = self._return.parse_stream(stream, ctx, path + ["_return"], index=index, **kwargs)
            ctx.pop()
            return value
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
    
    def __getattr__(self, name):
        if name in self:
            return self[name]
        elif name in self._types:
            return self._types[name]
        else:
            raise AttributeError()
    
    @classmethod
    def _or_type(self, other):
        if not issubclass(other, Container):
            return None
        if set(n for n, t in self._contents if not n.startswith("_")) != set(n for n, t in other._contents if not n.startswith("_")):
            raise TypeError(f"Piped containers must have matching fields")
        
        # TODO this should return a properly piped type of the result!!!!! XXX
        
        return self
        
    
    def __or__(self, other):
        if not isinstance(other, Container):
            return NotImplemented
        if set(n for n, t in self._contents if not n.startswith("_")) != set(n for n, t in other._contents if not n.startswith("_")):
            raise TypeError(f"Piped containers must have matching fields")
        
        newdict = {}
        for key0 in self:
            try:
                newdict[key0] = self[key0] | other[key0]
            except Exception as ex:
                if key0.startswith("_"):
                    newdict[key0] = None
                else:
                    raise type(ex)(f"{type(ex).__name__}: {ex}\nWhile piping {key0}")
        
        return type(self)(newdict)
    
    def _save(self, ctx, path):
        for key, value in self.items():
            if key.startswith("_"):
                continue
            value._save(ctx, path + [key])
    
    def _is_empty(self):
        for key in self:
            if not key.startswith("_"):
                return False
        return True
    
    def __repr__(self):
        name = type(self).__name__
        return f"<{name}>"
    
    def _pretty_repr(self):
        name = type(self).__name__
        if name == "Container":
            name = ""
        out = f"{name} {'{'}\n"
        for name, type_ in self._contents:
            if isinstance(name, tuple): continue
            if not name: continue
            if isinstance(self[name], Container):
                valrepr = "\n  ".join(self[name]._pretty_repr().split('\n'))
            else:
                valrepr = repr(self[name])
            out += f"  {name}: {valrepr}\n"
        out += "}"
        
        if len(self._contents) == 0:
            out = out.replace("\n", "")
        return out.strip()

class ExprName(Primitive):
    #_name
    
    @classmethod
    def resolve(self, ctx, path):
        if self._name[0] in UPPERCASE:
            for context in reversed(ctx):
                if type(context) == dict:
                    if self._name in context:
                        return context[self._name].resolve(ctx, path)
                else:
                    if self._name in context._types:
                        return context._types[self._name].resolve(ctx, path)
            
            raise ResolveError(path, f"Cannot resolve type {self._name}")
        else:
            # This is a reference!
            final_type = None
            for context in reversed(ctx):
                if isinstance(context, dict):
                    if self._name in context:
                        final_type = context[self._name]
                        break
                else:
                    for name, type_ in context._contents:
                        if name == self._name:
                            final_type = type_
                            break
                if final_type:
                    break
            
            if final_type == None:
                error_text = f"Cannot resolve name {self._name}"
                if self._name in "b1 b2 b4 u8 u16 u32".split():
                    error_text += f"\nDid you mean {self._name.upper()}?"
                raise ResolveError(path, error_text)
            
            self._final_type = final_type.infer_type()
            
            return self

    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        for context in reversed(ctx):
            if self._name in context:
                return context[self._name]
        
        raise ParseError(path, f"Cannot resolve name {self._name}")

class ExprInt(Primitive):
    _final = True
    _final_type = int
    #_int
    
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return self._int

class Expr(Primitive):
    #_left
    #_right
    #_op
    
    @classmethod
    def resolve(self, ctx, path):
        self._left = self._left.resolve(ctx, path)
        self._right = self._right.resolve(ctx, path)
        self._final = self._left._final and self._right._final
        
        type_func_name = f'_{self._op.__name__.rstrip("_")}_type'
        
        transformed_type = None
        if hasattr(self._left.infer_type(), type_func_name):
            transformed_type = getattr(self._left.infer_type(), type_func_name)(self._right.infer_type())
        
        if self._left.infer_type() != self._right.infer_type() \
            and not issubclass(self._left.infer_type(), self._right.infer_type()) \
            and not issubclass(self._right.infer_type(), self._left.infer_type()) \
            and not (
              issubclass(self._left.infer_type(), Array) \
              and issubclass(self._right.infer_type(), Array) \
              and (
                self._left.infer_type()._type.infer_type() == self._right.infer_type()._type.infer_type() \
                or self._left.infer_type()._type.infer_type().__name__ == self._right.infer_type()._type.infer_type().__name__
              ) # XXX more type string comparison
            ) and not transformed_type:
                raise ResolveError(path, f"Both types in an `{self._op.__name__}` expression have to match or be compatible.\n{full_type_name(self._left.infer_type())} != {full_type_name(self._right.infer_type())}")
        
        self._yields = self._left._yields or self._right._yields
        if transformed_type:
            self._final_type = transformed_type
        else:
            self._final_type = self._left.infer_type()
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        left = self._left.parse_stream(stream, ctx, path, index=index, **kwargs)
        right = self._right.parse_stream(stream, ctx, path, index=index, **kwargs)
        return self._op(left, right)

class ExprAttr(Primitive):
    #_left
    #_name
    @classmethod
    def resolve(self, ctx, path):
        self._left = self._left.resolve(ctx, path)
        if not issubclass(self._left.infer_type(), Container):
            raise ResolveError(path, f"Only containers may be attributed, not {full_type_name(self._left.infer_type())}.")
        
        self._yields = self._left._yields
        self._final_type = dict(self._left.infer_type()._contents)[self._name].infer_type()
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        left = self._left.parse_stream(stream, ctx, path, index=index, **kwargs)
        return left[self._name]

class ExprIndex(Primitive):
    #_left
    #_index
    @classmethod
    def resolve(self, ctx, path):
        self._left = self._left.resolve(ctx, path)
        self._index = self._index.resolve(ctx, path)
        if not issubclass(self._left.infer_type(), Array):
            raise ResolveError(path, f"Only arrays may be indexed, not {full_type_name(self._left.infer_type())}.")
        if not issubclass(self._index.infer_type(), int):
            raise ResolveError(path, f"Only ints may be used for indexing, not {full_type_name(self._index.infer_type())}.")
        
        self._yields = self._left._yields or self._index._yields
        self._final_type = self._left.infer_type()._type
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        left = self._left.parse_stream(stream, ctx, path, index=index, **kwargs)
        index = self._index.parse_stream(stream, ctx, path, index=index, **kwargs)
        return left[index]

class Return(Primitive):
    #_expr
    
    @classmethod
    def resolve(self, ctx, path):
        self._expr = self._expr.resolve(ctx, path)
        self._yields = self._expr._yields
        self._final_type = self._expr.infer_type()
        self._final = self._expr._final
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return self._expr.parse_stream(stream, ctx, path, index=index, **kwargs)

class Index(Primitive):
    _final_type = int
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return index

class Position(Primitive):
    _final_type = int
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return stream.tell()

class RightSize(Primitive):
    _final_type = int
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        for x in ctx:
            if '_right_size' in x:
                return x['_right_size']

def eval_with_ctx(expr, ctx, extra_ctx=None):
    if len(ctx):
        context = {'_root': ctx[0]}
        for x in ctx:
            context.update(x)
    else:
        context = {'_root': None}
    context['_terminator'] = Terminator() # XXX ?!
    if extra_ctx:
        context.update(extra_ctx)
    
    return eval(expr, context)

class Computed(Primitive):
    # _expr
    @classmethod
    def resolve(self, ctx, path):
        return self

    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        extra_ctx = {
        #    '_pos': stream.tell(),
        #    '_i': index
        }
        try:
            result = eval_with_ctx(self._expr, ctx, extra_ctx)
        except Exception as ex:
            pathstr = ".".join(str(x) for x in path)
            raise Exception(f"{type(ex).__name__}: {ex}\nWhile computing {pathstr}\nExpression: {self._expr}")
        if not isinstance(result, VoidType) and result != None:
            pass
        return result

class ExprType(Primitive):
    pass

class Pointer(Primitive):
    #_type
    #_addr
    
    @classmethod
    def resolve(self, ctx, path):
        self._type = self._type.resolve(ctx, path)
        self._addr = self._addr.resolve(ctx, path + ["(addr)"])
        if not issubclass(self._addr.infer_type(), int):
            raise ResolveError(path, f"Address must resolve to int.\n{self._addr.__name__} resolves to {full_type_name(self._addr.infer_type())}.\nHINT: This could be a syntax ambiguity.  If you intend to index or attribute in your address expression, make sure to put it in parenthesis!")
        self._final_type = self._type.infer_type()
        self._yields = self._type._yields or self._addr._yields # god forbid
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, **kwargs):
        address = self._addr.parse_stream(stream, ctx, path + ['(addr)'], **kwargs)
        pos = stream.tell()
        stream.seek(address)
        result = self._type.parse_stream(stream, ctx, path, **kwargs)
        stream.seek(pos)
        return result

class PipePointer(Pointer):
    @classmethod
    def parse_stream(self, stream, ctx, path, pipebuffer=None, **kwargs):
        address = self._addr.parse_stream(stream, ctx, path + ['(addr)'], **kwargs)
        pos = pipebuffer.tell()
        if address < 0:
            pipebuffer.seek(address, 2)
        else:
            pipebuffer.seek(address)
        result = self._type.parse_stream(pipebuffer, ctx, path, pipebuffer=None, **kwargs)
        pipebuffer.seek(pos)
        return result

class Yield(Primitive):
    _yields = True
    @classmethod
    def resolve(self, ctx, path):
        # TODO yields must not be assigned
        self._type = self._type.resolve(ctx, path)
        self.__name__ = f"{self._type.__name__}Yield"
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, pipestream=None, **kwargs):
        # TODO check this in resolve already
        if not pipestream:
            raise Exception(f'Cannot yield outside of a pipe.\nPath: {".".join(str(x) for x in path)}')
        data = self._type.parse_stream(stream, ctx, path, **kwargs)
        if not isinstance(data, bytes):
            raise TypeError(f'Only bytes may be yielded through a pipe (not {type(data).__name__}).\nPath: {".".join(str(x) for x in path)}')
        pipestream.append(data)
        return None

class StringType(Primitive):
    def __init__(self, string):
        self.string = string
    
    def resolve(self, ctx, path):
        return self

    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return self.string

# TODO explain why this is a thing ('cause I forgot)
class MatchTypeMetaclass(type):
    def __getattr__(self, name):
        if name in self._match_types:
            return self._match_types[name]
        else:
            raise AttributeError()

class MatchType(Primitive, metaclass=MatchTypeMetaclass):
    @classmethod
    def resolve(self, ctx, path):
        self._match_types = {v.__name__: v for k, v in self._match.items()
            if isinstance(v, type) and issubclass(v, Primitive)}
        self._type = self._type.resolve(ctx, path)
        self._yields = self._type._yields
        self._final_type = None
        for key, value in self._match.items():
            if isinstance(key, str):
                ctx.append({key: self._type})
            self._match[key] = value.resolve(ctx, path + [key])
            if value._yields:
                self._yields = True
            if not self._final_type:
                self._final_type = value.infer_type()
            
            # XXX we resort to string comparisons because
            # we lack a proper type system
            if self._final_type.__name__ != value.infer_type().__name__:
                self._final_type = self
            if isinstance(key, str):
                ctx.pop()
        
        if self._final_type == None:
            self._final_type = self
        
        # minor optimization
        self._ranges = {}
        self._default_key = None
        for key, value in self._match.items():
            if isinstance(key, KeyRange):
                self._ranges[key] = value
            elif isinstance(key, DefaultKey):
                self._default_key = key
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        value = self._type.parse_stream(stream, ctx, path, index=index, **kwargs)
        
        key_value = value
        if isinstance(value, Byte):
            key_value = ord(value)
        
        if key_value in self._match:
            return self._match[key_value].parse_stream(stream, ctx, path + [f"[{value}]"], **kwargs)
        else:
            for range, rangeval in self._ranges.items():
                if range.from_ <= key_value < range.to:
                    return rangeval.parse_stream(stream, ctx, path + [f"[{range}]"], **kwargs)
            
            if self._default_key != None:
                ctx_extra = {}
                if self._default_key:
                    ctx_extra = {str(self._default_key): value}
                return self._match[self._default_key].parse_stream(stream, ctx + [ctx_extra], path + [f"[_]"], **kwargs)
            else:
                # XXX improve this error
                raise Exception(f"Parsed value {value}, but not present in match.\nPath: {'.'.join(str(x) for x in path)}")

class CharMatchType(MatchType):
    pass

class PipeStream(IOWithBits):
    def __init__(self, stream, ctx, type_, path):
        self._path = path
        self._stream = stream
        self._ctx = ctx
        self._type = type_
        
        self._buffer = BytesIO(b"")
        
        self._byte = None
        self._bit_number = None
        self._pos = 0
        self._free_bytes = 0
        
        if not issubclass(type_.infer_type(), bytes):
            if issubclass(type_, Container):
                if not type_._yields:
                    raise TypeError(f"Attempting to pipe {full_type_name(type_.infer_type())}, which is a Container that does not yield.")
            else:
                raise TypeError(f"Attempting to pipe {full_type_name(type_.infer_type())}")
    
    def read(self, num):
        self._buffer.seek(0, 2) # SEEK_END
        while self._free_bytes < num:
            result = self._type.parse_stream(self._stream, self._ctx, self._path + ["<PipeStream>"], pipebuffer=self._buffer, pipestream=self) # XXX
            if result != None and not (isinstance(result, Container) and result._is_empty()):
                if not isinstance(result, bytes):
                    print(repr(result))
                    errormsg = f"Pipe received {type(result)}.  Only bytes may be passed through a pipe."
                    if isinstance(result, Container):
                        errormsg += "\nHint: if you're yielding data, prefix your keys with _."
                    raise TypeError(errormsg)
                self._free_bytes += len(result)
                self._buffer.write(result)
        
        self._buffer.seek(self._pos)
        val = self._buffer.read(num)
        assert(len(val) == num)
        self._pos += num
        self._free_bytes -= num
        
        return val
    
    def tell(self):
        return None
    
    def append(self, data):
        pos = self._buffer.tell()
        self._buffer.seek(0, 2)
        self._free_bytes += len(data)
        self._buffer.write(data)
        self._buffer.seek(pos)
    
    @property
    def empty(self):
        return self._free_bytes == 0 and not self._bit_number
    
    def __repr__(self):
        return (f"<{'.'.join(str(x) for x in self._path)} PipeStream>")

class Pipe(Primitive):
    # _left_type
    # _right_type
    @classmethod
    def resolve(self, ctx, path):
        self._left_type = self._left_type.resolve(ctx, path + ["(left)"])
        self._right_type = self._right_type.resolve(ctx, path + ["(right)"])
        if not self._left_type._yields \
          and not issubclass(self._left_type.infer_type(), ByteString) \
          and hasattr(self._left_type.infer_type(), "__or__") \
          and not issubclass(self._right_type, PipedPrimitive):
            expr = Expr.new(f"(| {self._left_type.__name__} {self._right_type.__name__})",
                _left=self._left_type, _right=self._right_type, _op=operator.or_)
            return expr.resolve(ctx, path)
        
        self._yields = self._left_type._yields or self._right_type._yields
        self._final_type = self._right_type.infer_type()
        
        self.__name__ = f"({self._left_type.__name__})|({self._right_type.__name__})"
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        if issubclass(self._right_type, PipedPrimitive):
            ctx = []
            left = self._left_type.parse_stream(stream, ctx, path, index=index, **kwargs)
            result = self._right_type.parse_left(left, ctx, path)
            return result
        else:
            right_size = None
            try:
                right_size = self._right_type.size()
            except Exception as ex:
                pass
            ctx.append({'_right_size': right_size})
            pipe_stream = PipeStream(stream, ctx, self._left_type, path=path)
            result = self._right_type.parse_stream(pipe_stream, ctx, path, **kwargs)
            #if not pipe_stream.empty:
            #    raise ValueError("Unaccounted data remaining in pipe.  TODO this should be suppressable")
            ctx.pop()
            return result

class ForeignKey(Primitive):
    # _type
    # field_name
    def __init__(self, result, ctx):
        self._result = result
        self._ctx = ctx
    
    @classmethod
    def resolve(self, ctx, path):
        if isinstance(self._field_name, str):
            self._field_name = (self._field_name,)
        self._type = self._type.resolve(ctx, path)
        self._yields = self._type._yields
        
        self.__name__ = f"{self._type.__name__}ForeignKey"
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        result = self._type.parse_stream(stream, ctx, path, **kwargs)
        
        if result == None:
            return None
        
        return self(result, ctx[0])
    
    @property
    def _object(self):
        foreign = self._ctx
        key = self._field_name
        while isinstance(key, tuple) and len(key) == 2:
            foreign = foreign[key[0]]
            key = key[1]
        while isinstance(key, tuple) and len(key) == 1:
            key = key[0]
        foreign = foreign[key]
                
        try:
            obj = foreign[self._result]
        except (IndexError, KeyError):
            raise IndexError(f"Indexing foreign list `{self._field_name}[{self._result}]` failed")
        
        return obj
    
    def __getattr__(self, attr):
        obj = self._object
        
        return getattr(obj, attr)
        
    def __repr__(self):
        return f"{type(self).__name__}({repr(self._result)}, {repr(self._field_name)})"

class ForeignListAssignment():
    def __init__(self, name):
        self.name = name
    
class DefaultKey(str): pass

class KeyRange():
    def __init__(self, from_, to):
        self.from_ = from_
        self.to = to
    
    def __add__(self, other):
        if isinstance(other, int):
            return self.to - 1 + other
        else:
            return NotImplemented

class If(Primitive):
    # _computed
    # _true_container
    # _false_container
    @classmethod
    def resolve(self, ctx, path):
        self._computed = self._computed.resolve(ctx, path)
        self._true_container = self._true_container.resolve(ctx, path)
        self._true_container._embed = True
        if self._false_container:
            self._false_container = self._false_container.resolve(ctx, path)
            self._false_container._embed = True
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        result = self._computed.parse_stream(stream, ctx, path, index=index, **kwargs)
        
        if result:
            return self._true_container.parse_stream(stream, ctx, path, index=index, **kwargs)
        else:
            if self._false_container:
                return self._false_container.parse_stream(stream, ctx, path, index=index, **kwargs)
            else:
                return None

class Field(): pass

class SaveField(Field):
    _yields = False
    def __init__(self, field_name):
        self._field_name = field_name
    
    def resolve(self, ctx, path):
        return self
    
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        foreign = ctx[-1][self._field_name]
        if not hasattr(foreign, "_save"):
            raise ParseError(path, f"field {self._field_name} (type {full_type_name(type(foreign))}) has no attribute _save (INTERNAL)")
        foreign._save(ctx, path + [self._field_name])

class DebugField(Field):
    _yields = False
    def __init__(self, field_name):
        self._field_name = field_name
    
    def resolve(self, ctx, path):
        return self
    
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        foreign = ctx[-1][self._field_name]
        print(f"{self._field_name} is {full_type_name(type(foreign))}: {repr(foreign)}")

Array.ARRAY_CLASSES.update({
        (Byte,):            ByteString,
        (str,):             String,
        (StringType,):      String,
        (CharMatchType,):   String,
})
