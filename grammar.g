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
//STRING_DBL_INNER: /("\\\"[^"]/ ("\\\""|/[^"]/)
STRING_DBL: /"(\\\"|[^"])+"/
//STRING_SNG_INNER: ("\\'"|/[^']/)
STRING_SNG: /'(\\'|[^'])+'/
COMMENT: /\/\/.*/
?string: STRING_DBL -> string
       | STRING_SNG -> string

expr: EXPR -> eval
// XXX
ctx_expr: /=(.+)/  -> ctx_expr
//ctx_expr: expr
ctx_name: NAME  -> ctx_value

_NL: COMMENT? /(\r?\n[\t ]*)+/

?start: _NL* topstatement*

?name: NAME                -> name

?topstatement: "!import" NAME _NL+          -> import_
             | field

field: name ctx_expr _NL+           -> equ_field
    | name field_params type _NL+ -> field

?type: NAME                -> type
    | "{" _NL+ field* "}"   -> typedef
    | type enum            -> enum_type

?enum_name: NAME                -> enum_name
?enum_char: string              -> enum_char


?enum_expr: ctx_expr
enum_field: enum_name enum_expr? _NL  -> enum_field
        | enum_char enum_expr? _NL    -> enum_field

?enum: "enum" "{" _NL enum_field+ "}"   -> enum

// XXX does count pointer make sense?

field_params:
    | count
    | pointer
    | count pointer
    | pointer count

count: "[" expr "]"
       | "[" ctx_name "]"
       | "[" "]"
pointer: "@" expr    
       | "@" ctx_name
