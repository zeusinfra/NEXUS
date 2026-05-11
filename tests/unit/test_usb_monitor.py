from nexus_core.peripherals.usb_monitor import USBMonitor


class FakeDevice:
    def __init__(self, properties, subsystem="usb", device_type="usb_device"):
        self.properties = properties
        self.subsystem = subsystem
        self.device_type = device_type


def test_usb_storage_is_medium_risk():
    monitor = USBMonitor()
    device = FakeDevice(
        {
            "ID_VENDOR_FROM_DATABASE": "Kingston",
            "ID_MODEL_FROM_DATABASE": "DataTraveler",
            "ID_SERIAL_SHORT": "ABC123",
            "ID_VENDOR_ID": "0951",
            "ID_MODEL_ID": "1666",
            "ID_USB_DRIVER": "usb-storage",
        }
    )

    analysis = monitor.analyze_device(device)

    assert analysis.device_type == "Armazenamento USB"
    assert analysis.risk == "MEDIUM"
    assert "varredura" in analysis.action
    assert analysis.fingerprint == "0951:1666:ABC123"


def test_usb_hid_is_medium_risk_badusb_candidate():
    monitor = USBMonitor()
    device = FakeDevice(
        {
            "ID_VENDOR": "Example",
            "ID_MODEL": "Keyboard",
            "ID_SERIAL_SHORT": "KBD1",
            "ID_VENDOR_ID": "1234",
            "ID_MODEL_ID": "abcd",
            "ID_USB_INTERFACES": ":030101:",
        }
    )

    analysis = monitor.analyze_device(device)

    assert analysis.device_type == "HID USB"
    assert analysis.risk == "MEDIUM"
    assert "BadUSB" in analysis.reason


def test_usb_network_device_is_high_risk():
    monitor = USBMonitor()
    device = FakeDevice(
        {
            "ID_VENDOR": "Example",
            "ID_MODEL": "Ethernet",
            "ID_SERIAL_SHORT": "NET1",
            "ID_VENDOR_ID": "0bda",
            "ID_MODEL_ID": "8153",
            "ID_USB_INTERFACES": ":020600:",
        }
    )

    analysis = monitor.analyze_device(device)

    assert analysis.device_type == "Rede ou comunicacao USB"
    assert analysis.risk == "HIGH"
    assert "interfaces de rede" in analysis.action


def test_unknown_device_without_serial_is_promoted_to_medium_risk():
    monitor = USBMonitor()
    device = FakeDevice({"ID_VENDOR": "Unknown", "ID_MODEL": "Mystery"})

    analysis = monitor.analyze_device(device)

    assert analysis.risk == "MEDIUM"
    assert analysis.serial == "sem-serial"


def test_usb_interface_event_is_not_announced():
    monitor = USBMonitor()
    device = FakeDevice({"DEVTYPE": "usb_interface"})

    assert monitor._is_primary_usb_event(device) is False


def test_usb_device_event_is_announced():
    monitor = USBMonitor()
    device = FakeDevice({"DEVTYPE": "usb_device"})

    assert monitor._is_primary_usb_event(device) is True
