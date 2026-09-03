from fastapi import APIRouter

from app.playbooks import Playbook, list_playbooks

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


@router.get("", response_model=list[Playbook])
async def get_playbooks() -> list[Playbook]:
    return list_playbooks()
