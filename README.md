# Receipt Printer API with AI Conversation Topics

![Sample Output](samples.jpg)

This is a FastAPI-based HTTP API that generates AI-powered conversation topics and optionally prints them alongside images to a thermal receipt printer (e.g. Rongta RP326). Uses OpenAI's GPT models to create personalized conversation prompts for couples with young kids.

Supports both real printer output and dummy mode for testing and development.

## Requirements

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) for Python dependency and environment management
- `pyusb` (required for USB printer connection)
- `pyserial` (required only for real serial printing)
- OpenAI API key (for conversation topic generation)
- `cloudflared` (optional, for public HTTPS exposure)

## Setup Instructions

### 1. Clone the repo and set up the environment

```bash
git clone https://github.com/yourname/receipt-printer.git
cd receipt-printer

# Install dependencies and set up environment
make install
```

### 2. Set up OpenAI API key

```bash
export OPENAI_API_KEY='your-openai-api-key-here'
```

Add this to your shell profile (`.bashrc`, `.zshrc`, etc.) to make it persistent.

### 3. To regenerate the lockfile (optional)

```bash
make lock
```

This reads from `requirements.in` and creates a cross-platform compatible `uv.lock` using the `--universal` flag for better compatibility across different operating systems.

## Running the Server

### Run with dummy printer (no hardware required)

```bash
make run-dummy
```

This will render ESC/POS output to `output.escpos`.

### Run with real printer (e.g. /dev/usb/lp0)

```bash
make run-real
```

## AI Conversation Topic Generation

### Web Interface

Visit [http://localhost:8000/](http://localhost:8000/) in your browser to access the conversation topic generator:

1. **Optional Image**: Upload an image to print alongside the topics
2. **Optional Topic Focus**: Enter guidance like "make them about travel" or "focus on parenting"
3. **Generate**: Click "Print with AI Conversation Topics" to generate and print
4. **Success Feedback**: After printing, you'll see a success message with the generated conversation topics displayed on the page

### API Usage

#### Generate topics with image:
```bash
curl -X POST http://localhost:8000/print \
  -F "file=@drawing.jpg" \
  -F "user_prompt=make them about travel"
```

#### Generate topics without image:
```bash
curl -X POST http://localhost:8000/print \
  -F "user_prompt=focus on our future dreams"
```

#### Generate with default base prompt only:
```bash
curl -X POST http://localhost:8000/print
```

### Conversation Topic Features

- **Base Prompt**: Hardcoded prompt optimized for couples with young kids - emotionally grounded, lightly playful, and introspective
- **User Customization**: Optional text input to guide topic focus (e.g., "about travel", "parenting challenges")
- **Fallback System**: If OpenAI API fails, falls back to static conversation topics
- **Thermal-Safe Output**: All text is ASCII-only, no emojis or special characters that could break thermal printers
- **Date Stamps**: All printed topics include the current date for reference
- **Model**: Uses GPT-4 (configurable to GPT-3.5-turbo in `conversation_topics.py` for cost savings)

## Hardware Setup

### USB Printer Detection

The application automatically detects compatible USB thermal printers from known vendors including:
- Rongta (0x0FE6) - Original target printer
- Epson (0x04B8)
- Wincor Nixdorf (0x154F)
- Deltaco Electronics (0x0DD4)

If no compatible printer is found, it falls back to the original Rongta printer IDs (0x0FE6:0x811E).

### Linux USB Permissions

On Linux systems, you may need to set up USB permissions for the thermal printer:

```bash
# Find your printer's USB IDs
lsusb

# Create udev rule (replace with your printer's IDs)
sudo tee /etc/udev/rules.d/99-thermal-printer.rules <<EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fe6", ATTRS{idProduct}=="811e", MODE="0666", GROUP="dialout"
EOF

# Add your user to dialout group
sudo usermod -a -G dialout $USER

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Logout and login (or reboot) to apply group changes
```

## Testing

```bash
make test
```

Tests cover both dummy and mocked real printer modes.

## Public Exposure (Optional)

To make your local server reachable over HTTPS (e.g. for Twilio webhooks), use Cloudflare Tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
```

You’ll receive a public URL like:

```
https://your-project-name.trycloudflare.com
```

## Banner Generator

The API includes a web-based banner generator for creating and printing large text banners.

### Usage

1. Visit [http://localhost:8000/banner](http://localhost:8000/banner) in your browser.
2. Enter your desired text and click "Preview Banner".
3. The preview page will display the generated banner image and a "Print" button.
4. Click "Print" to send the banner image to the printer (or to the dummy output in dummy mode).

### Endpoints

- `GET /banner` — Shows a form to enter banner text.
- `POST /banner/preview` — Generates and previews the banner image, with a print button.
- `GET /banner/image?token=...` — Serves the generated banner image for preview/printing.

### Font Requirements

Banner generation requires a TrueType font (TTF) such as Arial or Verdana. The app will search for these fonts in common system locations. If no suitable font is found, banner generation will fail with an error. To add your own font, place a TTF file in a standard font directory or update the font search paths in `main.py`.

## File Overview

```
.
├── main.py                   # FastAPI app with /print, /banner, and related endpoints
├── conversation_topics.py    # OpenAI GPT integration for conversation topic generation
├── test_main.py             # Unit tests
├── requirements.in          # Top-level declared dependencies
├── uv.lock                  # Cross-platform locked transitive dependencies
├── Makefile                 # Run targets (install, test, run) with shell compatibility
├── CLAUDE.md                # Development context and instructions for AI assistants
├── output.escpos            # ESC/POS bytes written in dummy mode
```

## Environment Variables

| Variable            | Purpose                              |
|---------------------|--------------------------------------|
| `USE_PRINTER_DUMMY` | Set to `true` to use Dummy printer   |
| `OPENAI_API_KEY`    | Required: Your OpenAI API key for GPT conversation topic generation |

## Example Use Case

Take a photo of a toddler’s drawing, upload it via POST, and print it with a prompt to inspire storytelling. Useful for creative family projects or interactive installations.