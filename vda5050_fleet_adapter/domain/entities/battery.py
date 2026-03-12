"""VDA5050 배터리 상태 엔티티."""

from dataclasses import dataclass


@dataclass
class BatteryState:
    """AGV 배터리 상태.

    Args:
        battery_charge: 충전율 (%).
        charging: 충전 중 여부.
        battery_voltage: 전압 (V).
        battery_health: 배터리 건강도 (%).
        reach: 예상 주행 가능 거리 (m).
    """

    battery_charge: float
    charging: bool = False
    battery_voltage: float | None = None
    battery_health: float | None = None
    reach: int | None = None
