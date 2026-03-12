"""VDA5050 맵 상태 엔티티."""

from dataclasses import dataclass

from vda5050_fleet_adapter.domain.enums import MapStatus


@dataclass
class AgvMap:
    """AGV에 로드된 맵 정보.

    Args:
        map_id: 맵 식별자.
        map_version: 맵 버전.
        map_status: 활성화 상태.
    """

    map_id: str
    map_version: str
    map_status: MapStatus = MapStatus.DISABLED
