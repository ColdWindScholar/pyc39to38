"""
CLI for pyc39to38
"""

from argparse import ArgumentParser
from os.path import (
    isfile,
    exists
)
from os import (
    stat,
    unlink
)
from logging import (
    basicConfig,
    getLogger,
    INFO
)
from typing import NoReturn

from . import (
    CLI_PROG_NAME,
    LOG_CFG,
    __version__,
    PYC_SUFFIX,
    MIN_PYC_SIZE
)
from .asm import reasm_file
from .rules import do_39_to_38
from .cfg import Config


basicConfig(level=INFO, format=LOG_CFG)
logger = getLogger(CLI_PROG_NAME)


def die(msg: str) -> NoReturn:
    logger.fatal(msg)
    exit(1)


if __name__ == '__main__':
    parser = ArgumentParser(prog=CLI_PROG_NAME,
                            description='Convert Python 3.9 bytecode file to 3.8')
    parser.add_argument('input_pyc', type=str, help='input bytecode file')
    parser.add_argument('output_pyc', type=str, help='output bytecode file')
    parser.add_argument('-f', '--force', action='store_true', help='overwrite the existing output file')
    parser.add_argument('-V', '--version', action='version', version=__version__)
    parser.add_argument('--preserve-lineno-after-extarg', action='store_true',
                        help='preserve the state that the lineno is sometimes after EXTENDED_ARG')
    parser.add_argument('--no-begin-finally', action='store_true',
                        help='do not replace <finally block 1> and JUMP_FORWARD with BEGIN_FINALLY')
    args = parser.parse_args()
    input_pyc, output_pyc, force = args.input_pyc, args.output_pyc, args.force

    if not input_pyc.endswith(PYC_SUFFIX):
        die('input file %r does not have a .pyc extension' % input_pyc)
    if not output_pyc.endswith(PYC_SUFFIX):
        die('output file %r does not have a .pyc extension' % output_pyc)

    if not isfile(input_pyc):
        die('input path %r is not a valid file' % input_pyc)
    if exists(output_pyc):
        if force:
            unlink(output_pyc)
        else:
            die('output file %r already exists' % output_pyc)

    if stat(input_pyc).st_size < MIN_PYC_SIZE:
        die('input file %r is too small to be a valid bytecode file' % input_pyc)

    cfg = Config()
    cfg.preserve_lineno_after_extarg = args.preserve_lineno_after_extarg
    cfg.no_begin_finally = args.no_begin_finally

    if reasm_file(input_pyc, output_pyc, cfg, do_39_to_38):
        logger.info('done')
    else:
        logger.error('conversion failed')
