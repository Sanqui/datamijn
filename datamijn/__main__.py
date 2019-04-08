from datamijn.parsing import parse_definition, parse

from sys import argv

STRUCTF = argv[1]
FILEF = argv[2]

result = parse(open(STRUCTF), open(FILEF, "rb"))

print(result._pretty_repr())
#print(yaml.dump(result._python_value()))
#print(yaml.dump(result))
