from fastapi.testclient import TestClient
from main import app, get_printer_instance
from escpos.printer import Dummy
from io import BytesIO
import urllib.parse

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
