"""VDA5050 액션 엔티티."""

from dataclasses import dataclass, field

from vda5050_fleet_adapter.domain.enums import ActionStatus, BlockingType


@dataclass(frozen=True)
class ActionParameter:
    """액션 파라미터 키-값 쌍.

    Args:
        key: 파라미터 이름.
        value: 파라미터 값.
    """

    key: str
    value: str | float | int | bool | list


@dataclass
class Action:
    """VDA5050 액션 정의 (Order/InstantActions에서 사용).

    Args:
        action_type: 액션 종류 식별자 (e.g. 'pick', 'drop').
        action_id: 고유 ID (UUID 권장).
        blocking_type: 블로킹 유형.
        action_description: 액션 설명.
        action_parameters: 액션별 파라미터 목록.
    """

    action_type: str
    action_id: str
    blocking_type: BlockingType
    action_description: str = ''
    action_parameters: list[ActionParameter] = field(default_factory=list)


@dataclass
class ActionState:
    """AGV State 메시지 내 액션 실행 상태.

    Args:
        action_id: 대응하는 Action의 고유 ID.
        action_type: 액션 종류.
        action_status: 현재 실행 상태.
        action_description: 액션 설명.
        result_description: 실행 결과 설명.
    """

    action_id: str
    action_type: str
    action_status: ActionStatus = ActionStatus.WAITING
    action_description: str = ''
    result_description: str = ''

    def transition_to(self, new_status: ActionStatus) -> None:
        """액션 상태를 전이한다.

        Args:
            new_status: 전이할 새 상태.

        Raises:
            InvalidStateTransitionError: 허용되지 않는 상태 전이 시.
        """
        from vda5050_fleet_adapter.domain.exceptions import (
            InvalidStateTransitionError,
        )

        valid_transitions: dict[ActionStatus, set[ActionStatus]] = {
            ActionStatus.WAITING: {ActionStatus.INITIALIZING, ActionStatus.FAILED},
            ActionStatus.INITIALIZING: {ActionStatus.RUNNING, ActionStatus.FAILED},
            ActionStatus.RUNNING: {
                ActionStatus.PAUSED,
                ActionStatus.FINISHED,
                ActionStatus.FAILED,
            },
            ActionStatus.PAUSED: {ActionStatus.RUNNING, ActionStatus.FAILED},
            ActionStatus.FINISHED: set(),
            ActionStatus.FAILED: set(),
        }

        allowed = valid_transitions.get(self.action_status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f'Action [{self.action_id}]: '
                f'{self.action_status} -> {new_status} 전이 불가'
            )
        self.action_status = new_status
