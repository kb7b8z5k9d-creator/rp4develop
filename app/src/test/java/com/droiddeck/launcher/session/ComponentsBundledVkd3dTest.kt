package com.droiddeck.launcher.session

import android.content.Context
import com.droiddeck.launcher.core.Hashes
import com.droiddeck.launcher.runtime.LinuxRuntime
import com.github.luben.zstd.ZstdOutputStream
import org.apache.commons.compress.archivers.tar.TarArchiveEntry
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.io.File

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [28], manifest = Config.NONE)
class ComponentsBundledVkd3dTest {
    private lateinit var context: Context
    private lateinit var proton: File
    private lateinit var bundle: File
    private val relative = "files/lib/wine/vkd3d-proton/aarch64-windows/d3d12core.dll"

    @Before fun setUp() {
        context = RuntimeEnvironment.getApplication()
        File(context.filesDir, "components").deleteRecursively()
        LinuxRuntime.rootDir(context).deleteRecursively()
        proton = File(LinuxRuntime.rootDir(context), "root/.local/share/Steam/steamapps/common/Proton Experimental (ARM64)")
        File(proton, relative).apply { parentFile!!.mkdirs(); writeText("original v1") }
        File(proton, "proton").writeText("#!/bin/sh\n")
        File(proton, "version").writeText("1 experimental-v1-arm64\n")
        bundle = packageFile("bundled.wcp", "bundled readback")
    }

    @Test fun firstPreparationSavesOriginalAndRepairsASameVersionReinstall() {
        assertTrue(prepare())
        assertEquals("bundled readback", File(proton, relative).readText())
        val original = File(context.filesDir, "components/originals/${id()}/experimental-v1-arm64/vkd3d.wcp")
        assertTrue(original.isFile)
        val backup = Hashes.sha256(original)
        assertTrue(prepare())
        assertEquals(backup, Hashes.sha256(original))
        File(proton, relative).writeText("original v1")
        assertTrue(prepare())
        assertEquals("bundled readback", File(proton, relative).readText())
        assertEquals(backup, Hashes.sha256(original))
    }

    @Test fun aProtonUpdateGetsItsOwnBackupAndTheDefaultWithoutRestartingTheApp() {
        prepare()
        updateProton()
        assertTrue(prepare())
        assertEquals("bundled readback", File(proton, relative).readText())
        ComponentsManager.restore(context, id(), "vkd3d", "experimental-v2-arm64")
        assertEquals("original v2", File(proton, relative).readText())
    }

    @Test fun restoringOriginalOptsOutEvenAcrossProtonUpdates() {
        prepare()
        ComponentsManager.restore(context, id(), "vkd3d", "experimental-v1-arm64")
        assertFalse(prepare())
        assertEquals("original v1", File(proton, relative).readText())
        updateProton()
        assertFalse(prepare())
        assertEquals("original v2", File(proton, relative).readText())
    }

    @Test fun anExistingPlayerPackageIsPreserved() {
        packageFile("player.wcp", "player selected")
        ComponentsManager.swap(context, id(), "player.wcp")
        assertFalse(prepare())
        assertEquals("player selected", File(proton, relative).readText())
    }

    @Test fun aLegacyRestoredOriginalIsNotOverwrittenDuringMigration() {
        assertFalse(ComponentsManager.ensureBundledVkd3d(context, id(), bundle.name, Hashes.sha256(bundle), legacyApplied = true))
        assertEquals("original v1", File(proton, relative).readText())
    }

    @Test fun aBadPackageCannotModifyTheProton() {
        assertThrows(IllegalStateException::class.java) {
            ComponentsManager.ensureBundledVkd3d(context, id(), bundle.name, "0".repeat(64))
        }
        assertEquals("original v1", File(proton, relative).readText())
    }

    private fun prepare() = ComponentsManager.ensureBundledVkd3d(context, id(), bundle.name, Hashes.sha256(bundle))
    private fun id() = ComponentsManager.protons(context).single().id
    private fun updateProton() {
        File(proton, "version").writeText("2 experimental-v2-arm64\n")
        File(proton, relative).writeText("original v2")
    }

    private fun packageFile(name: String, contents: String): File {
        val file = File(context.filesDir, "components/packages/$name")
        file.parentFile!!.mkdirs()
        TarArchiveOutputStream(ZstdOutputStream(file.outputStream())).use { tar ->
            for ((path, text) in mapOf("profile.json" to """{"type":"VKD3D-Linux","versionName":"test"}""", relative to contents)) {
                val bytes = text.toByteArray()
                tar.putArchiveEntry(TarArchiveEntry(path).apply { size = bytes.size.toLong() })
                tar.write(bytes)
                tar.closeArchiveEntry()
            }
        }
        return file
    }
}
