:GBColor {
    _max  = 31
    r     b5
    g     b5
    b     b5
    _     b1
} | RGBColor

:GBPalette [4]GBColor

:GBPalDefault [4] {
    r = (3-_i) * (31/3)
    g = (3-_i) * (31/3)
    b = (3-_i) * (31/3)
    _max = 31
} | RGBColor

:GBBankFit {
    _right_size = _right.size()
    !if (_pos // 0x4000) != (_pos + _right_size - 1)//0x4000 {
        _pad    = 0x4000 - (_pos % 0x4000)
        _       [_pad]byte
    }
    bytes    [_right_size]byte
    = bytes
}
