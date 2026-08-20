# ComfyUI Prompt Engineering Guardrails

---

## DreamShaperXL + OldAnimeStyle LoRA — Masculine Characters

Both checkpoint and LoRA have a strong feminine bias for fantasy/armored characters. (CUI-LL-003)

**Always apply when generating male characters:**

```
Positive: (masculine:1.4), (male warrior:1.3), (strong jawline:1.3), (broad chest:1.2), (broad shoulders:1.2)
Negative: feminine, female, girl, woman, androgynous, soft features, delicate, slim waist
LoRA weight: reduce OldAnimeStyle to 0.6 max
```

---

## Enclosed Helmet + Large Horns — Concept Conflict

Large/dramatic horns trigger undead skull-face / open-helmet associations from training data. "Enclosed visor + large horns" is underrepresented. (CUI-LL-004)

**Always apply when prompting enclosed helmets with horns:**

```
Positive: (T-shaped visor:1.4), (fully enclosed helmet:1.3), (sealed faceplate:1.3), (no visible face), decorative helmet-mounted horns, structural swept horns
Negative: exposed face, open helmet, skull face, death knight face, undead face, visible face, no visor
Anchor archetype: Berserk-style dark armor, full plate helmet
```

---

## Full-Body Composition — DreamShaperXL Default Bias

DreamShaperXL + OldAnimeStyle defaults to bust/portrait for armored characters at standard resolutions. (CUI-LL-005)

**Always apply when full-body is required:**

```
Resolution: 768x1344 or 832x1248 (tall portrait forces vertical framing)
Positive: (full body shot:1.4), (full length:1.3), (from head to feet:1.2), (standing pose), (complete figure)
Negative: portrait, bust, headshot, cropped, upper body only, waist up
Alternative: use ControlNet pose skeleton to enforce composition
```
