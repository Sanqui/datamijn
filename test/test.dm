!import ascii

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
    none           = 0
    potion         = 1
    weapon         = 2
    armor          = 3
}

letter          u8 enum {
    "a"             = 0
    "b"             = 1
    "c"             = 2
    "d"             = 3
    END             = 0xfe
    END2            = 0xff
    _end           = (END, END2)
}

terminated_string [] letter


some_bits {
    bit_0        u1
    bit_1        u1
    bit_2        u1
    bit_3        u1
    bit_4        u1
    bit_5        u1
    bit_6        u1
    bit_7        u1
}

bit_array {
    bits        [8]u1
}

empty {
    // comment
}

//byte_plus_one {
//    byte            u8
//    one             = 1
//    byte_plus_one   = byte + one
//}

byte_plus_one {
    _byte            u8
    _one             = 1
    _val             = _byte + _one
}

FRUIT u8 enum {
    APPLE
    PEAR
    BANANA
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
    
    some_bits       @0x40 some_bits
    bit_array       @0x40 bit_array
    
    byte_plus_one   @0x40 byte_plus_one
    
    string_end      @0x50 [] char
    
    unknown_item_category @0x57 item_category
    
    tell            = _pos
    
    test_value      = 10
    test_access     {
        test            = _root.test_value
    }
    
    fruit           = FRUIT.APPLE
    
    !if 1 {
        conditional = 1
        another = 2
    }
    
    !if version == 291 {
        version_was_291 = 1
    }
    
    !if 0 {
        this_shouldnt_be_true = 1
    } !else {
        knew_it_all_along = 1
    }
    
    !assert version == 291
    
    testcomplex     = [0, 1, 2]
    xxxx_ptr    @_root.testcomplex[0] u16
    //xxxx_arr    [_root.testcomplex[1]] u16
    
    new {
        !if 1 {
            a = 1
            b = 1
        } !else {
            x = 0
            a = 0
            y = 0
        }
        
        derp        {
            _val        = 1
        }
        at_ptr_val  @derp u8
        size_val    @0 [derp] u8
        
        //error = missingno
        
        end_on_end [] {
            i       = _index
            _stop   = i == 5
        }
        
        
        added_list [5] {
            _add    = [_index]
        }
    }
    
}


