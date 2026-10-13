"""Check the public pet package's format, frame occupancy and safe cell edges."""
from pathlib import Path
import argparse
import hashlib
import json
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8]
CELL = (192, 208)

def validate(assets: Path) -> dict:
    errors = []
    manifest = json.loads((assets / 'pet.json').read_text(encoding='utf-8'))
    sheet = (assets / manifest['spritesheetPath']).resolve()
    if not sheet.is_relative_to(assets.resolve()):
        raise ValueError('Sprite sheet path must stay inside assets')
    data = sheet.read_bytes()
    if not 0 < len(data) <= 20 * 1024 * 1024:
        errors.append('Encoded image must be between 1 byte and 20 MiB')
    with Image.open(sheet) as opened:
        if opened.format not in {'PNG', 'WEBP'}:
            errors.append('Sprite sheet must be PNG or WebP')
        if opened.mode != 'RGBA':
            errors.append('Sprite sheet must include an alpha channel')
        image = opened.convert('RGBA')
    if image.size != (1536, 2288) or manifest.get('spriteVersionNumber') != 2:
        errors.append('Expected 1536x2288 v2 sheet')
    else:
        for row, count in enumerate(COUNTS):
            for col in range(8):
                alpha = image.crop((col*192, row*208, (col+1)*192, (row+1)*208)).getchannel('A')
                bounds = alpha.getbbox()
                if col >= count and bounds:
                    errors.append(f'Unused row {row}, frame {col} contains artwork')
                elif col < count and not bounds:
                    errors.append(f'Required row {row}, frame {col} is blank')
                elif bounds and (bounds[0] == 0 or bounds[1] == 0 or bounds[2] == 192 or bounds[3] == 208):
                    errors.append(f'Row {row}, frame {col} touches a cell edge')
    return {'valid': not errors, 'name': manifest['displayName'], 'sprite_version': 2, 'dimensions': list(image.size), 'cell_size': list(CELL), 'frame_counts': COUNTS, 'frames': sum(COUNTS), 'sha256': hashlib.sha256(data).hexdigest(), 'errors': errors}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, default=ROOT / 'assets')
    parser.add_argument('--json-out', type=Path, help='also save the validation result as UTF-8 JSON')
    args = parser.parse_args()
    result = validate(args.assets)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    print(encoded)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(encoded + '\n', encoding='utf-8')
    raise SystemExit(0 if result['valid'] else 1)

if __name__ == '__main__':
    main()

