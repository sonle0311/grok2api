# Story studio engines

Provider-neutral pieces ported from KeywordToVideoStudio. grok2api remains the model gateway.

Ported:

- subtitle parse and beat timeline
- duration budget, sentence split, raw script parse
- LLM JSON extraction
- 15-second clip versus still rule

Not ported: Gemini and CLI providers, Veo, Kling, Edge-TTS, YouTube Data API, the broken v2 tree, executables, and secrets. Image, video, and voice calls stay on grok2api.
