"""위치 및 속도 관련 값 객체."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NodePosition:
    """Order 내 노드의 위치 정보.

    Args:
        x: X 좌표 (m).
        y: Y 좌표 (m).
        map_id: 맵 식별자.
        theta: 방향 (rad), -PI ~ PI. None이면 방향 무관.
        allowed_deviation_xy: 허용 위치 오차 (m).
        allowed_deviation_theta: 허용 방향 오차 (rad).
    """

    x: float
    y: float
    map_id: str
    theta: float | None = None
    allowed_deviation_xy: float | None = None
    allowed_deviation_theta: float | None = None


@dataclass(frozen=True)
class AgvPosition:
    """AGV의 현재 위치 (State 메시지용).

    Args:
        x: X 좌표 (m).
        y: Y 좌표 (m).
        theta: 방향 (rad).
        map_id: 현재 맵 ID.
        position_initialized: 로컬라이제이션 초기화 여부.
        localization_score: 로컬라이제이션 품질 (0.0~1.0).
    """

    x: float
    y: float
    theta: float
    map_id: str
    position_initialized: bool = True
    localization_score: float | None = None


@dataclass(frozen=True)
class Velocity:
    """AGV 속도 벡터.

    Args:
        vx: X 방향 속도 (m/s).
        vy: Y 방향 속도 (m/s).
        omega: 각속도 (rad/s).
    """

    vx: float = 0.0
    vy: float = 0.0
    omega: float = 0.0
