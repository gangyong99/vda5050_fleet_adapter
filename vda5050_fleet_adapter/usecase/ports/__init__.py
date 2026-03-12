"""유스케이스 포트 인터페이스 (ABC).

infra 레이어에서 구현해야 하는 추상 인터페이스를 정의한다.
"""

from vda5050_fleet_adapter.usecase.ports.config_port import (
    ConfigPort,
    FleetManagerConfig,
    MqttConfig,
    ReferenceCoordinates,
)
from vda5050_fleet_adapter.usecase.ports.robot_api import (
    CommissionState,
    RobotAPI,
    RobotAPIResult,
    RobotUpdateData,
)

__all__ = [
    'CommissionState',
    'ConfigPort',
    'FleetManagerConfig',
    'MqttConfig',
    'ReferenceCoordinates',
    'RobotAPI',
    'RobotAPIResult',
    'RobotUpdateData',
]
