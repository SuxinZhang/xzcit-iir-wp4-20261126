# Build the typed inspection interfaces used by the WP4 vision and gateway chain.
# 构建 WP4 视觉与网关链路使用的类型化巡检接口。
cmake_minimum_required(VERSION 3.8)
project(iir_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)

# Generate language bindings from the canonical msg and srv definitions.
# 根据唯一的 msg 与 srv 定义生成各语言绑定。
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/DefectDetection.msg"
  "msg/DefectArray.msg"
  "msg/InspectionAlert.msg"
  "srv/InspectionCapture.srv"
  DEPENDENCIES std_msgs
)

# Export the runtime dependency so downstream packages can load the bindings.
# 导出运行时依赖，确保下游包能够加载这些绑定。
ament_export_dependencies(rosidl_default_runtime)
ament_package()
