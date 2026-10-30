# RP4 Pro DroidDeck 源码（fix51 + 本地改动）

Retroid Pocket 4 Pro 上 DroidDeck 的源码，用于构建自签名的独立版本。
基线是 [yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro) 的 `source` 分支
（fix51，`4ff63195`），上面叠加了本项目的合成器修复。

- 设备：Retroid Pocket 4 Pro（Mali-G77 MC9，Android 13，1334×750）
- 图形桥：[ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge) v0.5.4.2（fix51 已含）
- 发布仓库（README、补丁、APK）：[kb7b8z5k9d-creator/rp4test](https://github.com/kb7b8z5k9d-creator/rp4test)

## 本地改动

- **PanVK 初步接入（实验性）**：支持导入 PanVK 驱动、一键切换及直接加载 ICD；当驱动宣称支持 dma-buf 导出但实际导出失败时，自动检测并使用已有的兼容回退。已在 RP4 Pro 上验证 Steam 启动，以及 ForestTD 使用 Vulkan / Forward Mobile 进入游戏。PanVK 驱动需另行获取并导入，未打包在 APK 中。
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

- PanVK 下 ForestTD 默认 D3D12 路径仍闪退，VKD3D 报找不到合适的 CPU 可访问内存类型；小小梦魇增强版提示渲染资源显存不足，原因尚未确认。Vulkan 对照使用 Steam 启动参数 `%command% --rendering-method mobile --rendering-driver vulkan`，不代表其他游戏均兼容。
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

- **Initial PanVK integration (experimental):** import and switch to a PanVK driver, load its ICD directly, and automatically probe and use the existing dma-buf export fallback when a claimed native export fails. Steam startup and ForestTD's Vulkan / Forward Mobile renderer were tested on RP4 Pro. The PanVK driver is distributed separately and must be imported; it is not bundled in the APK.
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

- With PanVK, ForestTD's default D3D12 renderer still crashes with a VKD3D CPU-visible memory-type error; Little Nightmares Enhanced reports insufficient graphics memory, with the cause still unconfirmed. The Vulkan control used the Steam launch option `%command% --rendering-method mobile --rendering-driver vulkan`; other games have not been established as compatible.
- Prison Architect ground-texture flicker (Mesa zink texture/mipmap path).
- Crimsonland Chinese text offset (not scaling, not DXVK, not system fonts; cause not yet found).

## Upstream

- [Droid-Deck/DroidDeck](https://github.com/Droid-Deck/DroidDeck)
- [ASEbrahim/MaliBridge](https://github.com/ASEbrahim/MaliBridge)
- [yujikaido/droiddeck-rp4pro](https://github.com/yujikaido/droiddeck-rp4pro)
- [The412Banner/droiddeck-nonadreno-drivers](https://github.com/The412Banner/droiddeck-nonadreno-drivers)
