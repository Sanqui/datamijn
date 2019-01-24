!import ascii

$Coords {
    x       : u8
    y       : u8
    nested  : {
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

inner {
    string          @0x30 [4]Char
    string_end      @0x50 [] Char
    string_endx     @0x50 [7]Char
}

gfx {
    tiles       @0x100  [2]Tile1BPP
    !save tiles


    :GBColor short | {
        _max  = 31
        r     b5
        g     b5
        b     b5
        _     b1
    } | RGBColor
    :GBPalette [4]GBColor
    
    pal @0 GBPalette
    
    sanquiderp  @0x200  [0xb][0x10]GBTile
    sanquiderp = sanquiderp | pal
    !save sanquiderp
}

addition    u8 + u8
