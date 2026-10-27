#!/usr/bin/env python3
"""LINEAR-tiled images through the Mali bridge: memory requirements, layouts (queried only after
memory is bound, which is what crashed Mali r32p1 otherwise), and a write-through-the-map,
copy-to-optimal, read-back check at the game's scratch size. Run against a PRIVATE server."""
import ctypes as C
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vkreadback as R  # noqa: E402

u32, u64, ptr, f32 = C.c_uint32, C.c_uint64, C.c_void_p, C.c_float
SubresourceLayout = R.struct("SubresourceLayout", [("offset", u64), ("size", u64), ("rowPitch", u64), ("arrayPitch", u64), ("depthPitch", u64)])
ImgSubresource = R.struct("ImgSubresource", [("aspectMask", u32), ("mipLevel", u32), ("arrayLayer", u32)])
ImgCopy = R.struct("ImgCopy", [("srcSubresource", R.ImgSubLayers), ("srcOffset", R.Offset3D), ("dstSubresource", R.ImgSubLayers),
                               ("dstOffset", R.Offset3D), ("extent", R.Extent3D)])
FormatProps = R.struct("FormatProps", [("linear", u32), ("optimal", u32), ("buffer", u32)])


def main():
    VK = R.VK
    app = R.AppInfo(0, None, os.environ.get("VKL_APP", "Xwayland").encode(), 0, b"mesa zink", 0, (1 << 22) | (1 << 12))
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
    dev_type = [i for i, f in types if f & 0x1][0]
    gfp = fn("vkGetPhysicalDeviceFormatProperties", None)
    for fmt_name, fmt in (("B8G8R8A8", 44), ("R8G8B8A8", 37)):
        fp = FormatProps(); gfp(pd, fmt, C.byref(fp))
        print(f"format {fmt_name}: linearTilingFeatures 0x{fp.linear:x} optimalTilingFeatures 0x{fp.optimal:x}")
    prio = (f32 * 1)(1.0)
    qci = R.QueueCI(2, None, 0, 0, 1, prio)
    dci = R.DeviceCI(3, None, 0, 1, C.pointer(qci), 0, None, 0, None, None)
    dev = ptr()
    print("vkCreateDevice ->", fn("vkCreateDevice")(pd, C.byref(dci), None, C.byref(dev)))
    gdpa = C.CFUNCTYPE(ptr)(gipa(inst, b"vkGetDeviceProcAddr"))

    def dfn(name, restype=C.c_int):
        return C.CFUNCTYPE(restype)(gdpa(dev, name.encode()))

    q = ptr(); dfn("vkGetDeviceQueue", None)(dev, 0, 0, C.byref(q))
    create_image, destroy_image = dfn("vkCreateImage"), dfn("vkDestroyImage", None)
    get_ireq, get_breq = dfn("vkGetImageMemoryRequirements", None), dfn("vkGetBufferMemoryRequirements", None)
    get_layout = dfn("vkGetImageSubresourceLayout", None)
    alloc, free_mem, bind_i, bind_b = dfn("vkAllocateMemory"), dfn("vkFreeMemory", None), dfn("vkBindImageMemory"), dfn("vkBindBufferMemory")
    map_mem, unmap = dfn("vkMapMemory"), dfn("vkUnmapMemory", None)
    create_buffer = dfn("vkCreateBuffer")
    cpool = u64(0); dfn("vkCreateCommandPool")(dev, C.byref(R.CmdPoolCI(39, None, 2, 0)), None, C.byref(cpool))
    cb = u64(0); dfn("vkAllocateCommandBuffers")(dev, C.byref(R.CmdBufAI(40, None, cpool.value, 0, 1)), C.byref(cb))
    begin, end = dfn("vkBeginCommandBuffer"), dfn("vkEndCommandBuffer")
    barrier, copy_i2i, copy_i2b = dfn("vkCmdPipelineBarrier", None), dfn("vkCmdCopyImage", None), dfn("vkCmdCopyImageToBuffer", None)
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

    usages = {"src|dst": 0x3, "sampled|src|dst": 0x7, "sampled": 0x4}
    sizes = ((320, 240), (640, 480), (1280, 720), (64, 64), (16, 16), (1, 1))
    fmt_name, fmt = "B8G8R8A8", 44
    for (w, h) in sizes:
        for uname, usage in usages.items():
            img = u64(0)
            ci = R.ImageCI(14, None, 0, 1, fmt, R.Extent3D(w, h, 1), 1, 1, 1, 1, usage, 0, 0, None, 1)
            r = create_image(dev, C.byref(ci), None, C.byref(img))
            if r != 0:
                print(f"LINEAR {w}x{h} {uname:15} create -> {r}"); continue
            rq = R.MemReqs(); get_ireq(dev, img, C.byref(rq))
            line = f"LINEAR {w:4}x{h:<4} {uname:15} reqs size {rq.size:8} align {rq.alignment:5} types 0x{rq.memoryTypeBits:x}"
            if rq.size == 0 or not rq.memoryTypeBits:
                print(line + "  <-- BOGUS (no layout query: it crashes the driver)"); destroy_image(dev, img, None); continue
            mt = [i for i, f in types if (rq.memoryTypeBits >> i) & 1 and f & 0x2]
            mt = mt[0] if mt else [i for i, f in types if (rq.memoryTypeBits >> i) & 1][0]
            mem = u64(0)
            ra = alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, mt)), None, C.byref(mem))
            if ra != 0:
                print(line + f" alloc type {mt} -> {ra}"); destroy_image(dev, img, None); continue
            bind_i(dev, img, mem, u64(0))
            lay = SubresourceLayout(); get_layout(dev, img, C.byref(ImgSubresource(1, 0, 0)), C.byref(lay))
            line += f" | layout off {lay.offset} size {lay.size} pitch {lay.rowPitch}"
            bad = rq.size < w * h * 4 or lay.rowPitch < w * 4 or lay.size < w * h * 4
            print(line + ("  <-- TOO SMALL" if bad else ""))
            # write a pattern through the map, copy to an optimal image, read back
            if not bad and (types[mt][1] & 0x2) and uname == "src|dst" and w >= 16 and w <= 640:
                # row-varying pattern: pixel (x, y) = (x & 255, y & 255, 7, 255), compared byte-exact
                expected = b"".join(bytes([x & 255, y & 255, 7, 255]) for y in range(h) for x in range(w))
                p = ptr(); map_mem(dev, mem, u64(0), u64(rq.size), 0, C.byref(p))
                C.memset(p, 0x55, rq.size)
                for y in range(h):
                    C.memmove(p.value + lay.offset + y * lay.rowPitch, expected[y * w * 4:(y + 1) * w * 4], w * 4)
                unmap(dev, mem)
                dst = u64(0); create_image(dev, C.byref(R.ImageCI(14, None, 0, 1, fmt, R.Extent3D(w, h, 1), 1, 1, 1, 0, 0x3, 0, 0, None, 0)), None, C.byref(dst))
                rq2 = R.MemReqs(); get_ireq(dev, dst, C.byref(rq2)); dmem = u64(0)
                alloc(dev, C.byref(R.MemAllocInfo(5, None, rq2.size, [i for i, f in types if (rq2.memoryTypeBits >> i) & 1][0])), None, C.byref(dmem)); bind_i(dev, dst, dmem, u64(0))
                buf = u64(0); create_buffer(dev, C.byref(R.BufferCI(12, None, 0, w * h * 4, 0x2, 0, 0, None)), None, C.byref(buf))
                rb = R.MemReqs(); get_breq(dev, buf, C.byref(rb)); bmem = u64(0)
                alloc(dev, C.byref(R.MemAllocInfo(5, None, rb.size, host_type)), None, C.byref(bmem)); bind_b(dev, buf, bmem, u64(0))
                def rec():
                    img_barrier(img, 1, 6, 0x4000, 0x800)
                    img_barrier(dst, 0, 7, 0, 0x1000)
                    cp = ImgCopy(R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(w, h, 1))
                    copy_i2i(cb, img, 6, dst, 7, 1, C.byref(cp))
                    img_barrier(dst, 7, 6, 0x1000, 0x800)
                    region = R.BufImgCopy(0, 0, 0, R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(w, h, 1))
                    copy_i2b(cb, dst, 6, buf, 1, C.byref(region))
                res = run(rec)
                map_mem(dev, bmem, u64(0), u64(w * h * 4), 0, C.byref(p)); data = C.string_at(p, w * h * 4); unmap(dev, bmem)
                wrong = [y for y in range(h) if data[y * w * 4:(y + 1) * w * 4] != expected[y * w * 4:(y + 1) * w * 4]]
                detail = "" if not wrong else "  <-- WRONG CONTENT, first wrong row %d bytes %s" % (wrong[0], data[wrong[0] * w * 4:wrong[0] * w * 4 + 16].hex())
                print("    write via map -> copy to optimal -> read back: submit/wait %s %d ms; rows wrong %d/%d%s" % (res[:2], res[2], len(wrong), h, "  OK, byte-exact" if not wrong else detail))
            destroy_image(dev, img, None); free_mem(dev, mem, None)


if __name__ == "__main__":
    main()
