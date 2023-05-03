"""
simple pattern matching
"""

from types import ModuleType
from typing import (
    Optional,
    Callable
)

from xdis.cross_dis import op_size

from .utils import Instruction
from .patch import InPlacePatcher


REPLACE_ONE_OP_WITH_MULTI_INST_CALLBACK = Callable[[ModuleType, Instruction], list[Instruction]]


def find_op(insts: list[Instruction], opname: str) -> int:
    """
    Find the first instruction matching the given opname

    :param insts: list of instructions
    :param opname: name of instruction to find
    :return: index of first matching instruction, or -1 if not found
    """
    for i, inst in enumerate(insts):
        if inst.opname == opname:
            return i
    return -1


def insert_multiple_insts(patcher: InPlacePatcher, opc: ModuleType,
                          idx: int, inst: list[Instruction], label: Optional[str]):
    """
    Insert multiple instructions at the given index

    :param patcher: patcher
    :param opc: the opcode map (it's a module ig)
    :param idx: the index to insert at
    :param inst: the instructions to insert
    :param label: the label to place on the first instruction (if specified)
    """
    for i, inst in enumerate(inst):
        size = op_size(inst.opcode, opc)
        if i == 0 and label is not None:
            patcher.insert_inst(inst, size, idx + i, label)
        else:
            patcher.insert_inst(inst, size, idx + i)


def replace_one_op_with_multiple_insts(patcher: InPlacePatcher, opc: ModuleType, opname: str,
                                       callback: REPLACE_ONE_OP_WITH_MULTI_INST_CALLBACK) -> int:
    """
    replace the all matching op by given opname with the given instructions

    :param patcher: patcher
    :param opc: the opcode map (it's a module ig)
    :param opname: name of instruction to search
    :param callback: callback to get the instructions to replace with
    :return count of instructions replaced
    """
    count = 0
    while (idx := find_op(patcher.code.instructions, opname)) != -1:
        inst, _, label = patcher.pop_inst(idx)
        insts = callback(opc, inst)
        insert_multiple_insts(patcher, opc, idx, insts, label)
        count += 1
    return count
