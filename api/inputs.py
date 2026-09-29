"""Input contracts independent of the validated clinical classifier."""
from pydantic import BaseModel, Field, ConfigDict

class Query(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    pregunta: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=3, ge=1, le=10)

class ClinicalText(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    texto: str = Field(min_length=1, max_length=500000)
    nombre_archivo: str = Field(default='hc_manual.txt', min_length=1, max_length=200)
