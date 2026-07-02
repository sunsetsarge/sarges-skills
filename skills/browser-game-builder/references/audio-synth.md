# Web Audio Synth SFX Cookbook

Synthesize every game sound at runtime with the Web Audio API. **No audio files.**
Reasons this is the right default for a browser game:
- Nothing to license — a sourced sound clip can carry copyright; a sine wave can't.
- Nothing to download/decode — zero asset weight, no load stalls, works offline.
- Trivially parameterizable — pitch/length by unit or event, endless variety.

Reach for real audio files only if you want licensed music or voice-acted lines,
and then use explicitly royalty-free/CC0 sources and credit them.

## Core: one gain-enveloped voice
```js
let AC;
function audioInit(){ if(!AC){ try{ AC=new (AudioContext||webkitAudioContext)(); }catch(e){} }
  if(AC && AC.state==='suspended') AC.resume(); }   // call on first user gesture

function sfx(kind, x, y){
  if(muted || !AC) return;
  const vol = sfxVol(x,y); if(vol<=0) return;        // cull off-screen sounds
  if(sfxBudget<=0) return; sfxBudget--;              // throttle: cap voices/tick
  const t=AC.currentTime, g=AC.createGain();
  const out = AC.destination;
  if(vol<1){ const m=AC.createGain(); m.gain.value=vol; g.connect(m); m.connect(out); }
  else g.connect(out);
  VOICES[kind] ? VOICES[kind](t,g) : VOICES.click(t,g);
}
setInterval(()=>{ sfxBudget=8; }, 120);              // refill budget
```

**Positional culling** — silence sounds outside the viewport and soften toward
edges, so 200 units firing off-screen don't blow out the mix or the budget:
```js
function sfxVol(x,y){
  if(x==null || G.state!=='play') return 1;                       // UI sounds: full
  const L=G.cam.x, T=G.cam.y, R=L+innerWidth, B=T+innerHeight, m=140;
  if(x<L-m||x>R+m||y<T-m||y>B+m) return 0;                         // off-screen: mute
  const cx=(L+R)/2, cy=(T+B)/2, hw=(R-L)/2, hh=(B-T)/2;
  return clamp(1.05 - 0.6*Math.hypot((x-cx)/hw,(y-cy)/hh), 0.35, 1);
}
```

## Voice recipes
Each voice is `(t, g) => {…}` where `t`=start time, `g`=the gain node to output on.
Envelope with `gain.setValueAtTime` + `exponentialRampToValueAtTime` (ramp to a
tiny value like .001, never 0 — exp ramps can't reach 0).

```js
const VOICES = {
  // pitched blip down-sweep — machine-gun / small arms
  shoot(t,g){ const o=AC.createOscillator(); o.type='square';
    o.frequency.setValueAtTime(620,t); o.frequency.exponentialRampToValueAtTime(140,t+.06);
    g.gain.setValueAtTime(.025,t); g.gain.exponentialRampToValueAtTime(.001,t+.07);
    o.connect(g); o.start(t); o.stop(t+.08); },

  // saw down-sweep — rocket/missile launch
  rocket(t,g){ const o=AC.createOscillator(); o.type='sawtooth';
    o.frequency.setValueAtTime(300,t); o.frequency.exponentialRampToValueAtTime(90,t+.18);
    g.gain.setValueAtTime(.03,t); g.gain.exponentialRampToValueAtTime(.001,t+.2);
    o.connect(g); o.start(t); o.stop(t+.22); },

  // filtered noise burst — explosion
  boom(t,g){ const len=AC.sampleRate*.4, buf=AC.createBuffer(1,len,AC.sampleRate), d=buf.getChannelData(0);
    for(let i=0;i<len;i++) d[i]=(Math.random()*2-1)*(1-i/len);   // decaying noise
    const n=AC.createBufferSource(); n.buffer=buf;
    const f=AC.createBiquadFilter(); f.type='lowpass'; f.frequency.value=500;
    n.connect(f); f.connect(g); g.gain.setValueAtTime(.12,t); g.gain.exponentialRampToValueAtTime(.001,t+.4);
    n.start(t); },

  // two rising sines — cash / build-complete chime
  cash(t,g){ const o=AC.createOscillator(); o.type='sine';
    o.frequency.setValueAtTime(880,t); o.frequency.setValueAtTime(1320,t+.07);
    g.gain.setValueAtTime(.03,t); g.gain.exponentialRampToValueAtTime(.001,t+.15);
    o.connect(g); o.start(t); o.stop(t+.16); },

  // short triangle tick — UI click / select
  click(t,g){ const o=AC.createOscillator(); o.type='triangle'; o.frequency.value=520;
    g.gain.setValueAtTime(.04,t); g.gain.exponentialRampToValueAtTime(.001,t+.05);
    o.connect(g); o.start(t); o.stop(t+.06); },
};
```

Derive the rest by varying pitch/length/waveform of these primitives:
- **flame** = boom recipe, longer, band-pass ~800Hz, lower gain sustain.
- **AA/gatling** = shoot recipe, higher pitch, fire it 4× rapidly.
- **unit ready / move / attack ack** = short click/sine motifs, a slightly
  different pitch per faction so armies sound distinct without voice acting.
- **low-power / under-attack EVA** = a two-tone alarm (two alternating sines); gate
  so it can't spam more than once every few seconds.
- **victory / defeat** = a rising vs falling 3-note arpeggio.

## Event coverage checklist
Wire a sound to every one of these or the game feels mute:
UI click · place/build · build-complete · unit select · unit move-order ·
each weapon type firing · unit takes-fatal-damage/explodes · building destroyed ·
harvester deposits (cash) · low-power · under-attack · superweapon ready/launch ·
victory · defeat · a quiet ambient bed (optional looping pad).

## Ambient / music (optional)
A slow evolving pad from 2–3 detuned oscillators through a lowpass with a slow LFO
gives an ambient bed with no files. If you want real music, use CC0/royalty-free
tracks, keep them small, credit the source, and lazy-load after first interaction.
