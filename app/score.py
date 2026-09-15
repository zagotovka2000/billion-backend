import math


def calc_score(personal: int, level2: int, level3: int) -> float:
    inner = 1 + personal + 0.5 * level2 + 0.25 * level3
    return 1000.0 * math.log(inner)
