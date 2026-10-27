#!/usr/bin/env python3
"""GPU reads from a shared (dma-buf exported, AHardwareBuffer-backed) DRM-modifier image through the
Mali bridge: the kind gamescope's output and a game's swapchain images are. A row-varying pattern
is copied INTO it from a buffer, then read OUT via vkCmdCopyImageToBuffer and via a blit into an
optimal image, byte-exact. Run against a PRIVATE server."""
import ctypes as C
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vkreadback as R  # noqa: E402

u32, u64, ptr, f32 = C.c_uint32, C.c_uint64, C.c_void_p, C.c_float
ExtMemImageCI = R.struct("ExtMemImageCI", [("sType", u32), ("pNext", ptr), ("handleTypes", u32)])
DrmModListCI = R.struct("DrmModListCI", [("sType", u32), ("pNext", ptr), ("count", u32), ("pModifiers", C.POINTER(u64))])
ExportMemAllocInfo = R.struct("ExportMemAllocInfo", [("sType", u32), ("pNext", ptr), ("handleTypes", u32)])
DedicatedAllocInfo = R.struct("DedicatedAllocInfo", [("sType", u32), ("pNext", ptr), ("image", u64), ("buffer", u64)])
ImgBlit = R.struct("ImgBlit", [("srcSubresource", R.ImgSubLayers), ("srcOffsets", R.Offset3D * 2), ("dstSubresource", R.ImgSubLayers),
                               ("dstOffsets", R.Offset3D * 2)])
ImgCopy = R.struct("ImgCopy", [("srcSubresource", R.ImgSubLayers), ("srcOffset", R.Offset3D), ("dstSubresource", R.ImgSubLayers),
                               ("dstOffset", R.Offset3D), ("extent", R.Extent3D)])


def main():
    VK = R.VK
    app = R.AppInfo(0, None, b"yso_win.exe", 0, b"DXVK", 4235267, (1 << 22) | (1 << 12))
    iexts = (C.c_char_p * 1)(b"VK_KHR_get_physical_device_properties2")
    ici = R.InstanceCI(1, None, 0, C.pointer(app), 0, None, 1, iexts)
    inst = ptr()
    VK.vkCreateInstance.restype = C.c_int
    VK.vkCreateInstance(C.byref(ici), None, C.byref(inst))
    gipa = VK.vkGetInstanceProcAddr
    gipa.restype = ptr

    def fn(name, restype=C.c_int):
        return C.CFUNCTYPE(restype)(gipa(inst, name.encode()))

    enum = fn("vkEnumeratePhysicalDevices")
    n = u32(0); enum(inst, C.byref(n), None)
    pds = (ptr * max(n.value, 1))(); enum(inst, C.byref(n), pds)
    pd = C.c_void_p(pds[0])
    mp = R.MemProps(); fn("vkGetPhysicalDeviceMemoryProperties", None)(pd, C.byref(mp))
    types = [(i, mp.memoryTypes[i].propertyFlags) for i in range(mp.memoryTypeCount)]
    host_type = [i for i, f in types if f & 0x2][0]
    dexts = [b"VK_EXT_image_drm_format_modifier", b"VK_KHR_external_memory", b"VK_KHR_external_memory_fd", b"VK_EXT_external_memory_dma_buf",
             b"VK_KHR_dedicated_allocation", b"VK_KHR_get_memory_requirements2", b"VK_KHR_bind_memory2", b"VK_KHR_sampler_ycbcr_conversion",
             b"VK_KHR_image_format_list", b"VK_KHR_maintenance1"]
    dext_arr = (C.c_char_p * len(dexts))(*dexts)
    prio = (f32 * 1)(1.0)
    qci = R.QueueCI(2, None, 0, 0, 1, prio)
    dci = R.DeviceCI(3, None, 0, 1, C.pointer(qci), 0, None, len(dexts), dext_arr, None)
    dev = ptr()
    print("vkCreateDevice ->", fn("vkCreateDevice")(pd, C.byref(dci), None, C.byref(dev)))
    gdpa = C.CFUNCTYPE(ptr)(gipa(inst, b"vkGetDeviceProcAddr"))

    def dfn(name, restype=C.c_int):
        return C.CFUNCTYPE(restype)(gdpa(dev, name.encode()))

    q = ptr(); dfn("vkGetDeviceQueue", None)(dev, 0, 0, C.byref(q))
    create_image, create_buffer = dfn("vkCreateImage"), dfn("vkCreateBuffer")
    get_ireq, get_breq = dfn("vkGetImageMemoryRequirements", None), dfn("vkGetBufferMemoryRequirements", None)
    alloc, bind_i, bind_b = dfn("vkAllocateMemory"), dfn("vkBindImageMemory"), dfn("vkBindBufferMemory")
    map_mem, unmap = dfn("vkMapMemory"), dfn("vkUnmapMemory", None)
    cpool = u64(0); dfn("vkCreateCommandPool")(dev, C.byref(R.CmdPoolCI(39, None, 2, 0)), None, C.byref(cpool))
    cb = u64(0); dfn("vkAllocateCommandBuffers")(dev, C.byref(R.CmdBufAI(40, None, cpool.value, 0, 1)), C.byref(cb))
    begin, end = dfn("vkBeginCommandBuffer"), dfn("vkEndCommandBuffer")
    barrier = dfn("vkCmdPipelineBarrier", None)
    copy_b2i, copy_i2b, copy_i2i, blit = dfn("vkCmdCopyBufferToImage", None), dfn("vkCmdCopyImageToBuffer", None), dfn("vkCmdCopyImage", None), dfn("vkCmdBlitImage", None)
    submit, create_fence, wait_fence, reset_fence = dfn("vkQueueSubmit"), dfn("vkCreateFence"), dfn("vkWaitForFences"), dfn("vkResetFences")
    fence = u64(0); create_fence(dev, C.byref(R.FenceCI(8, None, 0)), None, C.byref(fence))

    def run(record):
        begin(cb, C.byref(R.CmdBufBI(42, None, 1, None))); record(); end(cb)
        cbs = (u64 * 1)(cb.value)
        si = R.SubmitInfo(4, None, 0, None, None, 1, cbs, 0, None)
        reset_fence(dev, 1, C.byref(fence))
        rs = submit(q, 1, C.byref(si), fence)
        t = time.time()
        rw = wait_fence(dev, 1, C.byref(fence), 1, u64(10**10))
        return rs, rw, round((time.time() - t) * 1000)

    def img_barrier(img, old, new, src, dst):
        b = R.ImgMemBarrier(45, None, src, dst, old, new, 0xFFFFFFFF, 0xFFFFFFFF, img.value, R.ImgSubRange(1, 0, 1, 0, 1))
        barrier(cb, 0x10000, 0x10000, 0, 0, None, 0, None, 1, C.byref(b))

    def make_buffer(size, usage):
        buf = u64(0)
        create_buffer(dev, C.byref(R.BufferCI(12, None, 0, size, usage, 0, 0, None)), None, C.byref(buf))
        rq = R.MemReqs(); get_breq(dev, buf, C.byref(rq))
        mem = u64(0); alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, host_type)), None, C.byref(mem)); bind_b(dev, buf, mem, u64(0))
        return buf, mem

    W, H = int(os.environ.get("VKE_W", "1280")), int(os.environ.get("VKE_H", "720"))
    FMT = int(os.environ.get("VKE_FMT", "37"))  # R8G8B8A8_UNORM as DXVK's swapchain
    expected = b"".join(bytes([x & 255, y & 255, 7, 255]) for y in range(H) for x in range(W))

    # the shared image: DRM-modifier tiling (linear modifier), dma-buf external, as gamescope/the WSI make it
    mods = (u64 * 1)(0)
    ml = DrmModListCI(1000158003, None, 1, mods)
    em = ExtMemImageCI(1000072001, C.addressof(ml), 0x200)
    img = u64(0)
    ci = R.ImageCI(14, C.addressof(em), 0, 1, FMT, R.Extent3D(W, H, 1), 1, 1, 1, 1000158000, 0x1 | 0x2 | 0x4 | 0x10, 0, 0, None, 0)
    print("shared DRM-modifier image ->", create_image(dev, C.byref(ci), None, C.byref(img)))
    rq = R.MemReqs(); get_ireq(dev, img, C.byref(rq))
    dai = DedicatedAllocInfo(1000127001, None, img.value, 0)
    exi = ExportMemAllocInfo(1000072002, C.addressof(dai), 0x200)
    mt = [i for i, f in types if (rq.memoryTypeBits >> i) & 1][0]
    mem = u64(0)
    print(f"exportable dedicated alloc (size {rq.size}, type {mt}) ->", alloc(dev, C.byref(R.MemAllocInfo(5, C.addressof(exi), rq.size, mt)), None, C.byref(mem)),
          "bind ->", bind_i(dev, img, mem, u64(0)))

    up, upmem = make_buffer(W * H * 4, 0x1)
    p = ptr(); map_mem(dev, upmem, u64(0), u64(W * H * 4), 0, C.byref(p)); C.memmove(p, expected, len(expected)); unmap(dev, upmem)
    out, outmem = make_buffer(W * H * 4, 0x2)
    dst = u64(0)
    create_image(dev, C.byref(R.ImageCI(14, None, 0, 1, FMT, R.Extent3D(W, H, 1), 1, 1, 1, 0, 0x1 | 0x2 | 0x4, 0, 0, None, 0)), None, C.byref(dst))
    rq2 = R.MemReqs(); get_ireq(dev, dst, C.byref(rq2)); dmem = u64(0)
    alloc(dev, C.byref(R.MemAllocInfo(5, None, rq2.size, [i for i, f in types if (rq2.memoryTypeBits >> i) & 1][0])), None, C.byref(dmem)); bind_i(dev, dst, dmem, u64(0))

    def check(label, data):
        wrong = [y for y in range(H) if data[y * W * 4:(y + 1) * W * 4] != expected[y * W * 4:(y + 1) * W * 4]]
        whites = data.count(b"\xff\xff\xff\xff") * 4 * 100 // len(data)
        print(f"  {label}: rows wrong {len(wrong)}/{H}, white {whites}%" + ("  OK, byte-exact" if not wrong else
              f"  <-- WRONG, first wrong row {wrong[0]} starts {data[wrong[0] * W * 4:wrong[0] * W * 4 + 16].hex()}"))

    # 1. upload into the shared image, read it straight back to a buffer
    def rec1():
        img_barrier(img, 0, 7, 0, 0x1000)
        region = R.BufImgCopy(0, 0, 0, R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
        copy_b2i(cb, up, img, 7, 1, C.byref(region))
        img_barrier(img, 7, 6, 0x1000, 0x800)
        copy_i2b(cb, img, 6, out, 1, C.byref(region))
    print("1 buffer -> shared image -> buffer:", run(rec1))
    map_mem(dev, outmem, u64(0), u64(W * H * 4), 0, C.byref(p)); check("read back", C.string_at(p, W * H * 4)); unmap(dev, outmem)
    # 2. blit the shared image into an optimal image (as DXVK's StretchRect from the back buffer), read that
    def rec2():
        img_barrier(dst, 0, 7, 0, 0x1000)
        bl = ImgBlit(R.ImgSubLayers(1, 0, 0, 1), (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(W, H, 1)),
                     R.ImgSubLayers(1, 0, 0, 1), (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(W, H, 1)))
        blit(cb, img, 6, dst, 7, 1, C.byref(bl), 0)
        img_barrier(dst, 7, 6, 0x1000, 0x800)
        region = R.BufImgCopy(0, 0, 0, R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
        copy_i2b(cb, dst, 6, out, 1, C.byref(region))
    print("2 shared image -> blit -> optimal image -> buffer:", run(rec2))
    map_mem(dev, outmem, u64(0), u64(W * H * 4), 0, C.byref(p)); check("after blit", C.string_at(p, W * H * 4)); unmap(dev, outmem)
    # 3. copy (not blit) the shared image into the optimal image
    def rec3():
        img_barrier(dst, 6, 7, 0x800, 0x1000)
        cp = ImgCopy(R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
        copy_i2i(cb, img, 6, dst, 7, 1, C.byref(cp))
        img_barrier(dst, 7, 6, 0x1000, 0x800)
        region = R.BufImgCopy(0, 0, 0, R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
        copy_i2b(cb, dst, 6, out, 1, C.byref(region))
    print("3 shared image -> copy -> optimal image -> buffer:", run(rec3))
    map_mem(dev, outmem, u64(0), u64(W * H * 4), 0, C.byref(p)); check("after copy", C.string_at(p, W * H * 4)); unmap(dev, outmem)


if __name__ == "__main__":
    main()
