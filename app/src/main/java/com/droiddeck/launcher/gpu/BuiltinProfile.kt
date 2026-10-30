package com.droiddeck.launcher.gpu

import android.content.Context
import android.os.Build
import android.util.Log
import com.droiddeck.launcher.session.ComponentsManager
import com.droiddeck.launcher.session.SessionPrefs
import java.io.File
import java.io.FileOutputStream

/**
 * The RP4 Pro build's out-of-the-box profile: the bundled PanVK driver (Vulkan 1.3), the VKD3D
 * readback fallback, the Mali bridge and the CEF compositing setting. Only applied on an MT8797 /
 * Retroid Pocket 4; every other device keeps the stock Mali bridge and the system driver.
 *
 * The driver is copied out of the APK on the first start; the VKD3D package is put in the component
 * store and selected for Proton Experimental once that Proton exists. A user's later choice is not
 * overwritten.
 */
object BuiltinProfile {
    private const val TAG = "BuiltinProfile"
    private const val DRIVER_ID = "PanVK_faux123_v1.1.3"
    private const val DRIVER_LIB = "libvulkan_panfrost.so"
    private const val WCP = "vkd3d-3.1-readback-fallback.wcp"
    private const val PREFS = "session"
    private const val KEY_PROFILE = "builtinProfileApplied"
    private const val KEY_VKD3D = "builtinVkd3dApplied"

    fun ensure(context: Context) {
        if (!isTargetDevice()) return
        val app = context.applicationContext
        Thread({
            runCatching { ensureDriver(app) }.onFailure { Log.w(TAG, "built-in PanVK", it) }
            runCatching { ensureVkd3d(app) }.onFailure { Log.w(TAG, "built-in VKD3D", it) }
        }, "builtin-profile").start()
    }

    /** MT8797 is the Dimensity 1100 in the Retroid Pocket 4 Pro; the name checks cover its builds. */
    internal fun isTargetDevice(): Boolean {
        val soc = if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else ""
        val identity = listOf(soc, Build.HARDWARE, Build.BOARD, Build.DEVICE, Build.MODEL)
            .joinToString(" ").lowercase()
        return identity.contains("mt8797") || identity.contains("rp4") || identity.contains("retroid")
    }

    private fun ensureDriver(context: Context) {
        val dir = File(context.filesDir, "graphics_driver/$DRIVER_ID")
        val library = File(dir, DRIVER_LIB)
        if (!library.isFile || library.length() < 1_000_000L) {
            dir.mkdirs()
            copyAsset(context, "panvk/$DRIVER_LIB", library)
            copyAsset(context, "panvk/meta.json", File(dir, "meta.json"))
            Log.i(TAG, "installed bundled PanVK $DRIVER_ID")
        }

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getBoolean(KEY_PROFILE, false)) return
        if (SessionPrefs.androidDriver(context).isEmpty()) {
            SessionPrefs.setAndroidDriver(context, DRIVER_ID)
            SessionPrefs.setGpuDriverMode(context, SessionPrefs.GPU_DRIVERS_MANUAL)
        }
        SessionPrefs.setVkBridge(context, true)
        SessionPrefs.setSteamMenus(context, "gpu")
        prefs.edit().putBoolean(KEY_PROFILE, true).apply()
        Log.i(TAG, "applied the RP4 Pro default profile")
    }

    private fun ensureVkd3d(context: Context) {
        val packages = File(context.filesDir, "components/packages").apply { mkdirs() }
        val wcp = File(packages, WCP)
        if (!wcp.isFile || wcp.length() < 100_000L) copyAsset(context, "vkd3d/$WCP", wcp)

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getBoolean(KEY_VKD3D, false)) return
        val proton = ComponentsManager.protons(context).firstOrNull {
            it.name.contains("Experimental", ignoreCase = true) ||
                it.dir.name.contains("Experimental", ignoreCase = true)
        } ?: return
        // A Proton in use gets its swap at the next start, not queued behind a running game here.
        if (ComponentsManager.inUse(context, proton)) return
        ComponentsManager.swap(context, proton.id, WCP)
        prefs.edit().putBoolean(KEY_VKD3D, true).apply()
        Log.i(TAG, "selected bundled VKD3D for ${proton.name} ${proton.version}")
    }

    private fun copyAsset(context: Context, asset: String, dest: File) {
        dest.parentFile?.mkdirs()
        context.assets.open(asset).use { input ->
            FileOutputStream(dest).use { output -> input.copyTo(output) }
        }
        dest.setReadable(true, false)
    }
}
