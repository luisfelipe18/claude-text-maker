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
        "TAREA: Reescribe la narrativa respetando hechos (nombres/fechas/lugares) y cambia el estilo.\n"
        "RESTRICCIONES: evita palabras que desmoneticen; mantén nombres, lugares y fechas.\n"
        "ESTILO: dinámico, con suspenso y ritmo juvenil.\n"
        "LONGITUD: ENTRE {MIN_WORDS} y {MAX_WORDS} palabras.\n\n"
        "SALIDA JSON ESTRICTO: {\"titulo\": str, \"cuerpo\": str}"
    )
    