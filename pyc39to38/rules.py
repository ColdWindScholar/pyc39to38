"""
patching rules - NOT PORTABLE
"""

from types import ModuleType
from typing import (
    List,
    Dict,
    Tuple
)

from xdis.disasm import get_opcode

from .utils import (
    build_inst,
    Instruction,
    recalc_idx,
    HISTORY
)
from .patch import InPlacePatcher
from .insts import (
    replace_op_with_insts,
    replace_op_with_inst,
    remove_insts,
    insert_inst
)
from .scan import (
    scan_finally,
    parse_finally_info,
    FinallyInfo
)
from . import PY38_VER


# args: (patcher, is_pypy)
# no return value
RULE_APPLIER = [[InPlacePatcher, bool], None]

# mapping of opname to (compare op arg, extra_opname)
COMPARE_OPS: Dict[str, Tuple[int, str]] = {
    'JUMP_IF_NOT_EXC_MATCH': (10, 'POP_JUMP_IF_FALSE')
}

COMPARE_OP = 'COMPARE_OP'

RERAISE = 'RERAISE'
END_FINALLY = 'END_FINALLY'
BEGIN_FINALLY = 'BEGIN_FINALLY'


def compare_op_callback(opc: ModuleType, inst: Instruction) -> List[Instruction]:
    compare_op_arg, extra_opname = COMPARE_OPS[inst.opname]
    compare_op_inst = build_inst(opc, COMPARE_OP, compare_op_arg)
    extra_inst = build_inst(opc, extra_opname, inst.arg)
    return [compare_op_inst, extra_inst]


def reraise_callback(opc: ModuleType, inst: Instruction) -> Instruction:
    return build_inst(opc, END_FINALLY, inst.arg)


def do_38_to_39_finally(patcher: InPlacePatcher, is_pypy: bool, opc: ModuleType,
                        history: HISTORY, finally_infos: List[FinallyInfo]):
    """
    fix finally blocks for 3.8 bytecode
    """
    children: List[FinallyInfo] = []

    for finally_info in finally_infos:
        # remove block1 and jump_forward
        count = finally_info.obj.block1.length + 1
        insts = remove_insts(patcher, recalc_idx(history, finally_info.obj.block1.start), count)
        history.append((finally_info.obj.block1.start, -count))
        # add BEGIN_FINALLY at there
        inst = build_inst(opc, BEGIN_FINALLY, None)
        insert_inst(patcher, opc, recalc_idx(history, finally_info.obj.block1.start), inst, None, True)
        history.append((finally_info.obj.block1.start, 1))
        # restore line number if any
        line_nos = []
        for _, _, _, line_no in insts:
            if line_no:
                line_nos.append(line_no)
        # check if there is any line number
        if line_nos:
            # find the smallest line number, then set it
            min_line_no = min(line_nos)
            block2_first_inst = patcher.code.instructions[recalc_idx(history, finally_info.obj.block2.start)]
            patcher.code.co_lnotab[block2_first_inst.offset] = min_line_no
        # fix everything in scope or block2
        if finally_info.scope_children:
            children.extend(finally_info.scope_children)
        if finally_info.block2_children:
            children.extend(finally_info.block2_children)

    # recursively fix children
    if children:
        do_38_to_39_finally(patcher, is_pypy, opc, history, children)


def do_39_to_38(patcher: InPlacePatcher, is_pypy: bool):
    """
    apply patches for adapting 3.9 bytecode to 3.8
    """
    opc = get_opcode(PY38_VER, is_pypy)
    for op in COMPARE_OPS.keys():
        replace_op_with_insts(patcher, opc, op, compare_op_callback)
    replace_op_with_inst(patcher, opc, RERAISE, reraise_callback)
    # do this at last, because it may introduce some messes
    # unless you want to recalc all the indexes
    finally_objs = scan_finally(patcher)
    finally_infos = parse_finally_info(finally_objs)
    history: HISTORY = []
    do_38_to_39_finally(patcher, is_pypy, opc, history, finally_infos)
