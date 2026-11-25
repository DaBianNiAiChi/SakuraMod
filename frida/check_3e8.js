'use strict';
// check_3e8.js -- read ShootableWeapon.m_characterAI (+0x3E8) for the player's
// weapon vs an AI weapon.

var MODULE = 'libil2cpp.so';

function setup(m) {
  var b = m.base;
  send({ tag: 'info', msg: 'base=' + b });

  var n = 0, MAX = 16;

  Interceptor.attach(b.add(0x200891C), {
    onEnter: function (a) {
      if (n >= MAX) return;
      n++;
      var x19 = this.context.x19;
      var rec = { n: n, x19: x19.toString() };

      try { rec.characterAI_3e8 = x19.add(0x3E8).readPointer().toString(); } catch (e) {}
      try { rec.charStatus_3f0 = x19.add(0x3F0).readPointer().toString(); } catch (e) {}
      try { rec.mChar_110 = x19.add(0x110).readPointer().toString(); } catch (e) {}
      try { rec.aiAgent_2e0 = x19.add(0x2E0).readPointer().toString(); } catch (e) {}

      // player reference
      try {
        var cls = b.add(0x3B9A3D0).readPointer().readPointer();
        var sf = cls.add(0xb8).readPointer();
        var inst = sf.add(0x78).readPointer();
        rec.playerGO = inst.add(0x368).readPointer().toString();
        rec.playerAI = inst.add(0x380).readPointer().toString();
        rec.playerCS = inst.add(0x378).readPointer().toString();
        rec.isPlayer_110 = (rec.mChar_110 === rec.playerGO);
        rec.isPlayer_3e8 = (rec.characterAI_3e8 === rec.playerAI);
        rec.isPlayer_3f0 = (rec.charStatus_3f0 === rec.playerCS);
      } catch (e) {}

      send({ tag: 'CHK', rec: rec });
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
