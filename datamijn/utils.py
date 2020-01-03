
UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

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

def full_type_name(type):
    IGNORE_BASES = (object, )
    name = type.__name__
    basenames = ", ".join(base.__name__ for base in type.__bases__ if base not in IGNORE_BASES)
    if basenames:
        name += f" ({basenames})"
    
    return name

def parse_symfile(f):
    symbols = {}
    for line in f.readlines():
        line = line.split(";")[0]
        if not line.strip(): continue
        addr, label = line.strip().split(' ')
        bank, offset = addr.split(':')
        bank, offset = int(bank, 16), int(offset, 16)
        if offset < 0x8000:
            addr = bank*0x4000 + offset % 0x4000
            symbols[label] = addr
    return symbols

class DatamijnError(Exception): pass

class ForeignKeyError(DatamijnError): pass

class DatamijnPathError(DatamijnError):
    def __init__(self, path, message):
        pathstr = '.'.join(str(x) for x in path)
        if not pathstr:
            pathstr = "(root)"
        message = f"{message}\nPath: {pathstr}"
    
        super().__init__(message)

class MakeError(DatamijnError): pass

class ResolveError(DatamijnPathError): pass

class ParseError(DatamijnPathError): pass

class ReadError(DatamijnError): pass

class SaveNotImplementedError(DatamijnPathError): pass
