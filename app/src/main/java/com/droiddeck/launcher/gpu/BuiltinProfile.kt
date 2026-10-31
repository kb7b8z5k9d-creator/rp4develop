package com.droiddeck.launcher.gpu

import android.content.Context
import android.os.Build
import android.util.Log
import com.droiddeck.launcher.session.ComponentsManager
import com.droiddeck.launcher.session.SessionPrefs
import com.droiddeck.launcher.core.Hashes
import com.droiddeck.launcher.runtime.LinuxRuntime
import java.io.File
import java.io.FileOutputStream

/**
 * Prepares the RP4 Pro defaults before a session starts. Application startup may warm the asset
 * copies, but never swaps a running Proton. Session startup waits for preparation after installing
 * Proton, so a first-time player does not need to restart the application.
 */
object BuiltinProfile {
    private const val TAG = "BuiltinProfile"
    private const val DRIVER_ID = "PanVK_faux123_v1.1.3"
    private const val DRIVER_LIB = "libvulkan_panfrost.so"
    private const val WCP = "vkd3d-3.1-readback-fallback.wcp"
    private const val PREFS = "session"
    private const val KEY_PROFILE = "builtinProfileApplied"
    private val lock = Any()
    private val verified = HashMap<String, Pair<Long, Long>>()
    internal const val WCP_HASH = "3c3043bdb57f18a7bc8b93f36acf846e35693f7eb4c7b97f2fb7f5922dc8cfa6"

    fun ensure(context: Context) {
        if (!isTargetDevice()) return
        val app = context.applicationContext
        Thread({
            runCatching { synchronized(lock) { ensureDriver(app) } }
                .onFailure { Log.w(TAG, "built-in PanVK preparation will retry before the session", it) }
        }, "builtin-profile").start()
    }

    /** Blocking; call on the installation/session worker before starting Steam or any game. */
    fun prepareForSession(context: Context) {
        if (!isTargetDevice()) return
        synchronized(lock) {
            ensureDriver(context)
            ensureVkd3d(context)
            removeLegacyDiagnostics(context)
        }
    }

    /** MT8797 is the Dimensity 1100 in the Retroid Pocket 4 Pro; the name checks cover its builds. */
    internal fun isTargetDevice(): Boolean {
        val soc = if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else ""
        return matchesDevice(listOf(soc, Build.HARDWARE, Build.BOARD, Build.DEVICE, Build.MODEL))
    }

    internal fun matchesDevice(fields: List<String>): Boolean {
        val identity = fields
            .joinToString(" ").lowercase()
        return identity.contains("mt8797") ||
            Regex("\\brp4\\s*pro\\b|retroid\\s*pocket\\s*4\\s*pro\\b").containsMatchIn(identity)
    }

    private fun ensureDriver(context: Context) {
        val dir = File(context.filesDir, "graphics_driver/$DRIVER_ID")
        ensureAsset(context, "panvk/$DRIVER_LIB", File(dir, DRIVER_LIB),
            "e2d222b5ab01a209c3e8bdc76ea7985cf3e0c57a709d030b3b3c5d947f5aaea0")
        ensureAsset(context, "panvk/meta.json", File(dir, "meta.json"),
            "2ea4d94b41335a2bee19e9a1328e2aaf72aa84a2f647e7de58d08f8b52adac65")

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (prefs.getBoolean(KEY_PROFILE, false)) return
        // An explicit empty driver ID means the player selected system Mali.
        if (!prefs.contains("androidDriver")) {
            SessionPrefs.setAndroidDriver(context, DRIVER_ID)
            SessionPrefs.setGpuDriverMode(context, SessionPrefs.GPU_DRIVERS_MANUAL)
        }
        if (!prefs.contains("vkBridge")) SessionPrefs.setVkBridge(context, true)
        if (!prefs.contains("steamMenus")) SessionPrefs.setSteamMenus(context, "gpu")
        prefs.edit().putBoolean(KEY_PROFILE, true).apply()
        Log.i(TAG, "applied the RP4 Pro default profile")
    }

    private fun ensureVkd3d(context: Context) {
        val packages = File(context.filesDir, "components/packages").apply { mkdirs() }
        val wcp = File(packages, WCP)
        ensureAsset(context, "vkd3d/$WCP", wcp, WCP_HASH)

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val proton = ComponentsManager.protons(context).firstOrNull {
            it.dir.name == "Proton Experimental (ARM64)" &&
                File(it.dir, "files/lib/wine/vkd3d-proton/aarch64-windows").isDirectory
        } ?: return
        ComponentsManager.ensureBundledVkd3d(context, proton.id, WCP, WCP_HASH,
            legacyApplied = prefs.getBoolean("builtinVkd3dApplied", false))
    }

    private fun ensureAsset(context: Context, asset: String, dest: File, hash: String) {
        val stamp = dest.length() to dest.lastModified()
        if (dest.isFile && verified[dest.absolutePath] == stamp) return
        if (!dest.isFile || Hashes.sha256(dest) != hash) {
            dest.parentFile?.mkdirs()
            val tmp = File(dest.parentFile, dest.name + ".builtin-new")
            try {
                context.assets.open(asset).use { input ->
                    FileOutputStream(tmp).use { output -> input.copyTo(output); output.fd.sync() }
                }
                check(Hashes.sha256(tmp) == hash) { "Bundled asset verification failed: $asset" }
                check(tmp.renameTo(dest)) { "Could not install bundled asset: $asset" }
                dest.setReadable(true, false)
            } finally {
                tmp.delete()
            }
            Log.i(TAG, "installed bundled asset $asset")
        }
        verified[dest.absolutePath] = dest.length() to dest.lastModified()
    }

    private fun removeLegacyDiagnostics(context: Context) {
        val root = LinuxRuntime.rootDir(context)
        File(root, "root/.vkbridge-env").delete()
        File(root, "usr/local/bin/droiddeck-vkbridge-smoke").delete()
        for (base in listOf(File(context.filesDir, "vkbridge-pipelines"), File(context.cacheDir, "vkbridge-pipelines"))) {
            File(base, "env").delete()
            base.listFiles()?.filter { it.isDirectory && it.name.startsWith("icd-") }
                ?.forEach { File(it, "env").delete() }
        }
    }
}
