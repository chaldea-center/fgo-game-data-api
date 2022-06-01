import re
from typing import Any, Optional, Union

from fastapi import HTTPException
from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncConnection

from ...config import Settings, logger
from ...db.helpers import fetch
from ...schemas.common import Region
from ...schemas.enums import FUNC_APPLYTARGET_NAME, FUNC_VALS_NOT_BUFF
from ...schemas.gameenums import FUNC_TARGETTYPE_NAME, FUNC_TYPE_NAME, FuncType
from ...schemas.nice import AssetURL, NiceFuncGroup
from ...schemas.raw import FunctionEntityNoReverse, MstFunc, MstFuncGroup
from ..utils import fmt_url, get_traits_list
from .buff import get_nice_buff


settings = Settings()


def remove_brackets(val_string: str) -> str:
    return val_string.removeprefix("[").removesuffix("]")


EVENT_DROP_FUNCTIONS = {
    FuncType.EVENT_POINT_UP,
    FuncType.EVENT_POINT_RATE_UP,
    FuncType.EVENT_DROP_UP,
    FuncType.EVENT_DROP_RATE_UP,
}
EVENT_FUNCTIONS = EVENT_DROP_FUNCTIONS | {
    FuncType.ENEMY_ENCOUNT_COPY_RATE_UP,
    FuncType.ENEMY_ENCOUNT_RATE_UP,
}
FRIEND_SUPPORT_FUNCTIONS = {
    FuncType.SERVANT_FRIENDSHIP_UP,
    FuncType.USER_EQUIP_EXP_UP,
    FuncType.EXP_UP,
    FuncType.QP_DROP_UP,
    FuncType.QP_UP,
}
LIST_DATAVALS = {
    "TargetList",
    "TargetRarityList",
    "AndCheckIndividualityList",
    "ParamAddSelfIndividuality",
    "ParamAddOpIndividuality",
    "ParamAddFieldIndividuality",
    "DamageRates",
    "OnPositions",
    "OffPositions",
    "NotTargetSkillIdArray",
}


async def parse_dataVals(
    conn: AsyncConnection, datavals: str, functype: int
) -> dict[str, Union[int, str, list[int]]]:
    error_message = f"Can't parse datavals: {datavals}"
    INITIAL_VALUE = -98765
    # Prefix to be used for temporary keys that need further parsing.
    # Some functions' datavals can't be parsed by themselves and need the first
    # or second datavals to determine whether it's a rate % or an absolute value.
    # See the "Further parsing" section.
    # The prefix should be something unlikely to be a dataval key.
    prefix = "aa"

    output: dict[str, Union[int, str, list[int]]] = {}
    if datavals != "[]":
        datavals = remove_brackets(datavals)
        array = re.split(r",\s*(?![^\[\]]*])", datavals)
        for i, arrayi in enumerate(array):
            text = ""
            value = INITIAL_VALUE
            try:
                value = int(arrayi)
                if functype in {
                    FuncType.DAMAGE_NP_INDIVIDUAL,
                    FuncType.DAMAGE_NP_STATE_INDIVIDUAL,
                    FuncType.DAMAGE_NP_STATE_INDIVIDUAL_FIX,
                    FuncType.DAMAGE_NP_INDIVIDUAL_SUM,
                    FuncType.DAMAGE_NP_RARE,
                    FuncType.DAMAGE_NP_AND_CHECK_INDIVIDUALITY,
                }:
                    if i == 0:
                        text = "Rate"
                    elif i == 1:
                        text = "Value"
                    elif i == 2:
                        text = "Target"
                    elif i == 3:
                        text = "Correction"
                elif functype in {FuncType.ADD_STATE, FuncType.ADD_STATE_SHORT}:
                    if i == 0:
                        text = "Rate"
                    elif i == 1:
                        text = "Turn"
                    elif i == 2:
                        text = "Count"
                    elif i == 3:
                        text = "Value"
                    elif i == 4:
                        text = "UseRate"
                    elif i == 5:
                        text = "Value2"
                elif functype == FuncType.SUB_STATE:
                    if i == 0:
                        text = "Rate"
                    elif i == 1:
                        text = "Value"
                    elif i == 2:
                        text = "Value2"
                elif functype == FuncType.TRANSFORM_SERVANT:
                    if i == 0:
                        text = "Rate"
                    elif i == 1:
                        text = "Value"
                    elif i == 2:
                        text = "Target"
                    elif i == 3:
                        text = "SetLimitCount"
                elif functype in EVENT_FUNCTIONS:
                    if i == 0:
                        text = "Individuality"
                    elif i == 3:
                        text = "EventId"
                    else:
                        text = prefix + str(i)
                elif functype == FuncType.CLASS_DROP_UP:
                    if i == 2:
                        text = "EventId"
                    else:
                        text = prefix + str(i)
                elif functype == FuncType.ENEMY_PROB_DOWN:
                    if i == 0:
                        text = "Individuality"
                    elif i == 1:
                        text = "RateCount"
                    elif i == 2:
                        text = "EventId"
                elif functype in FRIEND_SUPPORT_FUNCTIONS:
                    if i == 2:
                        text = "Individuality"
                    else:
                        text = prefix + str(i)
                elif functype in {
                    FuncType.FRIEND_POINT_UP,
                    FuncType.FRIEND_POINT_UP_DUPLICATE,
                }:
                    if i == 0:
                        text = "AddCount"
                else:
                    if i == 0:
                        text = "Rate"
                    elif i == 1:
                        text = "Value"
                    elif i == 2:
                        text = "Target"
            except ValueError:
                array2 = re.split(r":\s*(?![^\[\]]*])", arrayi)
                if len(array2) > 1:
                    if array2[0] == "DependFuncId1":
                        output["DependFuncId"] = int(remove_brackets(array2[1]))
                    elif array2[0] == "DependFuncVals1":
                        # This assumes DependFuncId is parsed before.
                        # If DW ever make it more complicated than this, consider
                        # using DUMMY_PREFIX + ... and parse it later
                        dependMstFunc = await fetch.get_one(conn, MstFunc, int(output["DependFuncId"]))  # type: ignore
                        if not dependMstFunc:
                            raise HTTPException(status_code=500, detail=error_message)
                        vals_value = await parse_dataVals(
                            conn, array2[1], dependMstFunc.funcType
                        )
                        output["DependFuncVals"] = vals_value  # type: ignore
                    elif array2[0] in LIST_DATAVALS:
                        try:
                            output[array2[0]] = [int(i) for i in array2[1].split("/")]
                        except ValueError:
                            raise HTTPException(status_code=500, detail=error_message)
                    else:
                        try:
                            text = array2[0]
                            value = int(array2[1])
                        except ValueError:
                            raise HTTPException(status_code=500, detail=error_message)
                else:
                    raise HTTPException(status_code=500, detail=error_message)

            if text:
                output[text] = value

        if not any(key.startswith(prefix) for key in output):
            if len(array) != len(output) and functype != FuncType.NONE:
                logger.warning(
                    f"Some datavals weren't parsed for func type {functype}: [{datavals}] => {output}"
                )

    # Further parsing
    prefix_0 = prefix + "0"
    prefix_1 = prefix + "1"
    prefix_2 = prefix + "2"
    if functype in EVENT_FUNCTIONS and prefix_1 in output:
        if output[prefix_1] == 1:
            output["AddCount"] = output[prefix_2]
        elif output[prefix_1] == 2:
            output["RateCount"] = output[prefix_2]
        elif output[prefix_1] == 3:
            output["DropRateCount"] = output[prefix_2]
    elif (
        functype in {FuncType.CLASS_DROP_UP} | FRIEND_SUPPORT_FUNCTIONS
        and prefix_0 in output
    ):
        if output[prefix_0] == 1:
            output["AddCount"] = output[prefix_1]
        elif output[prefix_0] == 2:
            output["RateCount"] = output[prefix_1]

    return output


def get_func_group_icon(region: Region, funcType: int, iconId: int) -> HttpUrl | None:
    if iconId == 0:
        return None

    base_settings = {"base_url": settings.asset_url, "region": region}
    if funcType in EVENT_DROP_FUNCTIONS:
        return fmt_url(AssetURL.items, **base_settings, item_id=iconId)
    else:
        return fmt_url(
            AssetURL.eventUi, **base_settings, event=f"func_group_icon_{iconId}"
        )


def get_nice_func_group(
    region: Region, funcGroup: MstFuncGroup, funcType: int
) -> NiceFuncGroup:
    return NiceFuncGroup(
        eventId=funcGroup.eventId,
        baseFuncId=funcGroup.baseFuncId,
        nameTotal=funcGroup.nameTotal,
        name=funcGroup.name,
        icon=get_func_group_icon(region, funcType, funcGroup.iconId),
        priority=funcGroup.priority,
        isDispValue=funcGroup.isDispValue,
    )


async def get_nice_function(
    conn: AsyncConnection,
    region: Region,
    function: FunctionEntityNoReverse,
    svals: Optional[list[str]] = None,
    svals2: Optional[list[str]] = None,
    svals3: Optional[list[str]] = None,
    svals4: Optional[list[str]] = None,
    svals5: Optional[list[str]] = None,
    followerVals: Optional[list[str]] = None,
) -> dict[str, Any]:
    nice_func: dict[str, Any] = {
        "funcId": function.mstFunc.id,
        "funcPopupText": function.mstFunc.popupText,
        "funcquestTvals": get_traits_list(function.mstFunc.questTvals),
        "functvals": get_traits_list(function.mstFunc.tvals),
        "funcType": FUNC_TYPE_NAME[function.mstFunc.funcType],
        "funcTargetTeam": FUNC_APPLYTARGET_NAME[function.mstFunc.applyTarget],
        "funcTargetType": FUNC_TARGETTYPE_NAME[function.mstFunc.targetType],
        "funcGroup": [
            get_nice_func_group(region, func_group, function.mstFunc.funcType)
            for func_group in function.mstFuncGroup
        ],
        "buffs": [
            get_nice_buff(buff, region) for buff in function.mstFunc.expandedVals
        ],
    }

    if function.mstFunc.funcType in FUNC_VALS_NOT_BUFF:
        nice_func["traitVals"] = get_traits_list(function.mstFunc.vals)

    funcPopupIconId = function.mstFunc.popupIconId
    if funcPopupIconId != 0:
        nice_func["funcPopupIcon"] = AssetURL.buffIcon.format(
            base_url=settings.asset_url, region=region, item_id=funcPopupIconId
        )

    for field, argument in [
        ("svals", svals),
        ("svals2", svals2),
        ("svals3", svals3),
        ("svals4", svals4),
        ("svals5", svals5),
        ("followerVals", followerVals),
    ]:
        if argument:
            nice_func[field] = [
                await parse_dataVals(conn, sval, function.mstFunc.funcType)
                for sval in argument
            ]

    return nice_func
