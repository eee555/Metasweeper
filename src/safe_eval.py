# Apache 2.0 licensed

"""
This module provides functions for evaluating Python code,
which is intended to be secure.

Warning: Since this module is new, its possible there are flaws in it.


How it Works
============

- Restrict built-in namespace access.
- Restrict byte-codes used.


What Works
==========

This works:

    a ** cos(b / c) - sin(d)

This will fail:

    a.b

    __import__("os").unlink("path")
"""

__all__ = (
    "safe_eval",
    "raise_if_code_unsafe",
    )

import dis
import sys
import math


builtins_whitelist = {
    # basic funcs
    "all",
    "any",
    "len",
    "max",
    "min",

    # types
    "bool",
    "float",
    "int",

    # math
    "abs",
    "divmod",
    "pow",
    "round",
    "sum",
}

if sys.version_info[0:2] == (3, 11):
    opcode_whitelist = {
        # Shared with Python 3.10.
        'POP_TOP',
        'NOP',
        'UNARY_POSITIVE',
        'UNARY_NEGATIVE',
        'UNARY_NOT',
        'UNARY_INVERT',
        'BINARY_SUBSCR',
        'RETURN_VALUE',
        'BUILD_TUPLE',
        'BUILD_LIST',
        'BUILD_SET',
        'BUILD_MAP',
        'COMPARE_OP',
        'JUMP_FORWARD',
        'JUMP_IF_FALSE_OR_POP',
        'JUMP_IF_TRUE_OR_POP',
        'LOAD_GLOBAL',
        'IS_OP',
        'LOAD_FAST',
        'STORE_FAST',
        'DELETE_FAST',
        'BUILD_SLICE',
        'LOAD_DEREF',
        'STORE_DEREF',
        'DELETE_DEREF',
        'LOAD_CONST',
        'LOAD_NAME',
        'CALL_FUNCTION_EX',

        # New in Python 3.11.
        'BINARY_OP',
        'RESUME',
        'CACHE',
        'PUSH_NULL',
        'CALL',
        'PRECALL',
        'SWAP',
        'KW_NAMES',

        'POP_JUMP_FORWARD_IF_FALSE',
        'POP_JUMP_FORWARD_IF_TRUE',
        'POP_JUMP_FORWARD_IF_NOT_NONE',
        'POP_JUMP_FORWARD_IF_NONE',
        'POP_JUMP_BACKWARD_IF_NOT_NONE',
        'POP_JUMP_BACKWARD_IF_NONE',
        'POP_JUMP_BACKWARD_IF_FALSE',
        'POP_JUMP_BACKWARD_IF_TRUE',
        'FORMAT_VALUE',
        'BUILD_STRING',
    }

elif sys.version_info[0:2] == (3, 10):
    # Python 3.10.
    opcode_whitelist = {
        '<0>',
        '<8>',
        'POP_TOP',
        'ROT_TWO',
        'ROT_THREE',
        'DUP_TOP',
        'DUP_TOP_TWO',
        'ROT_FOUR',
        'NOP',
        'UNARY_POSITIVE',
        'UNARY_NEGATIVE',
        'UNARY_NOT',
        'UNARY_INVERT',
        'BINARY_MATRIX_MULTIPLY',
        'INPLACE_MATRIX_MULTIPLY',
        'BINARY_POWER',
        'BINARY_MULTIPLY',
        'BINARY_MODULO',
        'BINARY_ADD',
        'BINARY_SUBTRACT',
        'BINARY_SUBSCR',
        'BINARY_FLOOR_DIVIDE',
        'BINARY_TRUE_DIVIDE',
        'INPLACE_FLOOR_DIVIDE',
        'INPLACE_TRUE_DIVIDE',
        'INPLACE_ADD',
        'INPLACE_SUBTRACT',
        'INPLACE_MULTIPLY',
        'INPLACE_MODULO',
        'BINARY_LSHIFT',
        'BINARY_RSHIFT',
        'BINARY_AND',
        'BINARY_XOR',
        'BINARY_OR',
        'INPLACE_POWER',
        'INPLACE_LSHIFT',
        'INPLACE_RSHIFT',
        'INPLACE_AND',
        'INPLACE_XOR',
        'INPLACE_OR',
        'RETURN_VALUE',
        'BUILD_TUPLE',
        'BUILD_LIST',
        'BUILD_SET',
        'BUILD_MAP',
        'COMPARE_OP',
        'JUMP_FORWARD',
        'JUMP_IF_FALSE_OR_POP',
        'JUMP_IF_TRUE_OR_POP',
        'JUMP_ABSOLUTE',
        'POP_JUMP_IF_FALSE',
        'POP_JUMP_IF_TRUE',
        'LOAD_GLOBAL',
        'IS_OP',
        'LOAD_FAST',
        'STORE_FAST',
        'DELETE_FAST',
        'BUILD_SLICE',
        'LOAD_DEREF',
        'STORE_DEREF',
        'DELETE_DEREF',
        'LOAD_CONST',
        'LOAD_NAME',
        'CALL_FUNCTION',
        'CALL_FUNCTION_KW',
        'CALL_FUNCTION_EX',
        'FORMAT_VALUE',
        'BUILD_STRING',
    }

elif sys.version_info[0:2] == (3, 12):
    opcode_whitelist = {
        '<8>',
        '<6>',
        '<10>',
        "RESUME",
        "CACHE",
        "LOAD_NAME",
        "CALL",
        "RETURN_VALUE",
        "LOAD_CONST",
        "PUSH_NULL",
        "UNARY_NEGATIVE",
        "BINARY_OP",
        "POP_JUMP_IF_FALSE",
        "POP_TOP",
        "FORMAT_VALUE",
        "END_FOR",
        "BUILD_STRING",
        "INTERPRETER_EXIT",
        }
    
else:
    raise RuntimeError("Python version not support!")
    

# Convert names to index
opname_reverse = {name: index for index, name in enumerate(dis.opname)}
try:
    opcode_whitelist_index = {opname_reverse[name] for name in opcode_whitelist}
except KeyError:
    opcode_whitelist_index = None

# It's useful to have a full list.
if opcode_whitelist_index is None:
    raise KeyError(
        "The following keys were not found: {!s}".format(
        list(sorted(name for name in opcode_whitelist if name not in opname_reverse)))
    )


def raise_if_code_unsafe(code, globals=None, locals=None):
    whitelist = set(builtins_whitelist)
    if globals:
        whitelist.update(globals)
    if locals:
        whitelist.update(locals)

    bad_ops = []
    for name in code.co_names:
        if name not in whitelist:
            bad_ops.append(name)

    if bad_ops:
        raise RuntimeError(
                "Name(s) %s not in white-list: (%s)" % (
                ", ".join(repr(name) for name in bad_ops),
                ", ".join(sorted(whitelist)))
                )
    del bad_ops

    code_bytes = code.co_code

    def code_size(opcode):
        if opcode >= dis.HAVE_ARGUMENT:
            return 3
        else:
            return 1

    i = 0
    code_len = len(code_bytes)
    while i < code_len:
        opcode = code_bytes[i]

        if opcode not in opcode_whitelist_index:
            raise RuntimeError("OpCode %r not in white-list %r" % (dis.opname[opcode], opcode))

        i += code_size(opcode)


def safe_eval(source, globals=None):
    
    locals = {
        "sin": math.sin,
        "tan": math.tan,
        "cos": math.cos,
        "log": math.log,
        }

    code = compile(source, "<safe_eval>", "eval")

    raise_if_code_unsafe(code, globals=globals, locals=locals)

    ans = eval(code, globals, locals)
    globals.pop('__builtins__') # 删去副作用
    return ans

if __name__ == "__main__":
    constraints = {
        "bbbv": 67,
        "right": 8888,
        "right_s": 11.9
        }
    a = safe_eval("any([min(22+2, 6), 7])", constraints)
    a = safe_eval("f'{right}@{right_s:.3f}'", constraints)
    a = safe_eval("sin(22+2) / cos(-50) - (log(7.21))", constraints)
    
    


