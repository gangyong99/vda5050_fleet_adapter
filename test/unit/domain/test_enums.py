"""도메인 열거형 단위 테스트."""

from vda5050_fleet_adapter.domain.enums import (
    ActionStatus,
    BlockingType,
    ConnectionState,
    EStopType,
    OperatingMode,
)


class TestOperatingMode:
    def test_values_match_vda5050_spec(self):
        assert OperatingMode.AUTOMATIC == 'AUTOMATIC'
        assert OperatingMode.SEMIAUTOMATIC == 'SEMIAUTOMATIC'
        assert OperatingMode.MANUAL == 'MANUAL'
        assert OperatingMode.SERVICE == 'SERVICE'
        assert OperatingMode.TEACHIN == 'TEACHIN'

    def test_from_string(self):
        assert OperatingMode('AUTOMATIC') is OperatingMode.AUTOMATIC


class TestActionStatus:
    def test_all_states_exist(self):
        expected = {'WAITING', 'INITIALIZING', 'RUNNING',
                    'PAUSED', 'FINISHED', 'FAILED'}
        actual = {s.value for s in ActionStatus}
        assert actual == expected


class TestBlockingType:
    def test_all_types_exist(self):
        expected = {'NONE', 'SOFT', 'HARD'}
        actual = {b.value for b in BlockingType}
        assert actual == expected


class TestEStopType:
    def test_all_types_exist(self):
        expected = {'AUTOACK', 'MANUAL', 'REMOTE', 'NONE'}
        actual = {e.value for e in EStopType}
        assert actual == expected


class TestConnectionState:
    def test_all_states_exist(self):
        expected = {'ONLINE', 'OFFLINE', 'CONNECTIONBROKEN'}
        actual = {c.value for c in ConnectionState}
        assert actual == expected
