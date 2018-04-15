coords {
    x       u8
    y       u8
    nested {
        z       u8
    }
}

val_ptr {
    _ptr         u16
    val          @_ptr u8
}

item_category   u8 enum {
    none            0
    potion          1
    weapon          2
    armor           3
}

letter          u8 enum {
    "a"             0
    "b"             1
    "c"             2
    "d"             3
}

char            u8 enum {
    "A"             0x41
    "B"
    "C"
    "D"
    "E"
    "F"
    "G"
    "H"
    "I"
    "J"
    "K"
    "L"
    "M"
    "N"
    "O"
    "P"
    "Q"
    "R"
    "S"
    "T"
    "U"
    "V"
    "W"
    "X"
    "Y"
    "Z"
    END         0x00
}

_start       {
    version         u16
    positions       [0x2]coords
    version_again   @0x0 u16
    val_ptr         u16
    val_count       u8
    vals            @val_ptr [val_count]u8
    item_category   @0x20 item_category
    letter          @0x21 letter
    string          @0x30 [4]char
}


