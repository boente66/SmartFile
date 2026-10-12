"""QR access to original documents; no claim that a visual mark proves identity."""
from io import BytesIO
from urllib.parse import urlsplit

from PIL import Image, ImageDraw
from reportlab.graphics.barcode.qr import QrCodeWidget


class SignatureVerificationService:
    VALIDATOR_URL = "https://validar.iti.gov.br/"
    GOVBR_SIGN_URL = "https://assinador.iti.br/"

    @staticmethod
    def validate_url(value):
        url = urlsplit(value)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or len(value) > 1500 or any(ord(c) < 32 for c in value)):
            raise ValueError("Informe o endereço HTTPS do documento ou da página de verificação.")
        return value

    @classmethod
    def qr_png(cls, url):
        cls.validate_url(url)
        code = QrCodeWidget(url).qr
        code.make()
        count = code.getModuleCount()
        image = Image.new("RGB",((count+8)*8,(count+8)*8),"white")
        draw = ImageDraw.Draw(image)
        for row in range(count):
            for col in range(count):
                if code.modules[row][col]:
                    x,y=(col+4)*8,(row+4)*8
                    draw.rectangle((x,y,x+7,y+7),fill="black")
        buffer = BytesIO();image.save(buffer,format="PNG");image.close()
        return buffer.getvalue()

    @classmethod
    def insert_qr(cls, document, url, page_number=1, rect=None):
        import fitz
        if not 1 <= page_number <= document.page_count:raise ValueError("Página do QR Code inválida.")
        page = document[page_number-1]
        rectangle = fitz.Rect(rect or (page.rect.width-100,20,page.rect.width-20,100))
        if rectangle.is_empty or not page.rect.contains(rectangle) or min(rectangle.width,rectangle.height)<40:
            raise ValueError("Posicione o QR Code dentro da página, com tamanho mínimo de 40 pontos.")
        page.insert_image(rectangle,stream=cls.qr_png(url),keep_proportion=True)

    @staticmethod
    def evidence(path, results=(), kind="CERTIFICATE"):
        """Local evidence, requiring the original file for verification, never an authentication token."""
        import hashlib
        from datetime import datetime, timezone
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda:stream.read(1024*1024),b""):digest.update(block)
        return {"sha256":digest.hexdigest(),"kind":kind,"checked_at":datetime.now(timezone.utc).isoformat(),
                "signatures":[{"field":r.field_name,"state":r.state,"integrity":r.integrity_ok,"trusted":r.trusted} for r in results],
                "identity_confirmed":kind=="CERTIFICATE" and bool(results) and all(r.state=="VALID" for r in results)}
