coords {
    x       u8
    y       u8
    nested {
        z       u8
    }
}

_start       {
    version         u16
    positions       [0x2]coords
    version_again   @0x0 u16
    aa_ptr          u16
    aa              @aa_ptr u8
    
}


