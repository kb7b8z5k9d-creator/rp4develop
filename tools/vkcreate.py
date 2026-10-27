#!/usr/bin/env python3
"""Does Mali r32p1 refuse MUTABLE_FORMAT only in the query, or also at vkCreateImage?

Creates a device through the bridge (as gamescope: promoted 1.2 instance) and tries the
output image gamescope makes: B8G8R8A8_UNORM, DRM-modifier tiling (linear), dma-buf external,
MUTABLE_FORMAT + format list [UNORM, SRGB]; then allocates exportable dedicated memory and
asks for the dma-buf fd, i.e. the whole path CVulkanTexture::BInit walks.
"""
import ctypes as C
import os
import sys

VK = C.CDLL("libvulkan.so.1")
u32, u64, ptr = C.c_uint32, C.c_uint64, C.c_void_p


class AppInfo(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("pApplicationName", C.c_char_p), ("applicationVersion", u32),
                ("pEngineName", C.c_char_p), ("engineVersion", u32), ("apiVersion", u32)]


class InstanceCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("flags", u32), ("pApplicationInfo", C.POINTER(AppInfo)),
                ("enabledLayerCount", u32), ("ppEnabledLayerNames", ptr), ("enabledExtensionCount", u32),
                ("ppEnabledExtensionNames", C.POINTER(C.c_char_p))]


class QueueCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("flags", u32), ("queueFamilyIndex", u32), ("queueCount", u32),
                ("pQueuePriorities", C.POINTER(C.c_float))]


class DeviceCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("flags", u32), ("queueCreateInfoCount", u32), ("pQueueCreateInfos", C.POINTER(QueueCI)),
                ("enabledLayerCount", u32), ("ppEnabledLayerNames", ptr), ("enabledExtensionCount", u32),
                ("ppEnabledExtensionNames", C.POINTER(C.c_char_p)), ("pEnabledFeatures", ptr)]


class Extent3D(C.Structure):
    _fields_ = [("w", u32), ("h", u32), ("d", u32)]


class ImageCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("flags", u32), ("imageType", u32), ("format", u32), ("extent", Extent3D),
                ("mipLevels", u32), ("arrayLayers", u32), ("samples", u32), ("tiling", u32), ("usage", u32), ("sharingMode", u32),
                ("queueFamilyIndexCount", u32), ("pQueueFamilyIndices", ptr), ("initialLayout", u32)]


class FormatListCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("viewFormatCount", u32), ("pViewFormats", C.POINTER(u32))]


class ExtMemImageCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("handleTypes", u32)]


class DrmModListCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("count", u32), ("pModifiers", C.POINTER(u64))]


class MemReqs(C.Structure):
    _fields_ = [("size", u64), ("alignment", u64), ("memoryTypeBits", u32)]


class MemReqs2(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("reqs", MemReqs)]


class DedicatedReqs(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("prefers", u32), ("requires", u32)]


class ImageMemReqsInfo2(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("image", u64)]


class MemAllocInfo(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("allocationSize", u64), ("memoryTypeIndex", u32)]


class ExportMemAllocInfo(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("handleTypes", u32)]


class DedicatedAllocInfo(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("image", u64), ("buffer", u64)]


class MemGetFdInfo(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("memory", u64), ("handleType", u32)]


class ImageViewCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("flags", u32), ("image", u64), ("viewType", u32), ("format", u32),
                ("components", u32 * 4), ("aspectMask", u32), ("baseMipLevel", u32), ("levelCount", u32), ("baseArrayLayer", u32),
                ("layerCount", u32)]


def main():
    app = AppInfo(0, None, b"gamescope", 0, b"hopefully not just some code", 0, (1 << 22) | (3 << 12))
    iexts = (C.c_char_p * 1)(b"VK_KHR_get_physical_device_properties2")
    ici = InstanceCI(1, None, 0, C.pointer(app), 0, None, 1, iexts)
    inst = ptr()
    VK.vkCreateInstance.restype = C.c_int
    r = VK.vkCreateInstance(C.byref(ici), None, C.byref(inst))
    print("vkCreateInstance ->", r)
    gipa = VK.vkGetInstanceProcAddr
    gipa.restype = ptr

    def fn(name, restype=C.c_int):
        p = gipa(inst, name.encode())
        if not p:
            print(f"  !! {name} not found")
            sys.exit(1)
        return C.CFUNCTYPE(restype)(p)

    enum = fn("vkEnumeratePhysicalDevices")
    n = u32(0)
    enum(inst, C.byref(n), None)
    pds = (ptr * max(n.value, 1))()
    enum(inst, C.byref(n), pds)
    pd = C.c_void_p(pds[0])

    dexts = [b"VK_EXT_image_drm_format_modifier", b"VK_KHR_external_memory", b"VK_KHR_external_memory_fd",
             b"VK_EXT_external_memory_dma_buf", b"VK_KHR_dedicated_allocation", b"VK_KHR_get_memory_requirements2",
             b"VK_KHR_bind_memory2", b"VK_KHR_sampler_ycbcr_conversion", b"VK_KHR_image_format_list", b"VK_KHR_maintenance1"]
    dext_arr = (C.c_char_p * len(dexts))(*dexts)
    prio = (C.c_float * 1)(1.0)
    qci = QueueCI(2, None, 0, 0, 1, prio)
    dci = DeviceCI(3, None, 0, 1, C.pointer(qci), 0, None, len(dexts), dext_arr, None)
    dev = ptr()
    create_dev = fn("vkCreateDevice")
    r = create_dev(pd, C.byref(dci), None, C.byref(dev))
    print("vkCreateDevice (10 exts) ->", r)
    if r != 0:
        sys.exit(1)
    gdpa = C.CFUNCTYPE(ptr)(gipa(inst, b"vkGetDeviceProcAddr"))

    def dfn(name, restype=C.c_int):
        p = gdpa(dev, name.encode())
        if not p:
            print(f"  !! {name} not found")
            sys.exit(1)
        return C.CFUNCTYPE(restype)(p)

    create_image = dfn("vkCreateImage")
    destroy_image = dfn("vkDestroyImage", None)
    get_reqs2 = dfn("vkGetImageMemoryRequirements2", None)
    alloc = dfn("vkAllocateMemory")
    free_mem = dfn("vkFreeMemory", None)
    bind = dfn("vkBindImageMemory")
    get_fd = dfn("vkGetMemoryFdKHR")
    create_view = dfn("vkCreateImageView")
    destroy_view = dfn("vkDestroyImageView", None)

    B8G8R8A8_UNORM, B8G8R8A8_SRGB = 44, 50
    DMA_BUF = 0x200
    TILING_DRM = 1000158000
    MUTABLE = 0x8

    def try_image(label, flags, with_list, usage, tiling=TILING_DRM, external=True, w=256, h=256):
        views = (u32 * 2)(B8G8R8A8_UNORM, B8G8R8A8_SRGB)
        fl = FormatListCI(1000147000, None, 2, views)
        mods = (u64 * 1)(0)
        ml = DrmModListCI(1000158003, None, 1, mods)
        em = ExtMemImageCI(1000072001, None, DMA_BUF)
        chain = None
        if tiling == TILING_DRM:
            chain = C.addressof(ml)
        if external:
            em.pNext = chain
            chain = C.addressof(em)
        if with_list:
            fl.pNext = chain
            chain = C.addressof(fl)
        ci = ImageCI(14, chain, flags, 1, B8G8R8A8_UNORM, Extent3D(w, h, 1), 1, 1, 1, tiling, usage, 0, 0, None, 0)
        img = u64(0)
        r = create_image(dev, C.byref(ci), None, C.byref(img))
        line = f"  {label:58} vkCreateImage -> {r}"
        if r != 0:
            print(line)
            return None
        # memory requirements, dedicated?
        ded = DedicatedReqs(1000127000, None, 0, 0)
        mr2 = MemReqs2(1000146003, C.addressof(ded))
        info = ImageMemReqsInfo2(1000146001, None, img.value)
        get_reqs2(dev, C.byref(info), C.byref(mr2))
        line += f"; size {mr2.reqs.size} types 0x{mr2.reqs.memoryTypeBits:x} dedicated prefers {ded.prefers} requires {ded.requires}"
        if not external:
            print(line)
            destroy_image(dev, img, None)
            return None
        # exportable dedicated allocation, as gamescope does
        dai = DedicatedAllocInfo(1000127001, None, img.value, 0)
        exi = ExportMemAllocInfo(1000072002, C.addressof(dai), DMA_BUF)
        types = mr2.reqs.memoryTypeBits
        mem_type = (types & -types).bit_length() - 1
        ai = MemAllocInfo(5, C.addressof(exi), mr2.reqs.size, mem_type)
        mem = u64(0)
        r = alloc(dev, C.byref(ai), None, C.byref(mem))
        line += f"; vkAllocateMemory(export dma-buf, type {mem_type}) -> {r}"
        if r == 0:
            r = bind(dev, img, mem, u64(0))
            line += f"; bind -> {r}"
            gi = MemGetFdInfo(1000074002, None, mem.value, DMA_BUF)
            fd = C.c_int(-1)
            r = get_fd(dev, C.byref(gi), C.byref(fd))
            line += f"; vkGetMemoryFdKHR -> {r} fd {fd.value}"
            if fd.value >= 0:
                os.close(fd.value)
            # the sRGB view gamescope makes on the mutable image
            vci = ImageViewCI(15, None, 0, img.value, 1, B8G8R8A8_SRGB, (u32 * 4)(0, 0, 0, 0), 1, 0, 1, 0, 1)
            view = u64(0)
            r = create_view(dev, C.byref(vci), None, C.byref(view))
            line += f"; sRGB view -> {r}"
            if r == 0:
                destroy_view(dev, view, None)
            free_mem(dev, mem, None)
        print(line)
        destroy_image(dev, img, None)
        return True

    out_usage = 0x4 | 0x8 | 0x1  # SAMPLED | STORAGE | TRANSFER_SRC
    blank_usage = 0x4 | 0x2      # SAMPLED | TRANSFER_DST
    print("== gamescope output image, B8G8R8A8_UNORM 256x256, DRM-modifier tiling (linear), dma-buf external")
    try_image("MUTABLE + format list (what gamescope asks)", MUTABLE, True, out_usage)
    try_image("MUTABLE, no format list", MUTABLE, False, out_usage)
    try_image("no MUTABLE, no list (what the driver's query accepts)", 0, False, out_usage)
    try_image("no MUTABLE, with format list", 0, True, out_usage)
    print("== blank texture usage")
    try_image("MUTABLE + format list", MUTABLE, True, blank_usage)
    try_image("no MUTABLE", 0, False, blank_usage)
    print("== controls")
    try_image("MUTABLE + list, DRM tiling, NOT external", MUTABLE, True, out_usage, external=False)
    try_image("MUTABLE + list, OPTIMAL tiling, not external", MUTABLE, True, out_usage, tiling=0, external=False)
    try_image("MUTABLE + list, OPTIMAL tiling, external dma-buf", MUTABLE, True, out_usage, tiling=0, external=True)
    print("== 1920x1080 as gamescope makes it")
    try_image("no MUTABLE, DRM linear, external, 1920x1080", 0, False, out_usage, w=1920, h=1080)


if __name__ == "__main__":
    main()
