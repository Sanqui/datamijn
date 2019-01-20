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
ctx_expr_par: /{=([^}]+)}/      -> ctx_expr_par

ctx_name: NAME             -> ctx_name

match_key: expr "=>"       -> match_key_int
    | expr ".." expr "=>"  -> match_key_range
    | string "=>"          -> match_key_string
    | NAME "=>"            -> match_key_default_name
    | "_" "=>"             -> match_key_default

stringtype: string         -> stringtype

match_expr: ctx_expr -> match_expr

match_field: match_key? type       _NL+  -> match_field
    |        match_key? stringtype _NL+  -> match_field
    |        match_key? match_expr _NL+  -> match_field

match: "match" "{" _NL match_field+ "}"   -> match

container: "{" _NL+ field* "}" -> container

count: "[" expr "]"
     | "[" ctx_name "]"
     | "[" "]"

typename: NAME               -> typename

type: typename               -> type_typename
    | container              -> type_container
    | typedef                -> type_typedef
    | count type             -> type_count
    | type match             -> type_match
    | type "char" match      -> type_char_match
    | type "|" type          -> type_pipe
    | type "->" field_name   -> type_foreign_key
    | ctx_expr_par           -> type_equ
    | "<" type               -> type_yield

pointer: /@[^ ]*/
pipepointer: /\|@[^ ]*/

field_params:
    | pointer
    | pipepointer

typedef: ":" NAME type              -> typedef
    |    ":" NAME                   -> typedefvoid

field_name: NAME                    -> field_name
    | field_name "." field_name     -> field_name_dot
    | field_name "[]." field_name   -> field_name_array
    | "_"                           -> field_name_underscore

field: field_name ctx_expr _NL+           -> equ_field
     | ctx_expr _NL+                      -> bare_equ_field
     | field_name field_params type _NL+  -> instance_field
     | typedef _NL+                       -> typedef_field
     | /\!if ([^\{]+)/ container ("!else" container)? _NL+ -> if_field
     | /\!assert(.*)/ _NL+                -> assert_field
     | "!save" field_name _NL+            -> save_field
     | "!debug" field_name _NL+           -> debug_field
     | "<" type _NL+                      -> yield_field

COMMENT: /\/\/.*/
_NL: COMMENT? /(\r?\n[\t ]*)+/

?topstatement: "!import" NAME _NL+  -> import_
             | field

start: _NL* topstatement*           -> container

