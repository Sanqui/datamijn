import pytest

import datamijn

@pytest.mark.parametrize("type,data,value", [
    ("u8", b"\x01", 1),
    ("u16", b"\x01\x02", 0x0201),
    ("u32", b"\x01\x02\x03\x04", 0x04030201),
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
    result = datamijn.parse(dm, b"\x10\x20")
    assert result.position.x == 0x10
    assert result.position.y == 0x20

def test_array():
    dm = """bytes   [6]u8"""
    
    result = datamijn.parse(dm, b"\x01\x02\x03\x04\x05\x06")
    assert result.bytes == [1,2,3,4,5,6]

def test_array_inline_typedef():
    dm = """
bytes   [2]{
    a   u8
    b   u8
}"""
    
    result = datamijn.parse(dm, b"\x01\x02\x03\x04")
    assert result.bytes[0].a == 1
    assert result.bytes[0].b == 2
    assert result.bytes[1].a == 3
    assert result.bytes[1].b == 4

def test_array_hex():
    dm = "bytes [0xff]u8"
    result = datamijn.parse(dm, b"\x01"*0xff)
    assert len(result.bytes) == 0xff

def test_pointer():
    db = "pointed_byte @10 u8"
    result = datamijn.parse(db, b"\x00"*10 + b"\x01")
    assert result.pointed_byte == 1

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
        
