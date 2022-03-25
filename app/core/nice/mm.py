from collections import defaultdict
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from ...core.basic import get_basic_quest_from_raw
from ...schemas.common import Language
from ...schemas.nice import NiceMasterMission
from ...schemas.raw import MasterMissionEntity, MstGift, MstMasterMission
from .. import raw
from .event.mission import get_nice_missions


def get_nice_master_mission_from_raw(
    raw_mm: MasterMissionEntity, lang: Language
) -> NiceMasterMission:
    gift_maps: dict[int, list[MstGift]] = defaultdict(list)
    for gift in raw_mm.mstGift:
        gift_maps[gift.id].append(gift)

    missions = get_nice_missions(
        raw_mm.mstEventMission,
        raw_mm.mstEventMissionCondition,
        raw_mm.mstEventMissionConditionDetail,
        gift_maps,
    )
    return NiceMasterMission(
        id=raw_mm.mstMasterMission.id,
        startedAt=raw_mm.mstMasterMission.startedAt,
        endedAt=raw_mm.mstMasterMission.endedAt,
        closedAt=raw_mm.mstMasterMission.closedAt,
        missions=missions,
        quests=[
            get_basic_quest_from_raw(mstQuest, lang) for mstQuest in raw_mm.mstQuest
        ],
    )


async def get_nice_master_mission(
    conn: AsyncConnection,
    mm_id: int,
    lang: Language,
    mstMasterMission: Optional[MstMasterMission] = None,
) -> NiceMasterMission:
    raw_mm = await raw.get_master_mission_entity(conn, mm_id, mstMasterMission)
    return get_nice_master_mission_from_raw(raw_mm, lang)


async def get_all_nice_mms(
    conn: AsyncConnection, mstMasterMissions: list[MstMasterMission], lang: Language
) -> list[NiceMasterMission]:  # pragma: no cover
    return [
        await get_nice_master_mission(conn, mm.id, lang, mm) for mm in mstMasterMissions
    ]
