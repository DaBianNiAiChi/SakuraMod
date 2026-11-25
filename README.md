# 樱花校园模拟器修改版 | Sakura School Simulator Mod

**中文：** 樱花校园模拟器修改版 | 武器射速提升 子弹飞行速度提升 无敌 无限金钱 全皮肤解锁 | 基于 233 乐园中文汉化版修改
**补充说明：** 233 乐园版所有皮肤全部已解锁，全部可用。

**English:** Sakura School Simulator Mod | Increased Weapon Fire Rate, Increased Bullet Speed, Invincible, Infinite Money, All Skins Unlocked | Based on the 233 Game Box Chinese localized version
**Note:** All skins from the 233 Game Box version are fully unlocked and usable.

---

## 下载 / Download

见 [Releases](../../releases) 页面。

- 文件名 / File: `SakuraMod_v100.apk`
- 大小 / Size: 约 652 MB

**国内用户提示：** GitHub 直连下载速度可能较慢，可尝试在链接前加上加速代理，例如
`https://gh-proxy.com/https://github.com/...`
（第三方服务，稳定性不保证）

---

## 功能 / Features

| 项目 | 说明 |
|---|---|
| **武器射速** | 提升 |
| **子弹飞行速度** | 提升 |
| **无敌** | 启用 |
| **金钱** | 无限 |
| **皮肤** | 全解锁（233 乐园版全部可用） |
| **版本** | 基于 233 乐园中文汉化版修改 |

| Feature | Description |
|---|---|
| **Weapon fire rate** | Increased |
| **Bullet flight speed** | Increased |
| **Invincible** | Enabled |
| **Money** | Infinite |
| **Skins** | All unlocked (233 Game Box version) |
| **Base** | Built on the 233 Game Box Chinese localized version |

---

## 已知问题 / Known Issues

- 敌人射速补偿机制偶尔会导致敌人开不出枪
- 子弹飞行速度无法区分玩家与敌人
- 高速连射时弹道存在轻微偏移
- 「开启误射」设置无法默认强制开启
- 人物血条不会常驻显示

---

## 安装要求 / Requirements

- Android 8.0+ / arm64-v8a
- 需要先卸载原版游戏 / Must uninstall the original game first
- 存档不兼容原版 / Save data is not compatible with the original

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

`docs/HANDOVER.md` documents the full reverse engineering process:
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
