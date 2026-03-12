"""VDA5050 안전 상태 엔티티."""

from dataclasses import dataclass

from vda5050_fleet_adapter.domain.enums import EStopType


@dataclass
class SafetyState:
    """AGV 안전 상태.

    Args:
        e_stop: 비상 정지 유형.
        field_violation: 안전 필드 침범 여부.
    """

    e_stop: EStopType = EStopType.NONE
    field_violation: bool = False
