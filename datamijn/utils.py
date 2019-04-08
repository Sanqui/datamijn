

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

class DatamijnPathError(Exception):
    def __init__(self, path, message):
        pathstr = '.'.join(str(x) for x in path)
        if not pathstr:
            pathstr = "(root)"
        message = f"{message}\nPath: {pathstr}"
    
        super().__init__(message)

class ResolveError(DatamijnPathError): pass

class ParseError(DatamijnPathError): pass
