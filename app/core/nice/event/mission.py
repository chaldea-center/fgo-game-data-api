from ....schemas.common import Region
from ....schemas.enums import DETAIL_MISSION_LINK_TYPE
from ....schemas.gameenums import (
    COND_TYPE_NAME,
    MISSION_PROGRESS_TYPE_NAME,
    MISSION_REWARD_TYPE_NAME,
    MISSION_TYPE_NAME,
    CondType,
)
from ....schemas.nice import (
    NiceEventMission,
    NiceEventMissionCondition,
    NiceEventMissionConditionDetail,
)
from ....schemas.raw import (
    MstEventMission,
    MstEventMissionCondition,
    MstEventMissionConditionDetail,
)
from ...utils import get_traits_list
from ..gift import GiftData, get_nice_gifts


def get_nice_mission_cond_detail(
    cond_detail: MstEventMissionConditionDetail,
) -> NiceEventMissionConditionDetail:
    return NiceEventMissionConditionDetail(
        id=cond_detail.id,
        missionTargetId=cond_detail.missionTargetId,
        missionCondType=cond_detail.missionCondType,
        logicType=cond_detail.logicType,
        targetIds=cond_detail.targetIds,
        addTargetIds=cond_detail.addTargetIds,
        targetQuestIndividualities=get_traits_list(
            cond_detail.targetQuestIndividualities
        ),
        conditionLinkType=DETAIL_MISSION_LINK_TYPE[cond_detail.conditionLinkType],
        targetEventIds=cond_detail.targetEventIds,
    )


def get_nice_mission_cond(
    cond: MstEventMissionCondition, details: dict[int, MstEventMissionConditionDetail]
) -> NiceEventMissionCondition:
    nice_mission_cond = NiceEventMissionCondition(
        id=cond.id,
        missionProgressType=MISSION_PROGRESS_TYPE_NAME[cond.missionProgressType],
        priority=cond.priority,
        missionTargetId=cond.missionTargetId,
        condGroup=cond.condGroup,
        condType=COND_TYPE_NAME[cond.condType],
        targetIds=cond.targetIds,
        targetNum=cond.targetNum,
        conditionMessage=cond.conditionMessage,
        closedMessage=cond.closedMessage,
        flag=cond.flag,
    )
    if (
        cond.condType == CondType.MISSION_CONDITION_DETAIL
        and cond.targetIds[0] in details
    ):
        nice_mission_cond.detail = get_nice_mission_cond_detail(
            details[cond.targetIds[0]]
        )
    return nice_mission_cond


def get_nice_mission(
    region: Region,
    mission: MstEventMission,
    conds: list[MstEventMissionCondition],
    details: dict[int, MstEventMissionConditionDetail],
    gift_data: GiftData,
) -> NiceEventMission:
    return NiceEventMission(
        id=mission.id,
        flag=mission.flag,
        type=MISSION_TYPE_NAME[mission.type],
        missionTargetId=mission.missionTargetId,
        dispNo=mission.dispNo,
        name=mission.name,
        detail=mission.detail,
        startedAt=mission.startedAt,
        endedAt=mission.endedAt,
        closedAt=mission.closedAt,
        rewardType=MISSION_REWARD_TYPE_NAME[mission.rewardType],
        gifts=get_nice_gifts(region, mission.giftId, gift_data),
        bannerGroup=mission.bannerGroup,
        priority=mission.priority,
        rewardRarity=mission.rewardRarity,
        notfyPriority=mission.notfyPriority,
        presentMessageId=mission.presentMessageId,
        conds=[get_nice_mission_cond(cond, details) for cond in conds],
    )


def get_nice_missions(
    region: Region,
    mstEventMission: list[MstEventMission],
    mstEventMissionCondition: list[MstEventMissionCondition],
    mstEventMissionConditionDetail: list[MstEventMissionConditionDetail],
    gift_data: GiftData,
) -> list[NiceEventMission]:
    mission_cond_details = {
        detail.id: detail for detail in mstEventMissionConditionDetail
    }
    missions = [
        get_nice_mission(
            region,
            mission,
            [cond for cond in mstEventMissionCondition if cond.missionId == mission.id],
            mission_cond_details,
            gift_data,
        )
        for mission in mstEventMission
    ]
    return missions
