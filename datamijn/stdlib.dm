:GBColor {
    _max   31
    r      B5
    g      B5
    b      B5
    _      B1
} | RGBColor

:GBPalette [4]GBColor

:GBPalDefault [4] ({
    r      (3-I) * (31/3)
    g      (3-I) * (31/3)
    b      (3-I) * (31/3)
    _max  31
} | RGBColor)

:GBBankFit {
    !if (Pos / 0x4000) != ((Pos + RightSize - 1) / 0x4000) {
        _pad    0x4000 - (Pos % 0x4000)
        _       [_pad]Byte
    }
    bytes    [RightSize]Byte
    = bytes
}
