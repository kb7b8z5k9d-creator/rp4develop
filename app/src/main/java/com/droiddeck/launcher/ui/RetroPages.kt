package com.droiddeck.launcher.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.gestures.snapping.rememberSnapFlingBehavior
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Casino
import androidx.compose.material.icons.outlined.FolderOpen
import androidx.compose.material.icons.outlined.PlayArrow
import androidx.compose.material.icons.outlined.ViewList
import androidx.compose.material.icons.outlined.ViewModule
import androidx.compose.material.icons.outlined.Wallpaper
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.droiddeck.launcher.R
import com.droiddeck.launcher.frontend.Library
import com.droiddeck.launcher.frontend.RetroLibrary
import kotlinx.coroutines.launch

/** Where the Retro pages were: the system last opened (the carousel starts there), and whether to focus a gallery's first game. */
internal object RetroNav {
    @Volatile var lastPlatform: String? = null
    @Volatile var focusFirst = false
    /** L1/R1 while a Retro page shows, wherever focus is (MainActivity.dispatchKeyEvent): -1 previous, +1 next system. */
    @Volatile var onShoulder: ((Int) -> Unit)? = null
}

@Composable
private fun ShoulderKeys(handler: (Int) -> Unit) {
    val current by androidx.compose.runtime.rememberUpdatedState(handler)
    androidx.compose.runtime.DisposableEffect(Unit) {
        val h: (Int) -> Unit = { current(it) }
        RetroNav.onShoulder = h
        onDispose { if (RetroNav.onShoulder === h) RetroNav.onShoulder = null }
    }
}

/** The Retro page's platforms: one card per system (its wallpaper, or its covers fanned out), sideways, as Daijishō shows them. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
internal fun RetroPlatforms(s: FrontEndState, a: FrontEndActions, onSelect: (String) -> Unit, modifier: Modifier) {
    val colors = MaterialTheme.colorScheme
    var picker by remember { mutableStateOf(false) }
    var paths by remember { mutableStateOf(false) }
    val list = rememberLazyListState(s.retro.indexOfFirst { it.platform.id == RetroNav.lastPlatform }.coerceAtLeast(0))
    val scope = rememberCoroutineScope()
    val libraryButtons = remember { HashMap<Int, FocusRequester>() }
    val step: (Int) -> Unit = { d ->
        if (s.retro.isNotEmpty()) {
            val t = (list.firstVisibleItemIndex + d).mod(s.retro.size)
            scope.launch {
                list.animateScrollToItem(t)
                runCatching { libraryButtons[t]?.requestFocus() }
            }
        }
    }
    ShoulderKeys(step)
    Column(modifier.fillMaxSize().padding(horizontal = 22.dp, vertical = 14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(stringResource(R.string.retro_title), fontSize = 28.sp, fontWeight = FontWeight.Black, color = colors.onBackground)
            Chip(stringResource(R.string.retro_games_count, s.retro.sumOf { it.games.size }), ok = false)
            Spacer(Modifier.weight(1f))
            SecondaryButton(stringResource(R.string.retro_paths), compact = true) { paths = !paths; picker = false }
            SecondaryButton(s.retroPack ?: stringResource(R.string.retro_wallpapers), compact = true) {
                picker = !picker; paths = false
                if (picker) a.onRetroWallpaperList()
            }
        }
        if (paths) {
            RootsPanel(s, a, Modifier.weight(1f).padding(top = 12.dp))
            return@Column
        }
        if (picker) {
            WallpaperPicker(s, a, Modifier.weight(1f).padding(top = 12.dp)) { picker = false }
            return@Column
        }
        if (s.retro.isEmpty()) {
            Box(Modifier.padding(top = 16.dp)) { Note(stringResource(R.string.retro_empty)) }
            return@Column
        }
        BoxWithConstraints(Modifier.weight(1f).fillMaxWidth().padding(top = 12.dp)) {
            val cardW = (maxWidth * 0.84f).coerceAtMost(760.dp)
            val side = (maxWidth - cardW) / 2
            LazyRow(
                state = list,
                flingBehavior = rememberSnapFlingBehavior(list),
                contentPadding = PaddingValues(horizontal = side),
                horizontalArrangement = Arrangement.spacedBy(18.dp),
                modifier = Modifier.fillMaxSize(),
            ) {
                itemsIndexed(s.retro, key = { _, sys -> sys.platform.id }) { i, sys ->
                    PlatformCard(sys, i, s.retro.size, a, onSelect, Modifier.width(cardW).fillMaxHeight(), libraryButtons.getOrPut(i) { FocusRequester() }) {
                        scope.launch { list.animateScrollToItem(i) }
                    }
                }
            }
        }
        LazyRow(horizontalArrangement = Arrangement.spacedBy(14.dp), modifier = Modifier.fillMaxWidth().padding(top = 10.dp)) {
            itemsIndexed(s.retro) { i, sys ->
                val current = list.firstVisibleItemIndex == i
                Text(
                    sys.platform.shortname.uppercase(), fontSize = 12.sp, fontWeight = if (current) FontWeight.Black else FontWeight.Bold,
                    fontStyle = FontStyle.Italic, color = if (current) colors.onBackground else colors.onSurfaceVariant,
                    modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable { scope.launch { list.animateScrollToItem(i) } }.padding(horizontal = 4.dp, vertical = 2.dp),
                )
            }
        }
    }
}

@Composable
private fun PlatformCard(
    sys: RetroLibrary.System, index: Int, count: Int, a: FrontEndActions, onSelect: (String) -> Unit, modifier: Modifier,
    library: FocusRequester, onFocused: () -> Unit,
) {
    var settings by remember { mutableStateOf(false) }
    Box(
        modifier.shadow(18.dp, RoundedCornerShape(26.dp)).clip(RoundedCornerShape(26.dp))
            .background(artBrush(hueOf(sys.platform.name)))
            .onFocusChanged { if (it.hasFocus) onFocused() },
    ) {
        val wall = sys.wallpaper
        if (wall != null) AsyncImage(model = wall, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
        else FannedCovers(sys.games.filter { it.art != null }.take(3), Modifier.align(Alignment.CenterEnd).fillMaxHeight().padding(end = 28.dp, top = 18.dp, bottom = 18.dp))
        Box(Modifier.fillMaxSize().background(Brush.horizontalGradient(0f to Color.Black.copy(alpha = 0.55f), 0.6f to Color.Transparent)))
        Column(Modifier.align(Alignment.BottomStart).padding(22.dp).widthIn(max = 460.dp)) {
            Text(sys.platform.name, fontSize = 34.sp, fontWeight = FontWeight.Black, fontStyle = FontStyle.Italic, color = Color.White, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(
                stringResource(R.string.retro_card_line, sys.games.size, index + 1, count),
                fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = Color.White.copy(alpha = 0.85f), modifier = Modifier.padding(top = 2.dp, bottom = 12.dp),
            )
            // the system's settings: which emulator plays it, and the folders its games come from
            if (settings) Column(
                Modifier.padding(bottom = 10.dp).clip(RoundedCornerShape(14.dp)).background(MaterialTheme.colorScheme.surface.copy(alpha = 0.94f)).padding(12.dp),
            ) {
                RetroPlayerPicker(sys, a)
                Text(stringResource(R.string.retro_paths_title), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 10.dp, bottom = 2.dp))
                Text(sys.folders.joinToString("\n") { it.path }, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurface)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                PrimaryButton(stringResource(R.string.retro_library), compact = true, icon = Icons.Outlined.PlayArrow, modifier = Modifier.focusRequester(library)) {
                    RetroNav.lastPlatform = sys.platform.id
                    RetroNav.focusFirst = true
                    onSelect("rsys:${sys.platform.id}")
                }
                SecondaryButton(stringResource(R.string.retro_random), compact = true) { if (sys.games.isNotEmpty()) a.onRetroGame(sys, sys.games.random()) }
                SecondaryButton(stringResource(R.string.retro_settings), compact = true) { settings = !settings }
            }
        }
    }
}

@Composable
private fun FannedCovers(games: List<Library.Rom>, modifier: Modifier) {
    Box(modifier.aspectRatio(1.1f), contentAlignment = Alignment.Center) {
        val angles = listOf(-9f, 0f, 9f)
        val shifts = listOf(-70, 0, 70)
        games.forEachIndexed { i, g ->
            val n = games.size
            val k = if (n == 1) 1 else if (n == 2) i * 2 else i
            AsyncImage(
                model = g.art, contentDescription = null, contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxHeight(0.86f).aspectRatio(0.72f)
                    .graphicsLayer { rotationZ = angles[k]; translationX = shifts[k].dp.toPx(); shadowElevation = 16.dp.toPx() },
            )
        }
    }
}

@Composable
private fun RootsPanel(s: FrontEndState, a: FrontEndActions, modifier: Modifier) {
    val colors = MaterialTheme.colorScheme
    Column(modifier.fillMaxWidth()) {
        Text(stringResource(R.string.retro_paths_title), fontSize = 18.sp, fontWeight = FontWeight.Bold, color = colors.onBackground)
        Text(stringResource(R.string.retro_paths_hint), fontSize = 13.sp, color = colors.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp, bottom = 10.dp))
        LazyColumn(Modifier.weight(1f, fill = false).fillMaxWidth()) {
            itemsIndexed(s.retroRoots) { _, path ->
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    Text(path, fontSize = 14.sp, color = colors.onBackground, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    SecondaryButton(stringResource(R.string.retro_remove), compact = true) { a.onRetroRemoveRoot(path) }
                }
            }
        }
        Box(Modifier.padding(top = 10.dp)) { PrimaryButton(stringResource(R.string.retro_add_folder), compact = true) { a.onRetroAddRoot() } }
    }
}

@Composable
private fun WallpaperPicker(s: FrontEndState, a: FrontEndActions, modifier: Modifier, onDone: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Column(modifier.fillMaxWidth()) {
        Text(stringResource(R.string.retro_wallpapers_hint), fontSize = 13.sp, color = colors.onSurfaceVariant, modifier = Modifier.padding(bottom = 8.dp))
        if (s.retroPackBusy != null) Text(stringResource(R.string.retro_wallpapers_busy, s.retroPackBusy), fontSize = 13.sp, color = colors.onBackground, modifier = Modifier.padding(bottom = 8.dp))
        val names = listOf<String?>(null) + s.retroPacks
        LazyColumn(Modifier.fillMaxWidth()) {
            itemsIndexed(names) { _, name ->
                val label = name ?: stringResource(R.string.retro_wallpapers_none)
                val chosen = name == s.retroPack
                Text(
                    (if (chosen) "● " else "") + label, fontSize = 15.sp, fontWeight = if (chosen) FontWeight.Bold else FontWeight.Normal, color = colors.onBackground,
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).clickable(enabled = s.retroPackBusy == null) { a.onRetroWallpaperPack(name); onDone() }
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                )
            }
        }
    }
}

/** A platform's games as a wall of box art (or a list), with the selected game's details in a bar at the bottom. */
@Composable
internal fun RetroGallery(s: FrontEndState, a: FrontEndActions, selected: String, onSelect: (String) -> Unit, modifier: Modifier) {
    val colors = MaterialTheme.colorScheme
    val id = selected.substringAfter(':')
    val sys = s.retro.firstOrNull { it.platform.id == id }
    if (sys == null) {
        Box(modifier.padding(22.dp)) { Note(stringResource(R.string.content_rom_gone)) }
        return
    }
    var listView by rememberSaveable { mutableStateOf(false) }
    var focusedIndex by remember(id) { mutableStateOf<Int?>(null) }
    var filter by rememberSaveable(id) { mutableStateOf(0) } // 0 all, 1 recent, 2 favourites
    val recent = remember(sys.games, s.retroStats) {
        sys.games.withIndex().filter { s.retroStats[it.value.hostPath.path] != null }.sortedByDescending { s.retroStats[it.value.hostPath.path]?.last ?: 0L }
    }
    val favorites = remember(sys.games, s.retroFavorites) { sys.games.withIndex().filter { it.value.hostPath.path in s.retroFavorites } }
    val shown = when (filter) { 1 -> recent; 2 -> favorites; else -> sys.games.withIndex().toList() }
    val firstGame = remember { FocusRequester() }
    LaunchedEffect(id, listView) {
        RetroNav.lastPlatform = id
        if (RetroNav.focusFirst) {
            RetroNav.focusFirst = false
            repeat(10) { if (runCatching { firstGame.requestFocus() }.isSuccess) return@LaunchedEffect; kotlinx.coroutines.delay(50) }
        }
    }
    val jump: (Int) -> Unit = { d ->
        val at = s.retro.indexOfFirst { it.platform.id == id }
        if (at >= 0 && s.retro.size > 1) {
            RetroNav.focusFirst = true
            onSelect("rsys:" + s.retro[(at + d).mod(s.retro.size)].platform.id)
        }
    }
    ShoulderKeys(jump)
    Column(modifier.fillMaxSize()) {
        if (!listView) Row(
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
            modifier = Modifier.fillMaxWidth().padding(start = 18.dp, end = 18.dp, top = 12.dp, bottom = 8.dp),
        ) {
            Text(sys.platform.name, fontSize = 22.sp, fontWeight = FontWeight.Black, color = colors.onBackground, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.widthIn(max = 360.dp))
            SecondaryButton(if (listView) stringResource(R.string.retro_grid_view) else stringResource(R.string.retro_list_view), compact = true) { listView = !listView }
            FilterChip(stringResource(R.string.retro_items, sys.games.size), filter == 0) { filter = 0 }
            FilterChip(stringResource(R.string.retro_recent, recent.size), filter == 1) { filter = if (filter == 1) 0 else 1 }
            FilterChip(stringResource(R.string.retro_favorites, favorites.size), filter == 2) { filter = if (filter == 2) 0 else 2 }
        }
        val open: (Int) -> Unit = { i -> onSelect("rgame:${sys.platform.id}:$i") }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            if (listView) Row(Modifier.fillMaxSize()) {
                // Daijisho's list: titles on the left, the selected game's cover, name and buttons on the right
                val pick = focusedIndex?.takeIf { f -> shown.any { it.index == f } } ?: shown.firstOrNull()?.index
                LazyColumn(Modifier.weight(0.46f).fillMaxHeight().padding(start = 12.dp, end = 6.dp)) {
                    itemsIndexed(shown) { _, (i, g) ->
                        ListTitle(g, g.hostPath.path in s.retroFavorites, pick == i, if (i == shown.first().index) firstGame else null, { focusedIndex = i }) {
                            if (pick == i) a.onRetroGame(sys, g) else focusedIndex = i
                        }
                    }
                }
                val sel = pick?.let { sys.games.getOrNull(it) }
                if (sel != null) ListDetail(s, a, sys, sel, filter == 1, Modifier.weight(0.54f).fillMaxHeight(),
                    onRecent = { filter = if (filter == 1) 0 else 1 }, onGrid = { listView = false }) { open(pick) }
            } else LazyVerticalGrid(
                columns = GridCells.Adaptive(118.dp), modifier = Modifier.fillMaxSize().padding(horizontal = 10.dp),
                contentPadding = PaddingValues(bottom = 8.dp),
            ) {
                itemsIndexed(shown) { _, (i, g) -> GalleryCell(g, focusedIndex == i, if (i == shown.first().index) firstGame else null, { focusedIndex = i }) { open(i) } }
            }
        }
        val g = focusedIndex?.let { sys.games.getOrNull(it) }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth().background(colors.surface).padding(horizontal = 18.dp, vertical = 8.dp),
        ) {
            if (listView) Text(
                stringResource(R.string.retro_list_status, sys.platform.name, ((focusedIndex ?: shown.firstOrNull()?.index ?: 0) + 1), sys.games.size),
                fontSize = 13.sp, color = colors.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f),
            ) else Text(
                if (g != null) listOfNotNull(
                    g.name, sys.info[g.hostPath.path]?.line()?.takeIf { it.isNotEmpty() },
                    s.retroStats[g.hostPath.path]?.let { st -> playedLine(st) },
                ).joinToString(" · ")
                else sys.platform.name,
                fontSize = 13.sp, color = colors.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f),
            )
            Text(stringResource(R.string.retro_gallery_keys), fontSize = 12.sp, fontWeight = FontWeight.Bold, color = colors.onBackground)
        }
    }
}

@Composable
internal fun playedLine(st: com.droiddeck.launcher.frontend.RetroStats.Stat): String =
    stringResource(R.string.retro_played, android.text.format.DateUtils.getRelativeTimeSpanString(st.last).toString(), st.count)

@Composable
private fun FilterChip(text: String, on: Boolean, onClick: () -> Unit) {
    if (on) PrimaryButton(text, compact = true) { onClick() } else SecondaryButton(text, compact = true) { onClick() }
}

@Composable
private fun GalleryCell(g: Library.Rom, focused: Boolean, req: FocusRequester?, onFocus: () -> Unit, onClick: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.then(if (req != null) Modifier.focusRequester(req) else Modifier).padding(4.dp).clip(RoundedCornerShape(12.dp))
            .background(if (focused) colors.surfaceVariant else Color.Transparent)
            .onFocusChanged { if (it.isFocused) onFocus() }
            .clickable { onFocus(); onClick() }
            .padding(6.dp),
    ) {
        Box(Modifier.fillMaxWidth().aspectRatio(1f), contentAlignment = Alignment.Center) {
            if (g.art != null) AsyncImage(model = g.art, contentDescription = g.name, contentScale = ContentScale.Fit, modifier = Modifier.fillMaxSize().clip(RoundedCornerShape(6.dp)))
            else Box(Modifier.fillMaxHeight().aspectRatio(0.75f).clip(RoundedCornerShape(8.dp)).background(artBrush(hueOf(g.name))), contentAlignment = Alignment.BottomStart) {
                Text(g.name, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = Color.White, maxLines = 3, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(6.dp))
            }
        }
        Text(
            g.name, fontSize = 13.sp, fontWeight = FontWeight.Bold, fontStyle = FontStyle.Italic, color = colors.onBackground,
            textAlign = TextAlign.Center, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 6.dp).height(36.dp),
        )
    }
}

@Composable
private fun ListTitle(g: Library.Rom, favorite: Boolean, selected: Boolean, req: FocusRequester?, onFocus: () -> Unit, onClick: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    val pal = LocalPalette.current
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.then(if (req != null) Modifier.focusRequester(req) else Modifier).fillMaxWidth().padding(vertical = 1.dp).clip(RoundedCornerShape(50))
            .background(if (selected) pal.signal else Color.Transparent)
            .onFocusChanged { if (it.isFocused) onFocus() }.clickable { onClick() }
            .padding(horizontal = 14.dp, vertical = 7.dp),
    ) {
        Text(g.name, fontSize = 16.sp, fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
            color = if (selected) Color.White else colors.onBackground, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
        if (favorite) Text("♥", fontSize = 15.sp, color = Color(0xFFE0457B), modifier = Modifier.padding(start = 6.dp))
    }
}

@Composable
private fun ListDetail(
    s: FrontEndState, a: FrontEndActions, sys: RetroLibrary.System, g: Library.Rom, recentOn: Boolean, modifier: Modifier,
    onRecent: () -> Unit, onGrid: () -> Unit, onDetail: () -> Unit,
) {
    val colors = MaterialTheme.colorScheme
    val context = androidx.compose.ui.platform.LocalContext.current
    val stat = s.retroStats[g.hostPath.path]
    val favorite = g.hostPath.path in s.retroFavorites
    val snap = remember(g.hostPath.path, g.art) { com.droiddeck.launcher.frontend.CoverArt.snap(context, g) }
    Column(modifier.padding(start = 6.dp, end = 14.dp, top = 8.dp, bottom = 6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.weight(1f).fillMaxWidth().clip(RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) {
            if (snap != null) AsyncImage(model = snap, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
            if (g.art != null) AsyncImage(
                model = g.art, contentDescription = g.name, contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxHeight(0.8f).fillMaxWidth(0.6f).graphicsLayer { shadowElevation = 18.dp.toPx() },
            ) else Box(Modifier.fillMaxHeight(0.9f).aspectRatio(0.75f).clip(RoundedCornerShape(10.dp)).background(artBrush(hueOf(g.name))), contentAlignment = Alignment.BottomStart) {
                Text(g.name, fontSize = 14.sp, fontWeight = FontWeight.Bold, color = Color.White, modifier = Modifier.padding(8.dp))
            }
        }
        Text(g.name, fontSize = 19.sp, fontWeight = FontWeight.Black, fontStyle = FontStyle.Italic, color = colors.onBackground,
            textAlign = TextAlign.Center, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 8.dp))
        Text(
            listOfNotNull(
                sys.info[g.hostPath.path]?.genre?.takeIf { it.isNotBlank() },
                stringResource(R.string.retro_list_played, stat?.let { android.text.format.DateUtils.getRelativeTimeSpanString(it.last).toString() }
                    ?: stringResource(R.string.retro_none), stat?.count ?: 0),
            ).joinToString(" • "),
            fontSize = 12.sp, color = colors.onSurfaceVariant, textAlign = TextAlign.Center, maxLines = 1, overflow = TextOverflow.Ellipsis,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
            PrimaryButton(stringResource(R.string.retro_play), compact = true, icon = Icons.Outlined.PlayArrow, enabled = sys.player != null) { a.onRetroGame(sys, g) }
            SecondaryButton(if (favorite) stringResource(R.string.retro_remove_favorite) else stringResource(R.string.retro_add_favorite), compact = true) { a.onRetroFavorite(g) }
            if (recentOn) PrimaryButton(stringResource(R.string.retro_recent_button), compact = true) { onRecent() }
            else SecondaryButton(stringResource(R.string.retro_recent_button), compact = true) { onRecent() }
            SecondaryButton(stringResource(R.string.retro_detail), compact = true) { onDetail() }
            SecondaryButton(stringResource(R.string.retro_grid_view), compact = true) { onGrid() }
        }
    }
}

@Composable
private fun GalleryRow(g: Library.Rom, detail: String, favorite: Boolean, focused: Boolean, onFocus: () -> Unit, onClick: () -> Unit) {
    val colors = MaterialTheme.colorScheme
    Row(
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp)).background(if (focused) colors.surfaceVariant else Color.Transparent)
            .onFocusChanged { if (it.isFocused) onFocus() }.clickable { onFocus(); onClick() }.padding(horizontal = 8.dp, vertical = 6.dp),
    ) {
        Box(Modifier.size(64.dp), contentAlignment = Alignment.Center) {
            if (g.art != null) AsyncImage(model = g.art, contentDescription = null, contentScale = ContentScale.Fit, modifier = Modifier.fillMaxSize())
            else Box(Modifier.fillMaxHeight().aspectRatio(0.75f).clip(RoundedCornerShape(6.dp)).background(artBrush(hueOf(g.name))))
        }
        Column(Modifier.weight(1f)) {
            Text((if (favorite) "★ " else "") + g.name, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = colors.onBackground, maxLines = 1, overflow = TextOverflow.Ellipsis)
            if (detail.isNotEmpty()) Text(detail, fontSize = 13.sp, color = colors.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 2.dp))
        }
    }
}
