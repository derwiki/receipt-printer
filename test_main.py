from fastapi.testclient import TestClient
from main import (
    app,
    get_printer_instance,
    get_usb_printer,
    get_printer,
    prepare_thermal_image,
    print_image_and_text,
    handle_printer_exceptions,
)
from escpos.printer import Dummy
from io import BytesIO
import urllib.parse
from unittest.mock import patch, MagicMock
from PIL import Image
from fastapi.responses import PlainTextResponse

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


# Image Processing Tests
def test_prepare_thermal_image_portrait():
    """Test image processing with portrait orientation image"""
    # Create a portrait image (height > width)
    test_image = Image.new("RGB", (100, 200), color="white")

    result = prepare_thermal_image(test_image, width=576)

    assert result.mode == "1"  # Should be converted to 1-bit
    assert result.width == 576  # Should be resized to target width
    assert result.height == 1152  # Should maintain aspect ratio


def test_prepare_thermal_image_landscape():
    """Test image processing with landscape orientation image"""
    # Create a landscape image (width > height)
    test_image = Image.new("RGB", (200, 100), color="white")

    result = prepare_thermal_image(test_image, width=576)

    assert result.mode == "1"  # Should be converted to 1-bit
    assert result.width == 576  # Should be resized to target width
    assert result.height == 288  # Should maintain aspect ratio


def test_prepare_thermal_image_grayscale():
    """Test image processing converts to grayscale"""
    # Create a color image
    test_image = Image.new("RGB", (100, 100), color=(255, 128, 64))

    result = prepare_thermal_image(test_image, width=576)

    assert result.mode == "1"  # Should be converted to 1-bit
    # Should be processed through grayscale conversion


def test_prepare_thermal_image_custom_width():
    """Test image processing with custom width"""
    test_image = Image.new("RGB", (100, 100), color="white")

    result = prepare_thermal_image(test_image, width=384)

    assert result.width == 384  # Should use custom width
    assert result.height == 384  # Should maintain aspect ratio


def test_print_image_and_text_with_image():
    """Test printing with both image and text"""
    mock_printer = MagicMock()
    test_image = Image.new("1", (100, 100), color=1)
    test_text = "Test receipt text"

    print_image_and_text(mock_printer, test_image, test_text)

    # Should call printer methods multiple times
    assert mock_printer.text.call_count >= 10
    assert mock_printer.image.call_count >= 10
    assert mock_printer.cut.call_count >= 10


def test_print_image_and_text_text_only():
    """Test printing with text only (no image)"""
    mock_printer = MagicMock()
    test_text = "Test receipt text only"

    print_image_and_text(mock_printer, None, test_text)

    # Should call printer methods multiple times
    assert mock_printer.text.call_count >= 10
    assert mock_printer.image.call_count == 0  # No image calls
    assert mock_printer.cut.call_count >= 10


def test_print_image_and_text_printer_cleanup():
    """Test that printer connection is properly closed"""
    mock_printer = MagicMock()
    mock_printer.close = MagicMock()
    test_text = "Test receipt text"

    print_image_and_text(mock_printer, None, test_text)

    # Should call close method if available
    mock_printer.close.assert_called_once()


def test_print_image_and_text_no_close_method():
    """Test printing with printer that has no close method"""
    mock_printer = MagicMock()
    # Remove close method to simulate printer without close
    del mock_printer.close
    test_text = "Test receipt text"

    # Should not raise an error
    print_image_and_text(mock_printer, None, test_text)


# Error Handling Tests
def test_handle_printer_exceptions_success():
    """Test that successful function calls pass through unchanged"""

    @handle_printer_exceptions
    async def test_func():
        return "success"

    # Test the wrapper function directly
    import asyncio

    result = asyncio.run(test_func())
    assert result == "success"


def test_handle_printer_exceptions_exception():
    """Test that exceptions are caught and return error response"""

    @handle_printer_exceptions
    async def test_func():
        raise Exception("Test error")

    import asyncio

    result = asyncio.run(test_func())

    assert isinstance(result, PlainTextResponse)
    assert result.status_code == 500
    assert "Test error" in result.body.decode()


def test_handle_printer_exceptions_printer_error():
    """Test that printer errors return proper error response"""

    @handle_printer_exceptions
    async def test_func():
        raise Exception("Printer connection failed")

    import asyncio

    result = asyncio.run(test_func())

    assert isinstance(result, PlainTextResponse)
    assert result.status_code == 500
    assert "Printer connection failed" in result.body.decode()


def test_print_endpoint_unsupported_file_type():
    """Test print endpoint with unsupported file type"""
    app.dependency_overrides[get_printer_instance] = dummy_printer_override

    # Create a text file instead of image
    test_file = BytesIO(b"This is not an image file")
    test_file.seek(0)

    response = client.post(
        "/print",
        files={"file": ("test.txt", test_file, "text/plain")},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.text == "Unsupported file type"

    app.dependency_overrides = {}


def test_print_endpoint_no_file():
    """Test print endpoint with no file uploaded"""
    app.dependency_overrides[get_printer_instance] = dummy_printer_override

    response = client.post(
        "/print",
        data={},  # No file
        follow_redirects=False,
    )

    assert response.status_code == 303
    # Should still work and generate conversation topics

    app.dependency_overrides = {}


def test_print_endpoint_raw_text():
    """Test print endpoint with raw text input"""
    app.dependency_overrides[get_printer_instance] = dummy_printer_override

    response = client.post(
        "/print",
        data={"raw_text": "Custom receipt text"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    # Should redirect with success and custom text

    app.dependency_overrides = {}
