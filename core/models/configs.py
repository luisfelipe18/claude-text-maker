# --- filepath: video_narrative_processor/core/models/configs.py
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class ProcessingConfig:
    run_dir: Path
    bucket: str
    s3_prefix: str = "videos/"
    region: str = "us-east-1"
    enable_aws: bool = True
    transcribe_output_prefix: str | None = "textos/"  # si None, AWS alojará el JSON temporal
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None

@dataclass
class RewriteConfig:
    model_name: str
    min_words: int
    max_words: int
    language: str = "ES"
    prompt_template: str = (
        """CONTEXTO: Eres experto en guiones virales para redes sociales.\n\n"""
        "TAREA: Reescribe la narrativa respetando hechos (nombres/fechas/lugares) y cambia el estilo. Quiero una versión nueva, con más gancho, NO una paráfrasis superficial.\n"
        "RESTRICCIONES: .\n"
        "   - Evita palabras que desmoneticen: usa eufemismos/rodeos para temas sensibles (autolesiones, sustancias ilícitas, violencia explícita, fallecimientos, lesiones graves, discriminación, extremismos, etc.).\n"
        "   - Mantén nombres, lugares y fechas.\n"
        "   - Estilo: dinámico, con suspenso, ritmo juvenil.\n"
        "   - Longitud: ENTRE {MIN_WORDS} y {MAX_WORDS} palabras.\n"
        "INSTRUCCIONES:\n"
        "   - Puedes reordenar la narracion y sus eventos (narrar en otro orden)."
        "   - Puedes Incluir una frase de enganche al inicio y un cierre que invite a interactuar."
        "   - Evita replicar exactamente el orden del texto original"
        "LONGITUD: ENTRE {MIN_WORDS} y {MAX_WORDS} palabras.\n\n"
        "SALIDA JSON estricto, sin texto extra: {\"titulo\": str, \"cuerpo\": str}"
    )
    