'use strict';
// set_ff.js -- runtime experiment: force SaveGameManager.FriendlyFire = true
// and report the value before/after.

var MODULE = 'libil2cpp.so';

function setup(m) {
  var b = m.base;
  send({ tag: 'info', msg: 'base=' + b });

  // class slot candidates, from FriendlyFireON disassembly
  var cands = [0x3B9BE40, 0x3B9AA38];

  cands.forEach(function (rva) {
    var slot = b.add(rva);
    var r = { tag: 'TRY', slot: '0x' + rva.toString(16) };
    try {
      var cls = slot.readPointer();
      r.cls = cls.toString();
      if (cls.isNull()) { send(r); return; }
      // class object: +0xb8 = static_fields
      var sf = cls.add(0xB8).readPointer();
      r.sf = sf.toString();
      if (sf.isNull()) { send(r); return; }
      var before = sf.add(0x10).readU8();
      r.before = before;
      sf.add(0x10).writeU8(1);
      var after = sf.add(0x10).readU8();
      r.after = after;
    } catch (e) {
      r.err = String(e).slice(0, 100);
    }
    send(r);
  });

  send({ tag: 'DONE' });
}

var mm = Process.findModuleByName(MODULE);
if (mm) { setup(mm); }
else {
  var iv = setInterval(function () {
    var m2 = Process.findModuleByName(MODULE);
    if (m2) { clearInterval(iv); setup(m2); }
  }, 200);
}
