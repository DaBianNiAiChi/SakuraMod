'use strict';
// verify_s9.js -- at 0x2008928 (fadd s1,s8,s9) read the ACTUAL s9 value,
// the branch taken, and the x21/x9 compared at 0x1FD9DC4.

var MODULE = 'libil2cpp.so';
var lastBranch = null, lastX21 = null, lastX9 = null;

function setup(m) {
  var b = m.base;
  send({ tag: 'info', msg: 'base=' + b });

  var n = 0, MAX = 24;

  // cmp x21, x9  @ 0x1FD9DC4
  Interceptor.attach(b.add(0x1FD9D84), { onEnter: function (a) { send({tag:'CAVE_ENTER', x19: this.context.x19.toString()}); } });
  Interceptor.attach(b.add(0x1FD9DC4), {
    onEnter: function (a) {
      lastX21 = this.context.x21.toString();
      lastX9 = this.context.x9.toString();
    }
  });

  // branch targets
  Interceptor.attach(b.add(0x1FD9DCC), {
    onEnter: function (a) { lastBranch = 'PLAYER'; }
  });
  Interceptor.attach(b.add(0x1FD9DD0), {
    onEnter: function (a) { lastBranch = lastBranch || 'ENEMY'; }
  });

  // fadd s1, s8, s9   @ 0x2008928
  Interceptor.attach(b.add(0x2008928), {
    onEnter: function (a) {
      if (n >= MAX) return;
      n++;
      send({
        tag: 'FADD',
        n: n,
        s9: this.context.s9,
        s8: this.context.s8,
        branch: lastBranch,
        x21: lastX21,
        x9: lastX9
      });
      lastBranch = null;
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
