#!/usr/bin/env python3
"""Specialization-constant test through the Mali bridge: a full-screen triangle drawn with a
fragment shader whose output depends on three spec constants (int branch, float arithmetic, bool
select). Each shader is run twice: unspecialized (defaults -> black) and specialized to MODE=1,
GAIN=1.0, SEL=true (-> white). A driver that folds spec constants at their defaults answers black
for the specialized pipeline. Shader files are given on the command line (vertex first).
Reuses the helpers of vkreadback.py by import.
"""
import ctypes as C
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vkreadback as R  # noqa: E402

u32, u64, ptr, f32, i32 = C.c_uint32, C.c_uint64, C.c_void_p, C.c_float, C.c_int32
ShaderModuleCI = R.struct("ShaderModuleCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("codeSize", u64), ("pCode", ptr)])
SpecMapEntry = R.struct("SpecMapEntry", [("constantID", u32), ("offset", u32), ("size", u64)])
SpecInfo = R.struct("SpecInfo", [("mapEntryCount", u32), ("pMapEntries", ptr), ("dataSize", u64), ("pData", ptr)])
StageCI = R.struct("StageCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("stage", u32), ("module", u64), ("pName", C.c_char_p),
                               ("pSpecializationInfo", ptr)])
VertexInputCI = R.struct("VertexInputCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("bindingCount", u32), ("pBindings", ptr),
                                           ("attrCount", u32), ("pAttrs", ptr)])
InputAsmCI = R.struct("InputAsmCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("topology", u32), ("primitiveRestartEnable", u32)])
Viewport = R.struct("Viewport", [("x", f32), ("y", f32), ("w", f32), ("h", f32), ("minDepth", f32), ("maxDepth", f32)])
ViewportCI = R.struct("ViewportCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("viewportCount", u32), ("pViewports", ptr),
                                     ("scissorCount", u32), ("pScissors", ptr)])
RasterCI = R.struct("RasterCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("depthClampEnable", u32), ("rasterizerDiscardEnable", u32),
                                 ("polygonMode", u32), ("cullMode", u32), ("frontFace", u32), ("depthBiasEnable", u32),
                                 ("depthBiasConstantFactor", f32), ("depthBiasClamp", f32), ("depthBiasSlopeFactor", f32), ("lineWidth", f32)])
MultisampleCI = R.struct("MultisampleCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("rasterizationSamples", u32),
                                           ("sampleShadingEnable", u32), ("minSampleShading", f32), ("pSampleMask", ptr),
                                           ("alphaToCoverageEnable", u32), ("alphaToOneEnable", u32)])
BlendAttachment = R.struct("BlendAttachment", [("blendEnable", u32), ("srcColor", u32), ("dstColor", u32), ("colorOp", u32), ("srcAlpha", u32),
                                               ("dstAlpha", u32), ("alphaOp", u32), ("colorWriteMask", u32)])
BlendCI = R.struct("BlendCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("logicOpEnable", u32), ("logicOp", u32),
                               ("attachmentCount", u32), ("pAttachments", ptr), ("blendConstants", f32 * 4)])
LayoutCI = R.struct("LayoutCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("setLayoutCount", u32), ("pSetLayouts", ptr),
                                 ("pushConstantRangeCount", u32), ("pPushConstantRanges", ptr)])
PipelineCI = R.struct("PipelineCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("stageCount", u32), ("pStages", ptr),
                                     ("pVertexInputState", ptr), ("pInputAssemblyState", ptr), ("pTessellationState", ptr),
                                     ("pViewportState", ptr), ("pRasterizationState", ptr), ("pMultisampleState", ptr),
                                     ("pDepthStencilState", ptr), ("pColorBlendState", ptr), ("pDynamicState", ptr), ("layout", u64),
                                     ("renderPass", u64), ("subpass", u32), ("basePipelineHandle", u64), ("basePipelineIndex", i32)])

W = H = 64
FMT = 37  # R8G8B8A8_UNORM


def main():
    VK = R.VK
    vert_path, frag_paths = sys.argv[1], sys.argv[2:]
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

    def make_image(w, h, fmt, usage):
        img = u64(0)
        ci = R.ImageCI(14, None, 0, 1, fmt, R.Extent3D(w, h, 1), 1, 1, 1, 0, usage, 0, 0, None, 0)
        r = create_image(dev, C.byref(ci), None, C.byref(img))
        rq = R.MemReqs(); get_ireq(dev, img, C.byref(rq))
        mt = dev_type if (rq.memoryTypeBits >> dev_type) & 1 else [i for i, f in types if (rq.memoryTypeBits >> i) & 1][0]
        mem = u64(0)
        alloc(dev, C.byref(R.MemAllocInfo(5, None, rq.size, mt)), None, C.byref(mem))
        bind_i(dev, img, mem, u64(0))
        return img, r

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
        r = create_sm(dev, C.byref(ShaderModuleCI(16, None, 0, len(code), C.cast(buf, ptr))), None, C.byref(sm))
        return sm, r, buf

    # render pass: one colour attachment, cleared, left in TRANSFER_SRC for the readback
    att = (R.AttachDesc * 1)(R.AttachDesc(0, FMT, 1, 1, 0, 2, 1, 0, 6))
    ref = (R.AttachRef * 1)(R.AttachRef(0, 2))
    sub = (R.SubpassDesc * 1)(R.SubpassDesc(0, 0, 0, None, 1, ref, None, None, 0, None))
    rp = u64(0); print("vkCreateRenderPass ->", create_rp(dev, C.byref(R.RenderPassCI(38, None, 0, 1, att, 1, sub, 0, None)), None, C.byref(rp)))
    img, r = make_image(W, H, FMT, 0x10 | 0x1)
    view = u64(0)
    print("vkCreateImageView ->", create_view(dev, C.byref(R.ImageViewCI(15, None, 0, img.value, 1, FMT, (u32 * 4)(0, 0, 0, 0),
                                                                           R.ImgSubRange(1, 0, 1, 0, 1))), None, C.byref(view)))
    views = (u64 * 1)(view.value)
    fb = u64(0); print("vkCreateFramebuffer ->", create_fb(dev, C.byref(R.FramebufferCI(37, None, 0, rp.value, 1, views, W, H, 1)), None, C.byref(fb)))
    layout = u64(0); print("vkCreatePipelineLayout ->", create_pl(dev, C.byref(LayoutCI(30, None, 0, 0, None, 0, None)), None, C.byref(layout)))
    vs, r, vs_keep = module(vert_path)
    print("vertex module ->", r)

    # specialization: MODE=1 (int), GAIN=1.0 (float), SEL=true (VkBool32 = 1)
    entries = (SpecMapEntry * 3)(SpecMapEntry(0, 0, 4), SpecMapEntry(1, 4, 4), SpecMapEntry(2, 8, 4))
    data = (C.c_uint8 * 12)()
    C.memmove(data, C.byref(i32(1)), 4); C.memmove(C.addressof(data) + 4, C.byref(f32(1.0)), 4); C.memmove(C.addressof(data) + 8, C.byref(u32(1)), 4)
    spec = SpecInfo(3, C.cast(entries, ptr), 12, C.cast(data, ptr))
    # the DXVK-pattern shaders: BITS=5, B0=true, B1=true, F=0.7, SW=2
    entries5 = (SpecMapEntry * 5)(*[SpecMapEntry(i, 4 * i, 4) for i in range(5)])
    data5 = (C.c_uint8 * 20)()
    for i, v in enumerate((u32(5), u32(1), u32(1), f32(0.7), u32(2))):
        C.memmove(C.addressof(data5) + 4 * i, C.byref(v), 4)
    spec5 = SpecInfo(5, C.cast(entries5, ptr), 20, C.cast(data5, ptr))

    vi = VertexInputCI(19, None, 0, 0, None, 0, None)
    ia = InputAsmCI(20, None, 0, 3, 0)
    vp = (Viewport * 1)(Viewport(0, 0, W, H, 0, 1))
    sc = (R.Rect2D * 1)(R.Rect2D(0, 0, W, H))
    vps = ViewportCI(22, None, 0, 1, C.cast(vp, ptr), 1, C.cast(sc, ptr))
    rs = RasterCI(23, None, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1.0)
    ms = MultisampleCI(24, None, 0, 1, 0, 0, None, 0, 0)
    ba = (BlendAttachment * 1)(BlendAttachment(0, 0, 0, 0, 0, 0, 0, 0xF))
    bs = BlendCI(26, None, 0, 0, 0, 1, C.cast(ba, ptr), (f32 * 4)(0, 0, 0, 0))

    buf, bmem = make_buffer(W * H * 4, 0x2)

    for frag_path in frag_paths:
        fs, r, fs_keep = module(frag_path)
        print(f"\n== fragment {os.path.basename(frag_path)} (module -> {r})")
        dx = os.path.basename(frag_path).startswith("dx")
        cases = (("defaults (no specialization)", None, "00000000"), ("specialized BITS=5 B0=B1=true F=0.7 SW=2", spec5, "ffffffff")) if dx else                 (("defaults (no specialization)", None, "000000ff"), ("specialized MODE=1 GAIN=1 SEL=true", spec, "ffffffff"))
        for label, sinfo, expect in cases:
            vs_spec = C.cast(C.pointer(sinfo), ptr) if (sinfo and os.environ.get("VKSPEC_VS") == "1") else None
            stages = (StageCI * 2)(StageCI(18, None, 0, 1, vs.value, b"main", vs_spec),
                                   StageCI(18, None, 0, 0x10, fs.value, b"main", C.cast(C.pointer(sinfo), ptr) if sinfo else None))
            pci = PipelineCI(28, None, 0, 2, C.cast(stages, ptr), C.addressof(vi), C.addressof(ia), None, C.addressof(vps), C.addressof(rs),
                             C.addressof(ms), None, C.addressof(bs), None, layout.value, rp.value, 0, 0, -1)
            pipe = u64(0)
            t = time.time()
            r = create_gp(dev, u64(0), 1, C.byref(pci), None, C.byref(pipe))
            ms_build = round((time.time() - t) * 1000)
            if r != 0:
                print(f"   {label}: vkCreateGraphicsPipelines -> {r}")
                continue
            p = ptr(); map_mem(dev, bmem, u64(0), u64(W * H * 4), 0, C.byref(p)); C.memset(p, 0x77, W * H * 4); unmap(dev, bmem)

            def rec():
                clear = (R.ClearValue * 1)(R.ClearValue((f32 * 4)(0.25, 0.5, 0.75, 1.0)))
                begin_rp(cb, C.byref(R.RenderPassBI(43, None, rp.value, fb.value, R.Rect2D(0, 0, W, H), 1, clear)), 0)
                bind_pipe(cb, 0, pipe)
                draw(cb, 3, 1, 0, 0)
                end_rp(cb)
                # colour writes -> transfer read (the render pass ends in TRANSFER_SRC_OPTIMAL already)
                b1 = R.ImgMemBarrier(45, None, 0x100, 0x800, 6, 6, 0xFFFFFFFF, 0xFFFFFFFF, img.value, R.ImgSubRange(1, 0, 1, 0, 1))
                barrier(cb, 0x400, 0x1000, 0, 0, None, 0, None, 1, C.byref(b1))
                region = R.BufImgCopy(0, 0, 0, R.ImgSubLayers(1, 0, 0, 1), R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
                copy_i2b(cb, img, 6, buf, 1, C.byref(region))
                # transfer write -> host read
                mb = (u32 * 4)(46, 0, 0x1000, 0x2000)  # VkMemoryBarrier{sType, pNext(low), src, dst} on 64-bit needs real layout:
                barrier(cb, 0x1000, 0x4000, 0, 0, None, 0, None, 0, None)
            rs_, rw = run(rec)
            map_mem(dev, bmem, u64(0), u64(W * H * 4), 0, C.byref(p))
            invalidate(dev, 1, C.byref(R.MappedRange(6, None, bmem.value, 0, u64(0xFFFFFFFFFFFFFFFF))))
            px = C.string_at(p.value + (H // 2 * W + W // 2) * 4, 4)
            corner = C.string_at(p.value, 4)
            unmap(dev, bmem)
            ok = px.hex() == expect
            print(f"   {label}: pipeline {ms_build} ms, submit {rs_}/{rw}, centre {px.hex()} corner {corner.hex()} expected {expect} -> {'OK' if ok else 'WRONG'}")


if __name__ == "__main__":
    main()
