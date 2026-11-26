"""ROS 2 node that detects power-equipment defects and archives inspection captures.
检测电力设备缺陷并归档巡检抓拍的 ROS 2 节点。
"""

from __future__ import annotations

import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Header

from iir_interfaces.msg import DefectArray, DefectDetection, InspectionAlert
from iir_interfaces.srv import InspectionCapture

from .annotate import decode_jpeg, draw_detections, encode_jpeg
from .archive import CaptureArchive, new_capture_id, utc_now_iso
from .backends import DEFAULT_LABELS, build_backend, load_labels
from .result import build_result


class InspectionVisionNode(Node):
    """Run RKNN inference on the shared camera stream and archive captures.
    在共享相机流上运行 RKNN 推理并归档抓拍。
    """

    def __init__(self, *, backend_factory=build_backend, archive_factory=CaptureArchive):
        super().__init__('iir_vision_rknn')

        # Declare every configuration knob with a production-safe default.
        # 声明全部配置项并给出生产安全默认值。
        self.declare_parameter('backend', 'auto')
        self.declare_parameter('model_file', '')
        self.declare_parameter('labels_file', '')
        self.declare_parameter('input_size', 640)
        self.declare_parameter('confidence_threshold', 0.25)
        self.declare_parameter('nms_iou_threshold', 0.45)
        self.declare_parameter('image_topic', '/image_raw/compressed')
        self.declare_parameter('capture_dir', '~/.cache/iir/captures')
        self.declare_parameter('max_image_age_s', 1.0)
        self.declare_parameter('auto_capture_period_s', 0.0)
        self.declare_parameter('jpeg_quality', 90)

        backend_kind = str(self.get_parameter('backend').value)
        model_file = str(self.get_parameter('model_file').value)
        labels_file = str(self.get_parameter('labels_file').value)
        input_size = int(self.get_parameter('input_size').value)
        confidence = float(self.get_parameter('confidence_threshold').value)
        nms_iou = float(self.get_parameter('nms_iou_threshold').value)
        image_topic = str(self.get_parameter('image_topic').value)
        capture_dir = str(self.get_parameter('capture_dir').value)
        self._max_image_age_s = float(self.get_parameter('max_image_age_s').value)
        self._jpeg_quality = int(self.get_parameter('jpeg_quality').value)

        if labels_file:
            labels, display_names = load_labels(labels_file)
        else:
            labels = list(DEFAULT_LABELS)
            display_names = {label: label for label in labels}
        self._labels = labels
        self._display_names = display_names

        self._backend = backend_factory(
            kind=backend_kind,
            model_file=model_file,
            labels=labels,
            input_size=input_size,
            conf_threshold=confidence,
            nms_iou=nms_iou,
            logger=self.get_logger(),
        )
        self._archive = archive_factory(capture_dir)

        # Cache only the newest frame; the camera node is the single owner of
        # the physical device and this node must never open it directly.
        # 仅缓存最新帧；相机节点是物理设备的唯一所有者，本节点不得直接打开设备。
        self._latest_frame = None
        self._subscription = self.create_subscription(
            CompressedImage, image_topic, self._on_image, qos_profile_sensor_data)
        self._defect_publisher = self.create_publisher(
            DefectArray, '/inspection/defects', 10)
        self._alert_publisher = self.create_publisher(
            InspectionAlert, '/inspection/alert', 10)
        self._capture_service = self.create_service(
            InspectionCapture, '/inspection/capture', self._on_capture)

        period_s = float(self.get_parameter('auto_capture_period_s').value)
        self._auto_timer = None
        if period_s > 0.0:
            # Periodic patrol capture is opt-in; manual and gateway triggers
            # always take precedence through the same capture path.
            # 周期性巡逻抓拍为可选功能；手动与网关照常通过同一抓拍路径触发。
            self._auto_timer = self.create_timer(period_s, self._on_auto_capture)

        self.get_logger().info(
            f'Inspection vision ready: backend={self._backend.name}, '
            f'labels={len(labels)}, capture_dir={capture_dir}')

    def _on_image(self, message: CompressedImage) -> None:
        """Store the newest compressed frame with its receipt time.
        保存最新压缩帧及其接收时刻。
        """
        self._latest_frame = {
            'data': bytes(message.data),
            'stamp_ns': int(message.header.stamp.sec) * 1_000_000_000
            + int(message.header.stamp.nanosec),
            'frame_id': message.header.frame_id or 'camera',
            'received_ns': int(self.get_clock().now().nanoseconds),
        }

    def _frame_age_s(self, frame: dict) -> float:
        """Return the age of a cached frame in seconds.
        返回缓存帧的年龄，单位为秒。
        """
        now_ns = int(self.get_clock().now().nanoseconds)
        if frame['stamp_ns'] > 0:
            return max(0.0, (now_ns - frame['stamp_ns']) / 1_000_000_000.0)
        return max(0.0, (now_ns - frame['received_ns']) / 1_000_000_000.0)

    def _run_capture(self, inspection_point: str, source: str, archive: bool):
        """Run the shared capture pipeline and return (ok, message, payload).
        执行共享抓拍流水线并返回 (是否成功, 消息, 载荷)。
        """
        frame = self._latest_frame
        if frame is None:
            return False, 'No camera frame has been received yet / 尚未收到相机帧', None
        age_s = self._frame_age_s(frame)
        if age_s > self._max_image_age_s:
            return False, (
                f'Latest camera frame is stale ({age_s:.2f} s) / '
                f'最新相机帧已过期（{age_s:.2f} 秒）'), None

        started = time.monotonic()
        try:
            image = decode_jpeg(frame['data'])
            detections = self._backend.infer(image)
            annotated = draw_detections(image, detections)
            original_bytes = encode_jpeg(image, self._jpeg_quality)
            annotated_bytes = encode_jpeg(annotated, self._jpeg_quality)
        except Exception as exc:  # Report a failed capture without killing the node.
            # 上报抓拍失败但保持节点存活。
            self.get_logger().error(f'Inspection capture failed: {exc}')
            return False, f'Inference failed: {exc} / 推理失败：{exc}', None

        inference_ms = (time.monotonic() - started) * 1000.0
        capture_id = new_capture_id()
        result = build_result(
            capture_id=capture_id,
            created_at=utc_now_iso(),
            inspection_point=inspection_point,
            source=source,
            backend=self._backend.name,
            inference_ms=inference_ms,
            image_width=int(image.shape[1]),
            image_height=int(image.shape[0]),
            detections=detections,
            display_names=self._display_names,
        )

        paths = {'image_path': '', 'annotated_path': ''}
        if archive:
            paths = self._archive.save(
                capture_id, original_bytes, annotated_bytes, result)
        result['image_path'] = paths['image_path']
        result['annotated_path'] = paths['annotated_path']
        return True, (
            f'Capture archived: {capture_id} / 抓拍已归档：{capture_id}'
            if archive else
            f'Capture completed without archive: {capture_id} / 抓拍完成但未归档：{capture_id}'
        ), (result, detections, frame)

    def _header_for(self, frame: dict) -> Header:
        """Build a message header that preserves the source frame stamp.
        构建保留源帧时间戳的消息头。
        """
        header = Header()
        if frame['stamp_ns'] > 0:
            header.stamp.sec = int(frame['stamp_ns'] // 1_000_000_000)
            header.stamp.nanosec = int(frame['stamp_ns'] % 1_000_000_000)
        else:
            header.stamp = self.get_clock().now().to_msg()
        header.frame_id = frame['frame_id']
        return header

    def _to_defect_array(self, result: dict, frame: dict) -> DefectArray:
        """Convert a result dictionary into the typed ROS message.
        将结果字典转换为类型化 ROS 消息。
        """
        message = DefectArray()
        message.header = self._header_for(frame)
        message.capture_id = result['capture_id']
        message.inspection_point = result['inspection_point']
        message.source = result['source']
        message.image_path = result['image_path']
        message.annotated_path = result['annotated_path']
        message.inference_ms = float(result['inference_ms'])
        for item in result['defects']:
            detection = DefectDetection()
            detection.label = str(item['label'])
            detection.confidence = float(item['confidence'])
            detection.x_min = float(item['bbox'][0])
            detection.y_min = float(item['bbox'][1])
            detection.x_max = float(item['bbox'][2])
            detection.y_max = float(item['bbox'][3])
            message.detections.append(detection)
        return message

    def _publish_alert(self, result: dict, frame: dict) -> None:
        """Publish the lightweight alert frame for gateway subscribers.
        向网关订阅者发布轻量告警帧。
        """
        alert = InspectionAlert()
        alert.header = self._header_for(frame)
        alert.capture_id = result['capture_id']
        alert.inspection_point = result['inspection_point']
        alert.severity = result['summary']['severity']
        alert.defect_count = int(result['summary']['defect_count'])
        alert.summary_json = json.dumps(result['summary'], ensure_ascii=False)
        self._alert_publisher.publish(alert)

    def _on_capture(self, request, response):
        """Handle the /inspection/capture service request.
        处理 /inspection/capture 服务请求。
        """
        ok, message, payload = self._run_capture(
            inspection_point=str(request.inspection_point).strip(),
            source=str(request.source).strip() or 'manual',
            archive=bool(request.archive),
        )
        response.success = bool(ok)
        response.message = message
        if ok:
            result, detections, frame = payload
            response.capture_id = result['capture_id']
            response.image_path = result['image_path']
            response.annotated_path = result['annotated_path']
            response.result_json = json.dumps(result, ensure_ascii=False)
            response.defects = self._to_defect_array(result, frame)
            self._defect_publisher.publish(response.defects)
            self._publish_alert(result, frame)
        return response

    def _on_auto_capture(self) -> None:
        """Run one periodic patrol capture while ignoring in-flight failures.
        执行一次周期性巡逻抓拍，并忽略进行中的失败。
        """
        ok, message, payload = self._run_capture('', 'patrol', True)
        if ok:
            result, detections, frame = payload
            self._defect_publisher.publish(self._to_defect_array(result, frame))
            self._publish_alert(result, frame)
            self.get_logger().info(message)
        else:
            self.get_logger().warning(message)

    def destroy_node(self):
        """Release backend resources before destroying the node.
        在销毁节点前释放后端资源。
        """
        self._backend.release()
        return super().destroy_node()


def main(args=None):
    """Initialise ROS 2 and spin the inspection node.
    初始化 ROS 2 并运行巡检节点。
    """
    rclpy.init(args=args)
    node = None
    try:
        node = InspectionVisionNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()
