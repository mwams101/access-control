"""Pass token signing and QR generation (Section 9 — Signed QR tokens)."""
import base64
from io import BytesIO

from django.core import signing

SIGNING_SALT = "access-control.pass"


def make_pass_token(pass_id: int) -> str:
    """The QR carries no PII — only a signed pass reference."""
    return signing.dumps({"pass_id": pass_id}, salt=SIGNING_SALT)


def read_pass_token(token: str) -> int:
    """Returns the pass id, raising signing.BadSignature on tampering."""
    data = signing.loads(token.strip(), salt=SIGNING_SALT)
    return int(data["pass_id"])


def qr_data_uri(token: str) -> str | None:
    """Render the token as a QR code PNG data URI for inline display/email.

    Returns None if the optional `qrcode` package is unavailable, in which
    case templates fall back to showing the token text.
    """
    try:
        import qrcode
    except ImportError:
        return None
    img = qrcode.make(token, box_size=8, border=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
