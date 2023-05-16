"""
scanning
"""

from typing import (
    Optional,
    List,
    TypeVar
)

from .patch import InPlacePatcher
from .insts import find_inst
from .utils import find_lino_no


SETUP_FINALLY = 'SETUP_FINALLY'
POP_BLOCK = 'POP_BLOCK'
JUMP_FORWARD = 'JUMP_FORWARD'
END_FINALLY = 'END_FINALLY'

UNCONFIRMED = -1
UNINITED = None


class Scope:
    """
    info of a "finally" block
    """
    def __init__(self, start: int, end: int, length: int):
        self.start = start
        self.end = end
        self.length = length

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(start={self.start}, end={self.end}, length={self.length})'


class FinallyBlock(Scope):
    """
    info of a "finally" block
    """
    pass


class _Finally:
    """
    info of a "finally" structure
    """
    def __init__(self, start: int, pop_block: int, scope: Optional[Scope],
                 block1: Optional[FinallyBlock], jump_forward: int,
                 block2: Optional[FinallyBlock], end_finally: int):
        self.setup_finally = start
        self.pop_block = pop_block
        self.scope = scope
        self.block1 = block1
        self.jump_forward = jump_forward
        self.block2 = block2
        self.end_finally = end_finally

    def __repr__(self) -> str:
        return (
            f'_Finally(start={self.setup_finally}, pop_block={self.pop_block}, \n'
            f'    scope={self.scope}, block1={self.block1}, jump_forward={self.jump_forward}, \n'
            f'    block2={self.block2}, end_finally={self.end_finally})\n'
        )


_FinallyInfo = TypeVar('_FinallyInfo', bound='FinallyInfo')


class FinallyInfo:
    def __init__(self, obj: _Finally, scope_children: List[_FinallyInfo], block1_children: List[_FinallyInfo],
                 block2_children: List[_FinallyInfo]):
        self.obj = obj
        self.scope_children = scope_children
        self.block1_children = block1_children
        self.block2_children = block2_children


def scan_finally(patcher: InPlacePatcher) -> List[_Finally]:
    """
    scan "finally" structures

    POP_BLOCK should be only used for exception handling ig

    :raises ValueError: if failed to parse "finally" scopes
    :raises TypeError: if failed to parse "finally" blocks
    """
    # stack for determining the scope of each "finally" block
    finally_stack = []
    # pending "finally" blocks
    finally_objs = []

    # find the scope of each "finally" block
    for i, inst in enumerate(patcher.code.instructions):
        if inst.opname == SETUP_FINALLY:  # the start of a "finally" block
            finally_obj = _Finally(i, UNCONFIRMED, UNINITED, UNINITED,
                                   UNCONFIRMED, UNINITED, UNCONFIRMED)
            # dereference the label and find the first instruction of the "finally" block2
            block2_first_inst_offset = patcher.label[inst.arg]
            block2_first_inst = find_inst(patcher.code.instructions, block2_first_inst_offset)
            if block2_first_inst == -1:
                raise ValueError(
                    f'cannot find block2 for "finally" at {finally_obj.setup_finally}'
                )
            # leave the end of block2 unconfirmed
            finally_obj.block2 = FinallyBlock(block2_first_inst, UNCONFIRMED, UNCONFIRMED)
            finally_stack.append(finally_obj)
        elif inst.opname == POP_BLOCK:  # the end of the scope of a "finally" block
            try:
                finally_obj = finally_stack.pop()
            except IndexError:
                raise ValueError(
                    f'unmatched "finally" at {i}'
                )
            finally_obj.pop_block = i
            # end - start + 1 = length
            scope_len = finally_obj.pop_block - finally_obj.setup_finally - 1
            finally_obj.scope = Scope(finally_obj.setup_finally + 1, finally_obj.pop_block - 1, scope_len)
            finally_objs.append(finally_obj)

    # if the stack is not empty, something unexpected happened
    if finally_stack:
        raise ValueError(
            f'unmatched "finally", the first one is at {finally_stack[0].setup_finally}'
        )

    # to remove those are not "finally", we need to prepare a list
    remove = []

    for i, finally_obj in enumerate(finally_objs):
        # there's a JUMP_FORWARD before the "finally" block2
        finally_obj.jump_forward = finally_obj.block2.start - 1
        if finally_obj.jump_forward == finally_obj.pop_block:
            # if the JUMP_FORWARD doesn't exist, and it's the same as the POP_BLOCK
            # it's not a "finally", but an "except" without "finally"
            remove.append(i)
            continue
        elif patcher.code.instructions[finally_obj.jump_forward].opname != JUMP_FORWARD:
            raise TypeError(
                f'"except/finally" {finally_obj.setup_finally} is invalid, '
                f'{finally_obj.jump_forward} should be JUMP_FORWARD or POP_BLOCK, '
                f'but it\'s {patcher.code.instructions[finally_obj.jump_forward].opname}'
            )
        # the "finally" block1 stays between POP_BLOCK and JUMP_FORWARD
        block1_len = finally_obj.jump_forward - finally_obj.pop_block - 1
        if block1_len == 0:
            # if block1's length is 0, it's not a "finally", but an "except" with "finally"
            remove.append(i)
            continue
        finally_obj.block1 = FinallyBlock(finally_obj.pop_block + 1, finally_obj.jump_forward - 1, block1_len)
        # the "finally" block1 should be the same as the "finally" block2, so the length should be the same
        finally_obj.block2.end = finally_obj.block2.start + block1_len - 1
        finally_obj.block2.length = block1_len
        # the "finally" block2 is between JUMP_FORWARD and END_FINALLY
        # but, we need to compare every instruction with block1 for safety
        for j, inst in enumerate(patcher.code.instructions[finally_obj.block2.start:finally_obj.block2.end + 1]):
            block1_inst = patcher.code.instructions[finally_obj.block1.start + j]
            # find the line number of the instruction
            inst_line_no = find_lino_no(patcher.code.co_lnotab, inst.offset)
            block1_inst_line_no = find_lino_no(patcher.code.co_lnotab, block1_inst.offset)
            if inst.opname != block1_inst.opname or inst_line_no != block1_inst_line_no:
                raise TypeError(
                    f'"finally" {finally_obj.setup_finally} is invalid, block2 inst #{j} is different from block1. '
                    f'finally: {finally_obj}'
                )
            if patcher.need_backpatch(inst):  # if the inst is a jump, we need to calculate the relative offset
                # dereference the label and find the target instruction
                jump_target_inst = patcher.label[inst.arg]
                # calculate the relative offset
                relative_offset = jump_target_inst - inst.offset
                # also calculate for the block1 inst
                block1_jump_target_inst = patcher.label[block1_inst.arg]
                block1_relative_offset = block1_jump_target_inst - block1_inst.offset
                # check if they are the same
                if relative_offset != block1_relative_offset:
                    # this means the "finally" block2 is not the same as the "finally" block1
                    raise TypeError(
                        f'"finally" {finally_obj.setup_finally} is invalid, block2 inst #{j} is a jump, '
                        f'but the relative offset {relative_offset} is different from {block1_relative_offset}. '
                        f'finally: {finally_obj}'
                    )
            elif inst.arg != block1_inst.arg:
                # if the inst is not a jump, we just need to check the argument
                raise TypeError(
                    f'"finally" {finally_obj.setup_finally} is invalid, block2 inst #{j} has a different argument '
                    f'{inst.arg} from block1 ({block1_inst.arg}). '
                    f'finally: {finally_obj}'
                )
        # the next instruction of the "finally" block2 should be END_FINALLY
        finally_obj.end_finally = finally_obj.block2.end + 1
        if patcher.code.instructions[finally_obj.end_finally].opname != END_FINALLY:
            raise TypeError(
                f'"finally" {finally_obj.setup_finally} is invalid, {finally_obj.end_finally} should be END_FINALLY. '
                f'finally: {finally_obj}'
            )

    # remove those are not "finally"
    for i in reversed(remove):
        finally_objs.pop(i)

    return finally_objs


def parse_finally_info(finally_objs: List[_Finally], sort: bool = True) -> List[FinallyInfo]:
    """
    parse hierarchy information for given "finally" objects
    """
    if sort:
        # sort the "finally" objects by start position
        finally_objs.sort(key=lambda x: x.setup_finally)

    # the first "finally" object is definitely one of the root "finally" objects
    one_root_obj = finally_objs.pop(0)

    # let's see what are the children of the first "finally" object
    scope_children_obj = []
    block1_children_obj = []
    block2_children_obj = []
    remove = []

    # iterate through the rest of the "finally" objects
    for i, finally_obj in enumerate(finally_objs):
        # if this "finally" object is a "scope" child of the root "finally" object
        if one_root_obj.scope.start <= finally_obj.setup_finally <= one_root_obj.scope.end:
            scope_children_obj.append(finally_obj)
        # if this "finally" object is a "block1" child of the root "finally" object
        elif one_root_obj.block1.start <= finally_obj.setup_finally <= one_root_obj.block1.end:
            block1_children_obj.append(finally_obj)
        # if this "finally" object is a "block2" child of the root "finally" object
        elif one_root_obj.block2.start <= finally_obj.setup_finally <= one_root_obj.block2.end:
            block2_children_obj.append(finally_obj)
        else:
            continue
        # remove it from the list if it's a child
        remove.append(i)

    # remove those are children
    for i in reversed(remove):
        finally_objs.pop(i)

    # recursively parse the children
    one_root_info = FinallyInfo(
        obj=one_root_obj,
        scope_children=parse_finally_info(scope_children_obj, sort=False) if scope_children_obj else [],
        block1_children=parse_finally_info(block1_children_obj, sort=False) if block1_children_obj else [],
        block2_children=parse_finally_info(block2_children_obj, sort=False) if block2_children_obj else []
    )

    # result
    finally_infos = [one_root_info]

    # if there's still "finally" objects left, it means there's more than one root "finally" object
    if finally_objs:
        # recursively parse the next root "finally" object as well as its children
        finally_infos.extend(parse_finally_info(finally_objs, sort=False))

    return finally_infos
