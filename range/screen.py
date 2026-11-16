"""Turn a QEMU screendump (binary PPM) into a PNG the browser can show.

No third-party packages: QEMU's `screendump` writes P6 PPM, and PNG is a simple
container around zlib-compressed scanlines.
"""

import struct
import zlib


class ScreenError(RuntimeError):
    pass


def ppm_to_png(data: bytes) -> bytes:
    if not data.startswith(b"P6"):
        raise ScreenError("only binary PPM (P6) frames are supported")
    index = 2
    values: list[int] = []
    while len(values) < 3:
        while index < len(data) and data[index:index + 1].isspace():
            index += 1
        if data[index:index + 1] == b"#":
            while index < len(data) and data[index:index + 1] not in (b"\n", b"\r"):
                index += 1
            continue
        start = index
        while index < len(data) and data[index:index + 1].isdigit():
            index += 1
        if start == index:
            raise ScreenError("bad PPM header")
        values.append(int(data[start:index]))
    index += 1
    width, height, maxval = values
    if width <= 0 or height <= 0 or width * height > 16_000_000:
        raise ScreenError(f"unreasonable frame size {width}x{height}")
    if maxval != 255:
        raise ScreenError(f"unsupported PPM maxval {maxval}")
    size = width * height * 3
    pixels = data[index:index + size]
    if len(pixels) < size:
        raise ScreenError("truncated PPM frame")
    stride = width * 3
    raw = b"".join(b"\x00" + pixels[row * stride:(row + 1) * stride] for row in range(height))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )
