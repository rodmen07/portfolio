from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1400, 788

BG      = (10,  12,  28)
ACCENT  = (99, 179, 237)
GREEN   = (72, 199, 142)
MUTED   = (113, 128, 150)
WHITE   = (255, 255, 255)
CARD_BG = (22,  27,  47)

img  = Image.new('RGB', (W, H), BG)
draw = ImageDraw.Draw(img)

def font(size, bold=False):
    candidates = [
        'C:/Windows/Fonts/arialbd.ttf' if bold else 'C:/Windows/Fonts/arial.ttf',
        'C:/Windows/Fonts/Arial.ttf',
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

f_kicker  = font(18)
f_title   = font(50, bold=True)
f_version = font(22, bold=True)
f_sub     = font(18)
f_tag     = font(15)

# kicker
draw.text((70, 52), 'INFRAPORTAL  \u2022  MICROSERVICES PLATFORM', font=f_kicker, fill=ACCENT)

# version badge
badge = '  v1.2 \u2014 Operational Maturity  '
bx, by = 70, 86
bbox = draw.textbbox((bx, by), badge, font=f_version)
draw.rounded_rectangle([bbox[0]-6, bbox[1]-5, bbox[2]+6, bbox[3]+5], radius=6, fill=ACCENT)
draw.text((bx, by), badge, font=f_version, fill=BG)

# headline
draw.text((70, 150), 'Production-grade operations.', font=f_title, fill=WHITE)
draw.text((70, 210), '11 Rust microservices. Fully observable.', font=f_title, fill=WHITE)

# divider
draw.line([(70, 282), (W-70, 282)], fill=MUTED, width=1)

# cards
cards = [
    ('v1.2.1', 'Data Export Pipeline',     'Bulk CSV & JSON export\nfrom reporting-service'),
    ('v1.2.2', 'Audit Trail & Compliance', 'Rust audit-service \u2014\nimmutable CRM mutation log'),
    ('v1.2.3', 'Portfolio Observability',  'CRM events \u2192 Observaboard\nadmin service health dashboard'),
    ('v1.2.4', 'Service Resilience',       'E2E tests \u2022 k6 load testing\nchaos engineering runbook'),
]

card_w  = 290
card_h  = 185
gap     = 22
start_x = 70
card_y  = 302

for i, (ver, title, desc) in enumerate(cards):
    cx = start_x + i * (card_w + gap)
    cy = card_y
    draw.rounded_rectangle([cx, cy, cx+card_w, cy+card_h], radius=10, fill=CARD_BG)
    draw.rounded_rectangle([cx, cy, cx+4, cy+card_h], radius=2, fill=ACCENT)
    draw.text((cx+16, cy+14), ver, font=f_tag, fill=ACCENT)
    draw.text((cx+16, cy+40), title, font=font(17, bold=True), fill=WHITE)
    for j, line in enumerate(desc.split('\n')):
        draw.text((cx+16, cy+72 + j*26), line, font=f_sub, fill=MUTED)
    # checkmark
    draw.text((cx+card_w-32, cy+card_h-30), '\u2713', font=font(22, bold=True), fill=GREEN)

# tech tags
tags = ['Rust / Axum', 'PostgreSQL', 'Google Cloud Run', 'GitHub Actions', 'k6', 'Gemini AI']
tx = 70
ty = 524
for tag in tags:
    tbbox = draw.textbbox((tx, ty), tag, font=f_tag)
    tw = tbbox[2] - tbbox[0] + 18
    draw.rounded_rectangle([tx-2, ty-5, tx+tw, ty+22], radius=5, fill=(30, 36, 60))
    draw.text((tx+7, ty), tag, font=f_tag, fill=ACCENT)
    tx += tw + 10

# bottom rule + footer
draw.line([(70, 566), (W-70, 566)], fill=MUTED, width=1)
draw.text((70, 582), 'github.com/rodmen07/microservices  \u2022  Roderick Mendoza', font=f_kicker, fill=MUTED)
stack = '11 services  \u2022  Rust + Python + Go'
sbbox = draw.textbbox((0, 0), stack, font=f_kicker)
sw = sbbox[2] - sbbox[0]
draw.text((W - 70 - sw, 582), stack, font=f_kicker, fill=MUTED)

out = 'd:/Projects/Portfolio/v1.2-linkedin.png'
img.save(out, 'PNG')
print('Saved:', out)
