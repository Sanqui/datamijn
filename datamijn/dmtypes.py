import operator
from io import BytesIO, BufferedIOBase
from datamijn.utils import UPPERCASE, full_type_name, ResolveError, ParseError, ForeignKeyError, ReadError, SaveNotImplementedError, MakeError
from datamijn.traceint import TraceInt, Source

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
    
    def read(self, amount, strict=True):
        pos = self.tell()
        if self._byte != None:
            raise ReadError(f"Attempting to read bytes while not byte-aligned.\nRead of size {amount} at position {hex(pos)}.")
        result = super().read(amount)
        if strict and len(result) < amount:
            raise ReadError(f"Data access out of bounds.\nRead of size {amount} at position {hex(pos)}.")
        return result

BytesIOWithBits = type(f"BytesIOWithBits", (IOWithBits, BytesIO), {})

class Subs(dict):
    def __init__(self, *subs, **kwargs):
        for sub in subs:
            self[sub] = UninitializedSub
        for key, item in kwargs.items():
            if isinstance(item, list):
                for el in item:
                    if not issubclass(type(el), type) or not issubclass(el, DatamijnObject):
                        raise MakeError(f"Sub {key}: Element in list, {el}, is not a DatamijnObject, rather {type(el)} (internal error).")
            elif item is not None and (not issubclass(type(item), type) or not issubclass(item, DatamijnObject)):
                raise MakeError(f"Sub {key}: {item} is not a DatamijnObject, rather {type(item)} (internal error).")
            self[key] = item
    
    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        else:
            raise AttributeError(attr)
    
    def __setattr__(self, attr, val):
        if attr in self:
            self[attr] = val
        else:
            self.attr = val

class DatamijnObject():
    _size = None
    _char = False
    _embed = False
    _final = False
    _yields = False
    _final_type = None
    _inherited_fields = []
    _arguments = []
    _subs = Subs()
    
    #def __init__(self, value=None, data=None):
    #    self._value = value
    #    self._data = data
    
    @classmethod
    def size(self):
        if self._size != None:
            return int(self._size)
        elif self._final:
            return None
        else:
            raise NotImplementedError()
    
    @classmethod
    def rename(self, name=None):
        if name == None:
            if hasattr(self, '_namestring'):
                try:
                    self.__name__ = self._namestring.format(self=self)
                except (KeyError, AttributeError) as ex:
                    raise type(ex)(f"Invalid _namestring for class {self.__name__}: {type(ex).__name__}: {ex}")
            else:
                pass
        else:
            self.__name__ = name
    
    @classmethod
    def make(self, name=None, bases=[], make_all=False, **kwargs):
        newtype = type(name or self.__name__, (self, *bases), kwargs)
        if name is None:
            newtype.rename()
        
        newsubs = {}
        for subname, subval in self._subs.items():
            if subval == UninitializedSub:
                if subname not in kwargs:
                    raise MakeError(f"{self.__name__} takes sub `{subname}`, but not provided (internal error).")
                newsubs[subname] = kwargs[subname]
            else:
                if make_all:
                    newsubs[subname] = subval.make()
                else:
                    newsubs[subname] = subval

        newtype._subs = Subs(**newsubs)
        return newtype
        
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        raise NotImplementedError()
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, lenient=False, **kwargs):
        rich = ctx[0]._rich
        if rich:
            address = stream.tell()
            try:
                length = self.size()
            except NotImplementedError:
                length = None
            #data = stream.read(1)
            #data = Data(data=data, address=address, length=length)
        
        try:
            value = self._parse_stream(stream, ctx, path, index=index, **kwargs)
            assert value != None
        except Exception as ex:
            if lenient:
                obj = ex
            else:
                raise type(ex)(f'{ex}\nPath: {".".join(str(x) for x in path)}')
        else:
            if not isinstance(value, self):
                obj = self.__new__(self, value)
                obj.__init__(value)
            else:
                obj = value
        
        if rich:
            #obj._address = address
            #obj._size = length
            obj._path = path
            obj._error = isinstance(obj, Exception)
            
        return obj
    
    @classmethod
    def write(self, stream):
        raise NotImplementedError()
        
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def infer_type(self):
        if self._final_type != None and self._final_type != self:
            if issubclass(self._final_type, DatamijnObject):
                return self._final_type.infer_type()
            else:
                return self._final_type
        else:
            return self
    
    @classmethod
    def _or_type(self, other):
        return None
    
    def _save(self, ctx, path):
        pass
        #raise SaveNotImplementedError(path, f"{type(self).__name__} doesn't implement !save")
    
class UninitializedSub(DatamijnObject):
    @classmethod
    def make(self, name=None, bases=[], **kwargs):
        raise NotImplementedError()
    
    @classmethod
    def resolve(self, ctx, path):
        raise NotImplementedError()

#class PipedDatamijnObject(DatamijnObject):
#    _pipeable = True
#    @classmethod
#    def parse_left(self, left, ctx, path, index=None):
#        raise NotImplementedError()

class Token(DatamijnObject):
    _size = 0
    def __init__(self, self_=None):
        pass
    
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return self()
    
    def __str__(self):
        return f"<{type(self).__name__}>"
    
    def __repr__(self):
        return f"{self.__class__.__name__}"
    
    def __eq__(self, other):
        if type(self) == type(other):
            return True
        elif type(self) == other:
            return True
        else:
            return False

class Terminator(Token): pass

class Null(DatamijnObject):
    _size = 0
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return None

class Byte(DatamijnObject, bytes):
    _size = 1
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        address = stream.tell()
        read = stream.read(1)
        if len(read) != self._size:
            raise ParseError(path, "Failed to read stream")
        byte = self(read)
        byte._address = address
        byte._size = self._size
        return byte
    
    @classmethod
    def _mul_type(self, other):
        if issubclass(other, int):
            return bytes

class Short(DatamijnObject, bytes):
    _size = 2
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        address = stream.tell()
        read = stream.read(2)[::-1]
        if len(read) != self._size:
            raise ParseError(path, "Failed to read stream")
        short = self(read)
        short._address = address
        short._size = self._size
        return short

class Word(DatamijnObject, bytes):
    _size = 4
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        # FIXME
        read = stream.read(4)[::-1]
        if len(read) != self._size:
            raise ParseError(path, "Failed to read stream")
        return self(read)

class DatamijnInt(DatamijnObject, TraceInt):
    _root_name = "DatamijnInt"

    #def __add__(self, other):
    #    raise "ADD CALLED"
    
    def __repr__(self):
        #return f"{self.__class__.__name__}({int(self)})"
        if self._root_name == self.__class__.__name__:
            return str(int(self))
        else:
            return f"{self.__class__.__name__}({int(self)})"

class HexDatamijnObject(DatamijnInt):
    _root_name = "HexDatamijnObject"
    
    def __repr__(self):
        if self._root_name == self.__class__.__name__:
            return hex(int(self))
        else:
            return f"{self.__class__.__name__}({hex(int(self))})"

class DatamijnBits(DatamijnInt):
    _size = None
    _num_bits = None
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        value = stream.read_bits(self._num_bits)
        return value

class B1(DatamijnInt):
    _root_name = "B1"
    _size = None
    _num_bits = 1
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        value = stream.read_bit()
        return value

def make_bit_type(num_bits):
    return type(f"B{num_bits}", (DatamijnBits,), {"_num_bits": num_bits, "_root_name": f"B{num_bits}"})

class U8(DatamijnInt):
    _root_name = "U8"
    _size = 1
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        data = Byte().parse_stream(stream, ctx, path, **kwargs)
        value = self(ord(data))
        value._trace = Source(self, data)
        return value

class U16(DatamijnInt):
    _root_name = "U16"
    _size = 2
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        data = Short().parse_stream(stream, ctx, path, **kwargs)
        value = self(data[1] | (data[0] << 8))
        value._trace = Source(self, data)
        return value

class U32(DatamijnInt):
    _root_name = "U32"
    _size = 4
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        data = stream.read(4)
        value = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
        return value

class DatamijnString(DatamijnObject, str):
    _root_name = "DatamijnString"

    def __add__(self, other):
        new = DatamijnString(str(self) + str(other))

        # Pointless performance hit atm.
        #new._trace = Source(self.__add__, self, other)

        return new

class Array(DatamijnObject):
    _subs = Subs('parsetype', 'length')
    # _child_type
    # _length
    _force_array_type = None
    _concat = False
    _bytestring = False
    _final_length = False
    
    ARRAY_CLASSES = {
    }
    
    @classmethod
    def resolve(self, ctx, path):
        if type(self._subs.length) == int:
            self._final_length = True
        elif self._subs.length != None:
            self._length = self._subs.length.resolve(ctx, path)
            #if self._length._final:
            #    self._length = self._length.parse_stream(None, None, path)
            #    self._final_length = True
        else:
            self._length = None
        self._parsetype = self._subs.parsetype.resolve(ctx, path)
        
        new_array_type = None
        for elem_types, new_class in self.ARRAY_CLASSES.items():
            new_array_type = None
            cur_type = self
            for elem_type in elem_types:
                if hasattr(cur_type.infer_type(), "_parsetype") \
                  and issubclass(cur_type.infer_type()._parsetype.infer_type(), elem_type):
                    cur_type = cur_type.infer_type()._parsetype
                    new_array_type = new_class
                else:
                    new_array_type = None
            if new_array_type:
                break
    
        if self._force_array_type:
            new_array_type = self._force_array_type
        
        length_name = ""
        if self._length and isinstance(self._length, int):
            length_name = str(self._length)
        elif self._length:
            length_name = self._length.__name__
        
        if new_array_type:
            tail_name = new_array_type.__name__
        else:
            new_array_type = ListArray # !
            tail_name = ""
        
        self._child_type = self._parsetype.infer_type()
        
        name = f"[{length_name}]{self._child_type.__name__}{tail_name}"
        
        new = new_array_type.make(name, parsetype=self._subs.parsetype, _parsetype=self._parsetype, _child_type=self._child_type, length=self._subs.length, _length=self._length, _final_length=self._final_length)
        new._yields = self._parsetype._yields
        return new
        
    
    @classmethod
    def size(self):
        if isinstance(self._length, int):
            return self._length * self._parsetype.infer_type().size()
        else:
            return None
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, strict_read=True, **kwargs):
        contents = []
        if self._final_length:
            length = self._length
        elif self._length != None:
            length = self._length.parse_stream(stream, ctx, path, strict_read=strict_read, **kwargs)
        else:
            length = None
        
        start_address = stream.tell()
        
        if self._length != None and self._parsetype == Byte:
            # Speed optimization for byte arrays!
            print(type(stream))
            return stream.read(length, strict=strict_read)
        
        error = False
        i = 0
        while True:
            item = self._parsetype.parse_stream(stream, ctx, path + [i], index=i, strict_read=strict_read, **kwargs)
            if hasattr(item, '_error') and item._error:
                error = True
            if self._concat and len(contents) \
              and type(contents[-1]) == type(item) \
              and isinstance(item, str):
                contents[-1] += item
            else:
                contents.append(item)
            
            i += 1
            if length != None:
                if i >= length:
                    break
            elif issubclass(self._parsetype, int):
                if contents[-1] == 0:
                    break
            elif isinstance(contents[-1], Terminator):
                if type(contents[-1]) is Terminator:
                    contents.pop()
                break
            #else:
            #    raise ValueError("Improper terminating condition")
        
        size = stream.tell() - start_address

        #if contents and hasattr(contents[0], '_address'):
        #    start_address = contents[0]._address
        
        if self._bytestring or len(contents) and isinstance(contents[0], bytes):
            return b"".join(contents)
        else:
            obj = self(contents)
            obj._address = start_address
            obj._size = size
            obj._path = path
            obj._error = error
            return obj
    
    @classmethod
    def _or_type(self, other):
        if issubclass(other, Array):
            return self._parsetype._or_type(other._parsetype)
        return None
    
    def __or__(self, other):
        if len(self) != len(other):
            raise TypeError(f"Piped arrays must be of matching length ({len(self)} != {len(other)})")
        
        newlist = []
        for item0, item1 in zip(self, other):
            newlist.append(item0 | item1)
        
        newlist = type(self)(newlist)
        
        # XXX :(
        #if len(newlist) > 0:
        #    newlist._type = type(newlist[0])
        
        return newlist
        
    def _save(self, ctx, path):
        for i, elem in enumerate(self):
            elem._save(ctx, path + [i])
            
    def __repr__(self):
        return f"{type(self).__name__}"
    
    def _pretty_repr(self):
        #name = type(self).__name__
        #if name == "Array":
        #    name = ""
        #out = f"{name} [\n"
        out = f"[\n"
        for val in self:
            if isinstance(val, Struct) or isinstance(val, Array):
                valrepr = "\n  ".join(val._pretty_repr().split('\n'))
            else:
                valrepr = repr(val)
            out += f"  {valrepr},\n"
        out += "]"
        
        if len(self) == 0:
            out = out.replace("\n", "")
        return out.strip()

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
            elif isinstance(item, Exception):
                pass
            else:
                string += f"<{repr(item)}>"
        
        return string
    
    def _pretty_repr(self):
        string = str(self).replace('"', '\"')
        return '"' + str(self) + '"'

class ByteString(bytes, Array):
    _concat = True
    _bytestring = True

    def _pretty_repr(self):
        return repr(self)

class Struct(dict, DatamijnObject):
    _lenient = False
    _rich = True
    
    @classmethod
    def resolve(self, ctx=None, path=None, stdlib=None):
        if not ctx: ctx = []
        if not path: path = []
        ctx.append(self)
        
        self._types = {}
        self._contents = {}
        field_counter = 0
        
        if stdlib:
            self._fields.insert(0, (None, stdlib))
        
        for name, field in self._fields:
            if name == None and isinstance(field, type) and issubclass(field, DatamijnObject) and not issubclass(field, Yield):
                type_ = field
                name = field.__name__
                if name[0] not in UPPERCASE + "!":
                    raise ResolveError(path, f"{name}: Type names must start with an uppercase letter.")
                self._types[name] = NestedExprName.make(name, _name=name) # stub the type
                resolved = type_.resolve(ctx, path + [name])
                if resolved._embed:
                    self._types.update(resolved._types)
                else:
                    self._types[name]._replacement = resolved
                    self._types[name] = resolved
            else:
                if not self._lenient and name and isinstance(name, str) and name[0] in UPPERCASE:
                    raise ResolveError(path, f"{name}: Field names must start with a lowercase letter.")
                resolved = field.resolve(ctx, path + [name])
                
                if name in self._contents:
                    raise ResolveError(path, f"Field {name} is defined twice.  Please make sure each name is only used once.")
                #if name and name in self._contents and self._contents[name].infer_type() != resolved.infer_type():
                #    raise ResolveError(path, f"Field {name} is redefined with a different type.\n{full_type_name(self._contents[name].infer_type())} != {full_type_name(resolved.infer_type())}")
                
                if resolved._yields:
                    self._yields = True
                
                if not name or name == "_":
                    name = f"__unnamed_field{field_counter}"
                    field_counter += 1
                
                self._contents[name] = resolved
        
        if self._return:
            self._return = self._return.resolve(ctx, path + ["_return"])
            self._final_type = self._return.infer_type()
        
        ctx.pop()
        
        return self
    
    #@classmethod
    #def size(self):
    #    size = 0
    #    for name, type_ in self._contents:
    #        size += type_.size() or None
    #    
    #    return size
    
    @classmethod
    def parse_stream(self, stream, ctx=None, path=None, index=None, **kwargs):
        if not ctx: ctx = []
        if not path: path = []
        
        #rich = ctx[0]._rich if len(ctx) else self._rich
        #if rich:
        start_address = stream.tell()
        
        error = False
        size = 0
        obj = self()
        ctx.append(obj)
        obj._ctx = ctx
        for name, type_ in self._contents.items():
            passed_path = path[:]
            passed_path.append(name)
            address = stream.tell()
            result = type_.parse_stream(stream, ctx, passed_path, index=index, **kwargs)
            if hasattr(result, '_error') and result._error:
                error = True
            
            result_size = stream.tell() - address
            size += result_size
            #if hasattr(result, '_size') and result._size:
            #    size_extra += result._size - result_size
            if name:
                obj[name] = result
            #elif isinstance(result, Struct) and result._embed:
            #    obj.update(result)
        
        if self._return:
            value = self._return.parse_stream(stream, ctx, path + ["_return"], index=index, **kwargs)
            ctx.pop()
            return value
        else:
            ctx.pop()

            obj._address = start_address
            obj._size = size
            #obj._size_extra = size_extra
            obj._path = path
            obj._error = error
            return obj
    
    def __setitem__(self, key, value):
        if not isinstance(key, tuple):
            super().__setitem__(key, value)
        else:
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
        if not issubclass(other, Struct):
            return None
        if set(n for n, t in self._contents.items() if not n.startswith("_")) != set(n for n, t in other._contents.items() if not n.startswith("_")):
            raise TypeError(f"Piped structs must have matching fields")
        
        # TODO this should return a properly piped type of the result!!!!! XXX
        
        return self
        
    
    def __or__(self, other):
        if not isinstance(other, Struct):
            return NotImplemented
        if set(n for n, t in self._contents.items() if not n.startswith("_")) != set(n for n, t in other._contents.items() if not n.startswith("_")):
            raise TypeError(f"Piped structs must have matching fields")
        
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
        if hasattr(self, 'num'):
            return f"<{name} num {self.num}>"
        elif hasattr(self, 'id'):
            return f"<{name} id {self.id}>"
        else:
            return f"<{name}>"
    
    def _pretty_repr(self):
        name = type(self).__name__
        if name == "Struct":
            name = ""
        out = f"{name} {'{'}\n"
        for name, type_ in self._contents.items():
            if isinstance(name, tuple): continue
            if not name: continue
            if isinstance(self[name], Struct) or isinstance(self[name], Array):
                valrepr = "\n  ".join(self[name]._pretty_repr().split('\n'))
            else:
                valrepr = repr(self[name])
            out += f"  {name}: {valrepr}\n"
        out += "}"
        
        if len(self._contents) == 0:
            out = out.replace("\n", "")
        return out.strip()

class LenientStruct(Struct):
    """
        Doesn't care about field names.  Typically they must start
        with a lowercase letter.
    """
    # TODO rename this.  Can and will be confused with lenient parsing mode
    # which is something else.
    _lenient = True

class Name(DatamijnObject):
    _namestring = "{self._name}"
    _subs = Subs("type")
    #_name
    
    @classmethod
    def resolve(self, ctx, path):
        newtype = self._subs.type.make()
        newtype = newtype.resolve(ctx, path)
        newtype.rename(self._name)
        return newtype

class Function(DatamijnObject):
    _namestring = "{self._name}"
    _subs = Subs('type')
    #_name
    #_arguments
    
    @classmethod
    def resolve(self, ctx, path):
        for argument in self._arguments:
            if argument[0] not in UPPERCASE:
                raise ResolveError(path, 'Function arguments must start with capital letter.')
        return self
    
    @classmethod
    def call(self, ctx, path, arguments):
        if len(self._arguments) != len(arguments):
            raise ResolveError(path, f"Function {self.__name__} takes {len(self._arguments)} argument{'s' if len(arguments)!=1 else ''}, however {len(arguments)} {'was' if len(arguments)==1 else 'were'} provided.")
        ctx.append(dict(zip(self._arguments, arguments)))
        # It is not enough to make() the type here,
        # because its subtypes will be simply copied and resolved
        # once even on further calls.  This is why we make_all.
        newtype = self._subs.type.make(make_all=True)
        newtype = newtype.resolve(ctx, path + ["()"])
        newtype.rename(self._name)
        ctx.pop()
        return newtype
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        raise ParseError(path, f"Attempted to parse using a function {self.__name__}.  Functions must be called.")
        

class Call(DatamijnObject):
    _namestring = "{self._subs.func.__name__}({self._arguments})"
    _subs = Subs('func', 'arguments')
    
    @classmethod
    def resolve(self, ctx, path):
        self._func = self._subs.func.resolve(ctx, path)
        arguments = []
        for i, argument in enumerate(self._subs.arguments):
            arguments.append(argument.resolve(ctx, path+[f"(argument {i})"]))
        
        if not issubclass(self._func, Function):
            raise ResolveError(path, f"Attempting to call non-function {full_type_name(self._func)}")
        
        self._resolved_arguments = arguments
        self._expr = self._func.call(ctx, path, arguments)
        argstring = ", ".join(a.__name__ for a in self._arguments)
        self.__name__ = f"{self._func.__name__}({argstring})"
        self._final_type = self._expr._final_type
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        ctx.append(dict(zip(self._func._arguments, self._resolved_arguments)))
        result = self._expr.parse_stream(stream, ctx, path + ["()"], index=index)
        ctx.pop()
        return result

class ExprName(DatamijnObject):
    _namestring = "{self._name}"
    #_name
    
    @classmethod
    def resolve(self, ctx, path):
        if self._name[0] in UPPERCASE:
            for context in reversed(ctx):
                if type(context) == dict:
                    if self._name in context:
                        return context[self._name]
                else:
                    if self._name in context._types:
                        return context._types[self._name]
            
            raise ResolveError(path, f"Cannot resolve type {self._name}")
        else:
            # This is a reference!
            final_type = None
            if self._name in self._arguments:
                final_type = DatamijnObject # XXX
            for context in reversed(ctx):
                if isinstance(context, dict):
                    if self._name in context:
                        final_type = context[self._name]
                else:
                    if self._name in context._contents:
                        final_type = context._contents[self._name]
                    elif self._name in context._arguments:
                        final_type = DatamijnObject # XXX
                if final_type:
                    break
            
            if final_type == None:
                error_text = f"Cannot resolve name {self._name}"
                if self._name in "b1 b2 b4 u8 u16 u32".split():
                    error_text += f"\nDid you mean {self._name.upper()}?"
                raise ResolveError(path, error_text)
            
            final_type_inferred = final_type.infer_type()
            
            newtype = ExprName.make(None, [], _name=self._name, _final_type=final_type_inferred)
            
            return newtype

    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        for context in reversed(ctx):
            if self._name in context:
                return context[self._name]
        
        raise ParseError(path, f"Cannot resolve name {self._name}")

class NestedExprName(ExprName):
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        newtype = self._replacement
        return newtype.parse_stream(stream, ctx, path, index=index, **kwargs)

class ExprInt(DatamijnInt):
    _root_name = "ExprInt"
    _namestring = "{self._int}"
    #_final = True
    _final_type = DatamijnInt
    #_int
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return DatamijnInt(self._int)


class ExprHex(ExprInt, HexDatamijnObject):
    _root_name = "ExprHex"
    #_final = True
    _final_type = HexDatamijnObject
    #_int

class ExprString(DatamijnObject):
    _final = True
    _final_type = str
    #_string

    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return DatamijnString(self._string)

class ExprOp(DatamijnObject):
    _subs = Subs('left', 'right')
    #_op
    
    @classmethod
    def resolve(self, ctx, path):
        self._left = self._subs.left.resolve(ctx, path + ['(left)'])
        self._right = self._subs.right.resolve(ctx, path + ['(left)'])
        self._final = self._left._final and self._right._final
        
        type_func_name = f'_{self._op.__name__.rstrip("_")}_type'
        
        transformed_type = None
        if hasattr(self._left.infer_type(), type_func_name):
            transformed_type = getattr(self._left.infer_type(), type_func_name)(self._right.infer_type())
        
        # This is a basic sanity check, but it's a bit crazy yet doesn't cover
        # all cases.
        
        def get_all_bases(type):
            bases = set(type.__bases__)
            for base in type.__bases__:
                bases |= get_all_bases(base)
            
            return bases
        
        common_bases = get_all_bases(self._left.infer_type()) & get_all_bases(self._right.infer_type())
        common_bases -= set([object, DatamijnObject])
        
        # TODO check that arrays have matching subtypes
        if self._left.infer_type() != self._right.infer_type() \
            and not common_bases \
            and not transformed_type:
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

class ExprAttr(DatamijnObject):
    _namestring = "{self._subs.left.__name__}.{self._name}"
    _subs = Subs('left')
    #_name
    @classmethod
    def resolve(self, ctx, path):
        self._left = self._subs.left.resolve(ctx, path)
        if not issubclass(self._left.infer_type(), Struct):
            raise ResolveError(path, f"Only structs may be attributed, not {full_type_name(self._left.infer_type())}.")
        
        self._yields = self._left._yields
        self._final_type = dict(self._left.infer_type()._contents)[self._name].infer_type()
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        left = self._left.parse_stream(stream, ctx, path, index=index, **kwargs)
        return left[self._name]

class ExprIndex(DatamijnObject):
    _subs = Subs('left', 'index')
    @classmethod
    def resolve(self, ctx, path):
        self._left = self._subs.left.resolve(ctx, path)
        self._index = self._subs.index.resolve(ctx, path)
        if not issubclass(self._left.infer_type(), Array):
            raise ResolveError(path, f"Only arrays may be indexed, not {full_type_name(self._left.infer_type())}.")
        if not issubclass(self._index.infer_type(), int):
            raise ResolveError(path, f"Only ints may be used for indexing, not {full_type_name(self._index.infer_type())}.")
        
        self._yields = self._left._yields or self._index._yields
        
        self._final_type = self._left.infer_type()._child_type
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        left = self._left.parse_stream(stream, ctx, path, index=index, **kwargs)
        index = self._index.parse_stream(stream, ctx, path, index=index, **kwargs)
        return left[index]

class Return(DatamijnObject):
    _subs = Subs('expr')
    
    @classmethod
    def resolve(self, ctx, path):
        self._expr = self._subs.expr.resolve(ctx, path)
        self._yields = self._expr._yields
        self._final_type = self._expr.infer_type()
        self._final = self._expr._final
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return self._expr.parse_stream(stream, ctx, path, index=index, **kwargs)

class Index(DatamijnInt):
    _root_name = "Index"
    _final_type = DatamijnInt
    
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return index

class Position(DatamijnInt):
    _final_type = DatamijnInt
    
    @classmethod
    def _parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return stream.tell()

class RightSize(DatamijnObject):
    _final_type = int
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        for x in ctx:
            if '_right_size' in x:
                return x['_right_size']

class Pointer(DatamijnObject):
    _namestring = "@{self._subs.addr.__name__} {self._subs.type.__name__}"
    _subs = Subs('type', 'addr')
    
    @classmethod
    def resolve(self, ctx, path):
        self._addr = self._subs.addr.resolve(ctx, path + ["(addr)"])
        if not issubclass(self._addr.infer_type(), int):
            raise ResolveError(path, f"Pointer address must resolve to int.\n{self._addr.__name__} resolves to {full_type_name(self._addr.infer_type())}.\nHINT: This could be a syntax ambiguity.  If you intend to index or attribute in your address expression, make sure to put it in parenthesis!")
        self._type = self._subs.type.resolve(ctx, path)
        
        newtype = self.make(bases=[self._type.infer_type()], _addr=self._addr, _type=self._type, addr=self._subs.addr, type=self._subs.type)
        
        #newtype._final_type = self._type.infer_type()
        newtype._final_type = newtype
        newtype._yields = self._type._yields or self._addr._yields # god forbid
        
        return newtype
    
    @classmethod
    def parse_stream(self, stream, ctx, path, **kwargs):
        rich = ctx[0]._rich
        if rich:
            address = stream.tell()
            try:
                length = self._addr.size()
            except NotImplementedError:
                length = None
    
        address = self._addr.parse_stream(stream, ctx, path + ['(addr)'], **kwargs)
        # XXX handle the bit stuff elsewhere?
        pos = stream.tell()
        pos_bit = stream._bit_number
        stream_byte = stream._byte
        stream.seek(address)
        stream._bit_number = 0
        stream._byte = None
        result = self._type.parse_stream(stream, ctx, path, **kwargs)
        stream.seek(pos)
        stream._bit_number = pos_bit
        stream._byte = stream_byte
        
        #obj = self.__new__(self, result)
        #obj.__init__(result)
        obj = result
        if rich:
            if hasattr(result, '_address'):
                obj._path = result._path
                obj._address = result._address
                obj._size = result._size
            obj._pointer = address
        
        return obj

class PipePointer(Pointer):
    _namestring = "|@({self._addr.__name__})({self._type.__name__})"
    
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

class Yield(DatamijnObject):
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

class MatchResult(DatamijnObject):
    _concat = False
    #_key
    
    def __init__(self, dummy=None):
        pass

class ConcatableMatchResult(DatamijnObject):
    _concat = True

# TODO explain why this is a thing ('cause I forgot)
class MatchTypeMetaclass(type):
    def __getattr__(self, name):
        if name == '_match_types':
            raise AttributeError()
        
        if name in self._match_types:
            return self._match_types[name]
        else:
            raise AttributeError()

class MatchType(DatamijnObject, metaclass=MatchTypeMetaclass):
    _subs = Subs('type')
    _concat_result = False
    @classmethod
    def resolve(self, ctx, path):
        self._type = self._subs.type.resolve(ctx, path)
        self._yields = self._type._yields
        self._final_type = None
        
        ## Pass 1: collect all possible match types
        types = []
        for key, value in self._match.items():
            if isinstance(key, str):
                ctx.append({key: self._type})
            inferred_type = value.resolve(ctx, path + [key])
            if not issubclass(value, Terminator):
                types.append(inferred_type)
        
        if len(types) == 1:
            result_base = types[0]
        else:
            result_base = None
        
        if not self._concat_result:
            result_type = MatchResult
        else:
            result_type = ConcatableMatchResult
        
        if result_base:
            match_result = result_type.make(result_base.__name__, bases=[result_base])
        else:
            match_result = result_type.make(f"{self.__name__}Result", bases=[])
        
        for key, value in self._match.items():
            if isinstance(key, str):
                ctx.append({key: self._type})
            if value == Terminator:
                self._match[key] = value
            else:
                self._match[key] = value.resolve(ctx, path + [key])
                # Whose idea was this atrocity again?  Seriously don't.
                #self._match[key] = value.make(bases=[match_result]).resolve(ctx, path + [key])
            if value._yields:
                self._yields = True
            
            inferred_type = value.infer_type()
            if not issubclass(inferred_type, Terminator):
                pass
                #if not self._final_type:
                #    self._final_type = inferred_type
                
                # XXX we resort to string comparisons because
                # we lack a proper type system
                #if self._final_type.__name__ != inferred_type.__name__:
                #    self._final_type = self
            if isinstance(key, str):
                ctx.pop()
        
        if self._final_type == None:
            self._final_type = match_result
        
        # minor optimization
        self._ranges = {}
        self._default_key = None
        for key, value in self._match.items():
            if isinstance(key, KeyRange):
                self._ranges[key] = value
            elif isinstance(key, DefaultKey):
                self._default_key = key
        
        self._match_types = {v.__name__: v for k, v in self._match.items()
            if isinstance(v, type) and issubclass(v, DatamijnObject)}
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        value = self._type.parse_stream(stream, ctx, path, index=index, **kwargs)
        
        key_value = value
        if isinstance(value, Byte):
            key_value = ord(value)
        elif isinstance(value, int):
            key_value = int(key_value)
        
        if key_value in self._match:
            obj = self._match[key_value].parse_stream(stream, ctx, path + [f"[{key_value}]"], **kwargs)
            #if isinstance(obj, DatamijnObject):
            if obj != None:
                obj._match_value = value
            return obj
        else:
            for range, rangeval in self._ranges.items():
                if range.from_ <= key_value < range.to:
                    obj = rangeval.parse_stream(stream, ctx, path + [f"[{range}]"], **kwargs)
                    obj._match_value = value
                    return obj
            
            if self._default_key != None:
                ctx_extra = {}
                if self._default_key:
                    ctx_extra = {str(self._default_key): value}
                # XXX this makes sense e.g. for pokered.type_effectiveness
                obj = self._match[self._default_key].parse_stream(stream, ctx + [ctx_extra], path + [f"[_]"], **kwargs)
                # FIXME
                #if obj != None and obj._size != None and value._size != None:
                #    obj._address = value._address
                #    obj._size += value._size
                if isinstance(obj, DatamijnObject):
                    obj._match_value = value
                return obj
            else:
                # XXX improve this error
                raise Exception(f"Parsed value {value}, but not present in match.\nPath: {'.'.join(str(x) for x in path)}")

class CharMatchType(MatchType):
    _concat_result = True

class PipeStream(IOWithBits):
    def __init__(self, stream, ctx, type_, path):
        self._path = path
        self._stream = stream
        self._ctx = ctx
        self._type = type_
        
        self._buffer = BytesIOWithBits(b"")
        
        self._byte = None
        self._bit_number = None
        self._pos = 0
        self._free_bytes = 0
        
        if not issubclass(type_.infer_type(), bytes):
            if issubclass(type_, Struct):
                if not type_._yields:
                    raise TypeError(f"Attempting to pipe {full_type_name(type_.infer_type())}, which is a Struct that does not yield.")
            else:
                raise TypeError(f"Attempting to pipe {full_type_name(type_.infer_type())}")
    
    def read(self, num, strict=True):
        assert strict == True
        self._buffer.seek(0, 2) # SEEK_END
        while self._free_bytes < num:
            result = self._type.parse_stream(self._stream, self._ctx, self._path + ["<PipeStream>"], pipebuffer=self._buffer, pipestream=self, strict_read=False) # XXX
            if result != None and not (isinstance(result, Struct) and result._is_empty()):
                if not isinstance(result, bytes):
                    print(repr(result))
                    errormsg = f"Pipe received {type(result)}.  Only bytes may be passed through a pipe."
                    if isinstance(result, Struct):
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
        return self._pos
    
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

class Pipe(DatamijnObject):
    _namestring = "{self._subs.left.__name__}|{self._subs.right.__name__}"
    _subs = Subs('left', 'right')
    @classmethod
    def resolve(self, ctx, path):
        self._left_type = self._subs.left.resolve(ctx, path + ["(left)"])
        self._right_type = self._subs.right.resolve(ctx, path + ["(right)"])
        if not self._left_type._yields \
          and not issubclass(self._left_type.infer_type(), ByteString) \
          and hasattr(self._left_type.infer_type(), "__or__"):
          #and not (issubclass(self._right_type, PipedDatamijnObject) \
          #  and not issubclass(self._right_type, Pipe)):
            expr = ExprOp.make(f"({self._left_type.__name__}|{self._right_type.__name__})",
                left=self._left_type, right=self._right_type, _op=operator.or_)
            return expr.resolve(ctx, path)
        
        self._yields = self._left_type._yields or self._right_type._yields
        self._final_type = self._right_type.infer_type()
        
        #self.__name__ = f"({self._left_type.__name__})|({self._right_type.__name__})"
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        if False: #issubclass(self._right_type, PipedDatamijnObject):
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
            #ctx.append({'_right_size': right_size})
            ctx.append(Struct({'_right_size': right_size}))
            pipe_stream = PipeStream(stream, ctx, self._left_type, path=path)
            result = self._right_type.parse_stream(pipe_stream, ctx, path, **kwargs)
            #if not pipe_stream.empty:
            #    raise ValueError("Unaccounted data remaining in pipe.  TODO this should be suppressable")
            ctx.pop()
            return result

class Inheritance(DatamijnObject):
    _namestring = "{self._subs.left.__name__} {self._subs.right.__name__}"
    _subs = Subs('left', 'right')
    @classmethod
    def resolve(self, ctx, path):
        if issubclass(self._subs.left, Array) and self._subs.right == String:
            newtype = self._subs.left.make()
            newtype._force_array_type = self._subs.right
            newtype = newtype.resolve(ctx, path)
            return newtype
        
        if not issubclass(self._subs.left, Struct):
            raise ResolveError(path, f"""Can only apply inheritance to Structs or from String to Array
Attempted to inherit {self._subs.left.__name__} from {self._subs.right.__name__}""")
        
        newtype = self._subs.left.make(None, bases=[self._subs.right]).resolve(ctx, path)
        
        for field in self._subs.right._inherited_fields:
            if field not in newtype._contents:
                raise ResolveError(path, f"""Inherited Struct must have the necessary inherited fields
`{self._subs.left.__name__}` is mising the field `{field}`
`{self._subs.right.__name__}` needs the following fields: {', '.join(self._subs.right._inherited_fields)}""")
        
        return newtype
        

class ForeignKey(DatamijnObject):
    _subs = Subs('type')
    # field_name
    def __init__(self, key, ctx):
        self._key = key
        self._ctx = ctx
    
    @classmethod
    def resolve(self, ctx, path):
        self._type = self._subs.type.resolve(ctx, path)
        self._yields = self._type._yields
        
        if not isinstance(self._field_name, tuple):
            self._field_name = (self._field_name,)
        
        if self._field_name[0][0] in UPPERCASE:
            raise ResolveError(path, "Field name must begin with lowercase letter")
        
        # TODO flattern field name
        
        self.__name__ = f"{self._type.__name__} -> {self._field_name[-1]}"
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        key = self._type.parse_stream(stream, ctx, path, **kwargs)
        
        if key == None:
            return None
        
        return self(key, ctx[0])
    
    @property
    def _object(self):
        foreign = self._ctx
        key = self._field_name
        try:
            while isinstance(key, tuple) and len(key) == 2:
                foreign = foreign[key[0]]
                key = key[1]
            while isinstance(key, tuple) and len(key) == 1:
                key = key[0]
            foreign = foreign[key]
                
            obj = foreign[self._key]
        except (IndexError, KeyError):
            raise ForeignKeyError(f"Indexing foreign list `{self._field_name}[{self._key}]` failed")
        
        return obj
    
    def __getattr__(self, attr):
        if attr in ("_address", "_pointer", "_error"):
            try:
                return getattr(self._object, attr)
            except ForeignKeyError:
                raise AttributeError()
        
        return getattr(self._object, attr)
    
    def __getitem__(self, item):
        return self._object[item]
    
    def __eq__(self, other):
        if isinstance(other, ForeignKey):
            return self._object == other._object
        else:
            return False
        
    def __repr__(self):
        return f"-> {self._field_name[-1]}({repr(self._key)}, {repr(self._field_name)})"
    
    def __str__(self):
        return str(self._object)

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

# TODO broken
class If(DatamijnObject):
    # _expr
    # _true_struct
    # _false_struct
    @classmethod
    def resolve(self, ctx, path):
        self._expr = self._expr.resolve(ctx, path)
        self._true_struct = self._true_struct.resolve(ctx, path)
        self._true_struct._embed = True
        if self._false_struct:
            self._false_struct = self._false_struct.resolve(ctx, path)
            self._false_struct._embed = True
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        result = self._expr.parse_stream(stream, ctx, path, index=index, **kwargs)
        
        if result:
            return self._true_struct.parse_stream(stream, ctx, path, index=index, **kwargs)
        else:
            if self._false_struct:
                return self._false_struct.parse_stream(stream, ctx, path, index=index, **kwargs)
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
        path = path[:-1] # last element is __unnamed_field
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
        print(foreign)

Array.ARRAY_CLASSES.update({
        (Byte,):            ByteString,
        (str,):             String,
        (ExprString,):      String,
        (ConcatableMatchResult,):   String,
})
