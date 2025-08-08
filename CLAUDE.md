# Claude Development Context

This file contains context and instructions for Claude to work effectively with this receipt printer project.

## Project Overview

This is a FastAPI-based receipt printer application that generates AI-powered conversation topics using OpenAI's GPT models. The app is designed for couples with young kids who want deeper, more meaningful conversations.

## Key Features

- **AI Conversation Generation**: Uses OpenAI GPT-4 to generate 15 personalized conversation prompts
- **Optional Image Printing**: Can print images alongside conversation topics
- **Thermal Printer Safe**: All output is ASCII-only, no emojis or special characters
- **Fallback System**: Falls back to static topics if OpenAI API fails
- **Web Interface**: Simple HTML form for easy use
- **Flexible Input**: Both image upload and topic guidance are optional

## Technical Stack

- **Framework**: FastAPI
- **Package Management**: uv (not pip or poetry)
- **AI Integration**: OpenAI Python SDK
- **Printer**: ESC/POS thermal printer (Rongta RP326)
- **Image Processing**: PIL/Pillow
- **Testing**: pytest

## Development Commands

Always use these exact commands for common tasks:

```bash
# Install dependencies
make install

# Update dependencies after changes to requirements.in
make lock

# Run with dummy printer (for testing)
make run-dummy

# Run with real printer
make run-real

# Run tests
make test

# Format code
make format

# Lint code
make lint
```

## Environment Setup

Required environment variables:
- `OPENAI_API_KEY`: Your OpenAI API key (required for GPT functionality)
- `USE_PRINTER_DUMMY`: Set to "true" for dummy mode, "false" for real printer

## File Structure

- `main.py`: FastAPI app with routes and printer integration
- `conversation_topics.py`: OpenAI GPT integration module
- `test_main.py`: Unit tests
- `requirements.in`: Top-level dependencies (edit this, not uv.lock)
- `uv.lock`: Locked dependencies (auto-generated)
- `Makefile`: Development commands

## Key Dependencies

- `fastapi`: Web framework
- `openai`: GPT integration
- `python-escpos`: Thermal printer control
- `pyusb`: USB printer connection
- `pillow`: Image processing
- `uvicorn`: ASGI server

## Printer Configuration

The printer uses these USB IDs:
- Vendor ID: 0x0FE6
- Product ID: 0x811E

These are configured in the `get_printer()` function in `main.py`.

## AI Conversation System

### Base Prompt
The system uses a hardcoded base prompt optimized for couples with young kids. The prompt emphasizes:
- Emotionally grounded but lightly playful tone
- Introspective without being heavy
- Attuned to everyday realities of life with young kids
- Questions that reveal growth, shared values, small joys

### User Customization
Users can provide optional guidance (e.g., "make them about travel") which gets appended to the base prompt.

### Safety Features
- ASCII-only output (no emojis or special characters)
- Fallback to static topics if OpenAI fails
- Input validation and error handling

## Testing Strategy

- Uses pytest for unit tests
- Tests both dummy and real printer modes
- Covers core functionality and error cases
- Run with `make test`

## Code Style

- Uses black for formatting
- Uses ruff for linting
- Follows FastAPI best practices
- Comprehensive error handling with logging

## Development Notes

- Always test changes with dummy printer first
- Check logging output for debugging
- Both image and text input are optional
- The system gracefully handles missing inputs
- All text output is thermal printer safe (ASCII only)
- Always stage and commit your changes

## Common Issues

1. **USB Printer Not Found**: Ensure pyusb is installed and printer is connected
2. **OpenAI API Errors**: Check API key is set and valid
3. **Import Errors**: Run `make install` to ensure all dependencies are present
4. **Logging Not Visible**: Logging is configured to output to STDOUT in both main.py and conversation_topics.py

## Future Enhancements

Consider these areas for future development:
- Support for different printer models
- More conversation topic templates
- User customizable base prompts
- Topic history/favorites
- Integration with other AI models
