from math import copysign, floor
from sys import float_info


def round_half_up(value: float, places: int = 2) -> float:
    """Commercial rounding; compensate for binary noise at half boundaries.

    Keep in sync with roundHalfUp in frontend utils/calculations.js.
    """
    magnitude = abs(value)
    scale = 10 ** places
    rounded = floor((magnitude + float_info.epsilon * max(1, magnitude)) * scale + 0.5) / scale
    return copysign(rounded, value) if rounded else 0.0
