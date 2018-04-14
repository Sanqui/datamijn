%import common.CNAME -> NAME
%import common.WS_INLINE
%import common.NUMBER
%ignore WS_INLINE

_NL: /(\r?\n[\t ]*)+/

?start: _NL* field*

?field: name type _NL          -> field
      | name count type _NL    -> field_array

?name: NAME

?type: NAME                -> type
    | "{" _NL field+ "}"   -> typedef

?count: "[" NUMBER "]"
