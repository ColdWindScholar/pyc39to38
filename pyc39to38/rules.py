"""
patching rules - NOT PORTABLE
"""

from types import ModuleType
from typing import (
    List,
    Dict,
    Tuple
)
from warnings import warn

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
    FinallyInfo,
    scan_py39_list_from_tuple,
    Py39ListFromTuple
)
from .cfg import Config
from . import PY38_VER


# args: (patcher, is_pypy)
# no return value
RULE_APPLIER = [[InPlacePatcher, bool, Config], None]

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


def do_38_to_39_finally(patcher: InPlacePatcher, opc: ModuleType,
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
        do_38_to_39_finally(patcher, opc, history, children)


def do_38_to_39_list_creation(patcher: InPlacePatcher, opc: ModuleType, records: List[Py39ListFromTuple]):
    history: HISTORY = []
    # the const of the original tuple, the first element of the expended tuple and the elements count
    const_map: Dict[int, Tuple[int, int]] = {}
    warn_tuple = False
    for record in records:
        if record.const_idx not in const_map:
            orig_tuple = patcher.code.co_consts[record.const_idx]
            const_map[record.const_idx] = len(patcher.code.co_consts), len(orig_tuple)
            for elem in orig_tuple:
                if isinstance(elem, tuple) and not warn_tuple:
                    warn('uncompyle6 may has a bug that it may crash when tuples are in list constants.'
                         'if so please make sure you apply this patch to it before decompiling: '
                         'https://gist.github.com/ookiineko/bf87f5d52dcd983eaf9bd760436d70b2')
                    warn_tuple = True
                patcher.code.co_consts.append(elem)
        # delete the three instructions at the record
        insts = remove_insts(patcher, recalc_idx(history, record.pos), 3)
        label, line_no = insts[0][2], insts[0][3]
        first_elem, elem_count = const_map[record.const_idx]
        for i in range(elem_count):
            inst = build_inst(opc, 'LOAD_CONST', first_elem + i)
            insert_inst(patcher, opc, recalc_idx(history, record.pos) + i, inst, label if i == 0 else None)
            if i == 0 and line_no:
                patcher.code.co_lnotab[inst.offset] = line_no
        inst = build_inst(opc, 'BUILD_LIST', elem_count)
        insert_inst(patcher, opc, recalc_idx(history, record.pos + elem_count), inst, label, True)
        history.append((record.pos, -3 + elem_count + 1))


def do_39_to_38(patcher: InPlacePatcher, is_pypy: bool, cfg: Config):
    """
    apply patches for adapting 3.9 bytecode to 3.8
    """
    opc = get_opcode(PY38_VER, is_pypy)
    for op in COMPARE_OPS.keys():
        replace_op_with_insts(patcher, opc, op, compare_op_callback)
    replace_op_with_inst(patcher, opc, RERAISE, reraise_callback)
    do_38_to_39_list_creation(patcher, opc, scan_py39_list_from_tuple(patcher))
    # do this at last if you could, because it may cause some big chunk of deletions
    if not cfg.no_begin_finally:
        do_38_to_39_finally(
            patcher, opc, [],
            parse_finally_info(scan_finally(patcher))
        )
