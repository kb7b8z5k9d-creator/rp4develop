#!/usr/bin/env python3
"""Blit test through the Mali bridge: a small patterned source image (uploaded like DXVK uploads a
locked surface: via a host-visible buffer, or written straight into a LINEAR-tiled host-visible
image), blitted with scaling into an optimal image, read back and checked.
Reuses the helpers of vkreadback.py by import.
"""
import ctypes as C
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vkreadback as R  # noqa: E402

u32, u64, ptr, f32 = C.c_uint32, C.c_uint64, C.c_void_p, C.c_float
ImgBlit = R.struct("ImgBlit", [("srcSubresource", R.ImgSubLayers), ("srcOffsets", R.Offset3D * 2), ("dstSubresource", R.ImgSubLayers),
                               ("dstOffsets", R.Offset3D * 2)])
ImgCopy = R.struct("ImgCopy", [("srcSubresource", R.ImgSubLayers), ("srcOffset", R.Offset3D), ("dstSubresource", R.ImgSubLayers),
                               ("dstOffset", R.Offset3D), ("extent", R.Extent3D)])
SubresourceLayout = R.struct("SubresourceLayout", [("offset", u64), ("size", u64), ("rowPitch", u64), ("arrayPitch", u64), ("depthPitch", u64)])
ImgSubresource = R.struct("ImgSubresource", [("aspectMask", u32), ("mipLevel", u32), ("arrayLayer", u32)])


def main():
    VK = R.VK
    app = R.AppInfo(0, None, b"yso_win.exe", 0, b"DXVK", 4235267, (1 << 22) | (1 << 12))
    iexts = (C.c_char_p * 1)(b"VK_KHR_get_physical_device_properties2")
    ici = R.InstanceCI(1, None, 0, C.pointer(app), 0, None, 1, iexts)
    inst = ptr()
    VK.vkCreateInstance.restype = C.c_int
    print("vkCreateInstance ->", VK.vkCreateInstance(C.byref(ici), None, C.byref(inst)))
    gipa = VK.vkGetInstanceProcAddr
    gipa.restype = ptr

    def fn(name, restype=C.c_int):
        p = gipa(inst, name.encode())
        if not p:
            print("missing", name); sys.exit(1)
        return C.CFUNCTYPE(restype)(p)

    enum = fn("vkEnumeratePhysicalDevices")
    n = u32(0); enum(inst, C.byref(n), None)
    pds = (ptr * max(n.value, 1))(); enum(inst, C.byref(n), pds)
    pd = C.c_void_p(pds[0])
    mp = R.MemProps(); fn("vkGetPhysicalDeviceMemoryProperties", None)(pd, C.byref(mp))
    types = [(i, mp.memoryTypes[i].propertyFlags) for i in range(mp.memoryTypeCount)]
    host_type = [i for i, f in types if f & 0x2][0]
    dev_type = [i for i, f in types if f & 0x1][0]
    print("memory types:", ["%d:0x%x" % t for t in types], "host", host_type, "device", dev_type)
    prio = (f32 * 1)(1.0)
    qci = R.QueueCI(2, None, 0, 0, 1, prio)
    dci = R.DeviceCI(3, None, 0, 1, C.pointer(qci), 0, None, 0, None, None)
    dev = ptr()
    print("vkCreateDevice ->", fn("vkCreateDevice")(pd, C.byref(dci), None, C.byref(dev)))
    gdpa = C.CFUNCTYPE(ptr)(gipa(inst, b"vkGetDeviceProcAddr"))

    def dfn(name, restype=C.c_int):
        p = gdpa(dev, name.encode())
        if not p:
            print("missing", name); sys.exit(1)
        return C.CFUNCTYPE(restype)(p)

    q = ptr(); dfn("vkGetDeviceQueue", None)(dev, 0, 0, C.byref(q))
    create_image, create_buffer = dfn("vkCreateImage"), dfn("vkCreateBuffer")
    get_ireq, get_breq = dfn("vkGetImageMemoryRequirements", None), dfn("vkGetBufferMemoryRequirements", None)
    alloc, bind_i, bind_b = dfn("vkAllocateMemory"), dfn("vkBindImageMemory"), dfn("vkBindBufferMemory")
    map_mem, unmap = dfn("vkMapMemory"), dfn("vkUnmapMemory", None)
    get_layout = dfn("vkGetImageSubresourceLayout", None)
    cpool = u64(0); dfn("vkCreateCommandPool")(dev, C.byref(R.CmdPoolCI(39, None, 2, 0)), None, C.byref(cpool))
    cb = u64(0); dfn("vkAllocateCommandBuffers")(dev, C.byref(R.CmdBufAI(40, None, cpool.value, 0, 1)), C.byref(cb))
    begin, end = dfn("vkBeginCommandBuffer"), dfn("vkEndCommandBuffer")
    barrier = dfn("vkCmdPipelineBarrier", None)
    copy_b2i, copy_i2b, copy_i2i, blit = dfn("vkCmdCopyBufferToImage", None), dfn("vkCmdCopyImageToBuffer", None), dfn("vkCmdCopyImage", None), dfn("vkCmdBlitImage", None)
    submit, create_fence, wait_fence, reset_fence = dfn("vkQueueSubmit"), dfn("vkCreateFence"), dfn("vkWaitForFences"), dfn("vkResetFences")
    fence = u64(0); create_fence(dev, C.byref(R.FenceCI(8, None, 0)), None, C.byref(fence))

    def run(record):
        begin(cb, C.byref(R.CmdBufBI(42, None, 1, None)))
        record()
        end(cb)
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

    def make_image(w, h, fmt, tiling, usage, mem_type, initial=0):
        img = u64(0)
        ci = R.ImageCI(14, None, 0, 1, fmt, R.Extent3D(w, h, 1), 1, 1, 1, tiling, usage, 0, 0, None, initial)
        r = create_image(dev, C.byref(ci), None, C.byref(img))
        if r != 0:
            return None, None, r
        rq = R.MemReqs(); get_ireq(dev, img, C.byref(rq))
        if not (rq.memoryTypeBits >> mem_type) & 1:
            mem_type = [i for i, f in types if (rq.memoryTypeBits >> i) & 1][0]
        mem = u64(0)
        ra = alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, mem_type)), None, C.byref(mem))
        if ra != 0:
            return None, None, ra
        bind_i(dev, img, mem, u64(0))
        return img, mem, 0

    def make_buffer(size, usage, mem_type):
        buf = u64(0)
        create_buffer(dev, C.byref(R.BufferCI(12, None, 0, size, usage, 0, 0, None)), None, C.byref(buf))
        rq = R.MemReqs(); get_breq(dev, buf, C.byref(rq))
        mem = u64(0)
        alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, mem_type)), None, C.byref(mem))
        bind_b(dev, buf, mem, u64(0))
        return buf, mem

    SW, SH = 320, 240
    DW, DH = int(os.environ.get("VKB_DW", "1280")), int(os.environ.get("VKB_DH", "720"))
    # pattern: left half (64,128,192,255) BGRA, right half (192,96,32,255)
    left, right = bytes([64, 128, 192, 255]), bytes([192, 96, 32, 255])
    pattern = b"".join((left if x < SW // 2 else right) for y in range(SH) for x in range(SW))

    def read_image(img, w, h):
        buf, bmem = make_buffer(w * h * 4, 0x2, host_type)
        p = ptr(); map_mem(dev, bmem, u64(0), u64(w * h * 4), 0, C.byref(p)); C.memset(p, 0x77, w * h * 4); unmap(dev, bmem)
        def rec():
            region = R.BufImgCopy(0, 0, 0, R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(w, h, 1))
            copy_i2b(cb, img, 6, buf, 1, C.byref(region))
        rs, rw, ms = run(rec)
        map_mem(dev, bmem, u64(0), u64(w * h * 4), 0, C.byref(p))
        data = C.string_at(p, w * h * 4)
        unmap(dev, bmem)
        return data, ms

    def verdict(data, w, h):
        tl, tr = data[(h // 2 * w + w // 8) * 4:][:4], data[(h // 2 * w + w * 7 // 8) * 4:][:4]
        whites = data.count(b"\xff\xff\xff\xff") * 4 * 100 // len(data)
        lefts = data.count(left) * 4 * 100 // len(data)
        rights = data.count(right) * 4 * 100 // len(data)
        return f"left-sample {tl.hex()} right-sample {tr.hex()} | left {lefts}% right {rights}% white {whites}% marker {data.count(b'wwww') * 4 * 100 // len(data)}%"

    FMT = 44  # B8G8R8A8_UNORM
    print(f"\n== source {SW}x{SH} BGRA8, destination {DW}x{DH}; expected left {left.hex()} right {right.hex()}")

    # A: optimal source uploaded through a buffer (DXVK's usual upload), blit with linear filter
    src, _, r = make_image(SW, SH, FMT, 0, 0x1 | 0x2 | 0x4, dev_type)
    up, upmem = make_buffer(len(pattern), 0x1, host_type)
    p = ptr(); map_mem(dev, upmem, u64(0), u64(len(pattern)), 0, C.byref(p)); C.memmove(p, pattern, len(pattern)); unmap(dev, upmem)
    dst, _, r2 = make_image(DW, DH, FMT, 0, 0x1 | 0x2 | 0x4 | 0x10, dev_type)
    def rec_a():
        img_barrier(src, 0, 7, 0, 0x1000)
        region = R.BufImgCopy(0, 0, 0, R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(SW, SH, 1))
        copy_b2i(cb, up, src, 7, 1, C.byref(region))
        img_barrier(src, 7, 6, 0x1000, 0x800)
        img_barrier(dst, 0, 7, 0, 0x1000)
        bl = ImgBlit(R.ImgSubLayers(1, 0, 0, 1), (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(SW, SH, 1)),
                     R.ImgSubLayers(1, 0, 0, 1), (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(DW, DH, 1)))
        blit(cb, src, 6, dst, 7, 1, C.byref(bl), 1)
        img_barrier(dst, 7, 6, 0x1000, 0x800)
    print("A optimal src via buffer, blit linear:", run(rec_a))
    data, ms = read_image(dst, DW, DH); print("   ", verdict(data, DW, DH), f"(readback {ms} ms)")

    # B: LINEAR host-visible source written through the mapping, blit
    src2, mem2, r = make_image(SW, SH, FMT, 1, 0x1 | 0x2 | 0x4, host_type, initial=1)
    print("B linear host-visible source image ->", r)
    if r == 0:
        lay = SubresourceLayout(); get_layout(dev, src2, C.byref(ImgSubresource(1, 0, 0)), C.byref(lay))
        print(f"   layout: offset {lay.offset} size {lay.size} rowPitch {lay.rowPitch}")
        rq = R.MemReqs(); get_ireq(dev, src2, C.byref(rq))
        map_mem(dev, mem2, u64(0), u64(rq.size), 0, C.byref(p))
        C.memset(p, 0x55, rq.size)  # no recycled memory can pass
        for y in range(SH):
            C.memmove(p.value + lay.offset + y * lay.rowPitch, pattern[y * SW * 4:(y + 1) * SW * 4], SW * 4)
        unmap(dev, mem2)
        dst2, _, _ = make_image(DW, DH, FMT, 0, 0x1 | 0x2 | 0x4 | 0x10, dev_type)
        def rec_b():
            img_barrier(src2, 1, 6, 0x4000, 0x800)  # PREINITIALIZED -> TRANSFER_SRC
            img_barrier(dst2, 0, 7, 0, 0x1000)
            bl = ImgBlit(R.ImgSubLayers(1, 0, 0, 1), (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(SW, SH, 1)),
                         R.ImgSubLayers(1, 0, 0, 1), (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(DW, DH, 1)))
            blit(cb, src2, 6, dst2, 7, 1, C.byref(bl), 1)
            img_barrier(dst2, 7, 6, 0x1000, 0x800)
        print("B linear src written via map, blit linear:", run(rec_b))
        data, ms = read_image(dst2, DW, DH); print("   ", verdict(data, DW, DH), f"(readback {ms} ms)")
        # B2: copy (no scaling) from the linear image into a same-size optimal image
        dst3, _, _ = make_image(SW, SH, FMT, 0, 0x1 | 0x2 | 0x4, dev_type)
        def rec_b2():
            img_barrier(dst3, 0, 7, 0, 0x1000)
            cp = ImgCopy(R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(SW, SH, 1))
            copy_i2i(cb, src2, 6, dst3, 7, 1, C.byref(cp))
            img_barrier(dst3, 7, 6, 0x1000, 0x800)
        print("B2 linear src, vkCmdCopyImage same size:", run(rec_b2))
        data, ms = read_image(dst3, SW, SH); print("   ", verdict(data, SW, SH), f"(readback {ms} ms)")
        # B3: read the linear image straight back through its mapping
        map_mem(dev, mem2, u64(0), u64(rq.size), 0, C.byref(p))
        row = C.string_at(p.value + lay.offset + (SH // 2) * lay.rowPitch, SW * 4)
        unmap(dev, mem2)
        print("B3 linear image re-read through the map:", verdict(row, SW, 1))

    # C: many small image creations + clears, timed (what the trace showed the game doing)
    t = time.time()
    imgs = []
    for i in range(20):
        im, _, r = make_image(SW, SH, FMT, 0, 0x1 | 0x2 | 0x4, dev_type)
        imgs.append(im)
    print(f"C 20 image creations: {(time.time() - t) * 1000:.0f} ms")


if __name__ == "__main__":
    main()
