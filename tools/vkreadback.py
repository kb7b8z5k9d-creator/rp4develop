#!/usr/bin/env python3
"""Read-back test through the Mali bridge: render into an image, copy it to a host-visible buffer,
map, and check the bytes. Mimics what Zink does for a DirectDraw/wined3d surface lock.

Cases: clear via vkCmdClearColorImage; clear via a render pass (tile memory / AFBC path);
copy to a buffer in each host-visible memory type; read twice (cache behaviour).
"""
import ctypes as C
import os
import sys
import time

VK = C.CDLL("libvulkan.so.1")
u32, u64, ptr, f32 = C.c_uint32, C.c_uint64, C.c_void_p, C.c_float


class S(C.Structure):
    pass


def struct(name, fields):
    return type(name, (C.Structure,), {"_fields_": fields})


AppInfo = struct("AppInfo", [("sType", u32), ("pNext", ptr), ("pApplicationName", C.c_char_p), ("applicationVersion", u32),
                             ("pEngineName", C.c_char_p), ("engineVersion", u32), ("apiVersion", u32)])
InstanceCI = struct("InstanceCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("pApplicationInfo", C.POINTER(AppInfo)),
                                   ("enabledLayerCount", u32), ("ppEnabledLayerNames", ptr), ("enabledExtensionCount", u32),
                                   ("ppEnabledExtensionNames", C.POINTER(C.c_char_p))])
QueueCI = struct("QueueCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("queueFamilyIndex", u32), ("queueCount", u32),
                             ("pQueuePriorities", C.POINTER(f32))])
DeviceCI = struct("DeviceCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("queueCreateInfoCount", u32),
                               ("pQueueCreateInfos", C.POINTER(QueueCI)), ("enabledLayerCount", u32), ("ppEnabledLayerNames", ptr),
                               ("enabledExtensionCount", u32), ("ppEnabledExtensionNames", C.POINTER(C.c_char_p)), ("pEnabledFeatures", ptr)])
Extent3D = struct("Extent3D", [("w", u32), ("h", u32), ("d", u32)])
ImageCI = struct("ImageCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("imageType", u32), ("format", u32), ("extent", Extent3D),
                             ("mipLevels", u32), ("arrayLayers", u32), ("samples", u32), ("tiling", u32), ("usage", u32), ("sharingMode", u32),
                             ("queueFamilyIndexCount", u32), ("pQueueFamilyIndices", ptr), ("initialLayout", u32)])
MemReqs = struct("MemReqs", [("size", u64), ("alignment", u64), ("memoryTypeBits", u32)])
MemAllocInfo = struct("MemAllocInfo", [("sType", u32), ("pNext", ptr), ("allocationSize", u64), ("memoryTypeIndex", u32)])
BufferCI = struct("BufferCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("size", u64), ("usage", u32), ("sharingMode", u32),
                               ("queueFamilyIndexCount", u32), ("pQueueFamilyIndices", ptr)])
MemType = struct("MemType", [("propertyFlags", u32), ("heapIndex", u32)])
MemHeap = struct("MemHeap", [("size", u64), ("flags", u32)])
MemProps = struct("MemProps", [("memoryTypeCount", u32), ("memoryTypes", MemType * 32), ("memoryHeapCount", u32), ("memoryHeaps", MemHeap * 16)])
CmdPoolCI = struct("CmdPoolCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("queueFamilyIndex", u32)])
CmdBufAI = struct("CmdBufAI", [("sType", u32), ("pNext", ptr), ("commandPool", u64), ("level", u32), ("commandBufferCount", u32)])
CmdBufBI = struct("CmdBufBI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("pInheritanceInfo", ptr)])
ImgSubRange = struct("ImgSubRange", [("aspectMask", u32), ("baseMipLevel", u32), ("levelCount", u32), ("baseArrayLayer", u32), ("layerCount", u32)])
ImgMemBarrier = struct("ImgMemBarrier", [("sType", u32), ("pNext", ptr), ("srcAccessMask", u32), ("dstAccessMask", u32), ("oldLayout", u32),
                                         ("newLayout", u32), ("srcQueueFamilyIndex", u32), ("dstQueueFamilyIndex", u32), ("image", u64),
                                         ("subresourceRange", ImgSubRange)])
ClearColor = struct("ClearColor", [("f", f32 * 4)])
ImgSubLayers = struct("ImgSubLayers", [("aspectMask", u32), ("mipLevel", u32), ("baseArrayLayer", u32), ("layerCount", u32)])
Offset3D = struct("Offset3D", [("x", C.c_int32), ("y", C.c_int32), ("z", C.c_int32)])
BufImgCopy = struct("BufImgCopy", [("bufferOffset", u64), ("bufferRowLength", u32), ("bufferImageHeight", u32), ("imageSubresource", ImgSubLayers),
                                   ("imageOffset", Offset3D), ("imageExtent", Extent3D)])
SubmitInfo = struct("SubmitInfo", [("sType", u32), ("pNext", ptr), ("waitSemaphoreCount", u32), ("pWaitSemaphores", ptr), ("pWaitDstStageMask", ptr),
                                   ("commandBufferCount", u32), ("pCommandBuffers", C.POINTER(u64)), ("signalSemaphoreCount", u32), ("pSignalSemaphores", ptr)])
FenceCI = struct("FenceCI", [("sType", u32), ("pNext", ptr), ("flags", u32)])
MappedRange = struct("MappedRange", [("sType", u32), ("pNext", ptr), ("memory", u64), ("offset", u64), ("size", u64)])
# render pass
AttachDesc = struct("AttachDesc", [("flags", u32), ("format", u32), ("samples", u32), ("loadOp", u32), ("storeOp", u32), ("stencilLoadOp", u32),
                                   ("stencilStoreOp", u32), ("initialLayout", u32), ("finalLayout", u32)])
AttachRef = struct("AttachRef", [("attachment", u32), ("layout", u32)])
SubpassDesc = struct("SubpassDesc", [("flags", u32), ("pipelineBindPoint", u32), ("inputAttachmentCount", u32), ("pInputAttachments", ptr),
                                     ("colorAttachmentCount", u32), ("pColorAttachments", C.POINTER(AttachRef)), ("pResolveAttachments", ptr),
                                     ("pDepthStencilAttachment", ptr), ("preserveAttachmentCount", u32), ("pPreserveAttachments", ptr)])
RenderPassCI = struct("RenderPassCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("attachmentCount", u32), ("pAttachments", C.POINTER(AttachDesc)),
                                       ("subpassCount", u32), ("pSubpasses", C.POINTER(SubpassDesc)), ("dependencyCount", u32), ("pDependencies", ptr)])
ImageViewCI = struct("ImageViewCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("image", u64), ("viewType", u32), ("format", u32),
                                     ("components", u32 * 4), ("subresourceRange", ImgSubRange)])
FramebufferCI = struct("FramebufferCI", [("sType", u32), ("pNext", ptr), ("flags", u32), ("renderPass", u64), ("attachmentCount", u32),
                                         ("pAttachments", C.POINTER(u64)), ("width", u32), ("height", u32), ("layers", u32)])
Rect2D = struct("Rect2D", [("x", C.c_int32), ("y", C.c_int32), ("w", u32), ("h", u32)])
ClearValue = struct("ClearValue", [("f", f32 * 4)])
RenderPassBI = struct("RenderPassBI", [("sType", u32), ("pNext", ptr), ("renderPass", u64), ("framebuffer", u64), ("renderArea", Rect2D),
                                       ("clearValueCount", u32), ("pClearValues", C.POINTER(ClearValue))])


def main():
    W, H = int(os.environ.get("VKR_W", "1280")), int(os.environ.get("VKR_H", "720"))
    app = AppInfo(0, None, os.environ.get("VKR_APP", "Xwayland").encode(), 0, b"mesa zink", 0, (1 << 22) | (1 << 12))
    iexts = (C.c_char_p * 1)(b"VK_KHR_get_physical_device_properties2")
    ici = InstanceCI(1, None, 0, C.pointer(app), 0, None, 1, iexts)
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
    mp = MemProps(); fn("vkGetPhysicalDeviceMemoryProperties", None)(pd, C.byref(mp))
    types = [(i, mp.memoryTypes[i].propertyFlags) for i in range(mp.memoryTypeCount)]
    print("memory types:", ["%d:0x%x" % t for t in types])
    prio = (f32 * 1)(1.0)
    qci = QueueCI(2, None, 0, 0, 1, prio)
    dci = DeviceCI(3, None, 0, 1, C.pointer(qci), 0, None, 0, None, None)
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
    map_mem, unmap, invalidate = dfn("vkMapMemory"), dfn("vkUnmapMemory", None), dfn("vkInvalidateMappedMemoryRanges")
    cpool = u64(0); dfn("vkCreateCommandPool")(dev, C.byref(CmdPoolCI(39, None, 2, 0)), None, C.byref(cpool))
    cb = u64(0); dfn("vkAllocateCommandBuffers")(dev, C.byref(CmdBufAI(40, None, cpool.value, 0, 1)), C.byref(cb))
    begin, end = dfn("vkBeginCommandBuffer"), dfn("vkEndCommandBuffer")
    barrier = dfn("vkCmdPipelineBarrier", None)
    clear = dfn("vkCmdClearColorImage", None)
    copy_i2b = dfn("vkCmdCopyImageToBuffer", None)
    submit, create_fence, wait_fence, reset_fence = dfn("vkQueueSubmit"), dfn("vkCreateFence"), dfn("vkWaitForFences"), dfn("vkResetFences")
    create_rp, create_view, create_fb = dfn("vkCreateRenderPass"), dfn("vkCreateImageView"), dfn("vkCreateFramebuffer")
    begin_rp, end_rp = dfn("vkCmdBeginRenderPass", None), dfn("vkCmdEndRenderPass", None)
    fence = u64(0); create_fence(dev, C.byref(FenceCI(8, None, 0)), None, C.byref(fence))

    FMT = 44  # B8G8R8A8_UNORM
    img = u64(0)
    ici2 = ImageCI(14, None, 0, 1, FMT, Extent3D(W, H, 1), 1, 1, 1, 0, 0x1 | 0x2 | 0x4 | 0x10, 0, 0, None, 0)
    print("image ->", create_image(dev, C.byref(ici2), None, C.byref(img)))
    r = MemReqs(); get_ireq(dev, img, C.byref(r))
    imem = u64(0)
    dl = [i for i, f in types if (r.memoryTypeBits >> i) & 1 and f & 1][0]
    print("image mem type", dl, "->", alloc(dev, C.byref(MemAllocInfo(5, None, r.size, dl)), None, C.byref(imem)), "bind", bind_i(dev, img, imem, u64(0)))

    def run(record):
        begin(cb, C.byref(CmdBufBI(42, None, 1, None)))
        record()
        end(cb)
        cbs = (u64 * 1)(cb.value)
        si = SubmitInfo(4, None, 0, None, None, 1, cbs, 0, None)
        reset_fence(dev, 1, C.byref(fence))
        rs = submit(q, 1, C.byref(si), fence)
        t = time.time()
        rw = wait_fence(dev, 1, C.byref(fence), 1, u64(10**10))
        return rs, rw, (time.time() - t) * 1000

    def img_barrier(old, new, src, dst):
        b = ImgMemBarrier(45, None, src, dst, old, new, 0xFFFFFFFF, 0xFFFFFFFF, img.value, ImgSubRange(1, 0, 1, 0, 1))
        barrier(cb, 0x10000, 0x10000, 0, 0, None, 0, None, 1, C.byref(b))

    color = (0.25, 0.5, 0.75, 1.0)
    expect = bytes([round(color[2] * 255), round(color[1] * 255), round(color[0] * 255), 255])  # BGRA in memory

    def readback(label, buf_type, invalidate_first):
        buf = u64(0)
        size = W * H * 4
        create_buffer(dev, C.byref(BufferCI(12, None, 0, size, 0x2, 0, 0, None)), None, C.byref(buf))
        br = MemReqs(); get_breq(dev, buf, C.byref(br))
        if not (br.memoryTypeBits >> buf_type) & 1:
            print(f"  {label}: buffer cannot use memory type {buf_type} (bits 0x{br.memoryTypeBits:x})"); return
        bmem = u64(0)
        ra = alloc(dev, C.byref(MemAllocInfo(5, None, br.size, buf_type)), None, C.byref(bmem))
        if ra != 0:
            print(f"  {label}: alloc type {buf_type} -> {ra}"); return
        bind_b(dev, buf, bmem, u64(0))
        # pre-fill the mapped memory with a marker so a skipped copy shows
        p = ptr()
        map_mem(dev, bmem, u64(0), u64(size), 0, C.byref(p))
        C.memset(p, 0x77, size)
        unmap(dev, bmem)

        def rec():
            img_barrier(1, 6, 0x100, 0x800)  # GENERAL -> TRANSFER_SRC
            region = BufImgCopy(0, 0, 0, ImgSubLayers(1, 0, 0, 1), Offset3D(0, 0, 0), Extent3D(W, H, 1))
            copy_i2b(cb, img, 6, buf, 1, C.byref(region))
            img_barrier(6, 1, 0x800, 0x100)
        rs, rw, ms = run(rec)
        map_mem(dev, bmem, u64(0), u64(size), 0, C.byref(p))
        if invalidate_first:
            invalidate(dev, 1, C.byref(MappedRange(6, None, bmem.value, 0, 0xFFFFFFFFFFFFFFFF)))
        data = C.string_at(p, size)
        unmap(dev, bmem)
        first, mid, last = data[:4], data[size // 2: size // 2 + 4], data[-4:]
        ok = data.count(expect) * 4
        print(f"  {label}: submit {rs} wait {rw} {ms:.0f} ms; px first {first.hex()} mid {mid.hex()} last {last.hex()}; "
              f"{ok * 100 // size}% expected ({expect.hex()}), marker left {data.count(b'\\x77\\x77\\x77\\x77') * 4 * 100 // size}%")

    print(f"\n== {W}x{H} BGRA8: vkCmdClearColorImage to {color}")
    def rec_clear():
        img_barrier(0, 1, 0, 0x1000)
        cc = ClearColor((f32 * 4)(*color))
        clear(cb, img, 1, C.byref(cc), 1, C.byref(ImgSubRange(1, 0, 1, 0, 1)))
    print("  clear:", run(rec_clear))
    for t_i, f in types:
        if f & 0x2:
            readback(f"type {t_i} (0x{f:x}) no invalidate", t_i, False)
            readback(f"type {t_i} (0x{f:x}) with invalidate", t_i, True)

    print(f"\n== render pass clear (LOAD_OP_CLEAR) to {color}, then read back")
    att = AttachDesc(0, FMT, 1, 1, 0, 2, 1, 1, 1)  # initial GENERAL, final GENERAL
    ref = AttachRef(0, 2)  # COLOR_ATTACHMENT_OPTIMAL
    sub = SubpassDesc(0, 0, 0, None, 1, C.pointer(ref), None, None, 0, None)
    rp = u64(0); print("  render pass ->", create_rp(dev, C.byref(RenderPassCI(38, None, 0, 1, C.pointer(att), 1, C.pointer(sub), 0, None)), None, C.byref(rp)))
    view = u64(0); create_view(dev, C.byref(ImageViewCI(15, None, 0, img.value, 1, FMT, (u32 * 4)(0, 0, 0, 0), ImgSubRange(1, 0, 1, 0, 1))), None, C.byref(view))
    views = (u64 * 1)(view.value)
    fb = u64(0); print("  framebuffer ->", create_fb(dev, C.byref(FramebufferCI(37, None, 0, rp.value, 1, views, W, H, 1)), None, C.byref(fb)))
    color2 = (0.75, 0.25, 0.5, 1.0)
    expect2 = bytes([round(color2[2] * 255), round(color2[1] * 255), round(color2[0] * 255), 255])
    def rec_rp():
        cv = ClearValue((f32 * 4)(*color2))
        begin_rp(cb, C.byref(RenderPassBI(43, None, rp.value, fb.value, Rect2D(0, 0, W, H), 1, C.pointer(cv))), 0)
        end_rp(cb)
    print("  render pass:", run(rec_rp))
    # expected changes for the next read-backs
    globals()["expect"] = expect2
    nonlocal_expect = expect2
    def readback2(label, t_i, inv):
        nonlocal expect
        expect = expect2
        readback(label, t_i, inv)
    for t_i, f in types:
        if f & 0x2:
            readback2(f"type {t_i} (0x{f:x}) after render pass", t_i, True)


if __name__ == "__main__":
    main()
