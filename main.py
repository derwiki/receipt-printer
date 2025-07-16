import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import PlainTextResponse
from PIL import Image
from escpos.printer import Serial, Dummy

app = FastAPI()

def get_printer():
    use_dummy = os.getenv("USE_PRINTER_DUMMY", "false").lower() == "true"
    if use_dummy:
        print("⚠️  Using dummy printer")
        return Dummy()
    else:
        return Serial(devfile="/dev/usb/lp0", baudrate=9600, timeout=1)

def get_printer_instance():
    return get_printer()

@app.post("/print", response_class=PlainTextResponse)
async def print_image(
    file: UploadFile = File(...),
    printer=Depends(get_printer_instance)
):
    if file.content_type not in ["image/jpeg", "image/png"]:
        return PlainTextResponse("Unsupported file type", status_code=400)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp.flush()

        # Process image
        image = Image.open(tmp.name).convert("1")
        image = image.resize((384, int(image.height * (384 / image.width))), Image.Resampling.LANCZOS)

        # Use the injected printer
        p = printer
        p.image(image)
        p.text("\nWhat do you think this drawing shows?\n")
        p.text("Write your story here:\n")
        p.text("-" * 32 + "\n\n\n")
        p.cut()

        if isinstance(p, Dummy):
            with open("output.escpos", "wb") as f:
                f.write(p.output)
            return "Printed to dummy printer. ESC/POS bytes saved to output.escpos"

    return "Printed successfully."