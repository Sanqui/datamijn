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

def test_complex():
    result = datamijn.parse(open("test/test.dm"),
        open("test/test.bin", "rb"))
    assert result.version == 0x123
    assert result.pos1.x == 1
    assert result.pos1.y == 2
    assert result.pos1.nested.z == 3
    assert result.pos2.x == 0x22
    assert result.pos2.y == 0x33
    assert result.pos2.nested.z == 0x44

