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


REPLACE_OP_WITH_INST_CALLBACK = Callable[[ModuleType, Instruction], Instruction]
REPLACE_OP_WITH_INSTS_CALLBACK = Callable[[ModuleType, Instruction], list[Instruction]]


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


def find_inst(insts: list[Instruction], offset: int) -> int:
    """
    Find the first instruction matching the given offset

    :param insts: list of instructions
    :param offset: offset of instruction to find
    :return: index of first matching instruction, or -1 if not found
    """
    for i, inst in enumerate(insts):
        if inst.offset == offset:
            return i
    return -1


def insert_inst(patcher: InPlacePatcher, opc: ModuleType, idx: int,
                inst: Instruction, label: Optional[str], shift_line_no: bool = False):
    """
    insert instruction at idx

    :param patcher: patcher
    :param opc: the opcode map (it's a module ig)
    :param idx: the index to insert at
    :param inst: the instruction to insert
    :param label: the label to place on the instruction (if specified)
    :param shift_line_no: whether to shift the line number at the offset if any (default: False)
    """
    size = op_size(inst.opcode, opc)
    patcher.insert_inst(inst, size, idx, label, shift_line_no)


def insert_insts(patcher: InPlacePatcher, opc: ModuleType, idx: int, inst: list[Instruction],
                 label: Optional[str], shift_line_no: bool = False):
    """
    Insert multiple instructions at the given index

    :param patcher: patcher
    :param opc: the opcode map (it's a module ig)
    :param idx: the index to insert at
    :param inst: the instructions to insert
    :param label: the label to place on the first instruction (if specified)
    :param shift_line_no: whether to shift the line number at the offset if any (default: False)
    """
    for i, inst in enumerate(inst):
        if i == 0:
            insert_inst(patcher, opc, idx + i, inst, label, shift_line_no)
        else:
            insert_inst(patcher, opc, idx + i, inst, None)


def remove_insts(patcher: InPlacePatcher,
                 idx: int, count: int) -> list[tuple[Instruction, bool, Optional[str], Optional[int]]]:
    """
    remove instructions at idx

    :param patcher: patcher
    :param idx: the index to remove at
    :param count: number of instructions to remove
    :return: list of tuple of instruction, whether it needs to be backpatched,
             and label name (if any), line number (if any)
    """
    buff = []
    for _ in range(count):
        inst, backpatched, label_name, line_no = patcher.pop_inst(idx)
        buff.append((inst, backpatched, label_name, line_no))
    return buff


def replace_op_with_inst(patcher: InPlacePatcher, opc: ModuleType,
                         opname: str, callback: REPLACE_OP_WITH_INST_CALLBACK):
    """
    replace all matching op by given opname with the given instruction

    :param patcher: patcher
    :param opc: the opcode map (it's a module ig)
    :param opname: name of instruction to search
    :param callback: callback to get the instruction to replace with
    """
    while (idx := find_op(patcher.code.instructions, opname)) != -1:
        inst, _, label, line_no = patcher.pop_inst(idx)
        inst = callback(opc, inst)
        insert_inst(patcher, opc, idx, inst, label, True)
        # restore line number if any
        if line_no is not None:
            patcher.code.co_lnotab[inst.offset] = line_no


def replace_op_with_insts(patcher: InPlacePatcher, opc: ModuleType, opname: str,
                          callback: REPLACE_OP_WITH_INSTS_CALLBACK) -> int:
    """
    replace all matching op by given opname with the given instructions

    :param patcher: patcher
    :param opc: the opcode map (it's a module ig)
    :param opname: name of instruction to search
    :param callback: callback to get the instructions to replace with
    :return count of instructions replaced
    """
    count = 0
    while (idx := find_op(patcher.code.instructions, opname)) != -1:
        inst, _, label, line_no = patcher.pop_inst(idx)
        insts = callback(opc, inst)
        insert_insts(patcher, opc, idx, insts, label, True)
        # restore line number if any
        if line_no is not None:
            patcher.code.co_lnotab[inst.offset] = line_no
        count += 1
    return count
