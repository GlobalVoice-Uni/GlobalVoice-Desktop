import os
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import cuda_runtime


class CudaRuntimeTests(unittest.TestCase):
    def test_prefers_installed_nvidia_profile_in_frozen_build(self):
        frozen_root = Path("pacote")

        with (
            patch.dict(os.environ, {"GLOBALVOICE_CUDA_RUNTIME": ""}),
            patch.object(cuda_runtime.sys, "_MEIPASS", str(frozen_root), create=True),
        ):
            candidates = cuda_runtime._candidate_directories()

        expected_profile = (
            frozen_root / "runtime" / "nvidia" / "cuda12"
        ).resolve()
        self.assertEqual(candidates[0], expected_profile)
        self.assertEqual(candidates[1], frozen_root.resolve())

    def test_uses_the_first_complete_runtime_directory(self):
        first = Path("incompleto")
        second = Path("perfil-nvidia")

        with patch.object(
            cuda_runtime,
            "_load_from_directory",
            side_effect=[False, True],
        ) as load_from_directory:
            result = cuda_runtime.prepare_cuda_runtime((first, second))

        self.assertTrue(result.available)
        self.assertEqual(result.source_directory, second)
        self.assertEqual(load_from_directory.call_count, 2)

    def test_reports_unavailable_when_no_profile_or_system_library_loads(self):
        with (
            patch.object(cuda_runtime, "_load_from_directory", return_value=False),
            patch.object(cuda_runtime, "_load_from_system", return_value=False),
        ):
            result = cuda_runtime.prepare_cuda_runtime((Path("ausente"),))

        self.assertFalse(result.available)
        self.assertIsNone(result.source_directory)


if __name__ == "__main__":
    unittest.main()
