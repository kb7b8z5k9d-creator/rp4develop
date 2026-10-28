package com.droiddeck.launcher.frontend

import android.content.Context
import android.os.Environment
import com.droiddeck.launcher.session.SessionPrefs
import java.io.File

/**
 * The Retro page's library: ROM folders on internal storage and SD cards, each folder matched to a Daijishō platform
 * by its name, played in an installed Android emulator (one chosen per platform, Daijishō's first installed one
 * unless picked). Roots: SessionPrefs.romsDir when set, every "Roms*" folder at the top of a storage volume, and
 * the folders added here (prefs "retro", "roots").
 */
object RetroLibrary {
    const val ID_PREFIX = "android:"
    private const val PREFS = "retro"
    private const val MAX_DEPTH = 2

    class System(
        val platform: Platforms.Platform,
        val folders: List<File>,
        val games: List<Library.Rom>,
        val players: List<Platforms.Player>,
        val player: Platforms.Player?,
        /** The chosen Daijisho wallpaper pack's picture for this platform (WallpaperPacks), or null. */
        val wallpaper: File? = null,
    ) {
        val id: String get() = ID_PREFIX + platform.id
    }

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun playerId(context: Context, platform: String): String? = prefs(context).getString("player.$platform", null)

    fun setPlayer(context: Context, platform: String, player: String) {
        prefs(context).edit().putString("player.$platform", player).apply()
    }

    fun extraRoots(context: Context): List<String> =
        prefs(context).getString("roots", "").orEmpty().lines().map { it.trim() }.filter { it.isNotEmpty() }

    /** Storage volumes: internal storage and each SD card or USB drive under /storage. */
    private fun volumes(): List<File> {
        val out = LinkedHashSet<File>()
        out.add(Environment.getExternalStorageDirectory())
        File("/storage").listFiles()?.filter { it.isDirectory && it.name != "emulated" && it.name != "self" && it.canRead() }?.forEach { out.add(it) }
        return out.toList()
    }

    fun roots(context: Context): List<File> {
        val out = LinkedHashSet<File>()
        SessionPrefs.romsDir(context).takeIf { it.isNotEmpty() }?.let { out.add(File(it)) }
        for (v in volumes()) v.listFiles()?.filter { it.isDirectory && it.name.lowercase().startsWith("rom") }?.forEach { out.add(it) }
        extraRoots(context).forEach { out.add(File(it)) }
        return out.filter { it.isDirectory }.map { it.canonicalFile }.distinct()
    }

    private val notGames = setOf("srm", "sav", "state", "txt", "nfo", "png", "jpg", "jpeg", "xml", "dat", "rtc", "cfg", "ini", "db", "pdf", "mp4", "pup")

    /** Arcade BIOS sets that sit beside the games in MAME and FinalBurn folders. */
    private val biosSets = setOf("neogeo", "pgm", "qsound", "skns", "cpzn1", "cpzn2", "decocass", "isgsm", "naomi", "awbios", "hng64",
        "nmk004", "ym2608", "bubsys", "konamigx", "megaplay", "stvbios", "coh1000c", "coh1002m", "coh3002c", "playch10")

    private val arcade = setOf("mame", "neogeo", "fbneo", "cps1", "cps2", "cps3", "mame2003", "arcade")

    @Volatile private var arcadeTitles: Map<String, String>? = null

    /** MAME and FinalBurn set names -> titles (assets/retro/arcade-titles.tsv, from the MAME 2003-Plus metadata). */
    private fun arcadeTitle(context: Context, set: String): String? {
        val map = arcadeTitles ?: synchronized(this) {
            arcadeTitles ?: runCatching {
                context.assets.open("retro/arcade-titles.tsv").bufferedReader().useLines { lines ->
                    lines.mapNotNull { l -> l.split('\t', limit = 2).takeIf { it.size == 2 }?.let { it[0] to it[1] } }.toMap()
                }
            }.getOrDefault(emptyMap()).also { arcadeTitles = it }
        }
        return map[set.lowercase()]
    }

    /** The name shown: tags dropped, a release number ("0028 - ") and underscores gone; arcade sets by their title. */
    private fun displayTitle(context: Context, platform: String, stem: String): String {
        val isArcade = platform in arcade
        val name = if (isArcade) arcadeTitle(context, stem) ?: stem else stem
        return name.replace(Regex("\\s*[(\\[][^)\\]]*[)\\]]"), "")
            .let { if (isArcade) it else it.replace(Regex("^\\d{3,4}\\s*-\\s*"), "") }
            .replace('_', ' ').replace(Regex("\\s+"), " ").trim().ifEmpty { stem }
    }

    /** A folder's games: the files its player (or else the platform) takes, a .cue/.m3u standing for the files it names. */
    private fun games(context: Context, platform: Platforms.Platform, player: Platforms.Player?, folder: File): List<Library.Rom> {
        val accept = player?.accept ?: platform.accept
        val files = ArrayList<File>()
        folder.walkTopDown().maxDepth(MAX_DEPTH).filter { it.isFile && !it.name.startsWith(".") }.forEach { files.add(it) }
        val sheets = files.filter { it.extension.lowercase() in setOf("cue", "m3u", "gdi") }
        val named = sheets.flatMap { s -> runCatching { s.readLines().take(200) }.getOrDefault(emptyList()) }
            .flatMap { line -> Regex("[^\"\\\\/]+\\.[A-Za-z0-9]{2,4}").findAll(line).map { it.value.trim().lowercase() } }.toSet()
        return files.filter { f ->
            val ext = f.extension.lowercase()
            ext !in notGames && (accept == null || accept.matches(f.name)) &&
                !(ext == "zip" && f.nameWithoutExtension.lowercase() in biosSets) &&
                !(f.name.lowercase() in named && sheets.none { it == f })
        }.sortedBy { it.name.lowercase() }.map { f ->
            val rom = Library.Rom(displayTitle(context, platform.id, f.nameWithoutExtension), f, f.absolutePath, ID_PREFIX + platform.id)
            CoverArt.cached(context, rom)?.let { Library.Rom(rom.name, rom.hostPath, rom.guestPath, rom.emulatorId, it) } ?: rom
        }
    }

    fun scan(context: Context): List<System> {
        val byPlatform = LinkedHashMap<String, MutableList<File>>()
        for (root in roots(context)) {
            root.listFiles()?.filter { it.isDirectory }?.forEach { dir ->
                val p = Platforms.forFolder(context, dir.name) ?: return@forEach
                byPlatform.getOrPut(p.id) { ArrayList() }.add(dir)
            }
        }
        return byPlatform.mapNotNull { (id, folders) ->
            val platform = Platforms.byId(context, id) ?: return@mapNotNull null
            val players = Platforms.installedPlayers(context, platform).filter { AndroidLaunch.usable(it) }
            val chosen = playerId(context, id)?.let { pid -> players.firstOrNull { it.id == pid } } ?: byFolderName(players, folders) ?: players.firstOrNull()
            val games = folders.flatMap { games(context, platform, chosen, it) }
            if (games.isEmpty()) null else System(platform, folders, games, players, chosen, WallpaperPacks.forPlatform(context, platform))
        }.sortedBy { it.platform.name.lowercase() }
    }

    /** A RetroArch core the folder is named after ("Arcade - Mame 2003 Plus" -> mame2003_plus), the longest such name. */
    private fun byFolderName(players: List<Platforms.Player>, folders: List<File>): Platforms.Player? {
        val names = folders.map { it.name.lowercase().replace(Regex("[^a-z0-9]"), "") }
        return players.filter { p -> p.core != null && names.any { n -> p.core.lowercase().replace(Regex("[^a-z0-9]"), "").let { c -> c.length >= 4 && n.contains(c) } } }
            .maxByOrNull { it.core!!.length }
    }

    fun collectionsFor(context: Context, emulatorId: String): List<String>? {
        if (!emulatorId.startsWith(ID_PREFIX)) return null
        return Platforms.byId(context, emulatorId.removePrefix(ID_PREFIX))?.collection?.let { listOf(it) }
    }
}
