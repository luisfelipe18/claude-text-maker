# --- filepath: video_narrative_processor/utils/exceptions.py
class ProcessorError(Exception):
    """Base error for processing pipeline."""

class DownloadError(ProcessorError):
    pass

class TranscribeError(ProcessorError):
    pass

class RewriteError(ProcessorError):
    pass

class DocumentError(ProcessorError):
    pass

