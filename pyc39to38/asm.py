"""
assembly related operations
"""

from tempfile import NamedTemporaryFile
from traceback import print_exc
from os import unlink
from logging import getLogger
from struct import pack
from typing import Optional

from xdis.disasm import (
    disassemble_file,
    get_opcode
)
from xasm.assemble import (
    asm_file,
    Assembler
)
from xasm.write_pyc import write_pycfile

from .utils import rm_suffix
from .walk import walk_codes
from .rules import RULE_APPLIER
from . import (
    FILE_ENCODING,
    PYASM_SUFFIX,
    PY38_VER,
    PY39_VER
)


logger = getLogger('asm')

SOURCE_SIZE_OFF = 12
SOURCE_SIZE_FMT = '<I'


def reasm_file(input_path: str, output_path: str, rule_applier: RULE_APPLIER) -> bool:
    """
    reassemble a Python bytecode file

    :param input_path: input file path
    :param output_path: output file path
    :param rule_applier: rule applier
    :return: True if success, False if failed
    """
    version: tuple[int, ...]
    timestamp: int
    asm: Assembler
    tmp_asm: Optional[NamedTemporaryFile] = None

    try:
        with NamedTemporaryFile(
            'w', suffix=PYASM_SUFFIX,
            prefix=rm_suffix(input_path),
            delete=False,
            encoding=FILE_ENCODING
        ) as tmp_asm:
            (
                _, _, version, timestamp, _, is_pypy, _, _
            ) = disassemble_file(input_path, tmp_asm, 'xasm')

        if version != PY39_VER:
            logger.error('input bytecode version is not 3.9, aborting')
            return False

        asm = asm_file(tmp_asm.name)
    except (OSError, IOError):
        print_exc()
        return False
    finally:
        # TODO: do we still need tmp_asm for trans_asm and write_pycfile?
        if tmp_asm is not None:
            unlink(tmp_asm.name)  # anyway, we are removing it here, seems OK

    opc = get_opcode(version, is_pypy)
    new_asm = walk_codes(opc, asm, is_pypy, rule_applier)

    try:
        with open(output_path, 'wb') as fp:
            write_pycfile(fp, new_asm.code_list, timestamp, PY38_VER)
            # write_pycfile writes a zero, in our case it's better to write the real size
            fp.seek(SOURCE_SIZE_OFF)
            fp.write(pack(SOURCE_SIZE_FMT, new_asm.size))
    except (OSError, IOError):
        print_exc()
        return False
    else:
        return True
