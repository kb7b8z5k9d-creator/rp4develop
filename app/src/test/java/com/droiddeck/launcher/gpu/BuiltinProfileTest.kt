package com.droiddeck.launcher.gpu

import android.content.Context
import android.os.Build
import com.droiddeck.launcher.core.Hashes
import com.droiddeck.launcher.runtime.LinuxRuntime
import com.droiddeck.launcher.session.ComponentsManager
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.util.ReflectionHelpers
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], manifest = Config.NONE)
class BuiltinProfileTest {
    private lateinit var context: Context

    @Before fun setUp() {
        context = RuntimeEnvironment.getApplication()
        ReflectionHelpers.setStaticField(Build::class.java, "HARDWARE", "mt8797")
        context.getSharedPreferences("session", Context.MODE_PRIVATE).edit().clear().commit()
        for (dir in listOf("graphics_driver", "components")) File(context.filesDir, dir).deleteRecursively()
        LinuxRuntime.rootDir(context).deleteRecursively()
    }

    @Test fun theDefaultIsLimitedToTheSupportedDevice() {
        assertTrue(BuiltinProfile.matchesDevice(listOf("MT8797")))
        assertTrue(BuiltinProfile.matchesDevice(listOf("RP4Pro")))
        assertTrue(BuiltinProfile.matchesDevice(listOf("Retroid Pocket 4 Pro")))
        assertFalse(BuiltinProfile.matchesDevice(listOf("Retroid Pocket 4")))
        assertFalse(BuiltinProfile.matchesDevice(listOf("Retroid Pocket 5")))
        assertFalse(BuiltinProfile.matchesDevice(listOf("Retroid", "unverified device")))
    }

    @Test fun preparingAssetsPreservesExistingPlayerPreferences() {
        val prefs = context.getSharedPreferences("session", Context.MODE_PRIVATE)
        prefs.edit().putString("androidDriver", "").putString("gpuDriverMode", "manual")
            .putBoolean("vkBridge", false).putString("steamMenus", "software").commit()
        BuiltinProfile.prepareForSession(context)
        assertEquals("", prefs.getString("androidDriver", null))
        assertEquals("manual", prefs.getString("gpuDriverMode", null))
        assertFalse(prefs.getBoolean("vkBridge", true))
        assertEquals("software", prefs.getString("steamMenus", null))
    }

    @Test fun partialCopiesAreRepairedAndALaterInstalledProtonIsPreparedInTheSameApp() {
        val driver = File(context.filesDir, "graphics_driver/PanVK_faux123_v1.1.3/libvulkan_panfrost.so")
        driver.parentFile!!.mkdirs()
        driver.writeBytes(ByteArray(2_000_000))
        val wcp = File(context.filesDir, "components/packages/vkd3d-3.1-readback-fallback.wcp")
        wcp.parentFile!!.mkdirs()
        wcp.writeBytes(ByteArray(150_000))
        BuiltinProfile.prepareForSession(context)
        assertEquals("e2d222b5ab01a209c3e8bdc76ea7985cf3e0c57a709d030b3b3c5d947f5aaea0", Hashes.sha256(driver))
        assertTrue(File(driver.parentFile, "meta.json").isFile)
        assertEquals(BuiltinProfile.WCP_HASH, Hashes.sha256(wcp))

        val proton = File(LinuxRuntime.rootDir(context), "root/.local/share/Steam/steamapps/common/Proton Experimental (ARM64)")
        val dll = File(proton, "files/lib/wine/vkd3d-proton/aarch64-windows/d3d12core.dll")
        dll.parentFile!!.mkdirs()
        dll.writeText("stock")
        File(proton, "proton").writeText("#!/bin/sh\n")
        File(proton, "version").writeText("1 experimental-v1-arm64\n")
        BuiltinProfile.prepareForSession(context)
        val component = ComponentsManager.snapshot(context).protons.single().components.getValue("vkd3d")
        assertEquals(wcp.name, component.activeFile)
        assertNotEquals("stock", dll.readBytes().take(5).toByteArray().decodeToString())
    }
}
