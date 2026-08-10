import io
import base64
import qrcode
from qrcode.image.svg import SvgPathImage

def generate_prescription_qr_base64(verify_url: str) -> str:
    """
    Generates a standalone Base64 encoded SVG QR Code image for prescription verification.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)

    img = qr.make_image(image_factory=SvgPathImage)
    stream = io.BytesIO()
    img.save(stream)
    svg_bytes = stream.getvalue()
    
    encoded = base64.b64encode(svg_bytes).decode('utf-8')
    return f"data:image/svg+xml;base64,{encoded}"
