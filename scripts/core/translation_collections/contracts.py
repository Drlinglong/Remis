"""Validated public collection edits; publication identity is a separate action."""
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OutputSelection(StrictModel):
    language_code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9-]+$")
    output_folder_name: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\]+$")


class CollectionMember(StrictModel):
    project_id: str = Field(min_length=1, max_length=128)
    outputs: list[OutputSelection] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_languages(self):
        languages = [row.language_code for row in self.outputs]
        if len(set(languages)) != len(languages):
            raise ValueError("Select each member language only once")
        return self


class CollectionFields(StrictModel):
    title: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=8000)
    target_languages: list[str] = Field(min_length=1, max_length=30)
    members: list[CollectionMember] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_selections(self):
        projects = [row.project_id for row in self.members]
        if len(set(projects)) != len(projects):
            raise ValueError("Select each member project only once")
        if len(set(self.target_languages)) != len(self.target_languages):
            raise ValueError("Select each target language only once")
        if any(row.language_code not in self.target_languages for member in self.members for row in member.outputs):
            raise ValueError("Member output language is outside the collection targets")
        return self


class CreateCollection(CollectionFields):
    game_id: str = Field(min_length=1, max_length=80)


class UpdateCollection(CollectionFields):
    expected_revision: int = Field(ge=1)


class PublicationBinding(StrictModel):
    expected_revision: int = Field(ge=1)
    steam_id: str = Field(default="", max_length=20)
    approved: bool = False


class ExportApproval(StrictModel):
    plan_id: str = Field(pattern=r"^plan_[a-f0-9]{32}$")
    approved: bool = False
