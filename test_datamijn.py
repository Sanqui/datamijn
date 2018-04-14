import pytest

import datamijn

from codecs import decode
def b(string):
    return decode(string, 'hex')

@pytest.mark.parametrize("type,data,value", [
    ("u8",  b('01'), 1),
    ("u16", b('0102'), 0x0201),
    ("u32", b('01020304'), 0x04030201),
])
def test_basic_type(type, data, value):
    dm = f"value {type}"
    result = datamijn.parse(dm, data)
    assert result.value == value

def test_typedef():
    dm = """
position  {
    x   u8
    y   u8
}"""
    result = datamijn.parse(dm, b('1020'))
    assert result.position.x == 0x10
    assert result.position.y == 0x20

def test_array():
    dm = """bytes   [6]u8"""
    
    result = datamijn.parse(dm, b('010203040506'))
    assert result.bytes == [1,2,3,4,5,6]

def test_array_inline_typedef():
    dm = """
bytes   [2]{
    a   u8
    b   u8
}"""
    
    result = datamijn.parse(dm, b('01020304'))
    assert result.bytes[0].a == 1
    assert result.bytes[0].b == 2
    assert result.bytes[1].a == 3
    assert result.bytes[1].b == 4

def test_array_hex():
    dm = "bytes [0xff]u8"
    result = datamijn.parse(dm, b('01')*0xff)
    assert len(result.bytes) == 0xff

@pytest.mark.parametrize("test_hex", [True, False])
def test_pointer(test_hex):
    ptr = "0x0a" if test_hex else "10"
    db = f"pointed_byte @{ptr} u8"
    result = datamijn.parse(db, b('00')*10 + b('01'))
    assert result.pointed_byte == 1

def test_dynamic_pointer():
    db = """
val_ptr u16
val     @val_ptr u8
"""
    data = b('1000' + '00'*14 + 'aa')
    result = datamijn.parse(db, data)
    assert result.val == 0xaa

def test_dynamic_pointer_array():
    db = """
val_ptr         u16
val_count       u8
vals            @val_ptr [val_count] u8
"""
    data = b('1000' + '03' + '00'*13 + 'aabbcc')
    result = datamijn.parse(db, data)
    assert result.vals == [0xaa, 0xbb, 0xcc]

def test_complex():
    result = datamijn.parse(open("test/test.dm"),
        open("test/test.bin", "rb"))
    assert result.version == 0x123
    # don't test the rest because
    # it changes often

def test_reuse():
    dm = """
a {
    byte    u8
}
_start a"""
    result = datamijn.parse(dm, b"\x00")
    
    with pytest.raises(KeyError):
        dm2 = "_start a"
        result = datamijn.parse(dm2, b"\x00")
        
