"""
utility functions
"""

from os.path import (
    basename,
    extsep
)
from typing import Union
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


def recalc_idx(history: list[tuple[int, int]], idx: int) -> int:
    """
    Recalculate index after patching

    :param history: list of (idx, add/removed count)
    :param idx: index to recalculate
    :return: recalculated index
    """
    for _idx, _count in history:
        if idx > _idx:
            idx += _count
    return idx
