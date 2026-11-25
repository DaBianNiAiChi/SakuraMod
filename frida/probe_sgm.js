'use strict';
// probe_sgm.js -- at SaveGameManager.Start hook point, dump the real addresses
// of the class slot and static_fields so the patch can be written correctly.

var MODULE = 'libil2cpp.so';

function setup(m) {
  var b = m.base;
  send({ tag: 'info', msg: 'base=' + b });

  // hook right after the strb at 0x1E305C4, i.e. 0x1E305C8
  Interceptor.attach(b.add(0x1E305C8), {
    onEnter: function () {
      var r = { tag: 'S' };

      // --- read what FriendlyFireON would read ---
      // 0x1F27358: adrp x20, #...  -> 0x3B9B000
      // 0x1F27360: ldr  x20, [x20, #0xe40]  -> class slot at 0x3B9BE40
      var slot1 = b.add(0x3B9BE40);
      try { r.slot_3B9BE40 = slot1.readPointer().toString(); } catch (e) { r.slot_3B9BE40 = 'ERR'; }

      // 0x1F27390: adrp x20, #... -> 0x3B9A000
      // 0x1F2739C: ldr x20, [x20, #0xa38] -> class slot at 0x3B9AA38
      var slot2 = b.add(0x3B9AA38);
      try { r.slot_3B9AA38 = slot2.readPointer().toString(); } catch (e) { r.slot_3B9AA38 = 'ERR'; }

      // try to walk both
      [['a', slot1], ['b', slot2]].forEach(function (pair) {
        var k = pair[0], s = pair[1];
        try {
          var cls = s.readPointer();
          r['cls_' + k] = cls.toString();
          if (!cls.isNull()) {
            var sf = cls.add(0xB8).readPointer();
            r['sf_' + k] = sf.toString();
            r['sf_off_' + k] = '0x' + sf.sub(b).toString(16);
            if (!sf.isNull()) {
              r['ff_' + k] = sf.add(0x10).readU8();
            }
          }
        } catch (e) {
          r['walk_' + k + '_err'] = String(e).slice(0, 80);
        }
      });

      // also dump the current x19 / this
      try { r.x19 = this.context.x19.toString(); } catch (e) {}

      send(r);
    }
  });

  send({ tag: 'info', msg: 'ARMED' });
}

var mm = Process.findModuleByName(MODULE);
if (mm) { setup(mm); }
else {
  var iv = setInterval(function () {
    var m2 = Process.findModuleByName(MODULE);
    if (m2) { clearInterval(iv); setup(m2); }
  }, 200);
}
