#!/usr/bin/python3

# TODO study
# https://docs.python.org/3/library/collections.abc.html#module-collections.abc
# https://docs.python.org/3/library/numbers.html#module-numbers

import sys
import os.path
import math
import operator
from pathlib import Path
from io import BytesIO, BufferedIOBase
from pprint import pprint
import array as pyarray

from lark import Lark, Transformer
from lark.tree import Tree
import oyaml as yaml
import png

UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

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
    def get_final_type(self):
        if self._final_type != None and self._final_type != self:
            return self._final_type.get_final_type()
        else:
            return self
    
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

class Tile(Primitive):
    width = 8
    height = 8
    depth = 2
    
    @classmethod
    def size(self):
        return (self.depth*self.width*self.height)//8
    
    def __init__(self, tile):
        self.tile = tile
    
    def _open_with_path(self, ctx, path):
        output_dir = getattr(ctx[0], "_output_dir", None)
        if not output_dir:
            output_dir = ctx[0]._filepath + "/datamijn_out/"
        output_dir = Path(output_dir)
        filepath = Path("/".join(str(x) for x in path[:-1]))
        filename = filepath / f"{path[-1]}.png"
        full_filepath = output_dir / filepath
        full_filename = output_dir / filename
        os.makedirs(full_filepath, exist_ok=True)
        return filename, open(full_filename, 'wb')

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

class PlanarTile(Tile):
    width = 8
    height = 8
    depth = 2
    invert = False
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        #assert self.width == 8
        tile_data = stream.read(self.depth*self.width*self.height//8)
        tile = pyarray.array("B", [0]*8*self.width)
        i = 0
        for y in range(self.height):
            for d in range(self.depth):
                layer = bits(tile_data[i])
                i += 1
                for x in range(8):
                    tile[y*self.width + 7-x] |= layer[x] << d
            #if self.invert:
            #    line = [x ^ ((1 << self.depth) - 1) for x in line]
        return self(tile)
    
    def _save(self, ctx, path):
        self._filename, f = self._open_with_path(ctx, path)
        w = png.Writer(self.width, self.height, greyscale=True, bitdepth=self.depth)
        w.write_array(f, self.tile)
        f.close()

class PlanarCompositeTile(PlanarTile):
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        #assert self.width == 8
        tile_data = stream.read(self.depth*self.width*self.height//8)
        tile = pyarray.array("B", [0]*8*self.width)
        i = 0
        for d in range(self.depth):
            for line in range(self.height):
                layer = bits(tile_data[i])
                i += 1
                for x in range(8):
                    tile[line*self.width + 7-x] |= layer[x] << d
        return self(tile)
    
    def _save(self, ctx, path):
        self._filename, f = self._open_with_path(ctx, path)
        w = png.Writer(self.width, self.height, greyscale=True, bitdepth=self.depth)
        w.write_array(f, self.tile)
        f.close()

class Tile1BPP(PlanarTile):
    depth = 1

class NESTile(PlanarCompositeTile):
    depth = 2

class GBTile(PlanarTile):
    depth = 2
    invert = False

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
            raise Exception(f"Failed to read stream\nPath: {'.'.join(str(x) for x in path)}")
        return self(read)

class Short(Primitive, bytes):
    _size = 2
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        read = stream.read(2)[::-1]
        if len(read) != self._size:
            raise Exception(f"Failed to read stream\nPath: {'.'.join(str(x) for x in path)}")
        return self(read)

class Word(Primitive, bytes):
    _size = 4
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        read = stream.read(4)[::-1]
        if len(read) != self._size:
            raise Exception(f"Failed to read stream\nPath: {'.'.join(str(x) for x in path)}")
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

class Array(list, Primitive):
    # _type
    # _length
    _concat = False
    _bytestring = False
    @classmethod
    def resolve(self, ctx, path):
        ARRAY_CLASSES = {
            (Byte,):            ByteString,
            (CharMatchType,):   String,
            (Tile,):            Tileset,
            (Tileset, Tile):    Tileset,
            (Color,):           Palette
        }
        if self._length != None and not isinstance(self._length, int):
            self._length = self._length.resolve(ctx, path)
            if self._length._final:
                self._length = self._length.parse_stream(None, None, path)
        self._type = self._type.resolve(ctx, path)
        
        for elem_types, new_class in ARRAY_CLASSES.items():
            match = False
            cur_type = self
            for elem_type in elem_types:
                if issubclass(cur_type.get_final_type()._type.get_final_type(), elem_type):
                    cur_type = cur_type._type
                    match = True
                else:
                    match = False
            
            if match:
                return new_class.new(f"{self._type.__name__}{new_class.__name__}[{self._length}]", _type=self._type, _length=self._length)
        
        self.__name__ = f"{self._type.__name__}[{self._length if isinstance(self._length, int) else ''}]"
        return self
    
    @classmethod
    def size(self):
        if isinstance(self._length, int):
            return self._length * self._type.get_final_type().size()
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
        if issubclass(self._type, Container) and self._type._return != None and len(contents) > 0:
            self._type = type(contents[0])
        
        if self._bytestring or len(contents) and isinstance(contents[0], bytes):
            return b"".join(contents)
        else:
            return self(contents)
    
    def __add__(self, other):
        if not isinstance(other, Array):
            return NotImplemented
        # XXX well whadd'ya think, I'm matching names...
        #if self._type.get_final_type().__name__ != other._type.get_final_type().__name__:
        #    raise TypeError(f"Added arrays must be of matching subtype ({self._type.get_final_type().__name__} != {other._type.get_final_type().__name__})")

        # just pray
        
        return type(self)(list(self) + list(other))
    
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
    
class String(Array):
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

class ByteString(Array):
    _concat = True
    _bytestring = True
    

class Tileset(Array):
    def _save(self, ctx, path):
        palette = getattr(self, "_palette", None)
        if issubclass(self._type, Tile):
            # XXX maybe remove this
            for i, elem in enumerate(self):
                elem._save(ctx, path + [i])
            '''self._filename, f = self._type._open_with_path(self, ctx, path)
            width = 8
            height = len(self) * 8
            w = png.Writer(width, height,
                greyscale=True, bitdepth=self._type.depth)
            
            pic = pyarray.array("B", [])
            for y in range(height):
                for x in range(width):
                    tileno = ((y//8) * (width//8)) + x//8
                    if tileno < len(self):
                        pic.append(self[tileno].tile[(y%8) * 8 + x%8])
                    else:
                        pic.append(0)
            w.write_array(f, pic)
            f.close()'''
        elif issubclass(self._type, Tileset):
            self._filename, f = self._type._type._open_with_path(self, ctx, path)
            width = self._type._type.width*len(self[0])
            height = self._type._type.height*len(self)
            if not palette:
                w = png.Writer(width, height,
                    greyscale=True, bitdepth=self._type._type.depth)
            else:
                w = png.Writer(width, height,
                    greyscale=False, palette=palette.eightbit(), bitdepth=self._type._type.depth)
            
            pic = pyarray.array("B", [])
            for y in range(height):
                for x in range(width):
                    pic.append(self[y//8][x//8].tile[(y%8) * 8 + x%8])
            w.write_array(f, pic)
            f.close()
        else:
            raise NotImplementedError()
    
    def __or__(self, other):
        if isinstance(other, Palette):
            image = Image(self)
            image._type = self._type
            image._palette = other
            return image
        else:
            return NotImplemented
    
    def __repr__(self):
        return f"<{type(self).__name__}>"

class Image(Tileset):
    pass

class Palette(Array, PipedPrimitive):
    def eightbit(self):
        colors = []
        for color in self:
            mul = (255/color.max)
            colors.append((int(color.r * mul), int(color.g * mul), int(color.b * mul)))
        
        return colors
    
    def __repr__(self):
        return f"<{type(self).__name__}>"

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
                raise Exception(f"{name}: Type names must start with an uppercase letter.")
            resolved = type_.resolve(ctx + [new_types], path + [name])
            if resolved._embed:
                new_types.update(resolved._types)
            else:
                self._types[name] = resolved
        
        self._types.update(new_types)
        
        contents = []
        
        for name, type_ in self._contents:
            if name and isinstance(name, str) and name[0] in UPPERCASE:
                raise Exception(f"{name}: Field names must start with a lowercase letter.")
            contents.append((name, type_.resolve(ctx, path + [name])))
        
        self._contents = contents
        
        if self._return:
            self._return = self._return.resolve(ctx, path + ["_return"])
        
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
            
            context = ".".join(str(x) for x in path)
            raise NameError(f"Cannot resolve type {self._name}, path: {context}")
        else:
            return self

    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        for context in reversed(ctx):
            if self._name in context:
                return context[self._name]
        
        pathstr = ".".join(str(x) for x in path)
        raise NameError(f"Cannot resolve name {self._name}, path: {pathstr}")

class ExprNum(Primitive):
    _final = True
    #_num
    
    @classmethod
    def resolve(self, ctx, path):
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return self._num

class Expr(Primitive):
    #_left
    #_right
    #_op
    
    @classmethod
    def resolve(self, ctx, path):
        self._left = self._left.resolve(ctx, path)
        self._right = self._right.resolve(ctx, path)
        self._final = self._left._final and self._right._final
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        left = self._left.parse_stream(stream, ctx, path, index=index, **kwargs)
        right = self._right.parse_stream(stream, ctx, path, index=index, **kwargs)
        return self._op(left, right)

class Return(Primitive):
    #_expr
    
    @classmethod
    def resolve(self, ctx, path):
        self._expr = self._expr.resolve(ctx, path)
        self._final = self._expr._final
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return self._expr.parse_stream(stream, ctx, path, index=index, **kwargs)

class Index(Primitive):
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return index

class Position(Primitive):
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        return stream.tell()

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

# XXX this doesn't work as a class type - OK?
class Pointer(Primitive):
    def __init__(self, inner, address_expr):
        self.inner = inner
        self.address_expr = address_expr
    
    def resolve(self, ctx, path):
        self.inner = self.inner.resolve(ctx, path)
        return self
    
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        address = eval_with_ctx(self.address_expr, ctx)
        pos = stream.tell()
        stream.seek(address)
        obj = self.inner.parse_stream(stream, ctx, path, **kwargs)
        stream.seek(pos)
        return obj

class PipePointer(Pointer):
    def parse_stream(self, stream, ctx, path, index=None, pipebuffer=None, **kwargs):
        address = eval_with_ctx(self.address_expr, ctx)
        pos = pipebuffer.tell()
        if address < 0:
            pipebuffer.seek(address, 2)
        else:
            pipebuffer.seek(address)
        obj = self.inner.parse_stream(pipebuffer, ctx, path, **kwargs)
        pipebuffer.seek(pos)
        return obj

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
        for key, value in self._match.items():
            self._match[key] = value.resolve(ctx, path + [key])
        
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
    def get_final_type(self):
        final_type = None
        for type_ in self._match.values():
            if final_type == None:
                final_type = type_
            if type_ != final_type:
                return self
        return final_type
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        value = self._type.parse_stream(stream, ctx, path, index=index, **kwargs)
        
        if value in self._match:
            return self._match[value].parse_stream(stream, ctx, path + [f"[{value}]"], **kwargs)
        else:
            for range, rangeval in self._ranges.items():
                if range.from_ <= value < range.to:
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
        self._final_type = self._right_type
        
        self.__name__ = f"{self._left_type.__name__}|{self._right_type.__name__}"
        
        return self
    
    @classmethod
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        if issubclass(self._right_type, PipedPrimitive):
            ctx = []
            left = self._left_type.parse_stream(stream, ctx, path, index=index, **kwargs)
            result = self._right_type.parse_left(left, ctx, path)
            return result
        else:
            ctx.append({'_right': self._right_type})
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
    def __init__(self, field_name):
        self._field_name = field_name
    
    def resolve(self, ctx, path):
        return self
    
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        foreign = ctx[-1][self._field_name]
        foreign._save(ctx, path + [self._field_name])

class DebugField(Field):
    def __init__(self, field_name):
        self._field_name = field_name
    
    def resolve(self, ctx, path):
        return self
    
    def parse_stream(self, stream, ctx, path, index=None, **kwargs):
        foreign = ctx[-1][self._field_name]
        print(f"{self._field_name} is <{type(foreign).__name__}>: {repr(foreign)}")

class Color(PipedPrimitive):
    @property
    def hex(self):
        raise NotImplementedError()

class RGBColor(Color):
    def __init__(self, r, g, b, max):
        self.r = r
        self.g = g
        self.b = b
        self.max = max
    
    @classmethod
    def parse_left(self, container, ctx, path, index=None):
        return self(container.r, container.g, container.b, container._max)
    
    @property
    def hex(self):
        mul = (255/self.max)
        return "#{:02x}{:02x}{:02x}".format(int(self.r * mul), int(self.g * mul), int(self.b * mul))
    
    def __repr__(self):
        return f"RGBColor({self.r}, {self.g}, {self.b}, max={self.max})"
    

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
        self.ifcounter = 0
    
    def string(self, token):
        return token[0][1:-1]
    
    def eval(self, token):
        return eval(token[0])
    
    def stringtype(self, token):
        return StringType(token[0])
    
    def ctx_expr_par(self, token):
        expr = token[0][2:-1]
        
        return expr
    
    def ctx_name(self, token):
        return token[0].value
    
    def match_key_int(self, tree):
        return int(tree[0])
    
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
    
    def container(self, tree):
        struct = []
        types = {}
        return_ = None
        
        if len(tree) and isinstance(tree[-1], type) and issubclass(tree[-1], Return):
            return_ = tree.pop()
        
        for field in tree:
            if isinstance(field, type) and issubclass(field, Return):
                raise SyntaxError("Return must be last in container") # TODO nicer error
            if isinstance(field, type) and issubclass(field, Primitive):
                types[field.__name__] = field
            elif isinstance(field, Field):
                struct.append((None, field))
            elif type(field) == tuple and len(field) == 2:
                struct.append(field)
            else:
                print(tree)
                raise RuntimeError(f"Internal error: unknown container field {field}")
        
        return Container.new("Container", _contents=struct, _types=types, _return=return_)
    
    def type_pipe(self, tree):
        left_type, right_type = tree
        return Pipe.new(f"{left_type.__name__}|{right_type.__name__}",
            _left_type=left_type, _right_type=right_type)
    
    def expr_infix(self, tree):
        OPERATIONS = {
            "+": operator.add,
            "-": operator.sub,
            "*": operator.mul,
            "/": operator.floordiv
        }
        left, sign, right = tree
        return Expr.new(f"({sign} {left.__name__} {right.__name__})",
            _left=left, _right=right, _op=OPERATIONS[sign])
    
    def expr_bracket(self, tree):
        return tree[0]
    
    def type(self, tree):
        return tree[0]
    
    def type_foreign_key(self, tree):
        type_, field_name = tree
        return ForeignKey.new(f"{type_.__name__}ForeignKey",
            _type=type_, _field_name=field_name)
    
    def type_equ(self, tree):
        value = tree[0]
        return Computed.new("Computed", _expr=value)
    
    def type_yield(self, tree):
        type = tree[0]
        return Yield.new("Yield", _type=type)
    
    def type_expr(self, tree):
        print(tree)
        
        return None
    
    def type_match(self, tree):
        type = tree[0]
        match = tree[1]
        return MatchType.new(f"{type.__name__}Match", _type=type, _match=match)
        
    def type_char_match(self, tree):
        type = tree[0]
        match = tree[1]
        return CharMatchType.new(f"{type.__name__}Match", _type=type, _match=match)
    
    def field_name(self, f):
        return str(f[0])
    
    def field_name_dot(self, f):
        return (f[0], f[1])
    
    def field_name_array(self, f):
        return (ForeignListAssignment(f[0]), f[1])
    
    def field_name_underscore(self, f):
        return None
    
    def equ_field(self, f):
        name = f[0]
        value = f[1]
        
        return (name, Computed.new(name, _expr=value))
    
    def return_field(self, f):
        expr = f[0]
        
        return Return.new("Return", _expr=expr)
    
    def if_field(self, f):
        computed = Computed.new("IfCondition", _expr=f[0][4:])
        true_container = f[1]
        false_container = f[2] if len(f) == 3 else []
        
        return (None, If.new("If", _computed=computed, _true_container=true_container, _false_container=false_container))
    
    def assert_field(self, f):
        cond = f[0][8:]
        
        raise NotImplementedError()
    
    def save_field(self, f):
        field_name = f[0]
        
        return SaveField(field_name)
    
    def debug_field(self, f):
        field_name = f[0]
        
        return DebugField(field_name)
    
    def yield_field(self, f):
        type = f[0]
        
        return (None, Yield.new("Yield", _type=type))
    
    def expr_name(self, f):
        name = f[0]
        if name in primitive_types:
            return primitive_types[name]
        else:
            return ExprName.new(f"{name}", _name=name)
    
    def expr_num(self, f):
        num = eval(f[0])
        return ExprNum.new(f"{num}", _num=num)
    
    def type_typedef(self, f):
        return f[0]
    
    def type_container(self, f):
        return f[0]
    
    def type_count(self, f):
        count_tree, type_ = f
        if count_tree.children:
            count = count_tree.children[0]
        else:
            count = None
        return Array.new(f"{type_.__name__}[]", _type=type_, _length=count)
    
    def instance_field(self, f):
        name = f[0]
        params = f[1]
        type_ = f[2]
        
        field = type_
        for param in params.children:
            if param.data == "pointer":
                field = Pointer(field, param.children[0][1:])
            elif param.data == "pipepointer":
                field = PipePointer(field, param.children[0][2:])
            else:
                raise ValueError(f"Unknown param type: {param.data}")
        
        return (name, field)
    
    def typedef_field(self, f):
        return f[0]
    
    def typedef(self, f):
        name = f[0].value
        type_ = f[1]
        
        return type(name, (type_,), {})
    
    def typedefvoid(self, f):
        name = f[0].value
        
        return type(name, (VoidType,), {})
    
    def import_(self, token):
        path = token[0] + ".dm"
        if self.path:
            path = self.path + "/" + path
        
        return parse_definition(open(path), name=f"!imported_{token[0]}", embed=True)
        
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

def parse(definition, data, output_dir=None):
    stdlib = parse_definition(open(os.path.dirname(__file__)+"/stdlib.dm").read(), embed=True)
    struct = parse_definition(definition, stdlib=stdlib)
    struct._output_dir = output_dir
    
    start = struct
    
    if type(data) == bytes:
        type_ = BytesIO
    else:
        type_ = type(data)
    
    data = type(f"{type_.__name__}WithBits", (IOWithBits, type_), {})(data)
    
    result = start.parse_stream(data)

    result._structs = struct
    return result

if __name__ == "__main__":
    from sys import argv

    STRUCTF = argv[1]
    FILEF = argv[2]
    
    result = parse(open(STRUCTF), open(FILEF, "rb"))
    
    print(result._pretty_repr())
    #print(yaml.dump(result._python_value()))
    #print(yaml.dump(result))
