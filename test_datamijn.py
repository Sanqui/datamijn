import pytest
import os

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

def test_enum():
    db = """
test        u8 enum {
    zero       = 0
    one        = 1
    two        = 2
    three      = 3
}"""
    result = datamijn.parse(db, b("02"))
    assert result.test == "two"

def test_enum_string():
    db = """
test        u8 enum {
    "a"        = 0
    'b'        = 1
}"""
    result = datamijn.parse(db, b("01"))
    assert result.test == "b"

def test_enum_autoincrement():
    db = """
num        u8 enum {
    zero
    two_oh     = 0x20
    two_one
    four_oh    = 0x40
}
"""
    result = datamijn.parse(db, b("21"))
    assert result.num == "two_one"

def test_enum_string():
    db = """
char        u8 enum {
    "!"        = 0x21
    "A"        = 0x41
    "B"        = 0x42
    "C"        = 0x43
    END        = 0x00
}

_start {
    string      [5]char
}
"""
    result = datamijn.parse(db, b("4342412100"))
    assert result.string == ["CBA!", result._structs.char.END]

def test_bits():
    dm = """
some_bits {
    a        u1
    b        u1
    two      [2]u1
    rest     u4
}

_start {
    bits            some_bits
    following_byte  u8
}"""
    result = datamijn.parse(dm, b("07ff"))
    print(result)
    assert result.bits.a == 1
    assert result.bits.b == 1
    assert result.bits.two == [1, 0]
    assert result.bits.rest == 0
    assert result.following_byte == 0xff

def test_empty():
    dm = """
empty {

}"""
    result = datamijn.parse(dm, b(""))
    assert result.empty

def test_comment():
    dm = """
// initial comment
test0       u8 // comment after line
test1       u8
// comment at the end
"""
    result = datamijn.parse(dm, b("0001"))
    assert result.test0 == 0
    assert result.test1 == 1

def test_eval():
    dm = """
byte            u8
one             = 1
byte_plus_one   = byte + one
"""
    
    result = datamijn.parse(dm, b("05"))
    assert result.byte == 5
    assert result.one == 1
    assert result.byte_plus_one == 6

def test_val():
    dm = """
negative_twice_byte {
    _byte       u8
    _val        = _byte * -2
}

_start {
    a       negative_twice_byte
}
"""
    
    result = datamijn.parse(dm, b("05"))
    assert result.a == -10
    assert result.a._val == -10
    assert result.a._byte == 5
    assert str(result.a) == "-10"

def test_zero_terminated_array():
    dm = """
numbers         [] u8
"""
    result = datamijn.parse(dm, b("aabbcc00"))
    assert result.numbers == [0xaa, 0xbb, 0xcc]

def test_terminated_string():
    dm = """
char        u8 enum {
    "A"     = 0x41
    "B"
    "C"
    _END    = 0x00
    _end    = _END
}
_start {
    string      [] char
}
"""
    result = datamijn.parse(dm, b"BACA\x00")
    assert result.string == ["BACA"]

def test_multiple_terminated_string():
    dm = """
char        u8 enum {
    "A"     = 0x41
    "B"
    "C"
    _END1    = 0x00
    END2    = 0xff
    _end    = (_END1, END2)
}
_start {
    string      [] char
}
"""
    result = datamijn.parse(dm, b"BACA\x00")
    assert result.string == ["BACA"]
    result = datamijn.parse(dm, b"CABA\xff")
    assert result.string == ["CABA", result._structs.char.END2]

def test_pos():
    dm = """
pos0        = _pos
short       u16
pos1        = _pos
"""
    result = datamijn.parse(dm, b("aaaa"))
    assert result.pos0 == 0
    assert result.short == 0xaaaa
    assert result.pos1 == 2

def test_include(tmpdir):
    tmpdir.join("color.dm").write("""
color   u8 enum {
    WHITE      = 0
    RED        = 1
    GREEN      = 2
    BLUE       = 3
}
""")
    tmpdir.join("test.dm").write("""
!import color

_start {
    color1      color
    color2      color
}
""")
    
    result = datamijn.parse(open(tmpdir.join("test.dm")), b("0201"))
    assert result.color1 == result._structs.color.GREEN
    assert result.color2 == result._structs.color.RED

def test_complex():
    result = datamijn.parse(open("test/test.dm"),
        open("test/test.bin", "rb"))
    assert result.version == 0x123
    # don't test the rest because
    # it changes often

def test_cleanup():
    dm = """
a {
    byte    u8
}
_start a"""
    result = datamijn.parse(dm, b"\x00")
    
    with pytest.raises(KeyError):
        dm2 = "_start a"
        result = datamijn.parse(dm2, b"\x00")
        
