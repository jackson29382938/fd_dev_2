# UPS Template Mask

The UPS white rectangle was not removed. It is now represented as a configurable `template_mask` in the label layout settings.

## Original hardcoded mask location

The old hardcoded UPS mask was:

```python
_clear_region(sanitized, (0, 585, 405, 960))
```

That means:

- `x_position`: `0`
- `y_position`: `585`
- `width`: `405`
- `height`: `375`
- Right edge: `405`
- Bottom edge: `960`

Coordinates are measured in template pixels from the top-left of the UPS template.

## Configurable settings

The configurable mask lives under:

```json
{
  "label_layout": {
    "ups": {
      "template_mask": {
        "enabled": true,
        "x_position": 0,
        "y_position": 585,
        "width": 405,
        "height": 375,
        "opacity": 0.9
      }
    }
  }
}
```

## How to tune it manually

Use these keys if you edit/export/import settings JSON:

- `label_layout.ups.template_mask.enabled`
- `label_layout.ups.template_mask.x_position`
- `label_layout.ups.template_mask.y_position`
- `label_layout.ups.template_mask.width`
- `label_layout.ups.template_mask.height`
- `label_layout.ups.template_mask.opacity`

`opacity` is a decimal from `0.0` to `1.0`:

- `1.0` = fully white, same as the old destructive clear
- `0.9` = mostly white but slightly preserves underlying template lines
- `0.0` = no visible mask

## Implementation notes

The mask is applied in:

- `python/ftid_gen/label_processor.py`
- `swift/vendor/backend/ftid_gen/label_processor.py`

The default settings are defined in:

- `python/ftid_gen/settings_manager.py`
- `swift/vendor/backend/ftid_gen/settings_manager.py`

The backend merges missing default keys into existing settings files, so existing users should receive the new `template_mask` defaults without resetting all settings.
