"""Provider-specific GPT Image sizing for the web API."""
import math


def build_size(ratio: str, resolution: str, parameter_mode: str = "standard") -> str:
    try:
        rw, rh = map(int, str(ratio).split(':'))
        if rw <= 0 or rh <= 0 or max(rw / rh, rh / rw) > 3:
            raise ValueError
        long_edge = {'1K': 1024, '2K': 2048, '4K': 3840}[str(resolution).upper()]
    except (TypeError, ValueError, KeyError):
        raise ValueError('Unsupported GPT Image ratio or resolution.')
    if parameter_mode == 'apiyi_26':
        if str(resolution).upper() == '4K' and rw == rh:
            raise ValueError('API易 gpt-image-2.6-all 不支持 4K 方形图片，请选择 2K。')
        width = round(long_edge * rw / max(rw, rh))
        height = round(long_edge * rh / max(rw, rh))
        return f'{width}x{height}'
    if resolution.upper() == '1K' and ratio in ('3:2', '2:3'):
        long_edge = 1536
    divisor = math.gcd(rw, rh)
    unit_w, unit_h = 16 * rw // divisor, 16 * rh // divisor
    min_scale = math.ceil(math.sqrt(655360 / (unit_w * unit_h)))
    max_scale = min(3840 // unit_w, 3840 // unit_h,
                    math.floor(math.sqrt(8294400 / (unit_w * unit_h))))
    if min_scale > max_scale:
        raise ValueError('Unsupported GPT Image dimensions.')
    scale = max(min_scale, min(max_scale, round(long_edge / max(unit_w, unit_h))))
    return f'{unit_w * scale}x{unit_h * scale}'
