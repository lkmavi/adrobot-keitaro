"""Calculate offer traffic shares while preserving explicit operator choices."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def redistribute(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return copied offers with valid shares totaling 100 percent.

    Pinned active offers keep their assigned shares. Remaining traffic is divided
    evenly among unpinned active offers, with remainder points assigned in list
    order; archived offers always receive zero. Invalid pinned totals raise
    ``ValueError`` without changing the caller's input.
    """
    logger.debug("Redistributing offer shares: offer_count=%s", len(offers))
    result = [dict(offer) for offer in offers]

    active = [offer for offer in result if not offer["removed"]]

    pinned = [offer for offer in active if offer["pinned"]]

    free = [offer for offer in active if not offer["pinned"]]

    used = sum(int(offer["share"]) for offer in pinned)

    if any(not 0 <= int(offer["share"]) <= 100 for offer in pinned) or used > 100:
        logger.warning(
            "Invalid pinned offer shares: pinned_count=%s total_share=%s", len(pinned), used
        )
        raise ValueError("Закреплённые доли должны быть от 0 до 100 и в сумме не более 100%")

    if active and not free and used != 100:
        logger.warning("Pinned offer shares do not total 100: total_share=%s", used)
        raise ValueError("При закреплении всех офферов сумма долей должна быть 100%")

    if free:
        share, remainder = divmod(100 - used, len(free))

        for index, offer in enumerate(free):
            offer["share"] = share + (index < remainder)

    for offer in result:
        if offer["removed"]:
            offer["share"] = 0

    logger.debug("Offer shares redistributed: active_count=%s", len(active))
    return result
