# Third-party notices

Transparentor 1.1.0 is distributed under the MIT License, but it uses third-party
software and downloads optional model files that remain under their own terms.
This notice is informational and does not replace those license texts.

## AI runtime and model projects

| Component | Version/model | License | Project |
| --- | --- | --- | --- |
| rembg | 2.0.76 | MIT | <https://github.com/danielgatis/rembg> |
| ONNX Runtime DirectML | 1.24.4 | MIT | <https://github.com/microsoft/onnxruntime> |
| IS-Net / `isnet-general-use` | general-use weights | Apache-2.0 project | <https://github.com/xuebinqin/DIS> |
| BiRefNet / `birefnet-massive` | massive ONNX weights | MIT project | <https://github.com/ZhengPeng7/BiRefNet> |

Model weights are not included in `Transparentor.exe`. Transparentor asks before
downloading them from the model release URLs used by rembg.

## Packaged Python components

The Windows build may contain the following runtime components and their
transitive dependencies. Versions reflect the Transparentor 1.1.0 build
environment.

| Component | Version | Declared license |
| --- | ---: | --- |
| attrs | 26.1.0 | MIT |
| certifi | 2026.5.20 | MPL-2.0 |
| charset-normalizer | 3.4.7 | MIT |
| colorama | 0.4.6 | BSD |
| flatbuffers | 25.12.19 | Apache-2.0 |
| idna | 3.18 | BSD-3-Clause |
| ImageIO | 2.37.3 | BSD-2-Clause |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| lazy-loader | 0.5 | BSD-3-Clause |
| llvmlite | 0.47.0 | BSD-2-Clause and Apache-2.0 with LLVM exception |
| mpmath | 1.3.0 | BSD |
| networkx | 3.6.1 | BSD-3-Clause |
| numba | 0.65.1 | BSD |
| NumPy | 2.4.6 | BSD-3-Clause and bundled-component licenses |
| ONNX Runtime DirectML | 1.24.4 | MIT |
| OpenCV Python | 4.13.0.92 | Apache-2.0 |
| packaging | 26.2 | Apache-2.0 or BSD-2-Clause |
| Pillow | 12.2.0 | MIT-CMU |
| platformdirs | 4.10.0 | MIT |
| pooch | 1.9.0 | BSD-3-Clause |
| protobuf | 7.35.0 | BSD-3-Clause |
| PyMatting | 1.1.15 | MIT |
| referencing | 0.37.0 | MIT |
| requests | 2.34.2 | Apache-2.0 |
| rpds-py | 2026.5.1 | MIT |
| scikit-image | 0.26.0 | BSD-3-Clause and included component licenses |
| SciPy | 1.17.1 | BSD-3-Clause and included binary-component licenses |
| setuptools | 82.0.1 | MIT |
| SymPy | 1.14.0 | BSD |
| tifffile | 2026.6.1 | BSD-3-Clause |
| tkinterdnd2 | 0.4.4.1 | MIT |
| tqdm | 4.68.1 | MPL-2.0 and MIT |
| urllib3 | 2.7.0 | MIT |

The executable is produced with PyInstaller 6.20.0, licensed under GPL-2.0-or-later
with the PyInstaller exception permitting distribution of programs built with it.
Build-only packages such as altgraph, pefile, pyinstaller-hooks-contrib, and
pywin32-ctypes retain their respective licenses.

For complete license text and copyright details, consult each linked project and
the `*.dist-info/licenses` metadata installed with the exact package version.
