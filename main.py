import os
import tempfile
import logging
from functools import wraps
from fastapi import FastAPI, UploadFile, File, Depends, Request, Form
from fastapi.responses import (
    PlainTextResponse,
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from PIL import Image, ImageOps, ImageEnhance, ImageDraw, ImageFont
from escpos.printer import Dummy, Usb
from io import BytesIO
import uuid
from typing import Optional
from conversation_topics import generate_conversation_topics

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


def print_image_and_text(printer, image: Image.Image, text: str):
    """
    Print both an image and text to the receipt printer.

    Args:
        printer: ESC/POS printer instance (Dummy or Usb)
        image: Prepared thermal image (1-bit PIL Image)
        text: Text content to print after the image
    """
    printer.text("\n")
    printer.image(image)
    printer.text(text)
    printer.cut()


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
def index():
    return """
    <html>
        <head>
            <title>Receipt Printer</title>
        </head>
        <body>
            <h1>Upload an Image to Print</h1>
            <form action=\"/print\" method=\"post\" enctype=\"multipart/form-data\">
                <input type=\"file\" name=\"file\" accept=\"image/png, image/jpeg\" required><br><br>
                <label for=\"prompt_input\">Optional topic focus (e.g., \"make them about travel\"):</label><br>
                <input type=\"text\" name=\"user_prompt\" id=\"prompt_input\" placeholder=\"Enter optional topic guidance...\" style=\"width: 400px;\"><br><br>
                <button type=\"submit\">Print with AI Conversation Topics</button>
            </form>
        </body>
    </html>
    """


@app.post("/print", response_class=PlainTextResponse)
@handle_printer_exceptions
async def print_image(
    file: UploadFile = File(...),
    user_prompt: Optional[str] = Form(None),
    printer=Depends(get_printer_instance),
):
    if file.content_type not in ["image/jpeg", "image/png"]:
        return PlainTextResponse("Unsupported file type", status_code=400)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp.flush()

        original = Image.open(tmp.name)
        image = prepare_thermal_image(original, width=576)

        # Generate conversation topics using OpenAI
        try:
            logging.info("Generating conversation topics...")
            conversation_text = generate_conversation_topics(user_prompt)
        except Exception as e:
            logging.error(f"Failed to generate topics, using fallback: {e}")
            # Fallback to original static topics if OpenAI fails
            conversation_text = """
CONVERSATION TOPICS (FALLBACK)
========================================

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

        # Print image and generated text
        print_image_and_text(printer, image, conversation_text)

        if isinstance(printer, Dummy):
            with open("output.escpos", "wb") as f:
                f.write(printer.output)

    # Redirect to / after printing
    return RedirectResponse(url="/", status_code=303)


@app.get("/banner", response_class=HTMLResponse)
def banner_form():
    return """
    <html>
        <head><title>Banner Generator</title></head>
        <body>
            <h1>Banner Text Generator</h1>
            <form action=\"/banner/preview\" method=\"post\">
                <input type=\"text\" name=\"text\" placeholder=\"Enter banner text\" required>
                <button type=\"submit\">Preview Banner</button>
            </form>
        </body>
    </html>
    """


# In-memory store for banner images by token
banner_images = {}


@app.post("/banner/preview", response_class=HTMLResponse)
async def banner_preview(request: Request):
    form = await request.form()
    text = form.get("text", "")
    width = 2048  # Arbitrary wide width for banner
    height = 576
    bg = "white"
    fg = "black"
    # Find a scalable TTF font
    font_path = None
    possible_fonts = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Verdana.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/Users/adam/Library/Fonts/FreeSans.ttf",
        "/Users/adam/Library/Fonts/FreeSerif.ttf",
    ]
    for path in possible_fonts:
        if os.path.exists(path):
            font_path = path
            break
    if font_path is None:
        return PlainTextResponse(
            "No TTF font found on system. Please install Arial or DejaVuSans.",
            status_code=500,
        )
    # Binary search for largest font size that fits height
    min_size = 10
    max_size = height
    best_size = min_size
    while min_size <= max_size:
        mid = (min_size + max_size) // 2
        font = ImageFont.truetype(font_path, mid)
        dummy_img = Image.new("L", (10, 10))
        dummy_draw = ImageDraw.Draw(dummy_img)
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_height = bbox[3] - bbox[1]
        if text_height <= height * 0.95:
            best_size = mid
            min_size = mid + 1
        else:
            max_size = mid - 1
    font = ImageFont.truetype(font_path, best_size)
    dummy_img = Image.new("L", (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    temp_img = Image.new("RGBA", (text_width, text_height), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    temp_draw.text((-bbox[0], -bbox[1]), text, font=font, fill=fg)
    image = Image.new("RGB", (max(text_width, width), height), bg)
    x = (image.width - text_width) // 2
    y = (height - text_height) // 2
    image.paste(temp_img, (x, y), mask=temp_img.split()[-1])
    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    # Store image in memory with a token
    token = str(uuid.uuid4())
    banner_images[token] = buf.getvalue()
    # Render HTML with image and print button
    return HTMLResponse(
        f"""
    <html>
        <head><title>Banner Preview</title></head>
        <body>
            <h1>Banner Preview</h1>
            <img src="/banner/image?token={token}" style="border:1px solid #ccc; max-width:100%;"><br><br>
            <form id="printForm" action="/print" method="post" enctype="multipart/form-data">
                <input type="hidden" name="token" value="{token}">
                <input type="hidden" name="filename" value="banner.png">
                <button type="button" onclick="submitPrint()">Print</button>
            </form>
            <script>
            function submitPrint() {{
                fetch('/banner/image?token={token}')
                  .then(resp => resp.blob())
                  .then(blob => {{
                    const form = document.getElementById('printForm');
                    const fileInput = document.createElement('input');
                    fileInput.type = 'file';
                    fileInput.name = 'file';
                    const dt = new DataTransfer();
                    dt.items.add(new File([blob], 'banner.png', {{type: 'image/png'}}));
                    fileInput.files = dt.files;
                    form.appendChild(fileInput);
                    form.submit();
                  }});
            }}
            </script>
        </body>
    </html>
    """
    )


@app.get("/banner/image")
def banner_image(token: str):
    img_bytes = banner_images.get(token)
    if not img_bytes:
        return PlainTextResponse("Image not found", status_code=404)
    return StreamingResponse(BytesIO(img_bytes), media_type="image/png")
