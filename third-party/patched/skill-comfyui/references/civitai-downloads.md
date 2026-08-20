# CivitAI Model Downloads

---

## Known Issues & Rules (CHECK FIRST)

### Rule 1: Correct Download Endpoint

**WRONG:** `https://civitai.com/api/v1/download/models/{id}` → returns 404 or HTML page
**CORRECT:** `https://civitai.com/api/download/models/{id}?token={token}`

Always confirm the URL by calling the metadata endpoint first:

```
curl -s -H "Authorization: Bearer {token}" https://civitai.com/api/v1/model-versions/{id}
```

Use the `downloadUrl` field from the response — this is the authoritative source.

### Rule 2: Validate Downloaded Files

After every download, check the file is a real model (not HTML):

```powershell
$size = (Get-Item $out).Length
$head = [System.IO.File]::ReadAllBytes($out)[0..4]
if ($size -lt 1MB -or [System.Text.Encoding]::ASCII.GetString($head) -eq "<!DOC") {
    Write-Host "BAD FILE — HTML received, not a model"
    Remove-Item $out
}
```

### Rule 3: Token Authentication

Pass token in **both** the Authorization header AND as a query param for maximum compatibility:

```
curl.exe -L -H "Authorization: Bearer {token}" "https://civitai.com/api/download/models/{id}?token={token}"
```

### Rule 4: API Token vs MCP Token

The CivitAI MCP server token is NOT the same as Blaine's personal API key. Downloads always require Blaine's personal API key from civitai.com/user/account. (APP-LL-012, APP-LL-013)

---

## Download Template

```powershell
$token = "{BLAINE_CIVITAI_API_KEY}"
$dest = "D:\AI\ComfyUI_Models\Loras"

# Step 1: Get authoritative download URL
$meta = curl.exe -s -H "Authorization: Bearer $token" "https://civitai.com/api/v1/model-versions/{VERSION_ID}" | ConvertFrom-Json
$url = $meta.downloadUrl + "?token=$token"

# Step 2: Download
$out = Join-Path $dest "{FILENAME}.safetensors"
curl.exe -L -H "Authorization: Bearer $token" -o $out $url

# Step 3: Validate
$size = (Get-Item $out).Length
if ($size -lt 1MB) { Write-Host "WARNING: File may be HTML — check $out"; }
else { Write-Host "OK: $([math]::Round($size/1MB,2)) MB" }
```

---

## MCP Tool Usage

- `civitai:get_model_version(modelVersionId: {id})` — get metadata. Check `.downloadUrl` and `.files[].sizeKB`
- `civitai:get_model(modelId: {id})` — find version IDs from a model ID
- `civitai:get_download_url` — safe to use once you have a version ID (unaffected by null-description bug)

**Null description bug (CUI-LL-014):** If `get_model_version` throws a schema validation error, the model's description field is null. Do NOT retry — use `web_fetch` on the civitai.com model page directly to extract version IDs, trigger words, and settings.
