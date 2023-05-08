"""
patching rules - NOT PORTABLE
"""

from types import ModuleType

from xdis.disasm import get_opcode

from .utils import (
    build_inst,
    Instruction
)
from .patch import InPlacePatcher
from .insts import (
    replace_op_with_insts,
    replace_op_with_inst
)
from . import PY38_VER


# args: (patcher, is_pypy)
# no return value
RULE_APPLIER = [[InPlacePatcher, bool], None]

# mapping of opname to (compare op arg, extra_opname)
COMPARE_OPS: dict[str, tuple[int, str]] = {
    'JUMP_IF_NOT_EXC_MATCH': (10, 'POP_JUMP_IF_FALSE')
}

COMPARE_OP = 'COMPARE_OP'

RERAISE = 'RERAISE'
END_FINALLY = 'END_FINALLY'


def compare_op_callback(opc: ModuleType, inst: Instruction) -> list[Instruction]:
    compare_op_arg, extra_opname = COMPARE_OPS[inst.opname]
    compare_op_inst = build_inst(opc, COMPARE_OP, compare_op_arg)
    extra_inst = build_inst(opc, extra_opname, inst.arg)
    return [compare_op_inst, extra_inst]


def reraise_callback(opc: ModuleType, inst: Instruction) -> Instruction:
    return build_inst(opc, END_FINALLY, inst.arg)


def do_39_to_38(patcher: InPlacePatcher, is_pypy: bool):
    """
    apply patches for adapting 3.9 bytecode to 3.8
    """
    opc = get_opcode(PY38_VER, is_pypy)
    for op in COMPARE_OPS.keys():
        replace_op_with_insts(patcher, opc, op, compare_op_callback)
    replace_op_with_inst(patcher, opc, RERAISE, reraise_callback)
