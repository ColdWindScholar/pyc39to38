"""
some configurable options
"""


class Config:
    def __init__(self):
        # sometimes somehow the line number is after EXTENDED_ARG
        # if you hope to make sure this is persevered, set this
        self.preserve_lineno_after_extarg = False
        # disable the "finally" block patching
        self.no_begin_finally = False
