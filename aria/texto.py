import re
import unicodedata
from html.parser import HTMLParser

PATRONES_SECRETO = (
    re.compile(r"github_pat_\w{10,}|gh[pousr]_\w{20,}"),                    # tokens de GitHub
    re.compile(r"\b(contrase[ñn]a|password|passwd|clave|token|pass)\b\s*(es|:|=)\s*\S{6,}", re.I),
)
# Contraseña de aplicación de Google: 4 grupos de 4 letras al azar.
GRUPOS_4X4 = re.compile(r"\b([a-z]{4}) ?([a-z]{4}) ?([a-z]{4}) ?([a-z]{4})\b")


def parece_secreto(texto: str) -> bool:
    """Detecta contraseñas o tokens escritos por error en el chat."""
    if any(p.search(texto) for p in PATRONES_SECRETO):
        return True
    for grupos in GRUPOS_4X4.finditer(texto):
        letras = "".join(grupos.groups())
        # Letras al azar tienen ~20 % de vocales; el español, ~45 % ("para todo este caso").
        if sum(c in "aeiou" for c in letras) <= 5:
            return True
    return False


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres y palabras clave."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn").strip()


class _ExtractorTexto(HTMLParser):
    IGNORAR = {"script", "style", "noscript", "svg", "template"}

    def __init__(self):
        super().__init__()
        self.partes = []
        self._ignorando = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORAR:
            self._ignorando += 1

    def handle_endtag(self, tag):
        if tag in self.IGNORAR and self._ignorando:
            self._ignorando -= 1

    def handle_data(self, data):
        if not self._ignorando and data.strip():
            self.partes.append(data.strip())


def html_a_texto(html: str) -> str:
    extractor = _ExtractorTexto()
    extractor.feed(html)
    return "\n".join(extractor.partes)


EMOJIS = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")


def quitar_emojis(texto: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", EMOJIS.sub("", texto)).strip()


def recortar(texto: str, maximo: int) -> str:
    return texto if len(texto) <= maximo else texto[:maximo] + "\n[... recortado]"
