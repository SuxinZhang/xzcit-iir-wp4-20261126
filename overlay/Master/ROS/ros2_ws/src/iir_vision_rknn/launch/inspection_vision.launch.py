"""Launch the RKNN inspection node with configurable model and capture paths.
以可配置的模型与抓拍路径启动 RKNN 巡检节点。
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Build the launch description consumed by ros2 launch.
    构建由 ros2 launch 消费的启动描述。
    """
    return LaunchDescription([
        DeclareLaunchArgument(
            'backend', default_value='auto',
            description='Inference backend: auto, rknn, or mock. / 推理后端：auto、rknn 或 mock。'),
        DeclareLaunchArgument(
            'model_file', default_value='',
            description='Absolute path of the RKNN model file. / RKNN 模型文件的绝对路径。'),
        DeclareLaunchArgument(
            'labels_file', default_value='',
            description='Absolute path of the label table. / 标签表的绝对路径。'),
        DeclareLaunchArgument(
            'capture_dir', default_value='~/.cache/iir/captures',
            description='Archive directory for captures. / 抓拍归档目录。'),
        DeclareLaunchArgument(
            'auto_capture_period_s', default_value='0.0',
            description='Periodic patrol capture period; zero disables it. / 巡逻周期抓拍周期，零表示关闭。'),
        Node(
            package='iir_vision_rknn',
            executable='inspection_vision_node',
            name='iir_vision_rknn',
            output='screen',
            parameters=[{
                'backend': LaunchConfiguration('backend'),
                'model_file': LaunchConfiguration('model_file'),
                'labels_file': LaunchConfiguration('labels_file'),
                'capture_dir': LaunchConfiguration('capture_dir'),
                'auto_capture_period_s': LaunchConfiguration('auto_capture_period_s'),
            }],
        ),
    ])
