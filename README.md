pyc39to38 - Python 3.9 to 3.8 bytecode converter
===================================================

> **Warning**
>
> This tool is still in early development, don't expect it to be useful yet.

This is a simple tool to convert Python 3.9 bytecode to 3.8.

## Usage

```shell
$ python -m pyc39to38 path/to/file.pyc your/output.pyc
```

## Why?

Many decompilers like [uncompyle6][uncompyle6] and [pycdc][pycdc] don't completely support Python 3.9 yet.\
This tool can be used to convert the bytecode to 3.8 and then you can decompile it.

## How it works

This program uses [python-xdis][xdis] to disassemble the bytecode, and then uses [python-xasm][xasm]'s assembler\
 to assemble it back to bytecode, as well as rearranges the instructions where needed.

## Credits

- [rocky/python-xdis][xdis]
- [rocky/python-xasm][xasm]

## License

GPLv2 as per [python-xdis][xdis] and [python-xasm][xasm].

Please see the [LICENSE](LICENSE.txt) file for more information.

[xdis]: https://github.com/rocky/python-xdis.git
[xasm]: https://github.com/rocky/python-xasm.git

[uncompyle6]: https://github.com/rocky/python-uncompyle6.git
[pycdc]: https://github.com/zrax/pycdc.git
