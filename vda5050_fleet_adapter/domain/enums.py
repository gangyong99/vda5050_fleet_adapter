"""VDA5050 도메인 열거형 정의."""

from enum import StrEnum


class OperatingMode(StrEnum):
    """AGV 운영 모드."""

    AUTOMATIC = 'AUTOMATIC'
    SEMIAUTOMATIC = 'SEMIAUTOMATIC'
    MANUAL = 'MANUAL'
    SERVICE = 'SERVICE'
    TEACHIN = 'TEACHIN'


class BlockingType(StrEnum):
    """액션 블로킹 유형."""

    NONE = 'NONE'
    SOFT = 'SOFT'
    HARD = 'HARD'


class ActionStatus(StrEnum):
    """액션 실행 상태."""

    WAITING = 'WAITING'
    INITIALIZING = 'INITIALIZING'
    RUNNING = 'RUNNING'
    PAUSED = 'PAUSED'
    FINISHED = 'FINISHED'
    FAILED = 'FAILED'


class EStopType(StrEnum):
    """비상 정지 유형."""

    AUTOACK = 'AUTOACK'
    MANUAL = 'MANUAL'
    REMOTE = 'REMOTE'
    NONE = 'NONE'


class ErrorLevel(StrEnum):
    """에러 심각도."""

    WARNING = 'WARNING'
    FATAL = 'FATAL'


class InfoLevel(StrEnum):
    """정보 심각도."""

    INFO = 'INFO'
    DEBUG = 'DEBUG'


class MapStatus(StrEnum):
    """맵 활성화 상태."""

    ENABLED = 'ENABLED'
    DISABLED = 'DISABLED'


class ConnectionState(StrEnum):
    """MQTT 연결 상태."""

    ONLINE = 'ONLINE'
    OFFLINE = 'OFFLINE'
    CONNECTIONBROKEN = 'CONNECTIONBROKEN'


class CorridorRefPoint(StrEnum):
    """복도 기준점 유형."""

    KINEMATICCENTER = 'KINEMATICCENTER'
    CONTOUR = 'CONTOUR'
