# 로봇 B 연결을 위한 수정 계획: stop 속성 기반 pick/drop

## 배경

- **로봇 B**: 사람이 타는 로봇 (people mover)
- nav_graph에서 `pickDrop=true` 대신 **`stop=true`** 속성으로 탑승/하차 지점을 표시
- 기존 pickDrop 로직과의 차이:
  - **pickDrop Base/Horizon 분리 필요**: 탑승/하차 전 직전 노드에서 대기 (pickDrop과 동일)
  - **Station Node Removal 불필요**: 실제 stop 노드에서 직접 pick/drop action 수행

---

# Plan A: pickDrop 로직 재사용 (order update 방식)

## 핵심 판단: pickDrop 재사용

`stop=true`도 `_pick_drop.destination`에 설정하여 기존 pickDrop 로직을 그대로 탄다.
Station Node Removal은 `path[-2]`의 `pickDrop` 속성을 체크하므로, `stop` 노드에서는
자동으로 스킵된다. **별도 StopState, 별도 메서드, 별도 분기 불필요.**

## 흐름

```
navigate(dest=wp3)    →  wp1(B)→wp2(B)→wp3(H)   →  wp2에서 대기
execute_action(pick)  →  wp2(B)→wp3(B,pick)      →  wp3으로 이동 + pick (order 리셋)
navigate(dest=wp5)    →  wp3(B)→wp4(B)→wp5(H)   →  wp4에서 대기 (새 orderID)
execute_action(drop)  →  wp4(B)→wp5(B,drop)      →  wp5으로 이동 + drop (order 리셋)
```

- orderUpdateId=0에는 action 없음, orderUpdateId=1에서 action 부착
- pick/drop마다 order 리셋 → phase별로 별도 orderID

## 수정 대상

### 유일한 수정: `_detect_dest_attributes()` (robot_adapter.py:533)

**현재**:
```python
dest_is_pick_drop = dest_node_attrs.get('pickDrop', False)
```

**수정**:
```python
dest_is_pick_drop = (
    dest_node_attrs.get('pickDrop', False)
    or dest_node_attrs.get('stop', False)
)
```

### 이것만으로 동작하는 이유

| 기존 로직 | stop에서의 동작 | 이유 |
|-----------|----------------|------|
| pickDrop 조기 리턴 (L455) | 정상 동작 | `_pick_drop.destination` 설정됨 |
| pickDrop path 제거 (L820) | 정상 동작 | dest를 Horizon으로 만듦 |
| `_build_pick_drop_order_update` (L1318) | 정상 동작 | dest로 이동 + action |
| order 리셋 (L1184) | 정상 동작 | pick/drop 후 새 orderID |
| Station Node Removal (L733) | **스킵됨** | `_pick_drop.destination`이 이미 설정 + `pickDrop` 속성 체크 |
| `_reset_order_state` (L1538) | 정상 동작 | `_pick_drop.destination = None` |

## Order 예시

### 경로: wp1 → wp2 → wp3(stop=true) → wp4 → wp5(stop=true)

```
Phase 1 (navigate to wp3):
  orderId=order_A, updateId=0
  VDA5050: wp1(B,seq=0) → wp2(B,seq=2) → wp3(H,seq=4) → wp4(H,seq=6) → wp5(H,seq=8)
  actions: 없음
  → wp2 도착 시 execution.finished()

Phase 2 (pick at wp3):
  orderId=order_A, updateId=1
  VDA5050: wp2(B,seq=0) → wp3(B,seq=2, pick)
  → order 리셋

Phase 3 (navigate to wp5):
  orderId=order_B, updateId=0
  VDA5050: wp3(B,seq=0) → wp4(B,seq=2) → wp5(H,seq=4)
  actions: 없음
  → wp4 도착 시 execution.finished()

Phase 4 (drop at wp5):
  orderId=order_B, updateId=1
  VDA5050: wp4(B,seq=0) → wp5(B,seq=2, drop)
  → order 리셋
```

## 장단점

- **장점**: 코드 수정 1줄, 검증된 pickDrop 로직 재사용, 리스크 최소
- **단점**: 로봇이 처음 order에서 pick/drop 계획을 모름, orderUpdate 횟수 많음

---

# Plan B: 초기 order에 action 포함 방식

## 핵심 아이디어

navigate() 시점에 경로 상의 `stop=true` 노드를 스캔하여, bridge(RMF task)에서
전달받은 pick/drop 정보와 **매칭**되면 해당 노드에 action을 미리 부착한다.
로봇이 처음부터 전체 계획(어디서 pick, 어디서 drop)을 알 수 있다.

## 흐름

```
navigate(dest=wp3)    →  wp1(B)→wp2(B)→wp3(B,pick)→wp4(H)→wp5(H,drop)
                         → 로봇이 wp3까지 이동, wp3 도착 시 pick 실행
execute_action(pick)  →  이미 order에 포함됨, action 완료 대기만
navigate(dest=wp5)    →  wp3(B)→wp4(B)→wp5(B,drop)
                         → 로봇이 wp5까지 이동, wp5 도착 시 drop 실행
execute_action(drop)  →  이미 order에 포함됨, action 완료 대기만
```

- orderUpdateId=0에 **action이 이미 포함**됨
- execute_action은 action 완료를 **모니터링만** 함

## Plan A와의 차이

| 항목 | Plan A | Plan B |
|------|--------|--------|
| action 부착 시점 | execute_action (orderUpdate) | navigate (초기 order) |
| orderUpdate 필요 | 매 pick/drop마다 | navigate 경로 변경 시만 |
| 로봇의 사전 정보 | 없음 (경로만 앎) | 전체 계획 (action 포함) |
| Base/Horizon 분리 | 필요 (직전 노드 대기) | 필요 (직전 노드 대기) |
| order 리셋 | pick/drop마다 | pick/drop마다 |
| action 정보 소스 | execute_action 콜백 | navigate 시 bridge 매칭 |

## 전제 조건

navigate() 시점에 pick/drop action 정보를 알 수 있어야 한다:
- **방법 1**: RMF task description에서 phase 정보 파싱
- **방법 2**: config/nav_graph에 stop 노드별 action 종류 정의
- **방법 3**: bridge에서 전달받은 pick/drop 노드 목록과 nav_graph `stop=true` 매칭

→ 이 중 어떤 방법으로 action 정보를 확보하는지에 따라 구현이 달라짐.

## 수정 대상

### 1. `_detect_dest_attributes()` (robot_adapter.py:533)

Plan A와 동일하게 `stop` 속성 감지 추가. 단, `_pick_drop.destination`이 아닌
별도 `_stop` 상태로 관리 (navigate 흐름이 다르므로).

```python
@dataclass
class StopState:
    """stop 속성 노드 상태 (사람 탑승/하차용)."""
    destination: str | None = None
    action_map: dict[str, str] | None = None  # {node_name: action_type}
```

```python
# _detect_dest_attributes 내
dest_is_stop = dest_node_attrs.get('stop', False)
if dest_is_stop and dest_name_raw:
    self._stop.destination = dest_name_raw
else:
    self._stop.destination = None
```

### 2. navigate()에서 stop 노드에 action 미리 부착

`_apply_path_modifiers()` 이후, order 생성 직전에 stop 노드를 스캔:

```python
def _attach_stop_actions(
    self, vda_nodes: list, path: list[str],
) -> None:
    """경로 상 stop=true 노드에 pick/drop action을 미리 부착한다.

    bridge에서 전달받은 action 정보와 nav_graph stop 속성이
    일치하는 노드에만 action을 부착한다.
    """
    if self._stop.action_map is None:
        return

    for node, name in zip(vda_nodes, path):
        node_attrs = self.nav_nodes.get(name, {}).get('attributes', {})
        if not node_attrs.get('stop', False):
            continue

        action_type = self._stop.action_map.get(name)
        if action_type is None:
            continue  # 매칭 안 되면 부착 안 함 (안전)

        action = Action(
            action_type=action_type,
            action_id=f'{action_type}_{self.cmd_id}_{uuid.uuid4().hex[:8]}',
            blocking_type=BlockingType.HARD,
            action_parameters=[],
        )
        node.actions.append(action)
```

### 3. `_apply_path_modifiers()` — stop 노드 Base/Horizon 분리

stop dest를 **Horizon으로 유지**하되, action은 이미 부착된 상태:

```python
# pickDrop path 제거 로직(L820) 이후에 추가
if (
    self._stop.destination is not None
    and len(path) >= 2
):
    stop_idx = None
    for i, node in enumerate(path):
        if node == self._stop.destination:
            stop_idx = i
            break
    if stop_idx is not None and stop_idx >= 1:
        # stop dest를 Horizon으로 — 직전 노드까지만 Base
        base_end_index = stop_idx - 1
```

**Plan A와의 차이**: path에서 dest를 제거하지 않음. action이 이미 부착되어 있으므로
dest 노드를 order에 포함시키되 Horizon으로 설정.

### 4. execute_action() — action 완료 모니터링만

stop 노드에 action이 이미 order에 포함되어 있으므로, execute_action 콜백에서는
새 order update를 보내지 않고 **action 완료를 대기**만 한다:

```python
def execute_action(self, category, description, execution):
    ...
    # stop 노드 action이 이미 order에 포함된 경우
    if self._stop.destination is not None and self._stop.action_sent:
        # order update 없이 action 완료 모니터링만
        self._track_action_completion(action_id)
        return
    ...
```

### 5. order update 시 Base 릴리즈

action 완료 후 다음 navigate에서 Horizon이었던 stop 노드를 **Base로 릴리즈**:

```python
# navigate()에서 order update 시
# 이전 order의 Horizon이었던 stop 노드를 Base로 변경
# → orderUpdateId 증가, 같은 orderId
```

### 6. `_reset_order_state()` — stop 상태 리셋

```python
self._stop.destination = None
self._stop.action_map = None
```

### 7. action 정보 주입 경로 (bridge 연동)

bridge에서 pick/drop 노드 정보를 받아 `_stop.action_map`에 설정하는 부분.
**구현 방법은 bridge 인터페이스에 따라 결정.**

```python
# 예시: task description에서 파싱
# navigate 호출 전 또는 fleet adapter 초기화 시
robot_adapter._stop.action_map = {
    'wp3': 'pick',
    'wp5': 'drop',
}
```

## Order 예시

### 경로: wp1 → wp2 → wp3(stop=true) → wp4 → wp5(stop=true)

```
Phase 1 (navigate to wp3):
  orderId=order_A, updateId=0
  VDA5050: wp1(B,seq=0) → wp2(B,seq=2) → wp3(H,seq=4,pick) → wp4(H,seq=6) → wp5(H,seq=8,drop)
  → wp2 도착 시 execution.finished()

Phase 2 (pick at wp3):
  orderId=order_A, updateId=1
  VDA5050: wp1(B) → wp2(B) → wp3(B,pick) → wp4(H) → wp5(H,drop)
  → Horizon→Base 릴리즈 (orderUpdate), 로봇이 wp3으로 이동 + pick 실행
  → order 리셋

Phase 3 (navigate to wp5):
  orderId=order_B, updateId=0
  VDA5050: wp3(B,seq=0) → wp4(B,seq=2) → wp5(H,seq=4,drop)
  → wp4 도착 시 execution.finished()

Phase 4 (drop at wp5):
  orderId=order_B, updateId=1
  VDA5050: wp3(B) → wp4(B) → wp5(B,drop)
  → Horizon→Base 릴리즈, 로봇이 wp5으로 이동 + drop 실행
  → order 리셋
```

## 장단점

- **장점**: 로봇이 처음부터 전체 계획 파악, 경로 최적화/감속 준비 가능
- **단점**: 수정 범위 넓음 (6~7곳), action 정보 사전 확보 필요, bridge 연동 추가 구현

## 구현 순서

1. `StopState` dataclass 추가 + `__init__`에서 초기화
2. `_detect_dest_attributes()`에 stop 감지 로직 추가
3. bridge에서 action 정보 주입 경로 구현
4. `_attach_stop_actions()` 메서드 구현
5. `_apply_path_modifiers()`에 stop Base/Horizon 분리 추가
6. `execute_action()`에 stop action 모니터링 분기 추가
7. `_reset_order_state()`에 stop 리셋 추가
8. Unit test 작성
9. 기존 pickDrop 테스트 통과 확인

---

# Plan A vs Plan B 비교 요약

| 항목 | Plan A | Plan B |
|------|--------|--------|
| 코드 수정량 | **1줄** | 6~7곳 |
| 리스크 | 최소 (검증된 로직 재사용) | 중간 (새 로직 + bridge 연동) |
| 초기 order에 action | 없음 | **포함** |
| execute_action 동작 | order update 전송 | 완료 모니터링만 |
| orderUpdate 횟수 | 많음 (phase마다) | 적음 (릴리즈만) |
| bridge 연동 | 불필요 | **필요** |
| 로봇 사전 정보 | 경로만 | 전체 계획 |
| 구현 난이도 | 쉬움 | 중간~높음 |
