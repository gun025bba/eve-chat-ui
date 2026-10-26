# Regenerate iOS splash images from the final mark (icons/mark-*.svg). Needs rsvg-convert + Pillow.
import subprocess, glob, re, io
from PIL import Image
for f in glob.glob('splash/*.png'):
    theme, w, h = re.match(r'splash/(dark|light)-(\d+)x(\d+)\.png', f).groups(); w, h = int(w), int(h)
    s = round(w * 0.28)
    png = subprocess.run(['rsvg-convert', '-w', str(s), '-h', str(s), f'icons/mark-{theme}.svg'], capture_output=True, check=True).stdout
    bg = Image.new('RGB', (w, h), (0, 0, 0) if theme == 'dark' else (255, 255, 255))
    m = Image.open(io.BytesIO(png)).convert('RGBA'); bg.paste(m, ((w - s) // 2, (h - s) // 2), m); bg.save(f, optimize=True)
