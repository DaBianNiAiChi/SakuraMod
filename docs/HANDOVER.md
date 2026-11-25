# SakuraMod 技术说明

> Unity IL2CPP / ARM64 逆向分析与二进制补丁的技术记录。
> 本文档只记录技术事实：已验证的数据、遇到的坑、当前状态。

---

## 一、目标与产物

**目标**：`SakuraSimulator_1.047.10.apk`

**产物目录**：`<PROJECT_DIR>/`

**游戏**：樱花校园模拟器，基于 233 乐园中文汉化版
- 包名：`jp.garud.ssimulator.new`
- 另有一个独立的原版包 `jp.garud.ssimulator`（不在本项目范围内）
- Unity 2022.3.14f1c1 + IL2CPP + ARM64 单 ABI
- `global-metadata.dat` v29，未加密

---

## 二、地址规则（已验证）

```
文件偏移 = RVA − 0x1000
Frida 内存地址 = moduleBase + RVA
```

**原始 SO**：`libil2cpp.so`
- 65,039,288 字节
- sha256 `4d64fb0f74359573f110be35872a757732226a27bcb9a5c5f9eb5de8252e8fc4`

**ELF 段布局**：

```
.text          0x01607D9C  大小 0x030C0A4
.rodata        0x09567B0
.data.rel.ro   0x39AC9D0
.got           0x3B903A0
.data          0x3BFC7D8
.bss           0x3E09230
```

**Program header**（10 个）：

```
ph[1] R       offset 0x00000000  vaddr 0x00000000  filesz 0x01606D9C
ph[2] R+X     offset 0x01606D9C  vaddr 0x01607D9C  filesz 0x023A3C34
ph[3] R+W     offset 0x039AA9D0  vaddr 0x039AC9D0  filesz 0x0024EE08
ph[4] R+W     offset 0x03BF97D8  vaddr 0x03BFC7D8  filesz 0x0020CA58  memsz 0x00434A48
ph[9] NOTE    offset 0x00000270  filesz 0x000000B0
```

---

## 三、坑点一：dump.cs 的 RVA 不可靠

**`dump.cs` 中访问器桩（`ldr x0,[x0,#n]; ret`，8 字节）插在函数之间，也占据方法声明，导致 RVA 错位。**

**实测错位案例**：

| dump.cs 标注 | 实际内容 |
|---|---|
| `0x201C8C4 ButtonAdsPlay.Start` | 访问器桩，patch 后崩溃 |
| `0x1A52AC8 get_name()` | `CrossPlatformInputManager.VirtualAxis::get_name` |
| `0x36D5AD8 Rigidbody.set_velocity` | `NavMeshAgent.set_velocity` |
| `0x373FE60` | 不是函数入口，是 ICall thunk 的中段 |

**对策**：用 `funmap.json`（82,756 条 `{start,end,cls,decl}`）查归属，再用 capstone 反汇编确认函数序言（`sub sp, sp, #N` 或 `stp x29, x30, [sp, #-N]!`）。

**`funmap.json` 自身也不完全可靠**：
- 不覆盖 `UnityEngine.*`
- 会把相邻函数合并（例如把 `Item.Init` 和 `Item.OnDisable` 归成一个）
- 部分区域标为 `None::None`

---

## 四、坑点二：ADRP 的符号扩展

**`adrp` 的 21 位相对偏移是**有符号数**，可正可负。**

**capstone 反汇编显示的是相对值形式，例如 `adrp x20, #0x1c74000`，但实际目标地址是 `(PC & ~0xFFF) + (sign_extend(imm21) << 12)`。**

**实测**：

```
0x1F27358: adrp x20, #0x1c74000   -> 实际目标 0x3B9B000
```

**把显示值当成绝对地址会导致解引用错误的内存区域，实测崩溃为 `SEGV_MAPERR`，fault addr 形如 `0x6b3100aa1f03e1`（低 32 位是指令编码 `0xAA1F03E1` = `mov x1, xzr`）。**

**对策**：解码时做符号扩展并回填绝对地址，写完后用 capstone 反汇编回来复核。

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

## 五、坑点三：Frida 17 API 变化

**Frida 17.27.5 移除了全局模块枚举 API：**

```js
Module.enumerateExports()                          // undefined
Process.enumerateModuleExports(...)                // undefined
Process.getModuleByName('x.so').enumerateExports() // 正确
```

**其他实测事实**：
- 进程名是 `SakuraSimulator`（Unity product name），不是包名
- `rpc.exports` 的 `probe_value` 会被 Python 自动转成 `probeValue`
- `Memory.alloc()` 的作用域跨 RPC 调用失效，需要真实 `mmap`
- `mmap` 必须用 `PROT_READ|PROT_WRITE`（3）写入，再 `mprotect` 成 `PROT_READ|PROT_EXEC`（5）
- 从 Frida 线程调用 `il2cpp_domain_get()` 返回无效值，应直接读 cache slot `libil2cpp+0x3E1A7D0`
- **在每帧执行路径上运行任何 JS 会崩溃 UnityMain**，探针必须只读寄存器

---

## 六、坑点四：ARM64 编码细节

**`fmov Sd, #imm` 的 8 位立即数映射（实测枚举）：**

```
imm8=0x00 ->  2.0     0x40 ->  0.125
imm8=0x10 ->  4.0     0x50 ->  0.25
imm8=0x20 ->  8.0     0x60 ->  0.5
imm8=0x30 -> 16.0     0x70 ->  1.0
imm8=0x80-0xF0 -> 对应负值
```

**注意：`6.0` 无法用 `fmov` 直接编码，需要 `movz w17,#0x40c0; movk w17,#0x0000,lsl#16; fmov s16,w17`。**

**`fmul Sd, Sn, Sm` 与原始语义**：

```
原始: fmul s1, s11, s0     ; s1 = dir.x * speed
错误: fmul s1, s11, s16    ; s1 = dir.x * mult  —— 丢掉了 speed
正确: fmul s0, s0, s16     ; 先缩放 speed
      fmul s1, s11, s0     ; 再乘方向
      fmul s2, s12, s0
      fmul s0, s13, s0
```

**其他编码**：
- `stp_pre(rt,rt2,rn,imm7) = 0xA9800000|((imm7&0x7F)<<15)|(rt2<<10)|(rn<<5)|rt`，`imm7` 以 8 字节为单位
- `fmov d8,d9` 保存：`stp d8,d9,[sp,#-0x10]!` = `0x6D3F27E8`；恢复 `ldp d8,d9,[sp],#0x10` = `0x6CC127E8`
- 只保存 `d8/d9` 不够时，`s0-s15` 都是 caller-saved，跨 `bl` 必须备份

---

## 七、坑点五：调用函数的寄存器约定

**`BL` 会破坏 `x0-x18`（caller-saved）。`x19-x28` 是 callee-saved。**

**实测崩溃**：
- v96：把 `Item.m_Character` 存在 `x8` 跨 `bl classinit`，崩溃 `fault addr 0x800000000000e0`
- v115：`bl FriendlyFireON()` 时只保存 `x19/x30`，但该函数以尾调用 `b` 结尾，返回后 `Start` 使用的寄存器已被破坏，崩溃在 `0x1E30608`

**对策**：跨 `bl` 的值必须放在 `x19-x28`，并在跳板里成对 `stp/ldp` 保存；或使用 `bl` 之外的方式（直接写静态字段）。

---

## 八、坑点六：ELF 段表不可手工扩展

**尝试**：在文件末尾追加代码页，新增第 11 个 `PT_LOAD`（RX），同时把 `PT_NOTE` 缩小到只覆盖 `.note.gnu.build-id`。

**结果**：加载时报 `SEGV_ACCERR`，fault addr 恰好落在新段 vaddr 上，说明新段未获得可执行映射。

**对策**：放弃 ELF 结构修改，改用现有代码洞。

**v100 中可用的代码洞**：

```
0x1FD9D5C .. 0x1FD9D84   40 字节   （死 [Conditional] DebugLog 代码）
0x1FD9D84 .. 0x1FD9E08  128 字节
0x1FD9E0C .. 0x1FD9E38   44 字节
```

**扫描 .text 全段（`0x1607D9C..0x1913E40`）未发现其他 ≥100 字节的连续 RET/NOP 串。**

---

## 九、关键数据结构

### ShootableWeapon（`Opsive.ThirdPersonController`）

继承链：`ShootableWeapon : Weapon : Item : MonoBehaviour`

```
0x28   m_ItemType
0x110  m_Character (GameObject)
0x120  m_Inventory
0x158  m_FirePoint
0x160  m_FireMode (0=Single,1=Burst,2=FullAuto)
0x164  m_FireRate (float)
0x168  m_BurstRate
0x16C  m_ClipSize
0x170  m_FireCount
0x258  m_HitscanFireRange
0x25C  m_HitscanImpactLayers (LayerMask)
0x2E0  m_AIAgent (SharedMethod<bool>)
0x2F8  m_ShootDelay (float)
0x2FC  m_LastShootTime (float)
0x300  m_CurrentBurst
0x304  m_IsFiring
0x305  m_CanFire
0x308  m_FireEvent (ScheduledEvent, 实测为 null)
0x319  m_Reloading
0x3E0  TryUseCnt (byte)
0x3E8  m_characterAI
0x3F0  m_CharacterStatus
0x3F8  ReloadCnt (byte)
0x3F9  InfinityWeapon
```

### Projectile

```
0x6C   projectileType
0x70   m_InitialSpeed
0x74   m_Speed
0x78   m_Lifespan
0x80   m_ScheduledActivation
0x88   m_MovementForce
0x98   m_Rigidbody
0xA0   m_TrailRenderer
0xA8   m_Originator (GameObject)
0xB0   dummyobj
0xB8   enemyList (GameObject[])
0xC0   seekTag (string)
0xC8   seekTarget
0xDC   isPlayer (bool)
0xE1   EnemyHit
0xE4   m_EnemyType
```

**`Initialize` 内 `x24 == this + 0xA8`，因此：**

```
m_Speed     = [x24 - 0x34]
isPlayer    = [x24 + 0x34]
m_Originator= [x24]
```

### SystemManager

```
0x368  m_Character (GameObject)
0x370  m_Charactertransform
0x378  m_CharacterStatus
0x380  m_CharacterAI
```

**访问链**：

```asm
adrp x9, #0x3B9A000
ldr  x9, [x9, #0x3d0]      ; 类指针槽（.got 段）
ldr  x9, [x9]              ; 类对象
ldr  w10,[x9, #0xe0]       ; classinit 检查
cbnz w10, +0x8
bl   0x1808CE4             ; classinit
ldr  x9, [x9, #0xb8]       ; static_fields
ldr  x9, [x9, #0x78]       ; Instance
ldr  x9, [x9, #0x368]      ; m_Character
```

### CharacterStatus

```
0x30   ID
0x3C   Sex
0x48   Name
0x54   HPMax
0x58   HP
0xA4   Money
0xFB   Muteki
```

### CharacterAI

```
0x9F   FriendlyFire
0xA4   m_EnemyType
```

```
PurposeMode: Defender=0 Attacker=1 Catcher=2 ShopMember=3 Teacher=4
             Student=5 People=6 Patroller=7 None=8 Police=9 Goutou=10
tagID:       None=0 Player=1 Character1=2 Character2=3 Enemy=4 Point=5
```

### SaveGameManager

```
0x10   FriendlyFire（static bool，static_fields + 0x10）
0x90   HasBeamLauncher (int[])
0xC8   EquipBeamLauncher (bool[])
```

### DestroyManager

```
0x38   FriendlyFireLock（只声明，全二进制无读写点）
```

---

## 十、关键函数地址

```
Item.Init                        0x2000E18
Item.OnDisable                   0x2000DB4
  0x2000F48  str x1,[x19,#0x110]       m_Character 赋值
  0x2001264  bl InitializeSharedFields

ShootableWeapon.Awake            0x2006F18
  0x20071B4  fmov s0,#1.0              原版射速系数
  0x20071B8  fdiv s2,s0,s2
  0x20071C0  str s2,[x19,#0x2f8]
ShootableWeapon.Init             0x2008514
ShootableWeapon.TryUse           0x2008888
  0x20088D0  ldrb w8,[x19,#0x304]      m_IsFiring
  0x20088D8  ldrb w8,[x19,#0x3e0]      TryUseCnt
  0x20088E0  tst  w8,#0xfc
  0x2008918  ldr  s8,[x19,#0x2fc]      m_LastShootTime
  0x200891C  ldr  s9,[x19,#0x2f8]      m_ShootDelay
  0x2008920  mov  x0,xzr
  0x2008924  bl   0x3749CA0
  0x2008928  fadd s1,s8,s9
  0x200892C  fcmp s1,s0
  0x2008930  b.pl                    还在冷却
  0x2008934  ldr  x8,[x19,#0x350]     m_OverheatEvent
  0x200893C  ldrb w8,[x19,#0x3f9]     InfinityWeapon
  0x2008944  ldr  x0,[x19,#0x120]     m_Inventory
ShootableWeapon.DoFire           0x2008A98
ShootableWeapon.Fire             0x2009DF4
ShootableWeapon.ProjectileFire   0x2009E74
ShootableWeapon.HitscanFire      0x200A944
  0x200A9F4  add x0,x19,#0x25c          &m_HitscanImpactLayers
ShootableWeapon.EmptyClip        0x2008D80
ShootableWeapon.TryStartReload   0x2007E5C
ShootableWeapon.CanUse           0x2009200

Projectile.Initialize            0x200A470
Projectile.UpdateEnemyList       0x2012224
  0x201222C  ldr x0,[x0,#0xc0]          seekTag
  0x2012234  bl  GameObject.FindGameObjectsWithTag
  0x2012238  str x0,[x19,#0xb8]!        enemyList
Projectile.FixedUpdate           0x2012560
Projectile.Collide               0x2013178

Health.Damage                    0x2015A58
  0x2015A74  ldrb w8,[x0,#0x20]         无敌检查
  0x2015A78  cbz  w8, +0x24             非无敌则继续

SaveGameManager.Awake            0x1E300BC
SaveGameManager.Start            0x1E30548
SaveGameManager.FriendlyFireON   0x1F2734C
  0x1F27358  adrp x20 -> 0x3B9B000
  0x1F27360  ldr  x20,[x20,#0xe40]      x20 = 0x3B9BE40
  0x1F27390  adrp x20 -> 0x3B9A000
  0x1F27398  ldr  x20,[x20,#0xa38]      x20 = 0x3B9AA38
  0x1F273BC  ldr  x8,[x0,#0xb8]         static_fields
  0x1F273CC  strb w9,[x8,#0x10]         FriendlyFire = true

ShowChatLifeBar                  0x1E6FB48
ChatNewText                      0x1E6FC54
HideChatFromCharacter            0x1E7006C

Component.get_transform          0x373FE3C
Component.get_gameObject         0x373FE78
Transform.get_parent             0x374C7FC
Rigidbody.set_velocity           0x379A304
Rigidbody.AddForce               0x379BD80
IL2CPP classinit                 0x1808CE4
il2cpp_add_internal_call         0x186CC44
il2cpp_domain_get                0x186D1A8
```

---

## 十一、已验证的运行时事实

**以下结论均来自 Frida 探针实测，不是推断。**

### 有效判据

**`Item.m_Character`（`+0x110`）与 `SystemManager.m_Character`（`+0x368`）比较，在 `TryUse`（`0x200891C`）处可稳定区分玩家与 AI 武器。**

实测 20 次开火：玩家武器 `x21 == x9`，AI 武器全部不等。

**`Projectile.m_Originator`（`+0xA8`）保存开火者 GameObject，玩家与各 AI 均不同。**

### 无效判据

| 判据 | 实测结果 |
|---|---|
| `Projectile.isPlayer`（`+0xDC`） | **对玩家和所有 AI 都为 1**，不可用 |
| `ShootableWeapon.m_AIAgent`（`+0x2E0`） | 玩家与 AI 都非 null，值各异，不可用作判据 |
| `Item.m_Inventory` → `Inventory.m_GameObject` | 从不等于角色 GameObject |
| `ShootableWeapon.m_FireEvent`（`+0x308`） | **实测全为 null** |
| `Projectile.Initialize` 的 `x2` 参数 | **实测全为 NULL** |
| `Projectile.m_InitialSpeed`（`+0x70`） | 实测全为 0 |

### 其他事实

- `Rigidbody.set_velocity` 是 `0x379A304`，不是 `0x36D5AD8`（后者是 `NavMeshAgent`）
- `ButtonAdsPlay.PlayMark`（`+0x20`）没有任何写入点
- `DestroyManager.FriendlyFireLock`（`+0x38`）没有任何读写点

---

## 十二、当前版本状态（v100）

**SO**：`libil2cpp.so`
**sha256**：`aeac29ca07c4781ca46371b7204417bc8f90b81c852241716f91a9ca118d48f5`

### 已生效的补丁

| 位置 | 改动 | 效果 |
|---|---|---|
| `0x20071B4` | `fmov s0,#0.25` | 全局射速系数 |
| `0x200891C` | `b 0x1FD9D84` | 射速代码洞 |
| `0x1FD9D84` | 判据 + 缩放 + 写回 | 玩家 `m_ShootDelay ×0.5`，AI `×4.0` 并写回 |
| `0x200A568` | `b 0x1FD9D5C` | 子弹速度代码洞 |
| `0x1FD9D5C` | 全段乘 6.0 | 所有弹丸速度 ×6 |
| 其他 | 无敌 / 金钱 / 全解锁 / 广告移除 | — |

### 未解决的问题

**1. 子弹飞行速度无法区分玩家与敌人**

**可用判据是 `m_Originator`（`x24` 处一行 `ldr`），但比较 `SystemManager.m_Character` 需要约 12 条指令（48 字节），超出 40 字节代码洞容量。**

**尝试过的方案：**

| 方案 | 结果 |
|---|---|
| `isPlayer`（`+0xDC`） | 该字段对敌我都为 1，不可用 |
| `x2` 参数 | 恒为 NULL，不可用 |
| 两段代码洞拼接（`0x1FD9D5C` + `0x1FD9DE8`） | 编译期崩溃 `SEGV_MAPERR`，原因未定位 |
| ELF 新增 `PT_LOAD` | 加载时 `SEGV_ACCERR` |

**2. AI 射速补偿的副作用**

**AI 路径的 `str s9,[x19,#0x2f8]` 会逐次累乘：`0.25 → 1.0 → 4.0 → 16.0`，指数放大。**

**v100 保留该指令，实测 AI 偶尔无法开火。移除该 `str` 后（v112）射速表现为「双方都变慢」。**

**3. 弹道偏移**

**长按连射并移动转动视角时，弹道存在偏移，原因未定位。**

**4. 「开启误射」无法强制开启**

该开关是 `SaveGameManager.FriendlyFire`（`static_fields + 0x10`）。

**尝试直接在 `Start` 中写静态字段：探针显示 `0x3B9BE40` 与 `0x3B9AA38` 两个候选类指针槽解引用后，`+0xB8` 得到的值不是有效 `static_fields`（其一读得 `0x20006c29`）。正确的类指针槽尚未定位。**

**5. 人物血条不常驻**

`ShowChatLifeBar`（`0x1E6FB48`）是统一开关，遍历 `+0x508` 的列表逐个设置可见性；当前仅在 `ChatNewText` 时调用。没有常驻显示的路径。

**6. 「只能攻击敌人」的机制**

`Projectile.UpdateEnemyList`（`0x2012224`）以 `seekTag`（`+0xC0`）调用 `FindGameObjectsWithTag`，结果写入 `enemyList`（`+0xB8`）。Tag 不匹配的对象不进入可命中列表。

---

## 十三、构建与部署流程

### APK 打包

```
1. 基础包：<PROJECT_DIR>/Sakura_v61-aligned-debugSigned.apk
2. 替换 lib/arm64-v8a/libil2cpp.so
3. 替换 assets/aa/Android/packed_assets_all.bundle（可选，广告补丁）
4. 签名：java -jar uber-apk-signer.jar -a <apk> -o <outdir>
```

### 装机

**`adb install -r` 不会替换 .so，必须卸载后重装：**

```
adb -s <SERIAL> shell am force-stop jp.garud.ssimulator.new
adb -s <SERIAL> uninstall jp.garud.ssimulator.new
adb -s <SERIAL> install --no-streaming <apk>
adb -s <SERIAL> shell "su -c 'sha256sum /data/app/*/jp.garud.ssimulator.new*/lib/arm64/libil2cpp.so'"
```

### 环境

- Python：`<HOME>/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe`
- 已装：frida 17.27.5、capstone 5.0.9、UnityPy 1.25.4
- Git for Windows：`C:\Program Files\Git\cmd\git.exe`

---

## 十四、工作方法小结

**以下经验来自实际调试过程，按重要性排序。**

1. **改动前先用探针确认运行时值**。字段偏移和寄存器内容经常与静态分析结论不同，`isPlayer` 与 `x2` 都是实例。

2. **跳转写完后必须解码回验**。`cbz`、`b.cond`、`adrp` 的目标地址全部用独立解码函数复算一遍，与预期比对。

3. **跨 `bl` 的值必须放在 callee-saved 寄存器**，或改用直接写内存的方式。

4. **一次只改一个变量**。多变量同时改动时，崩溃或行为异常的原因无法定位。

5. **装机崩溃先读 logcat 的 fault addr**。低 32 位常常是指令编码，可据此判断是「读到了指令数据」还是「空指针」。

6. **代码洞容量是硬约束**。修改前先算字节数，超出时优先考虑降低功能粒度或换位置，而不是临时扩段表。
