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

ctx_name: NAME             -> ctx_name

match_key: expr "=>"       -> match_key_int
    | expr ".." expr "=>"  -> match_key_range
    | string "=>"          -> match_key_string
    | NAME "=>"            -> match_key_default_name
    | "_" "=>"             -> match_key_default

stringtype: string         -> stringtype

match_field: match_key? type       _NL+  -> match_field
    |        match_key? stringtype _NL+  -> match_field

match: "match" "{" _NL match_field+ "}"   -> match

container: "{" _NL+ field* "}" -> container

count: "[" expr2 "]"
     | "[" "]"

SIGNSUM: "+" | "-"
SIGNPRODUCT: "*" | "/"

type:   expr1               -> type

?expr1: expr2               -> type
    | "@" expr7 expr1        -> expr_ptr
    | "|@" expr7 expr1       -> expr_pipeptr
      

?expr2: expr3               -> type
      | expr2 SIGNSUM expr3 -> expr_infix

?expr3: expr4                -> type
      | expr3 SIGNPRODUCT expr4 -> expr_infix
      | expr3 ".." expr4    -> expr_infix

?expr4: expr5                -> type
      | expr4 "|" expr5      -> type_pipe

?expr5: expr6                -> type
    | ":" NAME expr5         -> typedef
    | ":" NAME               -> typedefvoid
    | count expr5            -> type_count
    | expr5 match            -> type_match
    | expr5 "char" match     -> type_char_match
    | "<" expr5              -> type_yield
    | expr5 "->" field_name  -> type_foreign_key

expr6: expr7                 -> type
    | expr6 "." NAME         -> expr_attr
    | expr6 "[" expr1 "]"    -> expr_index

expr7: NAME                  -> expr_name
    | container              -> type_container
    | NUM                    -> expr_int
    | "(" expr1 ")"          -> expr_bracket

typedef: ":" NAME type              -> typedef
    |    ":" NAME                   -> typedefvoid

field_name: NAME                    -> field_name
    | field_name "." field_name     -> field_name_dot
    | field_name "[]." field_name   -> field_name_array
    | "_"                           -> field_name_underscore

field: "=" type _NL+                      -> return_field
     | field_name type _NL+               -> instance_field
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

