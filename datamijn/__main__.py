from datamijn.parsing import parse_definition, parse

from sys import argv

struct_filename = argv[1]
binary_filename = argv[2]
if len(argv) > 3:
    output_mode = argv[3]
else:
    output_mode = "pretty_repr"

struct_file = open(struct_filename)
binary_file = open(binary_filename, "rb")

result = parse(struct_file, binary_file)

if output_mode == "pretty_repr":
    print(result._pretty_repr())
elif output_mode == "browser":
    binary_file = open(binary_filename, "rb")
    from datamijn.browser import DatamijnBrowser
    DatamijnBrowser(result, file=binary_file).main()
else:
    print(f"Unknown output mode {output_mode}")

#print(yaml.dump(result._python_value()))
#print(yaml.dump(result))

