import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from PIL import Image, ImageDraw

from ftid_gen.render.barcodes import create_zip_barcode, generate_barcode_image
from ftid_gen.render.text_overlay import add_fedex_text, add_ups_text, add_usps_text
from ftid_gen.config import SCRIPT_DIR

try:
    from ftid_gen.settings_manager import settings
except ImportError:
    settings = None


def _get_layout(carrier: str, layout_overrides: Optional[Dict] = None) -> Dict:
    carrier = carrier.lower().replace("ftid_", "")
    if layout_overrides:
        if carrier in layout_overrides:
            return layout_overrides[carrier]
        return layout_overrides
    if settings:
        return settings.get(f"label_layout.{carrier}", {})
    return {}


def resolve_barcode_config(carrier_layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    barcode_cfg = (carrier_layout or {}).get("barcode", {})
    return {
        "module_height": barcode_cfg.get("module_height", 15.0),
        "quiet_zone": barcode_cfg.get("whitespace", 6.5),
        "width": barcode_cfg.get("width", 970),
        "height": barcode_cfg.get("height", 300),
        "x_position": barcode_cfg.get("x_position", 90),
        "y_position": barcode_cfg.get("y_position", 1190),
        "whitespace": barcode_cfg.get("whitespace", 0),
    }


def resolve_maxicode_config(carrier_layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    maxicode_cfg = (carrier_layout or {}).get("maxicode", {})
    return {
        "scale": maxicode_cfg.get("scale"),
        "whitespace": maxicode_cfg.get("whitespace", 0),
        "width": maxicode_cfg.get("width", 312),
        "height": maxicode_cfg.get("height", 288),
        "x_offset": maxicode_cfg.get("x_offset", 42),
        "y_offset": maxicode_cfg.get("y_offset", -1144),
    }


def resolve_zip_barcode_config(carrier_layout: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    zip_cfg = (carrier_layout or {}).get("zip_barcode", {})
    return {
        "module_height": zip_cfg.get("module_height", 40.0),
        "quiet_zone": zip_cfg.get("whitespace", 6.5),
        "width": zip_cfg.get("width", 720),
        "height": zip_cfg.get("height", 170),
        "x_position": zip_cfg.get("x_position", 285),
        "y_position": zip_cfg.get("y_position", 765),
        "whitespace": zip_cfg.get("whitespace", 0),
    }


def resolve_template_path(
    carrier_layout: Optional[Dict[str, Any]],
    default_template_path: str | Path,
) -> Path:
    default_path = Path(default_template_path)
    custom_path = (carrier_layout or {}).get("custom_template_path")
    if custom_path:
        candidate = Path(str(custom_path)).expanduser()
        if candidate.exists():
            return candidate
    return default_path


def _safe_filename_part(value: str) -> str:
    safe = "".join(c for c in value if c.isalnum() or c in "-_")
    return safe[:48] or "label"


def _carrier_slug(name: str) -> str:
    label_type = name.lower()
    if "usps" in label_type:
        return "usps"
    if "ups" in label_type:
        return "ups"
    if "fedex" in label_type:
        return "fedex"
    return "unknown"


def _run_directory(output_dir: Path, name: str, ftid_info: Optional[Dict[str, Any]]) -> Path:
    tracking = ""
    if ftid_info and "original_tracking" in ftid_info:
        tracking = _safe_filename_part(str(ftid_info["original_tracking"]))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"{timestamp}_{uuid4().hex[:8]}"
    if tracking:
        run_id = f"{run_id}_{tracking}"

    directory = output_dir / "generated-labels" / _carrier_slug(name) / run_id
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def _full_template_path_for(blank_template_path: Path) -> Path:
    if "_blank" not in blank_template_path.name:
        return blank_template_path
    return blank_template_path.with_name(blank_template_path.name.replace("_blank", "_full", 1))


def _clear_region(image: Image.Image, box: Tuple[int, int, int, int], opacity: float = 1.0) -> None:
    left, top, right, bottom = box
    clamped = (
        max(0, left),
        max(0, top),
        min(image.width, right),
        min(image.height, bottom),
    )
    if clamped[0] >= clamped[2] or clamped[1] >= clamped[3]:
        return

    alpha = max(0, min(255, int(round(float(opacity) * 255))))
    if alpha >= 255:
        ImageDraw.Draw(image).rectangle(clamped, fill=(255, 255, 255, 255))
        return
    if alpha <= 0:
        return

    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    ImageDraw.Draw(overlay).rectangle(clamped, fill=(255, 255, 255, alpha))
    image.alpha_composite(overlay)


def _template_mask_config(name: str, carrier_layout: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    label_type = name.lower()
    layout = carrier_layout or {}
    mask_cfg = layout.get("template_mask") or {}

    if "ups" in label_type:
        return {
            "enabled": mask_cfg.get("enabled", True),
            "x_position": mask_cfg.get("x_position", 0),
            "y_position": mask_cfg.get("y_position", 585),
            "width": mask_cfg.get("width", 405),
            "height": mask_cfg.get("height", 375),
            "opacity": mask_cfg.get("opacity", 0.9),
        }

    return {
        "enabled": mask_cfg.get("enabled", False),
        "x_position": mask_cfg.get("x_position", 0),
        "y_position": mask_cfg.get("y_position", 0),
        "width": mask_cfg.get("width", 0),
        "height": mask_cfg.get("height", 0),
        "opacity": mask_cfg.get("opacity", 1.0),
    }


def _sanitize_blank_template(name: str, image: Image.Image, carrier_layout: Optional[Dict[str, Any]] = None) -> Image.Image:
    sanitized = image.convert("RGBA").copy()
    mask_cfg = _template_mask_config(name, carrier_layout)

    if mask_cfg.get("enabled", False):
        x = int(mask_cfg.get("x_position", 0))
        y = int(mask_cfg.get("y_position", 0))
        width = int(mask_cfg.get("width", 0))
        height = int(mask_cfg.get("height", 0))
        if width > 0 and height > 0:
            _clear_region(sanitized, (x, y, x + width, y + height), opacity=mask_cfg.get("opacity", 1.0))

    return sanitized


def _prepare_overlay_image(image: Image.Image, padding: int = 0) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = []
    for r, g, b, a in rgba.getdata():
        if a == 0 or (r > 250 and g > 250 and b > 250):
            pixels.append((255, 255, 255, 0))
        else:
            pixels.append((r, g, b, a))
    rgba.putdata(pixels)

    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        return rgba

    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(rgba.width, right + padding)
    bottom = min(rgba.height, bottom + padding)
    return rgba.crop((left, top, right, bottom))


def _paste_barcode_on_image(
    base: Image.Image,
    barcode_img: Image.Image,
    barcode_cfg: Dict[str, Any],
) -> None:
    size = (barcode_cfg["width"], barcode_cfg["height"])
    position = (barcode_cfg["x_position"], barcode_cfg["y_position"])
    prepared = _prepare_overlay_image(barcode_img, padding=barcode_cfg.get("whitespace", 0)).resize(size)
    base.paste(prepared, position, mask=prepared)


def _apply_maxicode_overlay(base: Image.Image, maxicode_cfg: Dict[str, Any], maxicode_path: str) -> None:
    if not os.path.exists(maxicode_path):
        return

    padding = maxicode_cfg.get("whitespace", 0)
    maxicode_img = _prepare_overlay_image(Image.open(maxicode_path), padding=padding)
    maxicode_img = maxicode_img.resize((maxicode_cfg["width"], maxicode_cfg["height"]))
    maxicode_position = (maxicode_cfg["x_offset"], base.height + maxicode_cfg["y_offset"])
    base.paste(maxicode_img, maxicode_position, mask=maxicode_img)


def compose_label(
    name: str,
    data: str,
    template_path: str | Path,
    ftid_info: Optional[Dict[str, Any]] = None,
    label_layout: Optional[Dict[str, Any]] = None,
    output_path: Optional[str | Path] = None,
) -> Tuple[Image.Image, str]:
    """Compose a full carrier label image using one Python rendering path."""
    carrier = _carrier_slug(name)
    carrier_layout = _get_layout(carrier, label_layout)
    default_template_path = Path(template_path)
    resolved_template_path = resolve_template_path(carrier_layout, default_template_path)

    barcode_cfg = resolve_barcode_config(carrier_layout)
    zip_barcode_cfg = resolve_zip_barcode_config(carrier_layout)
    maxicode_cfg = resolve_maxicode_config(carrier_layout)

    barcode_img = generate_barcode_image(
        data,
        module_height=barcode_cfg["module_height"],
        quiet_zone=barcode_cfg["quiet_zone"],
    )

    full_template_path = _full_template_path_for(default_template_path)
    blank_image = _sanitize_blank_template(name, Image.open(resolved_template_path), carrier_layout)
    if full_template_path.exists():
        with Image.open(full_template_path) as full_image:
            if blank_image.size != full_image.size:
                blank_image = blank_image.resize(full_image.size)

    base = blank_image.convert("RGBA")
    _paste_barcode_on_image(base, barcode_img, barcode_cfg)

    if ftid_info:
        label_path_for_text = output_path
        if label_path_for_text is None:
            label_path_for_text = default_template_path

        if "ups" in name.lower():
            from maxicode.pure_maxicode import generate_maxicode_image

            maxicode_path = default_template_path.parent / "maxicode_temp.png"
            if os.path.exists(maxicode_path):
                os.remove(maxicode_path)

            # Build MaxiCode data from ftid_info
            maxicode_data = ftid_info.get("tracking_bar", "")
            generate_maxicode_image(
                maxicode_data,
                str(maxicode_path),
                scale=maxicode_cfg.get("scale", 2),
            )
            _apply_maxicode_overlay(base, maxicode_cfg, maxicode_path)

            base.save(str(label_path_for_text))
            text_cfg = carrier_layout.get("text", {})
            add_ups_text(str(label_path_for_text), ftid_info, text_layout=text_cfg, zip_barcode_cfg=zip_barcode_cfg)
        elif "usps" in name.lower():
            base.save(str(label_path_for_text))
            text_cfg = carrier_layout.get("text", {})
            add_usps_text(str(label_path_for_text), ftid_info, text_layout=text_cfg, zip_barcode_cfg=zip_barcode_cfg)
        elif "fedex" in name.lower():
            base.save(str(label_path_for_text))
            text_cfg = carrier_layout.get("text", {})
            add_fedex_text(str(label_path_for_text), ftid_info, text_layout=text_cfg, zip_barcode_cfg=zip_barcode_cfg)
    else:
        if output_path:
            base.save(str(output_path))

    final_path = str(output_path or default_template_path)
    if output_path and os.path.exists(final_path):
        return barcode_img, final_path

    if output_path:
        base.save(final_path)
    return barcode_img, final_path


def position_barcode_on_label(
    name: str,
    barcode_img: Image.Image,
    template_path: str,
    output_path: str,
    layout_overrides: Optional[Dict] = None,
) -> None:
    carrier = _carrier_slug(name)
    carrier_layout = _get_layout(carrier, layout_overrides)
    barcode_cfg = resolve_barcode_config(carrier_layout)

    base = Image.open(template_path).convert("RGBA")
    _paste_barcode_on_image(base, barcode_img, barcode_cfg)
    base.save(output_path)


def process_label(
    name: str,
    data: str,
    template_path: str,
    script_dir: str,
    ftid_info: Optional[Dict[str, Any]] = None,
    label_layout: Optional[Dict[str, Any]] = None,
) -> Tuple[Image.Image, str]:
    try:
        from ftid_gen.config import OUTPUT_DIR

        output_dir = Path(OUTPUT_DIR)
    except ImportError:
        output_dir = Path(script_dir)

    run_dir = _run_directory(output_dir, name, ftid_info)
    default_template_path = Path(template_path)
    blank_output_path = run_dir / default_template_path.name

    barcode_img, label_path = compose_label(
        name,
        data,
        default_template_path,
        ftid_info=ftid_info,
        label_layout=label_layout,
        output_path=blank_output_path,
    )

    barcode_path = run_dir / "barcode.png"
    barcode_img.save(barcode_path)
    return barcode_img, label_path
