OPERATIONS = "add sub mul floordiv mod".split()

class Source():
    def __init__(self, function, *params):
        self.function = function
        self.params = params
        if len(params) == 1:
            self.param = params[0]
    
    def __str__(self):
        return f"{self.function.__name__} " + " ".join(str(x) for x in self.params)

class TraceInt(int):
    def __str__(self):
        if hasattr(self, "_source"):
            return f"{int(self)} ← (" + str(self._source) + ")"
        else:
            return str(int(self))

def make_method(int_func):
    def method(self, other):
        result = int_func(int(self), other)
        if result == NotImplemented:
            return NotImplemented
        
        newobj = type(self).__new__(type(self), result)

        newobj._trace = Source(int_func, self, other)

        return newobj
        
    return method

for operation in OPERATIONS:
    method_name = f"__{operation}__"
    int_func = getattr(int, method_name)
    func = make_method(int_func)
    setattr(TraceInt, method_name, func)

# Tiny tests
def test():
    x = TraceInt(5) + TraceInt(10)
    assert x == 15
    assert x._trace.params[0] == 5
    assert x._trace.params[1] == 10

    y = x * TraceInt(2)
    assert y == 30
    assert y._trace.params[0] == 15
    assert y._trace.params[0]._trace.params[0] == 5

    return True

test()
