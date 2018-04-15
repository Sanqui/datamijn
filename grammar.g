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
STRING_DBL_INNER: ("\\\""|/[^"]/)
STRING_DBL: "\"" STRING_DBL_INNER* "\""
STRING_SNG_INNER: ("\\'"|/[^']/)
STRING_SNG: "'" STRING_SNG_INNER* "'"
?string: STRING_DBL -> string
       | STRING_SNG -> string

expr: EXPR -> eval
ctx_name: NAME  -> ctx_value

_NL: /(\r?\n[\t ]*)+/

?start: _NL* field*

field: name field_params type _NL -> field

?name: NAME                -> name

?type: NAME                -> type
    | "{" _NL field+ "}"   -> typedef
    | type enum            -> enum_type

enum_field: name expr? _NL  -> enum_field
        | string expr? _NL  -> enum_field

?enum: "enum" "{" _NL enum_field+ "}"   -> enum

// XXX does count pointer make sense?

field_params:
    | count
    | pointer
    | count pointer
    | pointer count

count: "[" expr "]"
       | "[" ctx_name "]"
pointer: "@" expr    
       | "@" ctx_name
