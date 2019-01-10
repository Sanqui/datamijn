import pytest
import os

from datamijn import datamijn

from codecs import decode
def b(string):
    return decode(string.replace(" ", ""), 'hex')

@pytest.mark.parametrize("type,data,value", [
    ("u8",  b('01'), 1),
    ("u16", b('0102'), 0x0201),
#    ("u32", b('01020304'), 0x04030201),
])
def test_basic_type(type, data, value):
    dm = f"value {type}"
    result = datamijn.parse(dm, data)
    assert result.value == value
    assert result.value._data.data == data
    assert result.value._data.address == 0
    assert result.value._data.length == len(data)

def test_typedef():
    dm = """
position  {
    x   u8
    y   u8
}"""
    result = datamijn.parse(dm, b('1020'))
    assert result.position.x == 0x10
    assert result.position.x._data.data == b('10')
    assert result.position.x._data.address == 0x0
    assert result.position.x._data.length == 0x1
    assert result.position.y == 0x20
    assert result.position.y._data.data == b('20')
    assert result.position.y._data.address == 0x1
    assert result.position.y._data.length == 0x1
    
    keys = ['x', 'y']
    for key, real_key in zip(result.position, ['x', 'y']):
        assert key == real_key

def test_type_definition():
    dm = """
:Byte   u8

value   Byte
"""
    result = datamijn.parse(dm, b('01'))
    
    assert result.value == 1

def test_array():
    dm = """bytes   [6]u8"""
    
    nums = [1, 2, 3, 4, 5, 6]
    result = datamijn.parse(dm, b('010203040506'))
    
    assert result.bytes == nums
    
    # test iteration
    for byte, real in zip(result.bytes, nums):
        assert byte == real

def test_nested_array():
    dm = """bytes   [2][2][2]u8"""
    
    result = datamijn.parse(dm, b('0102030405060708'))
    assert result.bytes[0][0] == [1, 2]
    assert result.bytes[0][1] == [3, 4]
    assert result.bytes[1][0] == [5, 6]
    assert result.bytes[1][1] == [7, 8]


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

def test_equ():
    dm = "test  = 5"
    result = datamijn.parse(dm, b'')
    assert result.test == 5


def test_array_dynamic():
    dm = """
count   = 2
bytes   [count]u8
"""
    result = datamijn.parse(dm, b('aabb'))
    assert result.bytes == [0xaa, 0xbb]

def test_container_computed_value():
    dm = """
test    {
    x       u8
    = 2
}
"""
    result = datamijn.parse(dm, b("aa"))
    assert result.test.x == 0xaa
    assert result.test == 2


def test_array_computed():
    dm = """
test    {
    = 2
}

bytes    [test] u8
nested {
    bytes2 [test]u8
}
"""
    result = datamijn.parse(dm, b("aabbccdd"))
    assert result.test == 2
    assert result.bytes == [0xaa, 0xbb]
    assert result.nested.bytes2 == [0xcc, 0xdd]

@pytest.mark.parametrize("test_hex", [True, False])
def test_pointer(test_hex):
    ptr = "0x0a" if test_hex else "10"
    db = f"pointed_byte @{ptr} u8"
    result = datamijn.parse(db, b('00')*10 + b('01'))
    assert result.pointed_byte == 1
    assert result.pointed_byte._data.address == 10

def test_dynamic_pointer():
    db = """
val_ptr u16
val     @val_ptr u8
"""
    data = b('1000' + '00'*14 + 'aa')
    result = datamijn.parse(db, data)
    assert result.val == 0xaa

def test_dynamic_pointer_complex():
    db = """
val_ptr [1]u8
val     @_root.val_ptr[0] u8
"""
    data = b('0102')
    result = datamijn.parse(db, data)
    assert result.val_ptr == [1]
    assert result.val == 2
    

def test_dynamic_pointer_array():
    db = """
val_ptr         u16
val_count       u8
vals            @val_ptr [val_count] u8
"""
    data = b('1000' + '03' + '00'*13 + 'aabbcc')
    result = datamijn.parse(db, data)
    assert result.vals == [0xaa, 0xbb, 0xcc]

def test_pointer_computed():
    dm = """
test    {
    = 1
}

byte    @test u8
"""
    result = datamijn.parse(dm, b("00aa"))
    assert result.test == 1
    assert result.byte == 0xaa

def test_void_type():
    dm = """
:Token

token   Token
"""
    result = datamijn.parse(dm, b("ff"))
    assert result.token
    assert result.token._typename == "Token"
    assert isinstance(result.token, result.Token)
    assert result.token == result.Token()
    assert result.token == result.Token

def test_match():
    db = """
test        u8 match {
    0 => :Zero
    1 => :One
    2 => :Two
    3 => :Three
}"""
    result = datamijn.parse(db, b("02"))
    assert result.test._typename == "Two"

def test_match_default():
    db = """
test        u8 match {
    0 => :Zero
    1 => :One
    _ => :Unknown
}"""
    result = datamijn.parse(db, b("fe"))
    assert result.test._typename == "Unknown"

def test_match_default_name():
    db = """
test        u8 match {
    0 => :Zero
    1 => :One
    x => =x
}"""
    result = datamijn.parse(db, b("fe"))
    assert result.test == 0xfe


def test_match_missing():
    db = """
test       [2] u8 match {
    0 => :Zero
    1 => :One
}"""

    with pytest.raises(KeyError):
        result = datamijn.parse(db, b("0105"))
    #assert result.test == ["one", 5]


def test_match_string():
    db = """
test        u8 match {
    0 => "a a"
    1 => 'b b'
}"""
    result = datamijn.parse(db, b("01"))
    assert result.test == "b b"


def test_match_autoincrement():
    db = """
num        u8 match {
             :Zero
    0x20  => :TwoOh
             :TwoOne
    0x40  => :FourOh
}
"""
    result = datamijn.parse(db, b("21"))
    assert result.num._typename == "TwoOne"



def test_match_string():
    db = """
:Char        u8 match {
    0x21 => "!!"
    0x41 => "A"
    0x42 => "B"
    0x43 => "C"
    0x00 => :End    Terminator
}

string      [5]Char
"""
    result = datamijn.parse(db, b("4342412100"))
    assert result.string == ["C", "B", "A", "!!", result.Char.End]

def test_match_char_string():
    db = """
:Char        u8 char match {
    0x21 => "!!"
    0x41 => "A"
    0x42 => "B"
    0x43 => "C"
    0x00 => :End    Terminator
}

string      [5]Char
"""
    result = datamijn.parse(db, b("4342412100"))
    assert result.string == ["CBA!!", result.Char.End]

def test_bits():
    dm = """
:SomeBits {
    a          b1
    b          b1
    two        [2]b1
    rest       b4
}

bits            SomeBits
following_byte  u8
"""
    result = datamijn.parse(dm, b("0744"))
    assert result.bits.a == 1
    assert result.bits.b == 1
    assert result.bits.two == [1, 0]
    assert result.bits.rest == 0
    assert result.following_byte == 0x44

def test_bit_type():
    dm = """
:Bits   [8]b1
bits    Bits

"""
    result = datamijn.parse(dm, b("aa"))
    assert result.bits == [0, 1, 0, 1, 0, 1, 0, 1]

def test_bit_byte_boundary():
    dm = """
cards   [60]b9
"""
    result = datamijn.parse(dm, bytes([
                                    0b00000000,
                                    0b00000010,
                                    0b00001000,
                                    0b00011000,
                                    0b01000000,
                                    0b10100000,
                                ] + [0]*100))
    
    assert result.cards[0:6] == [0, 1, 2, 3, 4, 5]
    

def test_empty():
    dm = """
empty {

}"""
    result = datamijn.parse(dm, b(""))
    assert result.empty != None


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


def test_zero_terminated_array():
    dm = """
numbers         [] u8
"""
    result = datamijn.parse(dm, b("aabbcc00"))
    assert result.numbers == [0xaa, 0xbb, 0xcc, 0]


def test_terminated_array():
    dm = """
numbers         [] {
    number      u8
    = _terminator if number == 0xff else number
}
"""
    result = datamijn.parse(dm, b("000102ff"))
    assert result.numbers[0] == 0
    assert result.numbers[1] == 1
    assert result.numbers[2] == 2
    assert result.numbers[3] == datamijn.Terminator
    assert len(result.numbers) == 4

@pytest.mark.xfail # IDEA
def test_fold_array():
    dm = """
rle         [2] fold {
    count      u8
    value      u8
    = [value] * count
}
"""
    result = datamijn.parse(dm, b("02000501"))
    assert result.rle == [0, 0, 1, 1, 1, 1, 1]


def test_terminated_string():
    dm = """
:Char        u8 char match {
    0x41 => "A"
            "B"
            "C"
    // ...
    0x00 => :End Terminator
}

string      [] Char
"""
    result = datamijn.parse(dm, b"BACA\x00")
    assert result.string == ["BACA", result.Char.End]
    assert str(result.string) == "BACA"

def test_multiple_terminated_string():
    dm = """
:Char        u8 char match {
    0x41 => "A"
            "B"
            "C"
    
    0x00 => :End1 Terminator
    0xff => :End2 Terminator
}

string      [] Char
"""
    result = datamijn.parse(dm, b"BACA\x00")
    assert result.string == ["BACA", result.Char.End1]
    assert str(result.string) == "BACA"
    result = datamijn.parse(dm, b"CABA\xff")
    assert result.string == ["CABA", result.Char.End2]
    assert str(result.string) == "CABA"

def test_string_with_control_codes():
    dm = """
:Char        u8 char match {
    0x20 => " "
            "!"
    0x41 => "A"
            "B"
            "C"
            "D"
            "E"
            "F"
    // ...
    
    0xe0 => :PlayerName
    0xe1 => :TextSpeed  u8
    
    0x00 => :End Terminator
}

string      [] Char
"""
    result = datamijn.parse(dm, b"BAD \xe1\x05CAFE \xe0!\x00")
    assert result.string == ["BAD ", result.Char.TextSpeed(5), "CAFE ", result.Char.PlayerName, "!", result.Char.End]
    assert str(result.string) == "BAD <TextSpeed(5)>CAFE <PlayerName>!"

def test_match_range():
    dm = """
:Thing        u8 char match {
    0..8        => "0"
                   "8"
    0x80..0xff  => "Z"
}

stuff   [5]Thing
"""
    result = datamijn.parse(dm, b("00 07 08 05 ee"))
    
    assert str(result.stuff) == "0080Z"


def test_byte():
    dm = """
byte1    byte
byte2    byte
bytes    [4]byte
"""
    result = datamijn.parse(dm, b"a\xe3TEST")
    assert result.byte1 == b"a"
    assert result.byte2 == b"\xe3"
    assert result.bytes == b"TEST"

def test_byte_pipe():
    dm = """
num8     byte | u8
num16    byte | u16
bits     byte | {
    a          b1
    b          b1
    two        [2]b1
    rest       b4
    more       [8]b1
}
"""
    result = datamijn.parse(dm, b("1122330744ff"))
    assert result.num8 == 0x11
    assert result.num16 == 0x3322
    assert result.bits.a == 1
    assert result.bits.b == 1
    assert result.bits.two == [1, 0]
    assert result.bits.rest == 0

def test_byte_pipe_unaccounted():
    dm = """
bits     byte | {
    a          b1
    b          b1
    three      [3]b1
    // 3 bits unaccounted for
}
"""
    with pytest.raises(ValueError):
        result = datamijn.parse(dm, b("11"))

def test_short_pipe():
    dm = """
cards    short | [64]b9
"""
    result = datamijn.parse(dm, bytes([
                                    0b00000010,
                                    0b00000000,
                                    
                                    0b00011000,
                                    0b00001000,
                                    
                                    0b10100000,
                                    0b01000000,
                                ] + [0]*100))
    
    assert result.cards[0:6] == [0, 1, 2, 3, 4, 5]
    
def test_foreign_assignment():
    dm = """
struct {
    x       u8
    nested {
        
    }
}
foo         u8
struct.y    u8
struct.nested.bar u8
"""
    result = datamijn.parse(dm, b("01020304"))
    assert result.struct.x == 1
    assert result.foo == 2
    assert result.struct.y == 3
    assert result.struct.nested.bar == 4

def test_foreign_assignment_error():
    dm = """
unknown.x     u8
"""
    with pytest.raises(NameError):
        result = datamijn.parse(dm, b("01"))

def test_foreign_list_assignment():
    dm = """
stuff [4]{
    a   u8
    b   u8
    c   u8
}
stuff[].d   [4]u8
"""
    result = datamijn.parse(dm, b("0a0b0c 1a1b1c 2a2b2c 3a3b3c 0d1d2d3d"))
    assert result.stuff[0].a == 0x0a
    assert result.stuff[0].d == 0x0d
    assert result.stuff[3].a == 0x3a
    assert result.stuff[3].d == 0x3d
    
def test_foreign_list_assignment_errors():
    dm = """
stuff {
    a       u8
}
stuff[].b   [4]u8
"""
    with pytest.raises(TypeError):
        result = datamijn.parse(dm, b("00"*100))
    
    dm = """
stuff [4] {
    a       u8
}
stuff[].b   u8
"""
    with pytest.raises(TypeError):
        result = datamijn.parse(dm, b("00"*100))
    
    dm = """
stuff [5] {
    a       u8
}
stuff[].b   [4]u8
"""
    with pytest.raises(TypeError):
        result = datamijn.parse(dm, b("00"*100))

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

def test_foreign_key():
    dm = """
things      [4]{
    x   u8
    y   u8
}

thing   u8 -> things
"""
    result = datamijn.parse(dm, b("0001 1011 2021 3031  02"))
    
    assert result.thing.x == 0x20
    assert result.thing.y == 0x21

def test_foreign_key_val():
    dm = """
things      [4]{
    x   u8
    y   u8
}

thing   {= 2} -> things
"""
    result = datamijn.parse(dm, b("0001 1011 2021 3031"))
    assert result.thing.x == 0x20
    assert result.thing.y == 0x21

def test_foreign_key_error():
    dm = """
things      [4]{
    x   u8
}

thing   u8 -> things
"""
    with pytest.raises(IndexError):
        result = datamijn.parse(dm, b("00 11 21 31  05"))
        # a second resolve pass would catch this earlier
        result.thing.x

def test_null():
    dm = "x Null"
    
    result = datamijn.parse(dm, b(""))
    assert result.x == None

'''

def test_eval_enum_access():
    dm = """
FRUIT u8 enum {
    APPLE
    PEAR
    BANANA
}

_start {
    fruit       = FRUIT.BANANA
}"""
    result = datamijn.parse(dm, b"")
    # TODO should enums be accessible ad result.FRUIT.BANANA?
    assert result.fruit == result._structs.FRUIT.BANANA
    assert result.fruit == "BANANA"
    assert result.fruit == 2
'''

def test_index():
    dm = """
dummy_array  [4] {
    index       = _i
}
"""
    result = datamijn.parse(dm, b"")
    for i in range(4):
        assert result.dummy_array[i].index == i

'''

def test_nested_index():
    dm = """
dummy_array  [4] {
    x               {
        index = _index
    }
}
"""
    result = datamijn.parse(dm, b"")
    for i in range(4):
        assert result.dummy_array[i].x.index == i

def test_if():
    dm = """
!if 1 {
    true = 1
}
!if 0 {
    false = 1
}
"""
    result = datamijn.parse(dm, b"")
    assert result.true == 1
    assert result.false == None

def test_if_else():
    dm = """
!if 1 {
    true = 1
}!else {
    false = 1
}
"""
    result = datamijn.parse(dm, b"")
    assert result.true == 1
    assert result.false == None

def test_if_else_overlap():
    dm = """
!if 1 {
    a = 1
    b = 1
    c = 1
}!else {
    x = 0
    a = 0
    y = 0
    c = 0
    z = 0
}
"""
    result = datamijn.parse(dm, b"")
    assert result.a == 1
    assert result.b == 1
    assert result.c == 1
    assert result.x == None
    assert result.y == None
    assert result.z == None

@pytest.mark.xfail
def test_if_else_cross():
    dm = """
!if 0 {
    x = 1
    y = 1
}!else {
    y = 0
    x = 0
}
"""
    result = datamijn.parse(dm, b"")
    print(result)
    assert result.x == 0
    assert result.y == 0

def test_assert():
    dm = """
byte        u8
!assert byte == 5
"""
    result = datamijn.parse(dm, b("05"))
    assert result.byte == 5
    
'''

def test_type_name_error():
    dm = "something     NoExist"
    
    with pytest.raises(NameError):
        result = datamijn.parse(dm, b"")

def test_resolve_parent_type():
    dm = """
object1 {
    :TestA {
        foo     u8
    }

    object2 {
        x    TestA
    }
}
"""
    result = datamijn.parse(dm, b("aa"))
    assert result.object1.object2.x.foo == 0xaa

def test_import(tmpdir):
    tmpdir.join("color.dm").write("""
:Color   u8 match {
    :White
    :Red
    :Green
    :Blue
}
""")
    tmpdir.join("double.dm").write("""
!import color

:ColorAlias Color
""")
    tmpdir.join("test.dm").write("""
!import double

color0      Color
color1      Color
color2      ColorAlias
""")
    
    result = datamijn.parse(open(tmpdir.join("test.dm")), b("020100"))
    assert result.color0 == result.Color.Green
    assert result.color1 == result.Color.Red
    assert result.color2 == result.Color.White

def test_save_tile(tmpdir):
    tmpdir.join("test.dm").write("""
tile    Tile1BPP
!save tile
""")
    
    result = datamijn.parse(open(tmpdir.join("test.dm")), b('0011223344556677'), tmpdir.join("x"))
    assert open(tmpdir.join("/x/tile.png"))

def test_save_tiles(tmpdir):
    tmpdir.join("test.dm").write("""
tiles    [20]Tile1BPP
!save tiles
""")
    
    result = datamijn.parse(open(tmpdir.join("test.dm")), b('0011223344556677')*20, tmpdir.join("x"))
    assert open(tmpdir.join("/x/tiles.png"))


def test_save_pics(tmpdir):
    tmpdir.join("test.dm").write("""
pics    [5][2][2]Tile1BPP
!save pics
""")
    
    result = datamijn.parse(open(tmpdir.join("test.dm")), b('0011223344556677')*20, tmpdir.join("x"))
    for i in range(5):
        assert open(tmpdir.join(f"/x/pics/{i}.png"))


def test_complex():
    result = datamijn.parse(open("datamijn/test/test2.dm"),
        open("datamijn/test/test.bin", "rb"))
    assert result.version == 0x123
    # don't test the rest because
    # it changes often

def test_cleanup():
    dm = """
:A {
    byte    u8
}

a A"""
    result = datamijn.parse(dm, b"\x00")
    
    with pytest.raises(NameError):
        dm2 = "a A"
        result = datamijn.parse(dm2, b"\x00")


