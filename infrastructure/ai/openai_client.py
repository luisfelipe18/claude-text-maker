# --- filepath: video_narrative_processor/infrastructure/ai/openai_client.py
import json
from pathlib import Path

from openai import OpenAI

from utils.exceptions import RewriteError
from core.models.artifacts import RewrittenContent

class OpenAIRewriter:
    def __init__(self, api_key: str, model: str, prompt_template: str | None = None):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.prompt_template = prompt_template

    def rewrite_text(self, prompt: str, text: str) -> dict:
        r = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
        )
        content = r.choices[0].message.content
        return json.loads(content)

    def rewrite(self, transcript_txt: Path, out_dir: Path, min_w: int, max_w: int):
        try:
            text = transcript_txt.read_text(encoding="utf-8")
            tpl = self.prompt_template or (
                "CONTEXTO: Eres experto en guiones virales para redes sociales."
                "LONGITUD: ENTRE {MIN_WORDS} y {MAX_WORDS} palabras."
                'SALIDA JSON ESTRICTO: {\"titulo\": str, \\"cuerpo\\": str}'
            )
            prompt = tpl.replace("{MIN_WORDS}", str(min_w)).replace("{MAX_WORDS}", str(max_w))
            data = self.rewrite_text(prompt, text)
            body = (data.get("cuerpo") or "").strip()
            wc = len([w for w in body.split() if w])
            data["palabras"] = wc
            out = out_dir / f"{transcript_txt.stem}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return RewrittenContent(json_path=out, words_count=wc)
        except Exception as e:
            raise RewriteError(str(e))
