#!/usr/bin/env python3
"""Reproduce gamescope's flippable-image modifier query through the Mali bridge.

Runs inside the DroidDeck rootfs (python3 + libvulkan loader + bridge ICD) against a
bridge server started by hand. Prints what the driver answers for the exact
vkGetPhysicalDeviceImageFormatProperties2 chain gamescope builds in
CVulkanTexture::BInit / getModifierProps (rendervulkan.cpp), plus the DRM modifier
list the driver reports for each format.
"""
import ctypes as C
import os
import sys

VK = C.CDLL(os.environ.get("VKQ_LOADER", "libvulkan.so.1"))

u32, u64, ptr = C.c_uint32, C.c_uint64, C.c_void_p

# sTypes
ST_APP_INFO = 0
ST_INSTANCE_CI = 1
ST_DEVICE_QUEUE_CI = 2
ST_DEVICE_CI = 3
ST_MEM_ALLOC = 5
ST_IMAGE_CI = 14
ST_PD_PROPS2 = 1000059001
ST_FORMAT_PROPS2 = 1000059002
ST_IMAGE_FORMAT_PROPS2 = 1000059003
ST_PD_IMAGE_FORMAT_INFO2 = 1000059004
ST_PD_EXT_IMAGE_FORMAT_INFO = 1000071000
ST_EXT_IMAGE_FORMAT_PROPS = 1000071001
ST_EXT_MEM_IMAGE_CI = 1000072001
ST_EXPORT_MEM_ALLOC = 1000072002
ST_MEM_DEDICATED_REQS = 1000127000
ST_MEM_DEDICATED_ALLOC = 1000127001
ST_IMAGE_MEM_REQS_INFO2 = 1000146001
ST_MEM_REQS2 = 1000146003
ST_DRM_MOD_PROPS_LIST = 1000158000
ST_PD_IMAGE_DRM_MOD_INFO = 1000158002
ST_IMAGE_DRM_MOD_LIST_CI = 1000158003
ST_MEM_GET_FD_INFO = 1000074002

TILING_OPTIMAL, TILING_LINEAR, TILING_DRM = 0, 1, 1000158000
DMA_BUF = 0x200
FMT = {"B8G8R8A8_UNORM": 44, "R8G8B8A8_UNORM": 37, "B8G8R8A8_SRGB": 50, "A2B10G10R10_UNORM": 64}
USAGE = {"TRANSFER_SRC": 1, "TRANSFER_DST": 2, "SAMPLED": 4, "STORAGE": 8, "COLOR_ATTACHMENT": 0x10}


class AppInfo(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("pApplicationName", C.c_char_p), ("applicationVersion", u32),
                ("pEngineName", C.c_char_p), ("engineVersion", u32), ("apiVersion", u32)]


class InstanceCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("flags", u32), ("pApplicationInfo", C.POINTER(AppInfo)),
                ("enabledLayerCount", u32), ("ppEnabledLayerNames", ptr), ("enabledExtensionCount", u32),
                ("ppEnabledExtensionNames", C.POINTER(C.c_char_p))]


class PDProps2(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("raw", C.c_uint8 * 2048)]


class ImageFormatInfo2(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("format", u32), ("type", u32), ("tiling", u32), ("usage", u32), ("flags", u32)]


class ExtImageFormatInfo(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("handleType", u32)]


class DrmModInfo(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("drmFormatModifier", u64), ("sharingMode", u32), ("queueFamilyIndexCount", u32),
                ("pQueueFamilyIndices", ptr)]


class ImageFormatProps(C.Structure):
    _fields_ = [("w", u32), ("h", u32), ("d", u32), ("mipLevels", u32), ("arrayLayers", u32), ("sampleCounts", u32), ("maxResourceSize", u64)]


class ImageFormatProps2(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("props", ImageFormatProps)]


class ExtMemProps(C.Structure):
    _fields_ = [("features", u32), ("exportFromImported", u32), ("compatible", u32)]


class ExtImageFormatProps(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("ext", ExtMemProps)]


class FormatListCI(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("viewFormatCount", u32), ("pViewFormats", C.POINTER(u32))]


class FormatProps(C.Structure):
    _fields_ = [("linear", u32), ("optimal", u32), ("buffer", u32)]


class FormatProps2(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("props", FormatProps)]


class DrmModProps(C.Structure):
    _fields_ = [("modifier", u64), ("planeCount", u32), ("features", u32)]


class DrmModPropsList(C.Structure):
    _fields_ = [("sType", u32), ("pNext", ptr), ("count", u32), ("pProps", C.POINTER(DrmModProps))]


def check(r, what):
    if r != 0:
        print(f"  !! {what} -> {r}")
    return r


def main():
    api = os.environ.get("VKQ_API", "1.3").split(".")
    app = AppInfo(ST_APP_INFO, None, os.environ.get("VKQ_APP", "gamescope").encode(), 0, b"hopefully not just some code", 0,
                  (int(api[0]) << 22) | (int(api[1]) << 12))
    ext_names = [e.encode() for e in os.environ.get("VKQ_EXTS", "VK_KHR_get_physical_device_properties2").split(",") if e]
    exts = (C.c_char_p * max(len(ext_names), 1))(*ext_names)
    print(f"instance: app {app.pApplicationName.decode()} api {api[0]}.{api[1]} exts {[e.decode() for e in ext_names]}")
    ici = InstanceCI(ST_INSTANCE_CI, None, 0, C.pointer(app), 0, None, len(ext_names), exts)
    inst = ptr()
    VK.vkCreateInstance.restype = C.c_int
    if check(VK.vkCreateInstance(C.byref(ici), None, C.byref(inst)), "vkCreateInstance"):
        sys.exit(1)
    gipa = VK.vkGetInstanceProcAddr
    gipa.restype = ptr

    def fn(name, restype=C.c_int):
        p = gipa(inst, name.encode())
        if not p:
            print(f"  !! {name} not found")
            sys.exit(1)
        f = C.CFUNCTYPE(restype)(p)
        return f

    enum = fn("vkEnumeratePhysicalDevices")
    n = u32(0)
    check(enum(inst, C.byref(n), None), "enumerate")
    pds = (ptr * max(n.value, 1))()
    check(enum(inst, C.byref(n), pds), "enumerate2")
    pd = C.c_void_p(pds[0])
    gp2 = fn("vkGetPhysicalDeviceProperties2", None)
    pp = PDProps2(ST_PD_PROPS2, None)
    gp2(pd, C.byref(pp))
    raw = bytes(pp.raw)
    v = int.from_bytes(raw[0:4], "little")
    drv = int.from_bytes(raw[4:8], "little")
    name = raw[20:276].split(bytes([0]), 1)[0].decode()
    print(f"device: {name} api {v >> 22}.{(v >> 12) & 0x3ff}.{v & 0xfff} driver 0x{drv:x}")

    gfp2 = fn("vkGetPhysicalDeviceFormatProperties2", None)
    gifp2 = fn("vkGetPhysicalDeviceImageFormatProperties2")

    print("\n== DRM format modifiers the driver reports (vkGetPhysicalDeviceFormatProperties2 + DrmFormatModifierPropertiesListEXT)")
    mods_by_fmt = {}
    for name, f in FMT.items():
        lst = DrmModPropsList(ST_DRM_MOD_PROPS_LIST, None, 0, None)
        fp = FormatProps2(ST_FORMAT_PROPS2, C.addressof(lst))
        gfp2(pd, f, C.byref(fp))
        arr = (DrmModProps * max(lst.count, 1))()
        lst.pProps = arr
        gfp2(pd, f, C.byref(fp))
        mods = [(arr[i].modifier, arr[i].planeCount, arr[i].features) for i in range(lst.count)]
        mods_by_fmt[name] = mods
        lin = [m for m in mods if m[0] == 0]
        print(f"  {name}: optimal 0x{fp.props.optimal:x} linear 0x{fp.props.linear:x}; {lst.count} modifier(s); "
              f"LINEAR {'listed, features 0x%x' % lin[0][2] if lin else 'NOT listed'}")
        for m in mods[:6]:
            print(f"      modifier 0x{m[0]:016x} planes {m[1]} features 0x{m[2]:x}")
        if len(mods) > 6:
            print(f"      ... {len(mods) - 6} more")

    print("\n== gamescope's getModifierProps query: tiling DRM_FORMAT_MODIFIER, modifier LINEAR, handle DMA_BUF")
    cases = [
        ("blank 1x1 texture (vulkan_create_flat_texture)", "SAMPLED|TRANSFER_DST"),
        ("output image (vulkan_make_output_images)", "SAMPLED|STORAGE|TRANSFER_SRC"),
        ("bridge's own export check (server_emu.c)", "SAMPLED|COLOR_ATTACHMENT"),
        ("sampled only", "SAMPLED"),
        ("sampled + color attachment + transfer", "SAMPLED|COLOR_ATTACHMENT|TRANSFER_SRC|TRANSFER_DST"),
        ("storage only", "STORAGE"),
    ]
    print("== gamescope's exact flippable query: MUTABLE_FORMAT + VkImageFormatListCreateInfo [UNORM, SRGB], DRM_MOD linear, DMA_BUF")
    for label, usage_s in (("blank texture", "SAMPLED|TRANSFER_DST"), ("output image", "SAMPLED|STORAGE|TRANSFER_SRC")):
        usage = 0
        for u in usage_s.split("|"):
            usage |= USAGE[u]
        for with_list in (True, False):
            views = (u32 * 2)(FMT["B8G8R8A8_UNORM"], FMT["B8G8R8A8_SRGB"])
            fl = FormatListCI(1000147000, None, 2, views)
            mi = DrmModInfo(ST_PD_IMAGE_DRM_MOD_INFO, None, 0, 0, 0, None)
            ei = ExtImageFormatInfo(ST_PD_EXT_IMAGE_FORMAT_INFO, C.addressof(mi), DMA_BUF)
            fl.pNext = C.addressof(ei)
            ii = ImageFormatInfo2(ST_PD_IMAGE_FORMAT_INFO2, C.addressof(fl) if with_list else C.addressof(ei), FMT["B8G8R8A8_UNORM"], 1, TILING_DRM, usage, 0x8)
            ep = ExtImageFormatProps(ST_EXT_IMAGE_FORMAT_PROPS, None)
            ip = ImageFormatProps2(ST_IMAGE_FORMAT_PROPS2, C.addressof(ep))
            r = gifp2(pd, C.byref(ii), C.byref(ip))
            feat = ep.ext.features
            print(f"  {label:14} {usage_s:30} flags MUTABLE {'+ format list' if with_list else 'no list      '} -> {'OK features 0x%x' % feat if r == 0 else 'result %d' % r}")
    print()
    quick = os.environ.get("VKQ_QUICK") == "1"
    for fmt_name in ("B8G8R8A8_UNORM", "R8G8B8A8_UNORM"):
        for label, usage_s in (cases[2:3] if quick else cases):
            usage = 0
            for u in usage_s.split("|"):
                usage |= USAGE[u]
            for tiling_name, tiling in ((("DRM_MOD linear", TILING_DRM),) if quick else (("DRM_MOD linear", TILING_DRM), ("OPTIMAL", TILING_OPTIMAL), ("LINEAR", TILING_LINEAR))):
                mi = DrmModInfo(ST_PD_IMAGE_DRM_MOD_INFO, None, 0, 0, 0, None)
                ei = ExtImageFormatInfo(ST_PD_EXT_IMAGE_FORMAT_INFO, C.addressof(mi) if tiling == TILING_DRM else None, DMA_BUF)
                ii = ImageFormatInfo2(ST_PD_IMAGE_FORMAT_INFO2, C.addressof(ei), FMT[fmt_name], 1, tiling, usage, 0)
                ep = ExtImageFormatProps(ST_EXT_IMAGE_FORMAT_PROPS, None)
                ip = ImageFormatProps2(ST_IMAGE_FORMAT_PROPS2, C.addressof(ep))
                r = gifp2(pd, C.byref(ii), C.byref(ip))
                feat = ep.ext.features
                verdict = ("OK " + ("EXPORTABLE " if feat & 2 else "not-exportable ") + ("IMPORTABLE" if feat & 4 else "not-importable") + (" dedicated-only" if feat & 1 else "")) if r == 0 else f"result {r}"
                print(f"  {fmt_name:15} {tiling_name:15} {usage_s:45} -> {verdict} (features 0x{feat:x}, max {ip.props.w}x{ip.props.h})")
            # same query without the external-memory chain at all
            ii = ImageFormatInfo2(ST_PD_IMAGE_FORMAT_INFO2, None, FMT[fmt_name], 1, TILING_OPTIMAL, usage, 0)
            ip = ImageFormatProps2(ST_IMAGE_FORMAT_PROPS2, None)
            r = gifp2(pd, C.byref(ii), C.byref(ip))
            print(f"  {fmt_name:15} {'OPTIMAL, no ext':15} {usage_s:45} -> {'OK' if r == 0 else r}")
        print()


if __name__ == "__main__":
    main()
