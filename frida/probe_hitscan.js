'use strict';
// probe_hitscan.js -- read m_HitscanFireRange (+0x258) and
// m_HitscanImpactLayers (+0x25c) for every ShootableWeapon that fires.

var MODULE = 'libil2cpp.so';

function setup(m) {
  var b = m.base;
  send({ tag: 'info', msg: 'base=' + b });

  var n = 0, MAX = 10;

  Interceptor.attach(b.add(0x200A944), {
    onEnter: function () {
      if (n >= MAX) return;
      n++;
      var x19 = this.context.x19 || this.context.x0;
      var r = { tag: 'HC', n: n, thisp: x19.toString() };
      try { r.range = x19.add(0x258).readFloat(); } catch (e) {}
      try { r.layers = x19.add(0x25c).readS32(); } catch (e) {}
      try { r.dmgEvent = x19.add(0x260).readPointer().toString(); } catch (e) {}
      try { r.dmgAmount = x19.add(0x268).readFloat(); } catch (e) {}
      try { r.fireRange = x19.add(0x258).readFloat(); } catch (e) {}
      // also the projectile path fields
      try { r.fireMode = x19.add(0x160).readS32(); } catch (e) {}
      try {
        var mc = x19.add(0x110).readPointer();
        r.mChar = mc.toString();
      } catch (e) {}
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
