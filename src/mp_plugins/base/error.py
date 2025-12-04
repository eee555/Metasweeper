from ._data import _BaseData


class Error(_BaseData):
    """
    错误信息
    """

    type: str
    message: str
