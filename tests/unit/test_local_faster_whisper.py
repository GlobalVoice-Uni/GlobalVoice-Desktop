import unittest
from unittest.mock import MagicMock, patch

from backend.app.runtime_status import (
    ActiveDevice,
    DevicePreference,
    FallbackReason,
    RuntimeProvider,
)
from backend.app.cuda_runtime import CudaRuntimeCheck
from backend.app.transcribers import local_faster_whisper as transcriber_module


class LocalFasterWhisperTranscriberTests(unittest.TestCase):
    def test_cpu_request_does_not_probe_cuda(self):
        cpu_model = object()
        with (
            patch.object(
                transcriber_module.ctranslate2,
                "get_cuda_device_count",
            ) as cuda_device_count,
            patch.object(
                transcriber_module,
                "WhisperModel",
                return_value=cpu_model,
            ) as whisper_model,
            patch.object(transcriber_module, "prepare_cuda_runtime") as cuda_runtime,
        ):
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(
                model_size="small",
                device="cpu",
            )

        cuda_device_count.assert_not_called()
        cuda_runtime.assert_not_called()
        whisper_model.assert_called_once_with(
            "small",
            device="cpu",
            compute_type="int8",
            num_workers=1,
        )
        self.assertIs(transcriber.model, cpu_model)
        self.assertEqual(transcriber.device, "cpu")
        self.assertIsNone(transcriber.fallback_message)
        self.assertEqual(transcriber.runtime_status.preference, DevicePreference.CPU)
        self.assertEqual(transcriber.runtime_status.active_device, ActiveDevice.CPU)
        self.assertEqual(transcriber.runtime_status.provider, RuntimeProvider.CPU)

    def test_gpu_preference_uses_a_supported_compute_type(self):
        gpu_model = object()
        with (
            patch.object(
                transcriber_module.ctranslate2,
                "get_cuda_device_count",
                return_value=1,
            ),
            patch.object(
                transcriber_module.ctranslate2,
                "get_supported_compute_types",
                return_value={"float32", "int8", "int8_float32"},
            ),
            patch.object(
                transcriber_module,
                "prepare_cuda_runtime",
                return_value=CudaRuntimeCheck(available=True),
            ),
            patch.object(
                transcriber_module,
                "WhisperModel",
                return_value=gpu_model,
            ) as whisper_model,
        ):
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(
                model_size="small",
                device="gpu",
            )

        whisper_model.assert_called_once_with(
            "small",
            device="cuda",
            compute_type="float32",
            num_workers=1,
        )
        self.assertIs(transcriber.model, gpu_model)
        self.assertEqual(transcriber.device, "cuda")
        self.assertEqual(transcriber.compute_type, "float32")
        self.assertIsNone(transcriber.fallback_message)
        self.assertEqual(transcriber.runtime_status.preference, DevicePreference.GPU)
        self.assertEqual(transcriber.runtime_status.active_device, ActiveDevice.GPU)
        self.assertEqual(transcriber.runtime_status.provider, RuntimeProvider.CUDA)

    def test_gpu_preference_falls_back_when_all_gpu_loads_fail(self):
        cpu_model = object()
        with (
            patch.object(
                transcriber_module.ctranslate2,
                "get_cuda_device_count",
                return_value=1,
            ),
            patch.object(
                transcriber_module.ctranslate2,
                "get_supported_compute_types",
                return_value={"float32", "int8"},
            ),
            patch.object(
                transcriber_module,
                "prepare_cuda_runtime",
                return_value=CudaRuntimeCheck(available=True),
            ),
            patch.object(
                transcriber_module,
                "WhisperModel",
                side_effect=[RuntimeError("gpu"), RuntimeError("gpu"), cpu_model],
            ) as whisper_model,
        ):
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(
                model_size="small",
                device="gpu",
            )

        self.assertEqual(whisper_model.call_count, 3)
        self.assertIs(transcriber.model, cpu_model)
        self.assertEqual(transcriber.device, "cpu")
        self.assertEqual(transcriber.compute_type, "int8")
        self.assertEqual(
            transcriber.runtime_status.fallback_reason,
            FallbackReason.INITIALIZATION_FAILED,
        )
        self.assertEqual(transcriber.runtime_status.display_label, "CPU · fallback")
        self.assertNotIn("RuntimeError", transcriber.fallback_message)

    def test_gpu_preference_falls_back_without_loading_cuda_when_no_gpu_is_found(self):
        cpu_model = MagicMock()
        with (
            patch.object(
                transcriber_module.ctranslate2,
                "get_cuda_device_count",
                return_value=0,
            ),
            patch.object(
                transcriber_module,
                "WhisperModel",
                return_value=cpu_model,
            ) as whisper_model,
        ):
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(device="gpu")

        whisper_model.assert_called_once_with(
            "small",
            device="cpu",
            compute_type="int8",
            num_workers=1,
        )
        self.assertEqual(transcriber.device, "cpu")
        self.assertEqual(
            transcriber.runtime_status.fallback_reason,
            FallbackReason.ACCELERATOR_NOT_FOUND,
        )
        self.assertIn("GPU compativel nao encontrada", transcriber.fallback_message)

    def test_gpu_preference_falls_back_before_loading_when_cuda_libraries_are_missing(self):
        cpu_model = object()
        with (
            patch.object(
                transcriber_module.ctranslate2,
                "get_cuda_device_count",
                return_value=1,
            ),
            patch.object(
                transcriber_module,
                "prepare_cuda_runtime",
                return_value=CudaRuntimeCheck(available=False),
            ),
            patch.object(
                transcriber_module,
                "WhisperModel",
                return_value=cpu_model,
            ) as whisper_model,
        ):
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(device="gpu")

        whisper_model.assert_called_once_with(
            "small",
            device="cpu",
            compute_type="int8",
            num_workers=1,
        )
        self.assertEqual(
            transcriber.runtime_status.fallback_reason,
            FallbackReason.CUDA_LIBRARIES_MISSING,
        )
        self.assertIn("componentes de aceleracao NVIDIA", transcriber.fallback_message)


if __name__ == "__main__":
    unittest.main()
