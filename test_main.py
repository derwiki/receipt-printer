from fastapi.testclient import TestClient
from main import app, get_printer_instance
from escpos.printer import Dummy
from io import BytesIO

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
    assert response.headers["location"] == "/"

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
    assert response.headers["location"] == "/"

    app.dependency_overrides = {}
