#!/usr/bin/env python3
"""Shared-memory coherency test through the Mali bridge, with DXVK's timing: a host-visible,
HOST_COHERENT uniform buffer is written through its persistent mapping (no flush) and read by the
GPU right away, N times in a row with a different colour each time. A stale read (the GPU seeing an
older write) shows as a mismatch. Also the same with a vertex buffer: the full-screen triangle's
colour comes from a per-vertex attribute written just before the draw.
Shaders: tri.vert (position only) + ubo.frag; vcol.vert + vcol.frag. Reuses vkreadback.py by import.
"""
import ctypes as C
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vkreadback as R  # noqa: E402
import vkspec as S  # noqa: E402  (pipeline structs)

u32, u64, ptr, f32, i32 = C.c_uint32, C.c_uint64, C.c_void_p, C.c_float, C.c_int32
DSLBinding = R.struct("DSLBinding", [("binding", u32), ("descriptorType", u32), ("descriptorCount", u32), ("stageFlags", u32),
                                     ("pImmutableSamplers", ptr)])
DSLCI = R.struct("DSLCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("bindingCount", u32), ("pBindings", ptr)])
PoolSize = R.struct("PoolSize", [("type", u32), ("descriptorCount", u32)])
DescPoolCI = R.struct("DescPoolCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("maxSets", u32), ("poolSizeCount", u32), ("pPoolSizes", ptr)])
DescSetAI = R.struct("DescSetAI", [("sType", u32), ("pNext", ptr), ("descriptorPool", u64), ("descriptorSetCount", u32), ("pSetLayouts", ptr)])
DescBufInfo = R.struct("DescBufInfo", [("buffer", u64), ("offset", u64), ("range", u64)])
WriteDS = R.struct("WriteDS", [("sType", u32), ("pNext", ptr), ("dstSet", u64), ("dstBinding", u32), ("dstArrayElement", u32),
                               ("descriptorCount", u32), ("descriptorType", u32), ("pImageInfo", ptr), ("pBufferInfo", ptr), ("pTexelBufferView", ptr)])
VIBinding = R.struct("VIBinding", [("binding", u32), ("stride", u32), ("inputRate", u32)])
VIAttr = R.struct("VIAttr", [("location", u32), ("binding", u32), ("format", u32), ("offset", u32)])

W = H = 32
FMT = 37


def main():
    VK = R.VK
    vert, frag, vcvert, vcfrag = sys.argv[1:5]
    N = int(os.environ.get("VKCOH_N", "300"))
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
    print("memory types:", ["%d:0x%x" % t for t in types])
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
    invalidate = dfn("vkInvalidateMappedMemoryRanges")
    cpool = u64(0); dfn("vkCreateCommandPool")(dev, C.byref(R.CmdPoolCI(39, None, 2, 0)), None, C.byref(cpool))
    cb = u64(0); dfn("vkAllocateCommandBuffers")(dev, C.byref(R.CmdBufAI(40, None, cpool.value, 0, 1)), C.byref(cb))
    begin, end = dfn("vkBeginCommandBuffer"), dfn("vkEndCommandBuffer")
    copy_i2b, barrier = dfn("vkCmdCopyImageToBuffer", None), dfn("vkCmdPipelineBarrier", None)
    submit, create_fence, wait_fence, reset_fence = dfn("vkQueueSubmit"), dfn("vkCreateFence"), dfn("vkWaitForFences"), dfn("vkResetFences")
    fence = u64(0); create_fence(dev, C.byref(R.FenceCI(8, None, 0)), None, C.byref(fence))
    create_rp, create_view, create_fb = dfn("vkCreateRenderPass"), dfn("vkCreateImageView"), dfn("vkCreateFramebuffer")
    begin_rp, end_rp = dfn("vkCmdBeginRenderPass", None), dfn("vkCmdEndRenderPass", None)
    create_sm, create_pl, create_gp = dfn("vkCreateShaderModule"), dfn("vkCreatePipelineLayout"), dfn("vkCreateGraphicsPipelines")
    bind_pipe, draw = dfn("vkCmdBindPipeline", None), dfn("vkCmdDraw", None)
    create_dsl, create_pool, alloc_sets, update_sets = dfn("vkCreateDescriptorSetLayout"), dfn("vkCreateDescriptorPool"), dfn("vkAllocateDescriptorSets"), dfn("vkUpdateDescriptorSets", None)
    bind_sets, bind_vb = dfn("vkCmdBindDescriptorSets", None), dfn("vkCmdBindVertexBuffers", None)

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

    def make_image(w, h, fmt, usage):
        img = u64(0)
        ci = R.ImageCI(14, None, 0, 1, fmt, R.Extent3D(w, h, 1), 1, 1, 1, 0, usage, 0, 0, None, 0)
        create_image(dev, C.byref(ci), None, C.byref(img))
        rq = R.MemReqs(); get_ireq(dev, img, C.byref(rq))
        mt = dev_type if (rq.memoryTypeBits >> dev_type) & 1 else [i for i, f in types if (rq.memoryTypeBits >> i) & 1][0]
        mem = u64(0)
        alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, mt)), None, C.byref(mem))
        bind_i(dev, img, mem, u64(0))
        return img

    def make_buffer(size, usage, want):
        """want: property flags to prefer (HOST_VISIBLE|HOST_COHERENT, like DXVK's dynamic buffers)."""
        buf = u64(0)
        create_buffer(dev, C.byref(R.BufferCI(12, None, 0, size, usage, 0, 0, None)), None, C.byref(buf))
        rq = R.MemReqs(); get_breq(dev, buf, C.byref(rq))
        cands = [i for i, f in types if (rq.memoryTypeBits >> i) & 1 and (f & want) == want]
        mt = cands[0]
        mem = u64(0)
        alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, mt)), None, C.byref(mem))
        bind_b(dev, buf, mem, u64(0))
        return buf, mem, mt

    def module(path):
        code = open(path, "rb").read()
        keep = C.create_string_buffer(code, len(code))
        sm = u64(0)
        create_sm(dev, C.byref(S.ShaderModuleCI(16, None, 0, len(code), C.cast(keep, ptr))), None, C.byref(sm))
        return sm, keep

    att = (R.AttachDesc * 1)(R.AttachDesc(0, FMT, 1, 1, 0, 2, 1, 0, 6))
    ref = (R.AttachRef * 1)(R.AttachRef(0, 2))
    sub = (R.SubpassDesc * 1)(R.SubpassDesc(0, 0, 0, None, 1, ref, None, None, 0, None))
    rp = u64(0); create_rp(dev, C.byref(R.RenderPassCI(38, None, 0, 1, att, 1, sub, 0, None)), None, C.byref(rp))
    img = make_image(W, H, FMT, 0x10 | 0x1)
    view = u64(0)
    create_view(dev, C.byref(R.ImageViewCI(15, None, 0, img.value, 1, FMT, (u32 * 4)(0, 0, 0, 0), R.ImgSubRange(1, 0, 1, 0, 1))), None, C.byref(view))
    views = (u64 * 1)(view.value)
    fb = u64(0); create_fb(dev, C.byref(R.FramebufferCI(37, None, 0, rp.value, 1, views, W, H, 1)), None, C.byref(fb))
    rb, rbmem, _ = make_buffer(W * H * 4, 0x2, 0x2)  # readback: host-visible, any
    p = ptr(); map_mem(dev, rbmem, u64(0), u64(W * H * 4), 0, C.byref(p))

    # ---- part 1: uniform buffer written through its mapping right before each draw
    dsb = (DSLBinding * 1)(DSLBinding(0, 6, 1, 0x10, None))  # UNIFORM_BUFFER, fragment
    dsl = u64(0); create_dsl(dev, C.byref(DSLCI(32, None, 0, 1, C.cast(dsb, ptr))), None, C.byref(dsl))
    psz = (PoolSize * 1)(PoolSize(6, 4))
    pool = u64(0); create_pool(dev, C.byref(DescPoolCI(33, None, 0, 4, 1, C.cast(psz, ptr))), None, C.byref(pool))
    dsls = (u64 * 1)(dsl.value)
    dset = u64(0); alloc_sets(dev, C.byref(DescSetAI(34, None, pool.value, 1, C.cast(dsls, ptr))), C.byref(dset))
    ubo, ubomem, ubo_type = make_buffer(65536, 0x10, 0x6)  # UNIFORM_BUFFER, HOST_VISIBLE|HOST_COHERENT
    print("uniform buffer in memory type", ubo_type, "flags 0x%x" % types[ubo_type][1])
    ubop = ptr(); map_mem(dev, ubomem, u64(0), u64(65536), 0, C.byref(ubop))
    bi = DescBufInfo(ubo.value, 0, 16)
    wds = WriteDS(35, None, dset.value, 0, 0, 1, 6, None, C.addressof(bi), None)
    update_sets(dev, 1, C.byref(wds), 0, None)
    layout = u64(0); create_pl(dev, C.byref(S.LayoutCI(30, None, 0, 1, C.cast(dsls, ptr), 0, None)), None, C.byref(layout))
    vs, k1 = module(vert); fs, k2 = module(frag)
    stages = (S.StageCI * 2)(S.StageCI(18, None, 0, 1, vs.value, b"main", None), S.StageCI(18, None, 0, 0x10, fs.value, b"main", None))
    vi = S.VertexInputCI(19, None, 0, 0, None, 0, None)
    ia = S.InputAsmCI(20, None, 0, 3, 0)
    vp = (S.Viewport * 1)(S.Viewport(0, 0, W, H, 0, 1)); sc = (R.Rect2D * 1)(R.Rect2D(0, 0, W, H))
    vps = S.ViewportCI(22, None, 0, 1, C.cast(vp, ptr), 1, C.cast(sc, ptr))
    rs = S.RasterCI(23, None, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1.0)
    ms = S.MultisampleCI(24, None, 0, 1, 0, 0, None, 0, 0)
    ba = (S.BlendAttachment * 1)(S.BlendAttachment(0, 0, 0, 0, 0, 0, 0, 0xF))
    bs = S.BlendCI(26, None, 0, 0, 0, 1, C.cast(ba, ptr), (f32 * 4)(0, 0, 0, 0))
    pci = S.PipelineCI(28, None, 0, 2, C.cast(stages, ptr), C.addressof(vi), C.addressof(ia), None, C.addressof(vps), C.addressof(rs),
                       C.addressof(ms), None, C.addressof(bs), None, layout.value, rp.value, 0, 0, -1)
    pipe = u64(0); print("pipeline (ubo) ->", create_gp(dev, u64(0), 1, C.byref(pci), None, C.byref(pipe)))

    def frame(record_draw):
        def rec():
            clear = (R.ClearValue * 1)(R.ClearValue((f32 * 4)(0.0, 0.0, 0.0, 0.0)))
            begin_rp(cb, C.byref(R.RenderPassBI(43, None, rp.value, fb.value, R.Rect2D(0, 0, W, H), 1, clear)), 0)
            record_draw()
            end_rp(cb)
            b1 = R.ImgMemBarrier(45, None, 0x100, 0x800, 6, 6, 0xFFFFFFFF, 0xFFFFFFFF, img.value, R.ImgSubRange(1, 0, 1, 0, 1))
            barrier(cb, 0x400, 0x1000, 0, 0, None, 0, None, 1, C.byref(b1))
            region = R.BufImgCopy(0, 0, 0, R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
            copy_i2b(cb, img, 6, rb, 1, C.byref(region))
            barrier(cb, 0x1000, 0x4000, 0, 0, None, 0, None, 0, None)
        run(rec)
        invalidate(dev, 1, C.byref(R.MappedRange(6, None, rbmem.value, 0, u64(0xFFFFFFFFFFFFFFFF))))
        return C.string_at(p.value + (H // 2 * W + W // 2) * 4, 4)

    bad = 0
    t = time.time()
    for i in range(N):
        r, g, b = (i * 37) & 255, (i * 91) & 255, (i * 53) & 255
        col = (f32 * 4)(r / 255.0, g / 255.0, b / 255.0, 1.0)
        C.memmove(ubop, col, 16)  # the write, straight through the mapping, no flush (HOST_COHERENT)
        def d():
            bind_pipe(cb, 0, pipe)
            sets = (u64 * 1)(dset.value)
            bind_sets(cb, 0, layout, 0, 1, sets, 0, None)
            draw(cb, 3, 1, 0, 0)
        px = frame(d)
        want = bytes([r, g, b, 255])
        if px != want:
            bad += 1
            if bad <= 5: print(f"  ubo #{i}: got {px.hex()} want {want.hex()}")
    print(f"UBO written through the mapping before each draw: {bad} stale of {N} ({(time.time() - t) * 1000 / N:.1f} ms each)")

    # ---- part 2: a vertex buffer with a colour attribute written right before each draw, DXVK-style
    # ring: each draw's 3 vertices at a new offset, drawn with firstVertex (like DrawPrimitive StartVertex)
    vs2, k3 = module(vcvert); fs2, k4 = module(vcfrag)
    stages2 = (S.StageCI * 2)(S.StageCI(18, None, 0, 1, vs2.value, b"main", None), S.StageCI(18, None, 0, 0x10, fs2.value, b"main", None))
    vib = (VIBinding * 1)(VIBinding(0, 16, 0))  # stride 16: float2 pos + 4 x u8 colour + pad
    via = (VIAttr * 2)(VIAttr(0, 0, 103, 0), VIAttr(1, 0, 37, 8))  # R32G32_SFLOAT at 0, R8G8B8A8_UNORM at 8
    vi2 = S.VertexInputCI(19, None, 0, 1, C.cast(vib, ptr), 2, C.cast(via, ptr))
    layout2 = u64(0); create_pl(dev, C.byref(S.LayoutCI(30, None, 0, 0, None, 0, None)), None, C.byref(layout2))
    pci2 = S.PipelineCI(28, None, 0, 2, C.cast(stages2, ptr), C.addressof(vi2), C.addressof(ia), None, C.addressof(vps), C.addressof(rs),
                        C.addressof(ms), None, C.addressof(bs), None, layout2.value, rp.value, 0, 0, -1)
    pipe2 = u64(0); print("pipeline (vertex colour) ->", create_gp(dev, u64(0), 1, C.byref(pci2), None, C.byref(pipe2)))
    VBSIZE = 1 << 20
    vb, vbmem, vb_type = make_buffer(VBSIZE, 0x80, 0x6)  # VERTEX_BUFFER, HOST_VISIBLE|HOST_COHERENT
    print("vertex buffer in memory type", vb_type, "flags 0x%x" % types[vb_type][1])
    vbp = ptr(); map_mem(dev, vbmem, u64(0), u64(VBSIZE), 0, C.byref(vbp))
    C.memset(vbp, 0, VBSIZE)
    bad = 0
    t = time.time()
    tri = [(-1.0, -1.0), (3.0, -1.0), (-1.0, 3.0)]
    for i in range(N):
        r, g, b = (i * 37) & 255, (i * 91) & 255, (i * 53) & 255
        first = (i * 3) % (VBSIZE // 16 - 3)
        data = b"".join(C.string_at(C.byref((f32 * 2)(x, y)), 8) + bytes([r, g, b, 255]) + b"\0\0\0\0" for x, y in tri)
        C.memmove(vbp.value + first * 16, data, len(data))
        def d2():
            bind_pipe(cb, 0, pipe2)
            bufs = (u64 * 1)(vb.value); offs = (u64 * 1)(0)
            bind_vb(cb, 0, 1, bufs, offs)
            draw(cb, 3, 1, first, 0)
        px = frame(d2)
        want = bytes([r, g, b, 255])
        if px != want:
            bad += 1
            if bad <= 5: print(f"  vb #{i} (firstVertex {first}): got {px.hex()} want {want.hex()}")
    print(f"vertex ring written through the mapping before each draw (firstVertex): {bad} stale of {N} ({(time.time() - t) * 1000 / N:.1f} ms each)")

    # ---- part 3: DXVK's real pattern - many draws in ONE command buffer, each with its own
    # descriptor set (allocated per draw from a pool like DXVK's) pointing at its own 4 KB slice of a
    # uniform ring written just before; each draw scissored to one pixel so one readback checks all.
    set_scissor = dfn("vkCmdSetScissor", None)
    dyn = (u32 * 1)(3)  # VK_DYNAMIC_STATE_SCISSOR
    DynCI = R.struct("DynCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("dynamicStateCount", u32), ("pDynamicStates", ptr)])
    dci3 = DynCI(27, None, 0, 1, C.cast(dyn, ptr))
    pci3 = S.PipelineCI(28, None, 0, 2, C.cast(stages, ptr), C.addressof(vi), C.addressof(ia), None, C.addressof(vps), C.addressof(rs),
                        C.addressof(ms), None, C.addressof(bs), C.addressof(dci3), layout.value, rp.value, 0, 0, -1)
    pipe3 = u64(0); print("pipeline (ubo, dynamic scissor) ->", create_gp(dev, u64(0), 1, C.byref(pci3), None, C.byref(pipe3)))
    M = W * H  # one draw per pixel: 1024 draws, 1024 sets, 4 MB of uniform ring
    ring, ringmem, _ = make_buffer(M * 4096, 0x10, 0x6)
    ringp = ptr(); map_mem(dev, ringmem, u64(0), u64(M * 4096), 0, C.byref(ringp))
    psz3 = (PoolSize * 1)(PoolSize(6, 256))
    pool3 = u64(0); create_pool(dev, C.byref(DescPoolCI(33, None, 0, 256, 1, C.cast(psz3, ptr))), None, C.byref(pool3))
    pools = [pool3]
    sets = []
    for i in range(M):
        ds = u64(0)
        r = alloc_sets(dev, C.byref(DescSetAI(34, None, pools[-1].value, 1, C.cast(dsls, ptr))), C.byref(ds))
        if r != 0:  # pool full: a new one, as DXVK does
            np_ = u64(0); create_pool(dev, C.byref(DescPoolCI(33, None, 0, 256, 1, C.cast(psz3, ptr))), None, C.byref(np_)); pools.append(np_)
            r = alloc_sets(dev, C.byref(DescSetAI(34, None, pools[-1].value, 1, C.cast(dsls, ptr))), C.byref(ds))
            if r != 0: print("set alloc failed", r); break
        sets.append(ds.value)
    print(f"{len(sets)} descriptor sets from {len(pools)} pool(s)")
    for rep in range(3):
        for i, dsv in enumerate(sets):
            r_, g_, b_ = (i * 37 + rep) & 255, (i * 91 + rep * 7) & 255, (i * 53 + rep * 13) & 255
            col = (f32 * 4)(r_ / 255.0, g_ / 255.0, b_ / 255.0, 1.0)
            C.memmove(ringp.value + i * 4096, col, 16)
            bi3 = DescBufInfo(ring.value, i * 4096, 16)
            update_sets(dev, 1, C.byref(WriteDS(35, None, dsv, 0, 0, 1, 6, None, C.addressof(bi3), None)), 0, None)
        def d3():
            bind_pipe(cb, 0, pipe3)
            for i, dsv in enumerate(sets):
                sc1 = (R.Rect2D * 1)(R.Rect2D(i % W, i // W, 1, 1))
                set_scissor(cb, 0, 1, C.cast(sc1, ptr))
                ss = (u64 * 1)(dsv)
                bind_sets(cb, 0, layout, 0, 1, ss, 0, None)
                draw(cb, 3, 1, 0, 0)
        t = time.time()
        frame(d3)
        bad = 0
        for i in range(len(sets)):
            r_, g_, b_ = (i * 37 + rep) & 255, (i * 91 + rep * 7) & 255, (i * 53 + rep * 13) & 255
            px = C.string_at(p.value + i * 4, 4)
            if px != bytes([r_, g_, b_, 255]):
                bad += 1
                if bad <= 4: print(f"  draw {i}: got {px.hex()} want {bytes([r_, g_, b_, 255]).hex()}")
        print(f"rep {rep}: {len(sets)} draws, one set + one 4 KB slice each, in one command buffer: {bad} wrong ({(time.time() - t) * 1000:.0f} ms)")


if __name__ == "__main__":
    main()
