import re
from pathlib import Path

base_path = Path(__file__).resolve().parent.parent
files = list((base_path / 'app' / 'templates' / 'auth').glob('*.html'))

patterns = [
    (re.compile(r'height:\s*calc\(100vh - 80px\);'), 'height: 100vh;'),
    (re.compile(r'min-height:\s*calc\(100vh - 80px\);'), 'height: 100vh;'),
    (
        re.compile(
            r'background:\s*url\("\{\{ url_for\(\'static\', filename=\'images/bg/bg-image\.png\'\) \}\}"\)\s*center\s*/\s*cover\s*no-repeat;'
        ),
        'background-image: url("{{ url_for(\'static\', filename=\'images/bg/bg-image-petsona.png\') }}");\n  background-position: center;\n  background-size: cover;\n  background-repeat: no-repeat;'
    ),
    (
        re.compile(
            r'background:\s*url\("\{\{ url_for\(\'static\', filename=\'images/bg/bg-image\.png\'\) \}\}"\);'
        ),
        'background-image: url("{{ url_for(\'static\', filename=\'images/bg/bg-image-petsona.png\') }}");\n  background-position: center;\n  background-size: cover;\n  background-repeat: no-repeat;'
    ),
    (re.compile(r'rgba\(255, 255, 255, 0\.4\)'), 'rgba(255, 255, 255, 0.6)'),
]

print(f'Processing {len(files)} auth HTML files...')
for path in files:
    text = path.read_text(encoding='utf-8')
    new_text = text
    for pattern, replacement in patterns:
        new_text = pattern.sub(replacement, new_text)
    if new_text != text:
        path.write_text(new_text, encoding='utf-8')
        print(f'Updated {path.name}')
