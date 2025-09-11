from unittest.mock import MagicMock
import sys
import types

# Provide a lightweight stub for escpos.printer so importing main doesn't require the package
if 'escpos' not in sys.modules:
    sys.modules['escpos'] = types.ModuleType('escpos')
if 'escpos.printer' not in sys.modules:
    printer_mod = types.ModuleType('escpos.printer')

    class _StubDummy:
        def __init__(self, *args, **kwargs):
            self.output = b""

    class _StubUsb:
        def __init__(self, *args, **kwargs):
            pass

    printer_mod.Dummy = _StubDummy
    printer_mod.Usb = _StubUsb
    sys.modules['escpos.printer'] = printer_mod


def test_sanitize_for_receipt_quotes_and_dashes():
    from main import sanitize_for_receipt

    inp = "“Hello”, it’s working — right…?"
    out = sanitize_for_receipt(inp)
    assert out == '"Hello", it\'s working -- right...?'  # smart quotes/dash/ellipsis


def test_sanitize_for_receipt_accents_and_symbols():
    from main import sanitize_for_receipt

    inp = "café™ 50€ — ½ price"
    out = sanitize_for_receipt(inp)
    assert out == "cafe (TM) 50 EUR -- 1/2 price"


def test_sanitize_for_receipt_spaces_and_zero_width():
    from main import sanitize_for_receipt

    # NBSP and zero-width joiner should be handled
    inp = "A\u00A0B\u200BC"
    out = sanitize_for_receipt(inp)
    # NBSP becomes regular space; zero-width char is removed (no added space)
    assert out == "A BC"


def test_sanitize_for_receipt_fractions_and_arrows():
    from main import sanitize_for_receipt

    inp = "¼ + ¾ -> equals 1 → correct"
    out = sanitize_for_receipt(inp)
    # Note: input contains both ASCII '->' and Unicode right arrow
    assert out == "1/4 + 3/4 -> equals 1 -> correct"


def test_print_image_and_text_uses_sanitized_text():
    from main import print_image_and_text

    mock_printer = MagicMock()
    inp_text = "Print “Yay” now"

    print_image_and_text(mock_printer, None, inp_text)

    # First call prints a leading newline, second call should be sanitized text
    calls = mock_printer.text.call_args_list
    assert len(calls) == 2
    assert calls[0].args == ("\n",)
    assert calls[1].args == ('Print "Yay" now',)
    mock_printer.cut.assert_called_once()
