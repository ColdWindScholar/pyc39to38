"""
utility functions
"""

from os.path import (
    basename,
    extsep
)
from typing import Union

from xasm.assemble import Instruction as InstructionStub
from xdis.instruction import Instruction as RealInstruction


# for making IDE happy again
Instruction = Union[RealInstruction, InstructionStub]


# the RealInstruction has some properties readonly, use the one from xasm, so it will work well
# TODO: is this the correct way
def build_inst(opname: str, opcode: int, arg) -> Instruction:
    stub = InstructionStub()
    stub.opname = opname
    stub.opcode = opcode
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
