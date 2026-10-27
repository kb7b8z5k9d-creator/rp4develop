#!/usr/bin/env python3
"""Alpha-through-the-copy test, DXVK StretchRect style, through the Mali bridge.

Mimics Ys Origin's bloom source: the scene is drawn into a 4x MSAA B8G8R8A8 back buffer (cleared to
(0,0,0,1), a full-screen triangle writing (0.25, 0.5, 0.75, 0.125)), resolved with vkCmdResolveImage into
a single-sample image, blitted with scaling (linear) into a 512x256 texture and 1:1 (nearest) into the
top-left of a 2048x1024 texture, and every stage is read back. Also the same without MSAA (a plain blit).
A pixel must read bf 80 40 20 (B G R A). Shader files on the command line: vertex (full-screen triangle)
then the fragment shader.
"""
import ctypes as C
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vkreadback as R  # noqa: E402
import vkspec as S  # noqa: E402

u32, u64, ptr, f32, i32 = C.c_uint32, C.c_uint64, C.c_void_p, C.c_float, C.c_int32
ImgBlit = R.struct("ImgBlit", [("srcSubresource", R.ImgSubLayers), ("srcOffsets", R.Offset3D * 2), ("dstSubresource", R.ImgSubLayers),
                               ("dstOffsets", R.Offset3D * 2)])
ImgResolve = R.struct("ImgResolve", [("srcSubresource", R.ImgSubLayers), ("srcOffset", R.Offset3D), ("dstSubresource", R.ImgSubLayers),
                                     ("dstOffset", R.Offset3D), ("extent", R.Extent3D)])

W, H = int(os.environ.get("VKA_W", "1280")), int(os.environ.get("VKA_H", "720"))
FMT = int(os.environ.get("VKA_FMT", "44"))  # B8G8R8A8_UNORM; 37 = R8G8B8A8_UNORM
MASK = int(os.environ.get("VKA_MASK", "15"))  # colorWriteMask of the draw; 7 = RGB only: alpha must stay the clear's 1.0
EXPECT = os.environ.get("VKA_EXPECT", ("bf804020" if MASK & 8 else "bf8040ff") if FMT == 44 else "4080bf20")
USAGE = 0x1 | 0x2 | 0x4 | 0x10  # TRANSFER_SRC | TRANSFER_DST | SAMPLED | COLOR_ATTACHMENT (DXVK's render-target textures)


def main():
    VK = R.VK
    vert_path, frag_path = sys.argv[1], sys.argv[2]
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
    cpool = u64(0); dfn("vkCreateCommandPool")(dev, C.byref(R.CmdPoolCI(39, None, 2, 0)), None, C.byref(cpool))
    cb = u64(0); dfn("vkAllocateCommandBuffers")(dev, C.byref(R.CmdBufAI(40, None, cpool.value, 0, 1)), C.byref(cb))
    begin, end = dfn("vkBeginCommandBuffer"), dfn("vkEndCommandBuffer")
    copy_i2b = dfn("vkCmdCopyImageToBuffer", None)
    barrier = dfn("vkCmdPipelineBarrier", None)
    blit, resolve = dfn("vkCmdBlitImage", None), dfn("vkCmdResolveImage", None)
    invalidate = dfn("vkInvalidateMappedMemoryRanges")
    submit, create_fence, wait_fence, reset_fence = dfn("vkQueueSubmit"), dfn("vkCreateFence"), dfn("vkWaitForFences"), dfn("vkResetFences")
    fence = u64(0); create_fence(dev, C.byref(R.FenceCI(8, None, 0)), None, C.byref(fence))
    create_rp, create_view, create_fb = dfn("vkCreateRenderPass"), dfn("vkCreateImageView"), dfn("vkCreateFramebuffer")
    begin_rp, end_rp = dfn("vkCmdBeginRenderPass", None), dfn("vkCmdEndRenderPass", None)
    create_sm, create_pl, create_gp = dfn("vkCreateShaderModule"), dfn("vkCreatePipelineLayout"), dfn("vkCreateGraphicsPipelines")
    bind_pipe, draw = dfn("vkCmdBindPipeline", None), dfn("vkCmdDraw", None)

    def run(record):
        begin(cb, C.byref(R.CmdBufBI(42, None, 1, None)))
        record()
        end(cb)
        cbs = (u64 * 1)(cb.value)
        si = R.SubmitInfo(4, None, 0, None, None, 1, cbs, 0, None)
        reset_fence(dev, 1, C.byref(fence))
        rs = submit(q, 1, C.byref(si), fence)
        rw = wait_fence(dev, 1, C.byref(fence), 1, u64(10**10))
        return rs, rw

    def make_image(w, h, fmt, usage, samples=1):
        img = u64(0)
        ci = R.ImageCI(14, None, 0, 1, fmt, R.Extent3D(w, h, 1), 1, 1, samples, 0, usage, 0, 0, None, 0)
        r = create_image(dev, C.byref(ci), None, C.byref(img))
        rq = R.MemReqs(); get_ireq(dev, img, C.byref(rq))
        mt = dev_type if (rq.memoryTypeBits >> dev_type) & 1 else [i for i, f in types if (rq.memoryTypeBits >> i) & 1][0]
        mem = u64(0)
        ra = alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, mt)), None, C.byref(mem))
        rb = bind_i(dev, img, mem, u64(0))
        print(f"   image {w}x{h} fmt {fmt} samples {samples}: create {r}, alloc {ra} ({rq.size} bytes, type {mt}), bind {rb}")
        return img

    def make_buffer(size, usage):
        buf = u64(0)
        create_buffer(dev, C.byref(R.BufferCI(12, None, 0, size, usage, 0, 0, None)), None, C.byref(buf))
        rq = R.MemReqs(); get_breq(dev, buf, C.byref(rq))
        mem = u64(0)
        alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, host_type)), None, C.byref(mem))
        bind_b(dev, buf, mem, u64(0))
        return buf, mem

    def module(path):
        code = open(path, "rb").read()
        buf = C.create_string_buffer(code, len(code))
        sm = u64(0)
        r = create_sm(dev, C.byref(S.ShaderModuleCI(16, None, 0, len(code), C.cast(buf, ptr))), None, C.byref(sm))
        return sm, r, buf

    def img_barrier(img, src_access, dst_access, old, new, src_stage, dst_stage):
        b = R.ImgMemBarrier(45, None, src_access, dst_access, old, new, 0xFFFFFFFF, 0xFFFFFFFF, img.value, R.ImgSubRange(1, 0, 1, 0, 1))
        barrier(cb, src_stage, dst_stage, 0, 0, None, 0, None, 1, C.byref(b))

    layers = R.ImgSubLayers(1, 0, 0, 1)
    vs, r, vs_keep = module(vert_path); print("vertex module ->", r)
    fs, r, fs_keep = module(frag_path); print("fragment module ->", r)
    layout = u64(0); create_pl(dev, C.byref(S.LayoutCI(30, None, 0, 0, None, 0, None)), None, C.byref(layout))

    rb_buf, rb_mem = make_buffer(2048 * 1024 * 4, 0x2)

    def readback(img, w, h, label, points):
        """copies image (in TRANSFER_SRC_OPTIMAL) to the buffer and prints the pixels asked for"""
        p = ptr(); map_mem(dev, rb_mem, u64(0), u64(w * h * 4), 0, C.byref(p)); C.memset(p, 0x77, w * h * 4); unmap(dev, rb_mem)

        def rec():
            region = R.BufImgCopy(0, 0, 0, layers, R.Offset3D(0, 0, 0), R.Extent3D(w, h, 1))
            copy_i2b(cb, img, 6, rb_buf, 1, C.byref(region))
            barrier(cb, 0x1000, 0x4000, 0, 0, None, 0, None, 0, None)
        rs_, rw = run(rec)
        map_mem(dev, rb_mem, u64(0), u64(w * h * 4), 0, C.byref(p))
        invalidate(dev, 1, C.byref(R.MappedRange(6, None, rb_mem.value, 0, u64(0xFFFFFFFFFFFFFFFF))))
        out = []
        for (x, y) in points:
            out.append(f"({x},{y})={C.string_at(p.value + (y * w + x) * 4, 4).hex()}")
        unmap(dev, rb_mem)
        bad = [o for o in out if not o.endswith("=" + EXPECT)]
        print(f"   {label}: submit {rs_}/{rw}: {' '.join(out)} -> {'OK' if not bad else 'WRONG (want ' + EXPECT + ')'}")

    for samples in ((4, 1) if MASK == 15 else (1, 4)):
        print(f"\n== back buffer {W}x{H}, {samples} sample(s)")
        # render pass: one colour attachment, cleared to (0,0,0,1), stored, ends in TRANSFER_SRC_OPTIMAL
        att = (R.AttachDesc * 1)(R.AttachDesc(0, FMT, samples, 1, 0, 2, 1, 0, 6))
        ref = (R.AttachRef * 1)(R.AttachRef(0, 2))
        sub = (R.SubpassDesc * 1)(R.SubpassDesc(0, 0, 0, None, 1, ref, None, None, 0, None))
        rp = u64(0); print("   vkCreateRenderPass ->", create_rp(dev, C.byref(R.RenderPassCI(38, None, 0, 1, att, 1, sub, 0, None)), None, C.byref(rp)))
        bb = make_image(W, H, FMT, USAGE, samples)
        view = u64(0)
        print("   vkCreateImageView ->", create_view(dev, C.byref(R.ImageViewCI(15, None, 0, bb.value, 1, FMT, (u32 * 4)(0, 0, 0, 0),
                                                                                  R.ImgSubRange(1, 0, 1, 0, 1))), None, C.byref(view)))
        views = (u64 * 1)(view.value)
        fb = u64(0); print("   vkCreateFramebuffer ->", create_fb(dev, C.byref(R.FramebufferCI(37, None, 0, rp.value, 1, views, W, H, 1)), None, C.byref(fb)))
        stages = (S.StageCI * 2)(S.StageCI(18, None, 0, 1, vs.value, b"main", None), S.StageCI(18, None, 0, 0x10, fs.value, b"main", None))
        vi = S.VertexInputCI(19, None, 0, 0, None, 0, None)
        ia = S.InputAsmCI(20, None, 0, 3, 0)
        vp = (S.Viewport * 1)(S.Viewport(0, 0, W, H, 0, 1))
        sc = (R.Rect2D * 1)(R.Rect2D(0, 0, W, H))
        vps = S.ViewportCI(22, None, 0, 1, C.cast(vp, ptr), 1, C.cast(sc, ptr))
        rs = S.RasterCI(23, None, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1.0)
        ms = S.MultisampleCI(24, None, 0, samples, 0, 0, None, 0, 0)
        ba = (S.BlendAttachment * 1)(S.BlendAttachment(0, 0, 0, 0, 0, 0, 0, MASK))
        bs = S.BlendCI(26, None, 0, 0, 0, 1, C.cast(ba, ptr), (f32 * 4)(0, 0, 0, 0))
        pci = S.PipelineCI(28, None, 0, 2, C.cast(stages, ptr), C.addressof(vi), C.addressof(ia), None, C.addressof(vps), C.addressof(rs),
                           C.addressof(ms), None, C.addressof(bs), None, layout.value, rp.value, 0, 0, -1)
        pipe = u64(0); print("   vkCreateGraphicsPipelines ->", create_gp(dev, u64(0), 1, C.byref(pci), None, C.byref(pipe)))

        resolved = make_image(W, H, FMT, USAGE) if samples > 1 else None
        small = make_image(512, 256, FMT, USAGE)
        big = make_image(2048, 1024, FMT, USAGE)

        def rec():
            clear = (R.ClearValue * 1)(R.ClearValue((f32 * 4)(0.0, 0.0, 0.0, 1.0)))
            begin_rp(cb, C.byref(R.RenderPassBI(43, None, rp.value, fb.value, R.Rect2D(0, 0, W, H), 1, clear)), 0)
            bind_pipe(cb, 0, pipe)
            draw(cb, 3, 1, 0, 0)
            end_rp(cb)
            img_barrier(bb, 0x100, 0x800, 6, 6, 0x400, 0x1000)
            src = bb
            if resolved is not None:
                img_barrier(resolved, 0, 0x1000, 0, 7, 0x1, 0x1000)
                reg = ImgResolve(layers, R.Offset3D(0, 0, 0), layers, R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
                resolve(cb, bb, 6, resolved, 7, 1, C.byref(reg))
                img_barrier(resolved, 0x1000, 0x800, 7, 6, 0x1000, 0x1000)
                src = resolved
            img_barrier(small, 0, 0x1000, 0, 7, 0x1, 0x1000)
            b1 = ImgBlit(layers, (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(W, H, 1)), layers,
                         (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(512, 256, 1)))
            blit(cb, src, 6, small, 7, 1, C.byref(b1), 1)  # linear, scaled: the 512x256 bloom source
            img_barrier(small, 0x1000, 0x800, 7, 6, 0x1000, 0x1000)
            img_barrier(big, 0, 0x1000, 0, 7, 0x1, 0x1000)
            b2 = ImgBlit(layers, (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(W, H, 1)), layers,
                         (R.Offset3D * 2)(R.Offset3D(0, 0, 0), R.Offset3D(W, H, 1)))
            blit(cb, src, 6, big, 7, 1, C.byref(b2), 0)  # nearest, 1:1: the 2048x1024 frame copy
            img_barrier(big, 0x1000, 0x800, 7, 6, 0x1000, 0x1000)
        rs_, rw = run(rec)
        print(f"   draw+resolve+blits: submit {rs_}/{rw}")
        if resolved is not None:
            readback(resolved, W, H, "resolved 1280x720", [(0, 0), (W // 2, H // 2), (W - 1, H - 1)])
        else:
            readback(bb, W, H, "back buffer 1280x720", [(0, 0), (W // 2, H // 2), (W - 1, H - 1)])
        readback(small, 512, 256, "blit 512x256 (linear)", [(0, 0), (256, 128), (511, 255)])
        readback(big, 2048, 1024, "blit 2048x1024 (1:1 nearest)", [(0, 0), (W // 2, H // 2), (W - 1, H - 1)])


if __name__ == "__main__":
    main()
