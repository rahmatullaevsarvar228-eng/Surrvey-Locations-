"""Interface language. Only Uzbek (Latin) exists in v1; a `ru.py` with the same names can be added."""
from . import uz

LANGUAGES = {"uz": uz}
L = uz


def set_language(code: str):
    global L
    L = LANGUAGES.get(code, uz)
    return L
