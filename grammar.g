%import common.CNAME -> NAME
%import common.WS_INLINE
%ignore WS_INLINE

DIGIT: "0".."9"
HEXDIGIT: "a".."f"|"A".."F"|DIGIT
INT: "0x" HEXDIGIT+|DIGIT+
SIGNED_INT: ["+"|"-"] INT
NUM: INT | SIGNED_INT
// TODO: expressions should allow for math
EXPR: NUM


_NL: /(\r?\n[\t ]*)+/

?start: _NL* field*

field: name type _NL          -> field
     | name count type _NL    -> field_array

?name: NAME

?type: NAME                -> type
    | "{" _NL field+ "}"   -> typedef

?count: "[" EXPR "]"
