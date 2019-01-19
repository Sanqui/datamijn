:GBColor {
    _max  = 31
    r     b5
    g     b5
    b     b5
    _     b1
} | RGBColor

:GBPalette [4]GBColor

:GBBankFit {
    _right_size = _right.size()
    !if (_pos // 0x4000) != (_pos + _right_size - 1)//0x4000 {
        _pad    = 0x4000 - (_pos % 0x4000)
        _       [_pad]byte
    }
    bytes    [_right_size]byte
    = bytes
}
