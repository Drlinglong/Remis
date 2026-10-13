"""Application composition root for publication; transport does not own it."""
from functools import lru_cache
from pathlib import Path

from scripts.app_settings import APP_DATA_DIR, PROJECTS_DB_PATH
from scripts.core.repositories.workshop_publication_repository import WorkshopPublicationRepository
from scripts.core.services.steam_workshop_service import SteamWorkshopService
from scripts.core.services.steamugc_process_adapter import SteamUGCProcessAdapter
from scripts.core.services.workshop_publication_inputs import WorkshopPublicationInputs
from scripts.core.services.workshop_publication_service import WorkshopPublicationService
from scripts.core.services.workshop_publication_task_projection import WorkshopPublicationTaskProjection


@lru_cache(maxsize=1)
def publication_runtime():
    return WorkshopPublicationService(
        WorkshopPublicationRepository(PROJECTS_DB_PATH), WorkshopPublicationInputs(SteamWorkshopService()),
        SteamUGCProcessAdapter(), Path(APP_DATA_DIR) / "workshop_publication", WorkshopPublicationTaskProjection(),
    )
