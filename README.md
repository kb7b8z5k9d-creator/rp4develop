# RP4 Pro DroidDeck 源码（fix51 + 本地改动）

Retroid Pocket 4 Pro 上 DroidDeck 的源码，用于构建自签名的独立版本。
基线是 [yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro) 的 `source` 分支
（fix51，`4ff63195`），上面叠加了本项目的合成器修复。

- 设备：Retroid Pocket 4 Pro（Mali-G77 MC9，Android 13，1334×750）
- 图形桥：[ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge) v0.5.4.2（fix51 已含）
- 发布仓库（README、补丁、APK）：[kb7b8z5k9d-creator/rp4test](https://github.com/kb7b8z5k9d-creator/rp4test)

## 本地改动

- **PanVK 安装即用版（默认）**：APK 内置 faux123 PanVK v1.1.3（`assets/panvk/`）和 VKD3D readback 回退组件（`assets/vkd3d/`）。`BuiltinProfile` 仅在 MT8797 / Retroid 设备首次启动时复制驱动，设 `androidDriver` / `gpuDriverMode=manual` / `vkBridge=true` / `steamMenus=gpu`，并在 Proton Experimental 存在且未运行时自动选中 VKD3D。组件页首层“图形模式”可切回系统 Mali；Mali 帧率高、现有游戏最稳，PanVK 对 Vulkan 1.3 / D3D12 等新特性兼容性更强但帧率低。
- **通用 DX12 兼容改进**：按实际选中驱动的能力报告选择 DXVK，避免将系统 Mali 的 Vulkan 1.1 误当成 PanVK 的能力；VKD3D-Proton 回退组件已内置，允许缺少 HOST_CACHED 类型时回退到真实可用的 HOST_VISIBLE 内存。组件源码补丁和打包说明见 [`tools/vkd3d`](tools/vkd3d/README.md)。
- **合成器显示层**：窗口与场景容差 ±16 px、源矩形 ±2 px（1151×647 vs 1152×648）、按窗口实际矩形映射、
  忽略 ≤64×64 的触摸光标窗口。
- **zero-copy 默认开启**（不只在 HDR 时）。
- **签名与包名**：`com.rp4pro.droiddeck.lab`，`CN=RP4Pro Lab`；密钥不在仓库里。
- **构建/工具**：proot fastpath（含 svc 头）、7zip 26.05、comet 容器内 `safe.directory`、
  `droiddeck-session` 的 `BL_GAMESCOPE_ARGS` 调试入口。

## 构建

Windows + WSL2 Ubuntu 24.04 + Docker（`droiddeck-local-cross:24.04-v3`），NDK 27.3.13750724、JDK 17。
入口 `tools/build_local.sh`；构建脚本在 `tools/` 下。需要自备 Android SDK 与签名密钥。

## 已知问题

- 在 RP4 Pro / PanVK / Proton Experimental (ARM64) 上，小小梦魇增强版已能以 D3D12 进入游戏，画面正常但帧率很低，尚未进行性能优化。ForestTD 默认 D3D12 在较早的构建上验证可玩；其他 Proton 版本和 32 位组件尚未验证。
- Prison Architect 地面贴图闪烁（Mesa zink 的纹理/mipmap 路径）。
- Crimsonland 中文文字偏移（非缩放、非 DXVK、非系统字体，原因未定位）。

## 上游

- [Droid-Deck/DroidDeck](https://github.com/Droid-Deck/DroidDeck)
- [ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge)
- [yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro)
- [The412Banner/droiddeck-nonadreno-drivers](https://github.com/The412Banner/droiddeck-nonadreno-drivers)

---

# RP4 Pro DroidDeck source (fix51 + local changes)

Source for the DroidDeck build on the Retroid Pocket 4 Pro, used to build a self-signed, independent
package. The base is the `source` branch of
[yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro) (fix51, `4ff63195`),
with this project's compositor fixes on top.

- Device: Retroid Pocket 4 Pro (Mali-G77 MC9, Android 13, 1334×750)
- Graphics bridge: [ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge) v0.5.4.2 (already in fix51)
- Release repository (README, patch, APK): [kb7b8z5k9d-creator/rp4test](https://github.com/kb7b8z5k9d-creator/rp4test)

## Local changes

- **Install-and-play PanVK build (default):** the APK bundles faux123's PanVK v1.1.3 (`assets/panvk/`) and the VKD3D readback fallback (`assets/vkd3d/`). `BuiltinProfile` copies the driver only on MT8797 / Retroid devices, sets `androidDriver` / `gpuDriverMode=manual` / `vkBridge=true` / `steamMenus=gpu`, and selects the VKD3D component once Proton Experimental exists and is not in use. The Components page has a top-level "Graphics mode" switch back to system Mali; Mali has the higher frame rate and is the most stable for existing games, while PanVK is stronger for Vulkan 1.3 / D3D12 and other new features at a lower frame rate.
- **General D3D12 compatibility improvements:** DXVK selection uses the selected driver's actual capabilities instead of confusing system Mali Vulkan 1.1 with PanVK. The VKD3D-Proton fallback component is bundled and falls back to a real HOST_VISIBLE memory type when HOST_CACHED is unavailable. The source patch and packaging notes are in [`tools/vkd3d`](tools/vkd3d/README.md).
- **Compositor display layer**: window/scene tolerance ±16 px, source rectangle ±2 px
  (1151×647 against 1152×648), mapping onto the window's actual rectangle, and ignoring touch-cursor
  windows of 64×64 or less.
- **Zero-copy on by default** (not only when HDR is on).
- **Signature and package name**: `com.rp4pro.droiddeck.lab`, `CN=RP4Pro Lab`; the key is not in this
  repository.
- **Build/tooling**: proot fast path (including the svc headers), 7zip 26.05, `safe.directory` for
  comet inside the container, and the `BL_GAMESCOPE_ARGS` debug switch in `droiddeck-session`.

## Build

Windows + WSL2 Ubuntu 24.04 + Docker (`droiddeck-local-cross:24.04-v3`), NDK 27.3.13750724, JDK 17.
The entry point is `tools/build_local.sh`; the build scripts live under `tools/`. Bring your own
Android SDK and signing key.

## Known issues

- Little Nightmares Enhanced reached gameplay using D3D12 on RP4 Pro / PanVK / Proton Experimental (ARM64), with normal graphics but very low frame rates; performance has not been optimized. ForestTD's default D3D12 renderer was playable on an earlier build; other Proton versions and 32-bit components are unverified.
- Prison Architect ground-texture flicker (Mesa zink texture/mipmap path).
- Crimsonland Chinese text offset (not scaling, not DXVK, not system fonts; cause not yet found).

## Upstream

- [Droid-Deck/DroidDeck](https://github.com/Droid-Deck/DroidDeck)
- [ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge)
- [yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro)
- [The412Banner/droiddeck-nonadreno-drivers](https://github.com/The412Banner/droiddeck-nonadreno-drivers)
