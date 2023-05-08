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
from .pattern import replace_op_with_insts
from . import PY38_VER


RULE_APPLIER = [[InPlacePatcher, bool], None]

COMPARE_OPS: dict[str, tuple[int, str]] = {
    'JUMP_IF_NOT_EXC_MATCH': (10, 'POP_JUMP_IF_FALSE')
}

COMPARE_OP = 'COMPARE_OP'


def compare_op_callback(opc: ModuleType, inst: Instruction) -> list[Instruction]:
    compare_op_arg, extra_opname = COMPARE_OPS[inst.opname]
    compare_op_inst = build_inst(opc, COMPARE_OP, compare_op_arg)
    extra_inst = build_inst(opc, extra_opname, inst.arg)
    return [compare_op_inst, extra_inst]


def do_39_to_38(patcher: InPlacePatcher, is_pypy: bool):
    opc = get_opcode(PY38_VER, is_pypy)
    for op in COMPARE_OPS.keys():
        replace_op_with_insts(patcher, opc, op, compare_op_callback)
