"""값 객체 단위 테스트."""

from vda5050_fleet_adapter.domain.enums import CorridorRefPoint
from vda5050_fleet_adapter.domain.value_objects.physical import (
    Corridor,
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


class TestNodePosition:
    def test_frozen(self):
        pos = NodePosition(x=1.0, y=2.0, map_id='map1')
        try:
            pos.x = 99.0
            assert False, 'Should raise FrozenInstanceError'
        except AttributeError:
            pass

    def test_optional_fields_default_none(self):
        pos = NodePosition(x=1.0, y=2.0, map_id='map1')
        assert pos.theta is None
        assert pos.allowed_deviation_xy is None
        assert pos.allowed_deviation_theta is None

    def test_equality(self):
        a = NodePosition(x=1.0, y=2.0, map_id='m1', theta=0.5)
        b = NodePosition(x=1.0, y=2.0, map_id='m1', theta=0.5)
        assert a == b

    def test_inequality(self):
        a = NodePosition(x=1.0, y=2.0, map_id='m1')
        b = NodePosition(x=1.0, y=3.0, map_id='m1')
        assert a != b


class TestAgvPosition:
    def test_defaults(self):
        pos = AgvPosition(x=0.0, y=0.0, theta=0.0, map_id='map1')
        assert pos.position_initialized is True
        assert pos.localization_score is None


class TestVelocity:
    def test_defaults_zero(self):
        v = Velocity()
        assert v.vx == 0.0
        assert v.vy == 0.0
        assert v.omega == 0.0


class TestCorridor:
    def test_default_ref_point(self):
        c = Corridor(left_width=1.0, right_width=1.0)
        assert c.corridor_ref_point == CorridorRefPoint.KINEMATICCENTER


class TestTrajectory:
    def test_construction(self):
        t = Trajectory(
            degree=3,
            knot_vector=(0.0, 0.0, 0.0, 1.0, 1.0, 1.0),
            control_points=(
                ControlPoint(x=0.0, y=0.0),
                ControlPoint(x=1.0, y=1.0, weight=2.0),
                ControlPoint(x=2.0, y=0.0),
            ),
        )
        assert t.degree == 3
        assert len(t.control_points) == 3
        assert t.control_points[1].weight == 2.0
