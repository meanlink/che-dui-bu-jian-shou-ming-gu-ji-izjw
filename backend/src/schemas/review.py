from pydantic import BaseModel, Field
class PackageCreateInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    dataset_id: int
    vendor_id: int
    assets: list[str] = Field(min_length=1, max_length=500)
class VerdictInput(BaseModel):
    alias: str = Field(min_length=1, max_length=40)
    failed: int
class SubmissionInput(BaseModel):
    verdicts: list[VerdictInput] = Field(min_length=1, max_length=500)
