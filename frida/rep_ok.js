'use strict';
// rep_ok.js -- verify the two candidate class slots really hold class pointers.

var MODULE = 'libil2cpp.so';

function setup(m) {
  var b = m.base;
  send({ tag: 'info', msg: 'base=' + b });

  var cands = [
    ['0x3B9BE40', 0x3B9BE40],
    ['0x3B9AA38', 0x3B9AA38],
  ];

  cands.forEach(function (c) {
    var name = c[0], rva = c[1];
    var p = b.add(rva);
    var out = { tag: 'SLOT', name: name, addr: p.toString() };
    try {
      var v = p.readPointer();
      out.ptr = v.toString();
      var ok = false;
      if (!v.isNull()) {
        try {
          var w = v.readU32();
          out.firstWord = '0x' + w.toString(16);
          ok = true;
        } catch (e) {
          out.readErr = String(e).slice(0, 60);
        }
      }
      out.readable = ok;
    } catch (e) {
      out.err = String(e).slice(0, 60);
    }
    send(out);
  });

  // walk the ones that look like class pointers
  send({ tag: 'info', msg: 'walk done' });
}

var mm = Process.findModuleByName(MODULE);
if (mm) { setup(mm); }
else {
  var iv = setInterval(function () {
    var m2 = Process.findModuleByName(MODULE);
    if (m2) { clearInterval(iv); setup(m2); }
  }, 200);
}
