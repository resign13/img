"""GPT Image 2.5 sizing for the web API, including exact aspect ratios."""
import math


def build_size(ratio: str, resolution: str) -> str:
    try:
        rw, rh = map(int, str(ratio).split(':'))
        if rw <= 0 or rh <= 0 or max(rw / rh, rh / rw) > 3:
            raise ValueError
        long_edge = {'1K': 1024, '2K': 2048, '4K': 3840}[str(resolution).upper()]
    except (TypeError, ValueError, KeyError):
        raise ValueError('Unsupported GPT Image 2.5 ratio or resolution.')
    if resolution.upper() == '1K' and ratio in ('3:2', '2:3'):
        long_edge = 1536
    divisor = math.gcd(rw, rh)
    unit_w, unit_h = 16 * rw // divisor, 16 * rh // divisor
    min_scale = math.ceil(math.sqrt(655360 / (unit_w * unit_h)))
    max_scale = min(3840 // unit_w, 3840 // unit_h,
                    math.floor(math.sqrt(8294400 / (unit_w * unit_h))))
    if min_scale > max_scale:
        raise ValueError('Unsupported GPT Image 2.5 dimensions.')
    scale = max(min_scale, min(max_scale, round(long_edge / max(unit_w, unit_h))))
    return f'{unit_w * scale}x{unit_h * scale}'
