#!/usr/bin/env bash
# engineering-thinking 工作流门禁脚本
# 用法: gate-check.sh <子命令> [参数]
#
# 子命令:
#   init                    初始化当前任务的状态文件
#   stage <阶段名>          记录进入某阶段
#   plan <set|check>        记录/检查计划是否已写
#   edit <文件路径>          记录一次编辑并检查是否超限
#   confidence <数值>       记录置信度（0-100）
#   status                  显示当前状态
#   reset                   清除状态，开始新任务
#
# 状态文件位置: /tmp/.engineering-thinking-state.json
# 退出码: 0=通过 1=失败 3=参数错误

set -euo pipefail

STATE_FILE="/tmp/.engineering-thinking-state.json"
EDIT_LIMIT=2

# --- 工具函数 ---

ensure_state() {
  if [ ! -f "$STATE_FILE" ]; then
    init_state
  fi
}

init_state() {
  cat > "$STATE_FILE" << 'INIT'
{
  "current_stage": "",
  "stages_visited": [],
  "plan_exists": false,
  "confidence": 0,
  "edits": {},
  "in_recovery": false
}
INIT
}

read_field() {
  local field="$1"
  python3 -c "
import json, sys
with open('$STATE_FILE') as f:
    data = json.load(f)
keys = '$field'.split('.')
val = data
for k in keys:
    val = val[k] if isinstance(val, dict) else val
print(json.dumps(val) if isinstance(val, (dict, list, bool)) else val)
" 2>/dev/null
}

update_state() {
  local py_code="$1"
  python3 -c "
import json
with open('$STATE_FILE') as f:
    data = json.load(f)
$py_code
with open('$STATE_FILE', 'w') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
" 2>/dev/null
}

log() { echo "$*" >&2; }

ok()   { echo "{\"ok\":true,\"message\":\"$1\"}"; }
fail() { echo "{\"ok\":false,\"code\":\"$1\",\"error\":\"$2\",\"hint\":\"$3\"}"; }

# --- 子命令 ---

cmd_init() {
  init_state
  ok "状态已初始化"
}

cmd_stage() {
  local stage="${1:-}"
  if [ -z "$stage" ]; then
    fail "GT-001" "缺少阶段名" "用法: gate-check.sh stage <观察|理解|定位|上下文|假设|取证|计划|修改|验证|审查>"
    exit 3
  fi

  ensure_state
  update_state "
data['current_stage'] = '$stage'
if '$stage' not in data['stages_visited']:
    data['stages_visited'].append('$stage')
"
  ok "进入阶段: $stage"
}

cmd_plan() {
  local action="${1:-check}"
  ensure_state

  case "$action" in
    set)
      update_state "data['plan_exists'] = True"
      ok "计划已记录"
      ;;
    check)
      local exists
      exists=$(read_field "plan_exists")
      if [ "$exists" = "true" ] || [ "$exists" = "True" ]; then
        ok "计划已存在，允许进入修改阶段"
      else
        fail "GT-002" "尚未写计划" "必须先输出书面计划再修改代码。执行: gate-check.sh plan set"
        exit 1
      fi
      ;;
    *)
      fail "GT-001" "未知 plan 操作: $action" "可选: set / check"
      exit 3
      ;;
  esac
}

cmd_edit() {
  local filepath="${1:-}"
  if [ -z "$filepath" ]; then
    fail "GT-001" "缺少文件路径" "用法: gate-check.sh edit <文件路径>"
    exit 3
  fi

  ensure_state

  # 门禁1: 检查计划
  local plan_exists
  plan_exists=$(read_field "plan_exists")
  if [ "$plan_exists" != "true" ] && [ "$plan_exists" != "True" ]; then
    fail "GT-002" "门禁拦截: 尚未写计划就要编辑 $filepath" "先执行: gate-check.sh plan set"
    exit 1
  fi

  # 门禁2: 检查置信度
  local confidence
  confidence=$(read_field "confidence")
  if [ "$confidence" -lt 40 ] 2>/dev/null; then
    fail "GT-003" "门禁拦截: 置信度 ${confidence}% < 40%，不允许编辑" "继续调查，提升置信度后再改"
    exit 1
  fi

  # 门禁3: 检查编辑次数
  local count
  count=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    data = json.load(f)
print(data.get('edits', {}).get('$filepath', 0))
" 2>/dev/null)

  local new_count=$((count + 1))

  update_state "
edits = data.setdefault('edits', {})
edits['$filepath'] = edits.get('$filepath', 0) + 1
if edits['$filepath'] >= $EDIT_LIMIT:
    data['in_recovery'] = True
"

  if [ "$new_count" -gt "$EDIT_LIMIT" ]; then
    fail "GT-004" "门禁拦截: $filepath 已编辑 ${new_count} 次（上限 ${EDIT_LIMIT}），进入恢复模式" "停止编辑，执行恢复模式：总结→重新搜索→重新假设"
    exit 1
  fi

  ok "允许编辑 $filepath（第 ${new_count}/${EDIT_LIMIT} 次）"
}

cmd_confidence() {
  local value="${1:-}"
  if [ -z "$value" ]; then
    fail "GT-001" "缺少置信度值" "用法: gate-check.sh confidence <0-100>"
    exit 3
  fi

  ensure_state
  update_state "data['confidence'] = $value"

  if [ "$value" -lt 40 ] 2>/dev/null; then
    log "警告: 置信度 ${value}% < 40%，当前禁止修改代码"
  fi
  ok "置信度已记录: ${value}%"
}

cmd_status() {
  ensure_state
  python3 -c "
import json
with open('$STATE_FILE') as f:
    data = json.load(f)
print(json.dumps(data, ensure_ascii=False, indent=2))
" 2>/dev/null
}

cmd_reset() {
  init_state
  ok "状态已重置，可开始新任务"
}

# --- 入口 ---

case "${1:-}" in
  init)       cmd_init ;;
  stage)      cmd_stage "${2:-}" ;;
  plan)       cmd_plan "${2:-}" ;;
  edit)       cmd_edit "${2:-}" ;;
  confidence) cmd_confidence "${2:-}" ;;
  status)     cmd_status ;;
  reset)      cmd_reset ;;
  *)
    cat >&2 << 'USAGE'
engineering-thinking 工作流门禁

用法: gate-check.sh <子命令> [参数]

子命令:
  init                    初始化状态
  stage <阶段名>          记录当前阶段
  plan <set|check>        记录/检查计划
  edit <文件路径>          记录编辑（自动检查门禁）
  confidence <0-100>      记录置信度
  status                  显示当前状态
  reset                   清除状态
USAGE
    exit 3
    ;;
esac