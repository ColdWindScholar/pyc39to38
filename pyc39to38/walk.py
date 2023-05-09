"""
code walker
"""

from copy import copy
from types import ModuleType
from traceback import print_exc
from typing import Optional
from logging import getLogger

from xasm.assemble import (
    Assembler,
    create_code,
    decode_lineno_tab
)
from xdis.cross_dis import op_size

from .utils import Instruction
from .patch import InPlacePatcher
from .rules import RULE_APPLIER
from . import PY38_VER


logger = getLogger('walk')


def walk_codes(opc: ModuleType, asm: Assembler, is_pypy: bool, rule_applier: RULE_APPLIER) -> Optional[Assembler]:
    """
    Walk through the codes and downgrade them

    :param opc: opcode map (it's a module ig)
    :param asm: input Assembler
    :param is_pypy: set if is PyPy
    :param rule_applier: rule applier
    :return: output Assembler, None if failed
    """

    new_asm = Assembler(PY38_VER, is_pypy)
    new_asm.size = asm.size

    for code_idx, old_code in enumerate(asm.codes):
        new_code = copy(old_code)
        new_label = copy(asm.label[code_idx])
        old_backpatch_inst = asm.backpatch[code_idx]
        new_backpatch_inst: set[Instruction] = set()
        if isinstance(old_code.co_lnotab, dict):
            # co_lnotab is already decoded
            new_code.co_lnotab = copy(old_code.co_lnotab)
        else:
            # co_lnotab is bytes, decode it
            new_code.co_lnotab = decode_lineno_tab(
                old_code.co_lnotab, old_code.co_firstlineno
            )
        new_insts = []
        for old_inst in old_code.instructions:
            new_inst = copy(old_inst)
            new_insts.append(new_inst)
            if old_inst in old_backpatch_inst:
                # restore the backpatch tag
                if new_inst.opcode in opc.JREL_OPS:
                    new_inst.arg += new_inst.offset + op_size(new_inst.opcode, opc)
                new_inst.arg = f'L{new_inst.arg}'

                new_backpatch_inst.add(new_inst)
        new_code.instructions = new_insts
        # TODO: IDK when the `instructions` is going to be removed

        # note that patch can change the label and backpatch_inst
        patcher = InPlacePatcher(opc, new_code, new_label, new_backpatch_inst)
        try:
            rule_applier(patcher, is_pypy)
        except (ValueError, TypeError):
            logger.error('failed to apply rules:')
            print_exc()
            return None

        try:
            # messes are done, fix the stuffs xDD
            patcher.fix_all()
        except ValueError:
            logger.error('failed to fix the code:')
            print_exc()
            return None

        new_asm.code = new_code
        # this assembles the instructions and writes the code.co_code
        # after that it also freezes the code object
        co = create_code(new_asm, patcher.label, patcher.backpatch_inst)
        # append data to lists, also backup the code
        # TODO: i hope i understand this correctly
        new_asm.update_lists(co, patcher.label, patcher.backpatch_inst)

    # TODO: why is this getting reversed?
    new_asm.code_list.reverse()
    # TODO: what does this do?
    new_asm.finished = 'finished'
    return new_asm
