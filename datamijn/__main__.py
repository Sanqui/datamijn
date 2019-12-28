import click

from datamijn.parsing import parse_definition, parse

DATAMIJN_OUTPUTS = ["pretty_repr", "repl", "ipython", "browser"]

@click.command('datamijn')
@click.argument('struct-filename', type=click.Path(exists=True))
@click.argument('binary-filename', type=click.Path(exists=True))
@click.argument('output', type=click.Choice(DATAMIJN_OUTPUTS), default="pretty_repr")
@click.option('-p', '--show-private', is_flag=True)
@click.option('-l', '--lenient', is_flag=True)
def cli(struct_filename, binary_filename, output, show_private, lenient):
    struct_file = open(struct_filename, 'r')
    binary_file = open(binary_filename, 'rb')
    result = parse(struct_file, binary_file, lenient=lenient)

    if output == "pretty_repr":
        print(result._pretty_repr())
    elif output == "browser":
        binary_file = open(binary_filename, "rb")
        from datamijn.browser import DatamijnBrowser
        DatamijnBrowser(result, file=binary_file, binary_filename=binary_filename, show_private=show_private).main()
    elif output == "repl":
        print("The result of the parse is available under `result`.")
        import code
        code.interact(local=locals())
    elif output == "ipython":
        print("The result of the parse is available under `result`.")
        import IPython
        IPython.embed()
    else:
        print(f"Unknown output mode {output_mode}")

    #print(yaml.dump(result._python_value()))
    #print(yaml.dump(result))


if __name__ == '__main__':
    cli()
