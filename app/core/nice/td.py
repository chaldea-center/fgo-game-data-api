from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncConnection

from ...config import Settings
from ...schemas.common import Language, Region
from ...schemas.gameenums import CARD_TYPE_NAME, NiceTdEffectFlag
from ...schemas.nice import AssetURL, NiceTd
from ...schemas.raw import TdEntityNoReverse
from ..raw import get_td_entity_no_reverse, get_td_entity_no_reverse_many
from ..utils import get_np_name, get_traits_list, strip_formatting_brackets
from .func import get_nice_function
from .skill import get_nice_skill_script


settings = Settings()


def get_nice_td_effect_flag(effectFlag: int) -> NiceTdEffectFlag:
    if effectFlag == 1:
        return NiceTdEffectFlag.attackEnemyAll
    elif effectFlag == 2:
        return NiceTdEffectFlag.attackEnemyOne

    return NiceTdEffectFlag.support


async def get_nice_td(
    conn: AsyncConnection,
    tdEntity: TdEntityNoReverse,
    svtId: int,
    region: Region,
    lang: Language,
) -> list[dict[str, Any]]:
    nice_td: dict[str, Any] = {
        "id": tdEntity.mstTreasureDevice.id,
        "name": get_np_name(
            tdEntity.mstTreasureDevice.name, tdEntity.mstTreasureDevice.ruby, lang
        ),
        "originalName": tdEntity.mstTreasureDevice.name,
        "ruby": tdEntity.mstTreasureDevice.ruby,
        "rank": tdEntity.mstTreasureDevice.rank,
        "type": tdEntity.mstTreasureDevice.typeText,
        "effectFlags": [get_nice_td_effect_flag(tdEntity.mstTreasureDevice.effectFlag)],
        "individuality": get_traits_list(tdEntity.mstTreasureDevice.individuality),
    }

    if tdEntity.mstTreasureDeviceDetail:
        nice_td["detail"] = strip_formatting_brackets(
            tdEntity.mstTreasureDeviceDetail[0].detail
        )
        nice_td["unmodifiedDetail"] = tdEntity.mstTreasureDeviceDetail[0].detail

    nice_td["npGain"] = {
        "buster": [td_lv.tdPointB for td_lv in tdEntity.mstTreasureDeviceLv],
        "arts": [td_lv.tdPointA for td_lv in tdEntity.mstTreasureDeviceLv],
        "quick": [td_lv.tdPointQ for td_lv in tdEntity.mstTreasureDeviceLv],
        "extra": [td_lv.tdPointEx for td_lv in tdEntity.mstTreasureDeviceLv],
        "np": [td_lv.tdPoint for td_lv in tdEntity.mstTreasureDeviceLv],
        "defence": [td_lv.tdPointDef for td_lv in tdEntity.mstTreasureDeviceLv],
    }

    nice_td["script"] = {}
    if tdEntity.mstTreasureDeviceLv[0].script:
        for script_key in tdEntity.mstTreasureDeviceLv[0].script:
            nice_td["script"][script_key] = [
                get_nice_skill_script(tdLv.script)[script_key] if tdLv.script else None
                for tdLv in tdEntity.mstTreasureDeviceLv
            ]
    for script_key in ("tdTypeChangeIDs", "excludeTdChangeTypes"):
        if script_key in tdEntity.mstTreasureDevice.script:
            nice_td["script"][script_key] = tdEntity.mstTreasureDevice.script[
                script_key
            ]

    nice_td["functions"] = []

    for funci, _ in enumerate(tdEntity.mstTreasureDeviceLv[0].funcId):
        if tdEntity.mstTreasureDeviceLv[0].expandedFuncId:
            nice_func = await get_nice_function(
                conn,
                region,
                tdEntity.mstTreasureDeviceLv[0].expandedFuncId[funci],
                svals=[
                    skill_lv.svals[funci] for skill_lv in tdEntity.mstTreasureDeviceLv
                ],
                svals2=[
                    skill_lv.svals2[funci] for skill_lv in tdEntity.mstTreasureDeviceLv
                ],
                svals3=[
                    skill_lv.svals3[funci] for skill_lv in tdEntity.mstTreasureDeviceLv
                ],
                svals4=[
                    skill_lv.svals4[funci] for skill_lv in tdEntity.mstTreasureDeviceLv
                ],
                svals5=[
                    skill_lv.svals5[funci] for skill_lv in tdEntity.mstTreasureDeviceLv
                ],
            )

            nice_td["functions"].append(nice_func)

    chosen_svts = [
        svt_td for svt_td in tdEntity.mstSvtTreasureDevice if svt_td.svtId == svtId
    ]
    out_tds = []

    base_settings_id = {
        "base_url": settings.asset_url,
        "region": region,
        "item_id": svtId,
    }

    if not chosen_svts:  # pragma: no cover
        nice_td |= {
            "icon": AssetURL.commands.format(**base_settings_id, i="np"),
            "strengthStatus": 0,
            "num": 0,
            "priority": 0,
            "condQuestId": 0,
            "condQuestPhase": 0,
            "card": CARD_TYPE_NAME[5],
            "npDistribution": [],
        }
        out_tds.append(nice_td)

    for chosen_svt in chosen_svts:
        out_td = deepcopy(nice_td)
        imageId = chosen_svt.imageIndex
        if imageId < 2:
            file_i = "np"
        else:
            file_i = "np" + str(imageId // 2)
        out_td |= {
            "icon": AssetURL.commands.format(**base_settings_id, i=file_i),
            "strengthStatus": chosen_svt.strengthStatus,
            "num": chosen_svt.num,
            "priority": chosen_svt.priority,
            "condQuestId": chosen_svt.condQuestId,
            "condQuestPhase": chosen_svt.condQuestPhase,
            "card": CARD_TYPE_NAME[chosen_svt.cardId],
            "npDistribution": chosen_svt.damage,
        }
        out_tds.append(out_td)
    return out_tds


async def get_nice_td_from_id(
    conn: AsyncConnection,
    region: Region,
    td_id: int,
    lang: Language,
) -> NiceTd:
    raw_td = await get_td_entity_no_reverse(conn, td_id, expand=True)

    svt_id = next((svt_id.svtId for svt_id in raw_td.mstSvtTreasureDevice), td_id)
    nice_td = NiceTd.parse_obj(
        (await get_nice_td(conn, raw_td, svt_id, region, lang))[0]
    )

    return nice_td


@dataclass(eq=True, frozen=True)
class TdSvt:
    """Required parameters to get a specific nice NP"""

    td_id: int
    svt_id: int


MultipleNiceTds = dict[TdSvt, NiceTd]


async def get_multiple_nice_tds(
    conn: AsyncConnection, region: Region, td_svts: Iterable[TdSvt], lang: Language
) -> MultipleNiceTds:
    """Get multiple nice NPs at once

    Args:
        `conn`: DB Connection
        `region`: Region
        `td_svts`: List of skill id - NP id tuple pairs

    Returns:
        Mapping of td id - svt id tuple to nice NP
    """
    raw_tds = {
        td.mstTreasureDevice.id: td
        for td in await get_td_entity_no_reverse_many(
            conn, [td_svt.td_id for td_svt in td_svts], expand=True
        )
    }
    return {
        td_svt: NiceTd.parse_obj(
            (
                await get_nice_td(
                    conn, raw_tds[td_svt.td_id], td_svt.svt_id, region, lang
                )
            )[0]
        )
        for td_svt in td_svts
        if td_svt.td_id in raw_tds
    }
