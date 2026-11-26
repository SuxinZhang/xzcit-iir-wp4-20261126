# Lightweight defect alert pushed to the gateway and student H5 clients.
# 推送给业务网关与学生端 H5 客户端的轻量缺陷告警。
std_msgs/Header header
# Unique capture identifier matching the DefectArray message.
# 与 DefectArray 消息对应的唯一抓拍标识。
string capture_id
# Inspection point identifier configured by the patrol route.
# 巡检路线配置的巡检点标识。
string inspection_point
# Severity level: none, low, medium, or high.
# 严重程度：none、low、medium 或 high。
string severity
# Number of accepted defect detections in this capture.
# 本次抓拍通过筛选的缺陷数量。
uint16 defect_count
# Compact JSON summary for popup and list rendering.
# 用于弹窗与列表渲染的紧凑 JSON 摘要。
string summary_json
