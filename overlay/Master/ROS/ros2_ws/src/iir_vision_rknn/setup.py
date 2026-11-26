from glob import glob

from setuptools import setup

package_name = 'iir_vision_rknn'

# Install the ROS package metadata, launch files, and default label table.
# 安装 ROS 包元数据、launch 文件与默认标签表。
setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.txt')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='snow',
    maintainer_email='snow@example.com',
    description='RK3588S NPU defect detection and inspection capture archive.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'inspection_vision_node = iir_vision_rknn.node:main',
        ],
    },
)
