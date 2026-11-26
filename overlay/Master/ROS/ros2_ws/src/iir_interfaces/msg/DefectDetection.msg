# One power-equipment defect detection in original image pixel coordinates.
# 原始图像像素坐标系中的单个电力设备缺陷检测结果。
# Stable English label key, for example insulator_defect.
# 稳定的英文标签键，例如 insulator_defect。
string label
# Detection confidence in the inclusive range [0.0, 1.0].
# 检测置信度，取值范围为闭区间 [0.0, 1.0]。
float32 confidence
# Left edge of the bounding box in pixels.
# 检测框左边缘的像素坐标。
float32 x_min
# Top edge of the bounding box in pixels.
# 检测框上边缘的像素坐标。
float32 y_min
# Right edge of the bounding box in pixels.
# 检测框右边缘的像素坐标。
float32 x_max
# Bottom edge of the bounding box in pixels.
# 检测框下边缘的像素坐标。
float32 y_max
