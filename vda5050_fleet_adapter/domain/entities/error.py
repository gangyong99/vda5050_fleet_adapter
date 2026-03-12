"""VDA5050 에러 및 정보 엔티티."""

from dataclasses import dataclass, field

from vda5050_fleet_adapter.domain.enums import ErrorLevel, InfoLevel


@dataclass(frozen=True)
class ErrorReference:
    """에러 관련 엔티티 참조 (근본 원인 추적용).

    Args:
        reference_key: 참조 키 (e.g. 'nodeId', 'actionId').
        reference_value: 참조 값.
    """

    reference_key: str
    reference_value: str


@dataclass
class AgvError:
    """AGV 에러 정보.

    Args:
        error_type: 에러 유형 식별자.
        error_level: 심각도 (WARNING 또는 FATAL).
        error_description: 에러 상세 설명.
        error_hint: 해결 힌트.
        error_references: 관련 엔티티 참조 목록.
    """

    error_type: str
    error_level: ErrorLevel
    error_description: str = ''
    error_hint: str = ''
    error_references: list[ErrorReference] = field(default_factory=list)


@dataclass
class AgvInformation:
    """AGV 정보 메시지.

    Args:
        info_type: 정보 유형 식별자.
        info_level: 정보 레벨.
        info_description: 정보 상세 설명.
        info_references: 관련 엔티티 참조 목록.
    """

    info_type: str
    info_level: InfoLevel
    info_description: str = ''
    info_references: list[ErrorReference] = field(default_factory=list)
