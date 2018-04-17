#!/usr/bin/python3
import sys
import os.path

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

class AttrDict(dict):
    def __getattr__(self, attr):
        return self[attr]

# TODO replace this with actual enums somehow?
class Token(str):
    def __repr__(self):
        return f"Token({self})"

class EnumElement():
    def __init__(self, intvalue, value):
        self.intvalue = intvalue
        self.value = value
    
    def __add__(self, other):
        if type(self.value) == str and type(other) == EnumElement and type(other.value) == str:
            return self.value + other.value
        elif type(self.value) == str and type(other) == str:
            return self.value + other
        else:
            return NotImplemented
    
    def __radd__(self, other):
        if type(self.value) == str and type(other) == EnumElement and type(other.value) == str:
            return other.value + self.value
        elif type(self.value) == str and type(other) == str:
            return other + self.value
        else:
            return NotImplemented
    
    def __repr__(self):
        return f"EnumElement({self.intvalue}, {repr(self.value)})"
    
    def __eq__(self, other):
        #if isinstance(other, EnumElement):
        #    return self.intvalue == other.intvalue and self.value == other.value
        #else:
        if isinstance(other, int):
            return self.intvalue == other
        else:
            return self.value == other

# XXX killing writing here
class TypedEnum(Enum):
    def __init__(self, subcon, mapping):
        super(Enum, self).__init__(subcon)
        #for enum in merge:
        #    for enumentry in enum:
        #        mapping[enumentry.name] = enumentry.value
        self.charmapping = {k:EnumElement(v,k) for k,v in mapping.items() if type(k)==str}
        self.tokenmapping = {k:EnumElement(v,k) for k,v in mapping.items() if type(k)==Token and not k == "_end"}
        self.decmapping = {v:EnumElement(v,k) for k,v in mapping.items() if type(k)==str}
        self.decmapping.update({v:EnumElement(v,k) for k,v in mapping.items() if type(k)==Token and not k == "_end"})
        #self.ksymapping = {v:k for k,v in mapping.items()}
        
        if "_end" in mapping:
            self._end = mapping['_end']
        else:
            self._end = None
    
    def __getattr__(self, name):
        if name in self.tokenmapping:
            return self.tokenmapping[name]
        raise AttributeError
    
    def __getitem__(self, name):
        if name in self.charmapping:
            return self.charmapping[name]
        raise KeyError

class JoiningArray(Array):
    def __init__(self, count, subcon, discard=False):
        super(Array, self).__init__(subcon)
        self.count = count
        self.discard = discard
        self.predicate = None
        
    def _parse(self, stream, context, path):
        count = self.count
        predicate = self.predicate
        if count != None:
            if callable(count):
                count = count(context)
            if not 0 <= count:
                raise RangeError("invalid count %s" % (count,))
        obj = ListContainer()
        last_element = None
        include_last = True
        i = 0
        while True:
            context._index = i
            e = self.subcon._parsereport(stream, context, path)
            # XXX this should be elsewhere ?
            try:
                if type(last_element) == EnumElement or type(e) == EnumElement:
                    last_element += e
                else:
                    raise TypeError
            except TypeError:
                if last_element != None:
                    obj.append(last_element)
                last_element = e
            i += 1
            if i == count: break
            if predicate != None:
                end, include_last = predicate(last_element, obj, path)
                if end:
                    break
        if include_last:
            obj.append(last_element)
        return obj
        
class JoiningTerminatedArray(JoiningArray):
    def __init__(self, predicate, subcon, discard=False):
        super(Array, self).__init__(subcon)
        self.predicate = predicate
        self.discard = discard
        self.count = None

    def _sizeof(self, context, path):
        raise SizeofError("cannot calculate size, amount depends on actual data")

class WithPositionInContext(Subconstruct):
    def _parse(self, stream, context, path):
        context['_pos'] = stream.tell()
        # propagate _index
        c = context
        while '_index' not in c and hasattr(c, '_'):
            c = c_
        if '_index' in c:
            context['_index'] = c['_index']
        
        return self.subcon._parsereport(stream, context, path)

# Monkeypatch Construct
container___eq___old = Container.__eq__
def container___eq__(self, other):
    if "_val" in self:
        return self._val == other
    else:
        return container___eq___old(self, other)
Container.__eq__ = container___eq__

container___str___old = Container.__str__
def container___str__(self):
    if "_val" in self:
        return str(self._val)
    else:
        return container___str___old(self)
Container.__str__ = container___str__

class TreeToStruct(Transformer):
    def __init__(self, structs_by_name, path):
        self.structs_by_name = structs_by_name
        self.path = path
        self.enum_last = -1
        # XXX yes this is sadly an in-memory dupe
        self._enum = {}
        self.ifcounter = 0
    
    def _eval_ctx(self, expr):
        return lambda ctx: eval(expr, {**self.structs_by_name, **ctx})
    
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
        name = token[0]
        if isinstance(name, Construct):
            return name
        elif name in CONSTRUCT_ALIASES:
            return CONSTRUCT_ALIASES[name]
        elif name in "u1 u2 u3 u4 u5 u6 u7".split():
            return BitsInteger(int(name[1]))
        else:
            name = str(name)
            def func_type():
                if name not in self.structs_by_name:
                    raise NameError(f"Type {name} not defined in this context")
                return self.structs_by_name[name]
            return LazyBound(func_type)
    
    def typedef(self, tree):
        struct = []
        bitstruct = []
        
        flat_tree = []
        for field in tree:
            if isinstance(field, list):
                flat_tree += field
            else:
                flat_tree.append(field)
        
        for field in flat_tree:
            f = field
            while hasattr(f, 'subcon'):
                f = f.subcon
            if isinstance(f, BitsInteger):
                bitstruct.append(field)
            else:
                struct.append(field)
        if struct and bitstruct:
            raise ValueError("Cannot mix bit and byte fields within struct")
        if struct:
            return Struct(*struct)
        elif bitstruct:
            return BitsSwapped(BitStruct(*bitstruct))
        else:
            return Struct()
    
    def type_enum(self, tree):
        return TypedEnum(tree[0], tree[1])
    
    def equ_field(self, f):
        name = f[0].value
        value = f[1]
        
        return name / WithPositionInContext(Computed(value))
    
    def if_field(self, f):
        cond = self._eval_ctx(f[0][4:])
        # simulate an embedded if
        fields = []
        ifname = f"__if_{self.ifcounter}"
        fields.append(ifname / WithPositionInContext(Computed(cond)))
        assert type(f[1]) == Struct
        for field in f[1].subcons:
            name = field.name
            fields.append(name / If(self._eval_ctx(ifname), field))
        self.ifcounter += 1
        print(fields)
        return fields
    
    def field(self, f):
        name = f[0].value
        params = f[1]
        array = False
        count = None
        pointer = None
        for param in params.children:
            if param.data == "count":
                array = True
                if param.children:
                    count = param.children[0]
            elif param.data == "pointer":
                pointer = param.children[0]
            else:
                raise ValueError(f"Unknown param type: {param.data}")
        type_ = f[2]
        if array:
            if count:
                type_ = JoiningArray(count, type_)
            else:
                def predicate(obj, lst, ctx):
                    if hasattr(type_.subcon, 'subconfunc'):
                        t = type_.subcon.subconfunc()
                    else:
                        t = type_.subcon
                    if hasattr(t, "_end"):
                        #print("has _end", t._end, type(t._end), obj, type(obj))
                        include_last = True
                        if type(obj) == EnumElement and type(obj.value) == Token:
                            include_last = not obj.value.startswith("_")
                        end = t._end
                        if hasattr(end, "__iter__"):
                            if obj in end:
                                return True, include_last
                        else:
                            if obj == end:
                                return True, include_last
                    elif not obj:
                        return True, False
                    return False, False
                type_ = JoiningTerminatedArray(predicate, type_)
        
        if pointer != None:
            field = name / Pointer(pointer, type_)
        else:
            field = name / type_
        
        return field
    
    def import_(self, token):
        path = token[0] + ".dm"
        if self.path:
            path = self.path + "/" + path
        
        return parse_definition(open(path))
    
    def start(self, structs):
        flat_structs = []
        for struct in structs:
            if type(struct) == list:
                flat_structs += struct
            elif struct.name == None:
                flat_structs += struct.subcons
            else:
                flat_structs.append(struct)
                
        self.structs_by_name = {s.name: s for s in flat_structs}
        
        result = Struct(*flat_structs)
        return result
        
grammar = open(sys.path[0]+"/grammar.g").read()

def container_representer(dumper, data):
    if "_val" in data:
        return dumper.represent_data(data._val)
    else:
        data = dict({k:v for k,v in data.items() if not k.startswith("_")})
        return dumper.represent_data(data)
yaml.add_representer(Container, container_representer)
def list_container_representer(dumper, data):
    return dumper.represent_data(list(data))
yaml.add_representer(ListContainer, list_container_representer)
# TODO improve
def enum_integer_representer(dumper, data):
    return dumper.represent_data(int(data))
yaml.add_representer(EnumInteger, enum_integer_representer)
def enum_element_representer(dumper, data):
    return dumper.represent_data(str(data.value))
yaml.add_representer(EnumElement, enum_element_representer)
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
    
    return struct

def parse(definition, data):
    struct = parse_definition(definition)
    if hasattr(struct, "_start"):
        start = struct._start
    else:
        start = struct
    
    if type(data) != bytes:
        result = start.parse_stream(data)
    else:
        result = start.parse(data)

    result._structs = struct
    return result

if __name__ == "__main__":
    from sys import argv

    STRUCTF = argv[1]
    FILEF = argv[2]
    
    result = parse(open(STRUCTF), open(FILEF, "rb"))
    #print(result)
    print(yaml.dump(result, sort_keys=False))
