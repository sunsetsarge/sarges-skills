"""Lane D eval: 16x16 item icon + palette variants + 2-frame bob.

Exercises ramp/outline/masking, stats, palette-swap variants, animation,
GIF + spritesheet export -- the five things Lane D is supposed to beat the
generation lanes at.
"""
import sys
sys.path.insert(0, r"C:\Claude\sarges-skills\skills\pixel-art-studio\scripts")
from pixelstudio import Sprite, ramp

INK = "#1a1c2c"
GLASS = ramp("#41a6f6", 4)      # blue liquid, hue-shifted ramp
CORK = ramp("#b1793c", 3)
SHINE = "#f4f4f4"


def palette_for(liquid):
    """GOTCHA: Sprite(snap=True) is the DEFAULT -- any color not in the palette is
    silently snapped to the nearest entry. A variant must carry its own ramp in the
    palette or it comes out the base color with no error."""
    return liquid + CORK + [INK, SHINE]


def draw_potion(s, liquid, y=0):
    """Draw the potion at vertical offset y. liquid = 4-step ramp."""
    # cork
    s.rect(6, 1 + y, 9, 3, CORK[1])
    s.rect(6, 1 + y, 9, 1, CORK[2])
    # neck
    s.rect(6, 4 + y, 9, 5, liquid[3])
    # body: darkest first, then restack lighter shifted toward the light (top-left)
    s.ellipse(3, 6 + y, 12, 14 + y, liquid[0])
    s.ellipse(3, 6 + y, 11, 13 + y, liquid[1], only="opaque")
    s.ellipse(4, 7 + y, 10, 12 + y, liquid[2], only="opaque")
    # specular highlight, not hugging the outline
    s.px(5, 9 + y, SHINE)
    s.px(5, 10 + y, liquid[3])
    # selout: dark outline outside the silhouette
    s.outline(INK, where="outside")


def build(name, liquid):
    s = Sprite(16, 16, palette=palette_for(liquid))
    s.add_frame(copy=False)                 # frame 2 (frames are 1-BASED)
    s.use(frame=1); draw_potion(s, liquid, y=0)
    s.use(frame=2); draw_potion(s, liquid, y=-1)
    s.set_duration(320, frames="all")
    s.preview(f"{name}_preview.png", scale=12)
    s.stats()
    s.save_png(f"{name}.png", frame=1)                 # 1x master
    s.save_png(f"{name}@8x.png", frame=1, scale=8)     # display copy
    s.save_gif(f"{name}_bob.gif", scale=6)
    s.save_spritesheet(f"{name}_sheet.png", layout="horizontal")
    return s


build("potion_blue", GLASS)
# palette-swap variant: seconds, not a re-roll
build("potion_red", ramp("#e43b44", 4))
build("potion_green", ramp("#38b764", 4))
