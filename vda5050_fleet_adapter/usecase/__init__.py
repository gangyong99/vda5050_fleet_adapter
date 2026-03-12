"""VDA5050 Fleet Adapter 유스케이스 레이어.

도메인 로직을 포트를 통해 조율하는 애플리케이션 서비스를 정의한다.
domain 레이어만 의존하며, infra 레이어 의존성은 없다.
"""

from vda5050_fleet_adapter.usecase.robot_adapter import RobotAdapter

__all__ = [
    'RobotAdapter',
]
