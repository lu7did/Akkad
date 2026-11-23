#!/usr/bin/env python3
"""Embed a GRMP0001 NNUE model in ARM FLASH, including TWINS copies.

The loader and C++ symbol names retain their historical Grumpy identifiers;
these denote the on-disk FORMAT, not which network's weights are used.
"""
import argparse
from pathlib import Path

ARM = Path(__file__).resolve().parents[2] / "ARM"


def bytes_as_cpp(data: bytes) -> str:
    return "\n".join(
        "  " + ", ".join(f"0x{value:02x}" for value in data[start:start + 16]) + ","
        for start in range(0, len(data), 16)
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ARM / "assets/bashful.bin")
    parser.add_argument("--output", type=Path, default=ARM / "include/generated_grumpy.hpp")
    parser.add_argument("--twins-output", type=Path, default=ARM / "include/twins_grumpy.hpp")
    args = parser.parse_args()
    data = args.input.read_bytes()
    if len(data) != 1304 or data[:12] != b"GRMP0001\x69\x00\x00\x00":
        raise SystemExit(f"Incompatible NNUE GRMP0001 model: {args.input}")

    code = ("#pragma once\n#include <cstddef>\n#include <cstdint>\n"
            "// Generated from ARM/assets/bashful.bin; stored in program FLASH.\n"
            "namespace picoSargon {\ninline constexpr uint8_t GRUMPY_DATA[] = {\n"
            + bytes_as_cpp(data)
            + "\n};\ninline constexpr size_t GRUMPY_LENGTH = sizeof(GRUMPY_DATA);\n}\n")
    twins = ("#pragma once\n#include <cstdint>\n"
             "// Two immutable FLASH copies of Bashful for cooperative TWINS.\n"
             "namespace picoSargon {\n"
             "alignas(4) __attribute__((used)) static const uint8_t TWINS_GRUMPY_A[] = {\n"
             + bytes_as_cpp(data)
             + "\n};\n"
             "alignas(4) __attribute__((used)) static const uint8_t TWINS_GRUMPY_B[] = {\n"
             + bytes_as_cpp(data)
             + "\n};\nstatic constexpr unsigned TWINS_GRUMPY_BYTES = sizeof(TWINS_GRUMPY_A);\n}\n")
    for path, content in ((args.output, code), (args.twins_output, twins)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf8")
    print(f"Embedded {args.input.name}: {len(data)} bytes per network; TWINS=2 copies")


if __name__ == "__main__":
    main()
