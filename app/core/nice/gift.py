from dataclasses import dataclass

from ...config import Settings
from ...schemas.common import Region
from ...schemas.gameenums import (
    COMMON_CONSUME_TYPE_NAME,
    COND_TYPE_NAME,
    GIFT_TYPE_NAME,
)
from ...schemas.nice import (
    AssetURL,
    NiceBaseGift,
    NiceCommonConsume,
    NiceGift,
    NiceGiftAdd,
)
from ...schemas.raw import MstCommonConsume, MstGift, MstGiftAdd
from ..utils import fmt_url


settings = Settings()


@dataclass
class GiftData:
    gift_adds: list[MstGiftAdd]
    gift_maps: dict[int, list[MstGift]]


def get_nice_gifts(region: Region, gift_id: int, gift_data: GiftData) -> list[NiceGift]:
    return [
        get_nice_gift(region, gift, gift_data.gift_adds, gift_data.gift_maps)
        for gift in gift_data.gift_maps[gift_id]
    ]


def get_nice_common_consume(common_consume: MstCommonConsume) -> NiceCommonConsume:
    return NiceCommonConsume(
        id=common_consume.id,
        priority=common_consume.priority,
        type=COMMON_CONSUME_TYPE_NAME[common_consume.type],
        objectId=common_consume.objectId,
        num=common_consume.num,
    )


def get_nice_base_gift(raw_gift: MstGift) -> NiceBaseGift:
    return NiceBaseGift(
        id=raw_gift.id,
        type=GIFT_TYPE_NAME[raw_gift.type],
        objectId=raw_gift.objectId,
        priority=raw_gift.priority,
        num=raw_gift.num,
    )


def get_nice_gift_add(
    region: Region, gift_add: MstGiftAdd, prior_gifts: list[MstGift], icon_idx: int
) -> NiceGiftAdd:
    return NiceGiftAdd(
        priority=1 if gift_add.priority is None else gift_add.priority,
        replacementGiftIcon=fmt_url(
            AssetURL.items,
            base_url=settings.asset_url,
            region=region,
            item_id=gift_add.priorGiftIconIds[icon_idx],
        ),
        condType=COND_TYPE_NAME[gift_add.condType],
        targetId=gift_add.targetId,
        targetNum=gift_add.targetNum,
        replacementGifts=[get_nice_base_gift(gift) for gift in prior_gifts],
    )


def get_nice_gift_adds(
    region: Region,
    gift: MstGift,
    gift_adds: list[MstGiftAdd],
    gift_maps: dict[int, list[MstGift]],
) -> list[NiceGiftAdd]:
    nice_gift_adds: list[NiceGiftAdd] = []

    gift_index = sorted(gift.sort_id for gift in gift_maps[gift.id]).index(gift.sort_id)

    for gift_add in gift_adds:
        if gift_add.giftId == gift.id and len(gift_add.priorGiftIconIds) > gift_index:
            nice_gift_adds.append(
                get_nice_gift_add(
                    region, gift_add, gift_maps[gift_add.priorGiftId], gift_index
                )
            )

    return nice_gift_adds


def get_nice_gift(
    region: Region,
    raw_gift: MstGift,
    gift_adds: list[MstGiftAdd],
    gift_maps: dict[int, list[MstGift]],
) -> NiceGift:
    return NiceGift(
        id=raw_gift.id,
        type=GIFT_TYPE_NAME[raw_gift.type],
        objectId=raw_gift.objectId,
        priority=raw_gift.priority,
        num=raw_gift.num,
        giftAdds=get_nice_gift_adds(region, raw_gift, gift_adds, gift_maps),
    )
