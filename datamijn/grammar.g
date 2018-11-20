%import common.CNAME -> NAME
%import common.WS_INLINE
%ignore WS_INLINE

DIGIT: "0".."9"
HEXDIGIT: "a".."f"|"A".."F"|DIGIT
INT: "0x" HEXDIGIT+|DIGIT+
SIGNED_INT: ["+"|"-"] INT
NUM: INT | SIGNED_INT
// TODO: expressions should allow for some math
// but for now we have ctx_expr which is farpowerful
EXPR: NUM

STRING_DBL: /"(\\\"|[^"])+"/
STRING_SNG: /'(\\'|[^'])+'/

string: STRING_DBL -> string
      | STRING_SNG -> string

expr: EXPR -> eval

ctx_expr: /=(.+)/          -> ctx_expr

ctx_name: NAME             -> ctx_name

enum_key: NAME             -> enum_token
        | string           -> enum_str

enum_field: enum_key ctx_expr? _NL  -> enum_field

enum: "enum" "{" _NL enum_field+ "}"   -> enum

container: "{" _NL+ field* "}" -> container

count: "[" expr "]"
     | "[" ctx_name "]"
     | "[" "]"

type: NAME                   -> type
    | container
    | count type             -> type_count
    | type enum              -> type_enum

pointer: /@[^ ]*/
// "@" expr    
//       | "@" ctx_name

field_params:
    | pointer

field: NAME ctx_expr _NL+           -> equ_field
     | NAME field_params type _NL+  -> field
     | ":" NAME type _NL+           -> def_field
     | /\!if ([^\{]+)/ container ("!else" container)? _NL+ -> if_field
     | /\!assert(.*)/ _NL+          -> assert_field

COMMENT: /\/\/.*/
_NL: COMMENT? /(\r?\n[\t ]*)+/

?topstatement: "!import" NAME _NL+  -> import_
             | field

start: _NL* topstatement*           -> container

