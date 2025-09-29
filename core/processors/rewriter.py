# --- filepath: video_narrative_processor/core/processors/rewriter.py
from pathlib import Path
from core.processors.base import AIRewriter
from infrastructure.ai.openai_client import OpenAIRewriter

class DefaultAIRewriter(AIRewriter):
    def __init__(self, api_key: str, model: str, prompt_template: str | None = None):
        self.impl = OpenAIRewriter(api_key=api_key, model=model, prompt_template=prompt_template)

    def rewrite(self, transcript_txt: Path, out_dir: Path, min_w: int, max_w: int):
        return self.impl.rewrite(transcript_txt, out_dir, min_w, max_w)
