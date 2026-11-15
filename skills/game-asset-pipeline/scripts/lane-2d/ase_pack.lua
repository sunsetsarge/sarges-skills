-- ase_pack.lua: runs INSIDE Aseprite (headless). Driven by ase_pack.py; do not run by hand.
--   Aseprite.exe -b --script-param job=<job.json> --script ase_pack.lua
-- Reads the job file, builds one RGB sprite from the frame PNGs (tags, timing, optional
-- anchor slice), optionally locks it to a palette with a transparent entry at index 0,
-- saves the .aseprite and writes a stats file. A script error still writes a stats file
-- (ok=false + the message); a MISSING stats file means Aseprite never got that far.
--
-- Job file fields (all paths use forward slashes):
--   frames[]          cell PNGs in final order (RGBA, all the same size)
--   durations[]       one duration per frame, milliseconds
--   tags[]            {name, from, to, dir, repeats}   from/to are 1-based
--   pivot             {x, y} or null: adds the slice "anchor" over the whole cell
--   palette           null, {file = path} or {colors = {{r,g,b}, ...}}
--   dither            "none" | "bayer2x2" | "bayer4x4" | "bayer8x8"   (palette lock only)
--   alpha_threshold   0..255: alpha >= this becomes opaque, below becomes transparent
--   out_aseprite      where to save the .aseprite
--   stats             where to write the stats file

local ANI = {
  forward = AniDir.FORWARD, reverse = AniDir.REVERSE,
  pingpong = AniDir.PING_PONG, pingpong_reverse = AniDir.PING_PONG_REVERSE,
}

local function readfile(path)
  local f = assert(io.open(path, "rb"))
  local s = f:read("a")
  f:close()
  return s
end

local job = json.decode(readfile(app.params["job"]))
local stats = { ok = false }

local function writestats()
  local f = assert(io.open(job.stats, "wb"))
  f:write(json.encode(stats))
  f:close()
end

-- alpha is made binary at `thr`; returns the new image and its opaque-pixel count
local function binarize(img, thr)
  assert(img.rowStride == img.width * 4, "unexpected RGB row stride")
  local b = img.bytes
  local n = #b // 4
  local out, opaque = {}, 0
  for i = 0, n - 1 do
    local r, g, bl, a = string.byte(b, i * 4 + 1, i * 4 + 4)
    if a >= thr then
      out[i + 1] = string.char(r, g, bl, 255)
      opaque = opaque + 1
    else
      out[i + 1] = "\0\0\0\0"
    end
  end
  local res = Image(img.width, img.height, ColorMode.RGB)
  res.bytes = table.concat(out)
  return res, opaque
end

local function countOpaque(spr)
  local n = 0
  for _, cel in ipairs(spr.cels) do
    local img = cel.image
    if img.colorMode == ColorMode.RGB then
      for it in img:pixels() do
        if app.pixelColor.rgbaA(it()) > 0 then n = n + 1 end
      end
    else
      local t = spr.transparentColor
      for it in img:pixels() do
        if it() ~= t then n = n + 1 end
      end
    end
  end
  return n
end

local function main()
  local frames = job.frames
  assert(#frames > 0, "job has no frames")
  local first = Image{ fromFile = frames[1] }
  assert(first, "cannot load " .. frames[1])
  local w, h = first.width, first.height

  local spr = Sprite(w, h, ColorMode.RGB)
  app.sprite = spr
  for _ = 2, #frames do spr:newEmptyFrame() end
  local layer = spr.layers[1]
  layer.name = "art"

  local lock = job.palette ~= nil
  local thr = job.alpha_threshold or 128
  local raw_opaque = 0
  local before = 0
  for i, path in ipairs(frames) do
    local img = Image{ fromFile = path }
    assert(img, "cannot load " .. path)
    assert(img.width == w and img.height == h, "frame size mismatch: " .. path)
    assert(img.colorMode == ColorMode.RGB, "frame is not RGB(A): " .. path)
    if lock then
      for it in img:pixels() do
        if app.pixelColor.rgbaA(it()) > 0 then raw_opaque = raw_opaque + 1 end
      end
      local bin, n = binarize(img, thr)
      img = bin
      before = before + n
    end
    spr:newCel(layer, i, img, Point(0, 0))
    spr.frames[i].duration = (job.durations[i] or 100) / 1000
  end
  if not lock then
    before = countOpaque(spr)
    raw_opaque = before
  end

  -- tags (1-based inclusive)
  for _, t in ipairs(job.tags or {}) do
    local tag = spr:newTag(t.from, t.to)
    tag.name = t.name
    tag.aniDir = assert(ANI[t.dir], "bad direction " .. tostring(t.dir))
    if t.repeats then tag.repeats = t.repeats end
  end

  -- anchor slice
  if job.pivot then
    local s = spr:newSlice(Rectangle(0, 0, w, h))
    s.name = "anchor"
    s.pivot = Point(job.pivot.x, job.pivot.y)
  end

  -- palette lock: index 0 is a transparent entry, real colours start at 1, so no real
  -- colour can land on the transparent index
  if lock then
    local src
    if job.palette.file then
      src = Palette{ fromFile = job.palette.file }
      assert(src, "cannot load palette " .. job.palette.file)
    else
      local cols = job.palette.colors
      src = Palette(#cols)
      for i, c in ipairs(cols) do
        src:setColor(i - 1, Color{ r = c[1], g = c[2], b = c[3], a = 255 })
      end
    end
    local n = #src
    assert(n >= 1, "palette is empty")
    assert(n <= 255, "palette has " .. n .. " colours; indexed mode holds at most 255 plus the transparent entry")
    local np = Palette(n + 1)
    np:setColor(0, Color{ r = 0, g = 0, b = 0, a = 0 })
    local hex = {}
    for i = 0, n - 1 do
      local c = src:getColor(i)
      np:setColor(i + 1, Color{ r = c.red, g = c.green, b = c.blue, a = 255 })
      hex[#hex + 1] = string.format("%02x%02x%02x", c.red, c.green, c.blue)
    end
    spr:setPalette(np)
    spr.transparentColor = 0
    if job.dither and job.dither ~= "none" then
      app.command.ChangePixelFormat{ format = "indexed", dithering = "ordered", ["dithering-matrix"] = job.dither }
    else
      app.command.ChangePixelFormat{ format = "indexed", dithering = "none" }
    end
    assert(spr.colorMode == ColorMode.INDEXED, "sprite did not become indexed")
    stats.palette = hex
  end

  local after = countOpaque(spr)
  spr:saveAs(job.out_aseprite)
  assert(app.fs.isFile(job.out_aseprite) and app.fs.fileSize(job.out_aseprite) > 0, "save failed: " .. job.out_aseprite)

  stats.frames = #spr.frames
  stats.width = w
  stats.height = h
  stats.tags = #spr.tags
  stats.slices = #spr.slices
  stats.locked = lock
  stats.opaque_raw = raw_opaque
  stats.opaque_before = before
  stats.opaque_after = after
  stats.indexed = (spr.colorMode == ColorMode.INDEXED)
  stats.ok = true
end

local ok, err = xpcall(main, debug.traceback)
if not ok then
  stats.ok = false
  stats.error = tostring(err)
  print("ase_pack.lua ERROR: " .. tostring(err))
end
writestats()
