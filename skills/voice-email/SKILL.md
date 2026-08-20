---
name: voice-email
version: 1.0.0
description: Send emails via natural voice commands - designed for accessibility
---

# Voice Email Skill

Send emails using natural voice commands. Perfect for accessibility use cases.

## What It Does

When you receive a voice message, parse and send an email:

**Input format:**
```
new email to [recipient], subject [subject], body [body], send
```

**Examples:**
- "new email to john@example.com, subject Hello, body How are you doing, send"
- "send email to mom@gmail.com, subject Dinner, body See you at 7pm, send"

## Setup Requirements

1. **gogcli** - Google CLI for Gmail
2. **Deepgram** - For voice transcription
3. **Telegram** - For receiving voice messages

### Install gogcli
```bash
curl -sL https://gogcli.ai/install.sh | bash
gog auth add your-email@gmail.com
```

### Configure Deepgram
Add to openclaw.json:
```json
{
  "tools": {
    "media": {
      "audio": {
        "enabled": true,
        "models": [{ "provider": "deepgram", "model": "nova-3" }]
      }
    }
  }
}
```

## How It Works

1. User sends voice message on Telegram
2. Deepgram transcribes the audio
3. Agent parses: recipient, subject, body
4. Agent sends via: `gog gmail send --to "..." --subject "..." --body "..."`
5. Agent confirms success

## Command Parser

The agent extracts:
- `to`: Email address (after "to", "email to", "send to")
- `subject`: Text after "subject"
- `body`: Text after "body" (before "send")

## Usage

Simply send a voice message with the command. The agent will:
1. Transcribe it
2. Parse the fields
3. Send the email
4. Confirm via voice/text

## Example Commands

- "new email to john@example.com, subject Hello, body Just saying hi, send"
- "email to mom, subject Check this out, body Here's what I found, send"
- "send email to boss@company.com, subject Project Update, body Phase one complete, send"
