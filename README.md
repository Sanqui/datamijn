Datamijn
========

Finally, _painless_ datamining of ROMs.

Datamijn is primarily a domain-specific language for describing
binaries.  It's meant to be as concise as possible.  You know
what the data looks like and you just want YAML out of it.
Datamijn won't make you write any boilerplate.

A datamijn definition file is natural to write and read.  Example:

```
position {
    x       u8
    y       u8
}

_start       {
    version     u16
    positions   [8]position
}
```

In this `.dm` file, we describe a type, "coords", consisting of
two bytes.  We then describe how to parse the binary from the
beginning.

Is `position` only used once?  No problem.  In datamijn, you can
always define a type anonymously.

```
version     u16
positions   [8]{
    x           u8
    y           u8
}
```

In this example, we haven't defined `_start`, so datamijn starts
parsing the file from the first field.

Acknowledgements
----------------

Datamijn uses [Lark](https://github.com/erezsh/lark) to parse
its DSL, while all the binary parsing duty falls on [Construct](https://github.com/construct/construct/).  So it doesn't actually do much.

