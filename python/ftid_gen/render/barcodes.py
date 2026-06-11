import io
import warnings

warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

from barcode.codex import Code128
from barcode.writer import ImageWriter
from PIL import Image

def generate_barcode_image(data, remove_text=True, module_height=15.0, quiet_zone=6.5):
    writer_options = {
        "write_text": not remove_text,
        "module_height": module_height,
        "quiet_zone": quiet_zone,
        "background": "white",
        "foreground": "black"
    }

    buffer = io.BytesIO()
    barcode = Code128(data, writer=ImageWriter())
    barcode.write(buffer, options=writer_options)
    buffer.seek(0)

    img = Image.open(buffer).convert("RGBA")
    datas = img.getdata()
    new_data = [(255, 255, 255, 0) if item[0] > 250 and item[1] > 250 and item[2] > 250 else item for item in datas]
    img.putdata(new_data)
    return img

def create_zip_barcode(zip_code, module_height=40.0, quiet_zone=6.5, resize_to=(720, 170)):
    zip_barcode_data = f"420{zip_code}"
    buffer = io.BytesIO()
    code128 = Code128(zip_barcode_data, writer=ImageWriter())
    code128.write(buffer, options={
        "write_text": False,
        "module_height": module_height,
        "quiet_zone": quiet_zone,
        "background": "white",
        "foreground": "black"
    })
    buffer.seek(0)

    barcode_img = Image.open(buffer).convert("RGBA")
    barcode_data = barcode_img.getdata()
    barcode_clean = [(255, 255, 255, 0) if r > 250 and g > 250 and b > 250 else (r, g, b, a) for (r, g, b, a) in barcode_data]
    barcode_img.putdata(barcode_clean)
    return barcode_img.resize(resize_to, Image.Resampling.LANCZOS)
