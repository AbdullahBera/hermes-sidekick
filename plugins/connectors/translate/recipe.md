# Translate — model-native, private

"translate this to Turkish", "what does this French email say?", "how do I say 'where's the station'
in Japanese?" — it translates naturally, both directions, any language pair.

## Security posture
- **No translate service:** the **model itself** does the translation. Nothing is sent to Google
  Translate, DeepL, or any third party — no extra data leaves the VM beyond the normal model request.
- **Keyless:** nothing to sign up for, no API key.
- **Read-only:** it just gives you the translation — no account actions.

## Setup
Nothing required — it's a built-in capability. Optional tuning in the profile:
```yaml
connectors:
  translate:
    enabled: true
    default_target: ""     # a language to assume when you don't name one (e.g. "English")
    formality: natural     # natural | formal | casual
```

## How it works
- **Detects** the source language automatically; you don't have to say what it is.
- **Translates for meaning** — idioms and tone over literal word-for-word — and preserves register
  per `formality` (a formal email stays formal; a casual text stays casual).
- Names the detected language when it's ambiguous, and can give a short literal gloss if you ask.
- Pairs with the message rule in SOUL.md (Turkish names → Turkish); this is the general any-language tool.

## Verify
- "translate 'good morning, hope you slept well' to Turkish" → a natural Turkish rendering.
- Paste a sentence in another language and ask "what does this say?" → the meaning in your language.
