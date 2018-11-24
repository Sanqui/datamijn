
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

:ItemCategory   u8 match {
    0   => :None
    1   => :Potion
    2   => :Weapon
    3   => :Armor
}

version         u16
positions       [0x2]Coords


byte_plus_one   @0x40 BytePlusOne

item_category   @0x20 ItemCategory

bits            [16]b1

bytenum         byte | u8

struct          {

}

struct.x        u8

some_array  [10] {
}

some_array[].x  [10]u8


