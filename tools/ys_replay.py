#!/usr/bin/env python3
"""Replays one traced Ys Origin frame on the CPU: the vertex-buffer writes (Lock/memcpy blobs),
the vertex shader constants and every DrawPrimitive / DrawIndexedPrimitive made with the game's
sprite vertex shader (vs_1_1: r4 = v0 x c24..27, oPos = r4 x c4..7), and prints each draw's
screen extent in NDC as the PC would draw it. Usage: ys_replay.py <dump dir with calls.txt and
blob_call*.bin> [sprite VS handle] [vertex buffer handle]
"""
import glob
import os
import re
import struct
import sys

d = sys.argv[1]
VS = sys.argv[2] if len(sys.argv) > 2 else "0x5bb00920"
calls = open(os.path.join(d, "calls.txt"), encoding="utf-8", errors="replace").read().splitlines()

consts = {}          # register -> (x, y, z, w)
vbs = {}             # handle -> bytearray
streams = {}         # stream -> (handle, offset, stride)
locked = None        # (handle, offset)
vs = None
decl = None
indices = None
ibs = {}
topo_prims = {"D3DPT_TRIANGLELIST": lambda n: 3 * n, "D3DPT_TRIANGLESTRIP": lambda n: n + 2, "D3DPT_TRIANGLEFAN": lambda n: n + 2}
rows = []


def vec(row, c):
    return consts.get(c, (0.0, 0.0, 0.0, 0.0))


def xform(v):
    x, y, z = v
    v4 = (x, y, z, 1.0)
    r4 = tuple(sum(v4[i] * vec(0, 24 + k)[i] for i in range(4)) for k in range(4))
    o = tuple(sum(r4[i] * vec(0, 4 + k)[i] for i in range(4)) for k in range(4))
    return o


for line in calls:
    m = re.match(r"(\d+) (\S+)\((.*)\) = ", line)
    if not m:
        m2 = re.match(r"(\d+) memcpy\(dest = (0x[0-9a-f]+), src = blob\(\"(blob_call\d+\.bin)\"\), n = (\d+)\)", line)
        if m2 and locked:
            h, off = locked
            data = open(os.path.join(d, m2.group(3)), "rb").read()
            buf = vbs.setdefault(h, bytearray(1 << 20))
            buf[off:off + len(data)] = data
        continue
    no, fn, args = int(m.group(1)), m.group(2), m.group(3)
    if fn == "IDirect3DDevice9::SetVertexShaderConstantF":
        start = int(re.search(r"StartRegister = (\d+)", args).group(1))
        vals = [float("nan") if "nan" in x else float("inf") if "inf" in x else float(x)
                for x in re.search(r"pConstantData = \{([^}]*)\}", args).group(1).split(",")]
        if any(v != v for v in vals):
            print("%d: NaN in constants c%d..c%d" % (no, start, start + len(vals) // 4 - 1))
        for i in range(len(vals) // 4):
            consts[start + i] = tuple(vals[4 * i:4 * i + 4])
    elif fn == "IDirect3DDevice9::SetVertexShader":
        vs = re.search(r"pShader = (\S+)", args).group(1)
    elif fn == "IDirect3DDevice9::SetStreamSource":
        g = re.search(r"StreamNumber = (\d+), pStreamData = (0x[0-9a-f]+), OffsetInBytes = (\d+), Stride = (\d+)", args)
        streams[int(g.group(1))] = (g.group(2), int(g.group(3)), int(g.group(4)))
    elif fn == "IDirect3DVertexBuffer9::Lock":
        g = re.search(r"this = (0x[0-9a-f]+), OffsetToLock = (\d+)", args)
        locked = (g.group(1), int(g.group(2)))
    elif fn == "IDirect3DVertexBuffer9::Unlock":
        locked = None
    elif fn == "IDirect3DIndexBuffer9::Lock":
        g = re.search(r"this = (0x[0-9a-f]+), OffsetToLock = (\d+)", args)
        locked = ("ib" + g.group(1), int(g.group(2)))
    elif fn == "IDirect3DIndexBuffer9::Unlock":
        locked = None
    elif fn == "IDirect3DDevice9::SetIndices":
        indices = re.search(r"pIndexData = (\S+)", args).group(1)
    elif fn in ("IDirect3DDevice9::DrawPrimitive", "IDirect3DDevice9::DrawIndexedPrimitive"):
        if vs != VS:
            continue
        h, off, stride = streams.get(0, (None, 0, 0))
        buf = vbs.get(h)
        topo = re.search(r"PrimitiveType = (\S+),", args).group(1)
        prims = int(re.search(r"(?:PrimitiveCount|primCount) = (\d+)", args).group(1))
        if fn.endswith("DrawPrimitive"):
            first = int(re.search(r"StartVertex = (\d+)", args).group(1))
            count = topo_prims[topo](prims)
            verts = list(range(first, first + count))
        else:
            base = int(re.search(r"BaseVertexIndex = (\d+)", args).group(1))
            minv = int(re.search(r"MinVertexIndex = (\d+)", args).group(1))
            nv = int(re.search(r"NumVertices = (\d+)", args).group(1))
            verts = list(range(base + minv, base + minv + nv))  # the index buffer is static: its whole vertex range
        if buf is None:
            rows.append((no, fn.split("::")[1], topo, prims, "vertex buffer %s never written in this frame" % h))
            continue
        pts = []
        for vi in verts:
            o = off + vi * stride
            if o + 12 > len(buf):
                continue
            x, y, z = struct.unpack_from("<fff", buf, o)
            pts.append(xform((x, y, z)))
        if not pts:
            rows.append((no, fn.split("::")[1], topo, prims, "no vertices"))
            continue
        ndc = []
        for ox, oy, oz, ow in pts:
            if abs(ow) < 1e-6:
                ndc.append((float("inf"), float("inf"), float("inf")))
            else:
                ndc.append((ox / ow, oy / ow, oz / ow))
        xs, ys, zs = [p[0] for p in ndc], [p[1] for p in ndc], [p[2] for p in ndc]
        ws = [p[3] for p in pts]
        c0 = struct.unpack_from("<I", buf, off + verts[0] * stride + 12)[0]
        rows.append((no, fn.split("::")[1], topo, prims,
                     "ndc x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f w %.1f..%.1f colour %08x" %
                     (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), min(ws), max(ws), c0)))

big = 0
for no, fn, topo, prims, info in rows:
    flag = ""
    m = re.search(r"ndc x (\S+)\.\.(\S+) y (\S+)\.\.(\S+)", info)
    if m:
        x0, x1, y0, y1 = (float(v) for v in m.groups())
        w = min(x1, 1) - max(x0, -1)
        h = min(y1, 1) - max(y0, -1)
        if w > 0 and h > 0 and w * h / 4 > 0.25:
            flag = "  <-- covers %.0f%% of the screen" % (w * h / 4 * 100)
            big += 1
    print("%d %s %s x%d: %s%s" % (no, fn, topo.replace("D3DPT_", ""), prims, info, flag))
print("%d draws with the sprite VS, %d covering over a quarter of the screen" % (len(rows), big))
