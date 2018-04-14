%import common.CNAME -> NAME
%import common.WS_INLINE
%ignore WS_INLINE

_NL: /(\r?\n[\t ]*)+/

?start: _NL* field*

?field: name type _NL   -> field

?name: NAME

?type: NAME                -> type
    | "{" _NL field+ "}"   -> typedef

