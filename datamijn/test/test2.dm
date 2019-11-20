!import ascii

:Coords {
    x       U8
    y       U8
    nested  {
        z       U8
    }
}

:BytePlusOne {
    _byte        U8
    _one         1
    
    = _byte + _one
}

:ItemCategory   U8 match {
    0   => :None
    1   => :Potion
    2   => :Weapon
    3   => :Armor
}

version         U16
positions       [0x2]Coords


byte_plus_one   @0x40 BytePlusOne

item_category   @0x20 ItemCategory

bits            [16]B1

bytenum         Byte | U8

struct          {

}

struct.x        U8

some_array  [10] {
}

some_array[].x  [10]U8

inner {
    string          @0x30 [4]Char
    string_end      @0x50 [] Char
    string_endx     @0x50 [7]Char
}

gfx {
    tiles       @0x100  [2]Tile1BPP
    !save tiles


    :GBColor Short | {
        max  31
        r     B5
        g     B5
        b     B5
        _     B1
    } RGBColor
    :GBPalette [4]GBColor
    
    pal @0 GBPalette
    
    _sanquiderp  @0x200  [0xb][0x10]GBTile
    sanquiderp  _sanquiderp | pal
    !save sanquiderp
}

addition    U8 + U8

:Selfref {
    a {
        test U8
    }
    x a.test match {
        32 => Selfref
        x => x
    }
}

selfref Selfref
