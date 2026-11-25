# 樱花校园模拟器修改版 | Sakura School Simulator Mod

**中文：** 樱花校园模拟器修改版 | 武器射速提升 无敌 无限金钱 全解锁皮肤 中文汉化版
**补充说明：** 233乐园版所有皮肤全部已解锁，全部可用。

**English:** Sakura School Simulator Mod | Faster Weapon Fire Rate, Invincible, Infinite Money, All Skins Unlocked, Chinese Localized Version
**Note:** All skins from the 233 Game Box version are fully unlocked and usable.

---

## 下载 / Download

见 [Releases](../../releases) 页面。

- 文件名 / File: `SakuraMod_v100.apk`
- 大小 / Size: 约 652 MB

---

## 功能 / Features

| 项目 | 说明 |
|---|---|
| **玩家射速** | 8 发连射（原版单发） |
| **敌人射速** | 原版 |
| **子弹飞行速度** | 双方一致 |
| **无敌** | 开启 |
| **金钱** | 永久 99999999 |
| **真枪** | 开启（替换玩具枪模型） |
| **皮肤** | 233乐园版全部解锁 |
| **中文汉化** | 233乐园汉化版 |

| Feature | Description |
|---|---|
| **Player fire rate** | 8-round burst (vanilla is single shot) |
| **Enemy fire rate** | Vanilla |
| **Bullet speed** | Same for both sides |
| **Invincible** | Enabled |
| **Money** | Permanent 99999999 |
| **Real guns** | Enabled (replaces toy gun models) |
| **Skins** | All 233 Game Box skins unlocked |
| **Chinese localization** | 233 Game Box version |

---

## 已知问题 / Known Issues

- 敌人偶尔会开不出枪（射速补偿副作用）
- 子弹速度无法区分玩家/敌人
- 弹道有轻微偏移
- 误射无法强制开启
- 血条不常驻

---

## 安装要求 / Requirements

- Android 8.0+ / arm64-v8a
- 需要卸载原版游戏 / Must uninstall the original game
- 存档不兼容原版 / Save data is not compatible

---

## 校验 / Verification

SHA256 见 [SHA256.txt](SHA256.txt)

---

## 技术资料 / Technical Docs

`docs/HANDOVER.md` 记录了完整的逆向分析过程：
- Unity IL2CPP 结构
- 关键函数地址
- ARM64 补丁技巧
- 踩过的坑

`docs/HANDOVER.md` documents the full reverse-engineering process:
- Unity IL2CPP structure
- Key function addresses
- ARM64 patching techniques
- Pitfalls encountered

---

## 工具 / Tools

- `tools/` — ARM64 编码器、ELF 工具、反汇编辅助 / ARM64 encoder, ELF tools, disassembly helpers
- `frida/` — Frida 内存探针 / Frida memory probes

---

## 免责声明 / Disclaimer

本项目仅用于学习研究 Unity IL2CPP 逆向工程技术。请勿用于商业用途。游戏版权归 Garusoft Development 所有。

This project is for studying Unity IL2CPP reverse engineering only. Do not use commercially. Game copyright belongs to Garusoft Development.

---

## License

本仓库中的 **工具、脚本、文档** 使用 MIT 协议。

**游戏文件（APK）、游戏原始素材不在授权范围内**，版权归 Garusoft Development 所有。

详见 [LICENSE](LICENSE) 文件中的 SCOPE / EXCLUSIONS 说明。

---

Tools, scripts and documentation in this repository are MIT licensed.

**Game files (APK) and original game assets are NOT covered by this license.**
**Copyright belongs to Garusoft Development.**

See the SCOPE / EXCLUSIONS sections in [LICENSE](LICENSE).
