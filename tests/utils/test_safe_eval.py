"""
safe_eval 模块单元测试
"""
from __future__ import annotations

import pytest

# safe_eval 无需 Qt，可以独立测试
from utils.safe_eval import safe_eval, raise_if_code_unsafe


class TestSafeEval:
    """测试 safe_eval 安全沙箱"""

    def test_basic_arithmetic(self):
        assert safe_eval("1 + 2") == 3
        assert safe_eval("3 * 4") == 12
        assert safe_eval("10 / 2") == 5.0
        assert safe_eval("2 ** 10") == 1024
        assert safe_eval("17 % 5") == 2

    def test_math_functions(self):
        import math
        assert safe_eval("sin(0)") == pytest.approx(0.0)
        assert safe_eval("cos(0)") == pytest.approx(1.0)
        assert safe_eval("log(1)") == pytest.approx(0.0)
        assert safe_eval("tan(0)") == pytest.approx(0.0)

    def test_builtin_whitelist(self):
        assert safe_eval("len([1,2,3])") == 3
        assert safe_eval("max(1,5,3)") == 5
        assert safe_eval("min(1,5,3)") == 1
        assert safe_eval("abs(-5)") == 5
        assert safe_eval("sum([1,2,3])") == 6
        assert safe_eval("pow(2,3)") == 8
        assert safe_eval("round(3.7)") == 4
        assert safe_eval("bool(1)") is True
        assert safe_eval("int(3.14)") == 3
        assert safe_eval("float(3)") == 3.0

    def test_all_any(self):
        assert safe_eval("all([True, True])") is True
        assert safe_eval("all([True, False])") is False
        assert safe_eval("any([False, True])") is True

    def test_comparison_and_logic(self):
        assert safe_eval("3 > 2") is True
        assert safe_eval("3 < 2") is False
        assert safe_eval("not True") is False
        assert safe_eval("3 > 2 and 4 > 1") is True
        assert safe_eval("0 if True else 1") == 0
        assert safe_eval("0 if False else 1") == 1
        assert safe_eval("3 > 2 or 4 < 1") is True
        assert safe_eval("2 in [1,2,3]") is True
        assert safe_eval("4 in [1,2,3]") is False
        assert safe_eval("'a' not in ['b', 'c']") is True
        assert safe_eval("x in items", {"x": 3, "items": [1, 2, 3]}) is True

    def test_f_string(self):
        result = safe_eval("f'{a}@{b:.3f}'", {"a": 88, "b": 11.9})
        assert result == "88@11.900"

    def test_list_comprehension(self):
        result = safe_eval("[i**2 for i in [1,2,3]]")
        assert result == [1, 4, 9]
        result = safe_eval("[i for i in [1,2,3,4] if i > 2]")
        assert result == [3, 4]
        result = safe_eval("[i for i in lst if i > n]", {"lst": [5, 1, 3, 6], "n": 3})
        assert result == [5, 6]

    def test_dict_building(self):
        result = safe_eval("{'a': 1, 'b': 2}")
        assert result == {"a": 1, "b": 2}

    def test_set_building(self):
        result = safe_eval("{1, 2, 3}")
        assert result == {1, 2, 3}

    def test_string_operations(self):
        assert safe_eval("'abc' + 'def'") == "abcdef"
        assert safe_eval("'x' * 3") == "xxx"
        assert safe_eval("s + t", {"s": "hello", "t": " world"}) == "hello world"
        assert safe_eval("f'{a} {b}'", {"a": "hello", "b": "world"}) == "hello world"

    def test_imaginary_numbers(self):
        assert safe_eval("1j * 2j") == pytest.approx(-2 + 0j)
        assert safe_eval("(3+2j) + (1-1j)") == pytest.approx(4 + 1j)
        assert safe_eval("abs(3+4j)") == pytest.approx(5.0)
        assert safe_eval("abs(-5.0)") == 5.0

    def test_set_comprehension(self):
        result = safe_eval("{i**2 for i in [1, 2, 3]}")
        assert result == {1, 4, 9}

    def test_set_operations(self):
        a = {1, 2, 3}
        b = {3, 4, 5}
        assert safe_eval("a | b", {"a": a, "b": b}) == {1, 2, 3, 4, 5}
        assert safe_eval("a & b", {"a": a, "b": b}) == {3}

    def test_dict_comprehension(self):
        result = safe_eval("{k: k**2 for k in [1, 2, 3]}")
        assert result == {1: 1, 2: 4, 3: 9}

    def test_constraint_variables(self):
        constraints = {"bbbv": 67, "right": 8888, "right_s": 11.9}
        assert safe_eval("bbbv >= 4 and right < 5 or right_s == 2.3", constraints) is False
        assert safe_eval("bbbv >= 4", constraints) is True

    def test_with_constraint_nested(self):
        constraints = {"bbbv": 67, "right": 8888}
        assert safe_eval("all([any([min(bbbv+2, 6), 7]), 5, -4])", constraints) is True

    def test_combined_expression(self):
        constraints = {"bbbv": 67, "right": 8888, "right_s": 11.9}
        result = safe_eval("right_s * (bbbv / right)", constraints)
        assert result == pytest.approx(11.9 * (67 / 8888))

    def test_unsafe_attribute_access_raises(self):
        with pytest.raises(RuntimeError):
            safe_eval("__import__('os')")

    def test_unsafe_method_call_raises(self):
        with pytest.raises(RuntimeError):
            safe_eval("'abc'.__class__")

    def test_opcode_validation_rejects_unknown_opcodes(self):
        with pytest.raises(RuntimeError):
            safe_eval("lambda x: x + 1")
