
:Coords {
    x       u8
    y       u8
    nested {
        z       u8
    }
}

:BytePlusOne {
    _byte        u8
    _one         = 1
    
    = _byte + _one
}


version         u16
positions       [0x2]Coords


byte_plus_one   @0x40 BytePlusOne

