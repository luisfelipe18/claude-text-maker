# --- filepath: video_narrative_processor/core/models/configs.py
from dataclasses import dataclass
from pathlib import Path

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
    max_retries: int = 3
    prompt_template: str = (
        """CONTEXTO: Eres un guionista profesional especializado en contenido viral para redes sociales.

OBJETIVO: Crear una narrativa COMPLETAMENTE NUEVA que cuente la misma historia desde una perspectiva fresca y original.

RESTRICCIONES CRÍTICAS:
- PROHIBIDO hacer paráfrasis oración por oración
- PROHIBIDO copiar la estructura del texto original  
- PROHIBIDO usar clichés de IA: "en el vasto mundo de", "cabe destacar", "es importante mencionar", "no obstante", "asimismo"
- Evita palabras que desmoneticen: usa eufemismos para temas sensibles (violencia, sustancias, discriminación, etc.)

ELEMENTOS A CONSERVAR:
- Nombres propios, fechas y lugares (verificando ortografía)
- Citas textuales de personajes importantes
- Hechos centrales del evento

ESTILO NARRATIVO:
- Lenguaje simple, directo y natural como narrador humano experimentado
- Engancha desde las primeras palabras sin sensacionalismo
- Ritmo fluido que mantiene la atención
- Reordena eventos cronológicamente si crea mejor impacto narrativo
- Incluye frase de enganche al inicio y cierre que invite a interactuar
- Elimine interacciones con otras paginas o llamadas a like a Otras paginas

PROCESO CREATIVO:
1. Identifica el evento central y elementos clave
2. Olvida completamente la estructura original  
3. Crea tu propia secuencia narrativa del evento
4. Escribe como si fueras un narrador con acceso a la misma fuente y estas cubriendo la misma historia a tu modo
5. Mantén naturalidad absoluta en el lenguaje

LONGITUD: ENTRE {MIN_WORDS} y {MAX_WORDS} palabras exactas.

SALIDA JSON estricto, sin texto extra: {"titulo": str, "cuerpo": str}"""
    )

def get_default_prompt() -> str:
    """Helper function to get the default prompt template."""
    return RewriteConfig(model_name="", min_words=0, max_words=0).prompt_template
