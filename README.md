Datamijn
========

Finally, _painless_ datamining of ROMs.

Datamijn is primarily a domain-specific language for describing
binaries.  It's meant to be as concise as possible.  You know
what the data looks like and you just want YAML out of it.
Datamijn won't make you write any boilerplate.

A datamijn definition file is natural to write and read.  Example:

```
:Coordinate {
    x       u8
    y       u8
}

version     u16
count       u16
cordinates  [count]Coordinate
```

In this `.dm` file, we describe a type, "Coordinate", consisting of
two bytes.  We then describe how to parse the binary from the
beginning.

Is `Coordinate` only used once?  No need to pollute your namespace.
In datamijn, you can always define a type inline.

```
version     u16
count       u16
coordinates [count]{
    x           u8
    y           u8
}
```

A binary file parsed with such a definition might end up looking
like this pleasant YAML.

```yaml
version: 1
count: 6
positions:
- x: 20
  y: 26
- x: 8
  y: 60
...
```

**Datamijn is not stable!**  The language and API will change
on a whim depending on what Sanqui likes and needs (until v1.0).

Acknowledgements
----------------

Datamijn uses [Lark](https://github.com/erezsh/lark) to parse
its DSL.

The project uses [Pipenv](https://github.com/pypa/pipenv) because
it's 2018.

I'm also currently using a fork of PyYAML with support for not
sorting dict keys.
