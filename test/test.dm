position {
    x       u8
    y       u8
    nested {
        z       u8
    }
}

_start       {
    version     u16
    pos1        position
    pos2        position
}
