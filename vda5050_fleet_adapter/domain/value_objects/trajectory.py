"""NURBS 궤적 관련 값 객체."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ControlPoint:
    """NURBS 궤적의 제어점.

    Args:
        x: X 좌표 (m).
        y: Y 좌표 (m).
        weight: 제어점 가중치.
    """

    x: float
    y: float
    weight: float = 1.0


@dataclass(frozen=True)
class Trajectory:
    """NURBS 기반 엣지 궤적 정의.

    Args:
        degree: NURBS 차수.
        knot_vector: 매듭 벡터.
        control_points: 제어점 목록.
    """

    degree: int
    knot_vector: tuple[float, ...] = field(default_factory=tuple)
    control_points: tuple[ControlPoint, ...] = field(default_factory=tuple)
