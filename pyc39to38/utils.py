"""
utility functions
"""

from os.path import (
    basename,
    extsep
)
from typing import (
    Union,
    List,
    Tuple,
    Dict
)
from types import ModuleType
from xdis.codetype.code38 import Code38

from xasm.assemble import Instruction as InstructionStub
from xdis.instruction import Instruction as RealInstruction


# for making IDE happy again
class InstructionStubWithLineNo(InstructionStub):
    line_no: int


Instruction = Union[RealInstruction, InstructionStub, InstructionStubWithLineNo]


# the RealInstruction has some properties readonly, use the one from xasm, so it will work well
# TODO: is this the correct way
def build_inst(opc: ModuleType, opname: str, arg) -> Instruction:
    """
    Build an instruction from the given parameters
    :param opc: the opcode map (it's a module ig)
    :param opname: the name of the instruction
    :param arg: the argument for the instruction
    """
    stub = InstructionStub()
    stub.opname = opname
    stub.opcode = opc.opmap[opname]
    stub.arg = arg
    return stub


def rm_suffix(path: str, n_suffixes: int = 1) -> str:
    """
    Remove the last n suffixes from a path.
    :param path: path to remove suffixes from
    :param n_suffixes: number of suffixes to remove
    :return: path with suffixes removed
    """
    filename = basename(path)
    return filename.rsplit(extsep, n_suffixes)[0]


# idx, add/removed count
HISTORY = List[Tuple[int, int]]


def recalc_idx(history: HISTORY, idx: int) -> int:
    """
    Recalculate index after patching

    :param history: HISTORY
    :param idx: index to recalculate
    :return: recalculated index
    """
    orig_idx = idx
    for _idx, _count in history:
        if orig_idx > _idx:
            idx += _count
    return idx


def find_lino_no(lnotab: Dict[int, int], offset: int) -> int:
    """
    Find the line number for the given offset

    :param lnotab: line number table
    :param offset: offset to find line number for
    :return: line number for the given offset (or -1 if not found)
    """
    offs = sorted(lnotab.keys())
    for i, off in enumerate(offs):
        next_off = offs[i + 1] if i + 1 < len(offs) else None
        if offset >= off and (next_off is None or offset < next_off):
            return lnotab[off]
    return -1


def genlinestarts(code: Code38) -> bytes:
    """
    HACK: Generate line-number table by the given code object

    because xasm's behavior is strange, so I am doing this

    :raises ValueError: if the line-number info in code object is invalid
    """
    lnotab: Union[bytes, Dict[int, int]] = code.co_lnotab
    if isinstance(lnotab, bytes):
        # We already have a line-number table
        return lnotab
    elif len(lnotab) == 1 and lnotab[0] == code.co_firstlineno:
        # no firstlineno mismatch, the lnotab should be empty
        return b''
    else:
        out = bytearray()
        lnotab_items: List[Tuple[int, int]] = sorted(lnotab.items(), key=lambda x: x[0])
        last_offset = 0
        last_lineno = code.co_firstlineno
        for idx, (offset, lineno) in enumerate(lnotab_items):
            if idx == 0:
                if offset != 0 or lineno != code.co_firstlineno:
                    # firstlineno mismatched, need to add some entries to correct it
                    offset_inc = 0
                    lineno_inc = lineno - code.co_firstlineno
                else:
                    # no firstlineno mismatch, no need to correct at offset 0
                    continue
            else:
                offset_inc = offset - last_offset
                lineno_inc = lineno - last_lineno
            if offset_inc > 127:
                raise ValueError(f'Too long gap between two line numbers (idx={idx})')
            else:
                out.append(offset_inc)
                # ref: https://towardsdatascience.com/understanding-python-bytecode-e7edaae8734d
                neg_lineno_inc = lineno_inc < 0
                while lineno_inc < -128 if neg_lineno_inc else lineno_inc > 127:
                    out.append(255 if neg_lineno_inc else 127)
                    out.append(0)
                    if neg_lineno_inc:
                        lineno_inc += 128
                    else:
                        lineno_inc -= 127
                out.append(256 + lineno_inc if neg_lineno_inc else lineno_inc)
            last_offset = offset
            last_lineno = lineno
        return bytes(out)
