# 交接文档 —— 樱花校园模拟器 mod 项目

> **写给接手的 agent。请完整读完再动手。**
> **上一个 agent（lead）试了 v85 → v105，共 21 个版本，射速/弹速/换弹/弹道全部没做到用户要求。以下是所有已验证的事实和踩过的坑。**

---

## 一、项目基本情况

**目标**：`C:\Users\<USER>\Desktop\SakuraSimulator_1.047.10.apk`
**工作目录**：`C:\Users\<USER>\Desktop\Android\SakuraUnpack\`（**所有产物必须放在这个目录下**）

**游戏**：《樱花校园模拟器》233乐园(MetaApp)国内合规汉化版
- 包名：`jp.garud.ssimulator.new`（**不要动 `jp.garud.ssimulator`，那是原版，有用户存档**）
- Unity 2022.3.14f1c1 + IL2CPP + ARM64 单 ABI
- `global-metadata.dat` v29 未加密

**设备**：
- serial：`<YOUR_DEVICE_SERIAL>`（Android 14，rooted）
- 触摸设备：`/dev/input/event4`
- 屏幕：1080x2400，density 440
- `adb shell input tap` **无效**（Unity 吞掉），必须写 `/dev/input/event4`

---

## 二、核心地址规则（已验证）

```
文件偏移 = RVA − 0x1000
Frida 内存地址 = moduleBase + RVA
```

**原始 SO**：`_extract\lib\arm64-v8a\libil2cpp.so`
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

---

## 三、⚠️ 最重要的教训：dump.cs 的 RVA 有陷阱

**`_dump\dump.cs`（25MB，78,417 方法）里的 RVA **不可靠**！**

**原因**：IL2CPP 的访问器桩（`ldr x0,[x0,#n]; ret`，8 字节）插在函数之间，`dump.cs` 把它们也当成方法，导致 RVA 错位。

**真实案例（教训）**：
- `0x201C8C4` 标注是 `ButtonAdsPlay.Start`，**实际是访问器桩**，patch 后游戏崩溃
- `0x1A52AC8` 标注是 `get_name()`，**实际是 `CrossPlatformInputManager.VirtualAxis::get_name`**
- `0x36D5AD8` 标注是 `Rigidbody.set_velocity`，**实际是 `NavMeshAgent.set_velocity`**

**正确做法**：用 **`_dump\funmap.json`**（82,756 条 `{start,end,cls,decl}`）查地址归属。
- 工具：`_tools\funmap.py`、`_tools\mapq.py`

**但 `funmap.json` 也不完全可靠**：
- 它只覆盖游戏代码，不含 `UnityEngine.*`
- 会把多个函数合并（如把 `Item.Init` 和 `Item.OnDisable` 归成一个）
- 有些区域标 `None::None`

**最终验证方法：用 capstone 反汇编，看是不是标准的函数序言 `sub sp, sp, #N` 或 `stp x29, x30, [sp, #-N]!`**

---

## 四、用户的核心需求（全部未实现）

### 4.1 用户原话

> **"玩家的发射频率 8 倍，敌人的发射频率原版 1 倍"**
> **"玩家的子弹速度加快，敌人的子弹速度不变"**
> **"玩家不换弹（无限弹匣），敌人正常换弹"**
> **"弹道稳定，不要偏移（导弹横着飞、往上飞）"**
> **"我不接受敌人任何快于原版的选项"**

### 4.2 当前 v85 的实际状态（用户描述）

```
玩家的射速：正常（v85 的 4 倍）
敌人的射速：和玩家一样（也 4 倍）
玩家的弹速：正常
敌人的弹速：和玩家一样
换弹：双方都不换弹
弹道：有偏移问题
```

---

## 五、已验证的关键字段和地址

### 5.1 `ShootableWeapon`（`Opsive.ThirdPersonController.ShootableWeapon`）

**继承链**：`ShootableWeapon : Weapon : Item : MonoBehaviour`

```
0x28   m_ItemType (ItemType)
0x110  m_Character (GameObject)        ← ★ 能区分玩家/AI！
0x120  m_Inventory (Inventory)
0x150  m_ReloadStates
0x158  m_FirePoint (Transform)
0x160  m_FireMode (int: 0=Single, 1=Burst, 2=FullAuto)
0x164  m_FireRate (float)
0x168  m_BurstRate (int)
0x16C  m_ClipSize (int)
0x170  m_FireCount (int)
0x2E0  m_AIAgent (SharedMethod<bool>)  ← 恒非 null，但每次不同，不能区分
0x2F8  m_ShootDelay (float)            ← ★ 射速控制点
0x2FC  m_LastShootTime (float)
0x300  m_CurrentBurst (int)
0x304  m_IsFiring (bool)
0x305  m_CanFire (bool)
0x308  m_FireEvent (ScheduledEvent)    ← ★ 实测是 null（0x0）！
0x319  m_Reloading (bool)
0x3E0  TryUseCnt (byte)
0x3E8  m_characterAI (CharacterAI)
0x3F0  m_CharacterStatus (CharacterStatus)
0x3F8  ReloadCnt (byte)                ← ⚠️ 不是空闲字段！会被 CanUse() 自增
0x3F9  InfinityWeapon (bool)
```

### 5.2 `Item`（基类）

```
0x110  m_Character (GameObject)        ← Init 时 = get_gameObject(inventory)
0x120  m_Inventory (Inventory)
```

### 5.3 `Inventory`

```
0xD8   m_GameObject (GameObject)       ← 实测不等于玩家 GameObject
```

### 5.4 `SystemManager`

```
0x368  m_Character (GameObject)        ← ★ 玩家 GameObject，★ 稳定！
0x370  m_Charactertransform (Transform)
0x378  m_CharacterStatus
0x380  m_CharacterAI
```

**访问链**（血无敌补丁已验证）：
```asm
adrp x9, #0x1bda000        ; 或等价 adrp 到 0x3B9A3D0 的页
ldr  x9, [x9, #0x3d0]      ; 类指针槽（★ 在 .got 段，游戏运行中才有值）
ldr  x9, [x9]              ; 类对象
ldr  w10, [x9, #0xe0]      ; classinit 检查
cbnz w10, +0x8
bl   0x1808CE4             ; classinit
ldr  x9, [x9, #0xb8]       ; static_fields
ldr  x9, [x9, #0x78]       ; instance
ldr  x9, [x9, #0x368]      ; m_Character
```

### 5.5 关键 RVA（已用 capstone 验证过是函数入口）

```
Item.Init                         0x2000E18
Item.OnDisable                    0x2000DB4
Item.Init 里 m_Character 赋值     0x2000F48  (str x1,[x19,#0x110])
Item.Init 里 bl InitializeShared  0x2001264

ShootableWeapon.Awake             0x2006F18
  └ 0x20071B4: fmov s0,#0.25      ← ★ v85 的射速系数（原版是 #1.0）
  └ 0x20071B8: fdiv s2,s0,s2
  └ 0x20071C0: str s2,[x19,#0x2f8]
ShootableWeapon.Init              0x2008514
ShootableWeapon.TryUse            0x2008888
  └ 0x20088D0: ldrb w8,[x19,#0x304]   m_IsFiring
  └ 0x20088D8: ldrb w8,[x19,#0x3e0]   TryUseCnt
  └ 0x20088E0: tst w8,#0xfc           (cnt & 0xFC) != 0 → 不放行
  └ 0x2008918: ldr s8,[x19,#0x2fc]    m_LastShootTime
  └ 0x200891C: ldr s9,[x19,#0x2f8]    m_ShootDelay   ← ★ 常用跳板点
  └ 0x2008928: fadd s1,s8,s9
  └ 0x200892C: fcmp s1,s0
  └ 0x2008930: b.pl                   ← 还在冷却
  └ 0x2008934: ldr x8,[x19,#0x350]    m_OverheatEvent
  └ 0x200893C: ldrb w8,[x19,#0x3f9]   InfinityWeapon
  └ 0x2008944: ldr x0,[x19,#0x120]    m_Inventory
  └ 0x2008954: bl                     ; 弹匣检查
ShootableWeapon.Fire              0x2009DF4
ShootableWeapon.ProjectileFire    0x2009E74
ShootableWeapon.DoFire            0x2008A98
ShootableWeapon.EmptyClip         0x2008D80
ShootableWeapon.TryStartReload    0x2007E5C
ShootableWeapon.CanUse            0x2009200

Projectile.Initialize             0x200A470
  └ 0x200A4A0: mov x20, x2           ; x20 = originator GameObject
  └ 0x200A4B4: mov v13.16b, v2.16b   ; dir.z
  └ 0x200A4B8: mov v12.16b, v1.16b   ; dir.y
  └ 0x200A4BC: mov v11.16b, v0.16b   ; dir.x
  └ 0x200A564: ldur s0,[x24,#-0x34]  ; s0 = m_Speed (+0x74)
  └ 0x200A568: fmul s1,s11,s0        ← 常用跳板点
  └ 0x200A56C: fmul s2,s12,s0
  └ 0x200A570: fmul s0,s13,s0
  └ 0x200A574: stp s1,s2,[x24,#-0x20]
Projectile.FixedUpdate            0x2012560

Component.get_transform           0x373FE3C   ✅ 验证过是入口
Component.get_gameObject          0x373FE78   ✅ 验证过是入口
Transform.get_parent              0x374C7FC   ✅ 验证过是入口
Rigidbody.set_velocity            0x379A304   （不是 0x36D5AD8！）
Rigidbody.AddForce                0x379BD80
IL2CPP classinit                  0x1808CE4
SystemManager 类指针槽            0x3B9A3D0

CharacterAI.Attack                0x21DF2B0
CharacterAI.HasWeaponCheck        0x21CE724
```

---

## 六、代码洞可用空间

```
0x1FD9D5C..0x1FD9D80   36 字节   v85 子弹速度代码洞（已用于 6 倍弹速）
0x1FD9D84..0x1FD9E08  128 字节   ★ 完全空闲（死 DebugLog 代码）
0x1FD9E0C..0x1FD9E38   44 字节   v85 金钱代码洞
```

**这 128 字节是 `AnimatorMonitor.OnDeath` 里的 `[Conditional]` DebugLog 残留代码，release 版永远不会执行，可以完全覆盖。**

**扫描确认：整个 .text 段没有其它 ≥100 字节的连续 RET/NOP 串。**

---

## 七、已验证的运行时事实（用 Frida 探针实测）

### 7.1 `Item.m_Character`（`+0x110`）能完美区分玩家和 AI

**探针 `check_3e8.js` 实测 20 次开火：**
```
玩家武器:  m_Char (+0x110) = 0x7550be3a80 == SystemManager.m_Character  ✅
AI 武器:   m_Char (+0x110) = 各种其他值 != 玩家                          ✅
```

**这个判据**是有效的**，在 `TryUse`（`0x200891C`）处读取时 100% 准确。**

**⚠️ 但在 `Awake`（`0x2006F18`）时 `m_Character` 还是 null**（武器还没挂到角色上）。

### 7.2 `m_ShootDelay` 是射速控制点，但改它无效

**探针 `verify_s9.js` 实测：**
```
玩家武器:  s9 = 0.0625（原版 0.5 的 1/8）
AI 武器:   s9 = 0.5   （原版）
```

**探针证明 `s9` 确实传进了 `fadd s1,s8,s9`。**

**但用户实测游戏行为**没有任何变化。**

**这是最大的谜团——需要新 agent 解开。**

### 7.3 `m_FireEvent`（`+0x308`）是 null

**探针 `probe_fireevent.js` 实测：每个武器的 `m_FireEvent` 都是 `0x0`。**

**所以 `ScheduledEvent` 不是控制点。**

### 7.4 `Fire()` 调用非常频繁

**探针 `fire_trace.js` 实测：**
```
FIRE  A  last=93.9657
FIRE  A  last=94.0975  ← 间隔 0.13s
FIRE  A  last=118.124  ← 间隔 0.09s
FIRE  A  last=118.157  ← 间隔 0.033s
```

**`Fire()` 每 0.03~0.13 秒调用一次，说明冷却判断在别处。**

### 7.5 `TryUseCnt`（`+0x3E0`）是连发节流

```asm
0x20088D8: ldrb w8,[x19,#0x3e0]
0x20088DC: add  w8,w8,#1
0x20088E0: tst  w8,#0xfc
0x20088E4: strb w8,[x19,#0x3e0]
0x20088E8: b.eq +0x130    ; (cnt & 0xFC)==0 才放行
```

**即 `cnt % 64 == 0` 才放行。**

### 7.6 v85 的 7 处 `m_FireMode` 全局强制

**v85 把这 7 处的 `ldr w?,[x19,#0x160]` 改成了 `mov w?,#1`（Burst）：**
```
0x2008C08, 0x2008EDC, 0x2008F00, 0x20090C4,
0x20090E8, 0x2009774, 0x20097C0
```
**这导致所有武器（含 AI）都变连发。v104 已尝试恢复，但用户说无变化。**

---

## 八、v85 补丁完整清单（141 处改动）

**v85 = 用户最后确认"射速有效"的基线**
`_patched_v85\libil2cpp.so` sha256 `25b479de9fb2a67edc0bd4a2752a833b88d9e7a0630e92fb07a350c95ecf17b9`

主要改动：
```
0x20071B4: fmov s0,#1.0  →  #0.25      ★ 全局 4 倍射速
0x2008C08 等 7 处: FireMode → 1 (Burst)
0x200A568: 跳板 → 子弹速度 ×6 代码洞
0x1E4F260: 跳板 → 金钱代码洞
0x1E3202C: nop（FunnyMode 根因）
0x1EAB6B4: ret（ChangeFunnyModeWeapon）
0x220CCEC: ret
大量 mov w0,#1 / mov w0,wzr / ret（各种解锁）
```

---

## 九、最关键的未解之谜（新 agent 请从这里开始）

### **为什么改 `m_ShootDelay` 对实际射速没影响？**

**已知：**
- v85 的 `0x20071B4: fmov s0,#0.25`（改 Awake 里的系数）→ **射速确实变 4 倍**（用户确认）
- v102-v105 的 TryUse 钩子改 `s9` → **探针显示 s9 变了，但游戏行为没变**
- `m_FireEvent` 是 null
- `Fire()` 被每帧频繁调用

**推测（未验证）：**
1. **`m_ShootDelay` 在 `Awake` 之后被别处重新计算/覆盖**
2. **真正的冷却判断在 `WeaponHandler` 或某个 `Update` 里，用的不是 `m_ShootDelay`**
3. **`Opsive.ThirdPersonController.Scheduler` 有独立的计时器**

**建议的下一步：**
1. **用 Frida 追踪 `m_ShootDelay`（`+0x2F8`）的所有写入点**（用 `MemoryAccessMonitor` 或 hook 所有 `str`）
2. **找到谁在 `Awake` 之后重写它**
3. **或者：直接 hook `Fire()`，看它被调用的**真实条件**（不是 `TryUse`）

---

## 十、工具和环境

### Python
```
C:\Users\<USER>\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe
```
**已装**：frida 17.27.5、capstone 5.0.9、UnityPy 1.25.4

### ⚠️ Frida 17.27.5 的坑
```js
Module.enumerateExports()                          // ❌ undefined
Process.enumerateModuleExports(...)                // ❌ undefined
Process.getModuleByName('x.so').enumerateExports() // ✅
Module.findGlobalExportByName('il2cpp_xxx')        // ❌ null（GNU-hash-only）
```
**Frida 里进程名是 `SakuraSimulator`（Unity product name），不是包名！**

**Frida 会自动把 `rpc.exports` 的 `probe_value` 转成 `probeValue`。**

### Zig 交叉编译
```
_tools\zig\zig-windows-x86_64-0.13.0\zig.exe
zig cc -target aarch64-linux-musl -O2 -static -o out src.c
```
**解压用 `tar -xf`，不要用 `Expand-Archive`（太慢）。**

### APK 打包流程
```
1. 基础包：build\signed61\Sakura_v61-aligned-debugSigned.apk
2. 替换 lib/arm64-v8a/libil2cpp.so
3. 替换 assets/aa/Android/packed_assets_all.bundle（可选，广告补丁）
4. 签名：cmd /c 'java -jar "C:\Users\<USER>\Desktop\Android\uber-apk-signer.jar" -a "<apk>" -o "<outdir>"'
```

### ⚠️ 装机必须用卸载+安装（`install -r` 不会替换 SO！）
```powershell
adb -s <YOUR_DEVICE_SERIAL> shell am force-stop jp.garud.ssimulator.new
adb -s <YOUR_DEVICE_SERIAL> uninstall jp.garud.ssimulator.new
adb -s <YOUR_DEVICE_SERIAL> install --no-streaming <apk>
adb -s <YOUR_DEVICE_SERIAL> shell "su -c 'sha256sum /data/app/*/jp.garud.ssimulator.new*/lib/arm64/libil2cpp.so'"
```

---

## 十一、Frida 探针工具（可直接复用）

```
_tools\frida\
  check_clip.js / _run.py           → 读 m_ClipSize / m_ShootDelay
  check_3e8.js / _run.py            → 对比 m_characterAI / m_CharacterStatus / m_Character
  verify_s9.js / _run.py            → 读 TryUse 冷却判断的 s9 值
  fire_trace.js / _run.py           → 追踪 TryUse → DoFire → Fire → ProjectileFire
  measure_rate2.js / _run.py        → 按 owner 分组测射速间隔
  measure_bullet.js / _run.py       → 测弹丸 m_Speed
  probe_fireevent.js / _run.py      → 读 m_FireEvent
  runtime_patch.js / _run.py        → 纯运行时改射速和弹速（未验证效果）
```

---

## 十二、其它待办（优先级低于射速）

1. **BEAM 武器默认解锁**
   ```
   SaveGameManager.HasBeamLauncher   +0x90  int[]
   SaveGameManager.EquipBeamLauncher +0xC8  bool[]
   方法：
     Awake           0x1E300BC
     Start           0x1E30548
     Save            0x1E33AF4
     SaveHasWeapon   0x1E3765C
     CheckHasWeapon  0x1E37D08
     LoadHasWeapon   0x1E39228
   ```

2. **锁图标**（试过 6 种方法全失败）
   - `ButtonAdsPlay.PlayMark`（`+0x20`）零写入者
   - prefab `ImagePlayAds` 的 `m_IsActive` 一直是 1

3. **枪械粉色外观**（233 合规 mesh）

4. **被攻击不变机器人**

5. **能攻击 NPC/警察**

---

## 十三、用户沟通要点

1. **版本号只能升不能降**（v85 → v106 → …）
2. **不要回滚**，直接修
3. **一次改完所有问题**，不要一个一个来
4. **不要截图糊弄**，要真实行为验证
5. **用户很急躁**，请高效工作，先确认再动手
6. **不要动 `jp.garud.ssimulator`**（那是原版，有存档）
7. **所有产物放在 `C:\Users\<USER>\Desktop\Android\SakuraUnpack\` 下**

---

## 十四、最终建议

**上一个 agent 失败的核心原因：一直在 `ShootableWeapon.TryUse` 这一个函数上打补丁，而没有真正追踪到"谁在限制射速"。**

**新 agent 请：**
1. **先用 Frida `MemoryAccessMonitor` 监控 `m_ShootDelay`（`+0x2F8`）的所有读写**
2. **找到 `Awake` 之后谁重写了它**
3. **或者直接 hook `Fire()`，看调用它的真实条件**
4. **不要假设，全部用探针验证**

**祝成功。**
