# Pull request text for Droid-Deck/DroidDeck (branch `rp4pro-framegen-session-reset`)

**Title:** framegen: survive a window size change and a second launch on Mali-G77 r32p1

## Symptom

On the Retroid Pocket 4 Pro (Mali-G77 MC9, Arm driver r32p1) with Win-FG on, the app process dies with
SIGSEGV inside `libGLES_mali.so` (fault address 0x40 or 0x68, from `vkp_framegen_run`) at the first frame after
the presenting window changes size - Steam's window to a game's - and at the second game launch in one process.
Users see it as "press Play twice": the first press crashes the app, the relaunched process works once.

## Cause

Two things in `framegen/ddfg` (the Win-FG engine):

- `FrameGen::onResize` destroys the pyramid images, and `destroyScratch` resets the descriptor pool, with no
  wait for the GPU, while the previous frame still uses them. Mali's driver faults on that where desktop drivers
  tolerate it.
- The engine keeps its descriptor sets in a process-wide static `g_scratch` keyed only by the frame size. An
  engine rebuilt at the same size (a second session of the same game) reuses sets from a pool the previous
  engine destroyed.

## Change

- `vkDeviceWaitIdle` before both teardowns (`framegen.cpp`, `record_impl.inc`).
- `FrameGen::destroy` drops the scratch with its pool.
- (first commit) `vkp_framegen_session_begin()` resets the engine and the ring at each session start, so a
  session never inherits the previous one's engine state.

## Verified

Win-FG x2: Steam (1920x1080 then 1333x750 scene) -> Ys Origin (1280x720) -> exit -> Ys Origin again, all in
one app process: generating at 60 fps on screen (300 interpolated frames per 10 s in the compositor's stats),
no crash, no device loss. Before the change the same sequence crashed at the first game window.

## Note on the build

The APK the fix was verified in was built from the `mali-test-build` fork of this tree (the shipped v0.5.4),
where the engine lives under `framegen/winfg`; the same two hunks are in this branch for `framegen/ddfg`.

Tested by yujikaido (the PR author) on their own Retroid Pocket 4 Pro; investigation and patches written with Claude Code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
