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
    Tuple
)
from types import ModuleType

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


def find_lino_no(lnotab: dict[int, int], offset: int) -> int:
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
