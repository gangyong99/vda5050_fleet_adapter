"""물리적 측정값 관련 값 객체."""

from dataclasses import dataclass

from vda5050_fleet_adapter.domain.enums import CorridorRefPoint


@dataclass(frozen=True)
class BoundingBoxReference:
    """화물 바운딩 박스 기준점.

    Args:
        x: X 오프셋 (m).
        y: Y 오프셋 (m).
        z: Z 오프셋 (m).
        theta: 회전 (rad).
    """

    x: float
    y: float
    z: float
    theta: float = 0.0


@dataclass(frozen=True)
class LoadDimensions:
    """화물 크기.

    Args:
        length: 길이 (m).
        width: 너비 (m).
        height: 높이 (m).
    """

    length: float
    width: float
    height: float = 0.0


@dataclass(frozen=True)
class Corridor:
    """엣지의 장애물 회피 경계 정의.

    Args:
        left_width: 좌측 경계 폭 (m).
        right_width: 우측 경계 폭 (m).
        corridor_ref_point: 기준점 유형.
    """

    left_width: float
    right_width: float
    corridor_ref_point: CorridorRefPoint = CorridorRefPoint.KINEMATICCENTER
