# -*- mode: python ; coding: utf-8 -*-

import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata


project_root = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
entry_point = os.path.join(project_root, "frontend", "src", "main.py")
diagnostic_console = os.environ.get("GLOBALVOICE_DIAGNOSTIC_CONSOLE") == "1"
runtime_packages_path = os.environ.get(
    "GLOBALVOICE_RUNTIME_SITE_PACKAGES",
    os.path.join(project_root, ".venv", "Lib", "site-packages"),
)
cuda_runtime_source = os.environ.get("GLOBALVOICE_CUDA_RUNTIME_SOURCE")

datas = []
binaries = []
hiddenimports = [
    "ctranslate2._ext",
    "faster_whisper.assets",
]

# Os hooks padrao tratam PySide6, PyAV, NumPy, SciPy e sounddevice. Coletar todos
# os submodulos de Hugging Face ou CTranslate2 inclui CLIs e frameworks opcionais
# (Torch, TensorFlow etc.) que nao participam do fluxo de transcricao.
datas.extend(collect_data_files("faster_whisper"))
datas.extend(
    [
        (
            os.path.join(project_root, "backend", "assets", "silero_vad_16k_op15.onnx"),
            os.path.join("backend", "assets"),
        ),
        (
            os.path.join(project_root, "backend", "assets", "SILERO_VAD_LICENSE.txt"),
            os.path.join("backend", "assets"),
        ),
    ]
)
binaries.extend(collect_dynamic_libs("ctranslate2"))
if cuda_runtime_source:
    # cublas64 depende de cublasLt. O PyInstaller resolve essa dependencia e
    # inclui cada DLL uma unica vez na raiz interna do pacote.
    binaries.append((os.path.join(cuda_runtime_source, "cublas64_12.dll"), "."))

# Inclui o runtime C++ usado pelo Qt mesmo quando ele ja esta instalado na
# maquina de desenvolvimento. A build nao deve depender desse pre-requisito na
# maquina que receber a pasta.
cpp_runtime_candidates = (
    os.path.join(runtime_packages_path, "shiboken6", "msvcp140.dll"),
    os.path.join(sys.base_prefix, "vcruntime140.dll"),
    os.path.join(sys.base_prefix, "vcruntime140_1.dll"),
)
binaries.extend((path, ".") for path in cpp_runtime_candidates if os.path.isfile(path))

for distribution in ("faster-whisper", "ctranslate2", "onnxruntime"):
    try:
        datas.extend(copy_metadata(distribution))
    except Exception:
        pass


analysis = Analysis(
    [entry_point],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "experiments",
        "tests",
        "tensorflow",
        "jax",
        "flax",
        "silero_vad",
        "torch",
        "torchaudio",
        "PySide6.QtNetwork",
    ],
    noarchive=False,
    optimize=0,
)

# O resolvedor de DLLs do Windows pode encontrar bibliotecas pertencentes a
# outras ferramentas instaladas na maquina. Isso torna a build dependente do
# ambiente do desenvolvedor e pode quebrar o Qt em outra maquina. Mantemos
# somente binarios vindos do projeto, do Python usado na build ou do Windows.
allowed_binary_roots = tuple(
    os.path.normcase(os.path.abspath(path))
    for path in (project_root, sys.base_prefix, os.environ.get("WINDIR"))
    if path
)


def is_allowed_binary(source):
    if not isinstance(source, str):
        return True

    source = os.path.normcase(os.path.abspath(source))
    for root in allowed_binary_roots:
        try:
            if os.path.commonpath((source, root)) == root:
                return True
        except ValueError:
            continue
    return False


external_binaries = [
    destination
    for destination, source, _kind in analysis.binaries
    if not is_allowed_binary(source)
]
if external_binaries:
    print(
        "Dependencias binarias externas ignoradas: "
        + ", ".join(sorted(external_binaries))
    )
analysis.binaries = [
    entry for entry in analysis.binaries if is_allowed_binary(entry[1])
]

# A interface atual usa QtCore, QtGui e QtWidgets. Mantemos o backend padrao do
# Windows, o estilo nativo e os formatos de imagem, mas removemos alternativas
# que puxam QML/Quick, PDF, OpenGL por software e a pilha de rede/TLS. Esses
# componentes nao sao importados nem usados pelas telas do Global Voice.
unused_qt_binary_names = {
    "opengl32sw.dll",
    "qt6network.dll",
    "qt6opengl.dll",
    "qt6pdf.dll",
    "qt6qml.dll",
    "qt6qmlmeta.dll",
    "qt6qmlmodels.dll",
    "qt6qmlworkerscript.dll",
    "qt6quick.dll",
    "qt6virtualkeyboard.dll",
}
unused_qt_plugin_prefixes = (
    os.path.normcase(os.path.join("PySide6", "plugins", "networkinformation")),
    os.path.normcase(os.path.join("PySide6", "plugins", "tls")),
)
unused_qt_plugin_paths = {
    os.path.normcase(path)
    for path in (
        os.path.join("PySide6", "plugins", "imageformats", "qpdf.dll"),
        os.path.join("PySide6", "plugins", "platforminputcontexts", "qtvirtualkeyboardplugin.dll"),
        os.path.join("PySide6", "plugins", "platforms", "qdirect2d.dll"),
        os.path.join("PySide6", "plugins", "platforms", "qminimal.dll"),
        os.path.join("PySide6", "plugins", "platforms", "qoffscreen.dll"),
    )
}


def is_unused_qt_binary(destination):
    normalized = os.path.normcase(destination)
    if os.path.basename(normalized) in unused_qt_binary_names:
        return True
    if normalized in unused_qt_plugin_paths:
        return True
    return any(
        normalized == prefix or normalized.startswith(prefix + os.sep)
        for prefix in unused_qt_plugin_prefixes
    )


unused_qt_binaries = [
    destination
    for destination, _source, _kind in analysis.binaries
    if is_unused_qt_binary(destination)
]
if unused_qt_binaries:
    print("Componentes Qt nao usados ignorados: " + ", ".join(sorted(unused_qt_binaries)))
analysis.binaries = [
    entry for entry in analysis.binaries if not is_unused_qt_binary(entry[0])
]

# Wheels preparados para Windows mantem suas DLLs em diretorios proprios e os
# adicionam explicitamente ao carregador antes de importar as extensoes nativas.
# A analise recursiva do PyInstaller tambem copia essas mesmas DLLs para a raiz,
# duplicando conteudo sem acrescentar outra dependencia. Removemos somente a
# copia plana quando a origem exata ja esta preservada no diretorio conhecido.
package_binary_directories = {
    "av.libs",
    "ctranslate2",
    "numpy.libs",
    "scipy.libs",
}
nested_binary_sources = {
    os.path.normcase(os.path.abspath(source))
    for destination, source, _kind in analysis.binaries
    if os.path.normcase(os.path.dirname(destination)) in package_binary_directories
}
duplicate_root_binaries = [
    destination
    for destination, source, _kind in analysis.binaries
    if not os.path.dirname(destination)
    and os.path.normcase(os.path.abspath(source)) in nested_binary_sources
]
if duplicate_root_binaries:
    print(
        "Copias binarias planas ignoradas: "
        + ", ".join(sorted(duplicate_root_binaries))
    )
analysis.binaries = [
    entry
    for entry in analysis.binaries
    if os.path.dirname(entry[0])
    or os.path.normcase(os.path.abspath(entry[1])) not in nested_binary_sources
]

python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="GlobalVoice",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=diagnostic_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GlobalVoice",
)
