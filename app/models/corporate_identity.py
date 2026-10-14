from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class CorporateIdentity:
    organization_uuid: str = ''
    display_name: str = ''
    legal_name: str = ''
    cnpj: str = ''
    address: str = ''
    unit: str = ''
    privacy_contact: str = ''
    privacy_notice: str = ''
    accent_color: str = '#2563eb'
    header_color: str = '#0f172a'
    logo: str = ''
    institutional_image: str = ''
    revision: int = 0
    updated_at: str = ''
    editor_username: str = ''
    authority_instance_id: str = ''
    show_legal_details_on_receipts: bool = False

    @staticmethod
    def color(value):
        if not isinstance(value, str) or re.fullmatch(r'#[0-9a-fA-F]{6}', value) is None:
            raise ValueError('Use uma cor hexadecimal no formato #RRGGBB.')
        return value.lower()

    @staticmethod
    def luminance(color):
        values = [int(color[i:i+2], 16)/255 for i in (1, 3, 5)]
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in values]
        return sum(v*w for v, w in zip(linear, (.2126, .7152, .0722)))

    @classmethod
    def foreground(cls, background):
        background = cls.color(background)
        light = cls.luminance(background)
        return '#000000' if (light+.05)/.05 >= 4.5 else '#ffffff'

    @classmethod
    def contrast(cls, first, second):
        values = sorted((cls.luminance(first), cls.luminance(second)))
        return (values[1]+.05)/(values[0]+.05)

    def title(self, fallback='SmartFile'):
        return self.display_name or self.legal_name or fallback
