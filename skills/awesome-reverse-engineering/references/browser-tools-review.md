# Browser-tool intake review

Reviewed on **2026-10-13 UTC**, for [PR #9](https://github.com/morluto/awesome-reverse-engineering/pull/9). Recheck by **2026-11-13**, or earlier if the hosted tools change. These three workbenches add browser workflows to the 140-entry baseline, for **143 catalog entries**. The contributor disclosed that they build the tools as Nitramine.

The checks used an anonymous Linux x86_64 browser session reporting Headless Chromium 153. All three are hosted **alphas**. These are bounded manual browser observations; other browsers, large files, format variants, and full Windows behavior were not validated. Hosted URLs are mutable, so the fingerprints below describe the review-date bytes rather than a versioned release.

## Tasks, observations, and limits

| Resource / primary source | Task and observed evidence | Limits that affect selection |
| --- | --- | --- |
| [Rubber Room](https://binarybacktrace.com/tools/rubber_room) | Inspect a PE through its function list, x86-64 assembly, and debugger. The self-authored PE below exposes two functions and one import. The disassembly matches its six-instruction `probe` function, and the debugger services `kernel32!ExitProcess` with the expected code **43**. | Win32 emulation is partial. The DECOMP view produces experimental C-like pseudocode: in this case it omits the result computation and return value. It is not evidence of source recovery or a faithful recompilable program. |
| [Hex Harbinger](https://binarybacktrace.com/tools/hex_harbinger) | Inspect bytes with format-specific structure fields. The built-in demo loads. The PE below, an ELF64 header, a little-endian Mach-O64 header, and a stored ZIP each show matching magic, architecture/type, or archive fields. Selecting `e_magic` selects bytes **0x0-0x1** and shows the expected `0x5A4D` value. | These small inputs establish the observed templates, not full coverage of their format families, compressed ZIP methods, universal Mach-O binaries, or large-file behavior. |
| [Struct Smith](https://binarybacktrace.com/tools/struct_smith) · [delivered client](https://binarybacktrace.com/js/struct_smith.js?v=20260807) | Author and revise binary schemas in the site's Spec language. The PE preset parses the fixture; selecting its signature highlights bytes **0x80-0x83** (`50 45 00 00`). Changing `root PEFile` to `root MissingRoot` produces **E2701**; restoring the source clears it. This is a schema-authoring workflow alongside Hex Harbinger's template inspection. | The reviewed client rejects files larger than **64 MiB** before reading them. The checks do not establish interoperability with other schema languages or other browser engines. |

The existing [four resource examples](../examples/resource-intake/README.md) exercise different resources. Their CI results do not verify these hosted tools. Browser checks in this document are manual and date-specific.

## Reproduce the PE observation

The [self-authored source](../examples/browser-tools/probe.c) is a CC0-1.0 fixture; it does not use a third-party Windows executable or malware sample. It computes `probe(n) = n < 0 ? -1 : n * 2 + 1`, then calls `ExitProcess(probe(21))`. The independent expected result is **43**.

With a MinGW-w64 x86_64 compiler installed, run from the repository root:

```sh
mkdir -p /tmp/browser-tools-review
x86_64-w64-mingw32-gcc -O1 -fno-stack-protector -nostdlib \
  -Wl,--entry,entry -Wl,--subsystem,console -Wl,--no-insert-timestamp \
  -o /tmp/browser-tools-review/probe.exe examples/browser-tools/probe.c -lkernel32
x86_64-w64-mingw32-objdump -d /tmp/browser-tools-review/probe.exe
x86_64-w64-mingw32-objdump -x /tmp/browser-tools-review/probe.exe
```

The reviewed build used MinGW GCC **12-win32** and GNU ld **2.40**. Its PE was 6,646 bytes with SHA-256 `225590e0e26da6313f4440fc6fa928ee560ae65bf932ecba2f0848720d11be1f`. Different toolchain builds may produce different bytes.

1. Open Rubber Room, browse to the generated PE, and let analysis finish. Select the exported `probe` function. The assembly includes the sign test, arithmetic, and return path visible in objdump.
2. Inspect **DECOMP**. On the review date the output declared `void probe`, duplicated an `emulated` parameter name, referenced a missing label, and returned without a value. Both the positive `n * 2 + 1` computation and negative result assignment were absent. This is the concrete reason for qualifying the catalog description.
3. Open **DEBUG** and select **Run**. The entry point should finish through `ExitProcess` with code **43**. This verifies only this short instruction/import path.
4. Open Struct Smith and load the same PE. Change the first `root PEFile` declaration to `root MissingRoot`; observe E2701, then restore the declaration. The error should clear and the PE parse should return.
5. Open Hex Harbinger and load the same PE. Check its MZ/PE signatures, x86-64 machine field, and six section headers against the file bytes and objdump's header dump.

The signatures and COFF fields have a small independent byte-level oracle:

```python
from pathlib import Path
import struct

data = Path('/tmp/browser-tools-review/probe.exe').read_bytes()
assert data[:2] == b'MZ'
nt = struct.unpack_from('<I', data, 0x3C)[0]
assert data[nt:nt + 4] == b'PE\0\0'
assert struct.unpack_from('<HH', data, nt + 4) == (0x8664, 6)
```

The observed pseudocode failure is retained as a limitation, not counted as a successful decompiler round trip. The tool's assembly inspection and short emulation case are separately useful.

## Reproduce the other format checks

This standard-library snippet creates three small benign fixtures. The ELF and Mach-O files are header-only probes; the ZIP contains one stored text file.

```python
from pathlib import Path
import struct
import zipfile

p = Path('/tmp/browser-tools-review')
p.mkdir(exist_ok=True)
ident = b'\x7fELF' + bytes([2, 1, 1, 0, 0]) + b'\0' * 7
(p / 'minimal.elf').write_bytes(
    ident + struct.pack('<HHIQQQIHHHHHH', 1, 62, 1, 0, 0, 0, 0, 64, 0, 0, 64, 0, 0)
)
(p / 'minimal.macho').write_bytes(
    struct.pack('<IIIIIIII', 0xFEEDFACF, 0x01000007, 3, 1, 0, 0, 0, 0)
)
info = zipfile.ZipInfo('probe.txt', (2026, 10, 13, 0, 0, 0))
with zipfile.ZipFile(p / 'minimal.zip', 'w') as archive:
    archive.writestr(info, b'benign review fixture\n')
```

Load each file in Hex Harbinger. The observed results are ELF64/x86-64/REL, Mach-O64/x86_64/MH_OBJECT, and a ZIP entry named `probe.txt` with method 0 and a 22-byte payload. This checks recognition and displayed structure fields, not executable loading or archive extraction.

## Source fingerprints

The review retained the following SHA-256 fingerprints of fetched first-party assets. Cache-buster dates in URLs are observations, not release-version claims. No vendor implementation code is redistributed here.

| Source | SHA-256 |
| --- | --- |
| Rubber Room HTML | `b87ab084322d3a99a3f75e204558b3f1f57119899036d795b8ef97e433dd2cc8` |
| Hex Harbinger HTML | `0bef94efe3f5356a29be6600622092e832840fb1d96af2ffb61e254f377a66c2` |
| Struct Smith HTML | `46398526a868bd7506e988e3214a417f6d70d1d412b8377dc949dffedb302774` |
| [Hex Harbinger client](https://binarybacktrace.com/js/hex_harbinger.js?v=20261013) | `9f2377d00ba680c103cc24a85e11c4776bcf4ee65ec397fb71f16a5e6d3748d4` |
| [Struct Smith client](https://binarybacktrace.com/js/struct_smith.js?v=20260807) | `e63300ce177301e08101d2803f041b4b761f53b510b19111bb883b196028154e` |

At the next review, repeat the bounded cases and record changes to the observed output, limits, and asset fingerprints before widening any compatibility claims.
