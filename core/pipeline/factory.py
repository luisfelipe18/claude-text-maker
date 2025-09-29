# --- filepath: video_narrative_processor/core/pipeline/factory.py
import os
from dataclasses import dataclass
from core.models.configs import ProcessingConfig, RewriteConfig
from core.processors.downloader import DefaultDownloader
from core.processors.transcriber import AWSTranscriber
from core.processors.rewriter import DefaultAIRewriter
from core.processors.document_generator import DefaultWordGenerator
from infrastructure.aws.uploader import S3Uploader

@dataclass
class ProcessorFactory:
    pconf: ProcessingConfig
    rconf: RewriteConfig

    def build_downloader(self):
        return DefaultDownloader()

    def build_uploader(self):
        return S3Uploader(bucket=self.pconf.bucket, region=self.pconf.region)

    def build_transcriber(self):
        return AWSTranscriber(
            bucket=self.pconf.bucket,
            prefix=self.pconf.s3_prefix,
            region=self.pconf.region,
            output_prefix=self.pconf.transcribe_output_prefix,
            aws_access_key_id=self.pconf.aws_access_key_id,
            aws_secret_access_key=self.pconf.aws_secret_access_key
        )

    def build_rewriter(self):
        api_key = os.getenv("OPENAI_API_KEY")
        return DefaultAIRewriter(api_key=api_key, model=self.rconf.model_name, prompt_template=self.rconf.prompt_template)

    def build_docgen(self):
        return DefaultWordGenerator()
