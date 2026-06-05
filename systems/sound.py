"""Savage Dungeon — 音效管理器（基于 faatt.py 音频合成引擎）"""

import os
import io
import sys
import pygame

# 将项目根目录和 tools/ 加入 sys.path，以便导入 faatt
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tools_dir = os.path.join(_project_root, "tools")
for _p in (_tools_dir, _project_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---- 可选依赖标记 ----
_SYNTH_AVAILABLE = False
try:
    import numpy as np
    from scipy.io import wavfile as _wavfile
    from faatt import (
        synthesize_voice, SynthVoice, OscType, EnvShape, EffectChain, SR,
    )
    _SYNTH_AVAILABLE = True
except Exception:
    pass

SR = 44100  # 回退采样率
AUDIO_DIR = os.path.join(_project_root, "assets", "audio")
SFX_DIR = os.path.join(AUDIO_DIR, "sfx")


# ========================================================
#  地牢专用音效预设（基于 faatt 引擎）
# ========================================================
if _SYNTH_AVAILABLE:
    DUNGEON_SFX: dict[str, SynthVoice] = {
        # ---- 移动/探索 ----
        "step": SynthVoice(
            freq=90.0, osc_type=OscType.NOISE_PINK, duration=0.06,
            volume=0.12, env_shape=EnvShape.PERCUSSIVE,
            effect_chain=EffectChain(lp_filter_hz=1500, hp_filter_hz=80),
        ),
        "explore_safe": SynthVoice(
            freq=600.0, osc_type=OscType.SINE, duration=0.12,
            volume=0.30, env_shape=EnvShape.PERCUSSIVE,
            effect_chain=EffectChain(reverb_mix=0.08),
        ),
        "explore_threat": SynthVoice(
            freq=300.0, osc_type=OscType.SQUARE, duration=0.22,
            volume=0.35, env_shape=EnvShape.PERCUSSIVE,
            pitch_mod=-3,
            effect_chain=EffectChain(lp_filter_hz=4000, reverb_mix=0.1),
        ),

        # ---- 战斗 ----
        "monster_defeat": SynthVoice(
            freq=400.0, osc_type=OscType.SAW, duration=0.35,
            volume=0.45, env_shape=EnvShape.SWELL,
            pitch_mod=-5,
            harmonics=[(2.0, 0.2), (0.5, 0.15)],
            effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.4),
        ),
        "trap_dodge": SynthVoice(
            freq=2000.0, osc_type=OscType.NOISE_WHITE, duration=0.08,
            volume=0.28, env_shape=EnvShape.PERCUSSIVE,
            effect_chain=EffectChain(lp_filter_hz=8000, hp_filter_hz=2500),
        ),
        "damage_taken": SynthVoice(
            freq=140.0, osc_type=OscType.SAW, duration=0.28,
            volume=0.45, env_shape=EnvShape.REVERSE,
            pitch_mod=-10,
            effect_chain=EffectChain(
                lp_filter_hz=2000, distortion=0.2,
                reverb_mix=0.12, stereo_width=0.25,
            ),
        ),
        "critical_hit": SynthVoice(
            freq=260.0, osc_type=OscType.NOISE_BROWN, duration=0.22,
            volume=0.55, env_shape=EnvShape.PERCUSSIVE,
            effect_chain=EffectChain(
                lp_filter_hz=3500, distortion=0.4, bit_crush=8,
                reverb_mix=0.12,
            ),
            harmonics=[(2.0, 0.25)],
        ),
        "monster_slain": SynthVoice(
            freq=220.0, osc_type=OscType.SAW, duration=0.50,
            volume=0.50, env_shape=EnvShape.REVERSE,
            pitch_mod=-14,
            effect_chain=EffectChain(
                lp_filter_hz=2500, reverb_mix=0.2, reverb_decay=0.7,
                distortion=0.15, stereo_width=0.3,
            ),
            harmonics=[(0.5, 0.25), (1.5, 0.18)],
        ),

        # ---- UI ----
        "flag": SynthVoice(
            freq=780.0, osc_type=OscType.TRIANGLE, duration=0.08,
            volume=0.30, env_shape=EnvShape.PERCUSSIVE,
            pitch_mod=2,
        ),
        "perception": SynthVoice(
            freq=900.0, osc_type=OscType.SINE, duration=0.20,
            volume=0.28, env_shape=EnvShape.SWELL,
            pitch_mod=5,
            effect_chain=EffectChain(reverb_mix=0.15, reverb_decay=0.35),
        ),
        "benny_use": SynthVoice(
            freq=660.0, osc_type=OscType.SINE, duration=0.30,
            volume=0.38, env_shape=EnvShape.SWELL,
            pitch_mod=7,
            harmonics=[(2.0, 0.15)],
            vibrato_rate=5, vibrato_depth=1.5,
            effect_chain=EffectChain(reverb_mix=0.18, reverb_decay=0.45),
        ),
        "benny_restore": SynthVoice(
            freq=523.25, osc_type=OscType.TRIANGLE, duration=0.18,
            volume=0.40, env_shape=EnvShape.PERCUSSIVE,
            pitch_mod=4,
            effect_chain=EffectChain(reverb_mix=0.10),
        ),

        # ---- 系统 ----
        "game_over": SynthVoice(
            freq=200.0, osc_type=OscType.SAW, duration=1.0,
            volume=0.40, env_shape=EnvShape.REVERSE,
            pitch_mod=-12,
            effect_chain=EffectChain(
                lp_filter_hz=2000, reverb_mix=0.25, reverb_decay=1.2,
                stereo_width=0.35,
            ),
        ),
        "menu_open": SynthVoice(
            freq=440.0, osc_type=OscType.SINE, duration=0.22,
            volume=0.35, env_shape=EnvShape.SWELL,
            pitch_mod=5,
            effect_chain=EffectChain(reverb_mix=0.1),
        ),
        "menu_close": SynthVoice(
            freq=550.0, osc_type=OscType.SINE, duration=0.18,
            volume=0.30, env_shape=EnvShape.REVERSE,
            pitch_mod=-4,
        ),

        # ---- 特殊 ----
        "wall_bump": SynthVoice(
            freq=160.0, osc_type=OscType.SQUARE, duration=0.10,
            volume=0.25, env_shape=EnvShape.PERCUSSIVE,
            effect_chain=EffectChain(lp_filter_hz=1200, bit_crush=8),
        ),
        "blocked": SynthVoice(
            freq=200.0, osc_type=OscType.SQUARE, duration=0.12,
            volume=0.22, env_shape=EnvShape.PERCUSSIVE,
            pitch_mod=-2,
            effect_chain=EffectChain(lp_filter_hz=1800),
        ),
        "victory": SynthVoice(
            freq=523.25, osc_type=OscType.TRIANGLE, duration=0.80,
            volume=0.42, env_shape=EnvShape.SWELL,
            harmonics=[(1.5, 0.18), (2.0, 0.20), (2.5, 0.08)],
            effect_chain=EffectChain(
                reverb_mix=0.22, reverb_decay=0.9, stereo_width=0.4,
            ),
        ),
    }
else:
    DUNGEON_SFX = {}


def _synth_to_wav_bytes(voice) -> bytes:
    """将 SynthVoice 合成为 WAV 字节（内存中）"""
    if not _SYNTH_AVAILABLE:
        return b""
    sig = synthesize_voice(voice)
    if sig.ndim > 1 and sig.shape[1] >= 2:
        final = sig
    else:
        final = sig.reshape(-1, 1)
    wav_ints = np.clip(final * 32767, -32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    _wavfile.write(buf, SR, wav_ints)
    buf.seek(0)
    return buf.read()


class SoundManager:
    """地牢音效管理器 — 基于 faatt.py 合成引擎，通过 pygame.mixer 播放"""

    def __init__(self):
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self._enabled = True
        self._volume = 0.7  # 全局音量

        # 尝试初始化 pygame mixer
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=SR, size=-16, channels=2, buffer=512)
            except Exception:
                self._enabled = False
                print("[Sound] pygame.mixer 初始化失败，音效已禁用。")
                return

        if not _SYNTH_AVAILABLE:
            print("[Sound] faatt 合成引擎不可用（缺少 numpy/scipy），音效已禁用。")
            self._enabled = False
            return

        self._load_all()

    def _load_all(self):
        """预生成所有音效并加载到 mixer"""
        os.makedirs(SFX_DIR, exist_ok=True)

        for name, voice in DUNGEON_SFX.items():
            try:
                # 同时写入磁盘 + 加载到内存
                wav_path = os.path.join(SFX_DIR, f"{name}.wav")
                wav_bytes = _synth_to_wav_bytes(voice)
                if wav_bytes:
                    # 写入文件
                    with open(wav_path, "wb") as f:
                        f.write(wav_bytes)
                    # 加载到 pygame
                    snd = pygame.mixer.Sound(wav_path)
                    snd.set_volume(self._volume)
                    self._sounds[name] = snd
            except Exception as e:
                print(f"[Sound] 加载 {name} 失败: {e}")

        if DUNGEON_SFX:
            print(f"[Sound] 已加载 {len(self._sounds)}/{len(DUNGEON_SFX)} 个音效")

    # ---- 播放接口 ----

    def play(self, name: str) -> None:
        """播放指定音效（非阻塞）"""
        if not self._enabled:
            return
        snd = self._sounds.get(name)
        if snd is not None:
            snd.play()

    def play_step(self):
        self.play("step")

    def play_explore(self, threat: int = 0):
        """根据威胁值播放不同音效"""
        if threat == 0:
            self.play("explore_safe")
        else:
            self.play("explore_threat")

    def play_monster_defeat(self):
        self.play("monster_defeat")

    def play_trap_dodge(self):
        self.play("trap_dodge")

    def play_damage(self):
        self.play("damage_taken")

    def play_death(self):
        self.play("game_over")

    def play_flag(self):
        self.play("flag")

    def play_perception(self):
        self.play("perception")

    def play_benny_use(self):
        self.play("benny_use")

    def play_benny_restore(self):
        self.play("benny_restore")

    def play_wall_bump(self):
        self.play("wall_bump")

    def play_blocked(self):
        self.play("blocked")

    def play_menu_open(self):
        self.play("menu_open")

    def play_menu_close(self):
        self.play("menu_close")

    # ---- 音量控制 ----

    def set_volume(self, vol: float):
        """设置全局音量 (0.0 ~ 1.0)"""
        self._volume = max(0.0, min(1.0, vol))
        for snd in self._sounds.values():
            snd.set_volume(self._volume)

    def mute(self):
        """静音"""
        for snd in self._sounds.values():
            snd.set_volume(0.0)

    def unmute(self):
        """取消静音"""
        for snd in self._sounds.values():
            snd.set_volume(self._volume)
