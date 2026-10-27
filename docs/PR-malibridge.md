# Pull request text for ASEbrahim/MaliBridge (branch `rp4pro-fixes`)

**Title:** server: Mali-G77 r32p1 (Retroid Pocket 4 Pro) - mutable-format queries, AHB twins, linear tiling, nan_position

## Device

Retroid Pocket 4 Pro: MediaTek Dimensity 1100, Mali-G77 MC9, Android 13, kernel 4.19.191, Arm driver
`v1.r32p1-01eac0`, Vulkan 1.1.177, no `/dev/dma_heap`. Memory sharing lands on the AHardwareBuffer strategy
(type 1, uncached pages, coherent in practice).

## Commits

1. **mutable-format query retry** (`server_opaque.c`). r32p1 answers `VK_ERROR_FORMAT_NOT_SUPPORTED` to
   `vkGetPhysicalDeviceImageFormatProperties2` for a dma-buf image at DRM-modifier tiling whenever
   `VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT` is set, with or without a format list. gamescope sets the flag on every
   flippable image (its sRGB twin), skipped every modifier and died on `assert(modifiers.size() > 0)`. The same
   image creates fine with the flag, exports, and takes an sRGB view. A refused query with the flag is asked
   again without the flag and the list, and that answer returned. Proven with a ctypes probe inside the rootfs.
2. **AHB twin images; linear tiling hidden** (`server_emu_layer.c`, `server_memory.c`). r32p1 crashes inside
   `vkGetImageSubresourceLayout` on an AHB-external image with no memory bound (one such query took the live
   server down), and `vkGetImageMemoryRequirements` on it is undefined (VUID 04004): a plain twin of every
   AHB-external image answers requirements and layouts. Images bound to BLOB AHardwareBuffers read back with
   `rowPitch 0`, so Zink's linear staging went wrong: under the `ahb` strategy `linearTilingFeatures` is
   reported 0 for every format and Zink stages through buffers (`VKBRIDGE_AHB_LINEAR=1` turns the hiding off).
   Verified byte-exact with readback, blit, linear and export probes.
3. **Env-file switches and driver-module substitution** (`server_memory.c`, `server_emu_shader.c`).
   `VKBRIDGE_AHB_RARELY` from the env file; `VKBRIDGE_SPIRV_SUBST=1` also replaces the module the driver
   gets (after the bridge's rewrites) by `<cache dir>/spv-subst/<fnv1a>.spv`, the hash the profiler's
   `dump-spirv` files carry. This is what made the shader bisection below possible; it is off unless asked for.
4. **nan_position (MK-45)** (`spirv_nanpos.[ch]`, `server_errata_nanpos.c`, table entries). Ys Origin keeps its
   dead particles in the draw list with NaN world matrices (154 of the 208 sprite draws in one apitrace frame).
   A PC drops those primitives; r32p1 draws each as a sheet over the whole render target, so every room with
   effects was white at 12 fps. The erratum rewrites every vertex shader on its way to the driver: before each
   return of the entry point, a position with a NaN or Inf component (tested on the bits with scalar integer
   ops, so no fast-math folds it) or a zero w becomes (2, 2, 2, 1), outside the clip volume. Gated on r32
   drivers (`G_IN_RANGE`, both modes) until a probe tells more; `VKBRIDGE_ERRATA=-nan_position` turns it off.
   The output is a pure function of the input, so the pipeline cache keeps its entries. A NaN fed straight in
   as a vertex attribute *is* dropped by this driver, so the fault is in the arithmetic path; a startup probe
   would need a NaN matrix in a UBO. Verified: the room renders correctly at 60-69 fps.

## Not changed

The emulation set is read at server start (an env-file switch like `VKBRIDGE_EMU_DIVISOR=0` stays until the
app process restarts); this cost a morning and may be worth a note in the docs.

## Evidence

Screenshots, the apitrace replay script (`tools/ys_replay.py`) and the probes (`tools/vkstrip.py`,
`tools/vkalpha.py`, `tools/vkcoh.py`, `tools/vkspec.py`) are in the release repository.

Tested by yujikaido (the PR author) on their own Retroid Pocket 4 Pro; investigation and patches written with Claude Code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
