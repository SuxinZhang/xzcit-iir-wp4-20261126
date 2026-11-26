# XZCIT-IIR WP4：RKNN 视觉识别、Gateway 与 Web-Next / 学生端

本仓库是 WP4 的**独立 overlay 仓库**，包含：

- `overlay/Master/ROS/ros2_ws/src/iir_interfaces/`
- `overlay/Master/ROS/ros2_ws/src/iir_vision_rknn/`
- `overlay/Master/Gateway/`
- `overlay/Master/Web-Next/` 中的 WP4 页面、脚本、样式与路由文件
- `overlay/.github/workflows/ci.yml`：WP4 版本的 CI（含 Gateway job）
- `docs/`：两版任务书、WP1–WP5 对照清单、WP5 接口说明（供交叉参考）

## 为什么单独建仓库

WP4 与 WP1–WP3 基础工程分仓，原因：

1. **硬件/运行时完全不同**：WP4 需要 RK3588S NPU、`rknn-toolkit-lite2`、OpenCV、Python FastAPI 与 Web-Next 前端；基础工程是 STM32 HAL/FreeRTOS + ROS 2 导航，不应被 NPU/Python/前端依赖污染。
2. **模型与 Web 迭代节奏不同**：缺陷模型、标签表、阈值、Gateway API、管理端/学生端页面会独立频繁迭代；与固件/导航解耦后可以单独发布、回滚，不必每次重烧固件。
3. **验收条件不同**：WP4 的核心验收是 `.rknn` 模型、≥15 FPS、CPU <30%、抓拍后 2 秒内管理端/学生端可见；这些都需要独立的目标机和浏览器环境，与 WP1–WP3 的烧录/传感器/回充验收分开。
4. **依赖方向清晰**：WP4 依赖 WP1–WP3 提供的 `/image_raw/compressed` 单相机流和 Web-Next 基线；WP5 又依赖 WP4 的登录会话/告警/媒体入口。用 overlay 仓库可以显式表达依赖，而不把代码复制成多份。

## 如何与基础工程组合

本仓库**不是独立可运行工程**，需要先准备 WP1–WP3 基础工程，再应用本仓库 `overlay/`：

```bash
# 假设 base 是 WP1–WP3 基础工程根目录
rsync -a overlay/ "$BASE"/
```

- 新增目录：`iir_interfaces`、`iir_vision_rknn`、`Master/Gateway`
- 新增页面：`inspection.js`、`student.js`、`student.html`、`inspection.css`、`student.css`
- 覆盖文件：`Master/Web-Next/src/main.rs`、`web/index.html`、`web/js/app.js`、`web/js/ws.js`、`.github/workflows/ci.yml`

> 覆盖的 Web-Next 文件基于 WP1–WP3 基线；若基础工程已合入 WP5，请用三方合并而不是直接覆盖，避免丢失 interaction 改动。

## 关键设计边界

- `iir_vision_rknn` 只订阅 `/image_raw/compressed`，不打开 `/dev/video*`，遵循单相机采集源唯一红线。
- `Master/Gateway` 只负责巡检业务（抓拍、缺陷、历史、媒体），底座控制/巡逻仍由现有 Web-Next Rust Axum `/ws` 承载，避免出现第二个控制发布者。
- `web_debug.py` 不修改，仍作为底层调试入口。
- 学生端路由为 `/student`，移动端响应式 H5；管理端巡检页为 `#/inspection`。

## 本地验证摘要

| 检查 | 结果 |
| :--- | :--- |
| `Master/Gateway` pytest | 7/7 |
| `iir_vision_rknn` pytest | 14 通过，1 跳过（本机无 OpenCV） |
| Web-Next Rust 测试 | 49/49（串行） |
| `cargo fmt --check` / `cargo clippy` | 通过 / 退出码 0 |
| 全部 JS `node --check` | 通过 |
| 静态资源注册检查 | 通过 |
| Web-Next fake 冒烟 `/`、`/student`、JS/CSS、`/api/state` | 全 200 |
| Gateway fake 冒烟抓拍/媒体/历史 | 通过 |

## 上机前必读

`docs/WP1-WP5_任务书对照与上机验证清单.md` 的 WP4 条目仍未完成，重点：

- 真实 `.rknn` 模型与标签文件（当前仅有 mock 测试后端）
- RK3588S NPU 驱动、`rknn-toolkit-lite2`
- 实际 `/inspection/capture` ROS 服务、归档目录、摄像头帧
- ≥15 FPS、CPU <30%、抓拍后 2 秒管理端/`/student` 可见

> 本仓库是本地快照/overlay，不是原仓库，也未向原仓库推送。
