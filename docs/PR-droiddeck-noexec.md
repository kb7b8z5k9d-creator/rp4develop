# Pull request text for Droid-Deck/DroidDeck (branch `rp4pro-noexec-arm64ec`)

**Title:** preload/noexec: cover Wine's ARM64EC processes, not only FEX

## Symptom

A game installed on the SD card hangs at a black screen with sound (Ys Origin, 32-bit D3D8). Wine logs
`map_image_into_view failed to set 60000020 protection ... noexec filesystem?`, the ARM64EC FEX inside Wine
refuses the first call (`NoExec instruction in entry block`, access violation info[0]=8), and the main thread
ends in the game's own exception handler.

## Cause

Android mounts the SD card noexec. DroidDeck's shim `tools/linuxfs/preload/noexec.c` moves such mappings
only for processes named `FEX*`; Proton (ARM64, Wine ARM64EC) never got it, so the game's DLLs
(`release/programs/{ogg,vorbis,vorbisfile}.dll` on the card) could not be mapped executable.

## Change

Wine's processes count too (10 lines). Verified: Ys Origin reaches its title screen from the SD card at
61 fps on a Retroid Pocket 4 Pro. Built with the Zig cross toolchain from the `pr-1587` sources the shipped
runtime was built from; a build from `main` broke Zink's dma-buf sharing because `drm.c` differs there, which
may deserve its own look.

Tested by yujikaido (the PR author) on their own Retroid Pocket 4 Pro; investigation and patches written with Claude Code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
