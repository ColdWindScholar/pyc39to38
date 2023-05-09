"""
patcher
"""

from typing import Optional
from types import ModuleType

from xdis.codetype.code38 import Code38
from .utils import Instruction
from xdis.cross_dis import op_size
from xasm.assemble import is_int


# making IDE happy
# TODO: NOT PORTABLE? what is the correct way to do this?
class Code38WithInstructions(Code38):
    instructions: list[Instruction]


class InPlacePatcher:
    """
    patch stuffs in place
    """

    def __init__(self, opc: ModuleType, code: Code38WithInstructions,
                 label: dict[str, int], backpatch_inst: set[Instruction]):
        # opcode map (it's a module ig)
        self.opc = opc
        # code.co_lnotab is a dict[int, int], where the first int is offset, the second is line_no
        self.code = code
        # label is a dict[str, int], where str is label name, int is offset
        self.label = label
        # a set of jump instructions with string label as target,
        # these have to be patched to int offset later in create_code
        self.backpatch_inst = backpatch_inst

    def get_inst2label(self, idx: int) -> dict[Instruction, str]:
        """
        get a dict of instruction to label name

        :param idx: start index of instruction to iterate
        :return: dict of instruction to label name
        """
        inst2label = {}
        for inst in self.code.instructions[idx:]:
            for _label, _offset in self.label.items():
                if _offset == inst.offset:
                    inst2label[inst] = _label
                    break
        return inst2label

    def need_backpatch(self, inst: Instruction) -> bool:
        """
        check if instruction needs backpatching

        :param inst: instruction to check
        :return: whether it needs backpatching
        """
        if inst.opcode in self.opc.JUMP_OPS:
            if not is_int(inst.arg):
                return True
        return False

    def shift_line_no(self, offset: int, val: int, allow_equal: bool = False):
        """
        shift line number in co_lnotab after offset

        :param offset: offset to start shifting
        :param val: value to shift
        :param allow_equal: also shift the line number at offset if any (default: False)
        """
        # find the nearest line_no at offset
        offs = sorted(self.code.co_lnotab.keys())
        for i, off in enumerate(offs):
            next_off = offs[i + 1] if i + 1 < len(offs) else None
            if (off > offset or (allow_equal and off == offset)) and (next_off is None or off < next_off):
                break
        else:
            return
        for j in range(i, len(offs)):
            off = offs[j]
            line_no = self.code.co_lnotab.pop(off)
            self.code.co_lnotab[off + val] = line_no

    def pop_inst(self, idx: int) -> (Instruction, bool, Optional[str], Optional[int]):
        """
        remove instruction at idx

        NOTE: you must add another instruction if the label is used anywhere else
              or this can fail when re-assembling

        :param idx: index of instruction to remove
        :return: removed instruction, whether it is in backpatch_inst,
                 and label name if present, line number (if any)
        """
        # backup inst to label mapping
        old_inst2label = self.get_inst2label(idx + 1)

        popped_inst = self.code.instructions.pop(idx)

        backpatch = popped_inst in self.backpatch_inst
        if backpatch:
            self.backpatch_inst.remove(popped_inst)

        # remove label if present
        label = None
        for _label, _offset in self.label.items():
            if _offset == popped_inst.offset:
                label = _label
                break
        if label is not None:
            del self.label[label]

        # get the size of the popped instruction
        size = op_size(popped_inst.opcode, self.opc)

        # adjust offset of all instructions after popping
        for inst in self.code.instructions[idx:]:
            inst.offset -= size
            _label = old_inst2label.get(inst)
            if _label is not None:
                self.label[_label] = inst.offset

        # remove line number at offset if any
        line_no = None
        if popped_inst.offset in self.code.co_lnotab.keys():
            line_no = self.code.co_lnotab.pop(popped_inst.offset)

        # shift line number
        self.shift_line_no(popped_inst.offset, -size)

        return popped_inst, backpatch, label, line_no

    def insert_inst(self, inst: Instruction, size: int, idx: int,
                    label: Optional[str] = None, shift_line_no: bool = False):
        """
        insert instruction at idx

        :param inst: instruction to insert
        :param size: size of the instruction
        :param idx: index to insert at
        :param label: label name, None means not to add label
        :param shift_line_no: whether to shift the line number at the offset if any (default: False)

        :raises ValueError: if a label with the same name already exists
        """
        # backup inst to label mapping
        old_inst2label = self.get_inst2label(idx)

        # first calc offset for the inserting instruction
        last_inst = self.code.instructions[idx - 1]
        last_offset = last_inst.offset
        last_size = op_size(last_inst.opcode, self.opc)
        offset = last_offset + last_size
        inst.offset = offset

        self.code.instructions.insert(idx, inst)

        # add to backpatch if needed
        if self.need_backpatch(inst):
            self.backpatch_inst.add(inst)

        # add label if present
        if label is not None:
            if label in self.label:
                raise ValueError('Label %r already exists' % label)
            else:
                self.label[label] = offset

        # adjust offset of all instructions after insertion
        for _inst in self.code.instructions[idx + 1:]:
            _inst.offset += size
            _label = old_inst2label.get(_inst)
            if _label is not None:
                self.label[_label] = _inst.offset

        # shift line number
        self.shift_line_no(offset, size, shift_line_no)

    def fix_label(self):
        """
        fix label names

        :raises ValueError: if label already exists (well, it shouldn't. if it does, it's our bug)
        """
        new_label = {}
        for _label, _offset in self.label.items():
            pretty = f'L{_offset}'
            if pretty in new_label:
                raise ValueError('Label %r already exists' % pretty)
            else:
                new_label[pretty] = _offset
        self.label = new_label

    def fix_backpatch(self):
        """
        fix backpatch tags
        """
        for inst in self.backpatch_inst:
            _label = inst.arg
            label = self.label[_label]
            new = f'L{label}'
            if new != _label:
                inst.arg = new

    def fix_line_no(self):
        """
        fix line numbers
        """
        rest = self.code.instructions.copy()
        rest.sort(key=lambda x: x.offset)
        offs = sorted(self.code.co_lnotab.keys())
        for i, off in enumerate(offs):
            next_off = offs[i + 1] if i + 1 < len(offs) else None
            for j, inst in enumerate(rest):
                if inst.offset >= off and (next_off is None or inst.offset < next_off):
                    inst.line_no = self.code.co_lnotab[off]
                else:
                    break
            else:
                break
            rest = rest[j + 1:]

    def fix_all(self):
        """
        fix all
        """
        self.fix_backpatch()
        self.fix_label()
        self.fix_line_no()
