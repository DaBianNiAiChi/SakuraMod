# 樱花校园模拟器修改版 | Sakura School Simulator Mod

**中文：** 樱花校园模拟器修改版 | 武器射速提升 子弹飞行速度提升 无敌 无限金钱 全皮肤解锁 | 基于 233 乐园中文汉化版修改
**补充说明：** 233 乐园版所有皮肤全部已解锁，全部可用。

**English:** Sakura School Simulator Mod | Increased Weapon Fire Rate, Increased Bullet Speed, Invincible, Infinite Money, All Skins Unlocked | Based on the 233 Game Box Chinese localized version
**Note:** All skins from the 233 Game Box version are fully unlocked and usable.

---

## 下载 / Download

见 [Releases](../../releases) 页面。

- 文件名 / File: `SakuraMod.apk`
- 大小 / Size: 约 651 MB

**国内用户提示：** GitHub 直连下载速度可能较慢，可尝试在链接前加加速代理（第三方服务，稳定性不作保证）。

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

## 安装要求 / Requirements

- Android 8.0+ / arm64-v8a
- 需先卸载原版游戏 / Uninstall the original game first
- 存档不兼容原版 / Save data is not compatible with the original

---

## 校验 / Verification

SHA256 见 [SHA256.txt](SHA256.txt)

---

## 技术说明

> 以下为逆向分析与二进制补丁的技术记录，面向有 Unity IL2CPP 基础的读者。

### 一、目标与地址规则

**产物**：基于 `SakuraSimulator_1.047.10.apk`，包名 `jp.garud.ssimulator.new`（233 乐园中文汉化版）。Unity 2022.3.14f1c1，IL2CPP，ARM64 单 ABI，`global-metadata.dat` v29 未加密。

**地址换算**：

```
文件偏移 = RVA − 0x1000
Frida 内存地址 = moduleBase + RVA
```

**原始 SO**：65,039,288 字节，sha256 `4d64fb0f74359573f110be35872a757732226a27bcb9a5c5f9eb5de8252e8fc4`。

**ELF 段布局**：

```
.text          0x01607D9C  大小 0x030C0A4
.rodata        0x09567B0
.data.rel.ro   0x39AC9D0
.got           0x3B903A0
.data          0x3BFC7D8
.bss           0x3E09230
```

**Program header**（10 项）：

```
ph[1] R     offset 0x00000000  vaddr 0x00000000  filesz 0x01606D9C
ph[2] R+X   offset 0x01606D9C  vaddr 0x01607D9C  filesz 0x023A3C34
ph[3] R+W   offset 0x039AA9D0  vaddr 0x039AC9D0  filesz 0x0024EE08
ph[4] R+W   offset 0x03BF97D8  vaddr 0x03BFC7D8  filesz 0x0020CA58  memsz 0x00434A48
ph[9] NOTE  offset 0x00000270  filesz 0x000000B0
```

---

### 二、反编译符号不可直接采信

IL2CPP 编译产物会把访问器桩（`ldr x0,[x0,#n]; ret`，共 8 字节）插入方法表，这些桩本身也被声明为方法，导致其后所有 RVA 出现偏移。

实测偏差案例：

| 反编译标注 | 实际内容 |
|---|---|
| `0x201C8C4 ButtonAdsPlay.Start` | 访问器桩，跳转后崩溃 |
| `0x1A52AC8 get_name()` | `CrossPlatformInputManager.VirtualAxis::get_name` |
| `0x36D5AD8 Rigidbody.set_velocity` | `NavMeshAgent.set_velocity` |
| `0x373FE60` | 非函数入口，为 ICall thunk 中段 |

**处理方式**：先用函数边界索引（`funmap.json`，82,756 条 `{start,end,cls,decl}`）确定归属，再用反汇编器核对函数序言（`sub sp, sp, #N` 或 `stp x29, x30, [sp, #-N]!`）。

该索引本身亦不完整：不覆盖 `UnityEngine.*`，会将相邻函数合并（例如 `Item.Init` 与 `Item.OnDisable`），部分区域标记为 `None::None`。

---

### 三、ADRP 立即数需符号扩展

`adrp` 的 21 位立即数是**有符号**相对页偏移。反汇编器输出的显示形式（例如 `adrp x20, #0x1c74000`）并非目标地址，实际目标为 `(PC & ~0xFFF) + (sign_extend(imm21) << 12)`。

实测：

```
0x1F27358: adrp x20, #0x1c74000   -> 目标 0x3B9B000
```

按显示值当作绝对地址会在错误内存区域解引用，实测表现为 `SEGV_MAPERR`，fault addr 形如 `0x6b3100aa1f03e1`，低 32 位 `0xAA1F03E1` 为 `mov x1, xzr` 的指令编码。

正确解码：

```python
def adrp_target(at, w):
    immlo = (w >> 29) & 0x3
    immhi = (w >> 5) & 0x7FFFF
    imm = (immhi << 2) | immlo
    if imm & 0x100000:
        imm -= 0x200000
    return (at & ~0xFFF) + (imm << 12)
```

---

### 四、ARM64 编码要点

**`fmov Sd, #imm` 的 8 位立即数映射（实测枚举）：**

```
0x00 ->  2.0     0x40 -> 0.125
0x10 ->  4.0     0x50 -> 0.25
0x20 ->  8.0     0x60 -> 0.5
0x30 -> 16.0     0x70 -> 1.0
```

**`6.0` 无法用 `fmov` 直接编码**，需 `movz w17,#0x40c0; movk w17,#0x0000,lsl#16; fmov s16,w17`。

**方向向量缩放需保持原有乘序**：

```asm
; 原始
fmul s1, s11, s0      ; s1 = dir.x * speed
; 若直接改写为
fmul s1, s11, s16     ; s1 = dir.x * mult      —— 丢失 speed
; 正确做法
fmul s0, s0, s16      ; 先缩放 speed
fmul s1, s11, s0
fmul s2, s12, s0
fmul s0, s13, s0
```

**其他编码**：

- `stp_pre(rt,rt2,rn,imm7) = 0xA9800000 | ((imm7 & 0x7F) << 15) | (rt2 << 10) | (rn << 5) | rt`，`imm7` 以 8 字节为单位
- 保存 `d8/d9`：`stp d8,d9,[sp,#-0x10]!` = `0x6D3F27E8`；恢复 `ldp d8,d9,[sp],#0x10` = `0x6CC127E8`

---

### 五、调用约定与寄存器保存

`BL` 会破坏 `x0-x18`（caller-saved），`x19-x28` 为 callee-saved。

实测崩溃案例：

- 将 `Item.m_Character` 存放于 `x8` 并跨 `bl classinit`，崩溃 `fault addr 0x800000000000e0`
- `bl FriendlyFireON()` 时仅保存 `x19/x30`，但该函数以尾调用 `b` 结尾，返回后调用方寄存器已被破坏，崩溃于 `0x1E30608`

**结论**：跨 `BL` 的值应置于 `x19-x28` 并在跳板中成对 `stp/ldp` 保存，或改用直接写内存的方式。

---

### 六、代码空间

`.text` 段（`0x1607D9C..0x1913E40`）扫描后无超过 100 字节的连续空位。可用区域仅来自 `AnimatorMonitor.OnDeath` 中 release 模式下不执行的 `[Conditional]` DebugLog 残留：

```
0x1FD9D5C .. 0x1FD9D84   40 字节
0x1FD9D84 .. 0x1FD9E08  128 字节
0x1FD9E0C .. 0x1FD9E38   44 字节
```

**曾尝试在文件末尾追加代码页并新增第 11 个 `PT_LOAD`（RX），同时将 `PT_NOTE` 缩小至仅覆盖 `.note.gnu.build-id`。加载阶段报 `SEGV_ACCERR`，fault addr 落在新段 vaddr 上，表明新段未获得可执行映射。该方案已放弃。**

---

### 七、关键数据结构

**ShootableWeapon**（`Opsive.ThirdPersonController`，继承链 `ShootableWeapon : Weapon : Item : MonoBehaviour`）

```
0x28   m_ItemType
0x110  m_Character
0x120  m_Inventory
0x158  m_FirePoint
0x160  m_FireMode (0=Single, 1=Burst, 2=FullAuto)
0x164  m_FireRate
0x168  m_BurstRate
0x16C  m_ClipSize
0x170  m_FireCount
0x258  m_HitscanFireRange
0x25C  m_HitscanImpactLayers
0x2E0  m_AIAgent
0x2F8  m_ShootDelay
0x2FC  m_LastShootTime
0x300  m_CurrentBurst
0x304  m_IsFiring
0x305  m_CanFire
0x308  m_FireEvent
0x319  m_Reloading
0x3E0  TryUseCnt
0x3E8  m_characterAI
0x3F0  m_CharacterStatus
0x3F8  ReloadCnt
0x3F9  InfinityWeapon
```

**Projectile**

```
0x70   m_InitialSpeed
0x74   m_Speed
0x78   m_Lifespan
0x88   m_MovementForce
0x98   m_Rigidbody
0xA8   m_Originator
0xB8   enemyList
0xC0   seekTag
0xC8   seekTarget
0xDC   isPlayer
0xE4   m_EnemyType
```

`Initialize` 内 `x24 == this + 0xA8`，故：

```
m_Speed      = [x24 - 0x34]
isPlayer     = [x24 + 0x34]
m_Originator = [x24]
```

**SystemManager**

```
0x368  m_Character
0x370  m_Charactertransform
0x378  m_CharacterStatus
0x380  m_CharacterAI
```

访问链：

```asm
adrp x9, #0x3B9A000
ldr  x9, [x9, #0x3d0]      ; 类指针槽（.got）
ldr  x9, [x9]              ; 类对象
ldr  w10,[x9, #0xe0]       ; classinit 标志
cbnz w10, +0x8
bl   0x1808CE4
ldr  x9, [x9, #0xb8]       ; static_fields
ldr  x9, [x9, #0x78]       ; Instance
ldr  x9, [x9, #0x368]      ; m_Character
```

**CharacterStatus**

```
0x30 ID   0x3C Sex   0x48 Name
0x54 HPMax  0x58 HP  0xA4 Money  0xFB Muteki
```

**CharacterAI**

```
0x9F FriendlyFire   0xA4 m_EnemyType
PurposeMode: Defender=0 Attacker=1 Catcher=2 ShopMember=3 Teacher=4
             Student=5 People=6 Patroller=7 None=8 Police=9 Goutou=10
tagID:       None=0 Player=1 Character1=2 Character2=3 Enemy=4 Point=5
```

**SaveGameManager**：`0x10 FriendlyFire`（static）、`0x90 HasBeamLauncher`、`0xC8 EquipBeamLauncher`

**DestroyManager**：`0x38 FriendlyFireLock`（无读写点）

---

### 八、关键函数地址

```
Item.Init                        0x2000E18
  0x2000F48  str x1,[x19,#0x110]
  0x2001264  bl InitializeSharedFields
Item.OnDisable                   0x2000DB4

ShootableWeapon.Awake            0x2006F18
  0x20071B4  fmov s0,#1.0
  0x20071B8  fdiv s2,s0,s2
  0x20071C0  str s2,[x19,#0x2f8]
ShootableWeapon.Init             0x2008514
ShootableWeapon.TryUse           0x2008888
  0x20088D0  ldrb w8,[x19,#0x304]
  0x20088D8  ldrb w8,[x19,#0x3e0]
  0x20088E0  tst  w8,#0xfc
  0x2008918  ldr  s8,[x19,#0x2fc]
  0x200891C  ldr  s9,[x19,#0x2f8]
  0x2008920  mov  x0,xzr
  0x2008924  bl   0x3749CA0
  0x2008928  fadd s1,s8,s9
  0x200892C  fcmp s1,s0
  0x2008930  b.pl
  0x2008934  ldr  x8,[x19,#0x350]
  0x200893C  ldrb w8,[x19,#0x3f9]
  0x2008944  ldr  x0,[x19,#0x120]
ShootableWeapon.DoFire           0x2008A98
ShootableWeapon.Fire             0x2009DF4
ShootableWeapon.ProjectileFire   0x2009E74
ShootableWeapon.HitscanFire      0x200A944
  0x200A9F4  add x0,x19,#0x25c
ShootableWeapon.EmptyClip        0x2008D80
ShootableWeapon.TryStartReload   0x2007E5C
ShootableWeapon.CanUse           0x2009200

Projectile.Initialize            0x200A470
Projectile.UpdateEnemyList       0x2012224
  0x201222C  ldr x0,[x0,#0xc0]
  0x2012234  bl  FindGameObjectsWithTag
  0x2012238  str x0,[x19,#0xb8]!
Projectile.FixedUpdate           0x2012560
Projectile.Collide               0x2013178

Health.Damage                    0x2015A58
  0x2015A74  ldrb w8,[x0,#0x20]
  0x2015A78  cbz  w8,+0x24

SaveGameManager.Awake            0x1E300BC
SaveGameManager.Start            0x1E30548
SaveGameManager.FriendlyFireON   0x1F2734C
  0x1F27358  adrp -> 0x3B9B000
  0x1F27360  ldr  -> x20 = 0x3B9BE40
  0x1F27390  adrp -> 0x3B9A000
  0x1F27398  ldr  -> x20 = 0x3B9AA38
  0x1F273BC  ldr  x8,[x0,#0xb8]
  0x1F273CC  strb w9,[x8,#0x10]

ShowChatLifeBar                  0x1E6FB48
ChatNewText                      0x1E6FC54
HideChatFromCharacter            0x1E7006C

Component.get_transform          0x373FE3C
Component.get_gameObject         0x373FE78
Transform.get_parent             0x374C7FC
Rigidbody.set_velocity           0x379A304
Rigidbody.AddForce               0x379BD80
IL2CPP classinit                 0x1808CE4
```

---

### 九、运行时验证结论

以下结论均来自 Frida 探针实测，非静态推断。

**可用判据**

`Item.m_Character`（`+0x110`）与 `SystemManager.m_Character`（`+0x368`）的指针比较，在 `TryUse`（`0x200891C`）处可稳定区分玩家武器与 AI 武器。20 次开火采样中，玩家武器两侧指针相等，AI 武器全部不等。

`Projectile.m_Originator`（`+0xA8`）保存开火者 GameObject，各角色互不相同。

**不可用判据**

| 判据 | 实测结果 |
|---|---|
| `Projectile.isPlayer`（`+0xDC`） | 对玩家及全部 AI 均为 1 |
| `ShootableWeapon.m_AIAgent`（`+0x2E0`） | 两侧均非空且值各异 |
| `Item.m_Inventory` → `Inventory.m_GameObject` | 恒不等于角色 GameObject |
| `ShootableWeapon.m_FireEvent`（`+0x308`） | 实测全部为 null |
| `Projectile.Initialize` 参数 `x2` | 实测全部为 NULL |
| `Projectile.m_InitialSpeed`（`+0x70`） | 实测全部为 0 |

**其他实测事实**

- `Rigidbody.set_velocity` 为 `0x379A304`，`0x36D5AD8` 是 `NavMeshAgent`
- `ButtonAdsPlay.PlayMark`（`+0x20`）无写入点
- `DestroyManager.FriendlyFireLock`（`+0x38`）无任何读写点

---

### 十、当前版本（v100-r）状态

**SO sha256**：`ba03d3c77a4d9132cc904dc9de032e9adfe981d4f57f8bb737ff1ef1c5d46a60`

**已生效补丁**

| 位置 | 内容 |
|---|---|
| `0x20071B4` | `fmov s0,#0.25`，全局射速系数 |
| `0x200891C` | `b 0x1FD9D84`，射速代码洞入口 |
| `0x1FD9D84`–`0x1FD9DE4` | 判据、缩放、写回 |
| `0x1FD9DE0` | **`NOP`**（原 `str s9,[x19,#0x2f8]`）修正 AI 射速累乘 |
| `0x200A568` | `b 0x1FD9D5C`，子弹速度代码洞入口 |
| `0x1FD9D5C`–`0x1FD9D80` | 全弹丸速度 ×6.0 |
| 其他区域 | 无敌、金钱、全解锁、广告移除 |

**关于 `0x1FD9DE0` 的修正**

原补丁在该处写回 `m_ShootDelay`。由于每次冷却判断都会对局部值乘 4.0 后再写回，实际形成 `0.25 → 1.0 → 4.0 → 16.0` 的累乘，导致 AI 武器冷却时间指数增长并最终无法开火。改为 `NOP` 后不再写回，每次仅对局部副本缩放。

---

### 十一、尚未解决的问题

**1. 子弹飞行速度无法按发射方区分**

可用判据为 `m_Originator`（`x24` 处单条 `ldr`），但比较 `SystemManager.m_Character` 需约 12 条指令（48 字节），超出 40 字节代码洞容量。已验证的替代方案均不成立（见第九节）。

**2. 「开启误射」无法默认开启**

该设置为 `SaveGameManager.FriendlyFire`（`static_fields + 0x10`）。在 `SaveGameManager.Start` 中直接写入静态字段的两次尝试均于启动阶段崩溃；探针显示 `0x3B9BE40` 与 `0x3B9AA38` 两个候选槽解引用后 `+0xB8` 偏移取得的并非有效 `static_fields`（其中之一读出 `0x20006c29`）。正确槽位尚未定位。

**3. 连射时弹道偏移**

长按连续射击并同时移动视角时，弹道存在偏移，成因未定位。

**4. 人物血条不常驻**

`ShowChatLifeBar`（`0x1E6FB48`）为统一开关，遍历 `+0x508` 列表逐个设置可见性，当前仅在 `ChatNewText` 路径调用，无常驻显示路径。

**5. 攻击范围限制**

`Projectile.UpdateEnemyList`（`0x2012224`）以 `seekTag`（`+0xC0`）调用 `FindGameObjectsWithTag`，结果写入 `enemyList`（`+0xB8`）。Tag 不匹配的对象不进入可命中列表。

---

### 十二、构建与部署

**打包**

```
1. 基础包：Sakura_v61-aligned-debugSigned.apk
2. 替换 lib/arm64-v8a/libil2cpp.so
3. 替换 assets/aa/Android/packed_assets_all.bundle（可选，广告补丁）
4. 签名：java -jar uber-apk-signer.jar -a <apk> -o <outdir>
```

**装机**

`adb install -r` 不会替换 `.so`，必须卸载后重装：

```
adb -s <SERIAL> shell am force-stop jp.garud.ssimulator.new
adb -s <SERIAL> uninstall jp.garud.ssimulator.new
adb -s <SERIAL> install --no-streaming <apk>
adb -s <SERIAL> shell "su -c 'sha256sum /data/app/*/jp.garud.ssimulator.new*/lib/arm64/libil2cpp.so'"
```

**环境**

- Python 3，已安装 frida 17.27.5、capstone 5.0.9、UnityPy 1.25.4
- Git for Windows

---

### 十三、方法小结

1. 修改前以运行时探针确认真实值。字段偏移与寄存器内容常与静态分析结论不符。
2. 跳转指令写入后须独立解码复核目标地址（`cbz`、`b.cond`、`adrp`）。
3. 跨 `BL` 的值须置于 callee-saved 寄存器，或改为直接写内存。
4. 单次仅变更一个变量，否则异常原因无法定位。
5. 装机崩溃优先读取 logcat 中的 fault addr，其低 32 位常为指令编码，可据此区分「读到指令数据」与「访问空指针」。
6. 代码洞容量为硬约束，修改前先核算字节数。

---

## 工具 / Tools

- `tools/` — ARM64 编码器、ELF 工具、反汇编辅助
- `frida/` — Frida 内存探针

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
