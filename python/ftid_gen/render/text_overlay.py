from PIL import Image, ImageDraw, ImageFont
from ftid_gen.config import FONT_MAIN, FONT_BOLD, FONT_ARIAL
from ftid_gen.tracking_utils import format_ups_tracking, format_usps_tracking, format_fedex_tracking
from ftid_gen.render.barcodes import create_zip_barcode
import os

try:
    import pyperclipimg as pci
except ImportError:
    pci = None


def _is_final_blank_output(image_path):
    filename = os.path.basename(image_path).lower()
    return "_blank" in filename and "_full" not in filename


def _split_city_state_zip(line, fallback_zip=""):
    parts = [part for part in line.split() if part]
    if len(parts) >= 3:
        return " ".join(parts[:-2]), parts[-2], parts[-1]
    if len(parts) == 2:
        return parts[0], parts[1], fallback_zip
    if len(parts) == 1:
        return parts[0], "", fallback_zip
    return "", "", fallback_zip


def _cfg(cfg, key, default):
    if not cfg:
        return default
    value = cfg.get(key, default)
    return default if value is None else value


def _num(cfg, key, default):
    value = _cfg(cfg, key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _pos(cfg, x_key="start_x", y_key="start_y", default_x=0, default_y=0):
    x = int(round(_num(cfg, x_key, default_x))) + int(round(_num(cfg, "x_offset", 0)))
    y = int(round(_num(cfg, y_key, default_y))) + int(round(_num(cfg, "y_offset", 0)))
    return x, y


def _xy(cfg, default_x=0, default_y=0):
    return _pos(cfg, x_key="x_position", y_key="y_position", default_x=default_x, default_y=default_y)


def _scaled_size(cfg, default_width, default_height, baseline_scale=1.0):
    width = _num(cfg, "width", default_width)
    height = _num(cfg, "height", default_height)
    scale = _num(cfg, "scale", baseline_scale)
    factor = scale / baseline_scale if baseline_scale else scale
    return max(1, int(round(width * factor))), max(1, int(round(height * factor)))


def _lines_with_override(cfg, fallback_lines):
    override = _cfg(cfg, "text", None)
    if override is not None and str(override) != "":
        return [str(override)]
    return fallback_lines


def draw_text_block_scaled(draw, lines, start_x, start_y, font_path, base_font_size, scale=1.0, line_spacing=10, char_spacing=1.3, horizontal_squish=1.0, uppercase=True):
    scale = 1.0 if scale is None else scale
    line_spacing = 10 if line_spacing is None else line_spacing
    char_spacing = 1.3 if char_spacing is None else char_spacing
    horizontal_squish = 1.0 if horizontal_squish is None else horizontal_squish

    font_size = max(1, int(base_font_size * scale))
    font = ImageFont.truetype(font_path, font_size)
    for i, line in enumerate(lines):
        if not line:
            continue
        x = start_x
        y = start_y + i * (font.getbbox("A")[3] + int(line_spacing * scale))
        text = line.upper() if uppercase else line
        for char in text:
            bbox = font.getbbox(char)
            char_width = bbox[2] - bbox[0]
            draw.text((x, y), char, font=font, fill=(0, 0, 0))
            x += (char_width + (char_spacing * scale)) * horizontal_squish


def draw_text_block_scaled_fedex(draw, lines, start_x, start_y, font_path, base_font_size, scale=1.0, line_spacing=10, char_spacing=1.3, horizontal_squish=1.0):
    scale = 1.0 if scale is None else scale
    line_spacing = 10 if line_spacing is None else line_spacing
    char_spacing = 1.3 if char_spacing is None else char_spacing
    horizontal_squish = 1.0 if horizontal_squish is None else horizontal_squish

    font_size = max(1, int(base_font_size * scale))
    font = ImageFont.truetype(font_path, font_size)
    for i, line in enumerate(lines):
        if not line:
            continue
        x = start_x
        y = start_y + i * (font.getbbox("A")[3] + int(line_spacing * scale))
        formatted_words = []
        for word in line.split():
            if (len(word) == 2 and word.isalpha()) or word.upper() == "FROM:":
                formatted_words.append(word.upper())
            else:
                formatted_words.append(word.capitalize())
        formatted_line = " ".join(formatted_words)
        for char in formatted_line:
            bbox = font.getbbox(char)
            char_width = bbox[2] - bbox[0]
            draw.text((x, y), char, font=font, fill=(0, 0, 0))
            x += (char_width + (char_spacing * scale)) * horizontal_squish


def copy_image_to_clipboard(img):
    if pci is None:
        print("Clipboard image copy skipped: pyperclipimg is not installed.")
        return
    try:
        pci.copy(img)
        print("Copied to clipboard. Paste with Ctrl+V or Cmd+V.")
    except Exception as e:
        print("Could not copy image to clipboard:", e)


def save_image_to_downloads(img, filename="image.png"):
    try:
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        save_path = os.path.join(downloads_path, filename)
        counter = 1
        original_filename, extension = os.path.splitext(filename)
        while os.path.exists(save_path):
            save_path = os.path.join(downloads_path, f"{original_filename}_{counter}{extension}")
            counter += 1
        img.save(save_path)
        print(f"Image saved to: {save_path}")
    except Exception as e:
        print(f"Could not save image to downloads folder: {e}")


def _draw_standard_block(draw, cfg, lines, font_path, default_x, default_y, default_size, default_scale, default_line_spacing, default_char_spacing, uppercase=True):
    x, y = _pos(cfg, default_x=default_x, default_y=default_y)
    draw_text_block_scaled(
        draw,
        _lines_with_override(cfg, lines),
        start_x=x,
        start_y=y,
        font_path=font_path,
        base_font_size=_cfg(cfg, "font_size", default_size),
        scale=_cfg(cfg, "scale", default_scale),
        line_spacing=_cfg(cfg, "line_spacing", default_line_spacing),
        char_spacing=_cfg(cfg, "char_spacing", default_char_spacing),
        horizontal_squish=_cfg(cfg, "horizontal_squish", 1.0),
        uppercase=uppercase,
    )


def add_ups_text(image_path, info_data, text_layout=None, zip_barcode_cfg=None):
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)
    t = text_layout or {}
    z = zip_barcode_cfg or {}

    _draw_standard_block(draw, t.get("sender", {}), [info_data["sender"], info_data["sender_address"], info_data["sender_2nd_line"]], FONT_MAIN, 26, 3, 28, 1.3, -8, 1.3)
    _draw_standard_block(draw, t.get("receiver", {}), [info_data["receiver"], info_data["receiver_address"]], FONT_MAIN, 105, 235, 40, 1.2, -9, 1.5)
    _draw_standard_block(draw, t.get("receiver_2nd", {}), [info_data["receiver_2nd_line"]], FONT_BOLD, 105, 310, 60, 1.2, 0, -4)
    _draw_standard_block(draw, t.get("tracking", {}), [format_ups_tracking(info_data["tracking_number"])], FONT_MAIN, 293, 1055, 44, 1.1, 0, 0.3)

    center_text_cfg = t.get("center_text", {})
    state_abbrev = info_data["receiver_2nd_line"].split()[-2]
    zip_prefix = info_data["receiver_2nd_line"].split()[-1][:2]
    generated_center = f"{state_abbrev} {zip_prefix}5 7-67"
    center_text = str(_cfg(center_text_cfg, "text", generated_center) or generated_center)
    center_scale = _cfg(center_text_cfg, "scale", 2.5)
    center_font_size = _cfg(center_text_cfg, "font_size", 50)
    center_char_spacing = _cfg(center_text_cfg, "char_spacing", -10)
    center_font = ImageFont.truetype(FONT_BOLD, max(1, int(center_font_size * center_scale)))
    center_x_default = ((image.size[0] - center_font.getlength(center_text)) / 2) + 115
    center_x = _cfg(center_text_cfg, "x_position", center_x_default) + _cfg(center_text_cfg, "x_offset", 0)
    center_y = _cfg(center_text_cfg, "y_position", 600) + _cfg(center_text_cfg, "y_offset", 0)
    x_cursor = center_x
    for char in center_text:
        draw.text((x_cursor, int(center_y)), char, font=center_font, fill=(0, 0, 0))
        bbox = center_font.getbbox(char)
        x_cursor += (bbox[2] - bbox[0]) + (center_char_spacing * center_scale)

    zip_code = info_data["receiver_2nd_line"].split()[-1]
    zip_barcode_img = create_zip_barcode(
        zip_code,
        module_height=_cfg(z, "module_height", 40.0),
        quiet_zone=_cfg(z, "whitespace", 6.5),
        resize_to=_scaled_size(z, 720, 170),
    )
    image.paste(zip_barcode_img, _xy(z, 285, 765), zip_barcode_img)

    top_cfg = t.get("top_number", {})
    top_text = str(_cfg(top_cfg, "text", "1") or "1")
    top_scale = _cfg(top_cfg, "scale", 1.0)
    top_size = _cfg(top_cfg, "font_size", 52)
    top_font = ImageFont.truetype(FONT_BOLD, max(1, int(top_size * top_scale)))
    top_x_default = (image.size[0] - top_font.getlength(top_text)) / 2 + 77
    top_x = _cfg(top_cfg, "x_position", top_x_default) + _cfg(top_cfg, "x_offset", 0)
    top_y = _cfg(top_cfg, "y_position", -5) + _cfg(top_cfg, "y_offset", 0)
    draw_text_block_scaled(
        draw,
        [top_text],
        start_x=top_x,
        start_y=top_y,
        font_path=FONT_BOLD,
        base_font_size=top_size,
        scale=top_scale,
        line_spacing=_cfg(top_cfg, "line_spacing", 0),
        char_spacing=_cfg(top_cfg, "char_spacing", 0),
        horizontal_squish=_cfg(top_cfg, "horizontal_squish", 1.0),
    )

    image.save(image_path)
    if _is_final_blank_output(image_path):
        copy_image_to_clipboard(image)
        save_image_to_downloads(image, filename="image.png")


def add_usps_text(image_path, info_data, text_layout=None, zip_barcode_cfg=None):
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)
    t = text_layout or {}
    formatted_tracking = format_usps_tracking(info_data["tracking_number"])
    _draw_standard_block(draw, t.get("sender", {}), [info_data["sender"], info_data["sender_address"], info_data["sender_2nd_line"]], FONT_ARIAL, 20, 474, 28, 1.0, 7, 1.3)
    _draw_standard_block(draw, t.get("receiver", {}), [info_data["receiver"], info_data["receiver_address"]], FONT_ARIAL, 165, 725, 40, 1.1, 8, 1.5)
    _draw_standard_block(draw, t.get("receiver_2nd", {}), [info_data["receiver_2nd_line"]], FONT_ARIAL, 165, 825, 40, 1.1, 0, 0)
    _draw_standard_block(draw, t.get("tracking", {}), [formatted_tracking], FONT_ARIAL, 262, 1270, 60, 0.6, 0, -1.5)
    image.save(image_path)
    if _is_final_blank_output(image_path):
        copy_image_to_clipboard(image)
        save_image_to_downloads(image, filename="image.png")


def add_fedex_text(image_path, info_data, text_layout=None, zip_barcode_cfg=None):
    image = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(image)
    receiver_city, receiver_state, receiver_zip = _split_city_state_zip(info_data["receiver_2nd_line"], fallback_zip=info_data.get("receiver_zip", ""))
    t = text_layout or {}
    z = zip_barcode_cfg or {}

    def fedex_block(key, lines, default_x, default_y, default_size, default_scale, default_line, default_char, font=FONT_ARIAL):
        cfg = t.get(key, {})
        x, y = _pos(cfg, default_x=default_x, default_y=default_y)
        draw_text_block_scaled_fedex(
            draw,
            _lines_with_override(cfg, lines),
            start_x=x,
            start_y=y,
            font_path=font,
            base_font_size=_cfg(cfg, "font_size", default_size),
            scale=_cfg(cfg, "scale", default_scale),
            line_spacing=_cfg(cfg, "line_spacing", default_line),
            char_spacing=_cfg(cfg, "char_spacing", default_char),
            horizontal_squish=_cfg(cfg, "horizontal_squish", 0.9),
        )

    fedex_block("from_label", ["FROM:"], 70, 14, 34, 1.0, 20, 1)
    fedex_block("sender", [info_data["sender"], info_data["sender_address"], info_data["sender_2nd_line"]], 70, 52, 33, 1.0, 20, 1)
    fedex_block("ship_to_label", ["SHIP TO:"], 70, 262, 34, 1.0, 0, 1)
    receiver_line_2 = f"{receiver_city}  {receiver_state}  {receiver_zip}" if receiver_city and receiver_state and receiver_zip else info_data["receiver_2nd_line"]
    fedex_block("receiver", [info_data["receiver"], info_data["receiver_address"], receiver_line_2], 82, 312, 42, 1.05, 18, 1)

    tracking = format_fedex_tracking(info_data["tracking_number"])
    fedex_block("tracking", [tracking], 170, 1220, 62, 1.0, 0, 0, font=FONT_BOLD)
    prefix = f"9622  0137  0  (000  000  0000)  0  00  {tracking}"
    fedex_block("tracking_prefix", [prefix], 258, 1480, 55, 0.8, 0, 2.5, font=FONT_BOLD)

    if receiver_zip:
        zip_cfg = t.get("receiver_zip", {})
        _draw_standard_block(draw, zip_cfg, [receiver_zip], FONT_BOLD, 1120, 1340, 60, 1.1, 0, 0)
        zip_barcode_img = create_zip_barcode(
            receiver_zip,
            module_height=_cfg(z, "module_height", 40.0),
            quiet_zone=_cfg(z, "whitespace", 6.5),
            resize_to=_scaled_size(z, 720, 170),
        )
        image.paste(zip_barcode_img, _xy(z, 1120, 1340), zip_barcode_img)

    image.save(image_path)
    if _is_final_blank_output(image_path):
        copy_image_to_clipboard(image)
        save_image_to_downloads(image, filename="image.png")
