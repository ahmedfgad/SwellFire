# Background music

Eight action-forward loops, rendered from MIDI through a General-MIDI soundfont
by `tools/gen_world_music_sf2.py`. Every note is a *recorded* GM instrument
sample played by FluidSynth (no synthesized-waveform noise); the music is
original to Swellfire and shares nothing with the sibling CoinTex soundtrack.

- `bg_music_menu.wav`   — title screen, anthemic synth-pop runner hook (E major)
- `bg_music_world1.wav` — Meadow, sunny folk-pop gallop, steel guitar + glockenspiel (G major)
- `bg_music_world2.wav` — Desert, chase groove, sitar + taiko (A Phrygian-dominant)
- `bg_music_world3.wav` — Industrial, mechanical electro-funk, clavinet + distortion (C minor)
- `bg_music_world4.wav` — Snowfield, crystalline ice-trance, glockenspiel + choir pad (E major)
- `bg_music_world5.wav` — Volcano, molten metal march, distortion power chords + brass (F# minor)
- `bg_music_world6.wav` — Cosmos, driving space synthwave, pulsing saw arp (A minor)
- `bg_music_boss.wav`   — boss fights, epic battle, brass + distortion + taiko (D minor)

All are 44.1 kHz / 16-bit / mono, ~20 s seamless loops (played with `loop=True`
by `audio.py`). Re-generate with `python tools/gen_world_music_sf2.py`
(`--only world5,boss` to rebuild a subset). Dev/build-time only: it needs the
`fluidsynth` binary and a GM soundfont (default
`/usr/share/sounds/sf2/default-GM.sf2`), but numpy/FluidSynth are NOT runtime
dependencies — the WAVs ship pre-generated and `audio.py` just loads them.
