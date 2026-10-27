#!/usr/bin/env python3
"""Two probes through the Mali bridge for Ys Origin's effect sprites.

Part A, textures: 2x2 textures in the 16-bit packed formats DXVK uses for D3DFMT_A1R5G5B5
(A1R5G5B5_UNORM_PACK16, identity swizzle), D3DFMT_A4R4G4B4 (B4G4R4A4_UNORM_PACK16 with the
swizzle G,R,A,B) and D3DFMT_R5G6B5, sampled onto a 2x2 target: every output pixel is one texel.
Part B, draws: a 4-vertex TRIANGLE_STRIP quad (and a 6-vertex list) with the game's vertex layout
(float3 pos, two B8G8R8A8_UNORM colours, float2 uv, stride 28) from a host-visible vertex buffer,
drawn with firstVertex 562 (and with a binding offset), additive blending like the game.
Args: strip.vert strip.frag tri.vert tex2.frag
"""
import ctypes as C
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vkreadback as R  # noqa: E402
import vkspec as S  # noqa: E402
import vkcoh as K  # noqa: E402

u32, u64, ptr, f32, i32 = C.c_uint32, C.c_uint64, C.c_void_p, C.c_float, C.c_int32
SamplerCI = R.struct("SamplerCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("magFilter", u32), ("minFilter", u32), ("mipmapMode", u32),
                                   ("addressModeU", u32), ("addressModeV", u32), ("addressModeW", u32), ("mipLodBias", f32),
                                   ("anisotropyEnable", u32), ("maxAnisotropy", f32), ("compareEnable", u32), ("compareOp", u32),
                                   ("minLod", f32), ("maxLod", f32), ("borderColor", u32), ("unnormalizedCoordinates", u32)])
DescImageInfo = R.struct("DescImageInfo", [("sampler", u64), ("imageView", u64), ("imageLayout", u32)])
FMT = 44  # B8G8R8A8_UNORM target, bytes B G R A
TS = int(os.environ.get("VKA_TEX", "2"))  # texture size: 2 = one texel per output pixel, 128 = AFBC-sized quadrants
FILT = int(os.environ.get("VKA_FILTER", "0"))  # sampler filter: 0 nearest, 1 linear


def main():
    VK = R.VK
    vert_path, frag_path, tri_path, tex_path = sys.argv[1:5]
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
    copy_i2b, copy_b2i = dfn("vkCmdCopyImageToBuffer", None), dfn("vkCmdCopyBufferToImage", None)
    barrier = dfn("vkCmdPipelineBarrier", None)
    invalidate = dfn("vkInvalidateMappedMemoryRanges")
    submit, create_fence, wait_fence, reset_fence = dfn("vkQueueSubmit"), dfn("vkCreateFence"), dfn("vkWaitForFences"), dfn("vkResetFences")
    fence = u64(0); create_fence(dev, C.byref(R.FenceCI(8, None, 0)), None, C.byref(fence))
    create_rp, create_view, create_fb = dfn("vkCreateRenderPass"), dfn("vkCreateImageView"), dfn("vkCreateFramebuffer")
    begin_rp, end_rp = dfn("vkCmdBeginRenderPass", None), dfn("vkCmdEndRenderPass", None)
    create_sm, create_pl, create_gp = dfn("vkCreateShaderModule"), dfn("vkCreatePipelineLayout"), dfn("vkCreateGraphicsPipelines")
    bind_pipe, draw = dfn("vkCmdBindPipeline", None), dfn("vkCmdDraw", None)
    create_dsl, create_pool, alloc_sets, update_sets = dfn("vkCreateDescriptorSetLayout"), dfn("vkCreateDescriptorPool"), dfn("vkAllocateDescriptorSets"), dfn("vkUpdateDescriptorSets", None)
    bind_sets, bind_vb, create_sampler = dfn("vkCmdBindDescriptorSets", None), dfn("vkCmdBindVertexBuffers", None), dfn("vkCreateSampler")

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
        if r:
            print("   vkCreateImage fmt", fmt, "->", r)
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
        keep = C.create_string_buffer(code, len(code))
        sm = u64(0)
        r = create_sm(dev, C.byref(S.ShaderModuleCI(16, None, 0, len(code), C.cast(keep, ptr))), None, C.byref(sm))
        return sm, keep

    def img_barrier(img, src_access, dst_access, old, new, src_stage, dst_stage):
        b = R.ImgMemBarrier(45, None, src_access, dst_access, old, new, 0xFFFFFFFF, 0xFFFFFFFF, img.value, R.ImgSubRange(1, 0, 1, 0, 1))
        barrier(cb, src_stage, dst_stage, 0, 0, None, 0, None, 1, C.byref(b))

    layers = R.ImgSubLayers(1, 0, 0, 1)
    rb_buf, rb_mem = make_buffer(64 * 64 * 4, 0x2)

    def pixels(img, w, h, points):
        p = ptr(); map_mem(dev, rb_mem, u64(0), u64(w * h * 4), 0, C.byref(p)); C.memset(p, 0x77, w * h * 4); unmap(dev, rb_mem)

        def rec():
            region = R.BufImgCopy(0, 0, 0, layers, R.Offset3D(0, 0, 0), R.Extent3D(w, h, 1))
            copy_i2b(cb, img, 6, rb_buf, 1, C.byref(region))
            barrier(cb, 0x1000, 0x4000, 0, 0, None, 0, None, 0, None)
        run(rec)
        map_mem(dev, rb_mem, u64(0), u64(w * h * 4), 0, C.byref(p))
        invalidate(dev, 1, C.byref(R.MappedRange(6, None, rb_mem.value, 0, u64(0xFFFFFFFFFFFFFFFF))))
        out = [C.string_at(p.value + (y * w + x) * 4, 4).hex() for (x, y) in points]
        unmap(dev, rb_mem)
        return out

    def target(w, h):
        """render pass + framebuffer on a fresh B8G8R8A8 image, cleared to 0, ending in TRANSFER_SRC"""
        att = (R.AttachDesc * 1)(R.AttachDesc(0, FMT, 1, 1, 0, 2, 1, 0, 6))
        ref = (R.AttachRef * 1)(R.AttachRef(0, 2))
        sub = (R.SubpassDesc * 1)(R.SubpassDesc(0, 0, 0, None, 1, ref, None, None, 0, None))
        rp = u64(0); create_rp(dev, C.byref(R.RenderPassCI(38, None, 0, 1, att, 1, sub, 0, None)), None, C.byref(rp))
        img = make_image(w, h, FMT, 0x10 | 0x1)
        view = u64(0)
        create_view(dev, C.byref(R.ImageViewCI(15, None, 0, img.value, 1, FMT, (u32 * 4)(0, 0, 0, 0), R.ImgSubRange(1, 0, 1, 0, 1))), None, C.byref(view))
        views = (u64 * 1)(view.value)
        fb = u64(0); create_fb(dev, C.byref(R.FramebufferCI(37, None, 0, rp.value, 1, views, w, h, 1)), None, C.byref(fb))
        return rp, fb, img

    def pipeline(vs, fs, rp, w, h, vi, topology, layout, blend):
        stages = (S.StageCI * 2)(S.StageCI(18, None, 0, 1, vs.value, b"main", None), S.StageCI(18, None, 0, 0x10, fs.value, b"main", None))
        ia = S.InputAsmCI(20, None, 0, topology, 0)
        vp = (S.Viewport * 1)(S.Viewport(0, 0, w, h, 0, 1))
        sc = (R.Rect2D * 1)(R.Rect2D(0, 0, w, h))
        vps = S.ViewportCI(22, None, 0, 1, C.cast(vp, ptr), 1, C.cast(sc, ptr))
        rs = S.RasterCI(23, None, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1.0)
        ms = S.MultisampleCI(24, None, 0, 1, 0, 0, None, 0, 0)
        # blend: SRC_ALPHA (6) / ONE (1) add, like the game's additive sprites, or off
        ba = (S.BlendAttachment * 1)(S.BlendAttachment(1, 6, 1, 0, 6, 1, 0, 0xF) if blend else S.BlendAttachment(0, 0, 0, 0, 0, 0, 0, 0xF))
        bs = S.BlendCI(26, None, 0, 0, 0, 1, C.cast(ba, ptr), (f32 * 4)(0, 0, 0, 0))
        pci = S.PipelineCI(28, None, 0, 2, C.cast(stages, ptr), C.addressof(vi), C.addressof(ia), None, C.addressof(vps), C.addressof(rs),
                           C.addressof(ms), None, C.addressof(bs), None, layout.value, rp.value, 0, 0, -1)
        pipe = u64(0)
        r = create_gp(dev, u64(0), 1, C.byref(pci), None, C.byref(pipe))
        if r:
            print("   vkCreateGraphicsPipelines ->", r)
        return pipe, (stages, ia, vps, rs, ms, ba, bs, vp, sc)

    # ------------------------------------------------------------------ part A: 16-bit textures
    print("\n== part A: 16-bit packed textures sampled texel for texel")
    tri, k1 = module(tri_path)
    texfs, k2 = module(tex_path)
    dsb = (K.DSLBinding * 1)(K.DSLBinding(0, 1, 1, 0x10, None))  # COMBINED_IMAGE_SAMPLER, fragment
    dsl = u64(0); create_dsl(dev, C.byref(K.DSLCI(32, None, 0, 1, C.cast(dsb, ptr))), None, C.byref(dsl))
    dsls = (u64 * 1)(dsl.value)
    layoutA = u64(0); create_pl(dev, C.byref(S.LayoutCI(30, None, 0, 1, C.cast(dsls, ptr), 0, None)), None, C.byref(layoutA))
    psz = (K.PoolSize * 1)(K.PoolSize(1, 8))
    pool = u64(0); create_pool(dev, C.byref(K.DescPoolCI(33, None, 0, 8, 1, C.cast(psz, ptr))), None, C.byref(pool))
    sampler = u64(0); create_sampler(dev, C.byref(SamplerCI(31, None, 0, FILT, FILT, 0, 2, 2, 2, 0, 0, 1, 0, 0, 0, 0, 0, 0)), None, C.byref(sampler))
    rpA, fbA, imgA = target(2, 2)
    viA = S.VertexInputCI(19, None, 0, 0, None, 0, None)
    up_buf, up_mem = make_buffer(max(4096, TS * TS * 4), 0x1)
    cases = [
        # name, VkFormat, swizzle (0 = identity, else R=3 G=4 B=5 A=6), 4 texel u16 values, expected B G R A hex per pixel
        ("A1R5G5B5_PACK16 (D3DFMT_A1R5G5B5)", 6, (0, 0, 0, 0), [0xFC00, 0x03E0, 0x001F, 0x7FFF],
         ["0000ffff", "00ff0000", "ff000000", "ffffff00"]),
        ("B4G4R4A4_PACK16 swizzle G,R,A,B (D3DFMT_A4R4G4B4)", 3, (4, 3, 6, 5), [0xFF00, 0x00F0, 0x000F, 0x0FFF],
         ["0000ffff", "00ff0000", "ff000000", "ffffff00"]),
        ("R5G6B5_PACK16 (D3DFMT_R5G6B5)", 4, (0, 0, 0, 0), [0xF800, 0x07E0, 0x001F, 0xFFFF],
         ["0000ffff", "00ff00ff", "ff0000ff", "ffffffff"]),
        ("B8G8R8A8_UNORM reference (D3DFMT_A8R8G8B8)", 44, (0, 0, 0, 0), None, ["0000ffff", "00ff0000", "ff000000", "ffffff00"]),
        # the same A1R5G5B5 bytes through the sister formats: what does the driver really read?
        ("R5G5B5A1_PACK16 (7) with A1R5G5B5 bytes", 7, (0, 0, 0, 0), [0xFC00, 0x03E0, 0x001F, 0x8000], None),
        ("B5G5R5A1_PACK16 (8) with A1R5G5B5 bytes", 8, (0, 0, 0, 0), [0xFC00, 0x03E0, 0x001F, 0x8000], None),
        ("A1R5G5B5_PACK16 (6) bit-rotated bytes (v<<1|v>>15)", 6, (0, 0, 0, 0), [0xF801, 0x07C0, 0x003E, 0xFFFE],
         ["0000ffff", "00ff0000", "ff000000", "ffffff00"]),
        ("A1R5G5B5_PACK16 (6) alpha-only texels", 6, (0, 0, 0, 0), [0x8000, 0x0000, 0x8001, 0x0001], None),
    ]
    for name, fmt, swz, texels, expect in cases:
        tex = make_image(TS, TS, fmt, 0x4 | 0x2 | 0x1)  # SAMPLED | TRANSFER_DST | TRANSFER_SRC
        view = u64(0)
        r = create_view(dev, C.byref(R.ImageViewCI(15, None, 0, tex.value, 1, fmt, (u32 * 4)(*swz), R.ImgSubRange(1, 0, 1, 0, 1))), None, C.byref(view))
        p = ptr(); map_mem(dev, up_mem, u64(0), u64(TS * TS * 4), 0, C.byref(p))
        px = [struct.pack("<H", v) for v in texels] if texels is not None else [bytes.fromhex(h) for h in ("0000ffff", "00ff0000", "ff000000", "ffffff00")]
        rows = b""
        for y in range(TS):
            row = b""
            for x in range(TS):
                row += px[(2 * y // TS) * 2 + (2 * x // TS)]
            rows += row
        C.memmove(p, rows, len(rows))
        unmap(dev, up_mem)
        dset = u64(0); alloc_sets(dev, C.byref(K.DescSetAI(34, None, pool.value, 1, C.cast(dsls, ptr))), C.byref(dset))
        dii = DescImageInfo(sampler.value, view.value, 5)
        update_sets(dev, 1, C.byref(K.WriteDS(35, None, dset.value, 0, 0, 1, 1, C.addressof(dii), None, None)), 0, None)
        pipe, keep = pipeline(tri, texfs, rpA, 2, 2, viA, 3, layoutA, False)

        def rec():
            img_barrier(tex, 0, 0x1000, 0, 7, 0x1, 0x1000)
            region = R.BufImgCopy(0, 0, 0, layers, R.Offset3D(0, 0, 0), R.Extent3D(TS, TS, 1))
            copy_b2i(cb, up_buf, tex, 7, 1, C.byref(region))
            img_barrier(tex, 0x1000, 0x20, 7, 5, 0x1000, 0x80)
            clear = (R.ClearValue * 1)(R.ClearValue((f32 * 4)(0, 0, 0, 0)))
            begin_rp(cb, C.byref(R.RenderPassBI(43, None, rpA.value, fbA.value, R.Rect2D(0, 0, 2, 2), 1, clear)), 0)
            bind_pipe(cb, 0, pipe)
            ss = (u64 * 1)(dset.value)
            bind_sets(cb, 0, layoutA, 0, 1, ss, 0, None)
            draw(cb, 3, 1, 0, 0)
            end_rp(cb)
            img_barrier(imgA, 0x100, 0x800, 6, 6, 0x400, 0x1000)
        rs_, rw = run(rec)
        got = pixels(imgA, 2, 2, [(0, 0), (1, 0), (0, 1), (1, 1)])
        ok = expect is None or got == expect
        print(f"   {name}: view {r}, submit {rs_}/{rw}: got {' '.join(got)} want {' '.join(expect) if expect else '(see)'} -> {'OK' if ok else 'WRONG'}")
        if texels is not None and fmt != 44:
            p2 = ptr(); map_mem(dev, rb_mem, u64(0), u64(64), 0, C.byref(p2)); C.memset(p2, 0x77, 64); unmap(dev, rb_mem)

            def rec2():
                img_barrier(tex, 0x20, 0x800, 5, 6, 0x80, 0x1000)
                region = R.BufImgCopy(0, 0, 0, layers, R.Offset3D(0, 0, 0), R.Extent3D(2, 2, 1))
                copy_i2b(cb, tex, 6, rb_buf, 1, C.byref(region))  # the top-left 2x2 (one quadrant when TS > 2)
                barrier(cb, 0x1000, 0x4000, 0, 0, None, 0, None, 0, None)
            run(rec2)
            map_mem(dev, rb_mem, u64(0), u64(64), 0, C.byref(p2))
            invalidate(dev, 1, C.byref(R.MappedRange(6, None, rb_mem.value, 0, u64(0xFFFFFFFFFFFFFFFF))))
            back = struct.unpack("<4H", C.string_at(p2.value, 8))
            unmap(dev, rb_mem)
            print(f"      texels read back from the image: {' '.join('%04x' % v for v in back)} (uploaded {' '.join('%04x' % v for v in texels)})")

    # ------------------------------------------------------------------ part B: the game's strip draws
    print("\n== part B: 4-vertex strips from a dynamic vertex buffer, firstVertex 562, stride 28")
    vs, k3 = module(vert_path)
    fs, k4 = module(frag_path)
    layoutB = u64(0); create_pl(dev, C.byref(S.LayoutCI(30, None, 0, 0, None, 0, None)), None, C.byref(layoutB))
    W = H = 64
    rpB, fbB, imgB = target(W, H)
    vib = (K.VIBinding * 1)(K.VIBinding(0, 28, 0))
    via = (K.VIAttr * 4)(K.VIAttr(0, 0, 106, 0), K.VIAttr(1, 0, 44, 12), K.VIAttr(2, 0, 44, 16), K.VIAttr(3, 0, 103, 20))
    viB = S.VertexInputCI(19, None, 0, 1, C.cast(vib, ptr), 4, C.cast(via, ptr))
    VB = 114688  # the game's buffer size
    vbuf, vmem = make_buffer(VB, 0x80)
    vp_ = ptr(); map_mem(dev, vmem, u64(0), u64(VB), 0, C.byref(vp_)); C.memset(vp_, 0, VB)
    colour = bytes.fromhex("488fff87")  # D3DCOLOR 0x87ff8f48 in memory: B G R A
    want = "488fff87"  # target B8G8R8A8 bytes, blend ONE onto 0 with src alpha... see below

    def vertex(x, y):
        return struct.pack("<fff", x, y, 0.0) + colour + colour + struct.pack("<ff", 0.0, 0.0)
    strip = b"".join(vertex(x, y) for x, y in ((-0.5, 0.5), (-0.5, -0.5), (0.5, 0.5), (0.5, -0.5)))
    lst = b"".join(vertex(x, y) for x, y in ((-0.5, 0.5), (-0.5, -0.5), (0.5, 0.5), (0.5, 0.5), (-0.5, -0.5), (0.5, -0.5)))
    # the game's billboards: DrawIndexedPrimitive(BaseVertexIndex 448, 6 vertices, 2 triangles) -> vkCmdDrawIndexed with vertexOffset
    bind_ib, draw_indexed = dfn("vkCmdBindIndexBuffer", None), dfn("vkCmdDrawIndexed", None)
    ibuf, imem = make_buffer(4096, 0x40)  # INDEX_BUFFER
    ip = ptr(); map_mem(dev, imem, u64(0), u64(4096), 0, C.byref(ip)); C.memmove(ip, struct.pack("<6H", 0, 1, 2, 2, 1, 3), 12)
    C.memmove(ip.value + 1024, struct.pack("<6H", 0, 1, 2, 2, 1, 3), 12); unmap(dev, imem)
    tests = [("indexed list, vertexOffset 448, index offset 0", 3, -6, 448, 0, strip),
             ("indexed list, vertexOffset 448, index offset 1024", 3, -6, 448, 1024, strip),
             ("indexed list, vertexOffset 0, bind offset 12544", 3, -6, 0, 12544, strip),
             ("strip, firstVertex 562, bind offset 0", 4, 4, 562, 0, strip),
             ("list, firstVertex 466, bind offset 0", 3, 6, 466, 0, lst),
             ("strip, firstVertex 562, bind offset 57344", 4, 4, 562, 57344, strip),
             ("strip, firstVertex 0, bind offset 15736", 4, 4, 0, 15736, strip)]
    # NaN positions, as Ys Origin's dead particles have (their world matrix is NaN): the PC draws nothing
    nanq = b"".join(struct.pack("<fff", float("nan"), float("nan"), float("nan")) + colour + colour + struct.pack("<ff", 0.0, 0.0) for _ in range(4))
    nan1 = vertex(-0.5, 0.5) + vertex(-0.5, -0.5) + vertex(0.5, 0.5) + struct.pack("<fff", float("nan"), float("nan"), float("nan")) + colour + colour + struct.pack("<ff", 0.0, 0.0)
    # with stripw.vert (VKA_VSW): gl_Position = (pos.x, pos.y, uv.x, pos.z): w from the attribute
    NAN = float("nan")
    def vw(x, y, w, z=0.0):
        return struct.pack("<fff", x, y, w) + colour + colour + struct.pack("<ff", z, 0.0)
    vsw = module(os.environ["VKA_VSW"])[0] if os.environ.get("VKA_VSW") else None
    cases_nan = [("strip of 4 NaN vertices", nanq, vs), ("strip with one NaN vertex", nan1, vs)]
    if vsw:
        cases_nan += [("w = NaN on all 4 (x, y finite)", b"".join(vw(x, y, NAN) for x, y in ((-0.5, 0.5), (-0.5, -0.5), (0.5, 0.5), (0.5, -0.5))), vsw),
                      ("x, y, w all NaN", b"".join(vw(NAN, NAN, NAN) for _ in range(4)), vsw),
                      ("z = NaN, w = 1", b"".join(vw(x, y, 1.0, NAN) for x, y in ((-0.5, 0.5), (-0.5, -0.5), (0.5, 0.5), (0.5, -0.5))), vsw),
                      ("control: w = 1 (quad drawn)", b"".join(vw(x, y, 1.0) for x, y in ((-0.5, 0.5), (-0.5, -0.5), (0.5, 0.5), (0.5, -0.5))), vsw)]
    for name, data, vsx in cases_nan:
        C.memset(vp_, 0, VB)
        C.memmove(vp_.value + 562 * 28, data, len(data))
        pipe, keep = pipeline(vsx, fs, rpB, W, H, viB, 4, layoutB, True)

        def recn():
            clear = (R.ClearValue * 1)(R.ClearValue((f32 * 4)(0, 0, 0, 0)))
            begin_rp(cb, C.byref(R.RenderPassBI(43, None, rpB.value, fbB.value, R.Rect2D(0, 0, W, H), 1, clear)), 0)
            bind_pipe(cb, 0, pipe)
            bufs = (u64 * 1)(vbuf.value); offs = (u64 * 1)(0)
            bind_vb(cb, 0, 1, bufs, offs)
            draw(cb, 4, 1, 562, 0)
            end_rp(cb)
            img_barrier(imgB, 0x100, 0x800, 6, 6, 0x400, 0x1000)
        run(recn)
        p = ptr(); map_mem(dev, rb_mem, u64(0), u64(W * H * 4), 0, C.byref(p)); C.memset(p, 0x77, W * H * 4); unmap(dev, rb_mem)

        def recr():
            region = R.BufImgCopy(0, 0, 0, layers, R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
            copy_i2b(cb, imgB, 6, rb_buf, 1, C.byref(region))
            barrier(cb, 0x1000, 0x4000, 0, 0, None, 0, None, 0, None)
        run(recr)
        map_mem(dev, rb_mem, u64(0), u64(W * H * 4), 0, C.byref(p))
        invalidate(dev, 1, C.byref(R.MappedRange(6, None, rb_mem.value, 0, u64(0xFFFFFFFFFFFFFFFF))))
        raw = C.string_at(p.value, W * H * 4)
        unmap(dev, rb_mem)
        lit = sum(1 for i in range(0, len(raw), 4) if raw[i:i + 4] != bytes(4))
        print(f"   {name}: {lit} of {W * H} pixels written -> {'OK (nothing drawn)' if lit == 0 else 'DRAWN'}")
    # the frame's sequence: sprite buffer bound (stride-28 pipeline), a draw; another buffer with a stride-48
    # pipeline, a draw; the sprite buffer bound again, a strip at firstVertex 562 - all in one command buffer
    print("   -- rebind sequence: A(28) draw, B(48) draw, A(28) strip@562, one command buffer")
    vib48 = (K.VIBinding * 1)(K.VIBinding(0, 48, 0))
    via48 = (K.VIAttr * 4)(K.VIAttr(0, 0, 106, 0), K.VIAttr(1, 0, 44, 24), K.VIAttr(2, 0, 44, 28), K.VIAttr(3, 0, 103, 32))
    vi48 = S.VertexInputCI(19, None, 0, 1, C.cast(vib48, ptr), 4, C.cast(via48, ptr))
    bbuf, bmem = make_buffer(VB, 0x80)
    bp = ptr(); map_mem(dev, bmem, u64(0), u64(VB), 0, C.byref(bp))
    # B: a 48-byte-stride "mesh" quad top-right, with large values everywhere else (what a wrong fetch would show)
    C.memset(bp, 0x7f, VB)  # 0x7f7f7f7f floats: huge
    def v48(x, y):
        return struct.pack("<fff", x, y, 0.0) + struct.pack("<fff", 0, 0, 1) + bytes.fromhex("ff00ff00") + bytes.fromhex("00000000") + struct.pack("<ff", 0, 0) + struct.pack("<ff", 0, 0)
    C.memmove(bp, b"".join(v48(x, y) for x, y in ((0.1, 0.9), (0.1, 0.1), (0.9, 0.9), (0.9, 0.1))), 4 * 48)
    unmap(dev, bmem)
    C.memset(vp_, 0, VB)
    shadow = b"".join(vertex(x, y) for x, y in ((-0.9, 0.9), (-0.9, 0.1), (-0.1, 0.9), (-0.1, 0.1)))   # top-left, at 466
    part = b"".join(vertex(x, y) for x, y in ((0.1, -0.1), (0.1, -0.9), (0.9, -0.1), (0.9, -0.9)))     # bottom-right, at 562
    C.memmove(vp_.value + 466 * 28, shadow, len(shadow))
    C.memmove(vp_.value + 562 * 28, part, len(part))
    p28, k28 = pipeline(vs, fs, rpB, W, H, viB, 4, layoutB, True)
    p48, k48 = pipeline(vs, fs, rpB, W, H, vi48, 4, layoutB, True)

    def recseq():
        clear = (R.ClearValue * 1)(R.ClearValue((f32 * 4)(0, 0, 0, 0)))
        begin_rp(cb, C.byref(R.RenderPassBI(43, None, rpB.value, fbB.value, R.Rect2D(0, 0, W, H), 1, clear)), 0)
        bind_pipe(cb, 0, p28)
        bind_vb(cb, 0, 1, (u64 * 1)(vbuf.value), (u64 * 1)(0))
        draw(cb, 4, 1, 466, 0)
        bind_pipe(cb, 0, p48)
        bind_vb(cb, 0, 1, (u64 * 1)(bbuf.value), (u64 * 1)(0))
        draw(cb, 4, 1, 0, 0)
        bind_pipe(cb, 0, p28)
        bind_vb(cb, 0, 1, (u64 * 1)(vbuf.value), (u64 * 1)(0))
        draw(cb, 4, 1, 562, 0)
        end_rp(cb)
        img_barrier(imgB, 0x100, 0x800, 6, 6, 0x400, 0x1000)
    run(recseq)
    p = ptr(); map_mem(dev, rb_mem, u64(0), u64(W * H * 4), 0, C.byref(p)); C.memset(p, 0x77, W * H * 4); unmap(dev, rb_mem)

    def recr2():
        region = R.BufImgCopy(0, 0, 0, layers, R.Offset3D(0, 0, 0), R.Extent3D(W, H, 1))
        copy_i2b(cb, imgB, 6, rb_buf, 1, C.byref(region))
        barrier(cb, 0x1000, 0x4000, 0, 0, None, 0, None, 0, None)
    run(recr2)
    map_mem(dev, rb_mem, u64(0), u64(W * H * 4), 0, C.byref(p))
    invalidate(dev, 1, C.byref(R.MappedRange(6, None, rb_mem.value, 0, u64(0xFFFFFFFFFFFFFFFF))))
    raw = C.string_at(p.value, W * H * 4)
    unmap(dev, rb_mem)
    def quad(x0, y0, x1, y1):
        return sum(1 for y in range(y0, y1) for x in range(x0, x1) if raw[(y * W + x) * 4:(y * W + x) * 4 + 4] != bytes(4))
    lit = quad(0, 0, W, H)
    print(f"   lit: top-left (shadow stand-in) {quad(0, 0, 32, 32)}, top-right (mesh) {quad(32, 0, 64, 32)}, bottom-right (particle) {quad(32, 32, 64, 64)}, bottom-left (should be 0) {quad(0, 32, 32, 64)}, total {lit} -> {'OK' if quad(0, 32, 32, 64) == 0 and quad(32, 32, 64, 64) > 500 else 'WRONG'}")
    for blend in (False, True):
        print(f"   -- blending {'SRC_ALPHA/ONE (additive, as the game)' if blend else 'off'}")
        for name, topo, count, first, off, data in tests:
            C.memset(vp_, 0, VB)
            if count < 0: C.memmove(vp_.value + (0 if first else off) + first * 28, data, len(data))
            else: C.memmove(vp_.value + off + first * 28, data, len(data))
            pipe, keep = pipeline(vs, fs, rpB, W, H, viB, topo, layoutB, blend)

            def rec():
                clear = (R.ClearValue * 1)(R.ClearValue((f32 * 4)(0, 0, 0, 0)))
                begin_rp(cb, C.byref(R.RenderPassBI(43, None, rpB.value, fbB.value, R.Rect2D(0, 0, W, H), 1, clear)), 0)
                bind_pipe(cb, 0, pipe)
                if count < 0:  # indexed: `off` is the index buffer offset for the first two tests, the vertex bind offset for the third
                    ioff = off if first else 0
                    voff = 0 if first else off
                    bufs = (u64 * 1)(vbuf.value); offs = (u64 * 1)(voff)
                    bind_vb(cb, 0, 1, bufs, offs)
                    bind_ib(cb, ibuf, u64(ioff), 0)  # VK_INDEX_TYPE_UINT16
                    draw_indexed(cb, -count, 1, 0, first, 0)
                else:
                    bufs = (u64 * 1)(vbuf.value); offs = (u64 * 1)(off)
                    bind_vb(cb, 0, 1, bufs, offs)
                    draw(cb, count, 1, first, 0)
                end_rp(cb)
                img_barrier(imgB, 0x100, 0x800, 6, 6, 0x400, 0x1000)
            rs_, rw = run(rec)
            got = pixels(imgB, W, H, [(32, 32), (20, 44), (2, 2), (61, 61)])
            # centre and (20,44) inside the quad; corners outside (clear = 0)
            if blend:
                inside = bytes(int(round(c * 0x87 / 255)) for c in colour[:3]).hex() + "87"  # src*alpha + dst*1, alpha: a*a + 0
                inside = inside[:6] + format(int(round(0x87 * 0x87 / 255)), "02x")
            else:
                inside = colour.hex()
            exp = [inside, inside, "00000000", "00000000"]
            print(f"   {name}: submit {rs_}/{rw}: got {' '.join(got)} want {' '.join(exp)} -> {'OK' if got == exp else 'WRONG'}")
    unmap(dev, vmem)


if __name__ == "__main__":
    main()
