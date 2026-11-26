# Structured inference output archived for one inspection capture.
# 单次巡检抓拍归档的结构化推理输出。
std_msgs/Header header
# Unique capture identifier shared by the archive, gateway, and web clients.
# 由归档、网关与 Web 客户端共享的唯一抓拍标识。
string capture_id
# Inspection point identifier configured by the patrol route.
# 巡检路线配置的巡检点标识。
string inspection_point
# Trigger source: manual, patrol, or gateway.
# 触发来源：手动、巡逻或网关。
string source
# Absolute path of the archived original image on the edge computer.
# 边缘计算机上归档原图的绝对路径。
string image_path
# Absolute path of the archived annotated image on the edge computer.
# 边缘计算机上归档标注图的绝对路径。
string annotated_path
# Wall-clock inference duration in milliseconds.
# 推理耗时，单位为毫秒。
float32 inference_ms
# All accepted defect detections for this capture.
# 本次抓拍全部通过筛选的缺陷检测结果。
DefectDetection[] detections
