"""VDA5050 화물 엔티티."""

from dataclasses import dataclass

from vda5050_fleet_adapter.domain.value_objects.physical import (
    BoundingBoxReference,
    LoadDimensions,
)


@dataclass
class Load:
    """AGV에 적재된 화물 정보.

    Args:
        load_id: 화물 고유 ID.
        load_type: 화물 유형 (e.g. 'EPAL').
        load_position: 적재 위치 (e.g. 'front', 'rear').
        bounding_box_reference: 바운딩 박스 기준점.
        load_dimensions: 화물 크기.
        weight: 중량 (kg).
    """

    load_id: str = ''
    load_type: str = ''
    load_position: str = ''
    bounding_box_reference: BoundingBoxReference | None = None
    load_dimensions: LoadDimensions | None = None
    weight: float | None = None
