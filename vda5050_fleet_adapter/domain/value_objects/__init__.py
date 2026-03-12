"""VDA5050 값 객체 (불변, 동등성 기반 비교)."""

from vda5050_fleet_adapter.domain.value_objects.physical import (
    BoundingBoxReference,
    Corridor,
    LoadDimensions,
)
from vda5050_fleet_adapter.domain.value_objects.position import (
    AgvPosition,
    NodePosition,
    Velocity,
)
from vda5050_fleet_adapter.domain.value_objects.trajectory import (
    ControlPoint,
    Trajectory,
)

__all__ = [
    'AgvPosition',
    'BoundingBoxReference',
    'ControlPoint',
    'Corridor',
    'LoadDimensions',
    'NodePosition',
    'Trajectory',
    'Velocity',
]
