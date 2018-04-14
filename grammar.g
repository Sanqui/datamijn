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
expr: EXPR -> eval

_NL: /(\r?\n[\t ]*)+/

?start: _NL* field*

field: name field_params type _NL -> field

?name: NAME

?type: NAME                -> type
    | "{" _NL field+ "}"   -> typedef

field_params:
    | count
    | pointer
    | count pointer
    | pointer count

count: "[" expr "]"     
pointer: "@" expr    
       | "@" name   
