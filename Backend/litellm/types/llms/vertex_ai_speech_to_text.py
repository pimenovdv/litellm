from typing import List
from pydantic import BaseModel
from typing_extensions import TypedDict


class VertexSpeechToTextAutoDecodingConfig(TypedDict):
    pass


class VertexSpeechToTextRecognitionFeatures(TypedDict):
    enableAutomaticPunctuation: bool


class VertexSpeechToTextRecognitionConfig(TypedDict):
    model: str
    languageCodes: List[str]
    features: VertexSpeechToTextRecognitionFeatures
    autoDecodingConfig: VertexSpeechToTextAutoDecodingConfig


class VertexSpeechToTextRecognizeRequest(TypedDict):
    config: VertexSpeechToTextRecognitionConfig
    content: str


class VertexSpeechToTextAlternative(BaseModel):
    transcript: str | None = None


class VertexSpeechToTextResult(BaseModel):
    alternatives: List[VertexSpeechToTextAlternative] = []
    languageCode: str | None = None


class VertexSpeechToTextResponseMetadata(BaseModel):
    totalBilledDuration: str | None = None


class VertexSpeechToTextRecognizeResponse(BaseModel):
    results: List[VertexSpeechToTextResult] = []
    metadata: VertexSpeechToTextResponseMetadata | None = None
