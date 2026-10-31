# RP4 Pro DroidDeck 源码（fix51 + 本地改动 + 内置 PanVK）

Retroid Pocket 4 Pro 上 DroidDeck 的源码，用于构建自签名的独立版本。
基线是 [yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro) 的 `source` 分支
（fix51，`4ff63195`），上面叠加了本项目的合成器修复、PanVK 安装即用配置和通用 D3D12 改进。
当前版本为 [v0.5.1](https://github.com/kb7b8z5k9d-creator/rp4test/releases/tag/v0.5.1)，本机用户已确认可用。
**首次使用仍需手动开启 Mali Bridge，并下载、安装 Linux 运行时（支持包）。** 完整步骤见[发布仓库 README](https://github.com/kb7b8z5k9d-creator/rp4test#新手首次安装)。

- 设备：Retroid Pocket 4 Pro（Mali-G77 MC9，Android 13，1334×750）
- 图形桥：[ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge) v0.5.4.2（fix51 已含）
- 发布仓库（README、补丁、APK）：[kb7b8z5k9d-creator/rp4test](https://github.com/kb7b8z5k9d-creator/rp4test)

## 本地改动

首次安装：打开 **配置 → 概览**，把 **“Mali 桥接：关闭”** 切换为 **“Mali 桥接：开启”**，再点击 **“Linux 运行时 → 安装”**，等待下载、解压完成。玩 Steam 不需要另外安装 Linux 桌面。

之后启动 Steam，等待 Proton Experimental (ARM64) 下载及“准备游戏组件”完成，再登录账号。PanVK 与 VKD3D 已内置，不需要另外找 ZIP 或替换游戏 DLL，也不需要为启用 VKD3D 额外重开应用。图形模式可在配置的组件页检查；帧生成默认关闭，需要时自行开启。

APK SHA-256：`597cb6a1d8c65d978c3bf6ce0f0746db0e3b0c50772508ee39b95e71c0938890`。

- **PanVK 默认配置**：APK 内置 faux123 PanVK v1.1.3（`assets/panvk/`）和 VKD3D readback 回退组件（`assets/vkd3d/`）。v0.5.1 在支持的 RP4 Pro 上先安装 Proton Experimental (ARM64)，再核验并安装组件，最后启动 Steam，无需额外重启应用。资源经 SHA-256 校验后原子安装；已有驱动、菜单和组件选择得到保留。Proton 更新或重装后重新核对，玩家主动恢复原版则停止自动应用。
- **玩家版运行路径**：Release APK 不可调试、不打包 Vulkan smoke 测试程序；启动时不运行 smoke 或 vulkaninfo，不读取旧 `.vkbridge-env` 测试开关，关闭桥接逐秒帧统计写盘。保留带缓存的驱动兼容性检测和正常错误日志。电脑上的开发测试不打入 APK。
- **通用 DX12 兼容改进**：按实际选中驱动的能力报告选择 DXVK，避免将系统 Mali 的 Vulkan 1.1 误当成 PanVK 的能力；VKD3D-Proton 回退组件已内置，允许缺少 HOST_CACHED 类型时回退到真实可用的 HOST_VISIBLE 内存。组件源码补丁和打包说明见 [`tools/vkd3d`](tools/vkd3d/README.md)。
- **合成器显示层**：窗口与场景容差 ±16 px、源矩形 ±2 px（1151×647 vs 1152×648）、按窗口实际矩形映射、
  忽略 ≤64×64 的触摸光标窗口。
- **zero-copy 默认开启**（不只在 HDR 时）。
- **签名与包名**：`com.rp4pro.droiddeck.lab`，`CN=RP4Pro Lab`；密钥不在仓库里。
- **构建/工具**：proot fastpath（含 svc 头）、7zip 26.05、comet 容器内 `safe.directory`。

## 构建

Windows + WSL2 Ubuntu 24.04 + Docker（`droiddeck-local-cross:24.04-v3`），NDK 27.3.13750724、JDK 17。
入口 `tools/build_local.sh`；构建脚本在 `tools/` 下。需要自备 Android SDK 与签名密钥。
玩家 APK 使用 `DROIDDECK_BUILD_VARIANT=release`；开发调试与回归测试在电脑上单独运行。

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

# RP4 Pro DroidDeck source (fix51 + local changes + bundled PanVK)

Source for the DroidDeck build on the Retroid Pocket 4 Pro, used to build a self-signed, independent
package. The base is the `source` branch of
[yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro) (fix51, `4ff63195`),
with this project's compositor fixes, the install-and-play PanVK setup and general D3D12 improvements
on top. The current version is [v0.5.1](https://github.com/kb7b8z5k9d-creator/rp4test/releases/tag/v0.5.1), confirmed usable by the RP4 Pro owner.
**First-time users still need to enable the Mali bridge and download/install the Linux runtime support package manually.** See the [release repository guide](https://github.com/kb7b8z5k9d-creator/rp4test#first-time-setup).

- Device: Retroid Pocket 4 Pro (Mali-G77 MC9, Android 13, 1334×750)
- Graphics bridge: [ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge) v0.5.4.2 (already in fix51)
- Release repository (README, patch, APK): [kb7b8z5k9d-creator/rp4test](https://github.com/kb7b8z5k9d-creator/rp4test)

## Local changes

First install: open **Setup → Overview**, change **“Mali bridge: off”** to **“Mali bridge: on”**, then tap **“Install”** beside **“Linux runtime”** and wait for download/extraction. Steam does not require the separate Linux desktop.

Start Steam, wait for Proton Experimental (ARM64) and “Preparing game components”, then sign in. PanVK and VKD3D are bundled, with no separate ZIP or game-local DLL replacement needed, and no additional app restart to activate VKD3D. Check graphics mode on the Components page. Frame generation defaults to off; enable it yourself if desired.

APK SHA-256: `597cb6a1d8c65d978c3bf6ce0f0746db0e3b0c50772508ee39b95e71c0938890`.

- **Default PanVK profile:** the APK bundles faux123's PanVK v1.1.3 (`assets/panvk/`) and the VKD3D readback fallback (`assets/vkd3d/`). On supported RP4 Pro devices, v0.5.1 installs Proton Experimental (ARM64), verifies and prepares its component, then starts Steam without another app restart. Assets are verified with SHA-256 and installed atomically. Existing driver, menu and component choices are preserved; Proton updates and reinstalls trigger a new check, while explicitly restoring the original component opts out.
- **Player runtime:** release APKs are not debuggable and exclude the Vulkan smoke binary. Startup does not run smoke or vulkaninfo, does not read the legacy `.vkbridge-env` switches, and disables per-second bridge frame-statistics writes. Cached driver compatibility checks and normal error logs remain. Computer-side development tests are not packaged in the APK.
- **General D3D12 compatibility improvements:** DXVK selection uses the selected driver's actual capabilities instead of confusing system Mali Vulkan 1.1 with PanVK. The VKD3D-Proton fallback component is bundled and falls back to a real HOST_VISIBLE memory type when HOST_CACHED is unavailable. The source patch and packaging notes are in [`tools/vkd3d`](tools/vkd3d/README.md).
- **Compositor display layer**: window/scene tolerance ±16 px, source rectangle ±2 px
  (1151×647 against 1152×648), mapping onto the window's actual rectangle, and ignoring touch-cursor
  windows of 64×64 or less.
- **Zero-copy on by default** (not only when HDR is on).
- **Signature and package name**: `com.rp4pro.droiddeck.lab`, `CN=RP4Pro Lab`; the key is not in this
  repository.
- **Build/tooling**: proot fast path (including the svc headers), 7zip 26.05, and `safe.directory` for comet inside the container.

## Build

Windows + WSL2 Ubuntu 24.04 + Docker (`droiddeck-local-cross:24.04-v3`), NDK 27.3.13750724, JDK 17.
The entry point is `tools/build_local.sh`; the build scripts live under `tools/`. Bring your own
Android SDK and signing key.
Set `DROIDDECK_BUILD_VARIANT=release` for a player APK; development tests run separately on the computer.

## Known issues

- Little Nightmares Enhanced reached gameplay using D3D12 on RP4 Pro / PanVK / Proton Experimental (ARM64), with normal graphics but very low frame rates; performance has not been optimized. ForestTD's default D3D12 renderer was playable on an earlier build; other Proton versions and 32-bit components are unverified.
- Prison Architect ground-texture flicker (Mesa zink texture/mipmap path).
- Crimsonland Chinese text offset (not scaling, not DXVK, not system fonts; cause not yet found).

## Upstream

- [Droid-Deck/DroidDeck](https://github.com/Droid-Deck/DroidDeck)
- [ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge)
- [yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro)
- [The412Banner/droiddeck-nonadreno-drivers](https://github.com/The412Banner/droiddeck-nonadreno-drivers)
