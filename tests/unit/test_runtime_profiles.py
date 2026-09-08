import unittest

from backend.app.hardware_profiles import (
    GraphicsAdapter,
    GraphicsVendor,
    RuntimeProfile,
    graphics_vendor_from_device_id,
)
from backend.app.runtime_status import (
    ActiveDevice,
    DevicePreference,
    FallbackReason,
    RuntimeProvider,
    RuntimeStatus,
)


class RuntimeStatusTests(unittest.TestCase):
    def test_maps_common_pci_vendor_ids(self):
        self.assertEqual(
            graphics_vendor_from_device_id("PCI\\VEN_10DE&DEV_1C81"),
            GraphicsVendor.NVIDIA,
        )
        self.assertEqual(
            graphics_vendor_from_device_id("PCI\\VEN_1002&DEV_15DD"),
            GraphicsVendor.AMD,
        )
        self.assertEqual(
            graphics_vendor_from_device_id("PCI\\VEN_8086&DEV_9A49"),
            GraphicsVendor.INTEL,
        )

    def test_legacy_auto_value_keeps_gpu_as_preference(self):
        self.assertEqual(DevicePreference.from_value("auto"), DevicePreference.GPU)

    def test_cpu_fallback_is_visually_distinct_from_cpu_preference(self):
        fallback = RuntimeStatus(
            preference=DevicePreference.GPU,
            active_device=ActiveDevice.CPU,
            engine="engine",
            provider=RuntimeProvider.CPU,
            fallback_reason=FallbackReason.RUNTIME_UNAVAILABLE,
        )
        explicit_cpu = RuntimeStatus(
            preference=DevicePreference.CPU,
            active_device=ActiveDevice.CPU,
            engine="engine",
            provider=RuntimeProvider.CPU,
        )

        self.assertTrue(fallback.is_fallback)
        self.assertEqual(fallback.display_label, "CPU · fallback")
        self.assertIn("suporte de GPU", fallback.tooltip)
        self.assertFalse(explicit_cpu.is_fallback)
        self.assertEqual(explicit_cpu.display_label, "CPU")

    def test_runtime_profile_can_represent_cross_vendor_provider(self):
        directml = RuntimeProfile(
            profile_id="directml-default",
            engine="engine",
            provider=RuntimeProvider.DIRECTML,
            supported_vendors=(
                GraphicsVendor.NVIDIA,
                GraphicsVendor.AMD,
                GraphicsVendor.INTEL,
            ),
            runtime_family="directx12",
        )

        self.assertTrue(
            directml.supports(
                GraphicsAdapter(name="Radeon integrada", vendor=GraphicsVendor.AMD)
            )
        )


if __name__ == "__main__":
    unittest.main()
