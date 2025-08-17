from fastapi.testclient import TestClient
from main import app, get_printer_instance, get_usb_printer, get_printer
from escpos.printer import Dummy
from io import BytesIO
import urllib.parse
from unittest.mock import patch, MagicMock

client = TestClient(app)


def dummy_printer_override():
    return Dummy()


def test_print_endpoint_with_dummy():
    app.dependency_overrides[get_printer_instance] = dummy_printer_override

    # Simulate a JPEG file upload
    test_image = BytesIO()
    from PIL import Image

    Image.new("RGB", (100, 100), color="white").save(test_image, format="JPEG")
    test_image.seek(0)

    response = client.post(
        "/print",
        files={"file": ("test.jpg", test_image, "image/jpeg")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    # Check that redirect URL starts with expected pattern and contains success parameters
    assert response.headers["location"].startswith("/?success=true&conversation_text=")

    # Parse the URL to extract and decode the conversation_text parameter
    from urllib.parse import urlparse, parse_qs

    parsed_url = urlparse(response.headers["location"])
    query_params = parse_qs(parsed_url.query)

    assert "success" in query_params
    assert "conversation_text" in query_params
    assert query_params["success"][0] == "true"

    # Decode the conversation text and verify it contains expected content
    conversation_text = urllib.parse.unquote_plus(query_params["conversation_text"][0])
    assert "CONVERSATION TOPICS" in conversation_text

    app.dependency_overrides = {}  # Cleanup


def test_print_endpoint_with_real_printer_mock(monkeypatch):
    class MockPrinter:
        def image(self, img):
            pass

        def text(self, txt):
            pass

        def cut(self):
            pass

    def mock_real():
        return MockPrinter()

    app.dependency_overrides[get_printer_instance] = mock_real

    test_image = BytesIO()
    from PIL import Image

    Image.new("RGB", (100, 100), color="white").save(test_image, format="JPEG")
    test_image.seek(0)

    response = client.post(
        "/print",
        files={"file": ("test.jpg", test_image, "image/jpeg")},
        follow_redirects=False,
    )

    assert response.status_code == 303
    # Check that redirect URL starts with expected pattern and contains success parameters
    assert response.headers["location"].startswith("/?success=true&conversation_text=")

    # Parse the URL to extract and decode the conversation_text parameter
    from urllib.parse import urlparse, parse_qs

    parsed_url = urlparse(response.headers["location"])
    query_params = parse_qs(parsed_url.query)

    assert "success" in query_params
    assert "conversation_text" in query_params
    assert query_params["success"][0] == "true"

    # Decode the conversation text and verify it contains expected content
    conversation_text = urllib.parse.unquote_plus(query_params["conversation_text"][0])
    assert "CONVERSATION TOPICS" in conversation_text

    app.dependency_overrides = {}


# USB Printer Detection Tests
@patch("usb.core.find")
def test_get_usb_printer_success(mock_find):
    """Test successful USB printer detection"""
    # Mock USB device with known thermal printer vendor ID
    mock_device = MagicMock()
    mock_device.idVendor = 0x0FE6  # Known thermal printer vendor
    mock_device.idProduct = 0x811E

    mock_find.return_value = [mock_device]

    with patch("main.Usb") as mock_usb_class:
        mock_printer = MagicMock()
        mock_usb_class.return_value = mock_printer

        result = get_usb_printer()

        assert result == mock_printer
        mock_usb_class.assert_called_once_with(0x0FE6, 0x811E)


@patch("usb.core.find")
def test_get_usb_printer_fallback(mock_find):
    """Test fallback to hardcoded IDs when auto-detection fails"""
    mock_find.side_effect = Exception("USB detection failed")

    with patch("main.Usb") as mock_usb_class:
        mock_printer = MagicMock()
        mock_usb_class.return_value = mock_printer

        result = get_usb_printer()

        assert result == mock_printer
        mock_usb_class.assert_called_once_with(0x0FE6, 0x811E)


@patch("usb.core.find")
def test_get_usb_printer_connection_failure(mock_find):
    """Test handling of printer connection failures"""
    # Mock USB device that fails to connect
    mock_device = MagicMock()
    mock_device.idVendor = 0x0FE6
    mock_device.idProduct = 0x811E

    mock_find.return_value = [mock_device]

    with patch("main.Usb") as mock_usb_class:
        # First call fails, second call succeeds (fallback)
        mock_usb_class.side_effect = [Exception("Connection failed"), MagicMock()]

        get_usb_printer()

        assert mock_usb_class.call_count == 2
        # Should fall back to hardcoded IDs
        assert mock_usb_class.call_args_list[1] == ((0x0FE6, 0x811E),)


@patch.dict("os.environ", {"USE_PRINTER_DUMMY": "true"})
def test_get_printer_dummy_mode():
    """Test printer selection when USE_PRINTER_DUMMY is set"""
    result = get_printer()
    assert isinstance(result, Dummy)


@patch.dict("os.environ", {"USE_PRINTER_DUMMY": "false"})
@patch("main.get_usb_printer")
def test_get_printer_real_mode(mock_get_usb_printer):
    """Test printer selection when USE_PRINTER_DUMMY is false"""
    mock_printer = MagicMock()
    mock_get_usb_printer.return_value = mock_printer

    result = get_printer()

    assert result == mock_printer
    mock_get_usb_printer.assert_called_once()
