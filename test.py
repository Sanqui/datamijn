import datamijn

def test_byte():
    dm = "byte u8"
    result = datamijn.parse(dm, b"\x01")
    assert result == 1


