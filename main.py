import os
import tempfile
import logging
import urllib.parse
import uuid
from functools import wraps
from io import BytesIO
from typing import Optional
import re
import unicodedata

from fastapi import FastAPI, UploadFile, File, Depends, Request, Form, Query
from fastapi.responses import (
    PlainTextResponse,
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps, ImageEnhance, ImageDraw, ImageFont
from pilmoji import Pilmoji
from escpos.printer import Dummy, Usb

from conversation_topics import generate_conversation_topics

# Configure logging to output to STDOUT
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],  # This outputs to STDOUT
)

app = FastAPI()

# Set up templates
templates = Jinja2Templates(directory="templates")


def get_usb_printer():
    """
    Auto-detect USB thermal printer or use known fallback IDs.

    Returns:
        Usb: ESC/POS USB printer instance
    """
    import usb.core

    # Known thermal printer vendor IDs (common ones)
    known_thermal_vendors = [
        0x0FE6,  # Your original Rongta printer
        0x04B8,  # Epson
        0x154F,  # Wincor Nixdorf
        0x0DD4,  # Deltaco Electronics
        0x20D1,  # Unknown thermal printer vendor
        0x0416,  # Winbond Electronics Corp
    ]

    try:
        # Find all USB devices
        devices = usb.core.find(find_all=True)

        for device in devices:
            # Check if it's a known thermal printer vendor
            if device.idVendor in known_thermal_vendors:
                logging.info(
                    f"Found potential thermal printer: {device.idVendor:04x}:{device.idProduct:04x}"
                )
                try:
                    return Usb(device.idVendor, device.idProduct)
                except Exception as e:
                    logging.warning(
                        f"Failed to connect to printer {device.idVendor:04x}:{device.idProduct:04x}: {e}"
                    )
                    continue

        # If no known vendors found, try the original IDs as fallback
        logging.info("No auto-detected printers found, trying original IDs...")
        return Usb(0x0FE6, 0x811E)

    except Exception as e:
        logging.error(f"USB detection failed: {e}")
        # Fallback to original hardcoded IDs
        return Usb(0x0FE6, 0x811E)


def get_printer():
    use_dummy = os.getenv("USE_PRINTER_DUMMY", "false").lower() == "true"
    if use_dummy:
        print("⚠️  Using dummy printer")
        return Dummy()
    else:
        # Try to auto-detect thermal printer or fall back to known IDs
        return get_usb_printer()


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
    # TODO(2025-08-16): disable rotate images to portrait orientation
    # Rotate if image is landscape
    # if image.width > image.height:
    #    image = image.rotate(90, expand=True)

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


def print_image_and_text(printer, image: Optional[Image.Image], text: str):
    """
    Print both an image and text to the receipt printer.

    Args:
        printer: ESC/POS printer instance (Dummy or Usb)
        image: Prepared thermal image (1-bit PIL Image) or None
        text: Text content to print after the image
    """
    try:
        printer.text("\n")
        if image is not None:
            printer.image(image)
        # Sanitize text to printer-safe characters
        printer.text(sanitize_for_receipt(text))
        printer.cut()
    finally:
        # Always close the printer connection to prevent "Resource busy" errors
        if hasattr(printer, "close"):
            printer.close()


def sanitize_for_receipt(text: str) -> str:
    """
    Convert/strip characters that commonly print garbled on ESC/POS printers.

    - Normalizes fancy quotes/dashes/ellipsis to ASCII
    - Removes zero-width and bidi control characters
    - Replaces common symbols (degree, trademark, euro, etc.) with ASCII
    - Decomposes accents and drops non-ASCII fallbacks
    - Ensures only printable ASCII and newlines are emitted

    Args:
        text: Input text possibly containing Unicode punctuation/symbols

    Returns:
        Sanitized ASCII-only text suitable for receipt printers
    """
    if not text:
        return ""

    # Step 1: direct replacements for common typography and symbols
    repl = {
        # Quotes
        ord("“"): '"', ord("”"): '"', ord("„"): '"', ord("‟"): '"', ord("❝"): '"', ord("❞"): '"',
        ord("‘"): "'", ord("’"): "'", ord("‚"): "'", ord("‛"): "'", ord("❛"): "'", ord("❜"): "'",
        ord("‹"): '"', ord("›"): '"', ord("«"): '"', ord("»"): '"',

        # Dashes and hyphens
        ord("—"): "--",  # em dash
        ord("–"): "-",   # en dash
        ord("‑"): "-",   # non-breaking hyphen
        ord("−"): "-",   # minus sign

        # Ellipsis
        ord("…"): "...",

        # Spaces
        ord("\u00A0"): " ",  # NBSP
        ord("\u202F"): " ",  # narrow NBSP
        ord("\u2007"): " ",  # figure space
        ord("\u2009"): " ",  # thin space
        ord("\u2008"): " ",  # punctuation space
        ord("\u2002"): " ",  # en space
        ord("\u2003"): " ",  # em space
        ord("\u2004"): " ",  # three-per-em space
        ord("\u2005"): " ",  # four-per-em space
        ord("\u2006"): " ",  # six-per-em space

        # Symbols
        ord("°"): " deg",
        ord("•"): "*",
        ord("·"): "*",
        ord("™"): " (TM)",
        ord("®"): " (R)",
        ord("©"): " (C)",
        ord("€"): " EUR",
        ord("£"): " GBP",
        ord("¥"): " YEN",
        ord("¢"): " cent",

        # Fractions
        ord("½"): "1/2",
        ord("¼"): "1/4",
        ord("¾"): "3/4",
        ord("⅓"): "1/3",
        ord("⅔"): "2/3",
        ord("⅛"): "1/8",
        ord("⅜"): "3/8",
        ord("⅝"): "5/8",
        ord("⅞"): "7/8",

        # Arrows/common pictographs -> ASCII
        ord("→"): "->",
        ord("←"): "<-",
        ord("↑"): "^",
        ord("↓"): "v",
    }

    text = text.translate(repl)

    # Step 2: remove zero-width and bidi control characters that can confuse printers
    zero_width_pattern = re.compile("[\u200B\u200C\u200D\u2060\uFEFF\u200E\u200F\u202A-\u202E]")
    text = zero_width_pattern.sub("", text)

    # Step 3: normalize accents and drop non-ASCII remnants
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Step 4: normalize newlines and tabs
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.expandtabs(2)

    # Step 5: restrict to printable ASCII + newlines
    allowed = set(chr(c) for c in range(32, 127))
    allowed.add("\n")
    text = "".join(ch for ch in text if ch in allowed)

    # Optional: collapse excessive whitespace around newlines
    text = re.sub(r"[ \t]+\n", "\n", text)

    return text


def handle_printer_exceptions(endpoint_func):
    @wraps(endpoint_func)
    async def wrapper(*args, **kwargs):
        try:
            return await endpoint_func(*args, **kwargs)
        except Exception as e:
            logging.exception("Printer error in endpoint")
            return PlainTextResponse(f"Printer error: {e}", status_code=500)

    return wrapper


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request, success: bool = Query(False), conversation_text: str = Query("")
):
    from conversation_topics import BASE_PROMPT

    decoded_text = ""
    if success and conversation_text:
        # Decode URL-encoded conversation text
        decoded_text = urllib.parse.unquote_plus(conversation_text)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "base_prompt": BASE_PROMPT,
            "success": success,
            "conversation_text": decoded_text,
        },
    )


@app.post("/print", response_class=PlainTextResponse)
@handle_printer_exceptions
async def print_image(
    file: Optional[UploadFile] = File(None),
    user_prompt: Optional[str] = Form(None),
    system_prompt: Optional[str] = Form(None),
    raw_text: Optional[str] = Form(None),
    printer=Depends(get_printer_instance),
):
    image = None

    # Process image if provided
    if file and file.filename:
        if file.content_type not in ["image/jpeg", "image/png"]:
            return PlainTextResponse("Unsupported file type", status_code=400)

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp.flush()

            original = Image.open(tmp.name)
            image = prepare_thermal_image(original, width=576)

    # Use raw text if provided, otherwise generate conversation topics using OpenAI
    if raw_text and raw_text.strip():
        logging.info("Using provided raw text")
        conversation_text = raw_text.strip()
    else:
        # Generate conversation topics using OpenAI
        try:
            logging.info("Generating conversation topics...")
            conversation_text = generate_conversation_topics(user_prompt, system_prompt)
        except Exception as e:
            logging.error(f"Failed to generate topics, using fallback: {e}")
            # Fallback to original static topics if OpenAI fails
            from datetime import datetime
            import pytz

            pdt = pytz.timezone("America/Los_Angeles")
            today = datetime.now(pdt).strftime("%B %d, %Y")

            conversation_text = f"""
CONVERSATION TOPICS (FALLBACK)
========================================
Printed on: {today}

1. What's a small choice we made that quietly shaped our life in a big way?
2. What's something we've adapted to that used to feel like a dealbreaker?
3. What's a way we've helped each other become more ourselves?
4. What's something about you that's hard to explain but you know I get?
5. What's one way we've protected each other's energy lately?
6. What's a tension we've figured out how to live with instead of fix?
7. What's something we've made easier for each other — even if it's still hard?
8. What's one thing I do that reminds you we're on the same team?
9. What's something we're learning together, even if we're learning it slowly?
10. What's something that's still hard to say out loud, but getting easier?
11. What's a moment when you realized we'd changed — in a good way?
12. What's something you're holding onto right now that you don't want to rush past?
13. What's a shared memory that still teaches you something?
14. What's one truth we've earned the right to hold, just by going through life together?
15. What's a part of our story we might underestimate, but will probably mean a lot in hindsight?

========================================
            """

    # Print image and generated text (image may be None)
    print_image_and_text(printer, image, conversation_text)

    if isinstance(printer, Dummy):
        with open("output.escpos", "wb") as f:
            f.write(printer.output)

    # Redirect to / with success message and conversation text
    encoded_conversation_text = urllib.parse.quote_plus(conversation_text)
    success_url = f"/?success=true&conversation_text={encoded_conversation_text}"
    return RedirectResponse(url=success_url, status_code=303)


@app.get("/banner", response_class=HTMLResponse)
def banner_form(request: Request):
    return templates.TemplateResponse(request, "banner_form.html")


# In-memory store for banner images by token
banner_images = {}


POSSIBLE_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Verdana.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/Users/adam/Library/Fonts/FreeSans.ttf",
    "/Users/adam/Library/Fonts/FreeSerif.ttf",
]


def find_font_path():
    for path in POSSIBLE_FONTS:
        if os.path.exists(path):
            return path
    return None


def make_banner_image(text: str, height: int, font_path: str, bg="white", fg="black") -> Image.Image:
    """Render text into a landscape banner image filling the given height, with emoji support."""
    font_cache = {}
    min_size, max_size = 10, height
    best_size = min_size

    measure_canvas = Image.new("RGB", (10, 10))
    with Pilmoji(measure_canvas) as measurer:
        while min_size <= max_size:
            mid = (min_size + max_size) // 2
            if mid not in font_cache:
                font_cache[mid] = ImageFont.truetype(font_path, mid)
            font = font_cache[mid]
            _, text_h = measurer.getsize(text, font=font)
            if text_h <= height * 0.95:
                best_size = mid
                min_size = mid + 1
            else:
                max_size = mid - 1

        font = font_cache[best_size]
        text_w, text_h = measurer.getsize(text, font=font)

    img = Image.new("RGB", (max(text_w, 1), height), bg)
    with Pilmoji(img) as pilmoji:
        pilmoji.text((0, (height - text_h) // 2), text, fg, font)
    return img


@app.post("/banner/preview", response_class=HTMLResponse)
async def banner_preview(request: Request):
    form = await request.form()
    text = form.get("text", "")

    font_path = find_font_path()
    if font_path is None:
        return PlainTextResponse(
            "No TTF font found on system. Please install Arial or DejaVuSans.",
            status_code=500,
        )

    preview_image = make_banner_image(text, height=288, font_path=font_path)

    buf = BytesIO()
    preview_image.save(buf, format="JPEG", quality=95, optimize=True)
    buf.seek(0)

    token = str(uuid.uuid4())
    banner_images[token] = {"text": text, "font_path": font_path, "preview": buf.getvalue()}

    return templates.TemplateResponse(
        request, "banner_preview.html", {"token": token}
    )


@app.get("/banner/image")
def banner_image(token: str):
    stored = banner_images.get(token)
    if not stored:
        return PlainTextResponse("Image not found", status_code=404)
    return StreamingResponse(BytesIO(stored["preview"]), media_type="image/jpeg")


@app.post("/banner/print")
@handle_printer_exceptions
async def banner_print(token: str = Form(...), printer=Depends(get_printer_instance)):
    stored = banner_images.get(token)
    if not stored:
        return PlainTextResponse("Banner not found", status_code=404)

    # Render at full print resolution (576px = thermal paper width)
    banner_img = make_banner_image(stored["text"], height=576, font_path=stored["font_path"])

    # Rotate 90° so the banner spools along the receipt length
    banner_img = banner_img.rotate(90, expand=True)

    thermal_img = prepare_thermal_image(banner_img, width=576)
    print_image_and_text(printer, thermal_img, "")

    if isinstance(printer, Dummy):
        with open("output.escpos", "wb") as f:
            f.write(printer.output)

    return RedirectResponse(url="/?success=true&conversation_text=Banner+printed!", status_code=303)
