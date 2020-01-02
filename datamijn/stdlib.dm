:GBColor {
    max    31
    r      B5
    g      B5
    b      B5
    _      B1
} RGBColor

:GBPalette [4]GBColor

:GBPalDefault [4] ({
    r      (3-I) * (31/3)
    g      (3-I) * (31/3)
    b      (3-I) * (31/3)
    max  31
} RGBColor)

// this probably crashes atm because of the embed caused by !if
//:GBBankFit {
//    !if (Pos / 0x4000) != ((Pos + RightSize - 1) / 0x4000) {
//        _pad    0x4000 - (Pos % 0x4000)
//        _       [_pad]Byte
//    }
//    bytes    [RightSize]Byte
//    = bytes
//}

:GBAddr(Bank, Pointer) Pointer % 0x4000 + Bank * 0x4000
//:Test GBAddr(U16, U16)
