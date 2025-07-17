import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import PlainTextResponse
from PIL import Image, ImageOps, ImageEnhance
from escpos.printer import Dummy, Usb

app = FastAPI()


def get_printer():
    use_dummy = os.getenv("USE_PRINTER_DUMMY", "false").lower() == "true"
    if use_dummy:
        print("⚠️  Using dummy printer")
        return Dummy()
    else:
        return Usb(0x0FE6, 0x811E)


def get_printer_instance():
    return get_printer()


def prepare_thermal_image(image: Image.Image, width: int = 576) -> Image.Image:
    """
    Prepare a PIL Image for thermal receipt printing.

    - Rotates landscape images to portrait orientation
    - Resizes to target width (preserving aspect ratio)
    - Converts to grayscale
    - Boosts contrast and brightness
    - Applies Floyd–Steinberg dithering to binary

    Args:
        image (Image.Image): Original PIL image (any mode)
        width (int): Target printable width in pixels

    Returns:
        Image.Image: Dithered 1-bit image ready for ESC/POS printing
    """
    # Rotate if image is landscape
    if image.width > image.height:
        image = image.rotate(90, expand=True)

    # Resize to target width
    aspect = width / image.width
    image = image.resize((width, int(image.height * aspect)), Image.LANCZOS)

    # Grayscale
    image = ImageOps.grayscale(image)

    # Optional tone adjustments
    image = ImageEnhance.Contrast(image).enhance(1.5)
    image = ImageEnhance.Brightness(image).enhance(1.1)

    # Dither
    return image.convert("1", dither=Image.FLOYDSTEINBERG)


@app.post("/print", response_class=PlainTextResponse)
async def print_image(
    file: UploadFile = File(...), printer=Depends(get_printer_instance)
):
    if file.content_type not in ["image/jpeg", "image/png"]:
        return PlainTextResponse("Unsupported file type", status_code=400)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp.flush()

        original = Image.open(tmp.name)
        image = prepare_thermal_image(original, width=576)

        # Use the injected printer
        p = printer
        p.image(image)
        p.text("\n")
        p.text("-" * 32 + "\n\n\n")
        p.cut()

        if isinstance(p, Dummy):
            with open("output.escpos", "wb") as f:
                f.write(p.output)
            return "Printed to dummy printer. ESC/POS bytes saved to output.escpos"

    return "Printed successfully."
