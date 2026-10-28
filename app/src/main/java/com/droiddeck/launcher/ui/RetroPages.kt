package com.droiddeck.launcher.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.lazy.itemsIndexed
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

/** Where the Retro pages were: the system last opened (the cards start there), and whether to focus a gallery's first game. */
internal object RetroNav {
    @Volatile var lastPlatform: String? = null
    @Volatile var focusFirst = false
    /** L1/R1 while a Retro page shows, wherever focus is (MainActivity.dispatchKeyEvent): -1 previous, +1 next system. */
    @Volatile var onShoulder: ((Int) -> Unit)? = null
    /** Retro mode (RetroMode) is up, full screen over the rail; kept while a game plays, so Home comes back to it. */
    var open by mutableStateOf(false)
}

/** Takes L1/R1 while [active]: the newest active page has them, and hands them back when it goes or stops being active. */
@Composable
internal fun ShoulderKeys(active: Boolean = true, handler: (Int) -> Unit) {
    val current by androidx.compose.runtime.rememberUpdatedState(handler)
    androidx.compose.runtime.DisposableEffect(active) {
        if (!active) return@DisposableEffect onDispose { }
        val h: (Int) -> Unit = { current(it) }
        val before = RetroNav.onShoulder
        RetroNav.onShoulder = h
        onDispose { if (RetroNav.onShoulder === h) RetroNav.onShoulder = before }
    }
}

@Composable
internal fun PlatformCard(
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
            // the system's settings: which emulator plays it (its folders are listed in the same pop-up)
            if (settings) RetroEmulatorDialog(sys, a) { settings = false }
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

/** A platform's games as a wall of box art (or a list), with the selected game's details in a bar at the bottom. */
@Composable
internal fun RetroGallery(
    s: FrontEndState, a: FrontEndActions, selected: String, onSelect: (String) -> Unit, modifier: Modifier,
    active: Boolean = true, // false while a page covers it (retro mode keeps it under a game's page)
    refocus: Int = 0, // bumped to put focus back on the game last focused
) {
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
    val cells = remember(id) { HashMap<Int, FocusRequester>() }
    val cellFor: (Int) -> FocusRequester = { i -> if (i == shown.firstOrNull()?.index) firstGame else cells.getOrPut(i) { FocusRequester() } }
    LaunchedEffect(refocus) {
        val i = focusedIndex ?: return@LaunchedEffect
        if (refocus == 0) return@LaunchedEffect
        repeat(10) { if (runCatching { cellFor(i).requestFocus() }.isSuccess) return@LaunchedEffect; kotlinx.coroutines.delay(50) }
    }
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
    ShoulderKeys(active, jump)
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
                        ListTitle(g, g.hostPath.path in s.retroFavorites, pick == i, cellFor(i), { focusedIndex = i }) {
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
                itemsIndexed(shown) { _, (i, g) -> GalleryCell(g, focusedIndex == i, cellFor(i), { focusedIndex = i }) { open(i) } }
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
