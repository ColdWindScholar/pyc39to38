"""
code walker
"""

from copy import copy
from types import ModuleType
from traceback import print_exc
from typing import (
    Optional,
    Set,
    List,
    Tuple,
    Dict
)
from logging import getLogger

from xasm.assemble import (
    Assembler,
    create_code,
    decode_lineno_tab
)
from xdis.cross_dis import op_size
from xdis.codetype.code38 import Code38
from xdis.codetype.base import iscode

from .utils import (
    Instruction,
    HISTORY,
    recalc_idx,
    build_inst
)
from .patch import InPlacePatcher
from .rules import RULE_APPLIER
from . import PY38_VER


logger = getLogger('walk')

EXTENDED_ARG = 'EXTENDED_ARG'


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

    methods: Dict[str, Code38] = {}

    for code_idx, old_code in enumerate(asm.codes):
        new_code = copy(old_code)
        new_label = copy(asm.label[code_idx])
        old_backpatch_inst = asm.backpatch[code_idx]
        new_backpatch_inst: Set[Instruction] = set()
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

        # before applying the patches, we need to remove EXTENDED_ARG
        pre_history: HISTORY = []
        # idx, label, line_no
        remove: List[int] = []
        removed: List[Tuple[int, str, int]] = []
        for inst_idx, inst in enumerate(patcher.code.instructions):
            if inst.opname == EXTENDED_ARG:
                remove.append(inst_idx)
        for inst_idx in remove:
            idx = recalc_idx(pre_history, inst_idx)
            _, _, label, line_no = patcher.pop_inst(idx)
            pre_history.append((inst_idx, -1))
            removed.append((idx, label, line_no))
        for removed_inst_idx, label, line_no in removed:
            next_inst = patcher.code.instructions[removed_inst_idx]
            # if the removed inst has a label, we need some extra handling
            if label:
                # if next inst has label, we need to redirect all reference of the original label to it
                for iterating_label, label_off in patcher.label.items():
                    if label_off == next_inst.offset:
                        # replace all reference of the original label to the label of next inst
                        for inst in patcher.code.instructions:
                            if patcher.need_backpatch(inst):
                                # this inst has a label as arg
                                if inst.arg == label:
                                    inst.arg = iterating_label
                        break
                else:
                    # no label found for next inst, just add the original label back to there
                    patcher.label[label] = next_inst.offset
            # restore the line number if needed
            if line_no:
                patcher.code.co_lnotab[next_inst.offset] = line_no

        try:
            rule_applier(patcher, is_pypy)
        except (ValueError, TypeError):
            logger.error(f'failed to apply rules for code #{code_idx}:')
            print_exc()
            return None

        # add back the EXTENDED_ARG where needed
        while True:
            post_history: HISTORY = []
            dirty_insert = False
            for inst_idx, inst in enumerate(patcher.code.instructions.copy()):
                if patcher.need_backpatch(inst):
                    # this inst has a label as arg
                    # deref the label
                    label_off = patcher.label[inst.arg]
                    # recalc the idx
                    idx = recalc_idx(post_history, inst_idx)
                    # calculate the real arg
                    if inst.opcode in opc.JREL_OPS:
                        arg = label_off - inst.offset - op_size(inst.opcode, opc)
                    elif inst.opcode in opc.JABS_OPS:
                        arg = label_off
                    else:
                        raise ValueError(f'unsupported jump opcode {inst.opname} at idx {idx} in code #{code_idx}')
                    # if the arg is bigger than one byte, we need to add EXTENDED_ARG
                    # the arg for EXTENDED_ARG is how many extra bytes we need to extend
                    if arg > 255:
                        # check if we already have an EXTENDED_ARG on top
                        last_inst = patcher.code.instructions[idx - 1]
                        if last_inst.opname == EXTENDED_ARG:
                            # this is after the first run, we need to update the arg
                            last_inst.arg = arg // 256
                        else:
                            # we need to add EXTENDED_ARG
                            size = op_size(opc.opmap[EXTENDED_ARG], opc)
                            extended_arg_inst = build_inst(patcher.opc, EXTENDED_ARG, arg // 256)
                            patcher.insert_inst(extended_arg_inst, size, idx)
                            dirty_insert = True
                            post_history.append((inst_idx, 1))
                            # if the next inst has a label, move it to here
                            next_inst = patcher.code.instructions[idx + 1]
                            # iterate all labels
                            for iterating_label, label_off in patcher.label.items():
                                if label_off == next_inst.offset:
                                    # set the offset to this inst
                                    patcher.label[iterating_label] = extended_arg_inst.offset
                                    break
            if not dirty_insert:
                break

        try:
            # messes are done, fix the stuffs xDD
            patcher.fix_all()
        except ValueError:
            logger.error(f'failed to fix the code #{code_idx}:')
            print_exc()
            return None

        new_asm.code = new_code
        # fix the code objects in constants
        for idx, const in enumerate(new_asm.code.co_consts):
            if iscode(const):
                if const.co_name in methods:
                    new_asm.code.co_consts[idx] = methods[const.co_name]
                else:
                    logger.error(f'missing method \'{const.co_name}\' in code #{code_idx}')
                    return None
        # this assembles the instructions and writes the code.co_code
        # after that it also freezes the code object
        co = create_code(new_asm, patcher.label, patcher.backpatch_inst)
        # register the method name
        methods[co.co_name] = co
        # append data to lists, also backup the code
        # TODO: i hope i understand this correctly
        new_asm.update_lists(co, patcher.label, patcher.backpatch_inst)

    # TODO: why is this getting reversed?
    new_asm.code_list.reverse()
    # TODO: what does this do?
    new_asm.finished = 'finished'
    return new_asm
