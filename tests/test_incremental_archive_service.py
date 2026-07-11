from scripts.core.services.incremental_archive_service import IncrementalArchiveService


class FakeArchiveManager:
    def __init__(self):
        self.resolved = []
        self.created_versions = []
        self.archived = []

    def resolve_mod_entry(self, project_name, remote_file_id=None):
        self.resolved.append((project_name, remote_file_id))
        return 7

    def create_source_version(self, mod_id, archive_files_data):
        self.created_versions.append((mod_id, archive_files_data))
        return 42

    def archive_translated_results(self, version_id, archive_results, archive_files_data, target_lang_code):
        self.archived.append((version_id, archive_results, archive_files_data, target_lang_code))


def test_archive_language_result_resolves_archive_by_project_identity():
    fake_archive = FakeArchiveManager()
    service = IncrementalArchiveService(am=fake_archive)

    version_id = service.archive_language_result(
        project_id="project-1",
        project_name="Demo",
        target_lang_code="en",
        archive_files_data=[{"filename": "demo.yml", "texts_to_translate": ["Hello"]}],
        archive_results={"demo.yml": ["Hello"]},
    )

    assert version_id == 42
    assert fake_archive.resolved == [("Demo", "project-1")]
    assert fake_archive.created_versions == [(7, [{"filename": "demo.yml", "texts_to_translate": ["Hello"]}])]
    assert fake_archive.archived == [
        (42, {"demo.yml": ["Hello"]}, [{"filename": "demo.yml", "texts_to_translate": ["Hello"]}], "en")
    ]
