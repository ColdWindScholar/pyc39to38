pyc39to38 - Python 3.9 to 3.8 bytecode converter
===================================================

> **Warning**
>
> This tool is still in early development, don't expect it to be useful yet.

This is a simple tool to convert Python 3.9 bytecode to 3.8.

## TODO

- [ ] except blocks
  - [x] replace `RERAISE` with `END_FINALLY`
- [ ] finally blocks
  - [x] replace <finally block 1> and `JUMP_FORWARD` with `BEGIN_FINALLY`
- [ ] compare ops
  - [x] replace `JUMP_IF_NOT_EXC_MATCH` with `COMPARE_OP 10` and `POP_JUMP_IF_FALSE`
- [ ] list creation
  - [x] replace `LIST_EXTEND 1` (followed by an empty list creation and a `LOAD_CONST <tuple>`) 
        with multiple `LOAD_CONST` and `BUILD_LIST <tuple size>`

## BUGS

- [ ] except with `else` block
- [ ] except with `as` keyword

## Usage

```shell
$ python -m pyc39to38 path/to/file.pyc your/output.pyc
```

## Why?

Decompiler like [uncompyle6][uncompyle6] doesn't support Python 3.9 yet.\
This tool can be used to convert the bytecode to 3.8 then you can decompile it.

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
