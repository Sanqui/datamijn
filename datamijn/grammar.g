%import common.CNAME -> NAME
%import common.WS_INLINE
%ignore WS_INLINE

DIGIT: "0".."9"
HEXDIGIT: "a".."f"|"A".."F"|DIGIT
INT: "0x" HEXDIGIT+|DIGIT+
SIGNED_INT: ["+"|"-"] INT
NUM: INT | SIGNED_INT
EXPR: NUM

STRING_DBL: /"(\\\"|[^"])+"/
STRING_SNG: /'(\\'|[^'])+'/

string: STRING_DBL
      | STRING_SNG

num: EXPR

match_key: num "=>"        -> match_key_int
    | num ".." num "=>"    -> match_key_range
    | string "=>"          -> match_key_string
    | NAME "=>"            -> match_key_default_name
    | "_" "=>"             -> match_key_default

match_field: match_key? expr        _NL+

match: "match" "{" _NL match_field+ "}"

container: "{" _NL+ field* "}"

count: "[" expr2 "]"
     | "[" "]"

SIGNSUM: "+" | "-"
SIGNPRODUCT: "*" | "/" | "%"
SIGNEQ: "!=" | "=="

expr:   expr1                   -> expr

?expr1: expr2                   -> expr
    | "@" expr6 expr1           -> expr_ptr
    | "|@" expr6 expr1          -> expr_pipeptr
    | "<" expr2                 -> expr_yield
    | expr1 SIGNEQ expr2        -> expr_infix
      

?expr2: expr3                   -> expr
      | expr2 SIGNSUM expr3     -> expr_infix

?expr3: expr4                   -> expr
      | expr3 SIGNPRODUCT expr4 -> expr_infix
      | expr3 ".." expr4        -> expr_infix

?expr4: expr5                   -> expr
      | expr4 "|" expr5         -> expr_pipe

?expr5: expr6                   -> expr
    | expr5 NAME                -> expr_inherit
    | ":" NAME expr5            -> expr_typedef
    | ":" NAME                  -> expr_typedeftoken
    | count expr1               -> expr_count
    | expr5 match               -> expr_match
    | expr5 "char" match        -> expr_char_match
    | expr5 "->" field_name     -> expr_foreign_key

expr6: expr7                    -> expr
    | expr6 "[" expr1 "]"       -> expr_index

expr7: expr8                    -> expr
    | expr6 "." NAME            -> expr_attr

expr8: NAME                     -> expr_name
    | container                 -> expr_container
    | NUM                       -> expr_int
    | string                    -> expr_string
    | "(" expr1 ")"             -> expr_bracket

typedef: ":" NAME expr              -> expr_typedef
    |    ":" NAME                   -> expr_typedeftoken

field_name: NAME                    -> field_name
    | field_name "." field_name     -> field_name_dot
    | field_name "[]." field_name   -> field_name_array
    | "_"                           -> field_name_underscore

field: "=" expr _NL+                      -> field_return
     | field_name expr _NL+               -> field_instance
     | typedef _NL+                       -> field_typedef
     | "!if" expr container ("!else" container)? _NL+ -> field_if
     | /\!assert(.*)/ _NL+                -> field_assert
     | "!save" field_name _NL+            -> field_save
     | "!debug" field_name _NL+           -> field_debug
     | "<" expr _NL+                      -> field_yield

COMMENT: /\/\/.*/
_NL: COMMENT? /(\r?\n[\t ]*)+/

?topstatement: "!import" NAME _NL+  -> statement_import
             | "!symfile" NAME _NL+ -> statement_symfile
             | field

start: _NL* topstatement*           -> container

