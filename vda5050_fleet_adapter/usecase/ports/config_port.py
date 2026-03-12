"""설정 포트 인터페이스.

애플리케이션 설정의 로딩을 추상화한다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MqttConfig:
    """MQTT 브로커 접속 설정.

    Args:
        broker_host: 브로커 호스트 주소.
        broker_port: 브로커 포트 번호.
        keepalive_sec: 연결 유지 간격 (초).
        reconnect_max_delay_sec: 재연결 최대 대기 시간 (초).
    """

    broker_host: str = 'localhost'
    broker_port: int = 1883
    keepalive_sec: int = 60
    reconnect_max_delay_sec: int = 60


@dataclass(frozen=True)
class FleetManagerConfig:
    """VDA5050 Fleet Manager (MQTT) 설정.

    mrceki/vda5050_fleet_adapter의 fleet_manager 설정 형식.

    Args:
        ip: MQTT 브로커 IP.
        prefix: MQTT 토픽 prefix (e.g. 'uagv/v2/manufacturer').
        port: MQTT 브로커 포트.
        user: MQTT 인증 사용자명.
        password: MQTT 인증 비밀번호.
        robot_state_update_frequency: 상태 업데이트 주파수 (Hz).
    """

    ip: str = '127.0.0.1'
    prefix: str = 'uagv/v2/manufacturer'
    port: int = 1883
    user: str = ''
    password: str = ''
    robot_state_update_frequency: float = 10.0


@dataclass(frozen=True)
class ReferenceCoordinates:
    """좌표 변환 기준점 설정.

    Args:
        rmf: RMF 좌표계의 기준점 리스트 [[x,y], ...].
        robot: 로봇 좌표계의 기준점 리스트 [[x,y], ...].
    """

    rmf: list[list[float]] = field(default_factory=list)
    robot: list[list[float]] = field(default_factory=list)


class ConfigPort(ABC):
    """설정 로더 인터페이스."""

    @abstractmethod
    def load(
        self, config_path: str, nav_graph_path: str
    ) -> dict[str, Any]:
        """설정 파일을 로드하여 raw dict로 반환한다.

        Args:
            config_path: config.yaml 파일 경로.
            nav_graph_path: 내비게이션 그래프 파일 경로.

        Returns:
            raw YAML dict.
        """
