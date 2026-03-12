# VDA5050 Actions Definition

## Overview

VDA5050 fleet adapter에서 지원하는 action 목록과 정의를 관리하는 문서.
Action은 3가지 방식으로 AGV에 전달된다:

| 전달 방식 | 설명 | 사용 시점 |
|-----------|------|----------|
| **nodeAction** | Order의 Node에 첨부 | 특정 위치 도착 시 실행 |
| **edgeAction** | Order의 Edge에 첨부 | 이동 중 실행 |
| **instantAction** | Order와 독립적으로 전송 | 즉시 실행 (활성 order 없을 때) |

---

## Action 공통 구조

```json
{
  "actionType": "string",
  "actionId": "string (UUID)",
  "blockingType": "NONE | SOFT | HARD",
  "actionDescription": "string (optional)",
  "actionParameters": [
    { "key": "string", "value": "string | number | boolean | array" }
  ]
}
```

### BlockingType 정의

| Type | 설명 |
|------|------|
| `NONE` | 주행과 병렬 실행 가능 |
| `SOFT` | 다른 action과 병렬 가능, 주행은 차단 |
| `HARD` | 모든 것을 차단 (독점 실행) |

---

## 현재 구현된 Action

### System Actions (내부 사용)

| actionType | blockingType | 전달 방식 | 설명 | 비고 |
|------------|-------------|----------|------|------|
| `cancelOrder` | HARD | instantAction | 현재 order 취소 | negotiation 시 사용 |
| `startPause` | HARD | instantAction | AGV 일시 정지 | negotiation 시 사용 |
| `stopPause` | HARD | instantAction | 일시 정지 해제 | - |

### RMF Task Actions

| actionType | blockingType | 전달 방식 | 설명 | actionParameters |
|------------|-------------|----------|------|-----------------|
| `teleop` | HARD | instantAction | 원격 조종 | - |
| `pick` | HARD | nodeAction / instantAction | 화물 적재 | `loadType`, `loadID` |
| `drop` | HARD | nodeAction / instantAction | 화물 하역 | `stationName` |

#### `pick` Action 상세

카트/화물 적재 action. RMF Task 생성 시 매개변수로 전달받는다.

```json
{
  "actionType": "pick",
  "actionId": "pick-patrol.dispatch-0",
  "blockingType": "HARD",
  "actionParameters": [
    { "key": "loadType", "value": "Tool" },
    { "key": "loadID", "value": "SP4ECTR002" }
  ]
}
```

| Parameter | Type | 설명 | 예시 | 소스 |
|-----------|------|------|------|------|
| `loadType` | string | 적재물 타입 종류 | `"Tool"`, `"Pallet"`, `"Box"` | Task 매개변수 |
| `loadID` | string | 카트(적재물) 고유 ID | `"SP4ECTR002"` | Task 매개변수 |

#### `drop` Action 상세

카트/화물 하역 action. RMF Task 생성 시 매개변수로 전달받는다.

```json
{
  "actionType": "drop",
  "actionId": "drop-patrol.dispatch-0",
  "blockingType": "HARD",
  "actionParameters": [
    { "key": "stationName", "value": "1004" }
  ]
}
```

| Parameter | Type | 설명 | 예시 | 소스 |
|-----------|------|------|------|------|
| `stationName` | string | 하역할 스테이션 이름 | `"1004"` | Task 매개변수 |

#### Cart Delivery (pick/drop) 시퀀스 — pickDrop 모드

Cart delivery는 pickup → dropoff 2개의 phase로 구성된다.
`pickDrop: true` 속성이 있는 노드에서는 **Phase 1+2 = order_A, Phase 3+4 = order_B**로
2개의 orderID를 사용한다. pickDrop destination은 navigate 시 horizon으로 유지되어
order가 살아있는 상태에서 execute_action이 released로 전환한다.

**전제**: nav_graph에서 pickup/dropoff 스테이션에 `pickDrop: true` 속성이 설정되어 있어야 한다.

```
RMF Task: cart_delivery (wp1 → wp2[pickup, pickDrop] → wp3[dropoff, pickDrop])

Phase 1: navigate(dest=wp2, final=wp2)
  → 새 orderID 생성 (order_A), order_update_id=0
  → pickDrop 감지 → wp2를 horizon으로 유지
  → 도착 판정 대상 = wp1 (직전 노드)
  ┌──────────────────────────────────────────────┐
  │ Order (orderID=A, updateId=0)                │
  │   wp1(base, seq=0) → wp2(horizon, seq=2)     │
  └──────────────────────────────────────────────┘
  → wp1 거리 기반 도착 감지 → execution.finished()

Phase 2: execute_action('pick', {loadType, loadID})
  → active order 존재 + pickDrop → _build_pick_drop_order_update()
  → order_update_id++ (=1)
  → 경로: wp1 → wp2, 모든 노드 base (released)
  → wp2에 pick nodeAction(HARD) 부착
  ┌──────────────────────────────────────────────┐
  │ Order Update (orderID=A, updateId=1)         │
  │   wp1(base, seq=0) → wp2(base, seq=2,       │
  │     actions=[pick{HARD}])                     │
  │   ↳ track_action_id로 완료 추적              │
  └──────────────────────────────────────────────┘
  → Order 라이프사이클 리셋 (_active_order_id = None)
  → AGV의 actionStates에서 action_id FINISHED 감지 → execution.finished()

Phase 3: navigate(dest=wp3, final=wp3)
  → 새 orderID 생성 (order_B), order_update_id=0
  → pickDrop 감지 → wp3를 horizon으로 유지
  → 도착 판정 대상 = wp2 (직전 노드)
  ┌──────────────────────────────────────────────┐
  │ Order (orderID=B, updateId=0)                │
  │   wp2(base, seq=0) → wp3(horizon, seq=2)     │
  └──────────────────────────────────────────────┘
  → wp2 거리 기반 도착 감지 → execution.finished()

Phase 4: execute_action('drop', {stationName})
  → active order 존재 + pickDrop → _build_pick_drop_order_update()
  → order_update_id++ (=1)
  → 경로: wp2 → wp3, 모든 노드 base (released)
  → wp3에 drop nodeAction(HARD) 부착
  ┌──────────────────────────────────────────────┐
  │ Order Update (orderID=B, updateId=1)         │
  │   wp2(base, seq=0) → wp3(base, seq=2,       │
  │     actions=[drop{HARD}])                     │
  │   ↳ track_action_id로 완료 추적              │
  └──────────────────────────────────────────────┘
  → Order 라이프사이클 리셋 (_active_order_id = None)
  → AGV의 actionStates에서 action_id FINISHED 감지 → execution.finished()

Task 완료 → _reset_order_state()
```

핵심 구현 사항:
- `pickDrop: true` 속성이 있는 destination → navigate에서 horizon 유지, 직전 노드까지 base
- `execute_action()` 호출 시 `_pick_drop_destination`이 설정되면 `_build_pick_drop_order_update()` 사용
- `_build_pick_drop_order_update()`: 모든 노드 base, action을 마지막 노드에 부착, 전송 후 order 리셋
- Phase 1+2 = order_A, Phase 3+4 = order_B (별도 orderID)
- `track_action_id`로 action 완료를 모니터링 (order 완료가 아닌 action 단위)
- 로봇이 이미 pickDrop destination에 있으면 order 미생성, 즉시 완료

#### Cart Delivery — Station Node Removal 모드

pickDrop 속성이 destination의 **직전 노드**(staging node)에 있고, destination 자체가 실제 카트/드롭 위치(station node)인 시나리오. Station node는 VDA5050 order에서 제거되고, pick/drop action은 staging node에 부착된다. `stationName` 파라미터는 제거된 station node 이름으로 자동 채워진다.

**전제**: nav_graph에서 staging node에 `pickDrop: true` 속성이 설정되어 있어야 한다.

```
RMF Task: cart_delivery (wp1 → wp3[staging,pickDrop] → wp4[station] → wp5[staging,pickDrop] → wp6[station])

Phase 1: navigate(dest=wp4, final=wp4)
  → path 계산: [wp1, wp2, wp3, wp4]
  → station node removal: path[-2]=wp3(pickDrop) 감지
  → wp4(station) 제거, _pick_drop_station_node=wp4
  → path=[wp1, wp2, wp3], pickDrop dest=wp3
  → wp3를 horizon으로 유지, wp2까지 base
  → 도착 판정 대상 = wp2 (pre-staging)
  ┌──────────────────────────────────────────────┐
  │ Order (orderID=A, updateId=0)                │
  │   wp1(base, seq=0) → wp2(base, seq=2) →     │
  │   wp3(horizon, seq=4)                        │
  │   ↳ wp4는 order에 미포함                      │
  └──────────────────────────────────────────────┘
  → wp2 거리 기반 도착 감지 → execution.finished()

Phase 2: execute_action('pick', {loadType, loadID})
  → _build_pick_drop_order_update()
  → 경로: wp2 → wp3, 모든 노드 base
  → wp3에 pick nodeAction(HARD) 부착
  ┌──────────────────────────────────────────────┐
  │ Order Update (orderID=A, updateId=1)         │
  │   wp2(base, seq=0) → wp3(base, seq=2,       │
  │     actions=[pick{HARD}])                    │
  └──────────────────────────────────────────────┘
  → Order 라이프사이클 리셋

Phase 3: navigate(dest=wp6, final=wp6)
  → station node removal: wp5(pickDrop) 감지, wp6 제거
  → path=[..., wp5], pickDrop dest=wp5
  ┌──────────────────────────────────────────────┐
  │ Order (orderID=B, updateId=0)                │
  │   wp3(base) → ... → wp5(horizon)             │
  │   ↳ wp6는 order에 미포함                      │
  └──────────────────────────────────────────────┘

Phase 4: execute_action('drop', {stationName: 'wp6'})
  → stationName은 RMF Task params에서 제공
  → _build_pick_drop_order_update()
  ┌──────────────────────────────────────────────┐
  │ Order Update (orderID=B, updateId=1)         │
  │   ...→ wp5(base, actions=[drop{HARD,         │
  │     stationName=wp6}])                       │
  └──────────────────────────────────────────────┘
  → Order 라이프사이클 리셋

Task 완료 → _reset_order_state()
```

핵심 구현 사항:
- path[-2]가 pickDrop이면 path[-1](station node)을 경로에서 제거 (charging 패턴 동일)
- `_pick_drop_station_node`에 제거된 station node 이름 저장
- `stationName`은 RMF Task 파라미터에서 직접 제공 (auto-fill 없음). `drop` action은 항상 `stationName` 포함
- dest 자체에 pickDrop이 있는 기존 시나리오와 충돌하지 않음 (`_pick_drop_destination is None` 체크)

### Charging Actions

| actionType | blockingType | 전달 방식 | 설명 | actionParameters |
|------------|-------------|----------|------|-----------------|
| `startCharging` | HARD | nodeAction | 충전 시작 (charger 앞 노드에 부착) | `stationName` |
| `stopCharging` | HARD | nodeAction | 충전 중지 (다음 order의 첫 번째 노드에 부착) | - |

#### `startCharging` Action 상세

RMF 자동 충전 시 charger 앞 노드에 nodeAction으로 부착된다.
Adapter가 `destination.dock`을 감지하여 자동 생성하므로 config 등록 불필요.
AGV가 startCharging을 실행하면 charger로 자율 도킹 → 충전 시작.
**AGV가 FINISHED를 보고하면 = 도킹 완료 + 충전 시작 완료.**

```json
{
  "actionType": "startCharging",
  "actionId": "startCharging_5_a1b2c3d4",
  "blockingType": "HARD",
  "actionParameters": [
    { "key": "stationName", "value": "charger_1" }
  ]
}
```

| Parameter | Type | 설명 | 예시 | 소스 |
|-----------|------|------|------|------|
| `stationName` | string | 충전 스테이션 이름 (charger 노드 이름) | `"charger_1"` | `destination.dock` |

#### `stopCharging` Action 상세

충전 완료 후 **다음 order의 첫 번째 노드**에 nodeAction으로 부착된다.
Adapter는 SOC를 모니터링하지 않으며, 로봇의 충전/방전은 로봇이 자율적으로 관리한다.
파라미터 없음.

```json
{
  "actionType": "stopCharging",
  "actionId": "stopCharging_7_e5f6g7h8",
  "blockingType": "HARD",
  "actionParameters": []
}
```

#### Charging 시퀀스

RMF가 `battery_soc <= recharge_threshold`를 감지하면 자동으로 충전 task를 생성한다.
충전 task에서 RMF는 `navigate(destination)` 호출 시 `destination.dock = "charger_name"`을 설정한다.

**핵심 원칙:**
- Adapter는 SOC를 모니터링하지 않음 → 충전/방전 제어는 로봇 자율 영역
- `startCharging` FINISHED = 도킹 완료 + 충전 시작 → `execution.finished()`
- `stopCharging`은 다음 order에서 nodeAction으로 전달 (instantAction 아님)
- `_was_charging` 플래그로 다음 order에 `stopCharging` 부착 여부 결정

```
전제: config에 finishing_request: "park" 설정
      battery_soc <= recharge_threshold → RMF가 자동 충전 task 생성

경로 예시: wp1 → wp2 → wp3 → charger_1

Phase 1: navigate(dest=charger_1, dock="charger_1")
  → dock 감지 → _is_charging_pending = True
  → 경로 계산: [wp1, wp2, wp3, charger_1]
  → charger 노드 제거: [wp1, wp2, wp3]
  → wp3(pre-charger)에 startCharging nodeAction 부착
  → _navigate_target_position = wp3 좌표 (charger가 아닌 pre-charger)
  → track_action_id = startCharging의 action_id (action 완료 추적용)
  ┌──────────────────────────────────────────────────────────────┐
  │ Order (track_action_id=startCharging_X)                     │
  │   wp1(base) → wp2(base) → wp3(base,                         │
  │     actions=[startCharging{HARD, stationName:"charger_1"}])  │
  │   ↳ charger_1 노드는 order에 미포함                          │
  └──────────────────────────────────────────────────────────────┘

Phase 2: AGV 이동 → pre-charger(wp3) 도착
  → update()에서 거리 기반 도착 감지 (wp3까지)
  → _is_charging_pending → _is_charging 전환
  → execution.finished() 호출하지 않음 (startCharging action 대기)
  → AGV가 wp3 도착 후 startCharging nodeAction 자동 실행
  → AGV가 charger_1로 자율 도킹하여 충전 시작

Phase 3: startCharging action 완료 대기 (update() 루프)
  → _is_charging == True 상태에서 is_command_completed() 감시
  → startCharging action FINISHED (= 도킹 완료 + 충전 시작):
    → _was_charging = True (다음 order에 stopCharging 필요)
    → _is_charging_decommissioned = True (SOC 도달까지 decommission)
    → execution.finished() 호출
    → 충전 task 완료

Phase 4: 충전 중 decommission (update() 루프)
  → _is_charging_decommissioned == True 상태
  → battery_soc < recharge_soc → decommission 유지
    (dispatched=False, direct=False, idle=False → Task 할당 차단)
  → battery_soc >= recharge_soc → recommission
    (_is_charging_decommissioned = False, _last_commission = None)
    → 다음 update에서 API-level commission 재평가
  → _reset_order_state() 호출되어도 _was_charging,
    _is_charging_decommissioned은 보존

Phase 5: 다음 order (RMF가 새 task 생성 시)
  → navigate() 호출 시 _was_charging == True 감지
  → 첫 번째 노드에 stopCharging nodeAction 부착
  → _was_charging = False, _is_charging_decommissioned = False로 초기화
  ┌──────────────────────────────────────────────────────────┐
  │ Order (새 task)                                          │
  │   wp3(base, actions=[stopCharging{HARD}]) → ... → dest  │
  │   ↳ AGV가 stopCharging 실행 → 언도킹 → 이동 시작        │
  └──────────────────────────────────────────────────────────┘

Task 완료 → _reset_order_state()
```

핵심 구현 사항:
- `destination.dock`이 문자열이면 충전 task로 판단
- 경로에서 charger 노드(마지막 노드)를 제거하고, 바로 앞 노드에 `startCharging` 부착
- `_navigate_target_position`을 pre-charger 좌표로 변경하여 도착 판정 기준 조정
- pre-charger 도착 시 `_is_charging = True`로 전환
- `is_command_completed()`로 startCharging action FINISHED 감지 → `execution.finished()`
- `_was_charging`, `_is_charging_decommissioned` 플래그는 `_reset_order_state()`에서 초기화되지 않음
- 다음 navigate 호출 시 `_was_charging == True`이면 첫 번째 노드에 `stopCharging` 부착
- 충전 중 decommission: `_is_charging_decommissioned`가 True이면 `battery_soc >= recharge_soc`까지 decommission 유지
- `recharge_soc`는 config.yaml의 `rmf_fleet.recharge_soc`에서 로드 (기본값 1.0)

예외 처리:
- 충전 중 negotiation (`stop()`) → `_was_charging = True`, `_is_charging_decommissioned = False` → `startPause` → `cancelOrder` → 새 order에 `stopCharging` 부착
- `_reset_order_state()` 호출 시 `_was_charging`, `_is_charging_decommissioned`을 제외한 모든 충전 상태 초기화

### Map Management Actions

| actionType | blockingType | 전달 방식 | 설명 | actionParameters |
|------------|-------------|----------|------|-----------------|
| `downloadMap` | NONE | instantAction | 로봇 ONLINE 전환 시 맵 다운로드 | `mapId`, `mapDownloadUrl`, `mapVersion` |

#### `downloadMap` Action 상세

로봇이 ONLINE으로 연결(또는 재연결)될 때 자동으로 `downloadMap` instantAction을 전송한다.
Config(`download_map` 섹션)가 없으면 비활성화된다.

```json
{
  "actionType": "downloadMap",
  "actionId": "downloadMap_a1b2c3d4",
  "blockingType": "NONE",
  "actionParameters": [
    { "key": "mapId", "value": "L1" },
    { "key": "mapDownloadUrl", "value": "http://example.com/map.tar.gz" },
    { "key": "mapVersion", "value": "2.4.1" }
  ]
}
```

| Parameter | Type | 설명 | 예시 | 소스 |
|-----------|------|------|------|------|
| `mapId` | string | 다운로드할 맵 ID | `"L1"` | config.yaml `download_map.map_id` |
| `mapDownloadUrl` | string | 맵 파일 다운로드 URL | `"http://example.com/map.tar.gz"` | config.yaml `download_map.map_download_url` |
| `mapVersion` | string | 맵 버전 | `"2.4.1"` | config.yaml `download_map.map_version` |

#### downloadMap 시퀀스

```
Phase 1: 로봇 연결 감지
  → connection topic에서 ONLINE 수신
  → 이전 상태가 ONLINE이 아닌 경우 (None, OFFLINE, CONNECTIONBROKEN)
  → downloadMap instantAction 전송
  → _download_map_pending[robot_name] = action_id 저장

Phase 2: 맵 다운로드 완료 대기
  → navigate() 호출 시 is_download_map_ready() pre-flight check
  → _update_robot()에서 add_robot 전 is_download_map_ready() check
  → AGV의 actionStates에서 해당 action_id가 FINISHED/FAILED 확인
  → FINISHED/FAILED → is_download_map_ready() = True → 정상 동작 재개

Phase 3: 재연결 시
  → OFFLINE/CONNECTIONBROKEN → ONLINE 전환 감지
  → 새로운 downloadMap action 전송 (기존 pending 덮어쓰기)
  → 맵 다운로드 완료까지 order 전송 차단
```

#### Config 설정

```yaml
# config.yaml
download_map:
  map_id: "L1"
  map_download_url: "http://example.com/map.tar.gz"
```

`download_map` 섹션이 없으면 downloadMap 기능이 비활성화되며,
`is_download_map_ready()`는 항상 True를 반환한다.

---

## 추가 예정 Action

### Navigation / Positioning

| actionType | blockingType | 전달 방식 | 설명 | actionParameters | 구현 상태 |
|------------|-------------|----------|------|-----------------|----------|
| `initPosition` | HARD | instantAction | AGV 위치 초기화 | `x`, `y`, `theta`, `mapId`, `lastNodeId` | [ ] |
| `finePositioning` | HARD | nodeAction | 정밀 위치 조정 | `stationType`, `stationName` | [ ] |

### Cargo Handling

> `pick`/`drop`은 RMF Task Actions로 이동됨 (위 섹션 참조)

### Map Management

| actionType | blockingType | 전달 방식 | 설명 | actionParameters | 구현 상태 |
|------------|-------------|----------|------|-----------------|----------|
| `downloadMap` | NONE | instantAction | 맵 다운로드 | `mapId`, `mapDownloadUrl` | [x] |
| `enableMap` | NONE | instantAction | 맵 활성화 | `mapId` | [ ] |
| `deleteMap` | NONE | instantAction | 맵 삭제 | `mapId` | [ ] |

### Trigger / Wait

| actionType | blockingType | 전달 방식 | 설명 | actionParameters | 구현 상태 |
|------------|-------------|----------|------|-----------------|----------|
| `waitForTrigger` | HARD | nodeAction | 외부 트리거 대기 | `triggerType`, `timeout` | [ ] |

### Information

| actionType | blockingType | 전달 방식 | 설명 | actionParameters | 구현 상태 |
|------------|-------------|----------|------|-----------------|----------|
| `factsheetRequest` | NONE | instantAction | AGV factsheet 요청 | - | [ ] |

### Custom Actions (프로젝트 특화)

| actionType | blockingType | 전달 방식 | 설명 | actionParameters | 구현 상태 |
|------------|-------------|----------|------|-----------------|----------|
| | | | | | [ ] |

---

## Action 구현 체크리스트

새로운 action 추가 시 아래 항목을 모두 완료해야 한다:

- [ ] `domain/entities/action.py` - 필요시 action 관련 상수/헬퍼 추가
- [ ] `config/config.yaml` - `actions` 목록에 actionType 등록
- [ ] `usecase/robot_adapter.py` - execute_action 콜백에서 처리 로직 구현
- [ ] `infra/mqtt/vda5050_robot_api.py` - 전송 로직 (nodeAction / instantAction)
- [ ] `infra/mqtt/message_serializer.py` - 직렬화/역직렬화 확인
- [ ] `test/` - 단위 테스트 작성
- [ ] 이 문서(`VDA5050_ACTIONS.md`) 업데이트

---

## Config 등록 방법

`config.yaml`의 `actions` 목록에 actionType을 추가:

```yaml
rmf_fleet:
  actions: ["teleop", "pick", "drop", "NEW_ACTION_TYPE"]
```

---

## Action 흐름도

```
RMF Task
  │
  ├─ navigate() ──────────────────────────► Order (nodeAction/edgeAction)
  │                                              │
  ├─ execute_action() ─┬─ active order 있음 ──► Order Update (nodeAction)
  │                    └─ active order 없음 ──► InstantAction
  │
  └─ stop() ──────────────────────────────► InstantAction (startPause)

                         ┌──────────────────┐
                         │   AGV (VDA5050)   │
                         └────────┬─────────┘
                                  │
                         State (actionStates)
                                  │
                    ┌─────────────▼──────────────┐
                    │ WAITING → INITIALIZING →    │
                    │ RUNNING → FINISHED/FAILED   │
                    └─────────────────────────────┘
```
