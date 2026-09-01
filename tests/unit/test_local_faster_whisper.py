import unittest
from unittest.mock import MagicMock, patch

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
        ):
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(
                model_size="small",
                device="cpu",
            )

        cuda_device_count.assert_not_called()
        whisper_model.assert_called_once_with(
            "small",
            device="cpu",
            compute_type="int8",
            num_workers=1,
        )
        self.assertIs(transcriber.model, cpu_model)
        self.assertEqual(transcriber.device, "cpu")
        self.assertIsNone(transcriber.fallback_message)

    def test_auto_uses_a_compute_type_supported_by_the_gpu(self):
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
                "WhisperModel",
                return_value=gpu_model,
            ) as whisper_model,
        ):
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(
                model_size="small",
                device="auto",
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

    def test_auto_falls_back_to_cpu_when_all_gpu_loads_fail(self):
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
                "WhisperModel",
                side_effect=[RuntimeError("gpu"), RuntimeError("gpu"), cpu_model],
            ) as whisper_model,
        ):
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(
                model_size="small",
                device="auto",
            )

        self.assertEqual(whisper_model.call_count, 3)
        self.assertIs(transcriber.model, cpu_model)
        self.assertEqual(transcriber.device, "cpu")
        self.assertEqual(transcriber.compute_type, "int8")
        self.assertIn("CPU automaticamente", transcriber.fallback_message)

    def test_auto_falls_back_without_loading_cuda_when_no_gpu_is_found(self):
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
            transcriber = transcriber_module.LocalFasterWhisperTranscriber(device="auto")

        whisper_model.assert_called_once_with(
            "small",
            device="cpu",
            compute_type="int8",
            num_workers=1,
        )
        self.assertEqual(transcriber.device, "cpu")
        self.assertIn("Nenhuma GPU compativel", transcriber.fallback_message)


if __name__ == "__main__":
    unittest.main()
