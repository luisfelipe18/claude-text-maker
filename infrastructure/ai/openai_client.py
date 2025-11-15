# --- filepath: video_narrative_processor/infrastructure/ai/openai_client.py
import json
from pathlib import Path

from openai import OpenAI

from utils.exceptions import RewriteError
from core.models.artifacts import RewrittenContent
from core.models.configs import get_default_prompt

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

    def rewrite(self, transcript_txt: Path, out_dir: Path, min_w: int, max_w: int, max_retries: int = 3):
        try:
            text = transcript_txt.read_text(encoding="utf-8")
            # Usar el prompt desde la configuración central
            base_prompt = self.prompt_template or get_default_prompt()

            for attempt in range(max_retries):
                # Construir prompt con información de reintento si es necesario
                if attempt == 0:
                    prompt = base_prompt.replace("{MIN_WORDS}", str(min_w)).replace("{MAX_WORDS}", str(max_w))
                else:
                    # En reintentos, agregar información específica sobre el problema
                    retry_instruction = f"\n\nREINTENTO {attempt}: El intento anterior tuvo {previous_wc} palabras. DEBES generar EXACTAMENTE entre {min_w} y {max_w} palabras. "
                    if previous_wc < min_w:
                        retry_instruction += f"NECESITAS AGREGAR {min_w - previous_wc} palabras más como mínimo."
                    elif previous_wc > max_w:
                        retry_instruction += f"NECESITAS REDUCIR {previous_wc - max_w} palabras como mínimo."

                    prompt = base_prompt.replace("{MIN_WORDS}", str(min_w)).replace("{MAX_WORDS}", str(max_w)) + retry_instruction

                # Realizar la solicitud
                data = self.rewrite_text(prompt, text)
                body = (data.get("cuerpo") or "").strip()
                wc = len([w for w in body.split() if w])

                # Verificar si cumple con el rango de palabras
                if min_w <= wc <= max_w:
                    # Éxito: guardar y retornar
                    data["palabras"] = wc
                    data["intentos_realizados"] = attempt + 1
                    out = out_dir / f"{transcript_txt.stem}.json"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    return RewrittenContent(json_path=out, words_count=wc)
                else:
                    # No cumple: preparar para reintento
                    previous_wc = wc
                    if attempt == max_retries - 1:
                        # Último intento fallido: guardar de todos modos pero marcar el problema
                        data["palabras"] = wc
                        data["intentos_realizados"] = max_retries
                        data["problema_longitud"] = f"No se logró el rango {min_w}-{max_w} palabras en {max_retries} intentos. Resultado final: {wc} palabras."
                        out = out_dir / f"{transcript_txt.stem}.json"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                        return RewrittenContent(json_path=out, words_count=wc)

            # Este punto no debería alcanzarse nunca
            raise RewriteError("Error inesperado en el sistema de reintentos")

        except Exception as e:
            raise RewriteError(str(e))
