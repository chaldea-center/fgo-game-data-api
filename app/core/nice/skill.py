from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from ...config import Settings
from ...schemas.common import Language, Region
from ...schemas.enums import SKILL_TYPE_NAME, SkillScriptCond
from ...schemas.nice import (
    AssetURL,
    ExtraPassive,
    NiceSelectAddInfoBtnCond,
    NiceSkill,
    NiceSkillAdd,
    NiceSkillReverse,
)
from ...schemas.raw import (
    MstCommonRelease,
    MstSkillAdd,
    MstSvtPassiveSkill,
    SkillEntityNoReverse,
)
from ..raw import get_skill_entity_no_reverse, get_skill_entity_no_reverse_many
from ..utils import get_traits_list, get_translation, strip_formatting_brackets
from .common_release import get_nice_common_release
from .func import get_nice_function


settings = Settings()


def get_extra_passive(svt_passive: MstSvtPassiveSkill) -> ExtraPassive:
    return ExtraPassive(
        num=svt_passive.num,
        priority=svt_passive.priority,
        condQuestId=svt_passive.condQuestId,
        condQuestPhase=svt_passive.condQuestPhase,
        condLv=svt_passive.condLv,
        condLimitCount=svt_passive.condLimitCount,
        condFriendshipRank=svt_passive.condFriendshipRank,
        eventId=svt_passive.eventId,
        flag=svt_passive.flag,
        startedAt=svt_passive.startedAt,
        endedAt=svt_passive.endedAt,
    )


def get_nice_skill_add(
    skill_adds: list[MstSkillAdd], releases: list[MstCommonRelease], lang: Language
) -> list[NiceSkillAdd]:
    return [
        NiceSkillAdd(
            priority=skill_add.priority,
            releaseConditions=[
                get_nice_common_release(release)
                for release in releases
                if release.id == skill_add.commonReleaseId
            ],
            name=get_translation(lang, skill_add.name),
            ruby=skill_add.ruby,
        )
        for skill_add in skill_adds
    ]


def parse_skill_script_cond(cond: str) -> NiceSelectAddInfoBtnCond:
    if ":" in cond:
        cond_type, value = cond.split(":", maxsplit=2)
        if cond_type in SkillScriptCond.__members__:
            return NiceSelectAddInfoBtnCond(
                cond=SkillScriptCond(cond_type), value=int(value)
            )

    return NiceSelectAddInfoBtnCond(cond=SkillScriptCond.NONE)


def get_nice_skill_script(skill_script: dict[str, Any]) -> dict[str, Any]:
    if SelectAddInfo := skill_script.get("SelectAddInfo"):
        for button in SelectAddInfo["btn"]:
            button["conds"] = [
                parse_skill_script_cond(cond) for cond in button["conds"]
            ]

    return skill_script


async def get_nice_skill_with_svt(
    conn: AsyncConnection,
    skillEntity: SkillEntityNoReverse,
    svtId: int,
    region: Region,
    lang: Language,
    mstSvtPassiveSkills: Optional[list[MstSvtPassiveSkill]] = None,
) -> list[dict[str, Any]]:
    nice_skill: dict[str, Any] = {
        "id": skillEntity.mstSkill.id,
        "name": get_translation(lang, skillEntity.mstSkill.name),
        "originalName": skillEntity.mstSkill.name,
        "ruby": skillEntity.mstSkill.ruby,
        "type": SKILL_TYPE_NAME[skillEntity.mstSkill.type],
        "actIndividuality": get_traits_list(skillEntity.mstSkill.actIndividuality),
        "skillAdd": get_nice_skill_add(
            skillEntity.mstSkillAdd, skillEntity.mstCommonRelease, lang
        ),
    }

    if mstSvtPassiveSkills:
        nice_skill["extraPassive"] = [
            get_extra_passive(svt_skill)
            for svt_skill in mstSvtPassiveSkills
            if svt_skill.skillId == skillEntity.mstSkill.id
        ]
    else:
        nice_skill["extraPassive"] = []

    iconId = skillEntity.mstSkill.iconId
    if iconId != 0:
        nice_skill["icon"] = AssetURL.skillIcon.format(
            base_url=settings.asset_url, region=region, item_id=iconId
        )

    if skillEntity.mstSkillDetail:
        nice_skill["detail"] = strip_formatting_brackets(
            skillEntity.mstSkillDetail[0].detail
        )
        nice_skill["unmodifiedDetail"] = skillEntity.mstSkillDetail[0].detail

    nice_skill["aiIds"] = skillEntity.aiIds

    nice_skill["coolDown"] = [
        skill_lv.chargeTurn for skill_lv in skillEntity.mstSkillLv
    ]

    nice_skill["script"] = {
        scriptKey: [
            get_nice_skill_script(skillLv.script)[scriptKey]
            for skillLv in skillEntity.mstSkillLv
        ]
        for scriptKey in skillEntity.mstSkillLv[0].script
    }

    nice_skill["functions"] = []
    for funci, _ in enumerate(skillEntity.mstSkillLv[0].funcId):
        if skillEntity.mstSkillLv[0].expandedFuncId:
            function = skillEntity.mstSkillLv[0].expandedFuncId[funci]
            followerVals = (
                [
                    skill_lv.script["followerVals"][funci]
                    for skill_lv in skillEntity.mstSkillLv
                ]
                if "followerVals" in skillEntity.mstSkillLv[0].script
                else None
            )

            nice_func = await get_nice_function(
                conn,
                region,
                function,
                svals=[skill_lv.svals[funci] for skill_lv in skillEntity.mstSkillLv],
                followerVals=followerVals,
            )

            nice_skill["functions"].append(nice_func)

    # .mstSvtSkill returns the list of SvtSkill with the same skill_id
    chosen_svts = [
        svt_skill for svt_skill in skillEntity.mstSvtSkill if svt_skill.svtId == svtId
    ]
    if chosen_svts:
        out_skills = []
        for chosenSvt in chosen_svts:
            out_skill = deepcopy(nice_skill)
            out_skill |= {
                "strengthStatus": chosenSvt.strengthStatus,
                "num": chosenSvt.num,
                "priority": chosenSvt.priority,
                "condQuestId": chosenSvt.condQuestId,
                "condQuestPhase": chosenSvt.condQuestPhase,
                "condLv": chosenSvt.condLv,
                "condLimitCount": chosenSvt.condLimitCount,
            }
            out_skills.append(out_skill)
        return out_skills

    return [nice_skill]


async def get_nice_skill_from_raw(
    conn: AsyncConnection,
    region: Region,
    raw_skill: SkillEntityNoReverse,
    lang: Language,
) -> NiceSkillReverse:
    svt_list = [svt_skill.svtId for svt_skill in raw_skill.mstSvtSkill]
    if svt_list:
        svt_id = svt_list[0]
    else:
        svt_id = 0

    nice_skill = NiceSkillReverse.parse_obj(
        (await get_nice_skill_with_svt(conn, raw_skill, svt_id, region, lang))[0]
    )

    return nice_skill


async def get_nice_skill_from_id(
    conn: AsyncConnection,
    region: Region,
    skill_id: int,
    lang: Language,
) -> NiceSkillReverse:
    raw_skill = await get_skill_entity_no_reverse(conn, skill_id, expand=True)
    return await get_nice_skill_from_raw(conn, region, raw_skill, lang)


@dataclass(eq=True, frozen=True)
class SkillSvt:
    """Required parameters to get a specific nice skill"""

    skill_id: int
    svt_id: int


MultipleNiceSkills = dict[SkillSvt, NiceSkill]


async def get_multiple_nice_skills(
    conn: AsyncConnection,
    region: Region,
    skill_svts: Iterable[SkillSvt],
    lang: Language,
) -> MultipleNiceSkills:
    """Get multiple nice skills at once

    Args:
        `conn`: DB Connection
        `region`: Region
        `skill_svts`: List of skill id - svt id tuple pairs
        `lang`: Language

    Returns:
        Mapping of skill id - svt id tuple to nice skill
    """
    raw_skills = {
        skill.mstSkill.id: skill
        for skill in await get_skill_entity_no_reverse_many(
            conn, [skill.skill_id for skill in skill_svts], expand=True
        )
    }
    return {
        skill_svt: NiceSkill.parse_obj(
            (
                await get_nice_skill_with_svt(
                    conn, raw_skills[skill_svt.skill_id], skill_svt.svt_id, region, lang
                )
            )[0]
        )
        for skill_svt in skill_svts
        if skill_svt.skill_id in raw_skills
    }
