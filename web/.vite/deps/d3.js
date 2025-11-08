import {
  Transform,
  active_default,
  array_default,
  backIn,
  backInOut,
  backOut,
  basisClosed_default,
  basis_default,
  bounceIn,
  bounceInOut,
  bounceOut,
  circleIn,
  circleInOut,
  circleOut,
  color,
  create_default,
  creator_default,
  cubehelix,
  cubehelixLong,
  cubehelix_default,
  cubicIn,
  cubicInOut,
  cubicOut,
  date_default,
  discrete_default,
  dispatch_default,
  drag_default,
  elasticIn,
  elasticInOut,
  elasticOut,
  expIn,
  expInOut,
  expOut,
  gray,
  hcl,
  hclLong,
  hcl_default,
  hsl,
  hslLong,
  hsl_default,
  hue_default,
  identity,
  interpolateTransformCss,
  interpolateTransformSvg,
  interrupt_default,
  interval_default,
  lab,
  lab2,
  lch,
  linear,
  local,
  matcher_default,
  namespace_default,
  namespaces_default,
  nodrag_default,
  now,
  numberArray_default,
  number_default,
  object_default,
  piecewise,
  pointer_default,
  pointers_default,
  polyIn,
  polyInOut,
  polyOut,
  quadIn,
  quadInOut,
  quadOut,
  quantize_default,
  rgb,
  rgbBasis,
  rgbBasisClosed,
  rgb_default,
  round_default,
  selectAll_default,
  select_default,
  selection_default,
  selectorAll_default,
  selector_default,
  sinIn,
  sinInOut,
  sinOut,
  string_default,
  styleValue,
  timeout_default,
  timer,
  timerFlush,
  transform,
  transition,
  value_default,
  window_default,
  yesdrag,
  zoom_default,
  zoom_default2
} from "./chunk-F7R3KYJL.js";
import "./chunk-G3PMV62Z.js";

// node_modules/d3-array/src/ascending.js
function ascending(a4, b) {
  return a4 == null || b == null ? NaN : a4 < b ? -1 : a4 > b ? 1 : a4 >= b ? 0 : NaN;
}

// node_modules/d3-array/src/descending.js
function descending(a4, b) {
  return a4 == null || b == null ? NaN : b < a4 ? -1 : b > a4 ? 1 : b >= a4 ? 0 : NaN;
}

// node_modules/d3-array/src/bisector.js
function bisector(f) {
  let compare1, compare2, delta;
  if (f.length !== 2) {
    compare1 = ascending;
    compare2 = (d, x4) => ascending(f(d), x4);
    delta = (d, x4) => f(d) - x4;
  } else {
    compare1 = f === ascending || f === descending ? f : zero;
    compare2 = f;
    delta = f;
  }
  function left2(a4, x4, lo = 0, hi = a4.length) {
    if (lo < hi) {
      if (compare1(x4, x4) !== 0) return hi;
      do {
        const mid = lo + hi >>> 1;
        if (compare2(a4[mid], x4) < 0) lo = mid + 1;
        else hi = mid;
      } while (lo < hi);
    }
    return lo;
  }
  function right2(a4, x4, lo = 0, hi = a4.length) {
    if (lo < hi) {
      if (compare1(x4, x4) !== 0) return hi;
      do {
        const mid = lo + hi >>> 1;
        if (compare2(a4[mid], x4) <= 0) lo = mid + 1;
        else hi = mid;
      } while (lo < hi);
    }
    return lo;
  }
  function center2(a4, x4, lo = 0, hi = a4.length) {
    const i = left2(a4, x4, lo, hi - 1);
    return i > lo && delta(a4[i - 1], x4) > -delta(a4[i], x4) ? i - 1 : i;
  }
  return { left: left2, center: center2, right: right2 };
}
function zero() {
  return 0;
}

// node_modules/d3-array/src/number.js
function number(x4) {
  return x4 === null ? NaN : +x4;
}
function* numbers(values, valueof) {
  if (valueof === void 0) {
    for (let value of values) {
      if (value != null && (value = +value) >= value) {
        yield value;
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && (value = +value) >= value) {
        yield value;
      }
    }
  }
}

// node_modules/d3-array/src/bisect.js
var ascendingBisect = bisector(ascending);
var bisectRight = ascendingBisect.right;
var bisectLeft = ascendingBisect.left;
var bisectCenter = bisector(number).center;
var bisect_default = bisectRight;

// node_modules/d3-array/src/blur.js
function blur(values, r) {
  if (!((r = +r) >= 0)) throw new RangeError("invalid r");
  let length3 = values.length;
  if (!((length3 = Math.floor(length3)) >= 0)) throw new RangeError("invalid length");
  if (!length3 || !r) return values;
  const blur3 = blurf(r);
  const temp = values.slice();
  blur3(values, temp, 0, length3, 1);
  blur3(temp, values, 0, length3, 1);
  blur3(values, temp, 0, length3, 1);
  return values;
}
var blur2 = Blur2(blurf);
var blurImage = Blur2(blurfImage);
function Blur2(blur3) {
  return function(data, rx, ry = rx) {
    if (!((rx = +rx) >= 0)) throw new RangeError("invalid rx");
    if (!((ry = +ry) >= 0)) throw new RangeError("invalid ry");
    let { data: values, width, height } = data;
    if (!((width = Math.floor(width)) >= 0)) throw new RangeError("invalid width");
    if (!((height = Math.floor(height !== void 0 ? height : values.length / width)) >= 0)) throw new RangeError("invalid height");
    if (!width || !height || !rx && !ry) return data;
    const blurx = rx && blur3(rx);
    const blury = ry && blur3(ry);
    const temp = values.slice();
    if (blurx && blury) {
      blurh(blurx, temp, values, width, height);
      blurh(blurx, values, temp, width, height);
      blurh(blurx, temp, values, width, height);
      blurv(blury, values, temp, width, height);
      blurv(blury, temp, values, width, height);
      blurv(blury, values, temp, width, height);
    } else if (blurx) {
      blurh(blurx, values, temp, width, height);
      blurh(blurx, temp, values, width, height);
      blurh(blurx, values, temp, width, height);
    } else if (blury) {
      blurv(blury, values, temp, width, height);
      blurv(blury, temp, values, width, height);
      blurv(blury, values, temp, width, height);
    }
    return data;
  };
}
function blurh(blur3, T, S, w, h) {
  for (let y4 = 0, n = w * h; y4 < n; ) {
    blur3(T, S, y4, y4 += w, 1);
  }
}
function blurv(blur3, T, S, w, h) {
  for (let x4 = 0, n = w * h; x4 < w; ++x4) {
    blur3(T, S, x4, x4 + n, w);
  }
}
function blurfImage(radius) {
  const blur3 = blurf(radius);
  return (T, S, start, stop, step) => {
    start <<= 2, stop <<= 2, step <<= 2;
    blur3(T, S, start + 0, stop + 0, step);
    blur3(T, S, start + 1, stop + 1, step);
    blur3(T, S, start + 2, stop + 2, step);
    blur3(T, S, start + 3, stop + 3, step);
  };
}
function blurf(radius) {
  const radius0 = Math.floor(radius);
  if (radius0 === radius) return bluri(radius);
  const t = radius - radius0;
  const w = 2 * radius + 1;
  return (T, S, start, stop, step) => {
    if (!((stop -= step) >= start)) return;
    let sum4 = radius0 * S[start];
    const s0 = step * radius0;
    const s1 = s0 + step;
    for (let i = start, j = start + s0; i < j; i += step) {
      sum4 += S[Math.min(stop, i)];
    }
    for (let i = start, j = stop; i <= j; i += step) {
      sum4 += S[Math.min(stop, i + s0)];
      T[i] = (sum4 + t * (S[Math.max(start, i - s1)] + S[Math.min(stop, i + s1)])) / w;
      sum4 -= S[Math.max(start, i - s0)];
    }
  };
}
function bluri(radius) {
  const w = 2 * radius + 1;
  return (T, S, start, stop, step) => {
    if (!((stop -= step) >= start)) return;
    let sum4 = radius * S[start];
    const s2 = step * radius;
    for (let i = start, j = start + s2; i < j; i += step) {
      sum4 += S[Math.min(stop, i)];
    }
    for (let i = start, j = stop; i <= j; i += step) {
      sum4 += S[Math.min(stop, i + s2)];
      T[i] = sum4 / w;
      sum4 -= S[Math.max(start, i - s2)];
    }
  };
}

// node_modules/d3-array/src/count.js
function count(values, valueof) {
  let count3 = 0;
  if (valueof === void 0) {
    for (let value of values) {
      if (value != null && (value = +value) >= value) {
        ++count3;
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && (value = +value) >= value) {
        ++count3;
      }
    }
  }
  return count3;
}

// node_modules/d3-array/src/cross.js
function length(array3) {
  return array3.length | 0;
}
function empty(length3) {
  return !(length3 > 0);
}
function arrayify(values) {
  return typeof values !== "object" || "length" in values ? values : Array.from(values);
}
function reducer(reduce2) {
  return (values) => reduce2(...values);
}
function cross(...values) {
  const reduce2 = typeof values[values.length - 1] === "function" && reducer(values.pop());
  values = values.map(arrayify);
  const lengths = values.map(length);
  const j = values.length - 1;
  const index3 = new Array(j + 1).fill(0);
  const product = [];
  if (j < 0 || lengths.some(empty)) return product;
  while (true) {
    product.push(index3.map((j2, i2) => values[i2][j2]));
    let i = j;
    while (++index3[i] === lengths[i]) {
      if (i === 0) return reduce2 ? product.map(reduce2) : product;
      index3[i--] = 0;
    }
  }
}

// node_modules/d3-array/src/cumsum.js
function cumsum(values, valueof) {
  var sum4 = 0, index3 = 0;
  return Float64Array.from(values, valueof === void 0 ? (v2) => sum4 += +v2 || 0 : (v2) => sum4 += +valueof(v2, index3++, values) || 0);
}

// node_modules/d3-array/src/variance.js
function variance(values, valueof) {
  let count3 = 0;
  let delta;
  let mean2 = 0;
  let sum4 = 0;
  if (valueof === void 0) {
    for (let value of values) {
      if (value != null && (value = +value) >= value) {
        delta = value - mean2;
        mean2 += delta / ++count3;
        sum4 += delta * (value - mean2);
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && (value = +value) >= value) {
        delta = value - mean2;
        mean2 += delta / ++count3;
        sum4 += delta * (value - mean2);
      }
    }
  }
  if (count3 > 1) return sum4 / (count3 - 1);
}

// node_modules/d3-array/src/deviation.js
function deviation(values, valueof) {
  const v2 = variance(values, valueof);
  return v2 ? Math.sqrt(v2) : v2;
}

// node_modules/d3-array/src/extent.js
function extent(values, valueof) {
  let min4;
  let max5;
  if (valueof === void 0) {
    for (const value of values) {
      if (value != null) {
        if (min4 === void 0) {
          if (value >= value) min4 = max5 = value;
        } else {
          if (min4 > value) min4 = value;
          if (max5 < value) max5 = value;
        }
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null) {
        if (min4 === void 0) {
          if (value >= value) min4 = max5 = value;
        } else {
          if (min4 > value) min4 = value;
          if (max5 < value) max5 = value;
        }
      }
    }
  }
  return [min4, max5];
}

// node_modules/d3-array/src/fsum.js
var Adder = class {
  constructor() {
    this._partials = new Float64Array(32);
    this._n = 0;
  }
  add(x4) {
    const p = this._partials;
    let i = 0;
    for (let j = 0; j < this._n && j < 32; j++) {
      const y4 = p[j], hi = x4 + y4, lo = Math.abs(x4) < Math.abs(y4) ? x4 - (hi - y4) : y4 - (hi - x4);
      if (lo) p[i++] = lo;
      x4 = hi;
    }
    p[i] = x4;
    this._n = i + 1;
    return this;
  }
  valueOf() {
    const p = this._partials;
    let n = this._n, x4, y4, lo, hi = 0;
    if (n > 0) {
      hi = p[--n];
      while (n > 0) {
        x4 = hi;
        y4 = p[--n];
        hi = x4 + y4;
        lo = y4 - (hi - x4);
        if (lo) break;
      }
      if (n > 0 && (lo < 0 && p[n - 1] < 0 || lo > 0 && p[n - 1] > 0)) {
        y4 = lo * 2;
        x4 = hi + y4;
        if (y4 == x4 - hi) hi = x4;
      }
    }
    return hi;
  }
};
function fsum(values, valueof) {
  const adder = new Adder();
  if (valueof === void 0) {
    for (let value of values) {
      if (value = +value) {
        adder.add(value);
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if (value = +valueof(value, ++index3, values)) {
        adder.add(value);
      }
    }
  }
  return +adder;
}
function fcumsum(values, valueof) {
  const adder = new Adder();
  let index3 = -1;
  return Float64Array.from(
    values,
    valueof === void 0 ? (v2) => adder.add(+v2 || 0) : (v2) => adder.add(+valueof(v2, ++index3, values) || 0)
  );
}

// node_modules/internmap/src/index.js
var InternMap = class extends Map {
  constructor(entries, key = keyof) {
    super();
    Object.defineProperties(this, { _intern: { value: /* @__PURE__ */ new Map() }, _key: { value: key } });
    if (entries != null) for (const [key2, value] of entries) this.set(key2, value);
  }
  get(key) {
    return super.get(intern_get(this, key));
  }
  has(key) {
    return super.has(intern_get(this, key));
  }
  set(key, value) {
    return super.set(intern_set(this, key), value);
  }
  delete(key) {
    return super.delete(intern_delete(this, key));
  }
};
var InternSet = class extends Set {
  constructor(values, key = keyof) {
    super();
    Object.defineProperties(this, { _intern: { value: /* @__PURE__ */ new Map() }, _key: { value: key } });
    if (values != null) for (const value of values) this.add(value);
  }
  has(value) {
    return super.has(intern_get(this, value));
  }
  add(value) {
    return super.add(intern_set(this, value));
  }
  delete(value) {
    return super.delete(intern_delete(this, value));
  }
};
function intern_get({ _intern, _key }, value) {
  const key = _key(value);
  return _intern.has(key) ? _intern.get(key) : value;
}
function intern_set({ _intern, _key }, value) {
  const key = _key(value);
  if (_intern.has(key)) return _intern.get(key);
  _intern.set(key, value);
  return value;
}
function intern_delete({ _intern, _key }, value) {
  const key = _key(value);
  if (_intern.has(key)) {
    value = _intern.get(key);
    _intern.delete(key);
  }
  return value;
}
function keyof(value) {
  return value !== null && typeof value === "object" ? value.valueOf() : value;
}

// node_modules/d3-array/src/identity.js
function identity2(x4) {
  return x4;
}

// node_modules/d3-array/src/group.js
function group(values, ...keys) {
  return nest(values, identity2, identity2, keys);
}
function groups(values, ...keys) {
  return nest(values, Array.from, identity2, keys);
}
function flatten(groups2, keys) {
  for (let i = 1, n = keys.length; i < n; ++i) {
    groups2 = groups2.flatMap((g) => g.pop().map(([key, value]) => [...g, key, value]));
  }
  return groups2;
}
function flatGroup(values, ...keys) {
  return flatten(groups(values, ...keys), keys);
}
function flatRollup(values, reduce2, ...keys) {
  return flatten(rollups(values, reduce2, ...keys), keys);
}
function rollup(values, reduce2, ...keys) {
  return nest(values, identity2, reduce2, keys);
}
function rollups(values, reduce2, ...keys) {
  return nest(values, Array.from, reduce2, keys);
}
function index(values, ...keys) {
  return nest(values, identity2, unique, keys);
}
function indexes(values, ...keys) {
  return nest(values, Array.from, unique, keys);
}
function unique(values) {
  if (values.length !== 1) throw new Error("duplicate key");
  return values[0];
}
function nest(values, map4, reduce2, keys) {
  return (function regroup(values2, i) {
    if (i >= keys.length) return reduce2(values2);
    const groups2 = new InternMap();
    const keyof2 = keys[i++];
    let index3 = -1;
    for (const value of values2) {
      const key = keyof2(value, ++index3, values2);
      const group2 = groups2.get(key);
      if (group2) group2.push(value);
      else groups2.set(key, [value]);
    }
    for (const [key, values3] of groups2) {
      groups2.set(key, regroup(values3, i));
    }
    return map4(groups2);
  })(values, 0);
}

// node_modules/d3-array/src/permute.js
function permute(source, keys) {
  return Array.from(keys, (key) => source[key]);
}

// node_modules/d3-array/src/sort.js
function sort(values, ...F) {
  if (typeof values[Symbol.iterator] !== "function") throw new TypeError("values is not iterable");
  values = Array.from(values);
  let [f] = F;
  if (f && f.length !== 2 || F.length > 1) {
    const index3 = Uint32Array.from(values, (d, i) => i);
    if (F.length > 1) {
      F = F.map((f2) => values.map(f2));
      index3.sort((i, j) => {
        for (const f2 of F) {
          const c6 = ascendingDefined(f2[i], f2[j]);
          if (c6) return c6;
        }
      });
    } else {
      f = values.map(f);
      index3.sort((i, j) => ascendingDefined(f[i], f[j]));
    }
    return permute(values, index3);
  }
  return values.sort(compareDefined(f));
}
function compareDefined(compare = ascending) {
  if (compare === ascending) return ascendingDefined;
  if (typeof compare !== "function") throw new TypeError("compare is not a function");
  return (a4, b) => {
    const x4 = compare(a4, b);
    if (x4 || x4 === 0) return x4;
    return (compare(b, b) === 0) - (compare(a4, a4) === 0);
  };
}
function ascendingDefined(a4, b) {
  return (a4 == null || !(a4 >= a4)) - (b == null || !(b >= b)) || (a4 < b ? -1 : a4 > b ? 1 : 0);
}

// node_modules/d3-array/src/groupSort.js
function groupSort(values, reduce2, key) {
  return (reduce2.length !== 2 ? sort(rollup(values, reduce2, key), (([ak, av], [bk, bv]) => ascending(av, bv) || ascending(ak, bk))) : sort(group(values, key), (([ak, av], [bk, bv]) => reduce2(av, bv) || ascending(ak, bk)))).map(([key2]) => key2);
}

// node_modules/d3-array/src/array.js
var array = Array.prototype;
var slice = array.slice;
var map = array.map;

// node_modules/d3-array/src/constant.js
function constant(x4) {
  return () => x4;
}

// node_modules/d3-array/src/ticks.js
var e10 = Math.sqrt(50);
var e5 = Math.sqrt(10);
var e2 = Math.sqrt(2);
function tickSpec(start, stop, count3) {
  const step = (stop - start) / Math.max(0, count3), power = Math.floor(Math.log10(step)), error = step / Math.pow(10, power), factor = error >= e10 ? 10 : error >= e5 ? 5 : error >= e2 ? 2 : 1;
  let i1, i2, inc2;
  if (power < 0) {
    inc2 = Math.pow(10, -power) / factor;
    i1 = Math.round(start * inc2);
    i2 = Math.round(stop * inc2);
    if (i1 / inc2 < start) ++i1;
    if (i2 / inc2 > stop) --i2;
    inc2 = -inc2;
  } else {
    inc2 = Math.pow(10, power) * factor;
    i1 = Math.round(start / inc2);
    i2 = Math.round(stop / inc2);
    if (i1 * inc2 < start) ++i1;
    if (i2 * inc2 > stop) --i2;
  }
  if (i2 < i1 && 0.5 <= count3 && count3 < 2) return tickSpec(start, stop, count3 * 2);
  return [i1, i2, inc2];
}
function ticks(start, stop, count3) {
  stop = +stop, start = +start, count3 = +count3;
  if (!(count3 > 0)) return [];
  if (start === stop) return [start];
  const reverse2 = stop < start, [i1, i2, inc2] = reverse2 ? tickSpec(stop, start, count3) : tickSpec(start, stop, count3);
  if (!(i2 >= i1)) return [];
  const n = i2 - i1 + 1, ticks2 = new Array(n);
  if (reverse2) {
    if (inc2 < 0) for (let i = 0; i < n; ++i) ticks2[i] = (i2 - i) / -inc2;
    else for (let i = 0; i < n; ++i) ticks2[i] = (i2 - i) * inc2;
  } else {
    if (inc2 < 0) for (let i = 0; i < n; ++i) ticks2[i] = (i1 + i) / -inc2;
    else for (let i = 0; i < n; ++i) ticks2[i] = (i1 + i) * inc2;
  }
  return ticks2;
}
function tickIncrement(start, stop, count3) {
  stop = +stop, start = +start, count3 = +count3;
  return tickSpec(start, stop, count3)[2];
}
function tickStep(start, stop, count3) {
  stop = +stop, start = +start, count3 = +count3;
  const reverse2 = stop < start, inc2 = reverse2 ? tickIncrement(stop, start, count3) : tickIncrement(start, stop, count3);
  return (reverse2 ? -1 : 1) * (inc2 < 0 ? 1 / -inc2 : inc2);
}

// node_modules/d3-array/src/nice.js
function nice(start, stop, count3) {
  let prestep;
  while (true) {
    const step = tickIncrement(start, stop, count3);
    if (step === prestep || step === 0 || !isFinite(step)) {
      return [start, stop];
    } else if (step > 0) {
      start = Math.floor(start / step) * step;
      stop = Math.ceil(stop / step) * step;
    } else if (step < 0) {
      start = Math.ceil(start * step) / step;
      stop = Math.floor(stop * step) / step;
    }
    prestep = step;
  }
}

// node_modules/d3-array/src/threshold/sturges.js
function thresholdSturges(values) {
  return Math.max(1, Math.ceil(Math.log(count(values)) / Math.LN2) + 1);
}

// node_modules/d3-array/src/bin.js
function bin() {
  var value = identity2, domain = extent, threshold2 = thresholdSturges;
  function histogram(data) {
    if (!Array.isArray(data)) data = Array.from(data);
    var i, n = data.length, x4, step, values = new Array(n);
    for (i = 0; i < n; ++i) {
      values[i] = value(data[i], i, data);
    }
    var xz = domain(values), x06 = xz[0], x12 = xz[1], tz = threshold2(values, x06, x12);
    if (!Array.isArray(tz)) {
      const max5 = x12, tn = +tz;
      if (domain === extent) [x06, x12] = nice(x06, x12, tn);
      tz = ticks(x06, x12, tn);
      if (tz[0] <= x06) step = tickIncrement(x06, x12, tn);
      if (tz[tz.length - 1] >= x12) {
        if (max5 >= x12 && domain === extent) {
          const step2 = tickIncrement(x06, x12, tn);
          if (isFinite(step2)) {
            if (step2 > 0) {
              x12 = (Math.floor(x12 / step2) + 1) * step2;
            } else if (step2 < 0) {
              x12 = (Math.ceil(x12 * -step2) + 1) / -step2;
            }
          }
        } else {
          tz.pop();
        }
      }
    }
    var m3 = tz.length, a4 = 0, b = m3;
    while (tz[a4] <= x06) ++a4;
    while (tz[b - 1] > x12) --b;
    if (a4 || b < m3) tz = tz.slice(a4, b), m3 = b - a4;
    var bins = new Array(m3 + 1), bin2;
    for (i = 0; i <= m3; ++i) {
      bin2 = bins[i] = [];
      bin2.x0 = i > 0 ? tz[i - 1] : x06;
      bin2.x1 = i < m3 ? tz[i] : x12;
    }
    if (isFinite(step)) {
      if (step > 0) {
        for (i = 0; i < n; ++i) {
          if ((x4 = values[i]) != null && x06 <= x4 && x4 <= x12) {
            bins[Math.min(m3, Math.floor((x4 - x06) / step))].push(data[i]);
          }
        }
      } else if (step < 0) {
        for (i = 0; i < n; ++i) {
          if ((x4 = values[i]) != null && x06 <= x4 && x4 <= x12) {
            const j = Math.floor((x06 - x4) * step);
            bins[Math.min(m3, j + (tz[j] <= x4))].push(data[i]);
          }
        }
      }
    } else {
      for (i = 0; i < n; ++i) {
        if ((x4 = values[i]) != null && x06 <= x4 && x4 <= x12) {
          bins[bisect_default(tz, x4, 0, m3)].push(data[i]);
        }
      }
    }
    return bins;
  }
  histogram.value = function(_) {
    return arguments.length ? (value = typeof _ === "function" ? _ : constant(_), histogram) : value;
  };
  histogram.domain = function(_) {
    return arguments.length ? (domain = typeof _ === "function" ? _ : constant([_[0], _[1]]), histogram) : domain;
  };
  histogram.thresholds = function(_) {
    return arguments.length ? (threshold2 = typeof _ === "function" ? _ : constant(Array.isArray(_) ? slice.call(_) : _), histogram) : threshold2;
  };
  return histogram;
}

// node_modules/d3-array/src/max.js
function max(values, valueof) {
  let max5;
  if (valueof === void 0) {
    for (const value of values) {
      if (value != null && (max5 < value || max5 === void 0 && value >= value)) {
        max5 = value;
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && (max5 < value || max5 === void 0 && value >= value)) {
        max5 = value;
      }
    }
  }
  return max5;
}

// node_modules/d3-array/src/maxIndex.js
function maxIndex(values, valueof) {
  let max5;
  let maxIndex2 = -1;
  let index3 = -1;
  if (valueof === void 0) {
    for (const value of values) {
      ++index3;
      if (value != null && (max5 < value || max5 === void 0 && value >= value)) {
        max5 = value, maxIndex2 = index3;
      }
    }
  } else {
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && (max5 < value || max5 === void 0 && value >= value)) {
        max5 = value, maxIndex2 = index3;
      }
    }
  }
  return maxIndex2;
}

// node_modules/d3-array/src/min.js
function min(values, valueof) {
  let min4;
  if (valueof === void 0) {
    for (const value of values) {
      if (value != null && (min4 > value || min4 === void 0 && value >= value)) {
        min4 = value;
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && (min4 > value || min4 === void 0 && value >= value)) {
        min4 = value;
      }
    }
  }
  return min4;
}

// node_modules/d3-array/src/minIndex.js
function minIndex(values, valueof) {
  let min4;
  let minIndex2 = -1;
  let index3 = -1;
  if (valueof === void 0) {
    for (const value of values) {
      ++index3;
      if (value != null && (min4 > value || min4 === void 0 && value >= value)) {
        min4 = value, minIndex2 = index3;
      }
    }
  } else {
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && (min4 > value || min4 === void 0 && value >= value)) {
        min4 = value, minIndex2 = index3;
      }
    }
  }
  return minIndex2;
}

// node_modules/d3-array/src/quickselect.js
function quickselect(array3, k2, left2 = 0, right2 = Infinity, compare) {
  k2 = Math.floor(k2);
  left2 = Math.floor(Math.max(0, left2));
  right2 = Math.floor(Math.min(array3.length - 1, right2));
  if (!(left2 <= k2 && k2 <= right2)) return array3;
  compare = compare === void 0 ? ascendingDefined : compareDefined(compare);
  while (right2 > left2) {
    if (right2 - left2 > 600) {
      const n = right2 - left2 + 1;
      const m3 = k2 - left2 + 1;
      const z = Math.log(n);
      const s2 = 0.5 * Math.exp(2 * z / 3);
      const sd = 0.5 * Math.sqrt(z * s2 * (n - s2) / n) * (m3 - n / 2 < 0 ? -1 : 1);
      const newLeft = Math.max(left2, Math.floor(k2 - m3 * s2 / n + sd));
      const newRight = Math.min(right2, Math.floor(k2 + (n - m3) * s2 / n + sd));
      quickselect(array3, k2, newLeft, newRight, compare);
    }
    const t = array3[k2];
    let i = left2;
    let j = right2;
    swap(array3, left2, k2);
    if (compare(array3[right2], t) > 0) swap(array3, left2, right2);
    while (i < j) {
      swap(array3, i, j), ++i, --j;
      while (compare(array3[i], t) < 0) ++i;
      while (compare(array3[j], t) > 0) --j;
    }
    if (compare(array3[left2], t) === 0) swap(array3, left2, j);
    else ++j, swap(array3, j, right2);
    if (j <= k2) left2 = j + 1;
    if (k2 <= j) right2 = j - 1;
  }
  return array3;
}
function swap(array3, i, j) {
  const t = array3[i];
  array3[i] = array3[j];
  array3[j] = t;
}

// node_modules/d3-array/src/greatest.js
function greatest(values, compare = ascending) {
  let max5;
  let defined = false;
  if (compare.length === 1) {
    let maxValue;
    for (const element of values) {
      const value = compare(element);
      if (defined ? ascending(value, maxValue) > 0 : ascending(value, value) === 0) {
        max5 = element;
        maxValue = value;
        defined = true;
      }
    }
  } else {
    for (const value of values) {
      if (defined ? compare(value, max5) > 0 : compare(value, value) === 0) {
        max5 = value;
        defined = true;
      }
    }
  }
  return max5;
}

// node_modules/d3-array/src/quantile.js
function quantile(values, p, valueof) {
  values = Float64Array.from(numbers(values, valueof));
  if (!(n = values.length) || isNaN(p = +p)) return;
  if (p <= 0 || n < 2) return min(values);
  if (p >= 1) return max(values);
  var n, i = (n - 1) * p, i0 = Math.floor(i), value0 = max(quickselect(values, i0).subarray(0, i0 + 1)), value1 = min(values.subarray(i0 + 1));
  return value0 + (value1 - value0) * (i - i0);
}
function quantileSorted(values, p, valueof = number) {
  if (!(n = values.length) || isNaN(p = +p)) return;
  if (p <= 0 || n < 2) return +valueof(values[0], 0, values);
  if (p >= 1) return +valueof(values[n - 1], n - 1, values);
  var n, i = (n - 1) * p, i0 = Math.floor(i), value0 = +valueof(values[i0], i0, values), value1 = +valueof(values[i0 + 1], i0 + 1, values);
  return value0 + (value1 - value0) * (i - i0);
}
function quantileIndex(values, p, valueof = number) {
  if (isNaN(p = +p)) return;
  numbers2 = Float64Array.from(values, (_, i2) => number(valueof(values[i2], i2, values)));
  if (p <= 0) return minIndex(numbers2);
  if (p >= 1) return maxIndex(numbers2);
  var numbers2, index3 = Uint32Array.from(values, (_, i2) => i2), j = numbers2.length - 1, i = Math.floor(j * p);
  quickselect(index3, i, 0, j, (i2, j2) => ascendingDefined(numbers2[i2], numbers2[j2]));
  i = greatest(index3.subarray(0, i + 1), (i2) => numbers2[i2]);
  return i >= 0 ? i : -1;
}

// node_modules/d3-array/src/threshold/freedmanDiaconis.js
function thresholdFreedmanDiaconis(values, min4, max5) {
  const c6 = count(values), d = quantile(values, 0.75) - quantile(values, 0.25);
  return c6 && d ? Math.ceil((max5 - min4) / (2 * d * Math.pow(c6, -1 / 3))) : 1;
}

// node_modules/d3-array/src/threshold/scott.js
function thresholdScott(values, min4, max5) {
  const c6 = count(values), d = deviation(values);
  return c6 && d ? Math.ceil((max5 - min4) * Math.cbrt(c6) / (3.49 * d)) : 1;
}

// node_modules/d3-array/src/mean.js
function mean(values, valueof) {
  let count3 = 0;
  let sum4 = 0;
  if (valueof === void 0) {
    for (let value of values) {
      if (value != null && (value = +value) >= value) {
        ++count3, sum4 += value;
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && (value = +value) >= value) {
        ++count3, sum4 += value;
      }
    }
  }
  if (count3) return sum4 / count3;
}

// node_modules/d3-array/src/median.js
function median(values, valueof) {
  return quantile(values, 0.5, valueof);
}
function medianIndex(values, valueof) {
  return quantileIndex(values, 0.5, valueof);
}

// node_modules/d3-array/src/merge.js
function* flatten2(arrays) {
  for (const array3 of arrays) {
    yield* array3;
  }
}
function merge(arrays) {
  return Array.from(flatten2(arrays));
}

// node_modules/d3-array/src/mode.js
function mode(values, valueof) {
  const counts = new InternMap();
  if (valueof === void 0) {
    for (let value of values) {
      if (value != null && value >= value) {
        counts.set(value, (counts.get(value) || 0) + 1);
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if ((value = valueof(value, ++index3, values)) != null && value >= value) {
        counts.set(value, (counts.get(value) || 0) + 1);
      }
    }
  }
  let modeValue;
  let modeCount = 0;
  for (const [value, count3] of counts) {
    if (count3 > modeCount) {
      modeCount = count3;
      modeValue = value;
    }
  }
  return modeValue;
}

// node_modules/d3-array/src/pairs.js
function pairs(values, pairof = pair) {
  const pairs2 = [];
  let previous;
  let first = false;
  for (const value of values) {
    if (first) pairs2.push(pairof(previous, value));
    previous = value;
    first = true;
  }
  return pairs2;
}
function pair(a4, b) {
  return [a4, b];
}

// node_modules/d3-array/src/range.js
function range(start, stop, step) {
  start = +start, stop = +stop, step = (n = arguments.length) < 2 ? (stop = start, start = 0, 1) : n < 3 ? 1 : +step;
  var i = -1, n = Math.max(0, Math.ceil((stop - start) / step)) | 0, range4 = new Array(n);
  while (++i < n) {
    range4[i] = start + i * step;
  }
  return range4;
}

// node_modules/d3-array/src/rank.js
function rank(values, valueof = ascending) {
  if (typeof values[Symbol.iterator] !== "function") throw new TypeError("values is not iterable");
  let V = Array.from(values);
  const R = new Float64Array(V.length);
  if (valueof.length !== 2) V = V.map(valueof), valueof = ascending;
  const compareIndex = (i, j) => valueof(V[i], V[j]);
  let k2, r;
  values = Uint32Array.from(V, (_, i) => i);
  values.sort(valueof === ascending ? (i, j) => ascendingDefined(V[i], V[j]) : compareDefined(compareIndex));
  values.forEach((j, i) => {
    const c6 = compareIndex(j, k2 === void 0 ? j : k2);
    if (c6 >= 0) {
      if (k2 === void 0 || c6 > 0) k2 = j, r = i;
      R[j] = r;
    } else {
      R[j] = NaN;
    }
  });
  return R;
}

// node_modules/d3-array/src/least.js
function least(values, compare = ascending) {
  let min4;
  let defined = false;
  if (compare.length === 1) {
    let minValue;
    for (const element of values) {
      const value = compare(element);
      if (defined ? ascending(value, minValue) < 0 : ascending(value, value) === 0) {
        min4 = element;
        minValue = value;
        defined = true;
      }
    }
  } else {
    for (const value of values) {
      if (defined ? compare(value, min4) < 0 : compare(value, value) === 0) {
        min4 = value;
        defined = true;
      }
    }
  }
  return min4;
}

// node_modules/d3-array/src/leastIndex.js
function leastIndex(values, compare = ascending) {
  if (compare.length === 1) return minIndex(values, compare);
  let minValue;
  let min4 = -1;
  let index3 = -1;
  for (const value of values) {
    ++index3;
    if (min4 < 0 ? compare(value, value) === 0 : compare(value, minValue) < 0) {
      minValue = value;
      min4 = index3;
    }
  }
  return min4;
}

// node_modules/d3-array/src/greatestIndex.js
function greatestIndex(values, compare = ascending) {
  if (compare.length === 1) return maxIndex(values, compare);
  let maxValue;
  let max5 = -1;
  let index3 = -1;
  for (const value of values) {
    ++index3;
    if (max5 < 0 ? compare(value, value) === 0 : compare(value, maxValue) > 0) {
      maxValue = value;
      max5 = index3;
    }
  }
  return max5;
}

// node_modules/d3-array/src/scan.js
function scan(values, compare) {
  const index3 = leastIndex(values, compare);
  return index3 < 0 ? void 0 : index3;
}

// node_modules/d3-array/src/shuffle.js
var shuffle_default = shuffler(Math.random);
function shuffler(random) {
  return function shuffle2(array3, i0 = 0, i1 = array3.length) {
    let m3 = i1 - (i0 = +i0);
    while (m3) {
      const i = random() * m3-- | 0, t = array3[m3 + i0];
      array3[m3 + i0] = array3[i + i0];
      array3[i + i0] = t;
    }
    return array3;
  };
}

// node_modules/d3-array/src/sum.js
function sum(values, valueof) {
  let sum4 = 0;
  if (valueof === void 0) {
    for (let value of values) {
      if (value = +value) {
        sum4 += value;
      }
    }
  } else {
    let index3 = -1;
    for (let value of values) {
      if (value = +valueof(value, ++index3, values)) {
        sum4 += value;
      }
    }
  }
  return sum4;
}

// node_modules/d3-array/src/transpose.js
function transpose(matrix) {
  if (!(n = matrix.length)) return [];
  for (var i = -1, m3 = min(matrix, length2), transpose2 = new Array(m3); ++i < m3; ) {
    for (var j = -1, n, row = transpose2[i] = new Array(n); ++j < n; ) {
      row[j] = matrix[j][i];
    }
  }
  return transpose2;
}
function length2(d) {
  return d.length;
}

// node_modules/d3-array/src/zip.js
function zip() {
  return transpose(arguments);
}

// node_modules/d3-array/src/every.js
function every(values, test) {
  if (typeof test !== "function") throw new TypeError("test is not a function");
  let index3 = -1;
  for (const value of values) {
    if (!test(value, ++index3, values)) {
      return false;
    }
  }
  return true;
}

// node_modules/d3-array/src/some.js
function some(values, test) {
  if (typeof test !== "function") throw new TypeError("test is not a function");
  let index3 = -1;
  for (const value of values) {
    if (test(value, ++index3, values)) {
      return true;
    }
  }
  return false;
}

// node_modules/d3-array/src/filter.js
function filter(values, test) {
  if (typeof test !== "function") throw new TypeError("test is not a function");
  const array3 = [];
  let index3 = -1;
  for (const value of values) {
    if (test(value, ++index3, values)) {
      array3.push(value);
    }
  }
  return array3;
}

// node_modules/d3-array/src/map.js
function map2(values, mapper) {
  if (typeof values[Symbol.iterator] !== "function") throw new TypeError("values is not iterable");
  if (typeof mapper !== "function") throw new TypeError("mapper is not a function");
  return Array.from(values, (value, index3) => mapper(value, index3, values));
}

// node_modules/d3-array/src/reduce.js
function reduce(values, reducer2, value) {
  if (typeof reducer2 !== "function") throw new TypeError("reducer is not a function");
  const iterator = values[Symbol.iterator]();
  let done, next, index3 = -1;
  if (arguments.length < 3) {
    ({ done, value } = iterator.next());
    if (done) return;
    ++index3;
  }
  while ({ done, value: next } = iterator.next(), !done) {
    value = reducer2(value, next, ++index3, values);
  }
  return value;
}

// node_modules/d3-array/src/reverse.js
function reverse(values) {
  if (typeof values[Symbol.iterator] !== "function") throw new TypeError("values is not iterable");
  return Array.from(values).reverse();
}

// node_modules/d3-array/src/difference.js
function difference(values, ...others) {
  values = new InternSet(values);
  for (const other of others) {
    for (const value of other) {
      values.delete(value);
    }
  }
  return values;
}

// node_modules/d3-array/src/disjoint.js
function disjoint(values, other) {
  const iterator = other[Symbol.iterator](), set2 = new InternSet();
  for (const v2 of values) {
    if (set2.has(v2)) return false;
    let value, done;
    while ({ value, done } = iterator.next()) {
      if (done) break;
      if (Object.is(v2, value)) return false;
      set2.add(value);
    }
  }
  return true;
}

// node_modules/d3-array/src/intersection.js
function intersection(values, ...others) {
  values = new InternSet(values);
  others = others.map(set);
  out: for (const value of values) {
    for (const other of others) {
      if (!other.has(value)) {
        values.delete(value);
        continue out;
      }
    }
  }
  return values;
}
function set(values) {
  return values instanceof InternSet ? values : new InternSet(values);
}

// node_modules/d3-array/src/superset.js
function superset(values, other) {
  const iterator = values[Symbol.iterator](), set2 = /* @__PURE__ */ new Set();
  for (const o of other) {
    const io = intern(o);
    if (set2.has(io)) continue;
    let value, done;
    while ({ value, done } = iterator.next()) {
      if (done) return false;
      const ivalue = intern(value);
      set2.add(ivalue);
      if (Object.is(io, ivalue)) break;
    }
  }
  return true;
}
function intern(value) {
  return value !== null && typeof value === "object" ? value.valueOf() : value;
}

// node_modules/d3-array/src/subset.js
function subset(values, other) {
  return superset(other, values);
}

// node_modules/d3-array/src/union.js
function union(...others) {
  const set2 = new InternSet();
  for (const other of others) {
    for (const o of other) {
      set2.add(o);
    }
  }
  return set2;
}

// node_modules/d3-axis/src/identity.js
function identity_default(x4) {
  return x4;
}

// node_modules/d3-axis/src/axis.js
var top = 1;
var right = 2;
var bottom = 3;
var left = 4;
var epsilon = 1e-6;
function translateX(x4) {
  return "translate(" + x4 + ",0)";
}
function translateY(y4) {
  return "translate(0," + y4 + ")";
}
function number2(scale2) {
  return (d) => +scale2(d);
}
function center(scale2, offset) {
  offset = Math.max(0, scale2.bandwidth() - offset * 2) / 2;
  if (scale2.round()) offset = Math.round(offset);
  return (d) => +scale2(d) + offset;
}
function entering() {
  return !this.__axis;
}
function axis(orient, scale2) {
  var tickArguments = [], tickValues = null, tickFormat2 = null, tickSizeInner = 6, tickSizeOuter = 6, tickPadding = 3, offset = typeof window !== "undefined" && window.devicePixelRatio > 1 ? 0 : 0.5, k2 = orient === top || orient === left ? -1 : 1, x4 = orient === left || orient === right ? "x" : "y", transform2 = orient === top || orient === bottom ? translateX : translateY;
  function axis2(context) {
    var values = tickValues == null ? scale2.ticks ? scale2.ticks.apply(scale2, tickArguments) : scale2.domain() : tickValues, format2 = tickFormat2 == null ? scale2.tickFormat ? scale2.tickFormat.apply(scale2, tickArguments) : identity_default : tickFormat2, spacing = Math.max(tickSizeInner, 0) + tickPadding, range4 = scale2.range(), range0 = +range4[0] + offset, range1 = +range4[range4.length - 1] + offset, position = (scale2.bandwidth ? center : number2)(scale2.copy(), offset), selection = context.selection ? context.selection() : context, path2 = selection.selectAll(".domain").data([null]), tick = selection.selectAll(".tick").data(values, scale2).order(), tickExit = tick.exit(), tickEnter = tick.enter().append("g").attr("class", "tick"), line = tick.select("line"), text = tick.select("text");
    path2 = path2.merge(path2.enter().insert("path", ".tick").attr("class", "domain").attr("stroke", "currentColor"));
    tick = tick.merge(tickEnter);
    line = line.merge(tickEnter.append("line").attr("stroke", "currentColor").attr(x4 + "2", k2 * tickSizeInner));
    text = text.merge(tickEnter.append("text").attr("fill", "currentColor").attr(x4, k2 * spacing).attr("dy", orient === top ? "0em" : orient === bottom ? "0.71em" : "0.32em"));
    if (context !== selection) {
      path2 = path2.transition(context);
      tick = tick.transition(context);
      line = line.transition(context);
      text = text.transition(context);
      tickExit = tickExit.transition(context).attr("opacity", epsilon).attr("transform", function(d) {
        return isFinite(d = position(d)) ? transform2(d + offset) : this.getAttribute("transform");
      });
      tickEnter.attr("opacity", epsilon).attr("transform", function(d) {
        var p = this.parentNode.__axis;
        return transform2((p && isFinite(p = p(d)) ? p : position(d)) + offset);
      });
    }
    tickExit.remove();
    path2.attr("d", orient === left || orient === right ? tickSizeOuter ? "M" + k2 * tickSizeOuter + "," + range0 + "H" + offset + "V" + range1 + "H" + k2 * tickSizeOuter : "M" + offset + "," + range0 + "V" + range1 : tickSizeOuter ? "M" + range0 + "," + k2 * tickSizeOuter + "V" + offset + "H" + range1 + "V" + k2 * tickSizeOuter : "M" + range0 + "," + offset + "H" + range1);
    tick.attr("opacity", 1).attr("transform", function(d) {
      return transform2(position(d) + offset);
    });
    line.attr(x4 + "2", k2 * tickSizeInner);
    text.attr(x4, k2 * spacing).text(format2);
    selection.filter(entering).attr("fill", "none").attr("font-size", 10).attr("font-family", "sans-serif").attr("text-anchor", orient === right ? "start" : orient === left ? "end" : "middle");
    selection.each(function() {
      this.__axis = position;
    });
  }
  axis2.scale = function(_) {
    return arguments.length ? (scale2 = _, axis2) : scale2;
  };
  axis2.ticks = function() {
    return tickArguments = Array.from(arguments), axis2;
  };
  axis2.tickArguments = function(_) {
    return arguments.length ? (tickArguments = _ == null ? [] : Array.from(_), axis2) : tickArguments.slice();
  };
  axis2.tickValues = function(_) {
    return arguments.length ? (tickValues = _ == null ? null : Array.from(_), axis2) : tickValues && tickValues.slice();
  };
  axis2.tickFormat = function(_) {
    return arguments.length ? (tickFormat2 = _, axis2) : tickFormat2;
  };
  axis2.tickSize = function(_) {
    return arguments.length ? (tickSizeInner = tickSizeOuter = +_, axis2) : tickSizeInner;
  };
  axis2.tickSizeInner = function(_) {
    return arguments.length ? (tickSizeInner = +_, axis2) : tickSizeInner;
  };
  axis2.tickSizeOuter = function(_) {
    return arguments.length ? (tickSizeOuter = +_, axis2) : tickSizeOuter;
  };
  axis2.tickPadding = function(_) {
    return arguments.length ? (tickPadding = +_, axis2) : tickPadding;
  };
  axis2.offset = function(_) {
    return arguments.length ? (offset = +_, axis2) : offset;
  };
  return axis2;
}
function axisTop(scale2) {
  return axis(top, scale2);
}
function axisRight(scale2) {
  return axis(right, scale2);
}
function axisBottom(scale2) {
  return axis(bottom, scale2);
}
function axisLeft(scale2) {
  return axis(left, scale2);
}

// node_modules/d3-brush/src/constant.js
var constant_default = (x4) => () => x4;

// node_modules/d3-brush/src/event.js
function BrushEvent(type2, {
  sourceEvent,
  target,
  selection,
  mode: mode2,
  dispatch
}) {
  Object.defineProperties(this, {
    type: { value: type2, enumerable: true, configurable: true },
    sourceEvent: { value: sourceEvent, enumerable: true, configurable: true },
    target: { value: target, enumerable: true, configurable: true },
    selection: { value: selection, enumerable: true, configurable: true },
    mode: { value: mode2, enumerable: true, configurable: true },
    _: { value: dispatch }
  });
}

// node_modules/d3-brush/src/noevent.js
function nopropagation(event) {
  event.stopImmediatePropagation();
}
function noevent_default(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
}

// node_modules/d3-brush/src/brush.js
var MODE_DRAG = { name: "drag" };
var MODE_SPACE = { name: "space" };
var MODE_HANDLE = { name: "handle" };
var MODE_CENTER = { name: "center" };
var { abs, max: max2, min: min2 } = Math;
function number1(e) {
  return [+e[0], +e[1]];
}
function number22(e) {
  return [number1(e[0]), number1(e[1])];
}
var X = {
  name: "x",
  handles: ["w", "e"].map(type),
  input: function(x4, e) {
    return x4 == null ? null : [[+x4[0], e[0][1]], [+x4[1], e[1][1]]];
  },
  output: function(xy) {
    return xy && [xy[0][0], xy[1][0]];
  }
};
var Y = {
  name: "y",
  handles: ["n", "s"].map(type),
  input: function(y4, e) {
    return y4 == null ? null : [[e[0][0], +y4[0]], [e[1][0], +y4[1]]];
  },
  output: function(xy) {
    return xy && [xy[0][1], xy[1][1]];
  }
};
var XY = {
  name: "xy",
  handles: ["n", "w", "e", "s", "nw", "ne", "sw", "se"].map(type),
  input: function(xy) {
    return xy == null ? null : number22(xy);
  },
  output: function(xy) {
    return xy;
  }
};
var cursors = {
  overlay: "crosshair",
  selection: "move",
  n: "ns-resize",
  e: "ew-resize",
  s: "ns-resize",
  w: "ew-resize",
  nw: "nwse-resize",
  ne: "nesw-resize",
  se: "nwse-resize",
  sw: "nesw-resize"
};
var flipX = {
  e: "w",
  w: "e",
  nw: "ne",
  ne: "nw",
  se: "sw",
  sw: "se"
};
var flipY = {
  n: "s",
  s: "n",
  nw: "sw",
  ne: "se",
  se: "ne",
  sw: "nw"
};
var signsX = {
  overlay: 1,
  selection: 1,
  n: null,
  e: 1,
  s: null,
  w: -1,
  nw: -1,
  ne: 1,
  se: 1,
  sw: -1
};
var signsY = {
  overlay: 1,
  selection: 1,
  n: -1,
  e: null,
  s: 1,
  w: null,
  nw: -1,
  ne: -1,
  se: 1,
  sw: 1
};
function type(t) {
  return { type: t };
}
function defaultFilter(event) {
  return !event.ctrlKey && !event.button;
}
function defaultExtent() {
  var svg2 = this.ownerSVGElement || this;
  if (svg2.hasAttribute("viewBox")) {
    svg2 = svg2.viewBox.baseVal;
    return [[svg2.x, svg2.y], [svg2.x + svg2.width, svg2.y + svg2.height]];
  }
  return [[0, 0], [svg2.width.baseVal.value, svg2.height.baseVal.value]];
}
function defaultTouchable() {
  return navigator.maxTouchPoints || "ontouchstart" in this;
}
function local2(node) {
  while (!node.__brush) if (!(node = node.parentNode)) return;
  return node.__brush;
}
function empty2(extent2) {
  return extent2[0][0] === extent2[1][0] || extent2[0][1] === extent2[1][1];
}
function brushSelection(node) {
  var state = node.__brush;
  return state ? state.dim.output(state.selection) : null;
}
function brushX() {
  return brush(X);
}
function brushY() {
  return brush(Y);
}
function brush_default() {
  return brush(XY);
}
function brush(dim) {
  var extent2 = defaultExtent, filter2 = defaultFilter, touchable = defaultTouchable, keys = true, listeners = dispatch_default("start", "brush", "end"), handleSize = 6, touchending;
  function brush2(group2) {
    var overlay = group2.property("__brush", initialize).selectAll(".overlay").data([type("overlay")]);
    overlay.enter().append("rect").attr("class", "overlay").attr("pointer-events", "all").attr("cursor", cursors.overlay).merge(overlay).each(function() {
      var extent3 = local2(this).extent;
      select_default(this).attr("x", extent3[0][0]).attr("y", extent3[0][1]).attr("width", extent3[1][0] - extent3[0][0]).attr("height", extent3[1][1] - extent3[0][1]);
    });
    group2.selectAll(".selection").data([type("selection")]).enter().append("rect").attr("class", "selection").attr("cursor", cursors.selection).attr("fill", "#777").attr("fill-opacity", 0.3).attr("stroke", "#fff").attr("shape-rendering", "crispEdges");
    var handle = group2.selectAll(".handle").data(dim.handles, function(d) {
      return d.type;
    });
    handle.exit().remove();
    handle.enter().append("rect").attr("class", function(d) {
      return "handle handle--" + d.type;
    }).attr("cursor", function(d) {
      return cursors[d.type];
    });
    group2.each(redraw).attr("fill", "none").attr("pointer-events", "all").on("mousedown.brush", started).filter(touchable).on("touchstart.brush", started).on("touchmove.brush", touchmoved).on("touchend.brush touchcancel.brush", touchended).style("touch-action", "none").style("-webkit-tap-highlight-color", "rgba(0,0,0,0)");
  }
  brush2.move = function(group2, selection, event) {
    if (group2.tween) {
      group2.on("start.brush", function(event2) {
        emitter(this, arguments).beforestart().start(event2);
      }).on("interrupt.brush end.brush", function(event2) {
        emitter(this, arguments).end(event2);
      }).tween("brush", function() {
        var that = this, state = that.__brush, emit = emitter(that, arguments), selection0 = state.selection, selection1 = dim.input(typeof selection === "function" ? selection.apply(this, arguments) : selection, state.extent), i = value_default(selection0, selection1);
        function tween(t) {
          state.selection = t === 1 && selection1 === null ? null : i(t);
          redraw.call(that);
          emit.brush();
        }
        return selection0 !== null && selection1 !== null ? tween : tween(1);
      });
    } else {
      group2.each(function() {
        var that = this, args = arguments, state = that.__brush, selection1 = dim.input(typeof selection === "function" ? selection.apply(that, args) : selection, state.extent), emit = emitter(that, args).beforestart();
        interrupt_default(that);
        state.selection = selection1 === null ? null : selection1;
        redraw.call(that);
        emit.start(event).brush(event).end(event);
      });
    }
  };
  brush2.clear = function(group2, event) {
    brush2.move(group2, null, event);
  };
  function redraw() {
    var group2 = select_default(this), selection = local2(this).selection;
    if (selection) {
      group2.selectAll(".selection").style("display", null).attr("x", selection[0][0]).attr("y", selection[0][1]).attr("width", selection[1][0] - selection[0][0]).attr("height", selection[1][1] - selection[0][1]);
      group2.selectAll(".handle").style("display", null).attr("x", function(d) {
        return d.type[d.type.length - 1] === "e" ? selection[1][0] - handleSize / 2 : selection[0][0] - handleSize / 2;
      }).attr("y", function(d) {
        return d.type[0] === "s" ? selection[1][1] - handleSize / 2 : selection[0][1] - handleSize / 2;
      }).attr("width", function(d) {
        return d.type === "n" || d.type === "s" ? selection[1][0] - selection[0][0] + handleSize : handleSize;
      }).attr("height", function(d) {
        return d.type === "e" || d.type === "w" ? selection[1][1] - selection[0][1] + handleSize : handleSize;
      });
    } else {
      group2.selectAll(".selection,.handle").style("display", "none").attr("x", null).attr("y", null).attr("width", null).attr("height", null);
    }
  }
  function emitter(that, args, clean) {
    var emit = that.__brush.emitter;
    return emit && (!clean || !emit.clean) ? emit : new Emitter(that, args, clean);
  }
  function Emitter(that, args, clean) {
    this.that = that;
    this.args = args;
    this.state = that.__brush;
    this.active = 0;
    this.clean = clean;
  }
  Emitter.prototype = {
    beforestart: function() {
      if (++this.active === 1) this.state.emitter = this, this.starting = true;
      return this;
    },
    start: function(event, mode2) {
      if (this.starting) this.starting = false, this.emit("start", event, mode2);
      else this.emit("brush", event);
      return this;
    },
    brush: function(event, mode2) {
      this.emit("brush", event, mode2);
      return this;
    },
    end: function(event, mode2) {
      if (--this.active === 0) delete this.state.emitter, this.emit("end", event, mode2);
      return this;
    },
    emit: function(type2, event, mode2) {
      var d = select_default(this.that).datum();
      listeners.call(
        type2,
        this.that,
        new BrushEvent(type2, {
          sourceEvent: event,
          target: brush2,
          selection: dim.output(this.state.selection),
          mode: mode2,
          dispatch: listeners
        }),
        d
      );
    }
  };
  function started(event) {
    if (touchending && !event.touches) return;
    if (!filter2.apply(this, arguments)) return;
    var that = this, type2 = event.target.__data__.type, mode2 = (keys && event.metaKey ? type2 = "overlay" : type2) === "selection" ? MODE_DRAG : keys && event.altKey ? MODE_CENTER : MODE_HANDLE, signX = dim === Y ? null : signsX[type2], signY = dim === X ? null : signsY[type2], state = local2(that), extent3 = state.extent, selection = state.selection, W = extent3[0][0], w0, w1, N = extent3[0][1], n0, n1, E = extent3[1][0], e0, e1, S = extent3[1][1], s0, s1, dx = 0, dy = 0, moving, shifting = signX && signY && keys && event.shiftKey, lockX, lockY, points = Array.from(event.touches || [event], (t) => {
      const i = t.identifier;
      t = pointer_default(t, that);
      t.point0 = t.slice();
      t.identifier = i;
      return t;
    });
    interrupt_default(that);
    var emit = emitter(that, arguments, true).beforestart();
    if (type2 === "overlay") {
      if (selection) moving = true;
      const pts = [points[0], points[1] || points[0]];
      state.selection = selection = [[
        w0 = dim === Y ? W : min2(pts[0][0], pts[1][0]),
        n0 = dim === X ? N : min2(pts[0][1], pts[1][1])
      ], [
        e0 = dim === Y ? E : max2(pts[0][0], pts[1][0]),
        s0 = dim === X ? S : max2(pts[0][1], pts[1][1])
      ]];
      if (points.length > 1) move(event);
    } else {
      w0 = selection[0][0];
      n0 = selection[0][1];
      e0 = selection[1][0];
      s0 = selection[1][1];
    }
    w1 = w0;
    n1 = n0;
    e1 = e0;
    s1 = s0;
    var group2 = select_default(that).attr("pointer-events", "none");
    var overlay = group2.selectAll(".overlay").attr("cursor", cursors[type2]);
    if (event.touches) {
      emit.moved = moved;
      emit.ended = ended;
    } else {
      var view = select_default(event.view).on("mousemove.brush", moved, true).on("mouseup.brush", ended, true);
      if (keys) view.on("keydown.brush", keydowned, true).on("keyup.brush", keyupped, true);
      nodrag_default(event.view);
    }
    redraw.call(that);
    emit.start(event, mode2.name);
    function moved(event2) {
      for (const p of event2.changedTouches || [event2]) {
        for (const d of points)
          if (d.identifier === p.identifier) d.cur = pointer_default(p, that);
      }
      if (shifting && !lockX && !lockY && points.length === 1) {
        const point6 = points[0];
        if (abs(point6.cur[0] - point6[0]) > abs(point6.cur[1] - point6[1]))
          lockY = true;
        else
          lockX = true;
      }
      for (const point6 of points)
        if (point6.cur) point6[0] = point6.cur[0], point6[1] = point6.cur[1];
      moving = true;
      noevent_default(event2);
      move(event2);
    }
    function move(event2) {
      const point6 = points[0], point0 = point6.point0;
      var t;
      dx = point6[0] - point0[0];
      dy = point6[1] - point0[1];
      switch (mode2) {
        case MODE_SPACE:
        case MODE_DRAG: {
          if (signX) dx = max2(W - w0, min2(E - e0, dx)), w1 = w0 + dx, e1 = e0 + dx;
          if (signY) dy = max2(N - n0, min2(S - s0, dy)), n1 = n0 + dy, s1 = s0 + dy;
          break;
        }
        case MODE_HANDLE: {
          if (points[1]) {
            if (signX) w1 = max2(W, min2(E, points[0][0])), e1 = max2(W, min2(E, points[1][0])), signX = 1;
            if (signY) n1 = max2(N, min2(S, points[0][1])), s1 = max2(N, min2(S, points[1][1])), signY = 1;
          } else {
            if (signX < 0) dx = max2(W - w0, min2(E - w0, dx)), w1 = w0 + dx, e1 = e0;
            else if (signX > 0) dx = max2(W - e0, min2(E - e0, dx)), w1 = w0, e1 = e0 + dx;
            if (signY < 0) dy = max2(N - n0, min2(S - n0, dy)), n1 = n0 + dy, s1 = s0;
            else if (signY > 0) dy = max2(N - s0, min2(S - s0, dy)), n1 = n0, s1 = s0 + dy;
          }
          break;
        }
        case MODE_CENTER: {
          if (signX) w1 = max2(W, min2(E, w0 - dx * signX)), e1 = max2(W, min2(E, e0 + dx * signX));
          if (signY) n1 = max2(N, min2(S, n0 - dy * signY)), s1 = max2(N, min2(S, s0 + dy * signY));
          break;
        }
      }
      if (e1 < w1) {
        signX *= -1;
        t = w0, w0 = e0, e0 = t;
        t = w1, w1 = e1, e1 = t;
        if (type2 in flipX) overlay.attr("cursor", cursors[type2 = flipX[type2]]);
      }
      if (s1 < n1) {
        signY *= -1;
        t = n0, n0 = s0, s0 = t;
        t = n1, n1 = s1, s1 = t;
        if (type2 in flipY) overlay.attr("cursor", cursors[type2 = flipY[type2]]);
      }
      if (state.selection) selection = state.selection;
      if (lockX) w1 = selection[0][0], e1 = selection[1][0];
      if (lockY) n1 = selection[0][1], s1 = selection[1][1];
      if (selection[0][0] !== w1 || selection[0][1] !== n1 || selection[1][0] !== e1 || selection[1][1] !== s1) {
        state.selection = [[w1, n1], [e1, s1]];
        redraw.call(that);
        emit.brush(event2, mode2.name);
      }
    }
    function ended(event2) {
      nopropagation(event2);
      if (event2.touches) {
        if (event2.touches.length) return;
        if (touchending) clearTimeout(touchending);
        touchending = setTimeout(function() {
          touchending = null;
        }, 500);
      } else {
        yesdrag(event2.view, moving);
        view.on("keydown.brush keyup.brush mousemove.brush mouseup.brush", null);
      }
      group2.attr("pointer-events", "all");
      overlay.attr("cursor", cursors.overlay);
      if (state.selection) selection = state.selection;
      if (empty2(selection)) state.selection = null, redraw.call(that);
      emit.end(event2, mode2.name);
    }
    function keydowned(event2) {
      switch (event2.keyCode) {
        case 16: {
          shifting = signX && signY;
          break;
        }
        case 18: {
          if (mode2 === MODE_HANDLE) {
            if (signX) e0 = e1 - dx * signX, w0 = w1 + dx * signX;
            if (signY) s0 = s1 - dy * signY, n0 = n1 + dy * signY;
            mode2 = MODE_CENTER;
            move(event2);
          }
          break;
        }
        case 32: {
          if (mode2 === MODE_HANDLE || mode2 === MODE_CENTER) {
            if (signX < 0) e0 = e1 - dx;
            else if (signX > 0) w0 = w1 - dx;
            if (signY < 0) s0 = s1 - dy;
            else if (signY > 0) n0 = n1 - dy;
            mode2 = MODE_SPACE;
            overlay.attr("cursor", cursors.selection);
            move(event2);
          }
          break;
        }
        default:
          return;
      }
      noevent_default(event2);
    }
    function keyupped(event2) {
      switch (event2.keyCode) {
        case 16: {
          if (shifting) {
            lockX = lockY = shifting = false;
            move(event2);
          }
          break;
        }
        case 18: {
          if (mode2 === MODE_CENTER) {
            if (signX < 0) e0 = e1;
            else if (signX > 0) w0 = w1;
            if (signY < 0) s0 = s1;
            else if (signY > 0) n0 = n1;
            mode2 = MODE_HANDLE;
            move(event2);
          }
          break;
        }
        case 32: {
          if (mode2 === MODE_SPACE) {
            if (event2.altKey) {
              if (signX) e0 = e1 - dx * signX, w0 = w1 + dx * signX;
              if (signY) s0 = s1 - dy * signY, n0 = n1 + dy * signY;
              mode2 = MODE_CENTER;
            } else {
              if (signX < 0) e0 = e1;
              else if (signX > 0) w0 = w1;
              if (signY < 0) s0 = s1;
              else if (signY > 0) n0 = n1;
              mode2 = MODE_HANDLE;
            }
            overlay.attr("cursor", cursors[type2]);
            move(event2);
          }
          break;
        }
        default:
          return;
      }
      noevent_default(event2);
    }
  }
  function touchmoved(event) {
    emitter(this, arguments).moved(event);
  }
  function touchended(event) {
    emitter(this, arguments).ended(event);
  }
  function initialize() {
    var state = this.__brush || { selection: null };
    state.extent = number22(extent2.apply(this, arguments));
    state.dim = dim;
    return state;
  }
  brush2.extent = function(_) {
    return arguments.length ? (extent2 = typeof _ === "function" ? _ : constant_default(number22(_)), brush2) : extent2;
  };
  brush2.filter = function(_) {
    return arguments.length ? (filter2 = typeof _ === "function" ? _ : constant_default(!!_), brush2) : filter2;
  };
  brush2.touchable = function(_) {
    return arguments.length ? (touchable = typeof _ === "function" ? _ : constant_default(!!_), brush2) : touchable;
  };
  brush2.handleSize = function(_) {
    return arguments.length ? (handleSize = +_, brush2) : handleSize;
  };
  brush2.keyModifiers = function(_) {
    return arguments.length ? (keys = !!_, brush2) : keys;
  };
  brush2.on = function() {
    var value = listeners.on.apply(listeners, arguments);
    return value === listeners ? brush2 : value;
  };
  return brush2;
}

// node_modules/d3-chord/src/math.js
var abs2 = Math.abs;
var cos = Math.cos;
var sin = Math.sin;
var pi = Math.PI;
var halfPi = pi / 2;
var tau = pi * 2;
var max3 = Math.max;
var epsilon2 = 1e-12;

// node_modules/d3-chord/src/chord.js
function range2(i, j) {
  return Array.from({ length: j - i }, (_, k2) => i + k2);
}
function compareValue(compare) {
  return function(a4, b) {
    return compare(
      a4.source.value + a4.target.value,
      b.source.value + b.target.value
    );
  };
}
function chord_default() {
  return chord(false, false);
}
function chordTranspose() {
  return chord(false, true);
}
function chordDirected() {
  return chord(true, false);
}
function chord(directed, transpose2) {
  var padAngle = 0, sortGroups = null, sortSubgroups = null, sortChords = null;
  function chord2(matrix) {
    var n = matrix.length, groupSums = new Array(n), groupIndex = range2(0, n), chords = new Array(n * n), groups2 = new Array(n), k2 = 0, dx;
    matrix = Float64Array.from({ length: n * n }, transpose2 ? (_, i) => matrix[i % n][i / n | 0] : (_, i) => matrix[i / n | 0][i % n]);
    for (let i = 0; i < n; ++i) {
      let x4 = 0;
      for (let j = 0; j < n; ++j) x4 += matrix[i * n + j] + directed * matrix[j * n + i];
      k2 += groupSums[i] = x4;
    }
    k2 = max3(0, tau - padAngle * n) / k2;
    dx = k2 ? padAngle : tau / n;
    {
      let x4 = 0;
      if (sortGroups) groupIndex.sort((a4, b) => sortGroups(groupSums[a4], groupSums[b]));
      for (const i of groupIndex) {
        const x06 = x4;
        if (directed) {
          const subgroupIndex = range2(~n + 1, n).filter((j) => j < 0 ? matrix[~j * n + i] : matrix[i * n + j]);
          if (sortSubgroups) subgroupIndex.sort((a4, b) => sortSubgroups(a4 < 0 ? -matrix[~a4 * n + i] : matrix[i * n + a4], b < 0 ? -matrix[~b * n + i] : matrix[i * n + b]));
          for (const j of subgroupIndex) {
            if (j < 0) {
              const chord3 = chords[~j * n + i] || (chords[~j * n + i] = { source: null, target: null });
              chord3.target = { index: i, startAngle: x4, endAngle: x4 += matrix[~j * n + i] * k2, value: matrix[~j * n + i] };
            } else {
              const chord3 = chords[i * n + j] || (chords[i * n + j] = { source: null, target: null });
              chord3.source = { index: i, startAngle: x4, endAngle: x4 += matrix[i * n + j] * k2, value: matrix[i * n + j] };
            }
          }
          groups2[i] = { index: i, startAngle: x06, endAngle: x4, value: groupSums[i] };
        } else {
          const subgroupIndex = range2(0, n).filter((j) => matrix[i * n + j] || matrix[j * n + i]);
          if (sortSubgroups) subgroupIndex.sort((a4, b) => sortSubgroups(matrix[i * n + a4], matrix[i * n + b]));
          for (const j of subgroupIndex) {
            let chord3;
            if (i < j) {
              chord3 = chords[i * n + j] || (chords[i * n + j] = { source: null, target: null });
              chord3.source = { index: i, startAngle: x4, endAngle: x4 += matrix[i * n + j] * k2, value: matrix[i * n + j] };
            } else {
              chord3 = chords[j * n + i] || (chords[j * n + i] = { source: null, target: null });
              chord3.target = { index: i, startAngle: x4, endAngle: x4 += matrix[i * n + j] * k2, value: matrix[i * n + j] };
              if (i === j) chord3.source = chord3.target;
            }
            if (chord3.source && chord3.target && chord3.source.value < chord3.target.value) {
              const source = chord3.source;
              chord3.source = chord3.target;
              chord3.target = source;
            }
          }
          groups2[i] = { index: i, startAngle: x06, endAngle: x4, value: groupSums[i] };
        }
        x4 += dx;
      }
    }
    chords = Object.values(chords);
    chords.groups = groups2;
    return sortChords ? chords.sort(sortChords) : chords;
  }
  chord2.padAngle = function(_) {
    return arguments.length ? (padAngle = max3(0, _), chord2) : padAngle;
  };
  chord2.sortGroups = function(_) {
    return arguments.length ? (sortGroups = _, chord2) : sortGroups;
  };
  chord2.sortSubgroups = function(_) {
    return arguments.length ? (sortSubgroups = _, chord2) : sortSubgroups;
  };
  chord2.sortChords = function(_) {
    return arguments.length ? (_ == null ? sortChords = null : (sortChords = compareValue(_))._ = _, chord2) : sortChords && sortChords._;
  };
  return chord2;
}

// node_modules/d3-path/src/path.js
var pi2 = Math.PI;
var tau2 = 2 * pi2;
var epsilon3 = 1e-6;
var tauEpsilon = tau2 - epsilon3;
function append(strings) {
  this._ += strings[0];
  for (let i = 1, n = strings.length; i < n; ++i) {
    this._ += arguments[i] + strings[i];
  }
}
function appendRound(digits) {
  let d = Math.floor(digits);
  if (!(d >= 0)) throw new Error(`invalid digits: ${digits}`);
  if (d > 15) return append;
  const k2 = 10 ** d;
  return function(strings) {
    this._ += strings[0];
    for (let i = 1, n = strings.length; i < n; ++i) {
      this._ += Math.round(arguments[i] * k2) / k2 + strings[i];
    }
  };
}
var Path = class {
  constructor(digits) {
    this._x0 = this._y0 = // start of current subpath
    this._x1 = this._y1 = null;
    this._ = "";
    this._append = digits == null ? append : appendRound(digits);
  }
  moveTo(x4, y4) {
    this._append`M${this._x0 = this._x1 = +x4},${this._y0 = this._y1 = +y4}`;
  }
  closePath() {
    if (this._x1 !== null) {
      this._x1 = this._x0, this._y1 = this._y0;
      this._append`Z`;
    }
  }
  lineTo(x4, y4) {
    this._append`L${this._x1 = +x4},${this._y1 = +y4}`;
  }
  quadraticCurveTo(x12, y12, x4, y4) {
    this._append`Q${+x12},${+y12},${this._x1 = +x4},${this._y1 = +y4}`;
  }
  bezierCurveTo(x12, y12, x22, y22, x4, y4) {
    this._append`C${+x12},${+y12},${+x22},${+y22},${this._x1 = +x4},${this._y1 = +y4}`;
  }
  arcTo(x12, y12, x22, y22, r) {
    x12 = +x12, y12 = +y12, x22 = +x22, y22 = +y22, r = +r;
    if (r < 0) throw new Error(`negative radius: ${r}`);
    let x06 = this._x1, y06 = this._y1, x21 = x22 - x12, y21 = y22 - y12, x01 = x06 - x12, y01 = y06 - y12, l01_2 = x01 * x01 + y01 * y01;
    if (this._x1 === null) {
      this._append`M${this._x1 = x12},${this._y1 = y12}`;
    } else if (!(l01_2 > epsilon3)) ;
    else if (!(Math.abs(y01 * x21 - y21 * x01) > epsilon3) || !r) {
      this._append`L${this._x1 = x12},${this._y1 = y12}`;
    } else {
      let x20 = x22 - x06, y20 = y22 - y06, l21_2 = x21 * x21 + y21 * y21, l20_2 = x20 * x20 + y20 * y20, l21 = Math.sqrt(l21_2), l01 = Math.sqrt(l01_2), l = r * Math.tan((pi2 - Math.acos((l21_2 + l01_2 - l20_2) / (2 * l21 * l01))) / 2), t01 = l / l01, t21 = l / l21;
      if (Math.abs(t01 - 1) > epsilon3) {
        this._append`L${x12 + t01 * x01},${y12 + t01 * y01}`;
      }
      this._append`A${r},${r},0,0,${+(y01 * x20 > x01 * y20)},${this._x1 = x12 + t21 * x21},${this._y1 = y12 + t21 * y21}`;
    }
  }
  arc(x4, y4, r, a0, a1, ccw) {
    x4 = +x4, y4 = +y4, r = +r, ccw = !!ccw;
    if (r < 0) throw new Error(`negative radius: ${r}`);
    let dx = r * Math.cos(a0), dy = r * Math.sin(a0), x06 = x4 + dx, y06 = y4 + dy, cw = 1 ^ ccw, da2 = ccw ? a0 - a1 : a1 - a0;
    if (this._x1 === null) {
      this._append`M${x06},${y06}`;
    } else if (Math.abs(this._x1 - x06) > epsilon3 || Math.abs(this._y1 - y06) > epsilon3) {
      this._append`L${x06},${y06}`;
    }
    if (!r) return;
    if (da2 < 0) da2 = da2 % tau2 + tau2;
    if (da2 > tauEpsilon) {
      this._append`A${r},${r},0,1,${cw},${x4 - dx},${y4 - dy}A${r},${r},0,1,${cw},${this._x1 = x06},${this._y1 = y06}`;
    } else if (da2 > epsilon3) {
      this._append`A${r},${r},0,${+(da2 >= pi2)},${cw},${this._x1 = x4 + r * Math.cos(a1)},${this._y1 = y4 + r * Math.sin(a1)}`;
    }
  }
  rect(x4, y4, w, h) {
    this._append`M${this._x0 = this._x1 = +x4},${this._y0 = this._y1 = +y4}h${w = +w}v${+h}h${-w}Z`;
  }
  toString() {
    return this._;
  }
};
function path() {
  return new Path();
}
path.prototype = Path.prototype;
function pathRound(digits = 3) {
  return new Path(+digits);
}

// node_modules/d3-chord/src/array.js
var slice2 = Array.prototype.slice;

// node_modules/d3-chord/src/constant.js
function constant_default2(x4) {
  return function() {
    return x4;
  };
}

// node_modules/d3-chord/src/ribbon.js
function defaultSource(d) {
  return d.source;
}
function defaultTarget(d) {
  return d.target;
}
function defaultRadius(d) {
  return d.radius;
}
function defaultStartAngle(d) {
  return d.startAngle;
}
function defaultEndAngle(d) {
  return d.endAngle;
}
function defaultPadAngle() {
  return 0;
}
function defaultArrowheadRadius() {
  return 10;
}
function ribbon(headRadius) {
  var source = defaultSource, target = defaultTarget, sourceRadius = defaultRadius, targetRadius = defaultRadius, startAngle = defaultStartAngle, endAngle = defaultEndAngle, padAngle = defaultPadAngle, context = null;
  function ribbon2() {
    var buffer, s2 = source.apply(this, arguments), t = target.apply(this, arguments), ap = padAngle.apply(this, arguments) / 2, argv = slice2.call(arguments), sr = +sourceRadius.apply(this, (argv[0] = s2, argv)), sa0 = startAngle.apply(this, argv) - halfPi, sa1 = endAngle.apply(this, argv) - halfPi, tr = +targetRadius.apply(this, (argv[0] = t, argv)), ta0 = startAngle.apply(this, argv) - halfPi, ta1 = endAngle.apply(this, argv) - halfPi;
    if (!context) context = buffer = path();
    if (ap > epsilon2) {
      if (abs2(sa1 - sa0) > ap * 2 + epsilon2) sa1 > sa0 ? (sa0 += ap, sa1 -= ap) : (sa0 -= ap, sa1 += ap);
      else sa0 = sa1 = (sa0 + sa1) / 2;
      if (abs2(ta1 - ta0) > ap * 2 + epsilon2) ta1 > ta0 ? (ta0 += ap, ta1 -= ap) : (ta0 -= ap, ta1 += ap);
      else ta0 = ta1 = (ta0 + ta1) / 2;
    }
    context.moveTo(sr * cos(sa0), sr * sin(sa0));
    context.arc(0, 0, sr, sa0, sa1);
    if (sa0 !== ta0 || sa1 !== ta1) {
      if (headRadius) {
        var hr = +headRadius.apply(this, arguments), tr2 = tr - hr, ta2 = (ta0 + ta1) / 2;
        context.quadraticCurveTo(0, 0, tr2 * cos(ta0), tr2 * sin(ta0));
        context.lineTo(tr * cos(ta2), tr * sin(ta2));
        context.lineTo(tr2 * cos(ta1), tr2 * sin(ta1));
      } else {
        context.quadraticCurveTo(0, 0, tr * cos(ta0), tr * sin(ta0));
        context.arc(0, 0, tr, ta0, ta1);
      }
    }
    context.quadraticCurveTo(0, 0, sr * cos(sa0), sr * sin(sa0));
    context.closePath();
    if (buffer) return context = null, buffer + "" || null;
  }
  if (headRadius) ribbon2.headRadius = function(_) {
    return arguments.length ? (headRadius = typeof _ === "function" ? _ : constant_default2(+_), ribbon2) : headRadius;
  };
  ribbon2.radius = function(_) {
    return arguments.length ? (sourceRadius = targetRadius = typeof _ === "function" ? _ : constant_default2(+_), ribbon2) : sourceRadius;
  };
  ribbon2.sourceRadius = function(_) {
    return arguments.length ? (sourceRadius = typeof _ === "function" ? _ : constant_default2(+_), ribbon2) : sourceRadius;
  };
  ribbon2.targetRadius = function(_) {
    return arguments.length ? (targetRadius = typeof _ === "function" ? _ : constant_default2(+_), ribbon2) : targetRadius;
  };
  ribbon2.startAngle = function(_) {
    return arguments.length ? (startAngle = typeof _ === "function" ? _ : constant_default2(+_), ribbon2) : startAngle;
  };
  ribbon2.endAngle = function(_) {
    return arguments.length ? (endAngle = typeof _ === "function" ? _ : constant_default2(+_), ribbon2) : endAngle;
  };
  ribbon2.padAngle = function(_) {
    return arguments.length ? (padAngle = typeof _ === "function" ? _ : constant_default2(+_), ribbon2) : padAngle;
  };
  ribbon2.source = function(_) {
    return arguments.length ? (source = _, ribbon2) : source;
  };
  ribbon2.target = function(_) {
    return arguments.length ? (target = _, ribbon2) : target;
  };
  ribbon2.context = function(_) {
    return arguments.length ? (context = _ == null ? null : _, ribbon2) : context;
  };
  return ribbon2;
}
function ribbon_default() {
  return ribbon();
}
function ribbonArrow() {
  return ribbon(defaultArrowheadRadius);
}

// node_modules/d3-contour/src/array.js
var array2 = Array.prototype;
var slice3 = array2.slice;

// node_modules/d3-contour/src/ascending.js
function ascending_default(a4, b) {
  return a4 - b;
}

// node_modules/d3-contour/src/area.js
function area_default(ring) {
  var i = 0, n = ring.length, area = ring[n - 1][1] * ring[0][0] - ring[n - 1][0] * ring[0][1];
  while (++i < n) area += ring[i - 1][1] * ring[i][0] - ring[i - 1][0] * ring[i][1];
  return area;
}

// node_modules/d3-contour/src/constant.js
var constant_default3 = (x4) => () => x4;

// node_modules/d3-contour/src/contains.js
function contains_default(ring, hole) {
  var i = -1, n = hole.length, c6;
  while (++i < n) if (c6 = ringContains(ring, hole[i])) return c6;
  return 0;
}
function ringContains(ring, point6) {
  var x4 = point6[0], y4 = point6[1], contains = -1;
  for (var i = 0, n = ring.length, j = n - 1; i < n; j = i++) {
    var pi5 = ring[i], xi = pi5[0], yi = pi5[1], pj = ring[j], xj = pj[0], yj = pj[1];
    if (segmentContains(pi5, pj, point6)) return 0;
    if (yi > y4 !== yj > y4 && x4 < (xj - xi) * (y4 - yi) / (yj - yi) + xi) contains = -contains;
  }
  return contains;
}
function segmentContains(a4, b, c6) {
  var i;
  return collinear(a4, b, c6) && within(a4[i = +(a4[0] === b[0])], c6[i], b[i]);
}
function collinear(a4, b, c6) {
  return (b[0] - a4[0]) * (c6[1] - a4[1]) === (c6[0] - a4[0]) * (b[1] - a4[1]);
}
function within(p, q, r) {
  return p <= q && q <= r || r <= q && q <= p;
}

// node_modules/d3-contour/src/noop.js
function noop_default() {
}

// node_modules/d3-contour/src/contours.js
var cases = [
  [],
  [[[1, 1.5], [0.5, 1]]],
  [[[1.5, 1], [1, 1.5]]],
  [[[1.5, 1], [0.5, 1]]],
  [[[1, 0.5], [1.5, 1]]],
  [[[1, 1.5], [0.5, 1]], [[1, 0.5], [1.5, 1]]],
  [[[1, 0.5], [1, 1.5]]],
  [[[1, 0.5], [0.5, 1]]],
  [[[0.5, 1], [1, 0.5]]],
  [[[1, 1.5], [1, 0.5]]],
  [[[0.5, 1], [1, 0.5]], [[1.5, 1], [1, 1.5]]],
  [[[1.5, 1], [1, 0.5]]],
  [[[0.5, 1], [1.5, 1]]],
  [[[1, 1.5], [1.5, 1]]],
  [[[0.5, 1], [1, 1.5]]],
  []
];
function contours_default() {
  var dx = 1, dy = 1, threshold2 = thresholdSturges, smooth = smoothLinear;
  function contours(values) {
    var tz = threshold2(values);
    if (!Array.isArray(tz)) {
      const e = extent(values, finite);
      tz = ticks(...nice(e[0], e[1], tz), tz);
      while (tz[tz.length - 1] >= e[1]) tz.pop();
      while (tz[1] < e[0]) tz.shift();
    } else {
      tz = tz.slice().sort(ascending_default);
    }
    return tz.map((value) => contour(values, value));
  }
  function contour(values, value) {
    const v2 = value == null ? NaN : +value;
    if (isNaN(v2)) throw new Error(`invalid value: ${value}`);
    var polygons = [], holes = [];
    isorings(values, v2, function(ring) {
      smooth(ring, values, v2);
      if (area_default(ring) > 0) polygons.push([ring]);
      else holes.push(ring);
    });
    holes.forEach(function(hole) {
      for (var i = 0, n = polygons.length, polygon; i < n; ++i) {
        if (contains_default((polygon = polygons[i])[0], hole) !== -1) {
          polygon.push(hole);
          return;
        }
      }
    });
    return {
      type: "MultiPolygon",
      value,
      coordinates: polygons
    };
  }
  function isorings(values, value, callback) {
    var fragmentByStart = new Array(), fragmentByEnd = new Array(), x4, y4, t02, t12, t2, t3;
    x4 = y4 = -1;
    t12 = above(values[0], value);
    cases[t12 << 1].forEach(stitch);
    while (++x4 < dx - 1) {
      t02 = t12, t12 = above(values[x4 + 1], value);
      cases[t02 | t12 << 1].forEach(stitch);
    }
    cases[t12 << 0].forEach(stitch);
    while (++y4 < dy - 1) {
      x4 = -1;
      t12 = above(values[y4 * dx + dx], value);
      t2 = above(values[y4 * dx], value);
      cases[t12 << 1 | t2 << 2].forEach(stitch);
      while (++x4 < dx - 1) {
        t02 = t12, t12 = above(values[y4 * dx + dx + x4 + 1], value);
        t3 = t2, t2 = above(values[y4 * dx + x4 + 1], value);
        cases[t02 | t12 << 1 | t2 << 2 | t3 << 3].forEach(stitch);
      }
      cases[t12 | t2 << 3].forEach(stitch);
    }
    x4 = -1;
    t2 = values[y4 * dx] >= value;
    cases[t2 << 2].forEach(stitch);
    while (++x4 < dx - 1) {
      t3 = t2, t2 = above(values[y4 * dx + x4 + 1], value);
      cases[t2 << 2 | t3 << 3].forEach(stitch);
    }
    cases[t2 << 3].forEach(stitch);
    function stitch(line) {
      var start = [line[0][0] + x4, line[0][1] + y4], end = [line[1][0] + x4, line[1][1] + y4], startIndex = index3(start), endIndex = index3(end), f, g;
      if (f = fragmentByEnd[startIndex]) {
        if (g = fragmentByStart[endIndex]) {
          delete fragmentByEnd[f.end];
          delete fragmentByStart[g.start];
          if (f === g) {
            f.ring.push(end);
            callback(f.ring);
          } else {
            fragmentByStart[f.start] = fragmentByEnd[g.end] = { start: f.start, end: g.end, ring: f.ring.concat(g.ring) };
          }
        } else {
          delete fragmentByEnd[f.end];
          f.ring.push(end);
          fragmentByEnd[f.end = endIndex] = f;
        }
      } else if (f = fragmentByStart[endIndex]) {
        if (g = fragmentByEnd[startIndex]) {
          delete fragmentByStart[f.start];
          delete fragmentByEnd[g.end];
          if (f === g) {
            f.ring.push(end);
            callback(f.ring);
          } else {
            fragmentByStart[g.start] = fragmentByEnd[f.end] = { start: g.start, end: f.end, ring: g.ring.concat(f.ring) };
          }
        } else {
          delete fragmentByStart[f.start];
          f.ring.unshift(start);
          fragmentByStart[f.start = startIndex] = f;
        }
      } else {
        fragmentByStart[startIndex] = fragmentByEnd[endIndex] = { start: startIndex, end: endIndex, ring: [start, end] };
      }
    }
  }
  function index3(point6) {
    return point6[0] * 2 + point6[1] * (dx + 1) * 4;
  }
  function smoothLinear(ring, values, value) {
    ring.forEach(function(point6) {
      var x4 = point6[0], y4 = point6[1], xt = x4 | 0, yt = y4 | 0, v1 = valid(values[yt * dx + xt]);
      if (x4 > 0 && x4 < dx && xt === x4) {
        point6[0] = smooth1(x4, valid(values[yt * dx + xt - 1]), v1, value);
      }
      if (y4 > 0 && y4 < dy && yt === y4) {
        point6[1] = smooth1(y4, valid(values[(yt - 1) * dx + xt]), v1, value);
      }
    });
  }
  contours.contour = contour;
  contours.size = function(_) {
    if (!arguments.length) return [dx, dy];
    var _0 = Math.floor(_[0]), _1 = Math.floor(_[1]);
    if (!(_0 >= 0 && _1 >= 0)) throw new Error("invalid size");
    return dx = _0, dy = _1, contours;
  };
  contours.thresholds = function(_) {
    return arguments.length ? (threshold2 = typeof _ === "function" ? _ : Array.isArray(_) ? constant_default3(slice3.call(_)) : constant_default3(_), contours) : threshold2;
  };
  contours.smooth = function(_) {
    return arguments.length ? (smooth = _ ? smoothLinear : noop_default, contours) : smooth === smoothLinear;
  };
  return contours;
}
function finite(x4) {
  return isFinite(x4) ? x4 : NaN;
}
function above(x4, value) {
  return x4 == null ? false : +x4 >= value;
}
function valid(v2) {
  return v2 == null || isNaN(v2 = +v2) ? -Infinity : v2;
}
function smooth1(x4, v0, v1, value) {
  const a4 = value - v0;
  const b = v1 - v0;
  const d = isFinite(a4) || isFinite(b) ? a4 / b : Math.sign(a4) / Math.sign(b);
  return isNaN(d) ? x4 : x4 + d - 0.5;
}

// node_modules/d3-contour/src/density.js
function defaultX(d) {
  return d[0];
}
function defaultY(d) {
  return d[1];
}
function defaultWeight() {
  return 1;
}
function density_default() {
  var x4 = defaultX, y4 = defaultY, weight = defaultWeight, dx = 960, dy = 500, r = 20, k2 = 2, o = r * 3, n = dx + o * 2 >> k2, m3 = dy + o * 2 >> k2, threshold2 = constant_default3(20);
  function grid(data) {
    var values = new Float32Array(n * m3), pow2k = Math.pow(2, -k2), i = -1;
    for (const d of data) {
      var xi = (x4(d, ++i, data) + o) * pow2k, yi = (y4(d, i, data) + o) * pow2k, wi = +weight(d, i, data);
      if (wi && xi >= 0 && xi < n && yi >= 0 && yi < m3) {
        var x06 = Math.floor(xi), y06 = Math.floor(yi), xt = xi - x06 - 0.5, yt = yi - y06 - 0.5;
        values[x06 + y06 * n] += (1 - xt) * (1 - yt) * wi;
        values[x06 + 1 + y06 * n] += xt * (1 - yt) * wi;
        values[x06 + 1 + (y06 + 1) * n] += xt * yt * wi;
        values[x06 + (y06 + 1) * n] += (1 - xt) * yt * wi;
      }
    }
    blur2({ data: values, width: n, height: m3 }, r * pow2k);
    return values;
  }
  function density(data) {
    var values = grid(data), tz = threshold2(values), pow4k = Math.pow(2, 2 * k2);
    if (!Array.isArray(tz)) {
      tz = ticks(Number.MIN_VALUE, max(values) / pow4k, tz);
    }
    return contours_default().size([n, m3]).thresholds(tz.map((d) => d * pow4k))(values).map((c6, i) => (c6.value = +tz[i], transform2(c6)));
  }
  density.contours = function(data) {
    var values = grid(data), contours = contours_default().size([n, m3]), pow4k = Math.pow(2, 2 * k2), contour = (value) => {
      value = +value;
      var c6 = transform2(contours.contour(values, value * pow4k));
      c6.value = value;
      return c6;
    };
    Object.defineProperty(contour, "max", { get: () => max(values) / pow4k });
    return contour;
  };
  function transform2(geometry) {
    geometry.coordinates.forEach(transformPolygon);
    return geometry;
  }
  function transformPolygon(coordinates2) {
    coordinates2.forEach(transformRing);
  }
  function transformRing(coordinates2) {
    coordinates2.forEach(transformPoint);
  }
  function transformPoint(coordinates2) {
    coordinates2[0] = coordinates2[0] * Math.pow(2, k2) - o;
    coordinates2[1] = coordinates2[1] * Math.pow(2, k2) - o;
  }
  function resize() {
    o = r * 3;
    n = dx + o * 2 >> k2;
    m3 = dy + o * 2 >> k2;
    return density;
  }
  density.x = function(_) {
    return arguments.length ? (x4 = typeof _ === "function" ? _ : constant_default3(+_), density) : x4;
  };
  density.y = function(_) {
    return arguments.length ? (y4 = typeof _ === "function" ? _ : constant_default3(+_), density) : y4;
  };
  density.weight = function(_) {
    return arguments.length ? (weight = typeof _ === "function" ? _ : constant_default3(+_), density) : weight;
  };
  density.size = function(_) {
    if (!arguments.length) return [dx, dy];
    var _0 = +_[0], _1 = +_[1];
    if (!(_0 >= 0 && _1 >= 0)) throw new Error("invalid size");
    return dx = _0, dy = _1, resize();
  };
  density.cellSize = function(_) {
    if (!arguments.length) return 1 << k2;
    if (!((_ = +_) >= 1)) throw new Error("invalid cell size");
    return k2 = Math.floor(Math.log(_) / Math.LN2), resize();
  };
  density.thresholds = function(_) {
    return arguments.length ? (threshold2 = typeof _ === "function" ? _ : Array.isArray(_) ? constant_default3(slice3.call(_)) : constant_default3(_), density) : threshold2;
  };
  density.bandwidth = function(_) {
    if (!arguments.length) return Math.sqrt(r * (r + 1));
    if (!((_ = +_) >= 0)) throw new Error("invalid bandwidth");
    return r = (Math.sqrt(4 * _ * _ + 1) - 1) / 2, resize();
  };
  return density;
}

// node_modules/robust-predicates/esm/util.js
var epsilon4 = 11102230246251565e-32;
var splitter = 134217729;
var resulterrbound = (3 + 8 * epsilon4) * epsilon4;
function sum2(elen, e, flen, f, h) {
  let Q, Qnew, hh, bvirt;
  let enow = e[0];
  let fnow = f[0];
  let eindex = 0;
  let findex = 0;
  if (fnow > enow === fnow > -enow) {
    Q = enow;
    enow = e[++eindex];
  } else {
    Q = fnow;
    fnow = f[++findex];
  }
  let hindex = 0;
  if (eindex < elen && findex < flen) {
    if (fnow > enow === fnow > -enow) {
      Qnew = enow + Q;
      hh = Q - (Qnew - enow);
      enow = e[++eindex];
    } else {
      Qnew = fnow + Q;
      hh = Q - (Qnew - fnow);
      fnow = f[++findex];
    }
    Q = Qnew;
    if (hh !== 0) {
      h[hindex++] = hh;
    }
    while (eindex < elen && findex < flen) {
      if (fnow > enow === fnow > -enow) {
        Qnew = Q + enow;
        bvirt = Qnew - Q;
        hh = Q - (Qnew - bvirt) + (enow - bvirt);
        enow = e[++eindex];
      } else {
        Qnew = Q + fnow;
        bvirt = Qnew - Q;
        hh = Q - (Qnew - bvirt) + (fnow - bvirt);
        fnow = f[++findex];
      }
      Q = Qnew;
      if (hh !== 0) {
        h[hindex++] = hh;
      }
    }
  }
  while (eindex < elen) {
    Qnew = Q + enow;
    bvirt = Qnew - Q;
    hh = Q - (Qnew - bvirt) + (enow - bvirt);
    enow = e[++eindex];
    Q = Qnew;
    if (hh !== 0) {
      h[hindex++] = hh;
    }
  }
  while (findex < flen) {
    Qnew = Q + fnow;
    bvirt = Qnew - Q;
    hh = Q - (Qnew - bvirt) + (fnow - bvirt);
    fnow = f[++findex];
    Q = Qnew;
    if (hh !== 0) {
      h[hindex++] = hh;
    }
  }
  if (Q !== 0 || hindex === 0) {
    h[hindex++] = Q;
  }
  return hindex;
}
function estimate(elen, e) {
  let Q = e[0];
  for (let i = 1; i < elen; i++) Q += e[i];
  return Q;
}
function vec(n) {
  return new Float64Array(n);
}

// node_modules/robust-predicates/esm/orient2d.js
var ccwerrboundA = (3 + 16 * epsilon4) * epsilon4;
var ccwerrboundB = (2 + 12 * epsilon4) * epsilon4;
var ccwerrboundC = (9 + 64 * epsilon4) * epsilon4 * epsilon4;
var B = vec(4);
var C1 = vec(8);
var C2 = vec(12);
var D = vec(16);
var u = vec(4);
function orient2dadapt(ax, ay, bx, by, cx, cy, detsum) {
  let acxtail, acytail, bcxtail, bcytail;
  let bvirt, c6, ahi, alo, bhi, blo, _i, _j, _0, s1, s0, t12, t02, u32;
  const acx = ax - cx;
  const bcx = bx - cx;
  const acy = ay - cy;
  const bcy = by - cy;
  s1 = acx * bcy;
  c6 = splitter * acx;
  ahi = c6 - (c6 - acx);
  alo = acx - ahi;
  c6 = splitter * bcy;
  bhi = c6 - (c6 - bcy);
  blo = bcy - bhi;
  s0 = alo * blo - (s1 - ahi * bhi - alo * bhi - ahi * blo);
  t12 = acy * bcx;
  c6 = splitter * acy;
  ahi = c6 - (c6 - acy);
  alo = acy - ahi;
  c6 = splitter * bcx;
  bhi = c6 - (c6 - bcx);
  blo = bcx - bhi;
  t02 = alo * blo - (t12 - ahi * bhi - alo * bhi - ahi * blo);
  _i = s0 - t02;
  bvirt = s0 - _i;
  B[0] = s0 - (_i + bvirt) + (bvirt - t02);
  _j = s1 + _i;
  bvirt = _j - s1;
  _0 = s1 - (_j - bvirt) + (_i - bvirt);
  _i = _0 - t12;
  bvirt = _0 - _i;
  B[1] = _0 - (_i + bvirt) + (bvirt - t12);
  u32 = _j + _i;
  bvirt = u32 - _j;
  B[2] = _j - (u32 - bvirt) + (_i - bvirt);
  B[3] = u32;
  let det = estimate(4, B);
  let errbound = ccwerrboundB * detsum;
  if (det >= errbound || -det >= errbound) {
    return det;
  }
  bvirt = ax - acx;
  acxtail = ax - (acx + bvirt) + (bvirt - cx);
  bvirt = bx - bcx;
  bcxtail = bx - (bcx + bvirt) + (bvirt - cx);
  bvirt = ay - acy;
  acytail = ay - (acy + bvirt) + (bvirt - cy);
  bvirt = by - bcy;
  bcytail = by - (bcy + bvirt) + (bvirt - cy);
  if (acxtail === 0 && acytail === 0 && bcxtail === 0 && bcytail === 0) {
    return det;
  }
  errbound = ccwerrboundC * detsum + resulterrbound * Math.abs(det);
  det += acx * bcytail + bcy * acxtail - (acy * bcxtail + bcx * acytail);
  if (det >= errbound || -det >= errbound) return det;
  s1 = acxtail * bcy;
  c6 = splitter * acxtail;
  ahi = c6 - (c6 - acxtail);
  alo = acxtail - ahi;
  c6 = splitter * bcy;
  bhi = c6 - (c6 - bcy);
  blo = bcy - bhi;
  s0 = alo * blo - (s1 - ahi * bhi - alo * bhi - ahi * blo);
  t12 = acytail * bcx;
  c6 = splitter * acytail;
  ahi = c6 - (c6 - acytail);
  alo = acytail - ahi;
  c6 = splitter * bcx;
  bhi = c6 - (c6 - bcx);
  blo = bcx - bhi;
  t02 = alo * blo - (t12 - ahi * bhi - alo * bhi - ahi * blo);
  _i = s0 - t02;
  bvirt = s0 - _i;
  u[0] = s0 - (_i + bvirt) + (bvirt - t02);
  _j = s1 + _i;
  bvirt = _j - s1;
  _0 = s1 - (_j - bvirt) + (_i - bvirt);
  _i = _0 - t12;
  bvirt = _0 - _i;
  u[1] = _0 - (_i + bvirt) + (bvirt - t12);
  u32 = _j + _i;
  bvirt = u32 - _j;
  u[2] = _j - (u32 - bvirt) + (_i - bvirt);
  u[3] = u32;
  const C1len = sum2(4, B, 4, u, C1);
  s1 = acx * bcytail;
  c6 = splitter * acx;
  ahi = c6 - (c6 - acx);
  alo = acx - ahi;
  c6 = splitter * bcytail;
  bhi = c6 - (c6 - bcytail);
  blo = bcytail - bhi;
  s0 = alo * blo - (s1 - ahi * bhi - alo * bhi - ahi * blo);
  t12 = acy * bcxtail;
  c6 = splitter * acy;
  ahi = c6 - (c6 - acy);
  alo = acy - ahi;
  c6 = splitter * bcxtail;
  bhi = c6 - (c6 - bcxtail);
  blo = bcxtail - bhi;
  t02 = alo * blo - (t12 - ahi * bhi - alo * bhi - ahi * blo);
  _i = s0 - t02;
  bvirt = s0 - _i;
  u[0] = s0 - (_i + bvirt) + (bvirt - t02);
  _j = s1 + _i;
  bvirt = _j - s1;
  _0 = s1 - (_j - bvirt) + (_i - bvirt);
  _i = _0 - t12;
  bvirt = _0 - _i;
  u[1] = _0 - (_i + bvirt) + (bvirt - t12);
  u32 = _j + _i;
  bvirt = u32 - _j;
  u[2] = _j - (u32 - bvirt) + (_i - bvirt);
  u[3] = u32;
  const C2len = sum2(C1len, C1, 4, u, C2);
  s1 = acxtail * bcytail;
  c6 = splitter * acxtail;
  ahi = c6 - (c6 - acxtail);
  alo = acxtail - ahi;
  c6 = splitter * bcytail;
  bhi = c6 - (c6 - bcytail);
  blo = bcytail - bhi;
  s0 = alo * blo - (s1 - ahi * bhi - alo * bhi - ahi * blo);
  t12 = acytail * bcxtail;
  c6 = splitter * acytail;
  ahi = c6 - (c6 - acytail);
  alo = acytail - ahi;
  c6 = splitter * bcxtail;
  bhi = c6 - (c6 - bcxtail);
  blo = bcxtail - bhi;
  t02 = alo * blo - (t12 - ahi * bhi - alo * bhi - ahi * blo);
  _i = s0 - t02;
  bvirt = s0 - _i;
  u[0] = s0 - (_i + bvirt) + (bvirt - t02);
  _j = s1 + _i;
  bvirt = _j - s1;
  _0 = s1 - (_j - bvirt) + (_i - bvirt);
  _i = _0 - t12;
  bvirt = _0 - _i;
  u[1] = _0 - (_i + bvirt) + (bvirt - t12);
  u32 = _j + _i;
  bvirt = u32 - _j;
  u[2] = _j - (u32 - bvirt) + (_i - bvirt);
  u[3] = u32;
  const Dlen = sum2(C2len, C2, 4, u, D);
  return D[Dlen - 1];
}
function orient2d(ax, ay, bx, by, cx, cy) {
  const detleft = (ay - cy) * (bx - cx);
  const detright = (ax - cx) * (by - cy);
  const det = detleft - detright;
  const detsum = Math.abs(detleft + detright);
  if (Math.abs(det) >= ccwerrboundA * detsum) return det;
  return -orient2dadapt(ax, ay, bx, by, cx, cy, detsum);
}

// node_modules/robust-predicates/esm/orient3d.js
var o3derrboundA = (7 + 56 * epsilon4) * epsilon4;
var o3derrboundB = (3 + 28 * epsilon4) * epsilon4;
var o3derrboundC = (26 + 288 * epsilon4) * epsilon4 * epsilon4;
var bc = vec(4);
var ca = vec(4);
var ab = vec(4);
var at_b = vec(4);
var at_c = vec(4);
var bt_c = vec(4);
var bt_a = vec(4);
var ct_a = vec(4);
var ct_b = vec(4);
var bct = vec(8);
var cat = vec(8);
var abt = vec(8);
var u2 = vec(4);
var _8 = vec(8);
var _8b = vec(8);
var _16 = vec(8);
var _12 = vec(12);
var fin = vec(192);
var fin2 = vec(192);

// node_modules/robust-predicates/esm/incircle.js
var iccerrboundA = (10 + 96 * epsilon4) * epsilon4;
var iccerrboundB = (4 + 48 * epsilon4) * epsilon4;
var iccerrboundC = (44 + 576 * epsilon4) * epsilon4 * epsilon4;
var bc2 = vec(4);
var ca2 = vec(4);
var ab2 = vec(4);
var aa = vec(4);
var bb = vec(4);
var cc = vec(4);
var u3 = vec(4);
var v = vec(4);
var axtbc = vec(8);
var aytbc = vec(8);
var bxtca = vec(8);
var bytca = vec(8);
var cxtab = vec(8);
var cytab = vec(8);
var abt2 = vec(8);
var bct2 = vec(8);
var cat2 = vec(8);
var abtt = vec(4);
var bctt = vec(4);
var catt = vec(4);
var _82 = vec(8);
var _162 = vec(16);
var _16b = vec(16);
var _16c = vec(16);
var _32 = vec(32);
var _32b = vec(32);
var _48 = vec(48);
var _64 = vec(64);
var fin3 = vec(1152);
var fin22 = vec(1152);

// node_modules/robust-predicates/esm/insphere.js
var isperrboundA = (16 + 224 * epsilon4) * epsilon4;
var isperrboundB = (5 + 72 * epsilon4) * epsilon4;
var isperrboundC = (71 + 1408 * epsilon4) * epsilon4 * epsilon4;
var ab3 = vec(4);
var bc3 = vec(4);
var cd = vec(4);
var de = vec(4);
var ea = vec(4);
var ac = vec(4);
var bd = vec(4);
var ce = vec(4);
var da = vec(4);
var eb = vec(4);
var abc = vec(24);
var bcd = vec(24);
var cde = vec(24);
var dea = vec(24);
var eab = vec(24);
var abd = vec(24);
var bce = vec(24);
var cda = vec(24);
var deb = vec(24);
var eac = vec(24);
var adet = vec(1152);
var bdet = vec(1152);
var cdet = vec(1152);
var ddet = vec(1152);
var edet = vec(1152);
var abdet = vec(2304);
var cddet = vec(2304);
var cdedet = vec(3456);
var deter = vec(5760);
var _83 = vec(8);
var _8b2 = vec(8);
var _8c = vec(8);
var _163 = vec(16);
var _24 = vec(24);
var _482 = vec(48);
var _48b = vec(48);
var _96 = vec(96);
var _192 = vec(192);
var _384x = vec(384);
var _384y = vec(384);
var _384z = vec(384);
var _768 = vec(768);
var xdet = vec(96);
var ydet = vec(96);
var zdet = vec(96);
var fin4 = vec(1152);

// node_modules/delaunator/index.js
var EPSILON = Math.pow(2, -52);
var EDGE_STACK = new Uint32Array(512);
var Delaunator = class _Delaunator {
  static from(points, getX = defaultGetX, getY = defaultGetY) {
    const n = points.length;
    const coords = new Float64Array(n * 2);
    for (let i = 0; i < n; i++) {
      const p = points[i];
      coords[2 * i] = getX(p);
      coords[2 * i + 1] = getY(p);
    }
    return new _Delaunator(coords);
  }
  constructor(coords) {
    const n = coords.length >> 1;
    if (n > 0 && typeof coords[0] !== "number") throw new Error("Expected coords to contain numbers.");
    this.coords = coords;
    const maxTriangles = Math.max(2 * n - 5, 0);
    this._triangles = new Uint32Array(maxTriangles * 3);
    this._halfedges = new Int32Array(maxTriangles * 3);
    this._hashSize = Math.ceil(Math.sqrt(n));
    this._hullPrev = new Uint32Array(n);
    this._hullNext = new Uint32Array(n);
    this._hullTri = new Uint32Array(n);
    this._hullHash = new Int32Array(this._hashSize);
    this._ids = new Uint32Array(n);
    this._dists = new Float64Array(n);
    this.update();
  }
  update() {
    const { coords, _hullPrev: hullPrev, _hullNext: hullNext, _hullTri: hullTri, _hullHash: hullHash } = this;
    const n = coords.length >> 1;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY2 = -Infinity;
    for (let i = 0; i < n; i++) {
      const x4 = coords[2 * i];
      const y4 = coords[2 * i + 1];
      if (x4 < minX) minX = x4;
      if (y4 < minY) minY = y4;
      if (x4 > maxX) maxX = x4;
      if (y4 > maxY2) maxY2 = y4;
      this._ids[i] = i;
    }
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY2) / 2;
    let i0, i1, i2;
    for (let i = 0, minDist = Infinity; i < n; i++) {
      const d = dist(cx, cy, coords[2 * i], coords[2 * i + 1]);
      if (d < minDist) {
        i0 = i;
        minDist = d;
      }
    }
    const i0x = coords[2 * i0];
    const i0y = coords[2 * i0 + 1];
    for (let i = 0, minDist = Infinity; i < n; i++) {
      if (i === i0) continue;
      const d = dist(i0x, i0y, coords[2 * i], coords[2 * i + 1]);
      if (d < minDist && d > 0) {
        i1 = i;
        minDist = d;
      }
    }
    let i1x = coords[2 * i1];
    let i1y = coords[2 * i1 + 1];
    let minRadius = Infinity;
    for (let i = 0; i < n; i++) {
      if (i === i0 || i === i1) continue;
      const r = circumradius(i0x, i0y, i1x, i1y, coords[2 * i], coords[2 * i + 1]);
      if (r < minRadius) {
        i2 = i;
        minRadius = r;
      }
    }
    let i2x = coords[2 * i2];
    let i2y = coords[2 * i2 + 1];
    if (minRadius === Infinity) {
      for (let i = 0; i < n; i++) {
        this._dists[i] = coords[2 * i] - coords[0] || coords[2 * i + 1] - coords[1];
      }
      quicksort(this._ids, this._dists, 0, n - 1);
      const hull = new Uint32Array(n);
      let j = 0;
      for (let i = 0, d0 = -Infinity; i < n; i++) {
        const id = this._ids[i];
        const d = this._dists[id];
        if (d > d0) {
          hull[j++] = id;
          d0 = d;
        }
      }
      this.hull = hull.subarray(0, j);
      this.triangles = new Uint32Array(0);
      this.halfedges = new Uint32Array(0);
      return;
    }
    if (orient2d(i0x, i0y, i1x, i1y, i2x, i2y) < 0) {
      const i = i1;
      const x4 = i1x;
      const y4 = i1y;
      i1 = i2;
      i1x = i2x;
      i1y = i2y;
      i2 = i;
      i2x = x4;
      i2y = y4;
    }
    const center2 = circumcenter(i0x, i0y, i1x, i1y, i2x, i2y);
    this._cx = center2.x;
    this._cy = center2.y;
    for (let i = 0; i < n; i++) {
      this._dists[i] = dist(coords[2 * i], coords[2 * i + 1], center2.x, center2.y);
    }
    quicksort(this._ids, this._dists, 0, n - 1);
    this._hullStart = i0;
    let hullSize = 3;
    hullNext[i0] = hullPrev[i2] = i1;
    hullNext[i1] = hullPrev[i0] = i2;
    hullNext[i2] = hullPrev[i1] = i0;
    hullTri[i0] = 0;
    hullTri[i1] = 1;
    hullTri[i2] = 2;
    hullHash.fill(-1);
    hullHash[this._hashKey(i0x, i0y)] = i0;
    hullHash[this._hashKey(i1x, i1y)] = i1;
    hullHash[this._hashKey(i2x, i2y)] = i2;
    this.trianglesLen = 0;
    this._addTriangle(i0, i1, i2, -1, -1, -1);
    for (let k2 = 0, xp, yp; k2 < this._ids.length; k2++) {
      const i = this._ids[k2];
      const x4 = coords[2 * i];
      const y4 = coords[2 * i + 1];
      if (k2 > 0 && Math.abs(x4 - xp) <= EPSILON && Math.abs(y4 - yp) <= EPSILON) continue;
      xp = x4;
      yp = y4;
      if (i === i0 || i === i1 || i === i2) continue;
      let start = 0;
      for (let j = 0, key = this._hashKey(x4, y4); j < this._hashSize; j++) {
        start = hullHash[(key + j) % this._hashSize];
        if (start !== -1 && start !== hullNext[start]) break;
      }
      start = hullPrev[start];
      let e = start, q;
      while (q = hullNext[e], orient2d(x4, y4, coords[2 * e], coords[2 * e + 1], coords[2 * q], coords[2 * q + 1]) >= 0) {
        e = q;
        if (e === start) {
          e = -1;
          break;
        }
      }
      if (e === -1) continue;
      let t = this._addTriangle(e, i, hullNext[e], -1, -1, hullTri[e]);
      hullTri[i] = this._legalize(t + 2);
      hullTri[e] = t;
      hullSize++;
      let n2 = hullNext[e];
      while (q = hullNext[n2], orient2d(x4, y4, coords[2 * n2], coords[2 * n2 + 1], coords[2 * q], coords[2 * q + 1]) < 0) {
        t = this._addTriangle(n2, i, q, hullTri[i], -1, hullTri[n2]);
        hullTri[i] = this._legalize(t + 2);
        hullNext[n2] = n2;
        hullSize--;
        n2 = q;
      }
      if (e === start) {
        while (q = hullPrev[e], orient2d(x4, y4, coords[2 * q], coords[2 * q + 1], coords[2 * e], coords[2 * e + 1]) < 0) {
          t = this._addTriangle(q, i, e, -1, hullTri[e], hullTri[q]);
          this._legalize(t + 2);
          hullTri[q] = t;
          hullNext[e] = e;
          hullSize--;
          e = q;
        }
      }
      this._hullStart = hullPrev[i] = e;
      hullNext[e] = hullPrev[n2] = i;
      hullNext[i] = n2;
      hullHash[this._hashKey(x4, y4)] = i;
      hullHash[this._hashKey(coords[2 * e], coords[2 * e + 1])] = e;
    }
    this.hull = new Uint32Array(hullSize);
    for (let i = 0, e = this._hullStart; i < hullSize; i++) {
      this.hull[i] = e;
      e = hullNext[e];
    }
    this.triangles = this._triangles.subarray(0, this.trianglesLen);
    this.halfedges = this._halfedges.subarray(0, this.trianglesLen);
  }
  _hashKey(x4, y4) {
    return Math.floor(pseudoAngle(x4 - this._cx, y4 - this._cy) * this._hashSize) % this._hashSize;
  }
  _legalize(a4) {
    const { _triangles: triangles, _halfedges: halfedges, coords } = this;
    let i = 0;
    let ar = 0;
    while (true) {
      const b = halfedges[a4];
      const a0 = a4 - a4 % 3;
      ar = a0 + (a4 + 2) % 3;
      if (b === -1) {
        if (i === 0) break;
        a4 = EDGE_STACK[--i];
        continue;
      }
      const b0 = b - b % 3;
      const al = a0 + (a4 + 1) % 3;
      const bl = b0 + (b + 2) % 3;
      const p02 = triangles[ar];
      const pr = triangles[a4];
      const pl = triangles[al];
      const p1 = triangles[bl];
      const illegal = inCircle(
        coords[2 * p02],
        coords[2 * p02 + 1],
        coords[2 * pr],
        coords[2 * pr + 1],
        coords[2 * pl],
        coords[2 * pl + 1],
        coords[2 * p1],
        coords[2 * p1 + 1]
      );
      if (illegal) {
        triangles[a4] = p1;
        triangles[b] = p02;
        const hbl = halfedges[bl];
        if (hbl === -1) {
          let e = this._hullStart;
          do {
            if (this._hullTri[e] === bl) {
              this._hullTri[e] = a4;
              break;
            }
            e = this._hullPrev[e];
          } while (e !== this._hullStart);
        }
        this._link(a4, hbl);
        this._link(b, halfedges[ar]);
        this._link(ar, bl);
        const br = b0 + (b + 1) % 3;
        if (i < EDGE_STACK.length) {
          EDGE_STACK[i++] = br;
        }
      } else {
        if (i === 0) break;
        a4 = EDGE_STACK[--i];
      }
    }
    return ar;
  }
  _link(a4, b) {
    this._halfedges[a4] = b;
    if (b !== -1) this._halfedges[b] = a4;
  }
  // add a new triangle given vertex indices and adjacent half-edge ids
  _addTriangle(i0, i1, i2, a4, b, c6) {
    const t = this.trianglesLen;
    this._triangles[t] = i0;
    this._triangles[t + 1] = i1;
    this._triangles[t + 2] = i2;
    this._link(t, a4);
    this._link(t + 1, b);
    this._link(t + 2, c6);
    this.trianglesLen += 3;
    return t;
  }
};
function pseudoAngle(dx, dy) {
  const p = dx / (Math.abs(dx) + Math.abs(dy));
  return (dy > 0 ? 3 - p : 1 + p) / 4;
}
function dist(ax, ay, bx, by) {
  const dx = ax - bx;
  const dy = ay - by;
  return dx * dx + dy * dy;
}
function inCircle(ax, ay, bx, by, cx, cy, px, py) {
  const dx = ax - px;
  const dy = ay - py;
  const ex = bx - px;
  const ey = by - py;
  const fx = cx - px;
  const fy = cy - py;
  const ap = dx * dx + dy * dy;
  const bp = ex * ex + ey * ey;
  const cp = fx * fx + fy * fy;
  return dx * (ey * cp - bp * fy) - dy * (ex * cp - bp * fx) + ap * (ex * fy - ey * fx) < 0;
}
function circumradius(ax, ay, bx, by, cx, cy) {
  const dx = bx - ax;
  const dy = by - ay;
  const ex = cx - ax;
  const ey = cy - ay;
  const bl = dx * dx + dy * dy;
  const cl = ex * ex + ey * ey;
  const d = 0.5 / (dx * ey - dy * ex);
  const x4 = (ey * bl - dy * cl) * d;
  const y4 = (dx * cl - ex * bl) * d;
  return x4 * x4 + y4 * y4;
}
function circumcenter(ax, ay, bx, by, cx, cy) {
  const dx = bx - ax;
  const dy = by - ay;
  const ex = cx - ax;
  const ey = cy - ay;
  const bl = dx * dx + dy * dy;
  const cl = ex * ex + ey * ey;
  const d = 0.5 / (dx * ey - dy * ex);
  const x4 = ax + (ey * bl - dy * cl) * d;
  const y4 = ay + (dx * cl - ex * bl) * d;
  return { x: x4, y: y4 };
}
function quicksort(ids, dists, left2, right2) {
  if (right2 - left2 <= 20) {
    for (let i = left2 + 1; i <= right2; i++) {
      const temp = ids[i];
      const tempDist = dists[temp];
      let j = i - 1;
      while (j >= left2 && dists[ids[j]] > tempDist) ids[j + 1] = ids[j--];
      ids[j + 1] = temp;
    }
  } else {
    const median2 = left2 + right2 >> 1;
    let i = left2 + 1;
    let j = right2;
    swap2(ids, median2, i);
    if (dists[ids[left2]] > dists[ids[right2]]) swap2(ids, left2, right2);
    if (dists[ids[i]] > dists[ids[right2]]) swap2(ids, i, right2);
    if (dists[ids[left2]] > dists[ids[i]]) swap2(ids, left2, i);
    const temp = ids[i];
    const tempDist = dists[temp];
    while (true) {
      do
        i++;
      while (dists[ids[i]] < tempDist);
      do
        j--;
      while (dists[ids[j]] > tempDist);
      if (j < i) break;
      swap2(ids, i, j);
    }
    ids[left2 + 1] = ids[j];
    ids[j] = temp;
    if (right2 - i + 1 >= j - left2) {
      quicksort(ids, dists, i, right2);
      quicksort(ids, dists, left2, j - 1);
    } else {
      quicksort(ids, dists, left2, j - 1);
      quicksort(ids, dists, i, right2);
    }
  }
}
function swap2(arr, i, j) {
  const tmp = arr[i];
  arr[i] = arr[j];
  arr[j] = tmp;
}
function defaultGetX(p) {
  return p[0];
}
function defaultGetY(p) {
  return p[1];
}

// node_modules/d3-delaunay/src/path.js
var epsilon5 = 1e-6;
var Path2 = class {
  constructor() {
    this._x0 = this._y0 = // start of current subpath
    this._x1 = this._y1 = null;
    this._ = "";
  }
  moveTo(x4, y4) {
    this._ += `M${this._x0 = this._x1 = +x4},${this._y0 = this._y1 = +y4}`;
  }
  closePath() {
    if (this._x1 !== null) {
      this._x1 = this._x0, this._y1 = this._y0;
      this._ += "Z";
    }
  }
  lineTo(x4, y4) {
    this._ += `L${this._x1 = +x4},${this._y1 = +y4}`;
  }
  arc(x4, y4, r) {
    x4 = +x4, y4 = +y4, r = +r;
    const x06 = x4 + r;
    const y06 = y4;
    if (r < 0) throw new Error("negative radius");
    if (this._x1 === null) this._ += `M${x06},${y06}`;
    else if (Math.abs(this._x1 - x06) > epsilon5 || Math.abs(this._y1 - y06) > epsilon5) this._ += "L" + x06 + "," + y06;
    if (!r) return;
    this._ += `A${r},${r},0,1,1,${x4 - r},${y4}A${r},${r},0,1,1,${this._x1 = x06},${this._y1 = y06}`;
  }
  rect(x4, y4, w, h) {
    this._ += `M${this._x0 = this._x1 = +x4},${this._y0 = this._y1 = +y4}h${+w}v${+h}h${-w}Z`;
  }
  value() {
    return this._ || null;
  }
};

// node_modules/d3-delaunay/src/polygon.js
var Polygon = class {
  constructor() {
    this._ = [];
  }
  moveTo(x4, y4) {
    this._.push([x4, y4]);
  }
  closePath() {
    this._.push(this._[0].slice());
  }
  lineTo(x4, y4) {
    this._.push([x4, y4]);
  }
  value() {
    return this._.length ? this._ : null;
  }
};

// node_modules/d3-delaunay/src/voronoi.js
var Voronoi = class {
  constructor(delaunay, [xmin, ymin, xmax, ymax] = [0, 0, 960, 500]) {
    if (!((xmax = +xmax) >= (xmin = +xmin)) || !((ymax = +ymax) >= (ymin = +ymin))) throw new Error("invalid bounds");
    this.delaunay = delaunay;
    this._circumcenters = new Float64Array(delaunay.points.length * 2);
    this.vectors = new Float64Array(delaunay.points.length * 2);
    this.xmax = xmax, this.xmin = xmin;
    this.ymax = ymax, this.ymin = ymin;
    this._init();
  }
  update() {
    this.delaunay.update();
    this._init();
    return this;
  }
  _init() {
    const { delaunay: { points, hull, triangles }, vectors } = this;
    let bx, by;
    const circumcenters = this.circumcenters = this._circumcenters.subarray(0, triangles.length / 3 * 2);
    for (let i = 0, j = 0, n = triangles.length, x4, y4; i < n; i += 3, j += 2) {
      const t12 = triangles[i] * 2;
      const t2 = triangles[i + 1] * 2;
      const t3 = triangles[i + 2] * 2;
      const x13 = points[t12];
      const y13 = points[t12 + 1];
      const x22 = points[t2];
      const y22 = points[t2 + 1];
      const x32 = points[t3];
      const y32 = points[t3 + 1];
      const dx = x22 - x13;
      const dy = y22 - y13;
      const ex = x32 - x13;
      const ey = y32 - y13;
      const ab4 = (dx * ey - dy * ex) * 2;
      if (Math.abs(ab4) < 1e-9) {
        if (bx === void 0) {
          bx = by = 0;
          for (const i2 of hull) bx += points[i2 * 2], by += points[i2 * 2 + 1];
          bx /= hull.length, by /= hull.length;
        }
        const a4 = 1e9 * Math.sign((bx - x13) * ey - (by - y13) * ex);
        x4 = (x13 + x32) / 2 - a4 * ey;
        y4 = (y13 + y32) / 2 + a4 * ex;
      } else {
        const d = 1 / ab4;
        const bl = dx * dx + dy * dy;
        const cl = ex * ex + ey * ey;
        x4 = x13 + (ey * bl - dy * cl) * d;
        y4 = y13 + (dx * cl - ex * bl) * d;
      }
      circumcenters[j] = x4;
      circumcenters[j + 1] = y4;
    }
    let h = hull[hull.length - 1];
    let p02, p1 = h * 4;
    let x06, x12 = points[2 * h];
    let y06, y12 = points[2 * h + 1];
    vectors.fill(0);
    for (let i = 0; i < hull.length; ++i) {
      h = hull[i];
      p02 = p1, x06 = x12, y06 = y12;
      p1 = h * 4, x12 = points[2 * h], y12 = points[2 * h + 1];
      vectors[p02 + 2] = vectors[p1] = y06 - y12;
      vectors[p02 + 3] = vectors[p1 + 1] = x12 - x06;
    }
  }
  render(context) {
    const buffer = context == null ? context = new Path2() : void 0;
    const { delaunay: { halfedges, inedges, hull }, circumcenters, vectors } = this;
    if (hull.length <= 1) return null;
    for (let i = 0, n = halfedges.length; i < n; ++i) {
      const j = halfedges[i];
      if (j < i) continue;
      const ti = Math.floor(i / 3) * 2;
      const tj = Math.floor(j / 3) * 2;
      const xi = circumcenters[ti];
      const yi = circumcenters[ti + 1];
      const xj = circumcenters[tj];
      const yj = circumcenters[tj + 1];
      this._renderSegment(xi, yi, xj, yj, context);
    }
    let h0, h1 = hull[hull.length - 1];
    for (let i = 0; i < hull.length; ++i) {
      h0 = h1, h1 = hull[i];
      const t = Math.floor(inedges[h1] / 3) * 2;
      const x4 = circumcenters[t];
      const y4 = circumcenters[t + 1];
      const v2 = h0 * 4;
      const p = this._project(x4, y4, vectors[v2 + 2], vectors[v2 + 3]);
      if (p) this._renderSegment(x4, y4, p[0], p[1], context);
    }
    return buffer && buffer.value();
  }
  renderBounds(context) {
    const buffer = context == null ? context = new Path2() : void 0;
    context.rect(this.xmin, this.ymin, this.xmax - this.xmin, this.ymax - this.ymin);
    return buffer && buffer.value();
  }
  renderCell(i, context) {
    const buffer = context == null ? context = new Path2() : void 0;
    const points = this._clip(i);
    if (points === null || !points.length) return;
    context.moveTo(points[0], points[1]);
    let n = points.length;
    while (points[0] === points[n - 2] && points[1] === points[n - 1] && n > 1) n -= 2;
    for (let i2 = 2; i2 < n; i2 += 2) {
      if (points[i2] !== points[i2 - 2] || points[i2 + 1] !== points[i2 - 1])
        context.lineTo(points[i2], points[i2 + 1]);
    }
    context.closePath();
    return buffer && buffer.value();
  }
  *cellPolygons() {
    const { delaunay: { points } } = this;
    for (let i = 0, n = points.length / 2; i < n; ++i) {
      const cell = this.cellPolygon(i);
      if (cell) cell.index = i, yield cell;
    }
  }
  cellPolygon(i) {
    const polygon = new Polygon();
    this.renderCell(i, polygon);
    return polygon.value();
  }
  _renderSegment(x06, y06, x12, y12, context) {
    let S;
    const c0 = this._regioncode(x06, y06);
    const c1 = this._regioncode(x12, y12);
    if (c0 === 0 && c1 === 0) {
      context.moveTo(x06, y06);
      context.lineTo(x12, y12);
    } else if (S = this._clipSegment(x06, y06, x12, y12, c0, c1)) {
      context.moveTo(S[0], S[1]);
      context.lineTo(S[2], S[3]);
    }
  }
  contains(i, x4, y4) {
    if ((x4 = +x4, x4 !== x4) || (y4 = +y4, y4 !== y4)) return false;
    return this.delaunay._step(i, x4, y4) === i;
  }
  *neighbors(i) {
    const ci = this._clip(i);
    if (ci) for (const j of this.delaunay.neighbors(i)) {
      const cj = this._clip(j);
      if (cj) loop: for (let ai = 0, li = ci.length; ai < li; ai += 2) {
        for (let aj = 0, lj = cj.length; aj < lj; aj += 2) {
          if (ci[ai] === cj[aj] && ci[ai + 1] === cj[aj + 1] && ci[(ai + 2) % li] === cj[(aj + lj - 2) % lj] && ci[(ai + 3) % li] === cj[(aj + lj - 1) % lj]) {
            yield j;
            break loop;
          }
        }
      }
    }
  }
  _cell(i) {
    const { circumcenters, delaunay: { inedges, halfedges, triangles } } = this;
    const e0 = inedges[i];
    if (e0 === -1) return null;
    const points = [];
    let e = e0;
    do {
      const t = Math.floor(e / 3);
      points.push(circumcenters[t * 2], circumcenters[t * 2 + 1]);
      e = e % 3 === 2 ? e - 2 : e + 1;
      if (triangles[e] !== i) break;
      e = halfedges[e];
    } while (e !== e0 && e !== -1);
    return points;
  }
  _clip(i) {
    if (i === 0 && this.delaunay.hull.length === 1) {
      return [this.xmax, this.ymin, this.xmax, this.ymax, this.xmin, this.ymax, this.xmin, this.ymin];
    }
    const points = this._cell(i);
    if (points === null) return null;
    const { vectors: V } = this;
    const v2 = i * 4;
    return this._simplify(V[v2] || V[v2 + 1] ? this._clipInfinite(i, points, V[v2], V[v2 + 1], V[v2 + 2], V[v2 + 3]) : this._clipFinite(i, points));
  }
  _clipFinite(i, points) {
    const n = points.length;
    let P = null;
    let x06, y06, x12 = points[n - 2], y12 = points[n - 1];
    let c0, c1 = this._regioncode(x12, y12);
    let e0, e1 = 0;
    for (let j = 0; j < n; j += 2) {
      x06 = x12, y06 = y12, x12 = points[j], y12 = points[j + 1];
      c0 = c1, c1 = this._regioncode(x12, y12);
      if (c0 === 0 && c1 === 0) {
        e0 = e1, e1 = 0;
        if (P) P.push(x12, y12);
        else P = [x12, y12];
      } else {
        let S, sx0, sy0, sx1, sy1;
        if (c0 === 0) {
          if ((S = this._clipSegment(x06, y06, x12, y12, c0, c1)) === null) continue;
          [sx0, sy0, sx1, sy1] = S;
        } else {
          if ((S = this._clipSegment(x12, y12, x06, y06, c1, c0)) === null) continue;
          [sx1, sy1, sx0, sy0] = S;
          e0 = e1, e1 = this._edgecode(sx0, sy0);
          if (e0 && e1) this._edge(i, e0, e1, P, P.length);
          if (P) P.push(sx0, sy0);
          else P = [sx0, sy0];
        }
        e0 = e1, e1 = this._edgecode(sx1, sy1);
        if (e0 && e1) this._edge(i, e0, e1, P, P.length);
        if (P) P.push(sx1, sy1);
        else P = [sx1, sy1];
      }
    }
    if (P) {
      e0 = e1, e1 = this._edgecode(P[0], P[1]);
      if (e0 && e1) this._edge(i, e0, e1, P, P.length);
    } else if (this.contains(i, (this.xmin + this.xmax) / 2, (this.ymin + this.ymax) / 2)) {
      return [this.xmax, this.ymin, this.xmax, this.ymax, this.xmin, this.ymax, this.xmin, this.ymin];
    }
    return P;
  }
  _clipSegment(x06, y06, x12, y12, c0, c1) {
    const flip = c0 < c1;
    if (flip) [x06, y06, x12, y12, c0, c1] = [x12, y12, x06, y06, c1, c0];
    while (true) {
      if (c0 === 0 && c1 === 0) return flip ? [x12, y12, x06, y06] : [x06, y06, x12, y12];
      if (c0 & c1) return null;
      let x4, y4, c6 = c0 || c1;
      if (c6 & 8) x4 = x06 + (x12 - x06) * (this.ymax - y06) / (y12 - y06), y4 = this.ymax;
      else if (c6 & 4) x4 = x06 + (x12 - x06) * (this.ymin - y06) / (y12 - y06), y4 = this.ymin;
      else if (c6 & 2) y4 = y06 + (y12 - y06) * (this.xmax - x06) / (x12 - x06), x4 = this.xmax;
      else y4 = y06 + (y12 - y06) * (this.xmin - x06) / (x12 - x06), x4 = this.xmin;
      if (c0) x06 = x4, y06 = y4, c0 = this._regioncode(x06, y06);
      else x12 = x4, y12 = y4, c1 = this._regioncode(x12, y12);
    }
  }
  _clipInfinite(i, points, vx0, vy0, vxn, vyn) {
    let P = Array.from(points), p;
    if (p = this._project(P[0], P[1], vx0, vy0)) P.unshift(p[0], p[1]);
    if (p = this._project(P[P.length - 2], P[P.length - 1], vxn, vyn)) P.push(p[0], p[1]);
    if (P = this._clipFinite(i, P)) {
      for (let j = 0, n = P.length, c0, c1 = this._edgecode(P[n - 2], P[n - 1]); j < n; j += 2) {
        c0 = c1, c1 = this._edgecode(P[j], P[j + 1]);
        if (c0 && c1) j = this._edge(i, c0, c1, P, j), n = P.length;
      }
    } else if (this.contains(i, (this.xmin + this.xmax) / 2, (this.ymin + this.ymax) / 2)) {
      P = [this.xmin, this.ymin, this.xmax, this.ymin, this.xmax, this.ymax, this.xmin, this.ymax];
    }
    return P;
  }
  _edge(i, e0, e1, P, j) {
    while (e0 !== e1) {
      let x4, y4;
      switch (e0) {
        case 5:
          e0 = 4;
          continue;
        // top-left
        case 4:
          e0 = 6, x4 = this.xmax, y4 = this.ymin;
          break;
        // top
        case 6:
          e0 = 2;
          continue;
        // top-right
        case 2:
          e0 = 10, x4 = this.xmax, y4 = this.ymax;
          break;
        // right
        case 10:
          e0 = 8;
          continue;
        // bottom-right
        case 8:
          e0 = 9, x4 = this.xmin, y4 = this.ymax;
          break;
        // bottom
        case 9:
          e0 = 1;
          continue;
        // bottom-left
        case 1:
          e0 = 5, x4 = this.xmin, y4 = this.ymin;
          break;
      }
      if ((P[j] !== x4 || P[j + 1] !== y4) && this.contains(i, x4, y4)) {
        P.splice(j, 0, x4, y4), j += 2;
      }
    }
    return j;
  }
  _project(x06, y06, vx, vy) {
    let t = Infinity, c6, x4, y4;
    if (vy < 0) {
      if (y06 <= this.ymin) return null;
      if ((c6 = (this.ymin - y06) / vy) < t) y4 = this.ymin, x4 = x06 + (t = c6) * vx;
    } else if (vy > 0) {
      if (y06 >= this.ymax) return null;
      if ((c6 = (this.ymax - y06) / vy) < t) y4 = this.ymax, x4 = x06 + (t = c6) * vx;
    }
    if (vx > 0) {
      if (x06 >= this.xmax) return null;
      if ((c6 = (this.xmax - x06) / vx) < t) x4 = this.xmax, y4 = y06 + (t = c6) * vy;
    } else if (vx < 0) {
      if (x06 <= this.xmin) return null;
      if ((c6 = (this.xmin - x06) / vx) < t) x4 = this.xmin, y4 = y06 + (t = c6) * vy;
    }
    return [x4, y4];
  }
  _edgecode(x4, y4) {
    return (x4 === this.xmin ? 1 : x4 === this.xmax ? 2 : 0) | (y4 === this.ymin ? 4 : y4 === this.ymax ? 8 : 0);
  }
  _regioncode(x4, y4) {
    return (x4 < this.xmin ? 1 : x4 > this.xmax ? 2 : 0) | (y4 < this.ymin ? 4 : y4 > this.ymax ? 8 : 0);
  }
  _simplify(P) {
    if (P && P.length > 4) {
      for (let i = 0; i < P.length; i += 2) {
        const j = (i + 2) % P.length, k2 = (i + 4) % P.length;
        if (P[i] === P[j] && P[j] === P[k2] || P[i + 1] === P[j + 1] && P[j + 1] === P[k2 + 1]) {
          P.splice(j, 2), i -= 2;
        }
      }
      if (!P.length) P = null;
    }
    return P;
  }
};

// node_modules/d3-delaunay/src/delaunay.js
var tau3 = 2 * Math.PI;
var pow = Math.pow;
function pointX(p) {
  return p[0];
}
function pointY(p) {
  return p[1];
}
function collinear2(d) {
  const { triangles, coords } = d;
  for (let i = 0; i < triangles.length; i += 3) {
    const a4 = 2 * triangles[i], b = 2 * triangles[i + 1], c6 = 2 * triangles[i + 2], cross2 = (coords[c6] - coords[a4]) * (coords[b + 1] - coords[a4 + 1]) - (coords[b] - coords[a4]) * (coords[c6 + 1] - coords[a4 + 1]);
    if (cross2 > 1e-10) return false;
  }
  return true;
}
function jitter(x4, y4, r) {
  return [x4 + Math.sin(x4 + y4) * r, y4 + Math.cos(x4 - y4) * r];
}
var Delaunay = class _Delaunay {
  static from(points, fx = pointX, fy = pointY, that) {
    return new _Delaunay("length" in points ? flatArray(points, fx, fy, that) : Float64Array.from(flatIterable(points, fx, fy, that)));
  }
  constructor(points) {
    this._delaunator = new Delaunator(points);
    this.inedges = new Int32Array(points.length / 2);
    this._hullIndex = new Int32Array(points.length / 2);
    this.points = this._delaunator.coords;
    this._init();
  }
  update() {
    this._delaunator.update();
    this._init();
    return this;
  }
  _init() {
    const d = this._delaunator, points = this.points;
    if (d.hull && d.hull.length > 2 && collinear2(d)) {
      this.collinear = Int32Array.from({ length: points.length / 2 }, (_, i) => i).sort((i, j) => points[2 * i] - points[2 * j] || points[2 * i + 1] - points[2 * j + 1]);
      const e = this.collinear[0], f = this.collinear[this.collinear.length - 1], bounds = [points[2 * e], points[2 * e + 1], points[2 * f], points[2 * f + 1]], r = 1e-8 * Math.hypot(bounds[3] - bounds[1], bounds[2] - bounds[0]);
      for (let i = 0, n = points.length / 2; i < n; ++i) {
        const p = jitter(points[2 * i], points[2 * i + 1], r);
        points[2 * i] = p[0];
        points[2 * i + 1] = p[1];
      }
      this._delaunator = new Delaunator(points);
    } else {
      delete this.collinear;
    }
    const halfedges = this.halfedges = this._delaunator.halfedges;
    const hull = this.hull = this._delaunator.hull;
    const triangles = this.triangles = this._delaunator.triangles;
    const inedges = this.inedges.fill(-1);
    const hullIndex = this._hullIndex.fill(-1);
    for (let e = 0, n = halfedges.length; e < n; ++e) {
      const p = triangles[e % 3 === 2 ? e - 2 : e + 1];
      if (halfedges[e] === -1 || inedges[p] === -1) inedges[p] = e;
    }
    for (let i = 0, n = hull.length; i < n; ++i) {
      hullIndex[hull[i]] = i;
    }
    if (hull.length <= 2 && hull.length > 0) {
      this.triangles = new Int32Array(3).fill(-1);
      this.halfedges = new Int32Array(3).fill(-1);
      this.triangles[0] = hull[0];
      inedges[hull[0]] = 1;
      if (hull.length === 2) {
        inedges[hull[1]] = 0;
        this.triangles[1] = hull[1];
        this.triangles[2] = hull[1];
      }
    }
  }
  voronoi(bounds) {
    return new Voronoi(this, bounds);
  }
  *neighbors(i) {
    const { inedges, hull, _hullIndex, halfedges, triangles, collinear: collinear3 } = this;
    if (collinear3) {
      const l = collinear3.indexOf(i);
      if (l > 0) yield collinear3[l - 1];
      if (l < collinear3.length - 1) yield collinear3[l + 1];
      return;
    }
    const e0 = inedges[i];
    if (e0 === -1) return;
    let e = e0, p02 = -1;
    do {
      yield p02 = triangles[e];
      e = e % 3 === 2 ? e - 2 : e + 1;
      if (triangles[e] !== i) return;
      e = halfedges[e];
      if (e === -1) {
        const p = hull[(_hullIndex[i] + 1) % hull.length];
        if (p !== p02) yield p;
        return;
      }
    } while (e !== e0);
  }
  find(x4, y4, i = 0) {
    if ((x4 = +x4, x4 !== x4) || (y4 = +y4, y4 !== y4)) return -1;
    const i0 = i;
    let c6;
    while ((c6 = this._step(i, x4, y4)) >= 0 && c6 !== i && c6 !== i0) i = c6;
    return c6;
  }
  _step(i, x4, y4) {
    const { inedges, hull, _hullIndex, halfedges, triangles, points } = this;
    if (inedges[i] === -1 || !points.length) return (i + 1) % (points.length >> 1);
    let c6 = i;
    let dc = pow(x4 - points[i * 2], 2) + pow(y4 - points[i * 2 + 1], 2);
    const e0 = inedges[i];
    let e = e0;
    do {
      let t = triangles[e];
      const dt = pow(x4 - points[t * 2], 2) + pow(y4 - points[t * 2 + 1], 2);
      if (dt < dc) dc = dt, c6 = t;
      e = e % 3 === 2 ? e - 2 : e + 1;
      if (triangles[e] !== i) break;
      e = halfedges[e];
      if (e === -1) {
        e = hull[(_hullIndex[i] + 1) % hull.length];
        if (e !== t) {
          if (pow(x4 - points[e * 2], 2) + pow(y4 - points[e * 2 + 1], 2) < dc) return e;
        }
        break;
      }
    } while (e !== e0);
    return c6;
  }
  render(context) {
    const buffer = context == null ? context = new Path2() : void 0;
    const { points, halfedges, triangles } = this;
    for (let i = 0, n = halfedges.length; i < n; ++i) {
      const j = halfedges[i];
      if (j < i) continue;
      const ti = triangles[i] * 2;
      const tj = triangles[j] * 2;
      context.moveTo(points[ti], points[ti + 1]);
      context.lineTo(points[tj], points[tj + 1]);
    }
    this.renderHull(context);
    return buffer && buffer.value();
  }
  renderPoints(context, r) {
    if (r === void 0 && (!context || typeof context.moveTo !== "function")) r = context, context = null;
    r = r == void 0 ? 2 : +r;
    const buffer = context == null ? context = new Path2() : void 0;
    const { points } = this;
    for (let i = 0, n = points.length; i < n; i += 2) {
      const x4 = points[i], y4 = points[i + 1];
      context.moveTo(x4 + r, y4);
      context.arc(x4, y4, r, 0, tau3);
    }
    return buffer && buffer.value();
  }
  renderHull(context) {
    const buffer = context == null ? context = new Path2() : void 0;
    const { hull, points } = this;
    const h = hull[0] * 2, n = hull.length;
    context.moveTo(points[h], points[h + 1]);
    for (let i = 1; i < n; ++i) {
      const h2 = 2 * hull[i];
      context.lineTo(points[h2], points[h2 + 1]);
    }
    context.closePath();
    return buffer && buffer.value();
  }
  hullPolygon() {
    const polygon = new Polygon();
    this.renderHull(polygon);
    return polygon.value();
  }
  renderTriangle(i, context) {
    const buffer = context == null ? context = new Path2() : void 0;
    const { points, triangles } = this;
    const t02 = triangles[i *= 3] * 2;
    const t12 = triangles[i + 1] * 2;
    const t2 = triangles[i + 2] * 2;
    context.moveTo(points[t02], points[t02 + 1]);
    context.lineTo(points[t12], points[t12 + 1]);
    context.lineTo(points[t2], points[t2 + 1]);
    context.closePath();
    return buffer && buffer.value();
  }
  *trianglePolygons() {
    const { triangles } = this;
    for (let i = 0, n = triangles.length / 3; i < n; ++i) {
      yield this.trianglePolygon(i);
    }
  }
  trianglePolygon(i) {
    const polygon = new Polygon();
    this.renderTriangle(i, polygon);
    return polygon.value();
  }
};
function flatArray(points, fx, fy, that) {
  const n = points.length;
  const array3 = new Float64Array(n * 2);
  for (let i = 0; i < n; ++i) {
    const p = points[i];
    array3[i * 2] = fx.call(that, p, i, points);
    array3[i * 2 + 1] = fy.call(that, p, i, points);
  }
  return array3;
}
function* flatIterable(points, fx, fy, that) {
  let i = 0;
  for (const p of points) {
    yield fx.call(that, p, i, points);
    yield fy.call(that, p, i, points);
    ++i;
  }
}

// node_modules/d3-dsv/src/dsv.js
var EOL = {};
var EOF = {};
var QUOTE = 34;
var NEWLINE = 10;
var RETURN = 13;
function objectConverter(columns) {
  return new Function("d", "return {" + columns.map(function(name, i) {
    return JSON.stringify(name) + ": d[" + i + '] || ""';
  }).join(",") + "}");
}
function customConverter(columns, f) {
  var object2 = objectConverter(columns);
  return function(row, i) {
    return f(object2(row), i, columns);
  };
}
function inferColumns(rows) {
  var columnSet = /* @__PURE__ */ Object.create(null), columns = [];
  rows.forEach(function(row) {
    for (var column in row) {
      if (!(column in columnSet)) {
        columns.push(columnSet[column] = column);
      }
    }
  });
  return columns;
}
function pad(value, width) {
  var s2 = value + "", length3 = s2.length;
  return length3 < width ? new Array(width - length3 + 1).join(0) + s2 : s2;
}
function formatYear(year) {
  return year < 0 ? "-" + pad(-year, 6) : year > 9999 ? "+" + pad(year, 6) : pad(year, 4);
}
function formatDate(date2) {
  var hours = date2.getUTCHours(), minutes = date2.getUTCMinutes(), seconds2 = date2.getUTCSeconds(), milliseconds2 = date2.getUTCMilliseconds();
  return isNaN(date2) ? "Invalid Date" : formatYear(date2.getUTCFullYear(), 4) + "-" + pad(date2.getUTCMonth() + 1, 2) + "-" + pad(date2.getUTCDate(), 2) + (milliseconds2 ? "T" + pad(hours, 2) + ":" + pad(minutes, 2) + ":" + pad(seconds2, 2) + "." + pad(milliseconds2, 3) + "Z" : seconds2 ? "T" + pad(hours, 2) + ":" + pad(minutes, 2) + ":" + pad(seconds2, 2) + "Z" : minutes || hours ? "T" + pad(hours, 2) + ":" + pad(minutes, 2) + "Z" : "");
}
function dsv_default(delimiter) {
  var reFormat = new RegExp('["' + delimiter + "\n\r]"), DELIMITER = delimiter.charCodeAt(0);
  function parse(text, f) {
    var convert, columns, rows = parseRows(text, function(row, i) {
      if (convert) return convert(row, i - 1);
      columns = row, convert = f ? customConverter(row, f) : objectConverter(row);
    });
    rows.columns = columns || [];
    return rows;
  }
  function parseRows(text, f) {
    var rows = [], N = text.length, I = 0, n = 0, t, eof = N <= 0, eol = false;
    if (text.charCodeAt(N - 1) === NEWLINE) --N;
    if (text.charCodeAt(N - 1) === RETURN) --N;
    function token() {
      if (eof) return EOF;
      if (eol) return eol = false, EOL;
      var i, j = I, c6;
      if (text.charCodeAt(j) === QUOTE) {
        while (I++ < N && text.charCodeAt(I) !== QUOTE || text.charCodeAt(++I) === QUOTE) ;
        if ((i = I) >= N) eof = true;
        else if ((c6 = text.charCodeAt(I++)) === NEWLINE) eol = true;
        else if (c6 === RETURN) {
          eol = true;
          if (text.charCodeAt(I) === NEWLINE) ++I;
        }
        return text.slice(j + 1, i - 1).replace(/""/g, '"');
      }
      while (I < N) {
        if ((c6 = text.charCodeAt(i = I++)) === NEWLINE) eol = true;
        else if (c6 === RETURN) {
          eol = true;
          if (text.charCodeAt(I) === NEWLINE) ++I;
        } else if (c6 !== DELIMITER) continue;
        return text.slice(j, i);
      }
      return eof = true, text.slice(j, N);
    }
    while ((t = token()) !== EOF) {
      var row = [];
      while (t !== EOL && t !== EOF) row.push(t), t = token();
      if (f && (row = f(row, n++)) == null) continue;
      rows.push(row);
    }
    return rows;
  }
  function preformatBody(rows, columns) {
    return rows.map(function(row) {
      return columns.map(function(column) {
        return formatValue(row[column]);
      }).join(delimiter);
    });
  }
  function format2(rows, columns) {
    if (columns == null) columns = inferColumns(rows);
    return [columns.map(formatValue).join(delimiter)].concat(preformatBody(rows, columns)).join("\n");
  }
  function formatBody(rows, columns) {
    if (columns == null) columns = inferColumns(rows);
    return preformatBody(rows, columns).join("\n");
  }
  function formatRows(rows) {
    return rows.map(formatRow).join("\n");
  }
  function formatRow(row) {
    return row.map(formatValue).join(delimiter);
  }
  function formatValue(value) {
    return value == null ? "" : value instanceof Date ? formatDate(value) : reFormat.test(value += "") ? '"' + value.replace(/"/g, '""') + '"' : value;
  }
  return {
    parse,
    parseRows,
    format: format2,
    formatBody,
    formatRows,
    formatRow,
    formatValue
  };
}

// node_modules/d3-dsv/src/csv.js
var csv = dsv_default(",");
var csvParse = csv.parse;
var csvParseRows = csv.parseRows;
var csvFormat = csv.format;
var csvFormatBody = csv.formatBody;
var csvFormatRows = csv.formatRows;
var csvFormatRow = csv.formatRow;
var csvFormatValue = csv.formatValue;

// node_modules/d3-dsv/src/tsv.js
var tsv = dsv_default("	");
var tsvParse = tsv.parse;
var tsvParseRows = tsv.parseRows;
var tsvFormat = tsv.format;
var tsvFormatBody = tsv.formatBody;
var tsvFormatRows = tsv.formatRows;
var tsvFormatRow = tsv.formatRow;
var tsvFormatValue = tsv.formatValue;

// node_modules/d3-dsv/src/autoType.js
function autoType(object2) {
  for (var key in object2) {
    var value = object2[key].trim(), number5, m3;
    if (!value) value = null;
    else if (value === "true") value = true;
    else if (value === "false") value = false;
    else if (value === "NaN") value = NaN;
    else if (!isNaN(number5 = +value)) value = number5;
    else if (m3 = value.match(/^([-+]\d{2})?\d{4}(-\d{2}(-\d{2})?)?(T\d{2}:\d{2}(:\d{2}(\.\d{3})?)?(Z|[-+]\d{2}:\d{2})?)?$/)) {
      if (fixtz && !!m3[4] && !m3[7]) value = value.replace(/-/g, "/").replace(/T/, " ");
      value = new Date(value);
    } else continue;
    object2[key] = value;
  }
  return object2;
}
var fixtz = (/* @__PURE__ */ new Date("2019-01-01T00:00")).getHours() || (/* @__PURE__ */ new Date("2019-07-01T00:00")).getHours();

// node_modules/d3-fetch/src/blob.js
function responseBlob(response) {
  if (!response.ok) throw new Error(response.status + " " + response.statusText);
  return response.blob();
}
function blob_default(input, init) {
  return fetch(input, init).then(responseBlob);
}

// node_modules/d3-fetch/src/buffer.js
function responseArrayBuffer(response) {
  if (!response.ok) throw new Error(response.status + " " + response.statusText);
  return response.arrayBuffer();
}
function buffer_default(input, init) {
  return fetch(input, init).then(responseArrayBuffer);
}

// node_modules/d3-fetch/src/text.js
function responseText(response) {
  if (!response.ok) throw new Error(response.status + " " + response.statusText);
  return response.text();
}
function text_default(input, init) {
  return fetch(input, init).then(responseText);
}

// node_modules/d3-fetch/src/dsv.js
function dsvParse(parse) {
  return function(input, init, row) {
    if (arguments.length === 2 && typeof init === "function") row = init, init = void 0;
    return text_default(input, init).then(function(response) {
      return parse(response, row);
    });
  };
}
function dsv(delimiter, input, init, row) {
  if (arguments.length === 3 && typeof init === "function") row = init, init = void 0;
  var format2 = dsv_default(delimiter);
  return text_default(input, init).then(function(response) {
    return format2.parse(response, row);
  });
}
var csv2 = dsvParse(csvParse);
var tsv2 = dsvParse(tsvParse);

// node_modules/d3-fetch/src/image.js
function image_default(input, init) {
  return new Promise(function(resolve, reject) {
    var image = new Image();
    for (var key in init) image[key] = init[key];
    image.onerror = reject;
    image.onload = function() {
      resolve(image);
    };
    image.src = input;
  });
}

// node_modules/d3-fetch/src/json.js
function responseJson(response) {
  if (!response.ok) throw new Error(response.status + " " + response.statusText);
  if (response.status === 204 || response.status === 205) return;
  return response.json();
}
function json_default(input, init) {
  return fetch(input, init).then(responseJson);
}

// node_modules/d3-fetch/src/xml.js
function parser(type2) {
  return (input, init) => text_default(input, init).then((text) => new DOMParser().parseFromString(text, type2));
}
var xml_default = parser("application/xml");
var html = parser("text/html");
var svg = parser("image/svg+xml");

// node_modules/d3-force/src/center.js
function center_default(x4, y4) {
  var nodes, strength = 1;
  if (x4 == null) x4 = 0;
  if (y4 == null) y4 = 0;
  function force() {
    var i, n = nodes.length, node, sx = 0, sy = 0;
    for (i = 0; i < n; ++i) {
      node = nodes[i], sx += node.x, sy += node.y;
    }
    for (sx = (sx / n - x4) * strength, sy = (sy / n - y4) * strength, i = 0; i < n; ++i) {
      node = nodes[i], node.x -= sx, node.y -= sy;
    }
  }
  force.initialize = function(_) {
    nodes = _;
  };
  force.x = function(_) {
    return arguments.length ? (x4 = +_, force) : x4;
  };
  force.y = function(_) {
    return arguments.length ? (y4 = +_, force) : y4;
  };
  force.strength = function(_) {
    return arguments.length ? (strength = +_, force) : strength;
  };
  return force;
}

// node_modules/d3-quadtree/src/add.js
function add_default(d) {
  const x4 = +this._x.call(null, d), y4 = +this._y.call(null, d);
  return add(this.cover(x4, y4), x4, y4, d);
}
function add(tree, x4, y4, d) {
  if (isNaN(x4) || isNaN(y4)) return tree;
  var parent, node = tree._root, leaf = { data: d }, x06 = tree._x0, y06 = tree._y0, x12 = tree._x1, y12 = tree._y1, xm, ym, xp, yp, right2, bottom2, i, j;
  if (!node) return tree._root = leaf, tree;
  while (node.length) {
    if (right2 = x4 >= (xm = (x06 + x12) / 2)) x06 = xm;
    else x12 = xm;
    if (bottom2 = y4 >= (ym = (y06 + y12) / 2)) y06 = ym;
    else y12 = ym;
    if (parent = node, !(node = node[i = bottom2 << 1 | right2])) return parent[i] = leaf, tree;
  }
  xp = +tree._x.call(null, node.data);
  yp = +tree._y.call(null, node.data);
  if (x4 === xp && y4 === yp) return leaf.next = node, parent ? parent[i] = leaf : tree._root = leaf, tree;
  do {
    parent = parent ? parent[i] = new Array(4) : tree._root = new Array(4);
    if (right2 = x4 >= (xm = (x06 + x12) / 2)) x06 = xm;
    else x12 = xm;
    if (bottom2 = y4 >= (ym = (y06 + y12) / 2)) y06 = ym;
    else y12 = ym;
  } while ((i = bottom2 << 1 | right2) === (j = (yp >= ym) << 1 | xp >= xm));
  return parent[j] = node, parent[i] = leaf, tree;
}
function addAll(data) {
  var d, i, n = data.length, x4, y4, xz = new Array(n), yz = new Array(n), x06 = Infinity, y06 = Infinity, x12 = -Infinity, y12 = -Infinity;
  for (i = 0; i < n; ++i) {
    if (isNaN(x4 = +this._x.call(null, d = data[i])) || isNaN(y4 = +this._y.call(null, d))) continue;
    xz[i] = x4;
    yz[i] = y4;
    if (x4 < x06) x06 = x4;
    if (x4 > x12) x12 = x4;
    if (y4 < y06) y06 = y4;
    if (y4 > y12) y12 = y4;
  }
  if (x06 > x12 || y06 > y12) return this;
  this.cover(x06, y06).cover(x12, y12);
  for (i = 0; i < n; ++i) {
    add(this, xz[i], yz[i], data[i]);
  }
  return this;
}

// node_modules/d3-quadtree/src/cover.js
function cover_default(x4, y4) {
  if (isNaN(x4 = +x4) || isNaN(y4 = +y4)) return this;
  var x06 = this._x0, y06 = this._y0, x12 = this._x1, y12 = this._y1;
  if (isNaN(x06)) {
    x12 = (x06 = Math.floor(x4)) + 1;
    y12 = (y06 = Math.floor(y4)) + 1;
  } else {
    var z = x12 - x06 || 1, node = this._root, parent, i;
    while (x06 > x4 || x4 >= x12 || y06 > y4 || y4 >= y12) {
      i = (y4 < y06) << 1 | x4 < x06;
      parent = new Array(4), parent[i] = node, node = parent, z *= 2;
      switch (i) {
        case 0:
          x12 = x06 + z, y12 = y06 + z;
          break;
        case 1:
          x06 = x12 - z, y12 = y06 + z;
          break;
        case 2:
          x12 = x06 + z, y06 = y12 - z;
          break;
        case 3:
          x06 = x12 - z, y06 = y12 - z;
          break;
      }
    }
    if (this._root && this._root.length) this._root = node;
  }
  this._x0 = x06;
  this._y0 = y06;
  this._x1 = x12;
  this._y1 = y12;
  return this;
}

// node_modules/d3-quadtree/src/data.js
function data_default() {
  var data = [];
  this.visit(function(node) {
    if (!node.length) do
      data.push(node.data);
    while (node = node.next);
  });
  return data;
}

// node_modules/d3-quadtree/src/extent.js
function extent_default(_) {
  return arguments.length ? this.cover(+_[0][0], +_[0][1]).cover(+_[1][0], +_[1][1]) : isNaN(this._x0) ? void 0 : [[this._x0, this._y0], [this._x1, this._y1]];
}

// node_modules/d3-quadtree/src/quad.js
function quad_default(node, x06, y06, x12, y12) {
  this.node = node;
  this.x0 = x06;
  this.y0 = y06;
  this.x1 = x12;
  this.y1 = y12;
}

// node_modules/d3-quadtree/src/find.js
function find_default(x4, y4, radius) {
  var data, x06 = this._x0, y06 = this._y0, x12, y12, x22, y22, x32 = this._x1, y32 = this._y1, quads = [], node = this._root, q, i;
  if (node) quads.push(new quad_default(node, x06, y06, x32, y32));
  if (radius == null) radius = Infinity;
  else {
    x06 = x4 - radius, y06 = y4 - radius;
    x32 = x4 + radius, y32 = y4 + radius;
    radius *= radius;
  }
  while (q = quads.pop()) {
    if (!(node = q.node) || (x12 = q.x0) > x32 || (y12 = q.y0) > y32 || (x22 = q.x1) < x06 || (y22 = q.y1) < y06) continue;
    if (node.length) {
      var xm = (x12 + x22) / 2, ym = (y12 + y22) / 2;
      quads.push(
        new quad_default(node[3], xm, ym, x22, y22),
        new quad_default(node[2], x12, ym, xm, y22),
        new quad_default(node[1], xm, y12, x22, ym),
        new quad_default(node[0], x12, y12, xm, ym)
      );
      if (i = (y4 >= ym) << 1 | x4 >= xm) {
        q = quads[quads.length - 1];
        quads[quads.length - 1] = quads[quads.length - 1 - i];
        quads[quads.length - 1 - i] = q;
      }
    } else {
      var dx = x4 - +this._x.call(null, node.data), dy = y4 - +this._y.call(null, node.data), d2 = dx * dx + dy * dy;
      if (d2 < radius) {
        var d = Math.sqrt(radius = d2);
        x06 = x4 - d, y06 = y4 - d;
        x32 = x4 + d, y32 = y4 + d;
        data = node.data;
      }
    }
  }
  return data;
}

// node_modules/d3-quadtree/src/remove.js
function remove_default(d) {
  if (isNaN(x4 = +this._x.call(null, d)) || isNaN(y4 = +this._y.call(null, d))) return this;
  var parent, node = this._root, retainer, previous, next, x06 = this._x0, y06 = this._y0, x12 = this._x1, y12 = this._y1, x4, y4, xm, ym, right2, bottom2, i, j;
  if (!node) return this;
  if (node.length) while (true) {
    if (right2 = x4 >= (xm = (x06 + x12) / 2)) x06 = xm;
    else x12 = xm;
    if (bottom2 = y4 >= (ym = (y06 + y12) / 2)) y06 = ym;
    else y12 = ym;
    if (!(parent = node, node = node[i = bottom2 << 1 | right2])) return this;
    if (!node.length) break;
    if (parent[i + 1 & 3] || parent[i + 2 & 3] || parent[i + 3 & 3]) retainer = parent, j = i;
  }
  while (node.data !== d) if (!(previous = node, node = node.next)) return this;
  if (next = node.next) delete node.next;
  if (previous) return next ? previous.next = next : delete previous.next, this;
  if (!parent) return this._root = next, this;
  next ? parent[i] = next : delete parent[i];
  if ((node = parent[0] || parent[1] || parent[2] || parent[3]) && node === (parent[3] || parent[2] || parent[1] || parent[0]) && !node.length) {
    if (retainer) retainer[j] = node;
    else this._root = node;
  }
  return this;
}
function removeAll(data) {
  for (var i = 0, n = data.length; i < n; ++i) this.remove(data[i]);
  return this;
}

// node_modules/d3-quadtree/src/root.js
function root_default() {
  return this._root;
}

// node_modules/d3-quadtree/src/size.js
function size_default() {
  var size = 0;
  this.visit(function(node) {
    if (!node.length) do
      ++size;
    while (node = node.next);
  });
  return size;
}

// node_modules/d3-quadtree/src/visit.js
function visit_default(callback) {
  var quads = [], q, node = this._root, child, x06, y06, x12, y12;
  if (node) quads.push(new quad_default(node, this._x0, this._y0, this._x1, this._y1));
  while (q = quads.pop()) {
    if (!callback(node = q.node, x06 = q.x0, y06 = q.y0, x12 = q.x1, y12 = q.y1) && node.length) {
      var xm = (x06 + x12) / 2, ym = (y06 + y12) / 2;
      if (child = node[3]) quads.push(new quad_default(child, xm, ym, x12, y12));
      if (child = node[2]) quads.push(new quad_default(child, x06, ym, xm, y12));
      if (child = node[1]) quads.push(new quad_default(child, xm, y06, x12, ym));
      if (child = node[0]) quads.push(new quad_default(child, x06, y06, xm, ym));
    }
  }
  return this;
}

// node_modules/d3-quadtree/src/visitAfter.js
function visitAfter_default(callback) {
  var quads = [], next = [], q;
  if (this._root) quads.push(new quad_default(this._root, this._x0, this._y0, this._x1, this._y1));
  while (q = quads.pop()) {
    var node = q.node;
    if (node.length) {
      var child, x06 = q.x0, y06 = q.y0, x12 = q.x1, y12 = q.y1, xm = (x06 + x12) / 2, ym = (y06 + y12) / 2;
      if (child = node[0]) quads.push(new quad_default(child, x06, y06, xm, ym));
      if (child = node[1]) quads.push(new quad_default(child, xm, y06, x12, ym));
      if (child = node[2]) quads.push(new quad_default(child, x06, ym, xm, y12));
      if (child = node[3]) quads.push(new quad_default(child, xm, ym, x12, y12));
    }
    next.push(q);
  }
  while (q = next.pop()) {
    callback(q.node, q.x0, q.y0, q.x1, q.y1);
  }
  return this;
}

// node_modules/d3-quadtree/src/x.js
function defaultX2(d) {
  return d[0];
}
function x_default(_) {
  return arguments.length ? (this._x = _, this) : this._x;
}

// node_modules/d3-quadtree/src/y.js
function defaultY2(d) {
  return d[1];
}
function y_default(_) {
  return arguments.length ? (this._y = _, this) : this._y;
}

// node_modules/d3-quadtree/src/quadtree.js
function quadtree(nodes, x4, y4) {
  var tree = new Quadtree(x4 == null ? defaultX2 : x4, y4 == null ? defaultY2 : y4, NaN, NaN, NaN, NaN);
  return nodes == null ? tree : tree.addAll(nodes);
}
function Quadtree(x4, y4, x06, y06, x12, y12) {
  this._x = x4;
  this._y = y4;
  this._x0 = x06;
  this._y0 = y06;
  this._x1 = x12;
  this._y1 = y12;
  this._root = void 0;
}
function leaf_copy(leaf) {
  var copy3 = { data: leaf.data }, next = copy3;
  while (leaf = leaf.next) next = next.next = { data: leaf.data };
  return copy3;
}
var treeProto = quadtree.prototype = Quadtree.prototype;
treeProto.copy = function() {
  var copy3 = new Quadtree(this._x, this._y, this._x0, this._y0, this._x1, this._y1), node = this._root, nodes, child;
  if (!node) return copy3;
  if (!node.length) return copy3._root = leaf_copy(node), copy3;
  nodes = [{ source: node, target: copy3._root = new Array(4) }];
  while (node = nodes.pop()) {
    for (var i = 0; i < 4; ++i) {
      if (child = node.source[i]) {
        if (child.length) nodes.push({ source: child, target: node.target[i] = new Array(4) });
        else node.target[i] = leaf_copy(child);
      }
    }
  }
  return copy3;
};
treeProto.add = add_default;
treeProto.addAll = addAll;
treeProto.cover = cover_default;
treeProto.data = data_default;
treeProto.extent = extent_default;
treeProto.find = find_default;
treeProto.remove = remove_default;
treeProto.removeAll = removeAll;
treeProto.root = root_default;
treeProto.size = size_default;
treeProto.visit = visit_default;
treeProto.visitAfter = visitAfter_default;
treeProto.x = x_default;
treeProto.y = y_default;

// node_modules/d3-force/src/constant.js
function constant_default4(x4) {
  return function() {
    return x4;
  };
}

// node_modules/d3-force/src/jiggle.js
function jiggle_default(random) {
  return (random() - 0.5) * 1e-6;
}

// node_modules/d3-force/src/collide.js
function x(d) {
  return d.x + d.vx;
}
function y(d) {
  return d.y + d.vy;
}
function collide_default(radius) {
  var nodes, radii, random, strength = 1, iterations2 = 1;
  if (typeof radius !== "function") radius = constant_default4(radius == null ? 1 : +radius);
  function force() {
    var i, n = nodes.length, tree, node, xi, yi, ri, ri2;
    for (var k2 = 0; k2 < iterations2; ++k2) {
      tree = quadtree(nodes, x, y).visitAfter(prepare);
      for (i = 0; i < n; ++i) {
        node = nodes[i];
        ri = radii[node.index], ri2 = ri * ri;
        xi = node.x + node.vx;
        yi = node.y + node.vy;
        tree.visit(apply);
      }
    }
    function apply(quad, x06, y06, x12, y12) {
      var data = quad.data, rj = quad.r, r = ri + rj;
      if (data) {
        if (data.index > node.index) {
          var x4 = xi - data.x - data.vx, y4 = yi - data.y - data.vy, l = x4 * x4 + y4 * y4;
          if (l < r * r) {
            if (x4 === 0) x4 = jiggle_default(random), l += x4 * x4;
            if (y4 === 0) y4 = jiggle_default(random), l += y4 * y4;
            l = (r - (l = Math.sqrt(l))) / l * strength;
            node.vx += (x4 *= l) * (r = (rj *= rj) / (ri2 + rj));
            node.vy += (y4 *= l) * r;
            data.vx -= x4 * (r = 1 - r);
            data.vy -= y4 * r;
          }
        }
        return;
      }
      return x06 > xi + r || x12 < xi - r || y06 > yi + r || y12 < yi - r;
    }
  }
  function prepare(quad) {
    if (quad.data) return quad.r = radii[quad.data.index];
    for (var i = quad.r = 0; i < 4; ++i) {
      if (quad[i] && quad[i].r > quad.r) {
        quad.r = quad[i].r;
      }
    }
  }
  function initialize() {
    if (!nodes) return;
    var i, n = nodes.length, node;
    radii = new Array(n);
    for (i = 0; i < n; ++i) node = nodes[i], radii[node.index] = +radius(node, i, nodes);
  }
  force.initialize = function(_nodes, _random) {
    nodes = _nodes;
    random = _random;
    initialize();
  };
  force.iterations = function(_) {
    return arguments.length ? (iterations2 = +_, force) : iterations2;
  };
  force.strength = function(_) {
    return arguments.length ? (strength = +_, force) : strength;
  };
  force.radius = function(_) {
    return arguments.length ? (radius = typeof _ === "function" ? _ : constant_default4(+_), initialize(), force) : radius;
  };
  return force;
}

// node_modules/d3-force/src/link.js
function index2(d) {
  return d.index;
}
function find(nodeById, nodeId) {
  var node = nodeById.get(nodeId);
  if (!node) throw new Error("node not found: " + nodeId);
  return node;
}
function link_default(links) {
  var id = index2, strength = defaultStrength, strengths, distance = constant_default4(30), distances, nodes, count3, bias, random, iterations2 = 1;
  if (links == null) links = [];
  function defaultStrength(link3) {
    return 1 / Math.min(count3[link3.source.index], count3[link3.target.index]);
  }
  function force(alpha) {
    for (var k2 = 0, n = links.length; k2 < iterations2; ++k2) {
      for (var i = 0, link3, source, target, x4, y4, l, b; i < n; ++i) {
        link3 = links[i], source = link3.source, target = link3.target;
        x4 = target.x + target.vx - source.x - source.vx || jiggle_default(random);
        y4 = target.y + target.vy - source.y - source.vy || jiggle_default(random);
        l = Math.sqrt(x4 * x4 + y4 * y4);
        l = (l - distances[i]) / l * alpha * strengths[i];
        x4 *= l, y4 *= l;
        target.vx -= x4 * (b = bias[i]);
        target.vy -= y4 * b;
        source.vx += x4 * (b = 1 - b);
        source.vy += y4 * b;
      }
    }
  }
  function initialize() {
    if (!nodes) return;
    var i, n = nodes.length, m3 = links.length, nodeById = new Map(nodes.map((d, i2) => [id(d, i2, nodes), d])), link3;
    for (i = 0, count3 = new Array(n); i < m3; ++i) {
      link3 = links[i], link3.index = i;
      if (typeof link3.source !== "object") link3.source = find(nodeById, link3.source);
      if (typeof link3.target !== "object") link3.target = find(nodeById, link3.target);
      count3[link3.source.index] = (count3[link3.source.index] || 0) + 1;
      count3[link3.target.index] = (count3[link3.target.index] || 0) + 1;
    }
    for (i = 0, bias = new Array(m3); i < m3; ++i) {
      link3 = links[i], bias[i] = count3[link3.source.index] / (count3[link3.source.index] + count3[link3.target.index]);
    }
    strengths = new Array(m3), initializeStrength();
    distances = new Array(m3), initializeDistance();
  }
  function initializeStrength() {
    if (!nodes) return;
    for (var i = 0, n = links.length; i < n; ++i) {
      strengths[i] = +strength(links[i], i, links);
    }
  }
  function initializeDistance() {
    if (!nodes) return;
    for (var i = 0, n = links.length; i < n; ++i) {
      distances[i] = +distance(links[i], i, links);
    }
  }
  force.initialize = function(_nodes, _random) {
    nodes = _nodes;
    random = _random;
    initialize();
  };
  force.links = function(_) {
    return arguments.length ? (links = _, initialize(), force) : links;
  };
  force.id = function(_) {
    return arguments.length ? (id = _, force) : id;
  };
  force.iterations = function(_) {
    return arguments.length ? (iterations2 = +_, force) : iterations2;
  };
  force.strength = function(_) {
    return arguments.length ? (strength = typeof _ === "function" ? _ : constant_default4(+_), initializeStrength(), force) : strength;
  };
  force.distance = function(_) {
    return arguments.length ? (distance = typeof _ === "function" ? _ : constant_default4(+_), initializeDistance(), force) : distance;
  };
  return force;
}

// node_modules/d3-force/src/lcg.js
var a = 1664525;
var c = 1013904223;
var m = 4294967296;
function lcg_default() {
  let s2 = 1;
  return () => (s2 = (a * s2 + c) % m) / m;
}

// node_modules/d3-force/src/simulation.js
function x2(d) {
  return d.x;
}
function y2(d) {
  return d.y;
}
var initialRadius = 10;
var initialAngle = Math.PI * (3 - Math.sqrt(5));
function simulation_default(nodes) {
  var simulation, alpha = 1, alphaMin = 1e-3, alphaDecay = 1 - Math.pow(alphaMin, 1 / 300), alphaTarget = 0, velocityDecay = 0.6, forces = /* @__PURE__ */ new Map(), stepper = timer(step), event = dispatch_default("tick", "end"), random = lcg_default();
  if (nodes == null) nodes = [];
  function step() {
    tick();
    event.call("tick", simulation);
    if (alpha < alphaMin) {
      stepper.stop();
      event.call("end", simulation);
    }
  }
  function tick(iterations2) {
    var i, n = nodes.length, node;
    if (iterations2 === void 0) iterations2 = 1;
    for (var k2 = 0; k2 < iterations2; ++k2) {
      alpha += (alphaTarget - alpha) * alphaDecay;
      forces.forEach(function(force) {
        force(alpha);
      });
      for (i = 0; i < n; ++i) {
        node = nodes[i];
        if (node.fx == null) node.x += node.vx *= velocityDecay;
        else node.x = node.fx, node.vx = 0;
        if (node.fy == null) node.y += node.vy *= velocityDecay;
        else node.y = node.fy, node.vy = 0;
      }
    }
    return simulation;
  }
  function initializeNodes() {
    for (var i = 0, n = nodes.length, node; i < n; ++i) {
      node = nodes[i], node.index = i;
      if (node.fx != null) node.x = node.fx;
      if (node.fy != null) node.y = node.fy;
      if (isNaN(node.x) || isNaN(node.y)) {
        var radius = initialRadius * Math.sqrt(0.5 + i), angle2 = i * initialAngle;
        node.x = radius * Math.cos(angle2);
        node.y = radius * Math.sin(angle2);
      }
      if (isNaN(node.vx) || isNaN(node.vy)) {
        node.vx = node.vy = 0;
      }
    }
  }
  function initializeForce(force) {
    if (force.initialize) force.initialize(nodes, random);
    return force;
  }
  initializeNodes();
  return simulation = {
    tick,
    restart: function() {
      return stepper.restart(step), simulation;
    },
    stop: function() {
      return stepper.stop(), simulation;
    },
    nodes: function(_) {
      return arguments.length ? (nodes = _, initializeNodes(), forces.forEach(initializeForce), simulation) : nodes;
    },
    alpha: function(_) {
      return arguments.length ? (alpha = +_, simulation) : alpha;
    },
    alphaMin: function(_) {
      return arguments.length ? (alphaMin = +_, simulation) : alphaMin;
    },
    alphaDecay: function(_) {
      return arguments.length ? (alphaDecay = +_, simulation) : +alphaDecay;
    },
    alphaTarget: function(_) {
      return arguments.length ? (alphaTarget = +_, simulation) : alphaTarget;
    },
    velocityDecay: function(_) {
      return arguments.length ? (velocityDecay = 1 - _, simulation) : 1 - velocityDecay;
    },
    randomSource: function(_) {
      return arguments.length ? (random = _, forces.forEach(initializeForce), simulation) : random;
    },
    force: function(name, _) {
      return arguments.length > 1 ? (_ == null ? forces.delete(name) : forces.set(name, initializeForce(_)), simulation) : forces.get(name);
    },
    find: function(x4, y4, radius) {
      var i = 0, n = nodes.length, dx, dy, d2, node, closest;
      if (radius == null) radius = Infinity;
      else radius *= radius;
      for (i = 0; i < n; ++i) {
        node = nodes[i];
        dx = x4 - node.x;
        dy = y4 - node.y;
        d2 = dx * dx + dy * dy;
        if (d2 < radius) closest = node, radius = d2;
      }
      return closest;
    },
    on: function(name, _) {
      return arguments.length > 1 ? (event.on(name, _), simulation) : event.on(name);
    }
  };
}

// node_modules/d3-force/src/manyBody.js
function manyBody_default() {
  var nodes, node, random, alpha, strength = constant_default4(-30), strengths, distanceMin2 = 1, distanceMax2 = Infinity, theta2 = 0.81;
  function force(_) {
    var i, n = nodes.length, tree = quadtree(nodes, x2, y2).visitAfter(accumulate);
    for (alpha = _, i = 0; i < n; ++i) node = nodes[i], tree.visit(apply);
  }
  function initialize() {
    if (!nodes) return;
    var i, n = nodes.length, node2;
    strengths = new Array(n);
    for (i = 0; i < n; ++i) node2 = nodes[i], strengths[node2.index] = +strength(node2, i, nodes);
  }
  function accumulate(quad) {
    var strength2 = 0, q, c6, weight = 0, x4, y4, i;
    if (quad.length) {
      for (x4 = y4 = i = 0; i < 4; ++i) {
        if ((q = quad[i]) && (c6 = Math.abs(q.value))) {
          strength2 += q.value, weight += c6, x4 += c6 * q.x, y4 += c6 * q.y;
        }
      }
      quad.x = x4 / weight;
      quad.y = y4 / weight;
    } else {
      q = quad;
      q.x = q.data.x;
      q.y = q.data.y;
      do
        strength2 += strengths[q.data.index];
      while (q = q.next);
    }
    quad.value = strength2;
  }
  function apply(quad, x12, _, x22) {
    if (!quad.value) return true;
    var x4 = quad.x - node.x, y4 = quad.y - node.y, w = x22 - x12, l = x4 * x4 + y4 * y4;
    if (w * w / theta2 < l) {
      if (l < distanceMax2) {
        if (x4 === 0) x4 = jiggle_default(random), l += x4 * x4;
        if (y4 === 0) y4 = jiggle_default(random), l += y4 * y4;
        if (l < distanceMin2) l = Math.sqrt(distanceMin2 * l);
        node.vx += x4 * quad.value * alpha / l;
        node.vy += y4 * quad.value * alpha / l;
      }
      return true;
    } else if (quad.length || l >= distanceMax2) return;
    if (quad.data !== node || quad.next) {
      if (x4 === 0) x4 = jiggle_default(random), l += x4 * x4;
      if (y4 === 0) y4 = jiggle_default(random), l += y4 * y4;
      if (l < distanceMin2) l = Math.sqrt(distanceMin2 * l);
    }
    do
      if (quad.data !== node) {
        w = strengths[quad.data.index] * alpha / l;
        node.vx += x4 * w;
        node.vy += y4 * w;
      }
    while (quad = quad.next);
  }
  force.initialize = function(_nodes, _random) {
    nodes = _nodes;
    random = _random;
    initialize();
  };
  force.strength = function(_) {
    return arguments.length ? (strength = typeof _ === "function" ? _ : constant_default4(+_), initialize(), force) : strength;
  };
  force.distanceMin = function(_) {
    return arguments.length ? (distanceMin2 = _ * _, force) : Math.sqrt(distanceMin2);
  };
  force.distanceMax = function(_) {
    return arguments.length ? (distanceMax2 = _ * _, force) : Math.sqrt(distanceMax2);
  };
  force.theta = function(_) {
    return arguments.length ? (theta2 = _ * _, force) : Math.sqrt(theta2);
  };
  return force;
}

// node_modules/d3-force/src/radial.js
function radial_default(radius, x4, y4) {
  var nodes, strength = constant_default4(0.1), strengths, radiuses;
  if (typeof radius !== "function") radius = constant_default4(+radius);
  if (x4 == null) x4 = 0;
  if (y4 == null) y4 = 0;
  function force(alpha) {
    for (var i = 0, n = nodes.length; i < n; ++i) {
      var node = nodes[i], dx = node.x - x4 || 1e-6, dy = node.y - y4 || 1e-6, r = Math.sqrt(dx * dx + dy * dy), k2 = (radiuses[i] - r) * strengths[i] * alpha / r;
      node.vx += dx * k2;
      node.vy += dy * k2;
    }
  }
  function initialize() {
    if (!nodes) return;
    var i, n = nodes.length;
    strengths = new Array(n);
    radiuses = new Array(n);
    for (i = 0; i < n; ++i) {
      radiuses[i] = +radius(nodes[i], i, nodes);
      strengths[i] = isNaN(radiuses[i]) ? 0 : +strength(nodes[i], i, nodes);
    }
  }
  force.initialize = function(_) {
    nodes = _, initialize();
  };
  force.strength = function(_) {
    return arguments.length ? (strength = typeof _ === "function" ? _ : constant_default4(+_), initialize(), force) : strength;
  };
  force.radius = function(_) {
    return arguments.length ? (radius = typeof _ === "function" ? _ : constant_default4(+_), initialize(), force) : radius;
  };
  force.x = function(_) {
    return arguments.length ? (x4 = +_, force) : x4;
  };
  force.y = function(_) {
    return arguments.length ? (y4 = +_, force) : y4;
  };
  return force;
}

// node_modules/d3-force/src/x.js
function x_default2(x4) {
  var strength = constant_default4(0.1), nodes, strengths, xz;
  if (typeof x4 !== "function") x4 = constant_default4(x4 == null ? 0 : +x4);
  function force(alpha) {
    for (var i = 0, n = nodes.length, node; i < n; ++i) {
      node = nodes[i], node.vx += (xz[i] - node.x) * strengths[i] * alpha;
    }
  }
  function initialize() {
    if (!nodes) return;
    var i, n = nodes.length;
    strengths = new Array(n);
    xz = new Array(n);
    for (i = 0; i < n; ++i) {
      strengths[i] = isNaN(xz[i] = +x4(nodes[i], i, nodes)) ? 0 : +strength(nodes[i], i, nodes);
    }
  }
  force.initialize = function(_) {
    nodes = _;
    initialize();
  };
  force.strength = function(_) {
    return arguments.length ? (strength = typeof _ === "function" ? _ : constant_default4(+_), initialize(), force) : strength;
  };
  force.x = function(_) {
    return arguments.length ? (x4 = typeof _ === "function" ? _ : constant_default4(+_), initialize(), force) : x4;
  };
  return force;
}

// node_modules/d3-force/src/y.js
function y_default2(y4) {
  var strength = constant_default4(0.1), nodes, strengths, yz;
  if (typeof y4 !== "function") y4 = constant_default4(y4 == null ? 0 : +y4);
  function force(alpha) {
    for (var i = 0, n = nodes.length, node; i < n; ++i) {
      node = nodes[i], node.vy += (yz[i] - node.y) * strengths[i] * alpha;
    }
  }
  function initialize() {
    if (!nodes) return;
    var i, n = nodes.length;
    strengths = new Array(n);
    yz = new Array(n);
    for (i = 0; i < n; ++i) {
      strengths[i] = isNaN(yz[i] = +y4(nodes[i], i, nodes)) ? 0 : +strength(nodes[i], i, nodes);
    }
  }
  force.initialize = function(_) {
    nodes = _;
    initialize();
  };
  force.strength = function(_) {
    return arguments.length ? (strength = typeof _ === "function" ? _ : constant_default4(+_), initialize(), force) : strength;
  };
  force.y = function(_) {
    return arguments.length ? (y4 = typeof _ === "function" ? _ : constant_default4(+_), initialize(), force) : y4;
  };
  return force;
}

// node_modules/d3-format/src/formatDecimal.js
function formatDecimal_default(x4) {
  return Math.abs(x4 = Math.round(x4)) >= 1e21 ? x4.toLocaleString("en").replace(/,/g, "") : x4.toString(10);
}
function formatDecimalParts(x4, p) {
  if ((i = (x4 = p ? x4.toExponential(p - 1) : x4.toExponential()).indexOf("e")) < 0) return null;
  var i, coefficient = x4.slice(0, i);
  return [
    coefficient.length > 1 ? coefficient[0] + coefficient.slice(2) : coefficient,
    +x4.slice(i + 1)
  ];
}

// node_modules/d3-format/src/exponent.js
function exponent_default(x4) {
  return x4 = formatDecimalParts(Math.abs(x4)), x4 ? x4[1] : NaN;
}

// node_modules/d3-format/src/formatGroup.js
function formatGroup_default(grouping, thousands) {
  return function(value, width) {
    var i = value.length, t = [], j = 0, g = grouping[0], length3 = 0;
    while (i > 0 && g > 0) {
      if (length3 + g + 1 > width) g = Math.max(1, width - length3);
      t.push(value.substring(i -= g, i + g));
      if ((length3 += g + 1) > width) break;
      g = grouping[j = (j + 1) % grouping.length];
    }
    return t.reverse().join(thousands);
  };
}

// node_modules/d3-format/src/formatNumerals.js
function formatNumerals_default(numerals) {
  return function(value) {
    return value.replace(/[0-9]/g, function(i) {
      return numerals[+i];
    });
  };
}

// node_modules/d3-format/src/formatSpecifier.js
var re = /^(?:(.)?([<>=^]))?([+\-( ])?([$#])?(0)?(\d+)?(,)?(\.\d+)?(~)?([a-z%])?$/i;
function formatSpecifier(specifier) {
  if (!(match = re.exec(specifier))) throw new Error("invalid format: " + specifier);
  var match;
  return new FormatSpecifier({
    fill: match[1],
    align: match[2],
    sign: match[3],
    symbol: match[4],
    zero: match[5],
    width: match[6],
    comma: match[7],
    precision: match[8] && match[8].slice(1),
    trim: match[9],
    type: match[10]
  });
}
formatSpecifier.prototype = FormatSpecifier.prototype;
function FormatSpecifier(specifier) {
  this.fill = specifier.fill === void 0 ? " " : specifier.fill + "";
  this.align = specifier.align === void 0 ? ">" : specifier.align + "";
  this.sign = specifier.sign === void 0 ? "-" : specifier.sign + "";
  this.symbol = specifier.symbol === void 0 ? "" : specifier.symbol + "";
  this.zero = !!specifier.zero;
  this.width = specifier.width === void 0 ? void 0 : +specifier.width;
  this.comma = !!specifier.comma;
  this.precision = specifier.precision === void 0 ? void 0 : +specifier.precision;
  this.trim = !!specifier.trim;
  this.type = specifier.type === void 0 ? "" : specifier.type + "";
}
FormatSpecifier.prototype.toString = function() {
  return this.fill + this.align + this.sign + this.symbol + (this.zero ? "0" : "") + (this.width === void 0 ? "" : Math.max(1, this.width | 0)) + (this.comma ? "," : "") + (this.precision === void 0 ? "" : "." + Math.max(0, this.precision | 0)) + (this.trim ? "~" : "") + this.type;
};

// node_modules/d3-format/src/formatTrim.js
function formatTrim_default(s2) {
  out: for (var n = s2.length, i = 1, i0 = -1, i1; i < n; ++i) {
    switch (s2[i]) {
      case ".":
        i0 = i1 = i;
        break;
      case "0":
        if (i0 === 0) i0 = i;
        i1 = i;
        break;
      default:
        if (!+s2[i]) break out;
        if (i0 > 0) i0 = 0;
        break;
    }
  }
  return i0 > 0 ? s2.slice(0, i0) + s2.slice(i1 + 1) : s2;
}

// node_modules/d3-format/src/formatPrefixAuto.js
var prefixExponent;
function formatPrefixAuto_default(x4, p) {
  var d = formatDecimalParts(x4, p);
  if (!d) return x4 + "";
  var coefficient = d[0], exponent = d[1], i = exponent - (prefixExponent = Math.max(-8, Math.min(8, Math.floor(exponent / 3))) * 3) + 1, n = coefficient.length;
  return i === n ? coefficient : i > n ? coefficient + new Array(i - n + 1).join("0") : i > 0 ? coefficient.slice(0, i) + "." + coefficient.slice(i) : "0." + new Array(1 - i).join("0") + formatDecimalParts(x4, Math.max(0, p + i - 1))[0];
}

// node_modules/d3-format/src/formatRounded.js
function formatRounded_default(x4, p) {
  var d = formatDecimalParts(x4, p);
  if (!d) return x4 + "";
  var coefficient = d[0], exponent = d[1];
  return exponent < 0 ? "0." + new Array(-exponent).join("0") + coefficient : coefficient.length > exponent + 1 ? coefficient.slice(0, exponent + 1) + "." + coefficient.slice(exponent + 1) : coefficient + new Array(exponent - coefficient.length + 2).join("0");
}

// node_modules/d3-format/src/formatTypes.js
var formatTypes_default = {
  "%": (x4, p) => (x4 * 100).toFixed(p),
  "b": (x4) => Math.round(x4).toString(2),
  "c": (x4) => x4 + "",
  "d": formatDecimal_default,
  "e": (x4, p) => x4.toExponential(p),
  "f": (x4, p) => x4.toFixed(p),
  "g": (x4, p) => x4.toPrecision(p),
  "o": (x4) => Math.round(x4).toString(8),
  "p": (x4, p) => formatRounded_default(x4 * 100, p),
  "r": formatRounded_default,
  "s": formatPrefixAuto_default,
  "X": (x4) => Math.round(x4).toString(16).toUpperCase(),
  "x": (x4) => Math.round(x4).toString(16)
};

// node_modules/d3-format/src/identity.js
function identity_default2(x4) {
  return x4;
}

// node_modules/d3-format/src/locale.js
var map3 = Array.prototype.map;
var prefixes = ["y", "z", "a", "f", "p", "n", "µ", "m", "", "k", "M", "G", "T", "P", "E", "Z", "Y"];
function locale_default(locale3) {
  var group2 = locale3.grouping === void 0 || locale3.thousands === void 0 ? identity_default2 : formatGroup_default(map3.call(locale3.grouping, Number), locale3.thousands + ""), currencyPrefix = locale3.currency === void 0 ? "" : locale3.currency[0] + "", currencySuffix = locale3.currency === void 0 ? "" : locale3.currency[1] + "", decimal = locale3.decimal === void 0 ? "." : locale3.decimal + "", numerals = locale3.numerals === void 0 ? identity_default2 : formatNumerals_default(map3.call(locale3.numerals, String)), percent = locale3.percent === void 0 ? "%" : locale3.percent + "", minus = locale3.minus === void 0 ? "−" : locale3.minus + "", nan = locale3.nan === void 0 ? "NaN" : locale3.nan + "";
  function newFormat(specifier) {
    specifier = formatSpecifier(specifier);
    var fill = specifier.fill, align = specifier.align, sign3 = specifier.sign, symbol = specifier.symbol, zero2 = specifier.zero, width = specifier.width, comma = specifier.comma, precision = specifier.precision, trim = specifier.trim, type2 = specifier.type;
    if (type2 === "n") comma = true, type2 = "g";
    else if (!formatTypes_default[type2]) precision === void 0 && (precision = 12), trim = true, type2 = "g";
    if (zero2 || fill === "0" && align === "=") zero2 = true, fill = "0", align = "=";
    var prefix = symbol === "$" ? currencyPrefix : symbol === "#" && /[boxX]/.test(type2) ? "0" + type2.toLowerCase() : "", suffix = symbol === "$" ? currencySuffix : /[%p]/.test(type2) ? percent : "";
    var formatType = formatTypes_default[type2], maybeSuffix = /[defgprs%]/.test(type2);
    precision = precision === void 0 ? 6 : /[gprs]/.test(type2) ? Math.max(1, Math.min(21, precision)) : Math.max(0, Math.min(20, precision));
    function format2(value) {
      var valuePrefix = prefix, valueSuffix = suffix, i, n, c6;
      if (type2 === "c") {
        valueSuffix = formatType(value) + valueSuffix;
        value = "";
      } else {
        value = +value;
        var valueNegative = value < 0 || 1 / value < 0;
        value = isNaN(value) ? nan : formatType(Math.abs(value), precision);
        if (trim) value = formatTrim_default(value);
        if (valueNegative && +value === 0 && sign3 !== "+") valueNegative = false;
        valuePrefix = (valueNegative ? sign3 === "(" ? sign3 : minus : sign3 === "-" || sign3 === "(" ? "" : sign3) + valuePrefix;
        valueSuffix = (type2 === "s" ? prefixes[8 + prefixExponent / 3] : "") + valueSuffix + (valueNegative && sign3 === "(" ? ")" : "");
        if (maybeSuffix) {
          i = -1, n = value.length;
          while (++i < n) {
            if (c6 = value.charCodeAt(i), 48 > c6 || c6 > 57) {
              valueSuffix = (c6 === 46 ? decimal + value.slice(i + 1) : value.slice(i)) + valueSuffix;
              value = value.slice(0, i);
              break;
            }
          }
        }
      }
      if (comma && !zero2) value = group2(value, Infinity);
      var length3 = valuePrefix.length + value.length + valueSuffix.length, padding = length3 < width ? new Array(width - length3 + 1).join(fill) : "";
      if (comma && zero2) value = group2(padding + value, padding.length ? width - valueSuffix.length : Infinity), padding = "";
      switch (align) {
        case "<":
          value = valuePrefix + value + valueSuffix + padding;
          break;
        case "=":
          value = valuePrefix + padding + value + valueSuffix;
          break;
        case "^":
          value = padding.slice(0, length3 = padding.length >> 1) + valuePrefix + value + valueSuffix + padding.slice(length3);
          break;
        default:
          value = padding + valuePrefix + value + valueSuffix;
          break;
      }
      return numerals(value);
    }
    format2.toString = function() {
      return specifier + "";
    };
    return format2;
  }
  function formatPrefix2(specifier, value) {
    var f = newFormat((specifier = formatSpecifier(specifier), specifier.type = "f", specifier)), e = Math.max(-8, Math.min(8, Math.floor(exponent_default(value) / 3))) * 3, k2 = Math.pow(10, -e), prefix = prefixes[8 + e / 3];
    return function(value2) {
      return f(k2 * value2) + prefix;
    };
  }
  return {
    format: newFormat,
    formatPrefix: formatPrefix2
  };
}

// node_modules/d3-format/src/defaultLocale.js
var locale;
var format;
var formatPrefix;
defaultLocale({
  thousands: ",",
  grouping: [3],
  currency: ["$", ""]
});
function defaultLocale(definition) {
  locale = locale_default(definition);
  format = locale.format;
  formatPrefix = locale.formatPrefix;
  return locale;
}

// node_modules/d3-format/src/precisionFixed.js
function precisionFixed_default(step) {
  return Math.max(0, -exponent_default(Math.abs(step)));
}

// node_modules/d3-format/src/precisionPrefix.js
function precisionPrefix_default(step, value) {
  return Math.max(0, Math.max(-8, Math.min(8, Math.floor(exponent_default(value) / 3))) * 3 - exponent_default(Math.abs(step)));
}

// node_modules/d3-format/src/precisionRound.js
function precisionRound_default(step, max5) {
  step = Math.abs(step), max5 = Math.abs(max5) - step;
  return Math.max(0, exponent_default(max5) - exponent_default(step)) + 1;
}

// node_modules/d3-geo/src/math.js
var epsilon6 = 1e-6;
var epsilon22 = 1e-12;
var pi3 = Math.PI;
var halfPi2 = pi3 / 2;
var quarterPi = pi3 / 4;
var tau4 = pi3 * 2;
var degrees = 180 / pi3;
var radians = pi3 / 180;
var abs3 = Math.abs;
var atan = Math.atan;
var atan2 = Math.atan2;
var cos2 = Math.cos;
var ceil = Math.ceil;
var exp = Math.exp;
var hypot = Math.hypot;
var log = Math.log;
var pow2 = Math.pow;
var sin2 = Math.sin;
var sign = Math.sign || function(x4) {
  return x4 > 0 ? 1 : x4 < 0 ? -1 : 0;
};
var sqrt = Math.sqrt;
var tan = Math.tan;
function acos(x4) {
  return x4 > 1 ? 0 : x4 < -1 ? pi3 : Math.acos(x4);
}
function asin(x4) {
  return x4 > 1 ? halfPi2 : x4 < -1 ? -halfPi2 : Math.asin(x4);
}
function haversin(x4) {
  return (x4 = sin2(x4 / 2)) * x4;
}

// node_modules/d3-geo/src/noop.js
function noop() {
}

// node_modules/d3-geo/src/stream.js
function streamGeometry(geometry, stream) {
  if (geometry && streamGeometryType.hasOwnProperty(geometry.type)) {
    streamGeometryType[geometry.type](geometry, stream);
  }
}
var streamObjectType = {
  Feature: function(object2, stream) {
    streamGeometry(object2.geometry, stream);
  },
  FeatureCollection: function(object2, stream) {
    var features = object2.features, i = -1, n = features.length;
    while (++i < n) streamGeometry(features[i].geometry, stream);
  }
};
var streamGeometryType = {
  Sphere: function(object2, stream) {
    stream.sphere();
  },
  Point: function(object2, stream) {
    object2 = object2.coordinates;
    stream.point(object2[0], object2[1], object2[2]);
  },
  MultiPoint: function(object2, stream) {
    var coordinates2 = object2.coordinates, i = -1, n = coordinates2.length;
    while (++i < n) object2 = coordinates2[i], stream.point(object2[0], object2[1], object2[2]);
  },
  LineString: function(object2, stream) {
    streamLine(object2.coordinates, stream, 0);
  },
  MultiLineString: function(object2, stream) {
    var coordinates2 = object2.coordinates, i = -1, n = coordinates2.length;
    while (++i < n) streamLine(coordinates2[i], stream, 0);
  },
  Polygon: function(object2, stream) {
    streamPolygon(object2.coordinates, stream);
  },
  MultiPolygon: function(object2, stream) {
    var coordinates2 = object2.coordinates, i = -1, n = coordinates2.length;
    while (++i < n) streamPolygon(coordinates2[i], stream);
  },
  GeometryCollection: function(object2, stream) {
    var geometries = object2.geometries, i = -1, n = geometries.length;
    while (++i < n) streamGeometry(geometries[i], stream);
  }
};
function streamLine(coordinates2, stream, closed) {
  var i = -1, n = coordinates2.length - closed, coordinate;
  stream.lineStart();
  while (++i < n) coordinate = coordinates2[i], stream.point(coordinate[0], coordinate[1], coordinate[2]);
  stream.lineEnd();
}
function streamPolygon(coordinates2, stream) {
  var i = -1, n = coordinates2.length;
  stream.polygonStart();
  while (++i < n) streamLine(coordinates2[i], stream, 1);
  stream.polygonEnd();
}
function stream_default(object2, stream) {
  if (object2 && streamObjectType.hasOwnProperty(object2.type)) {
    streamObjectType[object2.type](object2, stream);
  } else {
    streamGeometry(object2, stream);
  }
}

// node_modules/d3-geo/src/area.js
var areaRingSum = new Adder();
var areaSum = new Adder();
var lambda00;
var phi00;
var lambda0;
var cosPhi0;
var sinPhi0;
var areaStream = {
  point: noop,
  lineStart: noop,
  lineEnd: noop,
  polygonStart: function() {
    areaRingSum = new Adder();
    areaStream.lineStart = areaRingStart;
    areaStream.lineEnd = areaRingEnd;
  },
  polygonEnd: function() {
    var areaRing = +areaRingSum;
    areaSum.add(areaRing < 0 ? tau4 + areaRing : areaRing);
    this.lineStart = this.lineEnd = this.point = noop;
  },
  sphere: function() {
    areaSum.add(tau4);
  }
};
function areaRingStart() {
  areaStream.point = areaPointFirst;
}
function areaRingEnd() {
  areaPoint(lambda00, phi00);
}
function areaPointFirst(lambda, phi2) {
  areaStream.point = areaPoint;
  lambda00 = lambda, phi00 = phi2;
  lambda *= radians, phi2 *= radians;
  lambda0 = lambda, cosPhi0 = cos2(phi2 = phi2 / 2 + quarterPi), sinPhi0 = sin2(phi2);
}
function areaPoint(lambda, phi2) {
  lambda *= radians, phi2 *= radians;
  phi2 = phi2 / 2 + quarterPi;
  var dLambda = lambda - lambda0, sdLambda = dLambda >= 0 ? 1 : -1, adLambda = sdLambda * dLambda, cosPhi = cos2(phi2), sinPhi = sin2(phi2), k2 = sinPhi0 * sinPhi, u4 = cosPhi0 * cosPhi + k2 * cos2(adLambda), v2 = k2 * sdLambda * sin2(adLambda);
  areaRingSum.add(atan2(v2, u4));
  lambda0 = lambda, cosPhi0 = cosPhi, sinPhi0 = sinPhi;
}
function area_default2(object2) {
  areaSum = new Adder();
  stream_default(object2, areaStream);
  return areaSum * 2;
}

// node_modules/d3-geo/src/cartesian.js
function spherical(cartesian2) {
  return [atan2(cartesian2[1], cartesian2[0]), asin(cartesian2[2])];
}
function cartesian(spherical2) {
  var lambda = spherical2[0], phi2 = spherical2[1], cosPhi = cos2(phi2);
  return [cosPhi * cos2(lambda), cosPhi * sin2(lambda), sin2(phi2)];
}
function cartesianDot(a4, b) {
  return a4[0] * b[0] + a4[1] * b[1] + a4[2] * b[2];
}
function cartesianCross(a4, b) {
  return [a4[1] * b[2] - a4[2] * b[1], a4[2] * b[0] - a4[0] * b[2], a4[0] * b[1] - a4[1] * b[0]];
}
function cartesianAddInPlace(a4, b) {
  a4[0] += b[0], a4[1] += b[1], a4[2] += b[2];
}
function cartesianScale(vector, k2) {
  return [vector[0] * k2, vector[1] * k2, vector[2] * k2];
}
function cartesianNormalizeInPlace(d) {
  var l = sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
  d[0] /= l, d[1] /= l, d[2] /= l;
}

// node_modules/d3-geo/src/bounds.js
var lambda02;
var phi0;
var lambda1;
var phi1;
var lambda2;
var lambda002;
var phi002;
var p0;
var deltaSum;
var ranges;
var range3;
var boundsStream = {
  point: boundsPoint,
  lineStart: boundsLineStart,
  lineEnd: boundsLineEnd,
  polygonStart: function() {
    boundsStream.point = boundsRingPoint;
    boundsStream.lineStart = boundsRingStart;
    boundsStream.lineEnd = boundsRingEnd;
    deltaSum = new Adder();
    areaStream.polygonStart();
  },
  polygonEnd: function() {
    areaStream.polygonEnd();
    boundsStream.point = boundsPoint;
    boundsStream.lineStart = boundsLineStart;
    boundsStream.lineEnd = boundsLineEnd;
    if (areaRingSum < 0) lambda02 = -(lambda1 = 180), phi0 = -(phi1 = 90);
    else if (deltaSum > epsilon6) phi1 = 90;
    else if (deltaSum < -epsilon6) phi0 = -90;
    range3[0] = lambda02, range3[1] = lambda1;
  },
  sphere: function() {
    lambda02 = -(lambda1 = 180), phi0 = -(phi1 = 90);
  }
};
function boundsPoint(lambda, phi2) {
  ranges.push(range3 = [lambda02 = lambda, lambda1 = lambda]);
  if (phi2 < phi0) phi0 = phi2;
  if (phi2 > phi1) phi1 = phi2;
}
function linePoint(lambda, phi2) {
  var p = cartesian([lambda * radians, phi2 * radians]);
  if (p0) {
    var normal = cartesianCross(p0, p), equatorial = [normal[1], -normal[0], 0], inflection = cartesianCross(equatorial, normal);
    cartesianNormalizeInPlace(inflection);
    inflection = spherical(inflection);
    var delta = lambda - lambda2, sign3 = delta > 0 ? 1 : -1, lambdai = inflection[0] * degrees * sign3, phii, antimeridian = abs3(delta) > 180;
    if (antimeridian ^ (sign3 * lambda2 < lambdai && lambdai < sign3 * lambda)) {
      phii = inflection[1] * degrees;
      if (phii > phi1) phi1 = phii;
    } else if (lambdai = (lambdai + 360) % 360 - 180, antimeridian ^ (sign3 * lambda2 < lambdai && lambdai < sign3 * lambda)) {
      phii = -inflection[1] * degrees;
      if (phii < phi0) phi0 = phii;
    } else {
      if (phi2 < phi0) phi0 = phi2;
      if (phi2 > phi1) phi1 = phi2;
    }
    if (antimeridian) {
      if (lambda < lambda2) {
        if (angle(lambda02, lambda) > angle(lambda02, lambda1)) lambda1 = lambda;
      } else {
        if (angle(lambda, lambda1) > angle(lambda02, lambda1)) lambda02 = lambda;
      }
    } else {
      if (lambda1 >= lambda02) {
        if (lambda < lambda02) lambda02 = lambda;
        if (lambda > lambda1) lambda1 = lambda;
      } else {
        if (lambda > lambda2) {
          if (angle(lambda02, lambda) > angle(lambda02, lambda1)) lambda1 = lambda;
        } else {
          if (angle(lambda, lambda1) > angle(lambda02, lambda1)) lambda02 = lambda;
        }
      }
    }
  } else {
    ranges.push(range3 = [lambda02 = lambda, lambda1 = lambda]);
  }
  if (phi2 < phi0) phi0 = phi2;
  if (phi2 > phi1) phi1 = phi2;
  p0 = p, lambda2 = lambda;
}
function boundsLineStart() {
  boundsStream.point = linePoint;
}
function boundsLineEnd() {
  range3[0] = lambda02, range3[1] = lambda1;
  boundsStream.point = boundsPoint;
  p0 = null;
}
function boundsRingPoint(lambda, phi2) {
  if (p0) {
    var delta = lambda - lambda2;
    deltaSum.add(abs3(delta) > 180 ? delta + (delta > 0 ? 360 : -360) : delta);
  } else {
    lambda002 = lambda, phi002 = phi2;
  }
  areaStream.point(lambda, phi2);
  linePoint(lambda, phi2);
}
function boundsRingStart() {
  areaStream.lineStart();
}
function boundsRingEnd() {
  boundsRingPoint(lambda002, phi002);
  areaStream.lineEnd();
  if (abs3(deltaSum) > epsilon6) lambda02 = -(lambda1 = 180);
  range3[0] = lambda02, range3[1] = lambda1;
  p0 = null;
}
function angle(lambda04, lambda12) {
  return (lambda12 -= lambda04) < 0 ? lambda12 + 360 : lambda12;
}
function rangeCompare(a4, b) {
  return a4[0] - b[0];
}
function rangeContains(range4, x4) {
  return range4[0] <= range4[1] ? range4[0] <= x4 && x4 <= range4[1] : x4 < range4[0] || range4[1] < x4;
}
function bounds_default(feature) {
  var i, n, a4, b, merged, deltaMax, delta;
  phi1 = lambda1 = -(lambda02 = phi0 = Infinity);
  ranges = [];
  stream_default(feature, boundsStream);
  if (n = ranges.length) {
    ranges.sort(rangeCompare);
    for (i = 1, a4 = ranges[0], merged = [a4]; i < n; ++i) {
      b = ranges[i];
      if (rangeContains(a4, b[0]) || rangeContains(a4, b[1])) {
        if (angle(a4[0], b[1]) > angle(a4[0], a4[1])) a4[1] = b[1];
        if (angle(b[0], a4[1]) > angle(a4[0], a4[1])) a4[0] = b[0];
      } else {
        merged.push(a4 = b);
      }
    }
    for (deltaMax = -Infinity, n = merged.length - 1, i = 0, a4 = merged[n]; i <= n; a4 = b, ++i) {
      b = merged[i];
      if ((delta = angle(a4[1], b[0])) > deltaMax) deltaMax = delta, lambda02 = b[0], lambda1 = a4[1];
    }
  }
  ranges = range3 = null;
  return lambda02 === Infinity || phi0 === Infinity ? [[NaN, NaN], [NaN, NaN]] : [[lambda02, phi0], [lambda1, phi1]];
}

// node_modules/d3-geo/src/centroid.js
var W0;
var W1;
var X0;
var Y0;
var Z0;
var X1;
var Y1;
var Z1;
var X2;
var Y2;
var Z2;
var lambda003;
var phi003;
var x0;
var y0;
var z0;
var centroidStream = {
  sphere: noop,
  point: centroidPoint,
  lineStart: centroidLineStart,
  lineEnd: centroidLineEnd,
  polygonStart: function() {
    centroidStream.lineStart = centroidRingStart;
    centroidStream.lineEnd = centroidRingEnd;
  },
  polygonEnd: function() {
    centroidStream.lineStart = centroidLineStart;
    centroidStream.lineEnd = centroidLineEnd;
  }
};
function centroidPoint(lambda, phi2) {
  lambda *= radians, phi2 *= radians;
  var cosPhi = cos2(phi2);
  centroidPointCartesian(cosPhi * cos2(lambda), cosPhi * sin2(lambda), sin2(phi2));
}
function centroidPointCartesian(x4, y4, z) {
  ++W0;
  X0 += (x4 - X0) / W0;
  Y0 += (y4 - Y0) / W0;
  Z0 += (z - Z0) / W0;
}
function centroidLineStart() {
  centroidStream.point = centroidLinePointFirst;
}
function centroidLinePointFirst(lambda, phi2) {
  lambda *= radians, phi2 *= radians;
  var cosPhi = cos2(phi2);
  x0 = cosPhi * cos2(lambda);
  y0 = cosPhi * sin2(lambda);
  z0 = sin2(phi2);
  centroidStream.point = centroidLinePoint;
  centroidPointCartesian(x0, y0, z0);
}
function centroidLinePoint(lambda, phi2) {
  lambda *= radians, phi2 *= radians;
  var cosPhi = cos2(phi2), x4 = cosPhi * cos2(lambda), y4 = cosPhi * sin2(lambda), z = sin2(phi2), w = atan2(sqrt((w = y0 * z - z0 * y4) * w + (w = z0 * x4 - x0 * z) * w + (w = x0 * y4 - y0 * x4) * w), x0 * x4 + y0 * y4 + z0 * z);
  W1 += w;
  X1 += w * (x0 + (x0 = x4));
  Y1 += w * (y0 + (y0 = y4));
  Z1 += w * (z0 + (z0 = z));
  centroidPointCartesian(x0, y0, z0);
}
function centroidLineEnd() {
  centroidStream.point = centroidPoint;
}
function centroidRingStart() {
  centroidStream.point = centroidRingPointFirst;
}
function centroidRingEnd() {
  centroidRingPoint(lambda003, phi003);
  centroidStream.point = centroidPoint;
}
function centroidRingPointFirst(lambda, phi2) {
  lambda003 = lambda, phi003 = phi2;
  lambda *= radians, phi2 *= radians;
  centroidStream.point = centroidRingPoint;
  var cosPhi = cos2(phi2);
  x0 = cosPhi * cos2(lambda);
  y0 = cosPhi * sin2(lambda);
  z0 = sin2(phi2);
  centroidPointCartesian(x0, y0, z0);
}
function centroidRingPoint(lambda, phi2) {
  lambda *= radians, phi2 *= radians;
  var cosPhi = cos2(phi2), x4 = cosPhi * cos2(lambda), y4 = cosPhi * sin2(lambda), z = sin2(phi2), cx = y0 * z - z0 * y4, cy = z0 * x4 - x0 * z, cz = x0 * y4 - y0 * x4, m3 = hypot(cx, cy, cz), w = asin(m3), v2 = m3 && -w / m3;
  X2.add(v2 * cx);
  Y2.add(v2 * cy);
  Z2.add(v2 * cz);
  W1 += w;
  X1 += w * (x0 + (x0 = x4));
  Y1 += w * (y0 + (y0 = y4));
  Z1 += w * (z0 + (z0 = z));
  centroidPointCartesian(x0, y0, z0);
}
function centroid_default(object2) {
  W0 = W1 = X0 = Y0 = Z0 = X1 = Y1 = Z1 = 0;
  X2 = new Adder();
  Y2 = new Adder();
  Z2 = new Adder();
  stream_default(object2, centroidStream);
  var x4 = +X2, y4 = +Y2, z = +Z2, m3 = hypot(x4, y4, z);
  if (m3 < epsilon22) {
    x4 = X1, y4 = Y1, z = Z1;
    if (W1 < epsilon6) x4 = X0, y4 = Y0, z = Z0;
    m3 = hypot(x4, y4, z);
    if (m3 < epsilon22) return [NaN, NaN];
  }
  return [atan2(y4, x4) * degrees, asin(z / m3) * degrees];
}

// node_modules/d3-geo/src/constant.js
function constant_default5(x4) {
  return function() {
    return x4;
  };
}

// node_modules/d3-geo/src/compose.js
function compose_default(a4, b) {
  function compose(x4, y4) {
    return x4 = a4(x4, y4), b(x4[0], x4[1]);
  }
  if (a4.invert && b.invert) compose.invert = function(x4, y4) {
    return x4 = b.invert(x4, y4), x4 && a4.invert(x4[0], x4[1]);
  };
  return compose;
}

// node_modules/d3-geo/src/rotation.js
function rotationIdentity(lambda, phi2) {
  if (abs3(lambda) > pi3) lambda -= Math.round(lambda / tau4) * tau4;
  return [lambda, phi2];
}
rotationIdentity.invert = rotationIdentity;
function rotateRadians(deltaLambda, deltaPhi, deltaGamma) {
  return (deltaLambda %= tau4) ? deltaPhi || deltaGamma ? compose_default(rotationLambda(deltaLambda), rotationPhiGamma(deltaPhi, deltaGamma)) : rotationLambda(deltaLambda) : deltaPhi || deltaGamma ? rotationPhiGamma(deltaPhi, deltaGamma) : rotationIdentity;
}
function forwardRotationLambda(deltaLambda) {
  return function(lambda, phi2) {
    lambda += deltaLambda;
    if (abs3(lambda) > pi3) lambda -= Math.round(lambda / tau4) * tau4;
    return [lambda, phi2];
  };
}
function rotationLambda(deltaLambda) {
  var rotation = forwardRotationLambda(deltaLambda);
  rotation.invert = forwardRotationLambda(-deltaLambda);
  return rotation;
}
function rotationPhiGamma(deltaPhi, deltaGamma) {
  var cosDeltaPhi = cos2(deltaPhi), sinDeltaPhi = sin2(deltaPhi), cosDeltaGamma = cos2(deltaGamma), sinDeltaGamma = sin2(deltaGamma);
  function rotation(lambda, phi2) {
    var cosPhi = cos2(phi2), x4 = cos2(lambda) * cosPhi, y4 = sin2(lambda) * cosPhi, z = sin2(phi2), k2 = z * cosDeltaPhi + x4 * sinDeltaPhi;
    return [
      atan2(y4 * cosDeltaGamma - k2 * sinDeltaGamma, x4 * cosDeltaPhi - z * sinDeltaPhi),
      asin(k2 * cosDeltaGamma + y4 * sinDeltaGamma)
    ];
  }
  rotation.invert = function(lambda, phi2) {
    var cosPhi = cos2(phi2), x4 = cos2(lambda) * cosPhi, y4 = sin2(lambda) * cosPhi, z = sin2(phi2), k2 = z * cosDeltaGamma - y4 * sinDeltaGamma;
    return [
      atan2(y4 * cosDeltaGamma + z * sinDeltaGamma, x4 * cosDeltaPhi + k2 * sinDeltaPhi),
      asin(k2 * cosDeltaPhi - x4 * sinDeltaPhi)
    ];
  };
  return rotation;
}
function rotation_default(rotate) {
  rotate = rotateRadians(rotate[0] * radians, rotate[1] * radians, rotate.length > 2 ? rotate[2] * radians : 0);
  function forward(coordinates2) {
    coordinates2 = rotate(coordinates2[0] * radians, coordinates2[1] * radians);
    return coordinates2[0] *= degrees, coordinates2[1] *= degrees, coordinates2;
  }
  forward.invert = function(coordinates2) {
    coordinates2 = rotate.invert(coordinates2[0] * radians, coordinates2[1] * radians);
    return coordinates2[0] *= degrees, coordinates2[1] *= degrees, coordinates2;
  };
  return forward;
}

// node_modules/d3-geo/src/circle.js
function circleStream(stream, radius, delta, direction, t02, t12) {
  if (!delta) return;
  var cosRadius = cos2(radius), sinRadius = sin2(radius), step = direction * delta;
  if (t02 == null) {
    t02 = radius + direction * tau4;
    t12 = radius - step / 2;
  } else {
    t02 = circleRadius(cosRadius, t02);
    t12 = circleRadius(cosRadius, t12);
    if (direction > 0 ? t02 < t12 : t02 > t12) t02 += direction * tau4;
  }
  for (var point6, t = t02; direction > 0 ? t > t12 : t < t12; t -= step) {
    point6 = spherical([cosRadius, -sinRadius * cos2(t), -sinRadius * sin2(t)]);
    stream.point(point6[0], point6[1]);
  }
}
function circleRadius(cosRadius, point6) {
  point6 = cartesian(point6), point6[0] -= cosRadius;
  cartesianNormalizeInPlace(point6);
  var radius = acos(-point6[1]);
  return ((-point6[2] < 0 ? -radius : radius) + tau4 - epsilon6) % tau4;
}
function circle_default() {
  var center2 = constant_default5([0, 0]), radius = constant_default5(90), precision = constant_default5(2), ring, rotate, stream = { point: point6 };
  function point6(x4, y4) {
    ring.push(x4 = rotate(x4, y4));
    x4[0] *= degrees, x4[1] *= degrees;
  }
  function circle() {
    var c6 = center2.apply(this, arguments), r = radius.apply(this, arguments) * radians, p = precision.apply(this, arguments) * radians;
    ring = [];
    rotate = rotateRadians(-c6[0] * radians, -c6[1] * radians, 0).invert;
    circleStream(stream, r, p, 1);
    c6 = { type: "Polygon", coordinates: [ring] };
    ring = rotate = null;
    return c6;
  }
  circle.center = function(_) {
    return arguments.length ? (center2 = typeof _ === "function" ? _ : constant_default5([+_[0], +_[1]]), circle) : center2;
  };
  circle.radius = function(_) {
    return arguments.length ? (radius = typeof _ === "function" ? _ : constant_default5(+_), circle) : radius;
  };
  circle.precision = function(_) {
    return arguments.length ? (precision = typeof _ === "function" ? _ : constant_default5(+_), circle) : precision;
  };
  return circle;
}

// node_modules/d3-geo/src/clip/buffer.js
function buffer_default2() {
  var lines = [], line;
  return {
    point: function(x4, y4, m3) {
      line.push([x4, y4, m3]);
    },
    lineStart: function() {
      lines.push(line = []);
    },
    lineEnd: noop,
    rejoin: function() {
      if (lines.length > 1) lines.push(lines.pop().concat(lines.shift()));
    },
    result: function() {
      var result = lines;
      lines = [];
      line = null;
      return result;
    }
  };
}

// node_modules/d3-geo/src/pointEqual.js
function pointEqual_default(a4, b) {
  return abs3(a4[0] - b[0]) < epsilon6 && abs3(a4[1] - b[1]) < epsilon6;
}

// node_modules/d3-geo/src/clip/rejoin.js
function Intersection(point6, points, other, entry) {
  this.x = point6;
  this.z = points;
  this.o = other;
  this.e = entry;
  this.v = false;
  this.n = this.p = null;
}
function rejoin_default(segments, compareIntersection2, startInside, interpolate, stream) {
  var subject = [], clip = [], i, n;
  segments.forEach(function(segment) {
    if ((n2 = segment.length - 1) <= 0) return;
    var n2, p02 = segment[0], p1 = segment[n2], x4;
    if (pointEqual_default(p02, p1)) {
      if (!p02[2] && !p1[2]) {
        stream.lineStart();
        for (i = 0; i < n2; ++i) stream.point((p02 = segment[i])[0], p02[1]);
        stream.lineEnd();
        return;
      }
      p1[0] += 2 * epsilon6;
    }
    subject.push(x4 = new Intersection(p02, segment, null, true));
    clip.push(x4.o = new Intersection(p02, null, x4, false));
    subject.push(x4 = new Intersection(p1, segment, null, false));
    clip.push(x4.o = new Intersection(p1, null, x4, true));
  });
  if (!subject.length) return;
  clip.sort(compareIntersection2);
  link(subject);
  link(clip);
  for (i = 0, n = clip.length; i < n; ++i) {
    clip[i].e = startInside = !startInside;
  }
  var start = subject[0], points, point6;
  while (1) {
    var current = start, isSubject = true;
    while (current.v) if ((current = current.n) === start) return;
    points = current.z;
    stream.lineStart();
    do {
      current.v = current.o.v = true;
      if (current.e) {
        if (isSubject) {
          for (i = 0, n = points.length; i < n; ++i) stream.point((point6 = points[i])[0], point6[1]);
        } else {
          interpolate(current.x, current.n.x, 1, stream);
        }
        current = current.n;
      } else {
        if (isSubject) {
          points = current.p.z;
          for (i = points.length - 1; i >= 0; --i) stream.point((point6 = points[i])[0], point6[1]);
        } else {
          interpolate(current.x, current.p.x, -1, stream);
        }
        current = current.p;
      }
      current = current.o;
      points = current.z;
      isSubject = !isSubject;
    } while (!current.v);
    stream.lineEnd();
  }
}
function link(array3) {
  if (!(n = array3.length)) return;
  var n, i = 0, a4 = array3[0], b;
  while (++i < n) {
    a4.n = b = array3[i];
    b.p = a4;
    a4 = b;
  }
  a4.n = b = array3[0];
  b.p = a4;
}

// node_modules/d3-geo/src/polygonContains.js
function longitude(point6) {
  return abs3(point6[0]) <= pi3 ? point6[0] : sign(point6[0]) * ((abs3(point6[0]) + pi3) % tau4 - pi3);
}
function polygonContains_default(polygon, point6) {
  var lambda = longitude(point6), phi2 = point6[1], sinPhi = sin2(phi2), normal = [sin2(lambda), -cos2(lambda), 0], angle2 = 0, winding = 0;
  var sum4 = new Adder();
  if (sinPhi === 1) phi2 = halfPi2 + epsilon6;
  else if (sinPhi === -1) phi2 = -halfPi2 - epsilon6;
  for (var i = 0, n = polygon.length; i < n; ++i) {
    if (!(m3 = (ring = polygon[i]).length)) continue;
    var ring, m3, point0 = ring[m3 - 1], lambda04 = longitude(point0), phi02 = point0[1] / 2 + quarterPi, sinPhi03 = sin2(phi02), cosPhi03 = cos2(phi02);
    for (var j = 0; j < m3; ++j, lambda04 = lambda12, sinPhi03 = sinPhi1, cosPhi03 = cosPhi1, point0 = point1) {
      var point1 = ring[j], lambda12 = longitude(point1), phi12 = point1[1] / 2 + quarterPi, sinPhi1 = sin2(phi12), cosPhi1 = cos2(phi12), delta = lambda12 - lambda04, sign3 = delta >= 0 ? 1 : -1, absDelta = sign3 * delta, antimeridian = absDelta > pi3, k2 = sinPhi03 * sinPhi1;
      sum4.add(atan2(k2 * sign3 * sin2(absDelta), cosPhi03 * cosPhi1 + k2 * cos2(absDelta)));
      angle2 += antimeridian ? delta + sign3 * tau4 : delta;
      if (antimeridian ^ lambda04 >= lambda ^ lambda12 >= lambda) {
        var arc = cartesianCross(cartesian(point0), cartesian(point1));
        cartesianNormalizeInPlace(arc);
        var intersection2 = cartesianCross(normal, arc);
        cartesianNormalizeInPlace(intersection2);
        var phiArc = (antimeridian ^ delta >= 0 ? -1 : 1) * asin(intersection2[2]);
        if (phi2 > phiArc || phi2 === phiArc && (arc[0] || arc[1])) {
          winding += antimeridian ^ delta >= 0 ? 1 : -1;
        }
      }
    }
  }
  return (angle2 < -epsilon6 || angle2 < epsilon6 && sum4 < -epsilon22) ^ winding & 1;
}

// node_modules/d3-geo/src/clip/index.js
function clip_default(pointVisible, clipLine, interpolate, start) {
  return function(sink) {
    var line = clipLine(sink), ringBuffer = buffer_default2(), ringSink = clipLine(ringBuffer), polygonStarted = false, polygon, segments, ring;
    var clip = {
      point: point6,
      lineStart,
      lineEnd,
      polygonStart: function() {
        clip.point = pointRing;
        clip.lineStart = ringStart;
        clip.lineEnd = ringEnd;
        segments = [];
        polygon = [];
      },
      polygonEnd: function() {
        clip.point = point6;
        clip.lineStart = lineStart;
        clip.lineEnd = lineEnd;
        segments = merge(segments);
        var startInside = polygonContains_default(polygon, start);
        if (segments.length) {
          if (!polygonStarted) sink.polygonStart(), polygonStarted = true;
          rejoin_default(segments, compareIntersection, startInside, interpolate, sink);
        } else if (startInside) {
          if (!polygonStarted) sink.polygonStart(), polygonStarted = true;
          sink.lineStart();
          interpolate(null, null, 1, sink);
          sink.lineEnd();
        }
        if (polygonStarted) sink.polygonEnd(), polygonStarted = false;
        segments = polygon = null;
      },
      sphere: function() {
        sink.polygonStart();
        sink.lineStart();
        interpolate(null, null, 1, sink);
        sink.lineEnd();
        sink.polygonEnd();
      }
    };
    function point6(lambda, phi2) {
      if (pointVisible(lambda, phi2)) sink.point(lambda, phi2);
    }
    function pointLine(lambda, phi2) {
      line.point(lambda, phi2);
    }
    function lineStart() {
      clip.point = pointLine;
      line.lineStart();
    }
    function lineEnd() {
      clip.point = point6;
      line.lineEnd();
    }
    function pointRing(lambda, phi2) {
      ring.push([lambda, phi2]);
      ringSink.point(lambda, phi2);
    }
    function ringStart() {
      ringSink.lineStart();
      ring = [];
    }
    function ringEnd() {
      pointRing(ring[0][0], ring[0][1]);
      ringSink.lineEnd();
      var clean = ringSink.clean(), ringSegments = ringBuffer.result(), i, n = ringSegments.length, m3, segment, point7;
      ring.pop();
      polygon.push(ring);
      ring = null;
      if (!n) return;
      if (clean & 1) {
        segment = ringSegments[0];
        if ((m3 = segment.length - 1) > 0) {
          if (!polygonStarted) sink.polygonStart(), polygonStarted = true;
          sink.lineStart();
          for (i = 0; i < m3; ++i) sink.point((point7 = segment[i])[0], point7[1]);
          sink.lineEnd();
        }
        return;
      }
      if (n > 1 && clean & 2) ringSegments.push(ringSegments.pop().concat(ringSegments.shift()));
      segments.push(ringSegments.filter(validSegment));
    }
    return clip;
  };
}
function validSegment(segment) {
  return segment.length > 1;
}
function compareIntersection(a4, b) {
  return ((a4 = a4.x)[0] < 0 ? a4[1] - halfPi2 - epsilon6 : halfPi2 - a4[1]) - ((b = b.x)[0] < 0 ? b[1] - halfPi2 - epsilon6 : halfPi2 - b[1]);
}

// node_modules/d3-geo/src/clip/antimeridian.js
var antimeridian_default = clip_default(
  function() {
    return true;
  },
  clipAntimeridianLine,
  clipAntimeridianInterpolate,
  [-pi3, -halfPi2]
);
function clipAntimeridianLine(stream) {
  var lambda04 = NaN, phi02 = NaN, sign0 = NaN, clean;
  return {
    lineStart: function() {
      stream.lineStart();
      clean = 1;
    },
    point: function(lambda12, phi12) {
      var sign1 = lambda12 > 0 ? pi3 : -pi3, delta = abs3(lambda12 - lambda04);
      if (abs3(delta - pi3) < epsilon6) {
        stream.point(lambda04, phi02 = (phi02 + phi12) / 2 > 0 ? halfPi2 : -halfPi2);
        stream.point(sign0, phi02);
        stream.lineEnd();
        stream.lineStart();
        stream.point(sign1, phi02);
        stream.point(lambda12, phi02);
        clean = 0;
      } else if (sign0 !== sign1 && delta >= pi3) {
        if (abs3(lambda04 - sign0) < epsilon6) lambda04 -= sign0 * epsilon6;
        if (abs3(lambda12 - sign1) < epsilon6) lambda12 -= sign1 * epsilon6;
        phi02 = clipAntimeridianIntersect(lambda04, phi02, lambda12, phi12);
        stream.point(sign0, phi02);
        stream.lineEnd();
        stream.lineStart();
        stream.point(sign1, phi02);
        clean = 0;
      }
      stream.point(lambda04 = lambda12, phi02 = phi12);
      sign0 = sign1;
    },
    lineEnd: function() {
      stream.lineEnd();
      lambda04 = phi02 = NaN;
    },
    clean: function() {
      return 2 - clean;
    }
  };
}
function clipAntimeridianIntersect(lambda04, phi02, lambda12, phi12) {
  var cosPhi03, cosPhi1, sinLambda0Lambda1 = sin2(lambda04 - lambda12);
  return abs3(sinLambda0Lambda1) > epsilon6 ? atan((sin2(phi02) * (cosPhi1 = cos2(phi12)) * sin2(lambda12) - sin2(phi12) * (cosPhi03 = cos2(phi02)) * sin2(lambda04)) / (cosPhi03 * cosPhi1 * sinLambda0Lambda1)) : (phi02 + phi12) / 2;
}
function clipAntimeridianInterpolate(from, to, direction, stream) {
  var phi2;
  if (from == null) {
    phi2 = direction * halfPi2;
    stream.point(-pi3, phi2);
    stream.point(0, phi2);
    stream.point(pi3, phi2);
    stream.point(pi3, 0);
    stream.point(pi3, -phi2);
    stream.point(0, -phi2);
    stream.point(-pi3, -phi2);
    stream.point(-pi3, 0);
    stream.point(-pi3, phi2);
  } else if (abs3(from[0] - to[0]) > epsilon6) {
    var lambda = from[0] < to[0] ? pi3 : -pi3;
    phi2 = direction * lambda / 2;
    stream.point(-lambda, phi2);
    stream.point(0, phi2);
    stream.point(lambda, phi2);
  } else {
    stream.point(to[0], to[1]);
  }
}

// node_modules/d3-geo/src/clip/circle.js
function circle_default2(radius) {
  var cr = cos2(radius), delta = 2 * radians, smallRadius = cr > 0, notHemisphere = abs3(cr) > epsilon6;
  function interpolate(from, to, direction, stream) {
    circleStream(stream, radius, delta, direction, from, to);
  }
  function visible(lambda, phi2) {
    return cos2(lambda) * cos2(phi2) > cr;
  }
  function clipLine(stream) {
    var point0, c0, v0, v00, clean;
    return {
      lineStart: function() {
        v00 = v0 = false;
        clean = 1;
      },
      point: function(lambda, phi2) {
        var point1 = [lambda, phi2], point22, v2 = visible(lambda, phi2), c6 = smallRadius ? v2 ? 0 : code(lambda, phi2) : v2 ? code(lambda + (lambda < 0 ? pi3 : -pi3), phi2) : 0;
        if (!point0 && (v00 = v0 = v2)) stream.lineStart();
        if (v2 !== v0) {
          point22 = intersect2(point0, point1);
          if (!point22 || pointEqual_default(point0, point22) || pointEqual_default(point1, point22))
            point1[2] = 1;
        }
        if (v2 !== v0) {
          clean = 0;
          if (v2) {
            stream.lineStart();
            point22 = intersect2(point1, point0);
            stream.point(point22[0], point22[1]);
          } else {
            point22 = intersect2(point0, point1);
            stream.point(point22[0], point22[1], 2);
            stream.lineEnd();
          }
          point0 = point22;
        } else if (notHemisphere && point0 && smallRadius ^ v2) {
          var t;
          if (!(c6 & c0) && (t = intersect2(point1, point0, true))) {
            clean = 0;
            if (smallRadius) {
              stream.lineStart();
              stream.point(t[0][0], t[0][1]);
              stream.point(t[1][0], t[1][1]);
              stream.lineEnd();
            } else {
              stream.point(t[1][0], t[1][1]);
              stream.lineEnd();
              stream.lineStart();
              stream.point(t[0][0], t[0][1], 3);
            }
          }
        }
        if (v2 && (!point0 || !pointEqual_default(point0, point1))) {
          stream.point(point1[0], point1[1]);
        }
        point0 = point1, v0 = v2, c0 = c6;
      },
      lineEnd: function() {
        if (v0) stream.lineEnd();
        point0 = null;
      },
      // Rejoin first and last segments if there were intersections and the first
      // and last points were visible.
      clean: function() {
        return clean | (v00 && v0) << 1;
      }
    };
  }
  function intersect2(a4, b, two) {
    var pa = cartesian(a4), pb = cartesian(b);
    var n1 = [1, 0, 0], n2 = cartesianCross(pa, pb), n2n2 = cartesianDot(n2, n2), n1n2 = n2[0], determinant = n2n2 - n1n2 * n1n2;
    if (!determinant) return !two && a4;
    var c1 = cr * n2n2 / determinant, c22 = -cr * n1n2 / determinant, n1xn2 = cartesianCross(n1, n2), A = cartesianScale(n1, c1), B2 = cartesianScale(n2, c22);
    cartesianAddInPlace(A, B2);
    var u4 = n1xn2, w = cartesianDot(A, u4), uu = cartesianDot(u4, u4), t2 = w * w - uu * (cartesianDot(A, A) - 1);
    if (t2 < 0) return;
    var t = sqrt(t2), q = cartesianScale(u4, (-w - t) / uu);
    cartesianAddInPlace(q, A);
    q = spherical(q);
    if (!two) return q;
    var lambda04 = a4[0], lambda12 = b[0], phi02 = a4[1], phi12 = b[1], z;
    if (lambda12 < lambda04) z = lambda04, lambda04 = lambda12, lambda12 = z;
    var delta2 = lambda12 - lambda04, polar = abs3(delta2 - pi3) < epsilon6, meridian = polar || delta2 < epsilon6;
    if (!polar && phi12 < phi02) z = phi02, phi02 = phi12, phi12 = z;
    if (meridian ? polar ? phi02 + phi12 > 0 ^ q[1] < (abs3(q[0] - lambda04) < epsilon6 ? phi02 : phi12) : phi02 <= q[1] && q[1] <= phi12 : delta2 > pi3 ^ (lambda04 <= q[0] && q[0] <= lambda12)) {
      var q1 = cartesianScale(u4, (-w + t) / uu);
      cartesianAddInPlace(q1, A);
      return [q, spherical(q1)];
    }
  }
  function code(lambda, phi2) {
    var r = smallRadius ? radius : pi3 - radius, code2 = 0;
    if (lambda < -r) code2 |= 1;
    else if (lambda > r) code2 |= 2;
    if (phi2 < -r) code2 |= 4;
    else if (phi2 > r) code2 |= 8;
    return code2;
  }
  return clip_default(visible, clipLine, interpolate, smallRadius ? [0, -radius] : [-pi3, radius - pi3]);
}

// node_modules/d3-geo/src/clip/line.js
function line_default(a4, b, x06, y06, x12, y12) {
  var ax = a4[0], ay = a4[1], bx = b[0], by = b[1], t02 = 0, t12 = 1, dx = bx - ax, dy = by - ay, r;
  r = x06 - ax;
  if (!dx && r > 0) return;
  r /= dx;
  if (dx < 0) {
    if (r < t02) return;
    if (r < t12) t12 = r;
  } else if (dx > 0) {
    if (r > t12) return;
    if (r > t02) t02 = r;
  }
  r = x12 - ax;
  if (!dx && r < 0) return;
  r /= dx;
  if (dx < 0) {
    if (r > t12) return;
    if (r > t02) t02 = r;
  } else if (dx > 0) {
    if (r < t02) return;
    if (r < t12) t12 = r;
  }
  r = y06 - ay;
  if (!dy && r > 0) return;
  r /= dy;
  if (dy < 0) {
    if (r < t02) return;
    if (r < t12) t12 = r;
  } else if (dy > 0) {
    if (r > t12) return;
    if (r > t02) t02 = r;
  }
  r = y12 - ay;
  if (!dy && r < 0) return;
  r /= dy;
  if (dy < 0) {
    if (r > t12) return;
    if (r > t02) t02 = r;
  } else if (dy > 0) {
    if (r < t02) return;
    if (r < t12) t12 = r;
  }
  if (t02 > 0) a4[0] = ax + t02 * dx, a4[1] = ay + t02 * dy;
  if (t12 < 1) b[0] = ax + t12 * dx, b[1] = ay + t12 * dy;
  return true;
}

// node_modules/d3-geo/src/clip/rectangle.js
var clipMax = 1e9;
var clipMin = -clipMax;
function clipRectangle(x06, y06, x12, y12) {
  function visible(x4, y4) {
    return x06 <= x4 && x4 <= x12 && y06 <= y4 && y4 <= y12;
  }
  function interpolate(from, to, direction, stream) {
    var a4 = 0, a1 = 0;
    if (from == null || (a4 = corner(from, direction)) !== (a1 = corner(to, direction)) || comparePoint(from, to) < 0 ^ direction > 0) {
      do
        stream.point(a4 === 0 || a4 === 3 ? x06 : x12, a4 > 1 ? y12 : y06);
      while ((a4 = (a4 + direction + 4) % 4) !== a1);
    } else {
      stream.point(to[0], to[1]);
    }
  }
  function corner(p, direction) {
    return abs3(p[0] - x06) < epsilon6 ? direction > 0 ? 0 : 3 : abs3(p[0] - x12) < epsilon6 ? direction > 0 ? 2 : 1 : abs3(p[1] - y06) < epsilon6 ? direction > 0 ? 1 : 0 : direction > 0 ? 3 : 2;
  }
  function compareIntersection2(a4, b) {
    return comparePoint(a4.x, b.x);
  }
  function comparePoint(a4, b) {
    var ca3 = corner(a4, 1), cb = corner(b, 1);
    return ca3 !== cb ? ca3 - cb : ca3 === 0 ? b[1] - a4[1] : ca3 === 1 ? a4[0] - b[0] : ca3 === 2 ? a4[1] - b[1] : b[0] - a4[0];
  }
  return function(stream) {
    var activeStream = stream, bufferStream = buffer_default2(), segments, polygon, ring, x__, y__, v__, x_, y_, v_, first, clean;
    var clipStream = {
      point: point6,
      lineStart,
      lineEnd,
      polygonStart,
      polygonEnd
    };
    function point6(x4, y4) {
      if (visible(x4, y4)) activeStream.point(x4, y4);
    }
    function polygonInside() {
      var winding = 0;
      for (var i = 0, n = polygon.length; i < n; ++i) {
        for (var ring2 = polygon[i], j = 1, m3 = ring2.length, point7 = ring2[0], a0, a1, b0 = point7[0], b1 = point7[1]; j < m3; ++j) {
          a0 = b0, a1 = b1, point7 = ring2[j], b0 = point7[0], b1 = point7[1];
          if (a1 <= y12) {
            if (b1 > y12 && (b0 - a0) * (y12 - a1) > (b1 - a1) * (x06 - a0)) ++winding;
          } else {
            if (b1 <= y12 && (b0 - a0) * (y12 - a1) < (b1 - a1) * (x06 - a0)) --winding;
          }
        }
      }
      return winding;
    }
    function polygonStart() {
      activeStream = bufferStream, segments = [], polygon = [], clean = true;
    }
    function polygonEnd() {
      var startInside = polygonInside(), cleanInside = clean && startInside, visible2 = (segments = merge(segments)).length;
      if (cleanInside || visible2) {
        stream.polygonStart();
        if (cleanInside) {
          stream.lineStart();
          interpolate(null, null, 1, stream);
          stream.lineEnd();
        }
        if (visible2) {
          rejoin_default(segments, compareIntersection2, startInside, interpolate, stream);
        }
        stream.polygonEnd();
      }
      activeStream = stream, segments = polygon = ring = null;
    }
    function lineStart() {
      clipStream.point = linePoint2;
      if (polygon) polygon.push(ring = []);
      first = true;
      v_ = false;
      x_ = y_ = NaN;
    }
    function lineEnd() {
      if (segments) {
        linePoint2(x__, y__);
        if (v__ && v_) bufferStream.rejoin();
        segments.push(bufferStream.result());
      }
      clipStream.point = point6;
      if (v_) activeStream.lineEnd();
    }
    function linePoint2(x4, y4) {
      var v2 = visible(x4, y4);
      if (polygon) ring.push([x4, y4]);
      if (first) {
        x__ = x4, y__ = y4, v__ = v2;
        first = false;
        if (v2) {
          activeStream.lineStart();
          activeStream.point(x4, y4);
        }
      } else {
        if (v2 && v_) activeStream.point(x4, y4);
        else {
          var a4 = [x_ = Math.max(clipMin, Math.min(clipMax, x_)), y_ = Math.max(clipMin, Math.min(clipMax, y_))], b = [x4 = Math.max(clipMin, Math.min(clipMax, x4)), y4 = Math.max(clipMin, Math.min(clipMax, y4))];
          if (line_default(a4, b, x06, y06, x12, y12)) {
            if (!v_) {
              activeStream.lineStart();
              activeStream.point(a4[0], a4[1]);
            }
            activeStream.point(b[0], b[1]);
            if (!v2) activeStream.lineEnd();
            clean = false;
          } else if (v2) {
            activeStream.lineStart();
            activeStream.point(x4, y4);
            clean = false;
          }
        }
      }
      x_ = x4, y_ = y4, v_ = v2;
    }
    return clipStream;
  };
}

// node_modules/d3-geo/src/clip/extent.js
function extent_default2() {
  var x06 = 0, y06 = 0, x12 = 960, y12 = 500, cache, cacheStream, clip;
  return clip = {
    stream: function(stream) {
      return cache && cacheStream === stream ? cache : cache = clipRectangle(x06, y06, x12, y12)(cacheStream = stream);
    },
    extent: function(_) {
      return arguments.length ? (x06 = +_[0][0], y06 = +_[0][1], x12 = +_[1][0], y12 = +_[1][1], cache = cacheStream = null, clip) : [[x06, y06], [x12, y12]];
    }
  };
}

// node_modules/d3-geo/src/length.js
var lengthSum;
var lambda03;
var sinPhi02;
var cosPhi02;
var lengthStream = {
  sphere: noop,
  point: noop,
  lineStart: lengthLineStart,
  lineEnd: noop,
  polygonStart: noop,
  polygonEnd: noop
};
function lengthLineStart() {
  lengthStream.point = lengthPointFirst;
  lengthStream.lineEnd = lengthLineEnd;
}
function lengthLineEnd() {
  lengthStream.point = lengthStream.lineEnd = noop;
}
function lengthPointFirst(lambda, phi2) {
  lambda *= radians, phi2 *= radians;
  lambda03 = lambda, sinPhi02 = sin2(phi2), cosPhi02 = cos2(phi2);
  lengthStream.point = lengthPoint;
}
function lengthPoint(lambda, phi2) {
  lambda *= radians, phi2 *= radians;
  var sinPhi = sin2(phi2), cosPhi = cos2(phi2), delta = abs3(lambda - lambda03), cosDelta = cos2(delta), sinDelta = sin2(delta), x4 = cosPhi * sinDelta, y4 = cosPhi02 * sinPhi - sinPhi02 * cosPhi * cosDelta, z = sinPhi02 * sinPhi + cosPhi02 * cosPhi * cosDelta;
  lengthSum.add(atan2(sqrt(x4 * x4 + y4 * y4), z));
  lambda03 = lambda, sinPhi02 = sinPhi, cosPhi02 = cosPhi;
}
function length_default(object2) {
  lengthSum = new Adder();
  stream_default(object2, lengthStream);
  return +lengthSum;
}

// node_modules/d3-geo/src/distance.js
var coordinates = [null, null];
var object = { type: "LineString", coordinates };
function distance_default(a4, b) {
  coordinates[0] = a4;
  coordinates[1] = b;
  return length_default(object);
}

// node_modules/d3-geo/src/contains.js
var containsObjectType = {
  Feature: function(object2, point6) {
    return containsGeometry(object2.geometry, point6);
  },
  FeatureCollection: function(object2, point6) {
    var features = object2.features, i = -1, n = features.length;
    while (++i < n) if (containsGeometry(features[i].geometry, point6)) return true;
    return false;
  }
};
var containsGeometryType = {
  Sphere: function() {
    return true;
  },
  Point: function(object2, point6) {
    return containsPoint(object2.coordinates, point6);
  },
  MultiPoint: function(object2, point6) {
    var coordinates2 = object2.coordinates, i = -1, n = coordinates2.length;
    while (++i < n) if (containsPoint(coordinates2[i], point6)) return true;
    return false;
  },
  LineString: function(object2, point6) {
    return containsLine(object2.coordinates, point6);
  },
  MultiLineString: function(object2, point6) {
    var coordinates2 = object2.coordinates, i = -1, n = coordinates2.length;
    while (++i < n) if (containsLine(coordinates2[i], point6)) return true;
    return false;
  },
  Polygon: function(object2, point6) {
    return containsPolygon(object2.coordinates, point6);
  },
  MultiPolygon: function(object2, point6) {
    var coordinates2 = object2.coordinates, i = -1, n = coordinates2.length;
    while (++i < n) if (containsPolygon(coordinates2[i], point6)) return true;
    return false;
  },
  GeometryCollection: function(object2, point6) {
    var geometries = object2.geometries, i = -1, n = geometries.length;
    while (++i < n) if (containsGeometry(geometries[i], point6)) return true;
    return false;
  }
};
function containsGeometry(geometry, point6) {
  return geometry && containsGeometryType.hasOwnProperty(geometry.type) ? containsGeometryType[geometry.type](geometry, point6) : false;
}
function containsPoint(coordinates2, point6) {
  return distance_default(coordinates2, point6) === 0;
}
function containsLine(coordinates2, point6) {
  var ao, bo, ab4;
  for (var i = 0, n = coordinates2.length; i < n; i++) {
    bo = distance_default(coordinates2[i], point6);
    if (bo === 0) return true;
    if (i > 0) {
      ab4 = distance_default(coordinates2[i], coordinates2[i - 1]);
      if (ab4 > 0 && ao <= ab4 && bo <= ab4 && (ao + bo - ab4) * (1 - Math.pow((ao - bo) / ab4, 2)) < epsilon22 * ab4)
        return true;
    }
    ao = bo;
  }
  return false;
}
function containsPolygon(coordinates2, point6) {
  return !!polygonContains_default(coordinates2.map(ringRadians), pointRadians(point6));
}
function ringRadians(ring) {
  return ring = ring.map(pointRadians), ring.pop(), ring;
}
function pointRadians(point6) {
  return [point6[0] * radians, point6[1] * radians];
}
function contains_default2(object2, point6) {
  return (object2 && containsObjectType.hasOwnProperty(object2.type) ? containsObjectType[object2.type] : containsGeometry)(object2, point6);
}

// node_modules/d3-geo/src/graticule.js
function graticuleX(y06, y12, dy) {
  var y4 = range(y06, y12 - epsilon6, dy).concat(y12);
  return function(x4) {
    return y4.map(function(y5) {
      return [x4, y5];
    });
  };
}
function graticuleY(x06, x12, dx) {
  var x4 = range(x06, x12 - epsilon6, dx).concat(x12);
  return function(y4) {
    return x4.map(function(x5) {
      return [x5, y4];
    });
  };
}
function graticule() {
  var x12, x06, X13, X03, y12, y06, Y13, Y03, dx = 10, dy = dx, DX = 90, DY = 360, x4, y4, X3, Y3, precision = 2.5;
  function graticule2() {
    return { type: "MultiLineString", coordinates: lines() };
  }
  function lines() {
    return range(ceil(X03 / DX) * DX, X13, DX).map(X3).concat(range(ceil(Y03 / DY) * DY, Y13, DY).map(Y3)).concat(range(ceil(x06 / dx) * dx, x12, dx).filter(function(x5) {
      return abs3(x5 % DX) > epsilon6;
    }).map(x4)).concat(range(ceil(y06 / dy) * dy, y12, dy).filter(function(y5) {
      return abs3(y5 % DY) > epsilon6;
    }).map(y4));
  }
  graticule2.lines = function() {
    return lines().map(function(coordinates2) {
      return { type: "LineString", coordinates: coordinates2 };
    });
  };
  graticule2.outline = function() {
    return {
      type: "Polygon",
      coordinates: [
        X3(X03).concat(
          Y3(Y13).slice(1),
          X3(X13).reverse().slice(1),
          Y3(Y03).reverse().slice(1)
        )
      ]
    };
  };
  graticule2.extent = function(_) {
    if (!arguments.length) return graticule2.extentMinor();
    return graticule2.extentMajor(_).extentMinor(_);
  };
  graticule2.extentMajor = function(_) {
    if (!arguments.length) return [[X03, Y03], [X13, Y13]];
    X03 = +_[0][0], X13 = +_[1][0];
    Y03 = +_[0][1], Y13 = +_[1][1];
    if (X03 > X13) _ = X03, X03 = X13, X13 = _;
    if (Y03 > Y13) _ = Y03, Y03 = Y13, Y13 = _;
    return graticule2.precision(precision);
  };
  graticule2.extentMinor = function(_) {
    if (!arguments.length) return [[x06, y06], [x12, y12]];
    x06 = +_[0][0], x12 = +_[1][0];
    y06 = +_[0][1], y12 = +_[1][1];
    if (x06 > x12) _ = x06, x06 = x12, x12 = _;
    if (y06 > y12) _ = y06, y06 = y12, y12 = _;
    return graticule2.precision(precision);
  };
  graticule2.step = function(_) {
    if (!arguments.length) return graticule2.stepMinor();
    return graticule2.stepMajor(_).stepMinor(_);
  };
  graticule2.stepMajor = function(_) {
    if (!arguments.length) return [DX, DY];
    DX = +_[0], DY = +_[1];
    return graticule2;
  };
  graticule2.stepMinor = function(_) {
    if (!arguments.length) return [dx, dy];
    dx = +_[0], dy = +_[1];
    return graticule2;
  };
  graticule2.precision = function(_) {
    if (!arguments.length) return precision;
    precision = +_;
    x4 = graticuleX(y06, y12, 90);
    y4 = graticuleY(x06, x12, precision);
    X3 = graticuleX(Y03, Y13, 90);
    Y3 = graticuleY(X03, X13, precision);
    return graticule2;
  };
  return graticule2.extentMajor([[-180, -90 + epsilon6], [180, 90 - epsilon6]]).extentMinor([[-180, -80 - epsilon6], [180, 80 + epsilon6]]);
}
function graticule10() {
  return graticule()();
}

// node_modules/d3-geo/src/interpolate.js
function interpolate_default(a4, b) {
  var x06 = a4[0] * radians, y06 = a4[1] * radians, x12 = b[0] * radians, y12 = b[1] * radians, cy0 = cos2(y06), sy0 = sin2(y06), cy1 = cos2(y12), sy1 = sin2(y12), kx0 = cy0 * cos2(x06), ky0 = cy0 * sin2(x06), kx1 = cy1 * cos2(x12), ky1 = cy1 * sin2(x12), d = 2 * asin(sqrt(haversin(y12 - y06) + cy0 * cy1 * haversin(x12 - x06))), k2 = sin2(d);
  var interpolate = d ? function(t) {
    var B2 = sin2(t *= d) / k2, A = sin2(d - t) / k2, x4 = A * kx0 + B2 * kx1, y4 = A * ky0 + B2 * ky1, z = A * sy0 + B2 * sy1;
    return [
      atan2(y4, x4) * degrees,
      atan2(z, sqrt(x4 * x4 + y4 * y4)) * degrees
    ];
  } : function() {
    return [x06 * degrees, y06 * degrees];
  };
  interpolate.distance = d;
  return interpolate;
}

// node_modules/d3-geo/src/identity.js
var identity_default3 = (x4) => x4;

// node_modules/d3-geo/src/path/area.js
var areaSum2 = new Adder();
var areaRingSum2 = new Adder();
var x00;
var y00;
var x02;
var y02;
var areaStream2 = {
  point: noop,
  lineStart: noop,
  lineEnd: noop,
  polygonStart: function() {
    areaStream2.lineStart = areaRingStart2;
    areaStream2.lineEnd = areaRingEnd2;
  },
  polygonEnd: function() {
    areaStream2.lineStart = areaStream2.lineEnd = areaStream2.point = noop;
    areaSum2.add(abs3(areaRingSum2));
    areaRingSum2 = new Adder();
  },
  result: function() {
    var area = areaSum2 / 2;
    areaSum2 = new Adder();
    return area;
  }
};
function areaRingStart2() {
  areaStream2.point = areaPointFirst2;
}
function areaPointFirst2(x4, y4) {
  areaStream2.point = areaPoint2;
  x00 = x02 = x4, y00 = y02 = y4;
}
function areaPoint2(x4, y4) {
  areaRingSum2.add(y02 * x4 - x02 * y4);
  x02 = x4, y02 = y4;
}
function areaRingEnd2() {
  areaPoint2(x00, y00);
}
var area_default3 = areaStream2;

// node_modules/d3-geo/src/path/bounds.js
var x03 = Infinity;
var y03 = x03;
var x1 = -x03;
var y1 = x1;
var boundsStream2 = {
  point: boundsPoint2,
  lineStart: noop,
  lineEnd: noop,
  polygonStart: noop,
  polygonEnd: noop,
  result: function() {
    var bounds = [[x03, y03], [x1, y1]];
    x1 = y1 = -(y03 = x03 = Infinity);
    return bounds;
  }
};
function boundsPoint2(x4, y4) {
  if (x4 < x03) x03 = x4;
  if (x4 > x1) x1 = x4;
  if (y4 < y03) y03 = y4;
  if (y4 > y1) y1 = y4;
}
var bounds_default2 = boundsStream2;

// node_modules/d3-geo/src/path/centroid.js
var X02 = 0;
var Y02 = 0;
var Z02 = 0;
var X12 = 0;
var Y12 = 0;
var Z12 = 0;
var X22 = 0;
var Y22 = 0;
var Z22 = 0;
var x002;
var y002;
var x04;
var y04;
var centroidStream2 = {
  point: centroidPoint2,
  lineStart: centroidLineStart2,
  lineEnd: centroidLineEnd2,
  polygonStart: function() {
    centroidStream2.lineStart = centroidRingStart2;
    centroidStream2.lineEnd = centroidRingEnd2;
  },
  polygonEnd: function() {
    centroidStream2.point = centroidPoint2;
    centroidStream2.lineStart = centroidLineStart2;
    centroidStream2.lineEnd = centroidLineEnd2;
  },
  result: function() {
    var centroid = Z22 ? [X22 / Z22, Y22 / Z22] : Z12 ? [X12 / Z12, Y12 / Z12] : Z02 ? [X02 / Z02, Y02 / Z02] : [NaN, NaN];
    X02 = Y02 = Z02 = X12 = Y12 = Z12 = X22 = Y22 = Z22 = 0;
    return centroid;
  }
};
function centroidPoint2(x4, y4) {
  X02 += x4;
  Y02 += y4;
  ++Z02;
}
function centroidLineStart2() {
  centroidStream2.point = centroidPointFirstLine;
}
function centroidPointFirstLine(x4, y4) {
  centroidStream2.point = centroidPointLine;
  centroidPoint2(x04 = x4, y04 = y4);
}
function centroidPointLine(x4, y4) {
  var dx = x4 - x04, dy = y4 - y04, z = sqrt(dx * dx + dy * dy);
  X12 += z * (x04 + x4) / 2;
  Y12 += z * (y04 + y4) / 2;
  Z12 += z;
  centroidPoint2(x04 = x4, y04 = y4);
}
function centroidLineEnd2() {
  centroidStream2.point = centroidPoint2;
}
function centroidRingStart2() {
  centroidStream2.point = centroidPointFirstRing;
}
function centroidRingEnd2() {
  centroidPointRing(x002, y002);
}
function centroidPointFirstRing(x4, y4) {
  centroidStream2.point = centroidPointRing;
  centroidPoint2(x002 = x04 = x4, y002 = y04 = y4);
}
function centroidPointRing(x4, y4) {
  var dx = x4 - x04, dy = y4 - y04, z = sqrt(dx * dx + dy * dy);
  X12 += z * (x04 + x4) / 2;
  Y12 += z * (y04 + y4) / 2;
  Z12 += z;
  z = y04 * x4 - x04 * y4;
  X22 += z * (x04 + x4);
  Y22 += z * (y04 + y4);
  Z22 += z * 3;
  centroidPoint2(x04 = x4, y04 = y4);
}
var centroid_default2 = centroidStream2;

// node_modules/d3-geo/src/path/context.js
function PathContext(context) {
  this._context = context;
}
PathContext.prototype = {
  _radius: 4.5,
  pointRadius: function(_) {
    return this._radius = _, this;
  },
  polygonStart: function() {
    this._line = 0;
  },
  polygonEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._point = 0;
  },
  lineEnd: function() {
    if (this._line === 0) this._context.closePath();
    this._point = NaN;
  },
  point: function(x4, y4) {
    switch (this._point) {
      case 0: {
        this._context.moveTo(x4, y4);
        this._point = 1;
        break;
      }
      case 1: {
        this._context.lineTo(x4, y4);
        break;
      }
      default: {
        this._context.moveTo(x4 + this._radius, y4);
        this._context.arc(x4, y4, this._radius, 0, tau4);
        break;
      }
    }
  },
  result: noop
};

// node_modules/d3-geo/src/path/measure.js
var lengthSum2 = new Adder();
var lengthRing;
var x003;
var y003;
var x05;
var y05;
var lengthStream2 = {
  point: noop,
  lineStart: function() {
    lengthStream2.point = lengthPointFirst2;
  },
  lineEnd: function() {
    if (lengthRing) lengthPoint2(x003, y003);
    lengthStream2.point = noop;
  },
  polygonStart: function() {
    lengthRing = true;
  },
  polygonEnd: function() {
    lengthRing = null;
  },
  result: function() {
    var length3 = +lengthSum2;
    lengthSum2 = new Adder();
    return length3;
  }
};
function lengthPointFirst2(x4, y4) {
  lengthStream2.point = lengthPoint2;
  x003 = x05 = x4, y003 = y05 = y4;
}
function lengthPoint2(x4, y4) {
  x05 -= x4, y05 -= y4;
  lengthSum2.add(sqrt(x05 * x05 + y05 * y05));
  x05 = x4, y05 = y4;
}
var measure_default = lengthStream2;

// node_modules/d3-geo/src/path/string.js
var cacheDigits;
var cacheAppend;
var cacheRadius;
var cacheCircle;
var PathString = class {
  constructor(digits) {
    this._append = digits == null ? append2 : appendRound2(digits);
    this._radius = 4.5;
    this._ = "";
  }
  pointRadius(_) {
    this._radius = +_;
    return this;
  }
  polygonStart() {
    this._line = 0;
  }
  polygonEnd() {
    this._line = NaN;
  }
  lineStart() {
    this._point = 0;
  }
  lineEnd() {
    if (this._line === 0) this._ += "Z";
    this._point = NaN;
  }
  point(x4, y4) {
    switch (this._point) {
      case 0: {
        this._append`M${x4},${y4}`;
        this._point = 1;
        break;
      }
      case 1: {
        this._append`L${x4},${y4}`;
        break;
      }
      default: {
        this._append`M${x4},${y4}`;
        if (this._radius !== cacheRadius || this._append !== cacheAppend) {
          const r = this._radius;
          const s2 = this._;
          this._ = "";
          this._append`m0,${r}a${r},${r} 0 1,1 0,${-2 * r}a${r},${r} 0 1,1 0,${2 * r}z`;
          cacheRadius = r;
          cacheAppend = this._append;
          cacheCircle = this._;
          this._ = s2;
        }
        this._ += cacheCircle;
        break;
      }
    }
  }
  result() {
    const result = this._;
    this._ = "";
    return result.length ? result : null;
  }
};
function append2(strings) {
  let i = 1;
  this._ += strings[0];
  for (const j = strings.length; i < j; ++i) {
    this._ += arguments[i] + strings[i];
  }
}
function appendRound2(digits) {
  const d = Math.floor(digits);
  if (!(d >= 0)) throw new RangeError(`invalid digits: ${digits}`);
  if (d > 15) return append2;
  if (d !== cacheDigits) {
    const k2 = 10 ** d;
    cacheDigits = d;
    cacheAppend = function append3(strings) {
      let i = 1;
      this._ += strings[0];
      for (const j = strings.length; i < j; ++i) {
        this._ += Math.round(arguments[i] * k2) / k2 + strings[i];
      }
    };
  }
  return cacheAppend;
}

// node_modules/d3-geo/src/path/index.js
function path_default(projection2, context) {
  let digits = 3, pointRadius = 4.5, projectionStream, contextStream;
  function path2(object2) {
    if (object2) {
      if (typeof pointRadius === "function") contextStream.pointRadius(+pointRadius.apply(this, arguments));
      stream_default(object2, projectionStream(contextStream));
    }
    return contextStream.result();
  }
  path2.area = function(object2) {
    stream_default(object2, projectionStream(area_default3));
    return area_default3.result();
  };
  path2.measure = function(object2) {
    stream_default(object2, projectionStream(measure_default));
    return measure_default.result();
  };
  path2.bounds = function(object2) {
    stream_default(object2, projectionStream(bounds_default2));
    return bounds_default2.result();
  };
  path2.centroid = function(object2) {
    stream_default(object2, projectionStream(centroid_default2));
    return centroid_default2.result();
  };
  path2.projection = function(_) {
    if (!arguments.length) return projection2;
    projectionStream = _ == null ? (projection2 = null, identity_default3) : (projection2 = _).stream;
    return path2;
  };
  path2.context = function(_) {
    if (!arguments.length) return context;
    contextStream = _ == null ? (context = null, new PathString(digits)) : new PathContext(context = _);
    if (typeof pointRadius !== "function") contextStream.pointRadius(pointRadius);
    return path2;
  };
  path2.pointRadius = function(_) {
    if (!arguments.length) return pointRadius;
    pointRadius = typeof _ === "function" ? _ : (contextStream.pointRadius(+_), +_);
    return path2;
  };
  path2.digits = function(_) {
    if (!arguments.length) return digits;
    if (_ == null) digits = null;
    else {
      const d = Math.floor(_);
      if (!(d >= 0)) throw new RangeError(`invalid digits: ${_}`);
      digits = d;
    }
    if (context === null) contextStream = new PathString(digits);
    return path2;
  };
  return path2.projection(projection2).digits(digits).context(context);
}

// node_modules/d3-geo/src/transform.js
function transform_default(methods) {
  return {
    stream: transformer(methods)
  };
}
function transformer(methods) {
  return function(stream) {
    var s2 = new TransformStream();
    for (var key in methods) s2[key] = methods[key];
    s2.stream = stream;
    return s2;
  };
}
function TransformStream() {
}
TransformStream.prototype = {
  constructor: TransformStream,
  point: function(x4, y4) {
    this.stream.point(x4, y4);
  },
  sphere: function() {
    this.stream.sphere();
  },
  lineStart: function() {
    this.stream.lineStart();
  },
  lineEnd: function() {
    this.stream.lineEnd();
  },
  polygonStart: function() {
    this.stream.polygonStart();
  },
  polygonEnd: function() {
    this.stream.polygonEnd();
  }
};

// node_modules/d3-geo/src/projection/fit.js
function fit(projection2, fitBounds, object2) {
  var clip = projection2.clipExtent && projection2.clipExtent();
  projection2.scale(150).translate([0, 0]);
  if (clip != null) projection2.clipExtent(null);
  stream_default(object2, projection2.stream(bounds_default2));
  fitBounds(bounds_default2.result());
  if (clip != null) projection2.clipExtent(clip);
  return projection2;
}
function fitExtent(projection2, extent2, object2) {
  return fit(projection2, function(b) {
    var w = extent2[1][0] - extent2[0][0], h = extent2[1][1] - extent2[0][1], k2 = Math.min(w / (b[1][0] - b[0][0]), h / (b[1][1] - b[0][1])), x4 = +extent2[0][0] + (w - k2 * (b[1][0] + b[0][0])) / 2, y4 = +extent2[0][1] + (h - k2 * (b[1][1] + b[0][1])) / 2;
    projection2.scale(150 * k2).translate([x4, y4]);
  }, object2);
}
function fitSize(projection2, size, object2) {
  return fitExtent(projection2, [[0, 0], size], object2);
}
function fitWidth(projection2, width, object2) {
  return fit(projection2, function(b) {
    var w = +width, k2 = w / (b[1][0] - b[0][0]), x4 = (w - k2 * (b[1][0] + b[0][0])) / 2, y4 = -k2 * b[0][1];
    projection2.scale(150 * k2).translate([x4, y4]);
  }, object2);
}
function fitHeight(projection2, height, object2) {
  return fit(projection2, function(b) {
    var h = +height, k2 = h / (b[1][1] - b[0][1]), x4 = -k2 * b[0][0], y4 = (h - k2 * (b[1][1] + b[0][1])) / 2;
    projection2.scale(150 * k2).translate([x4, y4]);
  }, object2);
}

// node_modules/d3-geo/src/projection/resample.js
var maxDepth = 16;
var cosMinDistance = cos2(30 * radians);
function resample_default(project, delta2) {
  return +delta2 ? resample(project, delta2) : resampleNone(project);
}
function resampleNone(project) {
  return transformer({
    point: function(x4, y4) {
      x4 = project(x4, y4);
      this.stream.point(x4[0], x4[1]);
    }
  });
}
function resample(project, delta2) {
  function resampleLineTo(x06, y06, lambda04, a0, b0, c0, x12, y12, lambda12, a1, b1, c1, depth, stream) {
    var dx = x12 - x06, dy = y12 - y06, d2 = dx * dx + dy * dy;
    if (d2 > 4 * delta2 && depth--) {
      var a4 = a0 + a1, b = b0 + b1, c6 = c0 + c1, m3 = sqrt(a4 * a4 + b * b + c6 * c6), phi2 = asin(c6 /= m3), lambda22 = abs3(abs3(c6) - 1) < epsilon6 || abs3(lambda04 - lambda12) < epsilon6 ? (lambda04 + lambda12) / 2 : atan2(b, a4), p = project(lambda22, phi2), x22 = p[0], y22 = p[1], dx2 = x22 - x06, dy2 = y22 - y06, dz = dy * dx2 - dx * dy2;
      if (dz * dz / d2 > delta2 || abs3((dx * dx2 + dy * dy2) / d2 - 0.5) > 0.3 || a0 * a1 + b0 * b1 + c0 * c1 < cosMinDistance) {
        resampleLineTo(x06, y06, lambda04, a0, b0, c0, x22, y22, lambda22, a4 /= m3, b /= m3, c6, depth, stream);
        stream.point(x22, y22);
        resampleLineTo(x22, y22, lambda22, a4, b, c6, x12, y12, lambda12, a1, b1, c1, depth, stream);
      }
    }
  }
  return function(stream) {
    var lambda004, x004, y004, a00, b00, c00, lambda04, x06, y06, a0, b0, c0;
    var resampleStream = {
      point: point6,
      lineStart,
      lineEnd,
      polygonStart: function() {
        stream.polygonStart();
        resampleStream.lineStart = ringStart;
      },
      polygonEnd: function() {
        stream.polygonEnd();
        resampleStream.lineStart = lineStart;
      }
    };
    function point6(x4, y4) {
      x4 = project(x4, y4);
      stream.point(x4[0], x4[1]);
    }
    function lineStart() {
      x06 = NaN;
      resampleStream.point = linePoint2;
      stream.lineStart();
    }
    function linePoint2(lambda, phi2) {
      var c6 = cartesian([lambda, phi2]), p = project(lambda, phi2);
      resampleLineTo(x06, y06, lambda04, a0, b0, c0, x06 = p[0], y06 = p[1], lambda04 = lambda, a0 = c6[0], b0 = c6[1], c0 = c6[2], maxDepth, stream);
      stream.point(x06, y06);
    }
    function lineEnd() {
      resampleStream.point = point6;
      stream.lineEnd();
    }
    function ringStart() {
      lineStart();
      resampleStream.point = ringPoint;
      resampleStream.lineEnd = ringEnd;
    }
    function ringPoint(lambda, phi2) {
      linePoint2(lambda004 = lambda, phi2), x004 = x06, y004 = y06, a00 = a0, b00 = b0, c00 = c0;
      resampleStream.point = linePoint2;
    }
    function ringEnd() {
      resampleLineTo(x06, y06, lambda04, a0, b0, c0, x004, y004, lambda004, a00, b00, c00, maxDepth, stream);
      resampleStream.lineEnd = lineEnd;
      lineEnd();
    }
    return resampleStream;
  };
}

// node_modules/d3-geo/src/projection/index.js
var transformRadians = transformer({
  point: function(x4, y4) {
    this.stream.point(x4 * radians, y4 * radians);
  }
});
function transformRotate(rotate) {
  return transformer({
    point: function(x4, y4) {
      var r = rotate(x4, y4);
      return this.stream.point(r[0], r[1]);
    }
  });
}
function scaleTranslate(k2, dx, dy, sx, sy) {
  function transform2(x4, y4) {
    x4 *= sx;
    y4 *= sy;
    return [dx + k2 * x4, dy - k2 * y4];
  }
  transform2.invert = function(x4, y4) {
    return [(x4 - dx) / k2 * sx, (dy - y4) / k2 * sy];
  };
  return transform2;
}
function scaleTranslateRotate(k2, dx, dy, sx, sy, alpha) {
  if (!alpha) return scaleTranslate(k2, dx, dy, sx, sy);
  var cosAlpha = cos2(alpha), sinAlpha = sin2(alpha), a4 = cosAlpha * k2, b = sinAlpha * k2, ai = cosAlpha / k2, bi = sinAlpha / k2, ci = (sinAlpha * dy - cosAlpha * dx) / k2, fi = (sinAlpha * dx + cosAlpha * dy) / k2;
  function transform2(x4, y4) {
    x4 *= sx;
    y4 *= sy;
    return [a4 * x4 - b * y4 + dx, dy - b * x4 - a4 * y4];
  }
  transform2.invert = function(x4, y4) {
    return [sx * (ai * x4 - bi * y4 + ci), sy * (fi - bi * x4 - ai * y4)];
  };
  return transform2;
}
function projection(project) {
  return projectionMutator(function() {
    return project;
  })();
}
function projectionMutator(projectAt) {
  var project, k2 = 150, x4 = 480, y4 = 250, lambda = 0, phi2 = 0, deltaLambda = 0, deltaPhi = 0, deltaGamma = 0, rotate, alpha = 0, sx = 1, sy = 1, theta = null, preclip = antimeridian_default, x06 = null, y06, x12, y12, postclip = identity_default3, delta2 = 0.5, projectResample, projectTransform, projectRotateTransform, cache, cacheStream;
  function projection2(point6) {
    return projectRotateTransform(point6[0] * radians, point6[1] * radians);
  }
  function invert(point6) {
    point6 = projectRotateTransform.invert(point6[0], point6[1]);
    return point6 && [point6[0] * degrees, point6[1] * degrees];
  }
  projection2.stream = function(stream) {
    return cache && cacheStream === stream ? cache : cache = transformRadians(transformRotate(rotate)(preclip(projectResample(postclip(cacheStream = stream)))));
  };
  projection2.preclip = function(_) {
    return arguments.length ? (preclip = _, theta = void 0, reset()) : preclip;
  };
  projection2.postclip = function(_) {
    return arguments.length ? (postclip = _, x06 = y06 = x12 = y12 = null, reset()) : postclip;
  };
  projection2.clipAngle = function(_) {
    return arguments.length ? (preclip = +_ ? circle_default2(theta = _ * radians) : (theta = null, antimeridian_default), reset()) : theta * degrees;
  };
  projection2.clipExtent = function(_) {
    return arguments.length ? (postclip = _ == null ? (x06 = y06 = x12 = y12 = null, identity_default3) : clipRectangle(x06 = +_[0][0], y06 = +_[0][1], x12 = +_[1][0], y12 = +_[1][1]), reset()) : x06 == null ? null : [[x06, y06], [x12, y12]];
  };
  projection2.scale = function(_) {
    return arguments.length ? (k2 = +_, recenter()) : k2;
  };
  projection2.translate = function(_) {
    return arguments.length ? (x4 = +_[0], y4 = +_[1], recenter()) : [x4, y4];
  };
  projection2.center = function(_) {
    return arguments.length ? (lambda = _[0] % 360 * radians, phi2 = _[1] % 360 * radians, recenter()) : [lambda * degrees, phi2 * degrees];
  };
  projection2.rotate = function(_) {
    return arguments.length ? (deltaLambda = _[0] % 360 * radians, deltaPhi = _[1] % 360 * radians, deltaGamma = _.length > 2 ? _[2] % 360 * radians : 0, recenter()) : [deltaLambda * degrees, deltaPhi * degrees, deltaGamma * degrees];
  };
  projection2.angle = function(_) {
    return arguments.length ? (alpha = _ % 360 * radians, recenter()) : alpha * degrees;
  };
  projection2.reflectX = function(_) {
    return arguments.length ? (sx = _ ? -1 : 1, recenter()) : sx < 0;
  };
  projection2.reflectY = function(_) {
    return arguments.length ? (sy = _ ? -1 : 1, recenter()) : sy < 0;
  };
  projection2.precision = function(_) {
    return arguments.length ? (projectResample = resample_default(projectTransform, delta2 = _ * _), reset()) : sqrt(delta2);
  };
  projection2.fitExtent = function(extent2, object2) {
    return fitExtent(projection2, extent2, object2);
  };
  projection2.fitSize = function(size, object2) {
    return fitSize(projection2, size, object2);
  };
  projection2.fitWidth = function(width, object2) {
    return fitWidth(projection2, width, object2);
  };
  projection2.fitHeight = function(height, object2) {
    return fitHeight(projection2, height, object2);
  };
  function recenter() {
    var center2 = scaleTranslateRotate(k2, 0, 0, sx, sy, alpha).apply(null, project(lambda, phi2)), transform2 = scaleTranslateRotate(k2, x4 - center2[0], y4 - center2[1], sx, sy, alpha);
    rotate = rotateRadians(deltaLambda, deltaPhi, deltaGamma);
    projectTransform = compose_default(project, transform2);
    projectRotateTransform = compose_default(rotate, projectTransform);
    projectResample = resample_default(projectTransform, delta2);
    return reset();
  }
  function reset() {
    cache = cacheStream = null;
    return projection2;
  }
  return function() {
    project = projectAt.apply(this, arguments);
    projection2.invert = project.invert && invert;
    return recenter();
  };
}

// node_modules/d3-geo/src/projection/conic.js
function conicProjection(projectAt) {
  var phi02 = 0, phi12 = pi3 / 3, m3 = projectionMutator(projectAt), p = m3(phi02, phi12);
  p.parallels = function(_) {
    return arguments.length ? m3(phi02 = _[0] * radians, phi12 = _[1] * radians) : [phi02 * degrees, phi12 * degrees];
  };
  return p;
}

// node_modules/d3-geo/src/projection/cylindricalEqualArea.js
function cylindricalEqualAreaRaw(phi02) {
  var cosPhi03 = cos2(phi02);
  function forward(lambda, phi2) {
    return [lambda * cosPhi03, sin2(phi2) / cosPhi03];
  }
  forward.invert = function(x4, y4) {
    return [x4 / cosPhi03, asin(y4 * cosPhi03)];
  };
  return forward;
}

// node_modules/d3-geo/src/projection/conicEqualArea.js
function conicEqualAreaRaw(y06, y12) {
  var sy0 = sin2(y06), n = (sy0 + sin2(y12)) / 2;
  if (abs3(n) < epsilon6) return cylindricalEqualAreaRaw(y06);
  var c6 = 1 + sy0 * (2 * n - sy0), r0 = sqrt(c6) / n;
  function project(x4, y4) {
    var r = sqrt(c6 - 2 * n * sin2(y4)) / n;
    return [r * sin2(x4 *= n), r0 - r * cos2(x4)];
  }
  project.invert = function(x4, y4) {
    var r0y = r0 - y4, l = atan2(x4, abs3(r0y)) * sign(r0y);
    if (r0y * n < 0)
      l -= pi3 * sign(x4) * sign(r0y);
    return [l / n, asin((c6 - (x4 * x4 + r0y * r0y) * n * n) / (2 * n))];
  };
  return project;
}
function conicEqualArea_default() {
  return conicProjection(conicEqualAreaRaw).scale(155.424).center([0, 33.6442]);
}

// node_modules/d3-geo/src/projection/albers.js
function albers_default() {
  return conicEqualArea_default().parallels([29.5, 45.5]).scale(1070).translate([480, 250]).rotate([96, 0]).center([-0.6, 38.7]);
}

// node_modules/d3-geo/src/projection/albersUsa.js
function multiplex(streams) {
  var n = streams.length;
  return {
    point: function(x4, y4) {
      var i = -1;
      while (++i < n) streams[i].point(x4, y4);
    },
    sphere: function() {
      var i = -1;
      while (++i < n) streams[i].sphere();
    },
    lineStart: function() {
      var i = -1;
      while (++i < n) streams[i].lineStart();
    },
    lineEnd: function() {
      var i = -1;
      while (++i < n) streams[i].lineEnd();
    },
    polygonStart: function() {
      var i = -1;
      while (++i < n) streams[i].polygonStart();
    },
    polygonEnd: function() {
      var i = -1;
      while (++i < n) streams[i].polygonEnd();
    }
  };
}
function albersUsa_default() {
  var cache, cacheStream, lower48 = albers_default(), lower48Point, alaska = conicEqualArea_default().rotate([154, 0]).center([-2, 58.5]).parallels([55, 65]), alaskaPoint, hawaii = conicEqualArea_default().rotate([157, 0]).center([-3, 19.9]).parallels([8, 18]), hawaiiPoint, point6, pointStream = { point: function(x4, y4) {
    point6 = [x4, y4];
  } };
  function albersUsa(coordinates2) {
    var x4 = coordinates2[0], y4 = coordinates2[1];
    return point6 = null, (lower48Point.point(x4, y4), point6) || (alaskaPoint.point(x4, y4), point6) || (hawaiiPoint.point(x4, y4), point6);
  }
  albersUsa.invert = function(coordinates2) {
    var k2 = lower48.scale(), t = lower48.translate(), x4 = (coordinates2[0] - t[0]) / k2, y4 = (coordinates2[1] - t[1]) / k2;
    return (y4 >= 0.12 && y4 < 0.234 && x4 >= -0.425 && x4 < -0.214 ? alaska : y4 >= 0.166 && y4 < 0.234 && x4 >= -0.214 && x4 < -0.115 ? hawaii : lower48).invert(coordinates2);
  };
  albersUsa.stream = function(stream) {
    return cache && cacheStream === stream ? cache : cache = multiplex([lower48.stream(cacheStream = stream), alaska.stream(stream), hawaii.stream(stream)]);
  };
  albersUsa.precision = function(_) {
    if (!arguments.length) return lower48.precision();
    lower48.precision(_), alaska.precision(_), hawaii.precision(_);
    return reset();
  };
  albersUsa.scale = function(_) {
    if (!arguments.length) return lower48.scale();
    lower48.scale(_), alaska.scale(_ * 0.35), hawaii.scale(_);
    return albersUsa.translate(lower48.translate());
  };
  albersUsa.translate = function(_) {
    if (!arguments.length) return lower48.translate();
    var k2 = lower48.scale(), x4 = +_[0], y4 = +_[1];
    lower48Point = lower48.translate(_).clipExtent([[x4 - 0.455 * k2, y4 - 0.238 * k2], [x4 + 0.455 * k2, y4 + 0.238 * k2]]).stream(pointStream);
    alaskaPoint = alaska.translate([x4 - 0.307 * k2, y4 + 0.201 * k2]).clipExtent([[x4 - 0.425 * k2 + epsilon6, y4 + 0.12 * k2 + epsilon6], [x4 - 0.214 * k2 - epsilon6, y4 + 0.234 * k2 - epsilon6]]).stream(pointStream);
    hawaiiPoint = hawaii.translate([x4 - 0.205 * k2, y4 + 0.212 * k2]).clipExtent([[x4 - 0.214 * k2 + epsilon6, y4 + 0.166 * k2 + epsilon6], [x4 - 0.115 * k2 - epsilon6, y4 + 0.234 * k2 - epsilon6]]).stream(pointStream);
    return reset();
  };
  albersUsa.fitExtent = function(extent2, object2) {
    return fitExtent(albersUsa, extent2, object2);
  };
  albersUsa.fitSize = function(size, object2) {
    return fitSize(albersUsa, size, object2);
  };
  albersUsa.fitWidth = function(width, object2) {
    return fitWidth(albersUsa, width, object2);
  };
  albersUsa.fitHeight = function(height, object2) {
    return fitHeight(albersUsa, height, object2);
  };
  function reset() {
    cache = cacheStream = null;
    return albersUsa;
  }
  return albersUsa.scale(1070);
}

// node_modules/d3-geo/src/projection/azimuthal.js
function azimuthalRaw(scale2) {
  return function(x4, y4) {
    var cx = cos2(x4), cy = cos2(y4), k2 = scale2(cx * cy);
    if (k2 === Infinity) return [2, 0];
    return [
      k2 * cy * sin2(x4),
      k2 * sin2(y4)
    ];
  };
}
function azimuthalInvert(angle2) {
  return function(x4, y4) {
    var z = sqrt(x4 * x4 + y4 * y4), c6 = angle2(z), sc = sin2(c6), cc2 = cos2(c6);
    return [
      atan2(x4 * sc, z * cc2),
      asin(z && y4 * sc / z)
    ];
  };
}

// node_modules/d3-geo/src/projection/azimuthalEqualArea.js
var azimuthalEqualAreaRaw = azimuthalRaw(function(cxcy) {
  return sqrt(2 / (1 + cxcy));
});
azimuthalEqualAreaRaw.invert = azimuthalInvert(function(z) {
  return 2 * asin(z / 2);
});
function azimuthalEqualArea_default() {
  return projection(azimuthalEqualAreaRaw).scale(124.75).clipAngle(180 - 1e-3);
}

// node_modules/d3-geo/src/projection/azimuthalEquidistant.js
var azimuthalEquidistantRaw = azimuthalRaw(function(c6) {
  return (c6 = acos(c6)) && c6 / sin2(c6);
});
azimuthalEquidistantRaw.invert = azimuthalInvert(function(z) {
  return z;
});
function azimuthalEquidistant_default() {
  return projection(azimuthalEquidistantRaw).scale(79.4188).clipAngle(180 - 1e-3);
}

// node_modules/d3-geo/src/projection/mercator.js
function mercatorRaw(lambda, phi2) {
  return [lambda, log(tan((halfPi2 + phi2) / 2))];
}
mercatorRaw.invert = function(x4, y4) {
  return [x4, 2 * atan(exp(y4)) - halfPi2];
};
function mercator_default() {
  return mercatorProjection(mercatorRaw).scale(961 / tau4);
}
function mercatorProjection(project) {
  var m3 = projection(project), center2 = m3.center, scale2 = m3.scale, translate = m3.translate, clipExtent = m3.clipExtent, x06 = null, y06, x12, y12;
  m3.scale = function(_) {
    return arguments.length ? (scale2(_), reclip()) : scale2();
  };
  m3.translate = function(_) {
    return arguments.length ? (translate(_), reclip()) : translate();
  };
  m3.center = function(_) {
    return arguments.length ? (center2(_), reclip()) : center2();
  };
  m3.clipExtent = function(_) {
    return arguments.length ? (_ == null ? x06 = y06 = x12 = y12 = null : (x06 = +_[0][0], y06 = +_[0][1], x12 = +_[1][0], y12 = +_[1][1]), reclip()) : x06 == null ? null : [[x06, y06], [x12, y12]];
  };
  function reclip() {
    var k2 = pi3 * scale2(), t = m3(rotation_default(m3.rotate()).invert([0, 0]));
    return clipExtent(x06 == null ? [[t[0] - k2, t[1] - k2], [t[0] + k2, t[1] + k2]] : project === mercatorRaw ? [[Math.max(t[0] - k2, x06), y06], [Math.min(t[0] + k2, x12), y12]] : [[x06, Math.max(t[1] - k2, y06)], [x12, Math.min(t[1] + k2, y12)]]);
  }
  return reclip();
}

// node_modules/d3-geo/src/projection/conicConformal.js
function tany(y4) {
  return tan((halfPi2 + y4) / 2);
}
function conicConformalRaw(y06, y12) {
  var cy0 = cos2(y06), n = y06 === y12 ? sin2(y06) : log(cy0 / cos2(y12)) / log(tany(y12) / tany(y06)), f = cy0 * pow2(tany(y06), n) / n;
  if (!n) return mercatorRaw;
  function project(x4, y4) {
    if (f > 0) {
      if (y4 < -halfPi2 + epsilon6) y4 = -halfPi2 + epsilon6;
    } else {
      if (y4 > halfPi2 - epsilon6) y4 = halfPi2 - epsilon6;
    }
    var r = f / pow2(tany(y4), n);
    return [r * sin2(n * x4), f - r * cos2(n * x4)];
  }
  project.invert = function(x4, y4) {
    var fy = f - y4, r = sign(n) * sqrt(x4 * x4 + fy * fy), l = atan2(x4, abs3(fy)) * sign(fy);
    if (fy * n < 0)
      l -= pi3 * sign(x4) * sign(fy);
    return [l / n, 2 * atan(pow2(f / r, 1 / n)) - halfPi2];
  };
  return project;
}
function conicConformal_default() {
  return conicProjection(conicConformalRaw).scale(109.5).parallels([30, 30]);
}

// node_modules/d3-geo/src/projection/equirectangular.js
function equirectangularRaw(lambda, phi2) {
  return [lambda, phi2];
}
equirectangularRaw.invert = equirectangularRaw;
function equirectangular_default() {
  return projection(equirectangularRaw).scale(152.63);
}

// node_modules/d3-geo/src/projection/conicEquidistant.js
function conicEquidistantRaw(y06, y12) {
  var cy0 = cos2(y06), n = y06 === y12 ? sin2(y06) : (cy0 - cos2(y12)) / (y12 - y06), g = cy0 / n + y06;
  if (abs3(n) < epsilon6) return equirectangularRaw;
  function project(x4, y4) {
    var gy = g - y4, nx = n * x4;
    return [gy * sin2(nx), g - gy * cos2(nx)];
  }
  project.invert = function(x4, y4) {
    var gy = g - y4, l = atan2(x4, abs3(gy)) * sign(gy);
    if (gy * n < 0)
      l -= pi3 * sign(x4) * sign(gy);
    return [l / n, g - sign(n) * sqrt(x4 * x4 + gy * gy)];
  };
  return project;
}
function conicEquidistant_default() {
  return conicProjection(conicEquidistantRaw).scale(131.154).center([0, 13.9389]);
}

// node_modules/d3-geo/src/projection/equalEarth.js
var A1 = 1.340264;
var A2 = -0.081106;
var A3 = 893e-6;
var A4 = 3796e-6;
var M = sqrt(3) / 2;
var iterations = 12;
function equalEarthRaw(lambda, phi2) {
  var l = asin(M * sin2(phi2)), l2 = l * l, l6 = l2 * l2 * l2;
  return [
    lambda * cos2(l) / (M * (A1 + 3 * A2 * l2 + l6 * (7 * A3 + 9 * A4 * l2))),
    l * (A1 + A2 * l2 + l6 * (A3 + A4 * l2))
  ];
}
equalEarthRaw.invert = function(x4, y4) {
  var l = y4, l2 = l * l, l6 = l2 * l2 * l2;
  for (var i = 0, delta, fy, fpy; i < iterations; ++i) {
    fy = l * (A1 + A2 * l2 + l6 * (A3 + A4 * l2)) - y4;
    fpy = A1 + 3 * A2 * l2 + l6 * (7 * A3 + 9 * A4 * l2);
    l -= delta = fy / fpy, l2 = l * l, l6 = l2 * l2 * l2;
    if (abs3(delta) < epsilon22) break;
  }
  return [
    M * x4 * (A1 + 3 * A2 * l2 + l6 * (7 * A3 + 9 * A4 * l2)) / cos2(l),
    asin(sin2(l) / M)
  ];
};
function equalEarth_default() {
  return projection(equalEarthRaw).scale(177.158);
}

// node_modules/d3-geo/src/projection/gnomonic.js
function gnomonicRaw(x4, y4) {
  var cy = cos2(y4), k2 = cos2(x4) * cy;
  return [cy * sin2(x4) / k2, sin2(y4) / k2];
}
gnomonicRaw.invert = azimuthalInvert(atan);
function gnomonic_default() {
  return projection(gnomonicRaw).scale(144.049).clipAngle(60);
}

// node_modules/d3-geo/src/projection/identity.js
function identity_default4() {
  var k2 = 1, tx = 0, ty = 0, sx = 1, sy = 1, alpha = 0, ca3, sa, x06 = null, y06, x12, y12, kx2 = 1, ky2 = 1, transform2 = transformer({
    point: function(x4, y4) {
      var p = projection2([x4, y4]);
      this.stream.point(p[0], p[1]);
    }
  }), postclip = identity_default3, cache, cacheStream;
  function reset() {
    kx2 = k2 * sx;
    ky2 = k2 * sy;
    cache = cacheStream = null;
    return projection2;
  }
  function projection2(p) {
    var x4 = p[0] * kx2, y4 = p[1] * ky2;
    if (alpha) {
      var t = y4 * ca3 - x4 * sa;
      x4 = x4 * ca3 + y4 * sa;
      y4 = t;
    }
    return [x4 + tx, y4 + ty];
  }
  projection2.invert = function(p) {
    var x4 = p[0] - tx, y4 = p[1] - ty;
    if (alpha) {
      var t = y4 * ca3 + x4 * sa;
      x4 = x4 * ca3 - y4 * sa;
      y4 = t;
    }
    return [x4 / kx2, y4 / ky2];
  };
  projection2.stream = function(stream) {
    return cache && cacheStream === stream ? cache : cache = transform2(postclip(cacheStream = stream));
  };
  projection2.postclip = function(_) {
    return arguments.length ? (postclip = _, x06 = y06 = x12 = y12 = null, reset()) : postclip;
  };
  projection2.clipExtent = function(_) {
    return arguments.length ? (postclip = _ == null ? (x06 = y06 = x12 = y12 = null, identity_default3) : clipRectangle(x06 = +_[0][0], y06 = +_[0][1], x12 = +_[1][0], y12 = +_[1][1]), reset()) : x06 == null ? null : [[x06, y06], [x12, y12]];
  };
  projection2.scale = function(_) {
    return arguments.length ? (k2 = +_, reset()) : k2;
  };
  projection2.translate = function(_) {
    return arguments.length ? (tx = +_[0], ty = +_[1], reset()) : [tx, ty];
  };
  projection2.angle = function(_) {
    return arguments.length ? (alpha = _ % 360 * radians, sa = sin2(alpha), ca3 = cos2(alpha), reset()) : alpha * degrees;
  };
  projection2.reflectX = function(_) {
    return arguments.length ? (sx = _ ? -1 : 1, reset()) : sx < 0;
  };
  projection2.reflectY = function(_) {
    return arguments.length ? (sy = _ ? -1 : 1, reset()) : sy < 0;
  };
  projection2.fitExtent = function(extent2, object2) {
    return fitExtent(projection2, extent2, object2);
  };
  projection2.fitSize = function(size, object2) {
    return fitSize(projection2, size, object2);
  };
  projection2.fitWidth = function(width, object2) {
    return fitWidth(projection2, width, object2);
  };
  projection2.fitHeight = function(height, object2) {
    return fitHeight(projection2, height, object2);
  };
  return projection2;
}

// node_modules/d3-geo/src/projection/naturalEarth1.js
function naturalEarth1Raw(lambda, phi2) {
  var phi22 = phi2 * phi2, phi4 = phi22 * phi22;
  return [
    lambda * (0.8707 - 0.131979 * phi22 + phi4 * (-0.013791 + phi4 * (3971e-6 * phi22 - 1529e-6 * phi4))),
    phi2 * (1.007226 + phi22 * (0.015085 + phi4 * (-0.044475 + 0.028874 * phi22 - 5916e-6 * phi4)))
  ];
}
naturalEarth1Raw.invert = function(x4, y4) {
  var phi2 = y4, i = 25, delta;
  do {
    var phi22 = phi2 * phi2, phi4 = phi22 * phi22;
    phi2 -= delta = (phi2 * (1.007226 + phi22 * (0.015085 + phi4 * (-0.044475 + 0.028874 * phi22 - 5916e-6 * phi4))) - y4) / (1.007226 + phi22 * (0.015085 * 3 + phi4 * (-0.044475 * 7 + 0.028874 * 9 * phi22 - 5916e-6 * 11 * phi4)));
  } while (abs3(delta) > epsilon6 && --i > 0);
  return [
    x4 / (0.8707 + (phi22 = phi2 * phi2) * (-0.131979 + phi22 * (-0.013791 + phi22 * phi22 * phi22 * (3971e-6 - 1529e-6 * phi22)))),
    phi2
  ];
};
function naturalEarth1_default() {
  return projection(naturalEarth1Raw).scale(175.295);
}

// node_modules/d3-geo/src/projection/orthographic.js
function orthographicRaw(x4, y4) {
  return [cos2(y4) * sin2(x4), sin2(y4)];
}
orthographicRaw.invert = azimuthalInvert(asin);
function orthographic_default() {
  return projection(orthographicRaw).scale(249.5).clipAngle(90 + epsilon6);
}

// node_modules/d3-geo/src/projection/stereographic.js
function stereographicRaw(x4, y4) {
  var cy = cos2(y4), k2 = 1 + cos2(x4) * cy;
  return [cy * sin2(x4) / k2, sin2(y4) / k2];
}
stereographicRaw.invert = azimuthalInvert(function(z) {
  return 2 * atan(z);
});
function stereographic_default() {
  return projection(stereographicRaw).scale(250).clipAngle(142);
}

// node_modules/d3-geo/src/projection/transverseMercator.js
function transverseMercatorRaw(lambda, phi2) {
  return [log(tan((halfPi2 + phi2) / 2)), -lambda];
}
transverseMercatorRaw.invert = function(x4, y4) {
  return [-y4, 2 * atan(exp(x4)) - halfPi2];
};
function transverseMercator_default() {
  var m3 = mercatorProjection(transverseMercatorRaw), center2 = m3.center, rotate = m3.rotate;
  m3.center = function(_) {
    return arguments.length ? center2([-_[1], _[0]]) : (_ = center2(), [_[1], -_[0]]);
  };
  m3.rotate = function(_) {
    return arguments.length ? rotate([_[0], _[1], _.length > 2 ? _[2] + 90 : 90]) : (_ = rotate(), [_[0], _[1], _[2] - 90]);
  };
  return rotate([0, 0, 90]).scale(159.155);
}

// node_modules/d3-hierarchy/src/cluster.js
function defaultSeparation(a4, b) {
  return a4.parent === b.parent ? 1 : 2;
}
function meanX(children) {
  return children.reduce(meanXReduce, 0) / children.length;
}
function meanXReduce(x4, c6) {
  return x4 + c6.x;
}
function maxY(children) {
  return 1 + children.reduce(maxYReduce, 0);
}
function maxYReduce(y4, c6) {
  return Math.max(y4, c6.y);
}
function leafLeft(node) {
  var children;
  while (children = node.children) node = children[0];
  return node;
}
function leafRight(node) {
  var children;
  while (children = node.children) node = children[children.length - 1];
  return node;
}
function cluster_default() {
  var separation = defaultSeparation, dx = 1, dy = 1, nodeSize = false;
  function cluster(root) {
    var previousNode, x4 = 0;
    root.eachAfter(function(node) {
      var children = node.children;
      if (children) {
        node.x = meanX(children);
        node.y = maxY(children);
      } else {
        node.x = previousNode ? x4 += separation(node, previousNode) : 0;
        node.y = 0;
        previousNode = node;
      }
    });
    var left2 = leafLeft(root), right2 = leafRight(root), x06 = left2.x - separation(left2, right2) / 2, x12 = right2.x + separation(right2, left2) / 2;
    return root.eachAfter(nodeSize ? function(node) {
      node.x = (node.x - root.x) * dx;
      node.y = (root.y - node.y) * dy;
    } : function(node) {
      node.x = (node.x - x06) / (x12 - x06) * dx;
      node.y = (1 - (root.y ? node.y / root.y : 1)) * dy;
    });
  }
  cluster.separation = function(x4) {
    return arguments.length ? (separation = x4, cluster) : separation;
  };
  cluster.size = function(x4) {
    return arguments.length ? (nodeSize = false, dx = +x4[0], dy = +x4[1], cluster) : nodeSize ? null : [dx, dy];
  };
  cluster.nodeSize = function(x4) {
    return arguments.length ? (nodeSize = true, dx = +x4[0], dy = +x4[1], cluster) : nodeSize ? [dx, dy] : null;
  };
  return cluster;
}

// node_modules/d3-hierarchy/src/hierarchy/count.js
function count2(node) {
  var sum4 = 0, children = node.children, i = children && children.length;
  if (!i) sum4 = 1;
  else while (--i >= 0) sum4 += children[i].value;
  node.value = sum4;
}
function count_default() {
  return this.eachAfter(count2);
}

// node_modules/d3-hierarchy/src/hierarchy/each.js
function each_default(callback, that) {
  let index3 = -1;
  for (const node of this) {
    callback.call(that, node, ++index3, this);
  }
  return this;
}

// node_modules/d3-hierarchy/src/hierarchy/eachBefore.js
function eachBefore_default(callback, that) {
  var node = this, nodes = [node], children, i, index3 = -1;
  while (node = nodes.pop()) {
    callback.call(that, node, ++index3, this);
    if (children = node.children) {
      for (i = children.length - 1; i >= 0; --i) {
        nodes.push(children[i]);
      }
    }
  }
  return this;
}

// node_modules/d3-hierarchy/src/hierarchy/eachAfter.js
function eachAfter_default(callback, that) {
  var node = this, nodes = [node], next = [], children, i, n, index3 = -1;
  while (node = nodes.pop()) {
    next.push(node);
    if (children = node.children) {
      for (i = 0, n = children.length; i < n; ++i) {
        nodes.push(children[i]);
      }
    }
  }
  while (node = next.pop()) {
    callback.call(that, node, ++index3, this);
  }
  return this;
}

// node_modules/d3-hierarchy/src/hierarchy/find.js
function find_default2(callback, that) {
  let index3 = -1;
  for (const node of this) {
    if (callback.call(that, node, ++index3, this)) {
      return node;
    }
  }
}

// node_modules/d3-hierarchy/src/hierarchy/sum.js
function sum_default(value) {
  return this.eachAfter(function(node) {
    var sum4 = +value(node.data) || 0, children = node.children, i = children && children.length;
    while (--i >= 0) sum4 += children[i].value;
    node.value = sum4;
  });
}

// node_modules/d3-hierarchy/src/hierarchy/sort.js
function sort_default(compare) {
  return this.eachBefore(function(node) {
    if (node.children) {
      node.children.sort(compare);
    }
  });
}

// node_modules/d3-hierarchy/src/hierarchy/path.js
function path_default2(end) {
  var start = this, ancestor = leastCommonAncestor(start, end), nodes = [start];
  while (start !== ancestor) {
    start = start.parent;
    nodes.push(start);
  }
  var k2 = nodes.length;
  while (end !== ancestor) {
    nodes.splice(k2, 0, end);
    end = end.parent;
  }
  return nodes;
}
function leastCommonAncestor(a4, b) {
  if (a4 === b) return a4;
  var aNodes = a4.ancestors(), bNodes = b.ancestors(), c6 = null;
  a4 = aNodes.pop();
  b = bNodes.pop();
  while (a4 === b) {
    c6 = a4;
    a4 = aNodes.pop();
    b = bNodes.pop();
  }
  return c6;
}

// node_modules/d3-hierarchy/src/hierarchy/ancestors.js
function ancestors_default() {
  var node = this, nodes = [node];
  while (node = node.parent) {
    nodes.push(node);
  }
  return nodes;
}

// node_modules/d3-hierarchy/src/hierarchy/descendants.js
function descendants_default() {
  return Array.from(this);
}

// node_modules/d3-hierarchy/src/hierarchy/leaves.js
function leaves_default() {
  var leaves = [];
  this.eachBefore(function(node) {
    if (!node.children) {
      leaves.push(node);
    }
  });
  return leaves;
}

// node_modules/d3-hierarchy/src/hierarchy/links.js
function links_default() {
  var root = this, links = [];
  root.each(function(node) {
    if (node !== root) {
      links.push({ source: node.parent, target: node });
    }
  });
  return links;
}

// node_modules/d3-hierarchy/src/hierarchy/iterator.js
function* iterator_default() {
  var node = this, current, next = [node], children, i, n;
  do {
    current = next.reverse(), next = [];
    while (node = current.pop()) {
      yield node;
      if (children = node.children) {
        for (i = 0, n = children.length; i < n; ++i) {
          next.push(children[i]);
        }
      }
    }
  } while (next.length);
}

// node_modules/d3-hierarchy/src/hierarchy/index.js
function hierarchy(data, children) {
  if (data instanceof Map) {
    data = [void 0, data];
    if (children === void 0) children = mapChildren;
  } else if (children === void 0) {
    children = objectChildren;
  }
  var root = new Node(data), node, nodes = [root], child, childs, i, n;
  while (node = nodes.pop()) {
    if ((childs = children(node.data)) && (n = (childs = Array.from(childs)).length)) {
      node.children = childs;
      for (i = n - 1; i >= 0; --i) {
        nodes.push(child = childs[i] = new Node(childs[i]));
        child.parent = node;
        child.depth = node.depth + 1;
      }
    }
  }
  return root.eachBefore(computeHeight);
}
function node_copy() {
  return hierarchy(this).eachBefore(copyData);
}
function objectChildren(d) {
  return d.children;
}
function mapChildren(d) {
  return Array.isArray(d) ? d[1] : null;
}
function copyData(node) {
  if (node.data.value !== void 0) node.value = node.data.value;
  node.data = node.data.data;
}
function computeHeight(node) {
  var height = 0;
  do
    node.height = height;
  while ((node = node.parent) && node.height < ++height);
}
function Node(data) {
  this.data = data;
  this.depth = this.height = 0;
  this.parent = null;
}
Node.prototype = hierarchy.prototype = {
  constructor: Node,
  count: count_default,
  each: each_default,
  eachAfter: eachAfter_default,
  eachBefore: eachBefore_default,
  find: find_default2,
  sum: sum_default,
  sort: sort_default,
  path: path_default2,
  ancestors: ancestors_default,
  descendants: descendants_default,
  leaves: leaves_default,
  links: links_default,
  copy: node_copy,
  [Symbol.iterator]: iterator_default
};

// node_modules/d3-hierarchy/src/accessors.js
function optional(f) {
  return f == null ? null : required(f);
}
function required(f) {
  if (typeof f !== "function") throw new Error();
  return f;
}

// node_modules/d3-hierarchy/src/constant.js
function constantZero() {
  return 0;
}
function constant_default6(x4) {
  return function() {
    return x4;
  };
}

// node_modules/d3-hierarchy/src/lcg.js
var a2 = 1664525;
var c2 = 1013904223;
var m2 = 4294967296;
function lcg_default2() {
  let s2 = 1;
  return () => (s2 = (a2 * s2 + c2) % m2) / m2;
}

// node_modules/d3-hierarchy/src/array.js
function array_default2(x4) {
  return typeof x4 === "object" && "length" in x4 ? x4 : Array.from(x4);
}
function shuffle(array3, random) {
  let m3 = array3.length, t, i;
  while (m3) {
    i = random() * m3-- | 0;
    t = array3[m3];
    array3[m3] = array3[i];
    array3[i] = t;
  }
  return array3;
}

// node_modules/d3-hierarchy/src/pack/enclose.js
function enclose_default(circles) {
  return packEncloseRandom(circles, lcg_default2());
}
function packEncloseRandom(circles, random) {
  var i = 0, n = (circles = shuffle(Array.from(circles), random)).length, B2 = [], p, e;
  while (i < n) {
    p = circles[i];
    if (e && enclosesWeak(e, p)) ++i;
    else e = encloseBasis(B2 = extendBasis(B2, p)), i = 0;
  }
  return e;
}
function extendBasis(B2, p) {
  var i, j;
  if (enclosesWeakAll(p, B2)) return [p];
  for (i = 0; i < B2.length; ++i) {
    if (enclosesNot(p, B2[i]) && enclosesWeakAll(encloseBasis2(B2[i], p), B2)) {
      return [B2[i], p];
    }
  }
  for (i = 0; i < B2.length - 1; ++i) {
    for (j = i + 1; j < B2.length; ++j) {
      if (enclosesNot(encloseBasis2(B2[i], B2[j]), p) && enclosesNot(encloseBasis2(B2[i], p), B2[j]) && enclosesNot(encloseBasis2(B2[j], p), B2[i]) && enclosesWeakAll(encloseBasis3(B2[i], B2[j], p), B2)) {
        return [B2[i], B2[j], p];
      }
    }
  }
  throw new Error();
}
function enclosesNot(a4, b) {
  var dr = a4.r - b.r, dx = b.x - a4.x, dy = b.y - a4.y;
  return dr < 0 || dr * dr < dx * dx + dy * dy;
}
function enclosesWeak(a4, b) {
  var dr = a4.r - b.r + Math.max(a4.r, b.r, 1) * 1e-9, dx = b.x - a4.x, dy = b.y - a4.y;
  return dr > 0 && dr * dr > dx * dx + dy * dy;
}
function enclosesWeakAll(a4, B2) {
  for (var i = 0; i < B2.length; ++i) {
    if (!enclosesWeak(a4, B2[i])) {
      return false;
    }
  }
  return true;
}
function encloseBasis(B2) {
  switch (B2.length) {
    case 1:
      return encloseBasis1(B2[0]);
    case 2:
      return encloseBasis2(B2[0], B2[1]);
    case 3:
      return encloseBasis3(B2[0], B2[1], B2[2]);
  }
}
function encloseBasis1(a4) {
  return {
    x: a4.x,
    y: a4.y,
    r: a4.r
  };
}
function encloseBasis2(a4, b) {
  var x12 = a4.x, y12 = a4.y, r1 = a4.r, x22 = b.x, y22 = b.y, r2 = b.r, x21 = x22 - x12, y21 = y22 - y12, r21 = r2 - r1, l = Math.sqrt(x21 * x21 + y21 * y21);
  return {
    x: (x12 + x22 + x21 / l * r21) / 2,
    y: (y12 + y22 + y21 / l * r21) / 2,
    r: (l + r1 + r2) / 2
  };
}
function encloseBasis3(a4, b, c6) {
  var x12 = a4.x, y12 = a4.y, r1 = a4.r, x22 = b.x, y22 = b.y, r2 = b.r, x32 = c6.x, y32 = c6.y, r3 = c6.r, a22 = x12 - x22, a32 = x12 - x32, b2 = y12 - y22, b3 = y12 - y32, c22 = r2 - r1, c32 = r3 - r1, d1 = x12 * x12 + y12 * y12 - r1 * r1, d2 = d1 - x22 * x22 - y22 * y22 + r2 * r2, d3 = d1 - x32 * x32 - y32 * y32 + r3 * r3, ab4 = a32 * b2 - a22 * b3, xa = (b2 * d3 - b3 * d2) / (ab4 * 2) - x12, xb = (b3 * c22 - b2 * c32) / ab4, ya = (a32 * d2 - a22 * d3) / (ab4 * 2) - y12, yb = (a22 * c32 - a32 * c22) / ab4, A = xb * xb + yb * yb - 1, B2 = 2 * (r1 + xa * xb + ya * yb), C = xa * xa + ya * ya - r1 * r1, r = -(Math.abs(A) > 1e-6 ? (B2 + Math.sqrt(B2 * B2 - 4 * A * C)) / (2 * A) : C / B2);
  return {
    x: x12 + xa + xb * r,
    y: y12 + ya + yb * r,
    r
  };
}

// node_modules/d3-hierarchy/src/pack/siblings.js
function place(b, a4, c6) {
  var dx = b.x - a4.x, x4, a22, dy = b.y - a4.y, y4, b2, d2 = dx * dx + dy * dy;
  if (d2) {
    a22 = a4.r + c6.r, a22 *= a22;
    b2 = b.r + c6.r, b2 *= b2;
    if (a22 > b2) {
      x4 = (d2 + b2 - a22) / (2 * d2);
      y4 = Math.sqrt(Math.max(0, b2 / d2 - x4 * x4));
      c6.x = b.x - x4 * dx - y4 * dy;
      c6.y = b.y - x4 * dy + y4 * dx;
    } else {
      x4 = (d2 + a22 - b2) / (2 * d2);
      y4 = Math.sqrt(Math.max(0, a22 / d2 - x4 * x4));
      c6.x = a4.x + x4 * dx - y4 * dy;
      c6.y = a4.y + x4 * dy + y4 * dx;
    }
  } else {
    c6.x = a4.x + c6.r;
    c6.y = a4.y;
  }
}
function intersects(a4, b) {
  var dr = a4.r + b.r - 1e-6, dx = b.x - a4.x, dy = b.y - a4.y;
  return dr > 0 && dr * dr > dx * dx + dy * dy;
}
function score(node) {
  var a4 = node._, b = node.next._, ab4 = a4.r + b.r, dx = (a4.x * b.r + b.x * a4.r) / ab4, dy = (a4.y * b.r + b.y * a4.r) / ab4;
  return dx * dx + dy * dy;
}
function Node2(circle) {
  this._ = circle;
  this.next = null;
  this.previous = null;
}
function packSiblingsRandom(circles, random) {
  if (!(n = (circles = array_default2(circles)).length)) return 0;
  var a4, b, c6, n, aa2, ca3, i, j, k2, sj, sk;
  a4 = circles[0], a4.x = 0, a4.y = 0;
  if (!(n > 1)) return a4.r;
  b = circles[1], a4.x = -b.r, b.x = a4.r, b.y = 0;
  if (!(n > 2)) return a4.r + b.r;
  place(b, a4, c6 = circles[2]);
  a4 = new Node2(a4), b = new Node2(b), c6 = new Node2(c6);
  a4.next = c6.previous = b;
  b.next = a4.previous = c6;
  c6.next = b.previous = a4;
  pack: for (i = 3; i < n; ++i) {
    place(a4._, b._, c6 = circles[i]), c6 = new Node2(c6);
    j = b.next, k2 = a4.previous, sj = b._.r, sk = a4._.r;
    do {
      if (sj <= sk) {
        if (intersects(j._, c6._)) {
          b = j, a4.next = b, b.previous = a4, --i;
          continue pack;
        }
        sj += j._.r, j = j.next;
      } else {
        if (intersects(k2._, c6._)) {
          a4 = k2, a4.next = b, b.previous = a4, --i;
          continue pack;
        }
        sk += k2._.r, k2 = k2.previous;
      }
    } while (j !== k2.next);
    c6.previous = a4, c6.next = b, a4.next = b.previous = b = c6;
    aa2 = score(a4);
    while ((c6 = c6.next) !== b) {
      if ((ca3 = score(c6)) < aa2) {
        a4 = c6, aa2 = ca3;
      }
    }
    b = a4.next;
  }
  a4 = [b._], c6 = b;
  while ((c6 = c6.next) !== b) a4.push(c6._);
  c6 = packEncloseRandom(a4, random);
  for (i = 0; i < n; ++i) a4 = circles[i], a4.x -= c6.x, a4.y -= c6.y;
  return c6.r;
}
function siblings_default(circles) {
  packSiblingsRandom(circles, lcg_default2());
  return circles;
}

// node_modules/d3-hierarchy/src/pack/index.js
function defaultRadius2(d) {
  return Math.sqrt(d.value);
}
function pack_default() {
  var radius = null, dx = 1, dy = 1, padding = constantZero;
  function pack(root) {
    const random = lcg_default2();
    root.x = dx / 2, root.y = dy / 2;
    if (radius) {
      root.eachBefore(radiusLeaf(radius)).eachAfter(packChildrenRandom(padding, 0.5, random)).eachBefore(translateChild(1));
    } else {
      root.eachBefore(radiusLeaf(defaultRadius2)).eachAfter(packChildrenRandom(constantZero, 1, random)).eachAfter(packChildrenRandom(padding, root.r / Math.min(dx, dy), random)).eachBefore(translateChild(Math.min(dx, dy) / (2 * root.r)));
    }
    return root;
  }
  pack.radius = function(x4) {
    return arguments.length ? (radius = optional(x4), pack) : radius;
  };
  pack.size = function(x4) {
    return arguments.length ? (dx = +x4[0], dy = +x4[1], pack) : [dx, dy];
  };
  pack.padding = function(x4) {
    return arguments.length ? (padding = typeof x4 === "function" ? x4 : constant_default6(+x4), pack) : padding;
  };
  return pack;
}
function radiusLeaf(radius) {
  return function(node) {
    if (!node.children) {
      node.r = Math.max(0, +radius(node) || 0);
    }
  };
}
function packChildrenRandom(padding, k2, random) {
  return function(node) {
    if (children = node.children) {
      var children, i, n = children.length, r = padding(node) * k2 || 0, e;
      if (r) for (i = 0; i < n; ++i) children[i].r += r;
      e = packSiblingsRandom(children, random);
      if (r) for (i = 0; i < n; ++i) children[i].r -= r;
      node.r = e + r;
    }
  };
}
function translateChild(k2) {
  return function(node) {
    var parent = node.parent;
    node.r *= k2;
    if (parent) {
      node.x = parent.x + k2 * node.x;
      node.y = parent.y + k2 * node.y;
    }
  };
}

// node_modules/d3-hierarchy/src/treemap/round.js
function round_default2(node) {
  node.x0 = Math.round(node.x0);
  node.y0 = Math.round(node.y0);
  node.x1 = Math.round(node.x1);
  node.y1 = Math.round(node.y1);
}

// node_modules/d3-hierarchy/src/treemap/dice.js
function dice_default(parent, x06, y06, x12, y12) {
  var nodes = parent.children, node, i = -1, n = nodes.length, k2 = parent.value && (x12 - x06) / parent.value;
  while (++i < n) {
    node = nodes[i], node.y0 = y06, node.y1 = y12;
    node.x0 = x06, node.x1 = x06 += node.value * k2;
  }
}

// node_modules/d3-hierarchy/src/partition.js
function partition_default() {
  var dx = 1, dy = 1, padding = 0, round = false;
  function partition(root) {
    var n = root.height + 1;
    root.x0 = root.y0 = padding;
    root.x1 = dx;
    root.y1 = dy / n;
    root.eachBefore(positionNode(dy, n));
    if (round) root.eachBefore(round_default2);
    return root;
  }
  function positionNode(dy2, n) {
    return function(node) {
      if (node.children) {
        dice_default(node, node.x0, dy2 * (node.depth + 1) / n, node.x1, dy2 * (node.depth + 2) / n);
      }
      var x06 = node.x0, y06 = node.y0, x12 = node.x1 - padding, y12 = node.y1 - padding;
      if (x12 < x06) x06 = x12 = (x06 + x12) / 2;
      if (y12 < y06) y06 = y12 = (y06 + y12) / 2;
      node.x0 = x06;
      node.y0 = y06;
      node.x1 = x12;
      node.y1 = y12;
    };
  }
  partition.round = function(x4) {
    return arguments.length ? (round = !!x4, partition) : round;
  };
  partition.size = function(x4) {
    return arguments.length ? (dx = +x4[0], dy = +x4[1], partition) : [dx, dy];
  };
  partition.padding = function(x4) {
    return arguments.length ? (padding = +x4, partition) : padding;
  };
  return partition;
}

// node_modules/d3-hierarchy/src/stratify.js
var preroot = { depth: -1 };
var ambiguous = {};
var imputed = {};
function defaultId(d) {
  return d.id;
}
function defaultParentId(d) {
  return d.parentId;
}
function stratify_default() {
  var id = defaultId, parentId = defaultParentId, path2;
  function stratify(data) {
    var nodes = Array.from(data), currentId = id, currentParentId = parentId, n, d, i, root, parent, node, nodeId, nodeKey, nodeByKey = /* @__PURE__ */ new Map();
    if (path2 != null) {
      const I = nodes.map((d2, i2) => normalize(path2(d2, i2, data)));
      const P = I.map(parentof);
      const S = new Set(I).add("");
      for (const i2 of P) {
        if (!S.has(i2)) {
          S.add(i2);
          I.push(i2);
          P.push(parentof(i2));
          nodes.push(imputed);
        }
      }
      currentId = (_, i2) => I[i2];
      currentParentId = (_, i2) => P[i2];
    }
    for (i = 0, n = nodes.length; i < n; ++i) {
      d = nodes[i], node = nodes[i] = new Node(d);
      if ((nodeId = currentId(d, i, data)) != null && (nodeId += "")) {
        nodeKey = node.id = nodeId;
        nodeByKey.set(nodeKey, nodeByKey.has(nodeKey) ? ambiguous : node);
      }
      if ((nodeId = currentParentId(d, i, data)) != null && (nodeId += "")) {
        node.parent = nodeId;
      }
    }
    for (i = 0; i < n; ++i) {
      node = nodes[i];
      if (nodeId = node.parent) {
        parent = nodeByKey.get(nodeId);
        if (!parent) throw new Error("missing: " + nodeId);
        if (parent === ambiguous) throw new Error("ambiguous: " + nodeId);
        if (parent.children) parent.children.push(node);
        else parent.children = [node];
        node.parent = parent;
      } else {
        if (root) throw new Error("multiple roots");
        root = node;
      }
    }
    if (!root) throw new Error("no root");
    if (path2 != null) {
      while (root.data === imputed && root.children.length === 1) {
        root = root.children[0], --n;
      }
      for (let i2 = nodes.length - 1; i2 >= 0; --i2) {
        node = nodes[i2];
        if (node.data !== imputed) break;
        node.data = null;
      }
    }
    root.parent = preroot;
    root.eachBefore(function(node2) {
      node2.depth = node2.parent.depth + 1;
      --n;
    }).eachBefore(computeHeight);
    root.parent = null;
    if (n > 0) throw new Error("cycle");
    return root;
  }
  stratify.id = function(x4) {
    return arguments.length ? (id = optional(x4), stratify) : id;
  };
  stratify.parentId = function(x4) {
    return arguments.length ? (parentId = optional(x4), stratify) : parentId;
  };
  stratify.path = function(x4) {
    return arguments.length ? (path2 = optional(x4), stratify) : path2;
  };
  return stratify;
}
function normalize(path2) {
  path2 = `${path2}`;
  let i = path2.length;
  if (slash(path2, i - 1) && !slash(path2, i - 2)) path2 = path2.slice(0, -1);
  return path2[0] === "/" ? path2 : `/${path2}`;
}
function parentof(path2) {
  let i = path2.length;
  if (i < 2) return "";
  while (--i > 1) if (slash(path2, i)) break;
  return path2.slice(0, i);
}
function slash(path2, i) {
  if (path2[i] === "/") {
    let k2 = 0;
    while (i > 0 && path2[--i] === "\\") ++k2;
    if ((k2 & 1) === 0) return true;
  }
  return false;
}

// node_modules/d3-hierarchy/src/tree.js
function defaultSeparation2(a4, b) {
  return a4.parent === b.parent ? 1 : 2;
}
function nextLeft(v2) {
  var children = v2.children;
  return children ? children[0] : v2.t;
}
function nextRight(v2) {
  var children = v2.children;
  return children ? children[children.length - 1] : v2.t;
}
function moveSubtree(wm, wp, shift) {
  var change = shift / (wp.i - wm.i);
  wp.c -= change;
  wp.s += shift;
  wm.c += change;
  wp.z += shift;
  wp.m += shift;
}
function executeShifts(v2) {
  var shift = 0, change = 0, children = v2.children, i = children.length, w;
  while (--i >= 0) {
    w = children[i];
    w.z += shift;
    w.m += shift;
    shift += w.s + (change += w.c);
  }
}
function nextAncestor(vim, v2, ancestor) {
  return vim.a.parent === v2.parent ? vim.a : ancestor;
}
function TreeNode(node, i) {
  this._ = node;
  this.parent = null;
  this.children = null;
  this.A = null;
  this.a = this;
  this.z = 0;
  this.m = 0;
  this.c = 0;
  this.s = 0;
  this.t = null;
  this.i = i;
}
TreeNode.prototype = Object.create(Node.prototype);
function treeRoot(root) {
  var tree = new TreeNode(root, 0), node, nodes = [tree], child, children, i, n;
  while (node = nodes.pop()) {
    if (children = node._.children) {
      node.children = new Array(n = children.length);
      for (i = n - 1; i >= 0; --i) {
        nodes.push(child = node.children[i] = new TreeNode(children[i], i));
        child.parent = node;
      }
    }
  }
  (tree.parent = new TreeNode(null, 0)).children = [tree];
  return tree;
}
function tree_default() {
  var separation = defaultSeparation2, dx = 1, dy = 1, nodeSize = null;
  function tree(root) {
    var t = treeRoot(root);
    t.eachAfter(firstWalk), t.parent.m = -t.z;
    t.eachBefore(secondWalk);
    if (nodeSize) root.eachBefore(sizeNode);
    else {
      var left2 = root, right2 = root, bottom2 = root;
      root.eachBefore(function(node) {
        if (node.x < left2.x) left2 = node;
        if (node.x > right2.x) right2 = node;
        if (node.depth > bottom2.depth) bottom2 = node;
      });
      var s2 = left2 === right2 ? 1 : separation(left2, right2) / 2, tx = s2 - left2.x, kx2 = dx / (right2.x + s2 + tx), ky2 = dy / (bottom2.depth || 1);
      root.eachBefore(function(node) {
        node.x = (node.x + tx) * kx2;
        node.y = node.depth * ky2;
      });
    }
    return root;
  }
  function firstWalk(v2) {
    var children = v2.children, siblings = v2.parent.children, w = v2.i ? siblings[v2.i - 1] : null;
    if (children) {
      executeShifts(v2);
      var midpoint = (children[0].z + children[children.length - 1].z) / 2;
      if (w) {
        v2.z = w.z + separation(v2._, w._);
        v2.m = v2.z - midpoint;
      } else {
        v2.z = midpoint;
      }
    } else if (w) {
      v2.z = w.z + separation(v2._, w._);
    }
    v2.parent.A = apportion(v2, w, v2.parent.A || siblings[0]);
  }
  function secondWalk(v2) {
    v2._.x = v2.z + v2.parent.m;
    v2.m += v2.parent.m;
  }
  function apportion(v2, w, ancestor) {
    if (w) {
      var vip = v2, vop = v2, vim = w, vom = vip.parent.children[0], sip = vip.m, sop = vop.m, sim = vim.m, som = vom.m, shift;
      while (vim = nextRight(vim), vip = nextLeft(vip), vim && vip) {
        vom = nextLeft(vom);
        vop = nextRight(vop);
        vop.a = v2;
        shift = vim.z + sim - vip.z - sip + separation(vim._, vip._);
        if (shift > 0) {
          moveSubtree(nextAncestor(vim, v2, ancestor), v2, shift);
          sip += shift;
          sop += shift;
        }
        sim += vim.m;
        sip += vip.m;
        som += vom.m;
        sop += vop.m;
      }
      if (vim && !nextRight(vop)) {
        vop.t = vim;
        vop.m += sim - sop;
      }
      if (vip && !nextLeft(vom)) {
        vom.t = vip;
        vom.m += sip - som;
        ancestor = v2;
      }
    }
    return ancestor;
  }
  function sizeNode(node) {
    node.x *= dx;
    node.y = node.depth * dy;
  }
  tree.separation = function(x4) {
    return arguments.length ? (separation = x4, tree) : separation;
  };
  tree.size = function(x4) {
    return arguments.length ? (nodeSize = false, dx = +x4[0], dy = +x4[1], tree) : nodeSize ? null : [dx, dy];
  };
  tree.nodeSize = function(x4) {
    return arguments.length ? (nodeSize = true, dx = +x4[0], dy = +x4[1], tree) : nodeSize ? [dx, dy] : null;
  };
  return tree;
}

// node_modules/d3-hierarchy/src/treemap/slice.js
function slice_default(parent, x06, y06, x12, y12) {
  var nodes = parent.children, node, i = -1, n = nodes.length, k2 = parent.value && (y12 - y06) / parent.value;
  while (++i < n) {
    node = nodes[i], node.x0 = x06, node.x1 = x12;
    node.y0 = y06, node.y1 = y06 += node.value * k2;
  }
}

// node_modules/d3-hierarchy/src/treemap/squarify.js
var phi = (1 + Math.sqrt(5)) / 2;
function squarifyRatio(ratio, parent, x06, y06, x12, y12) {
  var rows = [], nodes = parent.children, row, nodeValue, i0 = 0, i1 = 0, n = nodes.length, dx, dy, value = parent.value, sumValue, minValue, maxValue, newRatio, minRatio, alpha, beta;
  while (i0 < n) {
    dx = x12 - x06, dy = y12 - y06;
    do
      sumValue = nodes[i1++].value;
    while (!sumValue && i1 < n);
    minValue = maxValue = sumValue;
    alpha = Math.max(dy / dx, dx / dy) / (value * ratio);
    beta = sumValue * sumValue * alpha;
    minRatio = Math.max(maxValue / beta, beta / minValue);
    for (; i1 < n; ++i1) {
      sumValue += nodeValue = nodes[i1].value;
      if (nodeValue < minValue) minValue = nodeValue;
      if (nodeValue > maxValue) maxValue = nodeValue;
      beta = sumValue * sumValue * alpha;
      newRatio = Math.max(maxValue / beta, beta / minValue);
      if (newRatio > minRatio) {
        sumValue -= nodeValue;
        break;
      }
      minRatio = newRatio;
    }
    rows.push(row = { value: sumValue, dice: dx < dy, children: nodes.slice(i0, i1) });
    if (row.dice) dice_default(row, x06, y06, x12, value ? y06 += dy * sumValue / value : y12);
    else slice_default(row, x06, y06, value ? x06 += dx * sumValue / value : x12, y12);
    value -= sumValue, i0 = i1;
  }
  return rows;
}
var squarify_default = (function custom(ratio) {
  function squarify(parent, x06, y06, x12, y12) {
    squarifyRatio(ratio, parent, x06, y06, x12, y12);
  }
  squarify.ratio = function(x4) {
    return custom((x4 = +x4) > 1 ? x4 : 1);
  };
  return squarify;
})(phi);

// node_modules/d3-hierarchy/src/treemap/index.js
function treemap_default() {
  var tile = squarify_default, round = false, dx = 1, dy = 1, paddingStack = [0], paddingInner = constantZero, paddingTop = constantZero, paddingRight = constantZero, paddingBottom = constantZero, paddingLeft = constantZero;
  function treemap(root) {
    root.x0 = root.y0 = 0;
    root.x1 = dx;
    root.y1 = dy;
    root.eachBefore(positionNode);
    paddingStack = [0];
    if (round) root.eachBefore(round_default2);
    return root;
  }
  function positionNode(node) {
    var p = paddingStack[node.depth], x06 = node.x0 + p, y06 = node.y0 + p, x12 = node.x1 - p, y12 = node.y1 - p;
    if (x12 < x06) x06 = x12 = (x06 + x12) / 2;
    if (y12 < y06) y06 = y12 = (y06 + y12) / 2;
    node.x0 = x06;
    node.y0 = y06;
    node.x1 = x12;
    node.y1 = y12;
    if (node.children) {
      p = paddingStack[node.depth + 1] = paddingInner(node) / 2;
      x06 += paddingLeft(node) - p;
      y06 += paddingTop(node) - p;
      x12 -= paddingRight(node) - p;
      y12 -= paddingBottom(node) - p;
      if (x12 < x06) x06 = x12 = (x06 + x12) / 2;
      if (y12 < y06) y06 = y12 = (y06 + y12) / 2;
      tile(node, x06, y06, x12, y12);
    }
  }
  treemap.round = function(x4) {
    return arguments.length ? (round = !!x4, treemap) : round;
  };
  treemap.size = function(x4) {
    return arguments.length ? (dx = +x4[0], dy = +x4[1], treemap) : [dx, dy];
  };
  treemap.tile = function(x4) {
    return arguments.length ? (tile = required(x4), treemap) : tile;
  };
  treemap.padding = function(x4) {
    return arguments.length ? treemap.paddingInner(x4).paddingOuter(x4) : treemap.paddingInner();
  };
  treemap.paddingInner = function(x4) {
    return arguments.length ? (paddingInner = typeof x4 === "function" ? x4 : constant_default6(+x4), treemap) : paddingInner;
  };
  treemap.paddingOuter = function(x4) {
    return arguments.length ? treemap.paddingTop(x4).paddingRight(x4).paddingBottom(x4).paddingLeft(x4) : treemap.paddingTop();
  };
  treemap.paddingTop = function(x4) {
    return arguments.length ? (paddingTop = typeof x4 === "function" ? x4 : constant_default6(+x4), treemap) : paddingTop;
  };
  treemap.paddingRight = function(x4) {
    return arguments.length ? (paddingRight = typeof x4 === "function" ? x4 : constant_default6(+x4), treemap) : paddingRight;
  };
  treemap.paddingBottom = function(x4) {
    return arguments.length ? (paddingBottom = typeof x4 === "function" ? x4 : constant_default6(+x4), treemap) : paddingBottom;
  };
  treemap.paddingLeft = function(x4) {
    return arguments.length ? (paddingLeft = typeof x4 === "function" ? x4 : constant_default6(+x4), treemap) : paddingLeft;
  };
  return treemap;
}

// node_modules/d3-hierarchy/src/treemap/binary.js
function binary_default(parent, x06, y06, x12, y12) {
  var nodes = parent.children, i, n = nodes.length, sum4, sums = new Array(n + 1);
  for (sums[0] = sum4 = i = 0; i < n; ++i) {
    sums[i + 1] = sum4 += nodes[i].value;
  }
  partition(0, n, parent.value, x06, y06, x12, y12);
  function partition(i2, j, value, x07, y07, x13, y13) {
    if (i2 >= j - 1) {
      var node = nodes[i2];
      node.x0 = x07, node.y0 = y07;
      node.x1 = x13, node.y1 = y13;
      return;
    }
    var valueOffset = sums[i2], valueTarget = value / 2 + valueOffset, k2 = i2 + 1, hi = j - 1;
    while (k2 < hi) {
      var mid = k2 + hi >>> 1;
      if (sums[mid] < valueTarget) k2 = mid + 1;
      else hi = mid;
    }
    if (valueTarget - sums[k2 - 1] < sums[k2] - valueTarget && i2 + 1 < k2) --k2;
    var valueLeft = sums[k2] - valueOffset, valueRight = value - valueLeft;
    if (x13 - x07 > y13 - y07) {
      var xk = value ? (x07 * valueRight + x13 * valueLeft) / value : x13;
      partition(i2, k2, valueLeft, x07, y07, xk, y13);
      partition(k2, j, valueRight, xk, y07, x13, y13);
    } else {
      var yk = value ? (y07 * valueRight + y13 * valueLeft) / value : y13;
      partition(i2, k2, valueLeft, x07, y07, x13, yk);
      partition(k2, j, valueRight, x07, yk, x13, y13);
    }
  }
}

// node_modules/d3-hierarchy/src/treemap/sliceDice.js
function sliceDice_default(parent, x06, y06, x12, y12) {
  (parent.depth & 1 ? slice_default : dice_default)(parent, x06, y06, x12, y12);
}

// node_modules/d3-hierarchy/src/treemap/resquarify.js
var resquarify_default = (function custom2(ratio) {
  function resquarify(parent, x06, y06, x12, y12) {
    if ((rows = parent._squarify) && rows.ratio === ratio) {
      var rows, row, nodes, i, j = -1, n, m3 = rows.length, value = parent.value;
      while (++j < m3) {
        row = rows[j], nodes = row.children;
        for (i = row.value = 0, n = nodes.length; i < n; ++i) row.value += nodes[i].value;
        if (row.dice) dice_default(row, x06, y06, x12, value ? y06 += (y12 - y06) * row.value / value : y12);
        else slice_default(row, x06, y06, value ? x06 += (x12 - x06) * row.value / value : x12, y12);
        value -= row.value;
      }
    } else {
      parent._squarify = rows = squarifyRatio(ratio, parent, x06, y06, x12, y12);
      rows.ratio = ratio;
    }
  }
  resquarify.ratio = function(x4) {
    return custom2((x4 = +x4) > 1 ? x4 : 1);
  };
  return resquarify;
})(phi);

// node_modules/d3-polygon/src/area.js
function area_default4(polygon) {
  var i = -1, n = polygon.length, a4, b = polygon[n - 1], area = 0;
  while (++i < n) {
    a4 = b;
    b = polygon[i];
    area += a4[1] * b[0] - a4[0] * b[1];
  }
  return area / 2;
}

// node_modules/d3-polygon/src/centroid.js
function centroid_default3(polygon) {
  var i = -1, n = polygon.length, x4 = 0, y4 = 0, a4, b = polygon[n - 1], c6, k2 = 0;
  while (++i < n) {
    a4 = b;
    b = polygon[i];
    k2 += c6 = a4[0] * b[1] - b[0] * a4[1];
    x4 += (a4[0] + b[0]) * c6;
    y4 += (a4[1] + b[1]) * c6;
  }
  return k2 *= 3, [x4 / k2, y4 / k2];
}

// node_modules/d3-polygon/src/cross.js
function cross_default(a4, b, c6) {
  return (b[0] - a4[0]) * (c6[1] - a4[1]) - (b[1] - a4[1]) * (c6[0] - a4[0]);
}

// node_modules/d3-polygon/src/hull.js
function lexicographicOrder(a4, b) {
  return a4[0] - b[0] || a4[1] - b[1];
}
function computeUpperHullIndexes(points) {
  const n = points.length, indexes2 = [0, 1];
  let size = 2, i;
  for (i = 2; i < n; ++i) {
    while (size > 1 && cross_default(points[indexes2[size - 2]], points[indexes2[size - 1]], points[i]) <= 0) --size;
    indexes2[size++] = i;
  }
  return indexes2.slice(0, size);
}
function hull_default(points) {
  if ((n = points.length) < 3) return null;
  var i, n, sortedPoints = new Array(n), flippedPoints = new Array(n);
  for (i = 0; i < n; ++i) sortedPoints[i] = [+points[i][0], +points[i][1], i];
  sortedPoints.sort(lexicographicOrder);
  for (i = 0; i < n; ++i) flippedPoints[i] = [sortedPoints[i][0], -sortedPoints[i][1]];
  var upperIndexes = computeUpperHullIndexes(sortedPoints), lowerIndexes = computeUpperHullIndexes(flippedPoints);
  var skipLeft = lowerIndexes[0] === upperIndexes[0], skipRight = lowerIndexes[lowerIndexes.length - 1] === upperIndexes[upperIndexes.length - 1], hull = [];
  for (i = upperIndexes.length - 1; i >= 0; --i) hull.push(points[sortedPoints[upperIndexes[i]][2]]);
  for (i = +skipLeft; i < lowerIndexes.length - skipRight; ++i) hull.push(points[sortedPoints[lowerIndexes[i]][2]]);
  return hull;
}

// node_modules/d3-polygon/src/contains.js
function contains_default3(polygon, point6) {
  var n = polygon.length, p = polygon[n - 1], x4 = point6[0], y4 = point6[1], x06 = p[0], y06 = p[1], x12, y12, inside = false;
  for (var i = 0; i < n; ++i) {
    p = polygon[i], x12 = p[0], y12 = p[1];
    if (y12 > y4 !== y06 > y4 && x4 < (x06 - x12) * (y4 - y12) / (y06 - y12) + x12) inside = !inside;
    x06 = x12, y06 = y12;
  }
  return inside;
}

// node_modules/d3-polygon/src/length.js
function length_default2(polygon) {
  var i = -1, n = polygon.length, b = polygon[n - 1], xa, ya, xb = b[0], yb = b[1], perimeter = 0;
  while (++i < n) {
    xa = xb;
    ya = yb;
    b = polygon[i];
    xb = b[0];
    yb = b[1];
    xa -= xb;
    ya -= yb;
    perimeter += Math.hypot(xa, ya);
  }
  return perimeter;
}

// node_modules/d3-random/src/defaultSource.js
var defaultSource_default = Math.random;

// node_modules/d3-random/src/uniform.js
var uniform_default = (function sourceRandomUniform(source) {
  function randomUniform(min4, max5) {
    min4 = min4 == null ? 0 : +min4;
    max5 = max5 == null ? 1 : +max5;
    if (arguments.length === 1) max5 = min4, min4 = 0;
    else max5 -= min4;
    return function() {
      return source() * max5 + min4;
    };
  }
  randomUniform.source = sourceRandomUniform;
  return randomUniform;
})(defaultSource_default);

// node_modules/d3-random/src/int.js
var int_default = (function sourceRandomInt(source) {
  function randomInt(min4, max5) {
    if (arguments.length < 2) max5 = min4, min4 = 0;
    min4 = Math.floor(min4);
    max5 = Math.floor(max5) - min4;
    return function() {
      return Math.floor(source() * max5 + min4);
    };
  }
  randomInt.source = sourceRandomInt;
  return randomInt;
})(defaultSource_default);

// node_modules/d3-random/src/normal.js
var normal_default = (function sourceRandomNormal(source) {
  function randomNormal(mu, sigma) {
    var x4, r;
    mu = mu == null ? 0 : +mu;
    sigma = sigma == null ? 1 : +sigma;
    return function() {
      var y4;
      if (x4 != null) y4 = x4, x4 = null;
      else do {
        x4 = source() * 2 - 1;
        y4 = source() * 2 - 1;
        r = x4 * x4 + y4 * y4;
      } while (!r || r > 1);
      return mu + sigma * y4 * Math.sqrt(-2 * Math.log(r) / r);
    };
  }
  randomNormal.source = sourceRandomNormal;
  return randomNormal;
})(defaultSource_default);

// node_modules/d3-random/src/logNormal.js
var logNormal_default = (function sourceRandomLogNormal(source) {
  var N = normal_default.source(source);
  function randomLogNormal() {
    var randomNormal = N.apply(this, arguments);
    return function() {
      return Math.exp(randomNormal());
    };
  }
  randomLogNormal.source = sourceRandomLogNormal;
  return randomLogNormal;
})(defaultSource_default);

// node_modules/d3-random/src/irwinHall.js
var irwinHall_default = (function sourceRandomIrwinHall(source) {
  function randomIrwinHall(n) {
    if ((n = +n) <= 0) return () => 0;
    return function() {
      for (var sum4 = 0, i = n; i > 1; --i) sum4 += source();
      return sum4 + i * source();
    };
  }
  randomIrwinHall.source = sourceRandomIrwinHall;
  return randomIrwinHall;
})(defaultSource_default);

// node_modules/d3-random/src/bates.js
var bates_default = (function sourceRandomBates(source) {
  var I = irwinHall_default.source(source);
  function randomBates(n) {
    if ((n = +n) === 0) return source;
    var randomIrwinHall = I(n);
    return function() {
      return randomIrwinHall() / n;
    };
  }
  randomBates.source = sourceRandomBates;
  return randomBates;
})(defaultSource_default);

// node_modules/d3-random/src/exponential.js
var exponential_default = (function sourceRandomExponential(source) {
  function randomExponential(lambda) {
    return function() {
      return -Math.log1p(-source()) / lambda;
    };
  }
  randomExponential.source = sourceRandomExponential;
  return randomExponential;
})(defaultSource_default);

// node_modules/d3-random/src/pareto.js
var pareto_default = (function sourceRandomPareto(source) {
  function randomPareto(alpha) {
    if ((alpha = +alpha) < 0) throw new RangeError("invalid alpha");
    alpha = 1 / -alpha;
    return function() {
      return Math.pow(1 - source(), alpha);
    };
  }
  randomPareto.source = sourceRandomPareto;
  return randomPareto;
})(defaultSource_default);

// node_modules/d3-random/src/bernoulli.js
var bernoulli_default = (function sourceRandomBernoulli(source) {
  function randomBernoulli(p) {
    if ((p = +p) < 0 || p > 1) throw new RangeError("invalid p");
    return function() {
      return Math.floor(source() + p);
    };
  }
  randomBernoulli.source = sourceRandomBernoulli;
  return randomBernoulli;
})(defaultSource_default);

// node_modules/d3-random/src/geometric.js
var geometric_default = (function sourceRandomGeometric(source) {
  function randomGeometric(p) {
    if ((p = +p) < 0 || p > 1) throw new RangeError("invalid p");
    if (p === 0) return () => Infinity;
    if (p === 1) return () => 1;
    p = Math.log1p(-p);
    return function() {
      return 1 + Math.floor(Math.log1p(-source()) / p);
    };
  }
  randomGeometric.source = sourceRandomGeometric;
  return randomGeometric;
})(defaultSource_default);

// node_modules/d3-random/src/gamma.js
var gamma_default = (function sourceRandomGamma(source) {
  var randomNormal = normal_default.source(source)();
  function randomGamma(k2, theta) {
    if ((k2 = +k2) < 0) throw new RangeError("invalid k");
    if (k2 === 0) return () => 0;
    theta = theta == null ? 1 : +theta;
    if (k2 === 1) return () => -Math.log1p(-source()) * theta;
    var d = (k2 < 1 ? k2 + 1 : k2) - 1 / 3, c6 = 1 / (3 * Math.sqrt(d)), multiplier = k2 < 1 ? () => Math.pow(source(), 1 / k2) : () => 1;
    return function() {
      do {
        do {
          var x4 = randomNormal(), v2 = 1 + c6 * x4;
        } while (v2 <= 0);
        v2 *= v2 * v2;
        var u4 = 1 - source();
      } while (u4 >= 1 - 0.0331 * x4 * x4 * x4 * x4 && Math.log(u4) >= 0.5 * x4 * x4 + d * (1 - v2 + Math.log(v2)));
      return d * v2 * multiplier() * theta;
    };
  }
  randomGamma.source = sourceRandomGamma;
  return randomGamma;
})(defaultSource_default);

// node_modules/d3-random/src/beta.js
var beta_default = (function sourceRandomBeta(source) {
  var G = gamma_default.source(source);
  function randomBeta(alpha, beta) {
    var X3 = G(alpha), Y3 = G(beta);
    return function() {
      var x4 = X3();
      return x4 === 0 ? 0 : x4 / (x4 + Y3());
    };
  }
  randomBeta.source = sourceRandomBeta;
  return randomBeta;
})(defaultSource_default);

// node_modules/d3-random/src/binomial.js
var binomial_default = (function sourceRandomBinomial(source) {
  var G = geometric_default.source(source), B2 = beta_default.source(source);
  function randomBinomial(n, p) {
    n = +n;
    if ((p = +p) >= 1) return () => n;
    if (p <= 0) return () => 0;
    return function() {
      var acc = 0, nn = n, pp = p;
      while (nn * pp > 16 && nn * (1 - pp) > 16) {
        var i = Math.floor((nn + 1) * pp), y4 = B2(i, nn - i + 1)();
        if (y4 <= pp) {
          acc += i;
          nn -= i;
          pp = (pp - y4) / (1 - y4);
        } else {
          nn = i - 1;
          pp /= y4;
        }
      }
      var sign3 = pp < 0.5, pFinal = sign3 ? pp : 1 - pp, g = G(pFinal);
      for (var s2 = g(), k2 = 0; s2 <= nn; ++k2) s2 += g();
      return acc + (sign3 ? k2 : nn - k2);
    };
  }
  randomBinomial.source = sourceRandomBinomial;
  return randomBinomial;
})(defaultSource_default);

// node_modules/d3-random/src/weibull.js
var weibull_default = (function sourceRandomWeibull(source) {
  function randomWeibull(k2, a4, b) {
    var outerFunc;
    if ((k2 = +k2) === 0) {
      outerFunc = (x4) => -Math.log(x4);
    } else {
      k2 = 1 / k2;
      outerFunc = (x4) => Math.pow(x4, k2);
    }
    a4 = a4 == null ? 0 : +a4;
    b = b == null ? 1 : +b;
    return function() {
      return a4 + b * outerFunc(-Math.log1p(-source()));
    };
  }
  randomWeibull.source = sourceRandomWeibull;
  return randomWeibull;
})(defaultSource_default);

// node_modules/d3-random/src/cauchy.js
var cauchy_default = (function sourceRandomCauchy(source) {
  function randomCauchy(a4, b) {
    a4 = a4 == null ? 0 : +a4;
    b = b == null ? 1 : +b;
    return function() {
      return a4 + b * Math.tan(Math.PI * source());
    };
  }
  randomCauchy.source = sourceRandomCauchy;
  return randomCauchy;
})(defaultSource_default);

// node_modules/d3-random/src/logistic.js
var logistic_default = (function sourceRandomLogistic(source) {
  function randomLogistic(a4, b) {
    a4 = a4 == null ? 0 : +a4;
    b = b == null ? 1 : +b;
    return function() {
      var u4 = source();
      return a4 + b * Math.log(u4 / (1 - u4));
    };
  }
  randomLogistic.source = sourceRandomLogistic;
  return randomLogistic;
})(defaultSource_default);

// node_modules/d3-random/src/poisson.js
var poisson_default = (function sourceRandomPoisson(source) {
  var G = gamma_default.source(source), B2 = binomial_default.source(source);
  function randomPoisson(lambda) {
    return function() {
      var acc = 0, l = lambda;
      while (l > 16) {
        var n = Math.floor(0.875 * l), t = G(n)();
        if (t > l) return acc + B2(n - 1, l / t)();
        acc += n;
        l -= t;
      }
      for (var s2 = -Math.log1p(-source()), k2 = 0; s2 <= l; ++k2) s2 -= Math.log1p(-source());
      return acc + k2;
    };
  }
  randomPoisson.source = sourceRandomPoisson;
  return randomPoisson;
})(defaultSource_default);

// node_modules/d3-random/src/lcg.js
var mul = 1664525;
var inc = 1013904223;
var eps = 1 / 4294967296;
function lcg(seed = Math.random()) {
  let state = (0 <= seed && seed < 1 ? seed / eps : Math.abs(seed)) | 0;
  return () => (state = mul * state + inc | 0, eps * (state >>> 0));
}

// node_modules/d3-scale/src/init.js
function initRange(domain, range4) {
  switch (arguments.length) {
    case 0:
      break;
    case 1:
      this.range(domain);
      break;
    default:
      this.range(range4).domain(domain);
      break;
  }
  return this;
}
function initInterpolator(domain, interpolator) {
  switch (arguments.length) {
    case 0:
      break;
    case 1: {
      if (typeof domain === "function") this.interpolator(domain);
      else this.range(domain);
      break;
    }
    default: {
      this.domain(domain);
      if (typeof interpolator === "function") this.interpolator(interpolator);
      else this.range(interpolator);
      break;
    }
  }
  return this;
}

// node_modules/d3-scale/src/ordinal.js
var implicit = Symbol("implicit");
function ordinal() {
  var index3 = new InternMap(), domain = [], range4 = [], unknown = implicit;
  function scale2(d) {
    let i = index3.get(d);
    if (i === void 0) {
      if (unknown !== implicit) return unknown;
      index3.set(d, i = domain.push(d) - 1);
    }
    return range4[i % range4.length];
  }
  scale2.domain = function(_) {
    if (!arguments.length) return domain.slice();
    domain = [], index3 = new InternMap();
    for (const value of _) {
      if (index3.has(value)) continue;
      index3.set(value, domain.push(value) - 1);
    }
    return scale2;
  };
  scale2.range = function(_) {
    return arguments.length ? (range4 = Array.from(_), scale2) : range4.slice();
  };
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : unknown;
  };
  scale2.copy = function() {
    return ordinal(domain, range4).unknown(unknown);
  };
  initRange.apply(scale2, arguments);
  return scale2;
}

// node_modules/d3-scale/src/band.js
function band() {
  var scale2 = ordinal().unknown(void 0), domain = scale2.domain, ordinalRange = scale2.range, r0 = 0, r1 = 1, step, bandwidth, round = false, paddingInner = 0, paddingOuter = 0, align = 0.5;
  delete scale2.unknown;
  function rescale() {
    var n = domain().length, reverse2 = r1 < r0, start = reverse2 ? r1 : r0, stop = reverse2 ? r0 : r1;
    step = (stop - start) / Math.max(1, n - paddingInner + paddingOuter * 2);
    if (round) step = Math.floor(step);
    start += (stop - start - step * (n - paddingInner)) * align;
    bandwidth = step * (1 - paddingInner);
    if (round) start = Math.round(start), bandwidth = Math.round(bandwidth);
    var values = range(n).map(function(i) {
      return start + step * i;
    });
    return ordinalRange(reverse2 ? values.reverse() : values);
  }
  scale2.domain = function(_) {
    return arguments.length ? (domain(_), rescale()) : domain();
  };
  scale2.range = function(_) {
    return arguments.length ? ([r0, r1] = _, r0 = +r0, r1 = +r1, rescale()) : [r0, r1];
  };
  scale2.rangeRound = function(_) {
    return [r0, r1] = _, r0 = +r0, r1 = +r1, round = true, rescale();
  };
  scale2.bandwidth = function() {
    return bandwidth;
  };
  scale2.step = function() {
    return step;
  };
  scale2.round = function(_) {
    return arguments.length ? (round = !!_, rescale()) : round;
  };
  scale2.padding = function(_) {
    return arguments.length ? (paddingInner = Math.min(1, paddingOuter = +_), rescale()) : paddingInner;
  };
  scale2.paddingInner = function(_) {
    return arguments.length ? (paddingInner = Math.min(1, _), rescale()) : paddingInner;
  };
  scale2.paddingOuter = function(_) {
    return arguments.length ? (paddingOuter = +_, rescale()) : paddingOuter;
  };
  scale2.align = function(_) {
    return arguments.length ? (align = Math.max(0, Math.min(1, _)), rescale()) : align;
  };
  scale2.copy = function() {
    return band(domain(), [r0, r1]).round(round).paddingInner(paddingInner).paddingOuter(paddingOuter).align(align);
  };
  return initRange.apply(rescale(), arguments);
}
function pointish(scale2) {
  var copy3 = scale2.copy;
  scale2.padding = scale2.paddingOuter;
  delete scale2.paddingInner;
  delete scale2.paddingOuter;
  scale2.copy = function() {
    return pointish(copy3());
  };
  return scale2;
}
function point() {
  return pointish(band.apply(null, arguments).paddingInner(1));
}

// node_modules/d3-scale/src/constant.js
function constants(x4) {
  return function() {
    return x4;
  };
}

// node_modules/d3-scale/src/number.js
function number3(x4) {
  return +x4;
}

// node_modules/d3-scale/src/continuous.js
var unit = [0, 1];
function identity3(x4) {
  return x4;
}
function normalize2(a4, b) {
  return (b -= a4 = +a4) ? function(x4) {
    return (x4 - a4) / b;
  } : constants(isNaN(b) ? NaN : 0.5);
}
function clamper(a4, b) {
  var t;
  if (a4 > b) t = a4, a4 = b, b = t;
  return function(x4) {
    return Math.max(a4, Math.min(b, x4));
  };
}
function bimap(domain, range4, interpolate) {
  var d0 = domain[0], d1 = domain[1], r0 = range4[0], r1 = range4[1];
  if (d1 < d0) d0 = normalize2(d1, d0), r0 = interpolate(r1, r0);
  else d0 = normalize2(d0, d1), r0 = interpolate(r0, r1);
  return function(x4) {
    return r0(d0(x4));
  };
}
function polymap(domain, range4, interpolate) {
  var j = Math.min(domain.length, range4.length) - 1, d = new Array(j), r = new Array(j), i = -1;
  if (domain[j] < domain[0]) {
    domain = domain.slice().reverse();
    range4 = range4.slice().reverse();
  }
  while (++i < j) {
    d[i] = normalize2(domain[i], domain[i + 1]);
    r[i] = interpolate(range4[i], range4[i + 1]);
  }
  return function(x4) {
    var i2 = bisect_default(domain, x4, 1, j) - 1;
    return r[i2](d[i2](x4));
  };
}
function copy(source, target) {
  return target.domain(source.domain()).range(source.range()).interpolate(source.interpolate()).clamp(source.clamp()).unknown(source.unknown());
}
function transformer2() {
  var domain = unit, range4 = unit, interpolate = value_default, transform2, untransform, unknown, clamp = identity3, piecewise2, output, input;
  function rescale() {
    var n = Math.min(domain.length, range4.length);
    if (clamp !== identity3) clamp = clamper(domain[0], domain[n - 1]);
    piecewise2 = n > 2 ? polymap : bimap;
    output = input = null;
    return scale2;
  }
  function scale2(x4) {
    return x4 == null || isNaN(x4 = +x4) ? unknown : (output || (output = piecewise2(domain.map(transform2), range4, interpolate)))(transform2(clamp(x4)));
  }
  scale2.invert = function(y4) {
    return clamp(untransform((input || (input = piecewise2(range4, domain.map(transform2), number_default)))(y4)));
  };
  scale2.domain = function(_) {
    return arguments.length ? (domain = Array.from(_, number3), rescale()) : domain.slice();
  };
  scale2.range = function(_) {
    return arguments.length ? (range4 = Array.from(_), rescale()) : range4.slice();
  };
  scale2.rangeRound = function(_) {
    return range4 = Array.from(_), interpolate = round_default, rescale();
  };
  scale2.clamp = function(_) {
    return arguments.length ? (clamp = _ ? true : identity3, rescale()) : clamp !== identity3;
  };
  scale2.interpolate = function(_) {
    return arguments.length ? (interpolate = _, rescale()) : interpolate;
  };
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : unknown;
  };
  return function(t, u4) {
    transform2 = t, untransform = u4;
    return rescale();
  };
}
function continuous() {
  return transformer2()(identity3, identity3);
}

// node_modules/d3-scale/src/tickFormat.js
function tickFormat(start, stop, count3, specifier) {
  var step = tickStep(start, stop, count3), precision;
  specifier = formatSpecifier(specifier == null ? ",f" : specifier);
  switch (specifier.type) {
    case "s": {
      var value = Math.max(Math.abs(start), Math.abs(stop));
      if (specifier.precision == null && !isNaN(precision = precisionPrefix_default(step, value))) specifier.precision = precision;
      return formatPrefix(specifier, value);
    }
    case "":
    case "e":
    case "g":
    case "p":
    case "r": {
      if (specifier.precision == null && !isNaN(precision = precisionRound_default(step, Math.max(Math.abs(start), Math.abs(stop))))) specifier.precision = precision - (specifier.type === "e");
      break;
    }
    case "f":
    case "%": {
      if (specifier.precision == null && !isNaN(precision = precisionFixed_default(step))) specifier.precision = precision - (specifier.type === "%") * 2;
      break;
    }
  }
  return format(specifier);
}

// node_modules/d3-scale/src/linear.js
function linearish(scale2) {
  var domain = scale2.domain;
  scale2.ticks = function(count3) {
    var d = domain();
    return ticks(d[0], d[d.length - 1], count3 == null ? 10 : count3);
  };
  scale2.tickFormat = function(count3, specifier) {
    var d = domain();
    return tickFormat(d[0], d[d.length - 1], count3 == null ? 10 : count3, specifier);
  };
  scale2.nice = function(count3) {
    if (count3 == null) count3 = 10;
    var d = domain();
    var i0 = 0;
    var i1 = d.length - 1;
    var start = d[i0];
    var stop = d[i1];
    var prestep;
    var step;
    var maxIter = 10;
    if (stop < start) {
      step = start, start = stop, stop = step;
      step = i0, i0 = i1, i1 = step;
    }
    while (maxIter-- > 0) {
      step = tickIncrement(start, stop, count3);
      if (step === prestep) {
        d[i0] = start;
        d[i1] = stop;
        return domain(d);
      } else if (step > 0) {
        start = Math.floor(start / step) * step;
        stop = Math.ceil(stop / step) * step;
      } else if (step < 0) {
        start = Math.ceil(start * step) / step;
        stop = Math.floor(stop * step) / step;
      } else {
        break;
      }
      prestep = step;
    }
    return scale2;
  };
  return scale2;
}
function linear2() {
  var scale2 = continuous();
  scale2.copy = function() {
    return copy(scale2, linear2());
  };
  initRange.apply(scale2, arguments);
  return linearish(scale2);
}

// node_modules/d3-scale/src/identity.js
function identity4(domain) {
  var unknown;
  function scale2(x4) {
    return x4 == null || isNaN(x4 = +x4) ? unknown : x4;
  }
  scale2.invert = scale2;
  scale2.domain = scale2.range = function(_) {
    return arguments.length ? (domain = Array.from(_, number3), scale2) : domain.slice();
  };
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : unknown;
  };
  scale2.copy = function() {
    return identity4(domain).unknown(unknown);
  };
  domain = arguments.length ? Array.from(domain, number3) : [0, 1];
  return linearish(scale2);
}

// node_modules/d3-scale/src/nice.js
function nice2(domain, interval) {
  domain = domain.slice();
  var i0 = 0, i1 = domain.length - 1, x06 = domain[i0], x12 = domain[i1], t;
  if (x12 < x06) {
    t = i0, i0 = i1, i1 = t;
    t = x06, x06 = x12, x12 = t;
  }
  domain[i0] = interval.floor(x06);
  domain[i1] = interval.ceil(x12);
  return domain;
}

// node_modules/d3-scale/src/log.js
function transformLog(x4) {
  return Math.log(x4);
}
function transformExp(x4) {
  return Math.exp(x4);
}
function transformLogn(x4) {
  return -Math.log(-x4);
}
function transformExpn(x4) {
  return -Math.exp(-x4);
}
function pow10(x4) {
  return isFinite(x4) ? +("1e" + x4) : x4 < 0 ? 0 : x4;
}
function powp(base) {
  return base === 10 ? pow10 : base === Math.E ? Math.exp : (x4) => Math.pow(base, x4);
}
function logp(base) {
  return base === Math.E ? Math.log : base === 10 && Math.log10 || base === 2 && Math.log2 || (base = Math.log(base), (x4) => Math.log(x4) / base);
}
function reflect(f) {
  return (x4, k2) => -f(-x4, k2);
}
function loggish(transform2) {
  const scale2 = transform2(transformLog, transformExp);
  const domain = scale2.domain;
  let base = 10;
  let logs;
  let pows;
  function rescale() {
    logs = logp(base), pows = powp(base);
    if (domain()[0] < 0) {
      logs = reflect(logs), pows = reflect(pows);
      transform2(transformLogn, transformExpn);
    } else {
      transform2(transformLog, transformExp);
    }
    return scale2;
  }
  scale2.base = function(_) {
    return arguments.length ? (base = +_, rescale()) : base;
  };
  scale2.domain = function(_) {
    return arguments.length ? (domain(_), rescale()) : domain();
  };
  scale2.ticks = (count3) => {
    const d = domain();
    let u4 = d[0];
    let v2 = d[d.length - 1];
    const r = v2 < u4;
    if (r) [u4, v2] = [v2, u4];
    let i = logs(u4);
    let j = logs(v2);
    let k2;
    let t;
    const n = count3 == null ? 10 : +count3;
    let z = [];
    if (!(base % 1) && j - i < n) {
      i = Math.floor(i), j = Math.ceil(j);
      if (u4 > 0) for (; i <= j; ++i) {
        for (k2 = 1; k2 < base; ++k2) {
          t = i < 0 ? k2 / pows(-i) : k2 * pows(i);
          if (t < u4) continue;
          if (t > v2) break;
          z.push(t);
        }
      }
      else for (; i <= j; ++i) {
        for (k2 = base - 1; k2 >= 1; --k2) {
          t = i > 0 ? k2 / pows(-i) : k2 * pows(i);
          if (t < u4) continue;
          if (t > v2) break;
          z.push(t);
        }
      }
      if (z.length * 2 < n) z = ticks(u4, v2, n);
    } else {
      z = ticks(i, j, Math.min(j - i, n)).map(pows);
    }
    return r ? z.reverse() : z;
  };
  scale2.tickFormat = (count3, specifier) => {
    if (count3 == null) count3 = 10;
    if (specifier == null) specifier = base === 10 ? "s" : ",";
    if (typeof specifier !== "function") {
      if (!(base % 1) && (specifier = formatSpecifier(specifier)).precision == null) specifier.trim = true;
      specifier = format(specifier);
    }
    if (count3 === Infinity) return specifier;
    const k2 = Math.max(1, base * count3 / scale2.ticks().length);
    return (d) => {
      let i = d / pows(Math.round(logs(d)));
      if (i * base < base - 0.5) i *= base;
      return i <= k2 ? specifier(d) : "";
    };
  };
  scale2.nice = () => {
    return domain(nice2(domain(), {
      floor: (x4) => pows(Math.floor(logs(x4))),
      ceil: (x4) => pows(Math.ceil(logs(x4)))
    }));
  };
  return scale2;
}
function log2() {
  const scale2 = loggish(transformer2()).domain([1, 10]);
  scale2.copy = () => copy(scale2, log2()).base(scale2.base());
  initRange.apply(scale2, arguments);
  return scale2;
}

// node_modules/d3-scale/src/symlog.js
function transformSymlog(c6) {
  return function(x4) {
    return Math.sign(x4) * Math.log1p(Math.abs(x4 / c6));
  };
}
function transformSymexp(c6) {
  return function(x4) {
    return Math.sign(x4) * Math.expm1(Math.abs(x4)) * c6;
  };
}
function symlogish(transform2) {
  var c6 = 1, scale2 = transform2(transformSymlog(c6), transformSymexp(c6));
  scale2.constant = function(_) {
    return arguments.length ? transform2(transformSymlog(c6 = +_), transformSymexp(c6)) : c6;
  };
  return linearish(scale2);
}
function symlog() {
  var scale2 = symlogish(transformer2());
  scale2.copy = function() {
    return copy(scale2, symlog()).constant(scale2.constant());
  };
  return initRange.apply(scale2, arguments);
}

// node_modules/d3-scale/src/pow.js
function transformPow(exponent) {
  return function(x4) {
    return x4 < 0 ? -Math.pow(-x4, exponent) : Math.pow(x4, exponent);
  };
}
function transformSqrt(x4) {
  return x4 < 0 ? -Math.sqrt(-x4) : Math.sqrt(x4);
}
function transformSquare(x4) {
  return x4 < 0 ? -x4 * x4 : x4 * x4;
}
function powish(transform2) {
  var scale2 = transform2(identity3, identity3), exponent = 1;
  function rescale() {
    return exponent === 1 ? transform2(identity3, identity3) : exponent === 0.5 ? transform2(transformSqrt, transformSquare) : transform2(transformPow(exponent), transformPow(1 / exponent));
  }
  scale2.exponent = function(_) {
    return arguments.length ? (exponent = +_, rescale()) : exponent;
  };
  return linearish(scale2);
}
function pow3() {
  var scale2 = powish(transformer2());
  scale2.copy = function() {
    return copy(scale2, pow3()).exponent(scale2.exponent());
  };
  initRange.apply(scale2, arguments);
  return scale2;
}
function sqrt2() {
  return pow3.apply(null, arguments).exponent(0.5);
}

// node_modules/d3-scale/src/radial.js
function square(x4) {
  return Math.sign(x4) * x4 * x4;
}
function unsquare(x4) {
  return Math.sign(x4) * Math.sqrt(Math.abs(x4));
}
function radial() {
  var squared = continuous(), range4 = [0, 1], round = false, unknown;
  function scale2(x4) {
    var y4 = unsquare(squared(x4));
    return isNaN(y4) ? unknown : round ? Math.round(y4) : y4;
  }
  scale2.invert = function(y4) {
    return squared.invert(square(y4));
  };
  scale2.domain = function(_) {
    return arguments.length ? (squared.domain(_), scale2) : squared.domain();
  };
  scale2.range = function(_) {
    return arguments.length ? (squared.range((range4 = Array.from(_, number3)).map(square)), scale2) : range4.slice();
  };
  scale2.rangeRound = function(_) {
    return scale2.range(_).round(true);
  };
  scale2.round = function(_) {
    return arguments.length ? (round = !!_, scale2) : round;
  };
  scale2.clamp = function(_) {
    return arguments.length ? (squared.clamp(_), scale2) : squared.clamp();
  };
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : unknown;
  };
  scale2.copy = function() {
    return radial(squared.domain(), range4).round(round).clamp(squared.clamp()).unknown(unknown);
  };
  initRange.apply(scale2, arguments);
  return linearish(scale2);
}

// node_modules/d3-scale/src/quantile.js
function quantile2() {
  var domain = [], range4 = [], thresholds = [], unknown;
  function rescale() {
    var i = 0, n = Math.max(1, range4.length);
    thresholds = new Array(n - 1);
    while (++i < n) thresholds[i - 1] = quantileSorted(domain, i / n);
    return scale2;
  }
  function scale2(x4) {
    return x4 == null || isNaN(x4 = +x4) ? unknown : range4[bisect_default(thresholds, x4)];
  }
  scale2.invertExtent = function(y4) {
    var i = range4.indexOf(y4);
    return i < 0 ? [NaN, NaN] : [
      i > 0 ? thresholds[i - 1] : domain[0],
      i < thresholds.length ? thresholds[i] : domain[domain.length - 1]
    ];
  };
  scale2.domain = function(_) {
    if (!arguments.length) return domain.slice();
    domain = [];
    for (let d of _) if (d != null && !isNaN(d = +d)) domain.push(d);
    domain.sort(ascending);
    return rescale();
  };
  scale2.range = function(_) {
    return arguments.length ? (range4 = Array.from(_), rescale()) : range4.slice();
  };
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : unknown;
  };
  scale2.quantiles = function() {
    return thresholds.slice();
  };
  scale2.copy = function() {
    return quantile2().domain(domain).range(range4).unknown(unknown);
  };
  return initRange.apply(scale2, arguments);
}

// node_modules/d3-scale/src/quantize.js
function quantize() {
  var x06 = 0, x12 = 1, n = 1, domain = [0.5], range4 = [0, 1], unknown;
  function scale2(x4) {
    return x4 != null && x4 <= x4 ? range4[bisect_default(domain, x4, 0, n)] : unknown;
  }
  function rescale() {
    var i = -1;
    domain = new Array(n);
    while (++i < n) domain[i] = ((i + 1) * x12 - (i - n) * x06) / (n + 1);
    return scale2;
  }
  scale2.domain = function(_) {
    return arguments.length ? ([x06, x12] = _, x06 = +x06, x12 = +x12, rescale()) : [x06, x12];
  };
  scale2.range = function(_) {
    return arguments.length ? (n = (range4 = Array.from(_)).length - 1, rescale()) : range4.slice();
  };
  scale2.invertExtent = function(y4) {
    var i = range4.indexOf(y4);
    return i < 0 ? [NaN, NaN] : i < 1 ? [x06, domain[0]] : i >= n ? [domain[n - 1], x12] : [domain[i - 1], domain[i]];
  };
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : scale2;
  };
  scale2.thresholds = function() {
    return domain.slice();
  };
  scale2.copy = function() {
    return quantize().domain([x06, x12]).range(range4).unknown(unknown);
  };
  return initRange.apply(linearish(scale2), arguments);
}

// node_modules/d3-scale/src/threshold.js
function threshold() {
  var domain = [0.5], range4 = [0, 1], unknown, n = 1;
  function scale2(x4) {
    return x4 != null && x4 <= x4 ? range4[bisect_default(domain, x4, 0, n)] : unknown;
  }
  scale2.domain = function(_) {
    return arguments.length ? (domain = Array.from(_), n = Math.min(domain.length, range4.length - 1), scale2) : domain.slice();
  };
  scale2.range = function(_) {
    return arguments.length ? (range4 = Array.from(_), n = Math.min(domain.length, range4.length - 1), scale2) : range4.slice();
  };
  scale2.invertExtent = function(y4) {
    var i = range4.indexOf(y4);
    return [domain[i - 1], domain[i]];
  };
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : unknown;
  };
  scale2.copy = function() {
    return threshold().domain(domain).range(range4).unknown(unknown);
  };
  return initRange.apply(scale2, arguments);
}

// node_modules/d3-time/src/interval.js
var t0 = /* @__PURE__ */ new Date();
var t1 = /* @__PURE__ */ new Date();
function timeInterval(floori, offseti, count3, field) {
  function interval(date2) {
    return floori(date2 = arguments.length === 0 ? /* @__PURE__ */ new Date() : /* @__PURE__ */ new Date(+date2)), date2;
  }
  interval.floor = (date2) => {
    return floori(date2 = /* @__PURE__ */ new Date(+date2)), date2;
  };
  interval.ceil = (date2) => {
    return floori(date2 = new Date(date2 - 1)), offseti(date2, 1), floori(date2), date2;
  };
  interval.round = (date2) => {
    const d0 = interval(date2), d1 = interval.ceil(date2);
    return date2 - d0 < d1 - date2 ? d0 : d1;
  };
  interval.offset = (date2, step) => {
    return offseti(date2 = /* @__PURE__ */ new Date(+date2), step == null ? 1 : Math.floor(step)), date2;
  };
  interval.range = (start, stop, step) => {
    const range4 = [];
    start = interval.ceil(start);
    step = step == null ? 1 : Math.floor(step);
    if (!(start < stop) || !(step > 0)) return range4;
    let previous;
    do
      range4.push(previous = /* @__PURE__ */ new Date(+start)), offseti(start, step), floori(start);
    while (previous < start && start < stop);
    return range4;
  };
  interval.filter = (test) => {
    return timeInterval((date2) => {
      if (date2 >= date2) while (floori(date2), !test(date2)) date2.setTime(date2 - 1);
    }, (date2, step) => {
      if (date2 >= date2) {
        if (step < 0) while (++step <= 0) {
          while (offseti(date2, -1), !test(date2)) {
          }
        }
        else while (--step >= 0) {
          while (offseti(date2, 1), !test(date2)) {
          }
        }
      }
    });
  };
  if (count3) {
    interval.count = (start, end) => {
      t0.setTime(+start), t1.setTime(+end);
      floori(t0), floori(t1);
      return Math.floor(count3(t0, t1));
    };
    interval.every = (step) => {
      step = Math.floor(step);
      return !isFinite(step) || !(step > 0) ? null : !(step > 1) ? interval : interval.filter(field ? (d) => field(d) % step === 0 : (d) => interval.count(0, d) % step === 0);
    };
  }
  return interval;
}

// node_modules/d3-time/src/millisecond.js
var millisecond = timeInterval(() => {
}, (date2, step) => {
  date2.setTime(+date2 + step);
}, (start, end) => {
  return end - start;
});
millisecond.every = (k2) => {
  k2 = Math.floor(k2);
  if (!isFinite(k2) || !(k2 > 0)) return null;
  if (!(k2 > 1)) return millisecond;
  return timeInterval((date2) => {
    date2.setTime(Math.floor(date2 / k2) * k2);
  }, (date2, step) => {
    date2.setTime(+date2 + step * k2);
  }, (start, end) => {
    return (end - start) / k2;
  });
};
var milliseconds = millisecond.range;

// node_modules/d3-time/src/duration.js
var durationSecond = 1e3;
var durationMinute = durationSecond * 60;
var durationHour = durationMinute * 60;
var durationDay = durationHour * 24;
var durationWeek = durationDay * 7;
var durationMonth = durationDay * 30;
var durationYear = durationDay * 365;

// node_modules/d3-time/src/second.js
var second = timeInterval((date2) => {
  date2.setTime(date2 - date2.getMilliseconds());
}, (date2, step) => {
  date2.setTime(+date2 + step * durationSecond);
}, (start, end) => {
  return (end - start) / durationSecond;
}, (date2) => {
  return date2.getUTCSeconds();
});
var seconds = second.range;

// node_modules/d3-time/src/minute.js
var timeMinute = timeInterval((date2) => {
  date2.setTime(date2 - date2.getMilliseconds() - date2.getSeconds() * durationSecond);
}, (date2, step) => {
  date2.setTime(+date2 + step * durationMinute);
}, (start, end) => {
  return (end - start) / durationMinute;
}, (date2) => {
  return date2.getMinutes();
});
var timeMinutes = timeMinute.range;
var utcMinute = timeInterval((date2) => {
  date2.setUTCSeconds(0, 0);
}, (date2, step) => {
  date2.setTime(+date2 + step * durationMinute);
}, (start, end) => {
  return (end - start) / durationMinute;
}, (date2) => {
  return date2.getUTCMinutes();
});
var utcMinutes = utcMinute.range;

// node_modules/d3-time/src/hour.js
var timeHour = timeInterval((date2) => {
  date2.setTime(date2 - date2.getMilliseconds() - date2.getSeconds() * durationSecond - date2.getMinutes() * durationMinute);
}, (date2, step) => {
  date2.setTime(+date2 + step * durationHour);
}, (start, end) => {
  return (end - start) / durationHour;
}, (date2) => {
  return date2.getHours();
});
var timeHours = timeHour.range;
var utcHour = timeInterval((date2) => {
  date2.setUTCMinutes(0, 0, 0);
}, (date2, step) => {
  date2.setTime(+date2 + step * durationHour);
}, (start, end) => {
  return (end - start) / durationHour;
}, (date2) => {
  return date2.getUTCHours();
});
var utcHours = utcHour.range;

// node_modules/d3-time/src/day.js
var timeDay = timeInterval(
  (date2) => date2.setHours(0, 0, 0, 0),
  (date2, step) => date2.setDate(date2.getDate() + step),
  (start, end) => (end - start - (end.getTimezoneOffset() - start.getTimezoneOffset()) * durationMinute) / durationDay,
  (date2) => date2.getDate() - 1
);
var timeDays = timeDay.range;
var utcDay = timeInterval((date2) => {
  date2.setUTCHours(0, 0, 0, 0);
}, (date2, step) => {
  date2.setUTCDate(date2.getUTCDate() + step);
}, (start, end) => {
  return (end - start) / durationDay;
}, (date2) => {
  return date2.getUTCDate() - 1;
});
var utcDays = utcDay.range;
var unixDay = timeInterval((date2) => {
  date2.setUTCHours(0, 0, 0, 0);
}, (date2, step) => {
  date2.setUTCDate(date2.getUTCDate() + step);
}, (start, end) => {
  return (end - start) / durationDay;
}, (date2) => {
  return Math.floor(date2 / durationDay);
});
var unixDays = unixDay.range;

// node_modules/d3-time/src/week.js
function timeWeekday(i) {
  return timeInterval((date2) => {
    date2.setDate(date2.getDate() - (date2.getDay() + 7 - i) % 7);
    date2.setHours(0, 0, 0, 0);
  }, (date2, step) => {
    date2.setDate(date2.getDate() + step * 7);
  }, (start, end) => {
    return (end - start - (end.getTimezoneOffset() - start.getTimezoneOffset()) * durationMinute) / durationWeek;
  });
}
var timeSunday = timeWeekday(0);
var timeMonday = timeWeekday(1);
var timeTuesday = timeWeekday(2);
var timeWednesday = timeWeekday(3);
var timeThursday = timeWeekday(4);
var timeFriday = timeWeekday(5);
var timeSaturday = timeWeekday(6);
var timeSundays = timeSunday.range;
var timeMondays = timeMonday.range;
var timeTuesdays = timeTuesday.range;
var timeWednesdays = timeWednesday.range;
var timeThursdays = timeThursday.range;
var timeFridays = timeFriday.range;
var timeSaturdays = timeSaturday.range;
function utcWeekday(i) {
  return timeInterval((date2) => {
    date2.setUTCDate(date2.getUTCDate() - (date2.getUTCDay() + 7 - i) % 7);
    date2.setUTCHours(0, 0, 0, 0);
  }, (date2, step) => {
    date2.setUTCDate(date2.getUTCDate() + step * 7);
  }, (start, end) => {
    return (end - start) / durationWeek;
  });
}
var utcSunday = utcWeekday(0);
var utcMonday = utcWeekday(1);
var utcTuesday = utcWeekday(2);
var utcWednesday = utcWeekday(3);
var utcThursday = utcWeekday(4);
var utcFriday = utcWeekday(5);
var utcSaturday = utcWeekday(6);
var utcSundays = utcSunday.range;
var utcMondays = utcMonday.range;
var utcTuesdays = utcTuesday.range;
var utcWednesdays = utcWednesday.range;
var utcThursdays = utcThursday.range;
var utcFridays = utcFriday.range;
var utcSaturdays = utcSaturday.range;

// node_modules/d3-time/src/month.js
var timeMonth = timeInterval((date2) => {
  date2.setDate(1);
  date2.setHours(0, 0, 0, 0);
}, (date2, step) => {
  date2.setMonth(date2.getMonth() + step);
}, (start, end) => {
  return end.getMonth() - start.getMonth() + (end.getFullYear() - start.getFullYear()) * 12;
}, (date2) => {
  return date2.getMonth();
});
var timeMonths = timeMonth.range;
var utcMonth = timeInterval((date2) => {
  date2.setUTCDate(1);
  date2.setUTCHours(0, 0, 0, 0);
}, (date2, step) => {
  date2.setUTCMonth(date2.getUTCMonth() + step);
}, (start, end) => {
  return end.getUTCMonth() - start.getUTCMonth() + (end.getUTCFullYear() - start.getUTCFullYear()) * 12;
}, (date2) => {
  return date2.getUTCMonth();
});
var utcMonths = utcMonth.range;

// node_modules/d3-time/src/year.js
var timeYear = timeInterval((date2) => {
  date2.setMonth(0, 1);
  date2.setHours(0, 0, 0, 0);
}, (date2, step) => {
  date2.setFullYear(date2.getFullYear() + step);
}, (start, end) => {
  return end.getFullYear() - start.getFullYear();
}, (date2) => {
  return date2.getFullYear();
});
timeYear.every = (k2) => {
  return !isFinite(k2 = Math.floor(k2)) || !(k2 > 0) ? null : timeInterval((date2) => {
    date2.setFullYear(Math.floor(date2.getFullYear() / k2) * k2);
    date2.setMonth(0, 1);
    date2.setHours(0, 0, 0, 0);
  }, (date2, step) => {
    date2.setFullYear(date2.getFullYear() + step * k2);
  });
};
var timeYears = timeYear.range;
var utcYear = timeInterval((date2) => {
  date2.setUTCMonth(0, 1);
  date2.setUTCHours(0, 0, 0, 0);
}, (date2, step) => {
  date2.setUTCFullYear(date2.getUTCFullYear() + step);
}, (start, end) => {
  return end.getUTCFullYear() - start.getUTCFullYear();
}, (date2) => {
  return date2.getUTCFullYear();
});
utcYear.every = (k2) => {
  return !isFinite(k2 = Math.floor(k2)) || !(k2 > 0) ? null : timeInterval((date2) => {
    date2.setUTCFullYear(Math.floor(date2.getUTCFullYear() / k2) * k2);
    date2.setUTCMonth(0, 1);
    date2.setUTCHours(0, 0, 0, 0);
  }, (date2, step) => {
    date2.setUTCFullYear(date2.getUTCFullYear() + step * k2);
  });
};
var utcYears = utcYear.range;

// node_modules/d3-time/src/ticks.js
function ticker(year, month, week, day, hour, minute) {
  const tickIntervals = [
    [second, 1, durationSecond],
    [second, 5, 5 * durationSecond],
    [second, 15, 15 * durationSecond],
    [second, 30, 30 * durationSecond],
    [minute, 1, durationMinute],
    [minute, 5, 5 * durationMinute],
    [minute, 15, 15 * durationMinute],
    [minute, 30, 30 * durationMinute],
    [hour, 1, durationHour],
    [hour, 3, 3 * durationHour],
    [hour, 6, 6 * durationHour],
    [hour, 12, 12 * durationHour],
    [day, 1, durationDay],
    [day, 2, 2 * durationDay],
    [week, 1, durationWeek],
    [month, 1, durationMonth],
    [month, 3, 3 * durationMonth],
    [year, 1, durationYear]
  ];
  function ticks2(start, stop, count3) {
    const reverse2 = stop < start;
    if (reverse2) [start, stop] = [stop, start];
    const interval = count3 && typeof count3.range === "function" ? count3 : tickInterval(start, stop, count3);
    const ticks3 = interval ? interval.range(start, +stop + 1) : [];
    return reverse2 ? ticks3.reverse() : ticks3;
  }
  function tickInterval(start, stop, count3) {
    const target = Math.abs(stop - start) / count3;
    const i = bisector(([, , step2]) => step2).right(tickIntervals, target);
    if (i === tickIntervals.length) return year.every(tickStep(start / durationYear, stop / durationYear, count3));
    if (i === 0) return millisecond.every(Math.max(tickStep(start, stop, count3), 1));
    const [t, step] = tickIntervals[target / tickIntervals[i - 1][2] < tickIntervals[i][2] / target ? i - 1 : i];
    return t.every(step);
  }
  return [ticks2, tickInterval];
}
var [utcTicks, utcTickInterval] = ticker(utcYear, utcMonth, utcSunday, unixDay, utcHour, utcMinute);
var [timeTicks, timeTickInterval] = ticker(timeYear, timeMonth, timeSunday, timeDay, timeHour, timeMinute);

// node_modules/d3-time-format/src/locale.js
function localDate(d) {
  if (0 <= d.y && d.y < 100) {
    var date2 = new Date(-1, d.m, d.d, d.H, d.M, d.S, d.L);
    date2.setFullYear(d.y);
    return date2;
  }
  return new Date(d.y, d.m, d.d, d.H, d.M, d.S, d.L);
}
function utcDate(d) {
  if (0 <= d.y && d.y < 100) {
    var date2 = new Date(Date.UTC(-1, d.m, d.d, d.H, d.M, d.S, d.L));
    date2.setUTCFullYear(d.y);
    return date2;
  }
  return new Date(Date.UTC(d.y, d.m, d.d, d.H, d.M, d.S, d.L));
}
function newDate(y4, m3, d) {
  return { y: y4, m: m3, d, H: 0, M: 0, S: 0, L: 0 };
}
function formatLocale(locale3) {
  var locale_dateTime = locale3.dateTime, locale_date = locale3.date, locale_time = locale3.time, locale_periods = locale3.periods, locale_weekdays = locale3.days, locale_shortWeekdays = locale3.shortDays, locale_months = locale3.months, locale_shortMonths = locale3.shortMonths;
  var periodRe = formatRe(locale_periods), periodLookup = formatLookup(locale_periods), weekdayRe = formatRe(locale_weekdays), weekdayLookup = formatLookup(locale_weekdays), shortWeekdayRe = formatRe(locale_shortWeekdays), shortWeekdayLookup = formatLookup(locale_shortWeekdays), monthRe = formatRe(locale_months), monthLookup = formatLookup(locale_months), shortMonthRe = formatRe(locale_shortMonths), shortMonthLookup = formatLookup(locale_shortMonths);
  var formats = {
    "a": formatShortWeekday,
    "A": formatWeekday,
    "b": formatShortMonth,
    "B": formatMonth,
    "c": null,
    "d": formatDayOfMonth,
    "e": formatDayOfMonth,
    "f": formatMicroseconds,
    "g": formatYearISO,
    "G": formatFullYearISO,
    "H": formatHour24,
    "I": formatHour12,
    "j": formatDayOfYear,
    "L": formatMilliseconds,
    "m": formatMonthNumber,
    "M": formatMinutes,
    "p": formatPeriod,
    "q": formatQuarter,
    "Q": formatUnixTimestamp,
    "s": formatUnixTimestampSeconds,
    "S": formatSeconds,
    "u": formatWeekdayNumberMonday,
    "U": formatWeekNumberSunday,
    "V": formatWeekNumberISO,
    "w": formatWeekdayNumberSunday,
    "W": formatWeekNumberMonday,
    "x": null,
    "X": null,
    "y": formatYear2,
    "Y": formatFullYear,
    "Z": formatZone,
    "%": formatLiteralPercent
  };
  var utcFormats = {
    "a": formatUTCShortWeekday,
    "A": formatUTCWeekday,
    "b": formatUTCShortMonth,
    "B": formatUTCMonth,
    "c": null,
    "d": formatUTCDayOfMonth,
    "e": formatUTCDayOfMonth,
    "f": formatUTCMicroseconds,
    "g": formatUTCYearISO,
    "G": formatUTCFullYearISO,
    "H": formatUTCHour24,
    "I": formatUTCHour12,
    "j": formatUTCDayOfYear,
    "L": formatUTCMilliseconds,
    "m": formatUTCMonthNumber,
    "M": formatUTCMinutes,
    "p": formatUTCPeriod,
    "q": formatUTCQuarter,
    "Q": formatUnixTimestamp,
    "s": formatUnixTimestampSeconds,
    "S": formatUTCSeconds,
    "u": formatUTCWeekdayNumberMonday,
    "U": formatUTCWeekNumberSunday,
    "V": formatUTCWeekNumberISO,
    "w": formatUTCWeekdayNumberSunday,
    "W": formatUTCWeekNumberMonday,
    "x": null,
    "X": null,
    "y": formatUTCYear,
    "Y": formatUTCFullYear,
    "Z": formatUTCZone,
    "%": formatLiteralPercent
  };
  var parses = {
    "a": parseShortWeekday,
    "A": parseWeekday,
    "b": parseShortMonth,
    "B": parseMonth,
    "c": parseLocaleDateTime,
    "d": parseDayOfMonth,
    "e": parseDayOfMonth,
    "f": parseMicroseconds,
    "g": parseYear,
    "G": parseFullYear,
    "H": parseHour24,
    "I": parseHour24,
    "j": parseDayOfYear,
    "L": parseMilliseconds,
    "m": parseMonthNumber,
    "M": parseMinutes,
    "p": parsePeriod,
    "q": parseQuarter,
    "Q": parseUnixTimestamp,
    "s": parseUnixTimestampSeconds,
    "S": parseSeconds,
    "u": parseWeekdayNumberMonday,
    "U": parseWeekNumberSunday,
    "V": parseWeekNumberISO,
    "w": parseWeekdayNumberSunday,
    "W": parseWeekNumberMonday,
    "x": parseLocaleDate,
    "X": parseLocaleTime,
    "y": parseYear,
    "Y": parseFullYear,
    "Z": parseZone,
    "%": parseLiteralPercent
  };
  formats.x = newFormat(locale_date, formats);
  formats.X = newFormat(locale_time, formats);
  formats.c = newFormat(locale_dateTime, formats);
  utcFormats.x = newFormat(locale_date, utcFormats);
  utcFormats.X = newFormat(locale_time, utcFormats);
  utcFormats.c = newFormat(locale_dateTime, utcFormats);
  function newFormat(specifier, formats2) {
    return function(date2) {
      var string = [], i = -1, j = 0, n = specifier.length, c6, pad3, format2;
      if (!(date2 instanceof Date)) date2 = /* @__PURE__ */ new Date(+date2);
      while (++i < n) {
        if (specifier.charCodeAt(i) === 37) {
          string.push(specifier.slice(j, i));
          if ((pad3 = pads[c6 = specifier.charAt(++i)]) != null) c6 = specifier.charAt(++i);
          else pad3 = c6 === "e" ? " " : "0";
          if (format2 = formats2[c6]) c6 = format2(date2, pad3);
          string.push(c6);
          j = i + 1;
        }
      }
      string.push(specifier.slice(j, i));
      return string.join("");
    };
  }
  function newParse(specifier, Z) {
    return function(string) {
      var d = newDate(1900, void 0, 1), i = parseSpecifier(d, specifier, string += "", 0), week, day;
      if (i != string.length) return null;
      if ("Q" in d) return new Date(d.Q);
      if ("s" in d) return new Date(d.s * 1e3 + ("L" in d ? d.L : 0));
      if (Z && !("Z" in d)) d.Z = 0;
      if ("p" in d) d.H = d.H % 12 + d.p * 12;
      if (d.m === void 0) d.m = "q" in d ? d.q : 0;
      if ("V" in d) {
        if (d.V < 1 || d.V > 53) return null;
        if (!("w" in d)) d.w = 1;
        if ("Z" in d) {
          week = utcDate(newDate(d.y, 0, 1)), day = week.getUTCDay();
          week = day > 4 || day === 0 ? utcMonday.ceil(week) : utcMonday(week);
          week = utcDay.offset(week, (d.V - 1) * 7);
          d.y = week.getUTCFullYear();
          d.m = week.getUTCMonth();
          d.d = week.getUTCDate() + (d.w + 6) % 7;
        } else {
          week = localDate(newDate(d.y, 0, 1)), day = week.getDay();
          week = day > 4 || day === 0 ? timeMonday.ceil(week) : timeMonday(week);
          week = timeDay.offset(week, (d.V - 1) * 7);
          d.y = week.getFullYear();
          d.m = week.getMonth();
          d.d = week.getDate() + (d.w + 6) % 7;
        }
      } else if ("W" in d || "U" in d) {
        if (!("w" in d)) d.w = "u" in d ? d.u % 7 : "W" in d ? 1 : 0;
        day = "Z" in d ? utcDate(newDate(d.y, 0, 1)).getUTCDay() : localDate(newDate(d.y, 0, 1)).getDay();
        d.m = 0;
        d.d = "W" in d ? (d.w + 6) % 7 + d.W * 7 - (day + 5) % 7 : d.w + d.U * 7 - (day + 6) % 7;
      }
      if ("Z" in d) {
        d.H += d.Z / 100 | 0;
        d.M += d.Z % 100;
        return utcDate(d);
      }
      return localDate(d);
    };
  }
  function parseSpecifier(d, specifier, string, j) {
    var i = 0, n = specifier.length, m3 = string.length, c6, parse;
    while (i < n) {
      if (j >= m3) return -1;
      c6 = specifier.charCodeAt(i++);
      if (c6 === 37) {
        c6 = specifier.charAt(i++);
        parse = parses[c6 in pads ? specifier.charAt(i++) : c6];
        if (!parse || (j = parse(d, string, j)) < 0) return -1;
      } else if (c6 != string.charCodeAt(j++)) {
        return -1;
      }
    }
    return j;
  }
  function parsePeriod(d, string, i) {
    var n = periodRe.exec(string.slice(i));
    return n ? (d.p = periodLookup.get(n[0].toLowerCase()), i + n[0].length) : -1;
  }
  function parseShortWeekday(d, string, i) {
    var n = shortWeekdayRe.exec(string.slice(i));
    return n ? (d.w = shortWeekdayLookup.get(n[0].toLowerCase()), i + n[0].length) : -1;
  }
  function parseWeekday(d, string, i) {
    var n = weekdayRe.exec(string.slice(i));
    return n ? (d.w = weekdayLookup.get(n[0].toLowerCase()), i + n[0].length) : -1;
  }
  function parseShortMonth(d, string, i) {
    var n = shortMonthRe.exec(string.slice(i));
    return n ? (d.m = shortMonthLookup.get(n[0].toLowerCase()), i + n[0].length) : -1;
  }
  function parseMonth(d, string, i) {
    var n = monthRe.exec(string.slice(i));
    return n ? (d.m = monthLookup.get(n[0].toLowerCase()), i + n[0].length) : -1;
  }
  function parseLocaleDateTime(d, string, i) {
    return parseSpecifier(d, locale_dateTime, string, i);
  }
  function parseLocaleDate(d, string, i) {
    return parseSpecifier(d, locale_date, string, i);
  }
  function parseLocaleTime(d, string, i) {
    return parseSpecifier(d, locale_time, string, i);
  }
  function formatShortWeekday(d) {
    return locale_shortWeekdays[d.getDay()];
  }
  function formatWeekday(d) {
    return locale_weekdays[d.getDay()];
  }
  function formatShortMonth(d) {
    return locale_shortMonths[d.getMonth()];
  }
  function formatMonth(d) {
    return locale_months[d.getMonth()];
  }
  function formatPeriod(d) {
    return locale_periods[+(d.getHours() >= 12)];
  }
  function formatQuarter(d) {
    return 1 + ~~(d.getMonth() / 3);
  }
  function formatUTCShortWeekday(d) {
    return locale_shortWeekdays[d.getUTCDay()];
  }
  function formatUTCWeekday(d) {
    return locale_weekdays[d.getUTCDay()];
  }
  function formatUTCShortMonth(d) {
    return locale_shortMonths[d.getUTCMonth()];
  }
  function formatUTCMonth(d) {
    return locale_months[d.getUTCMonth()];
  }
  function formatUTCPeriod(d) {
    return locale_periods[+(d.getUTCHours() >= 12)];
  }
  function formatUTCQuarter(d) {
    return 1 + ~~(d.getUTCMonth() / 3);
  }
  return {
    format: function(specifier) {
      var f = newFormat(specifier += "", formats);
      f.toString = function() {
        return specifier;
      };
      return f;
    },
    parse: function(specifier) {
      var p = newParse(specifier += "", false);
      p.toString = function() {
        return specifier;
      };
      return p;
    },
    utcFormat: function(specifier) {
      var f = newFormat(specifier += "", utcFormats);
      f.toString = function() {
        return specifier;
      };
      return f;
    },
    utcParse: function(specifier) {
      var p = newParse(specifier += "", true);
      p.toString = function() {
        return specifier;
      };
      return p;
    }
  };
}
var pads = { "-": "", "_": " ", "0": "0" };
var numberRe = /^\s*\d+/;
var percentRe = /^%/;
var requoteRe = /[\\^$*+?|[\]().{}]/g;
function pad2(value, fill, width) {
  var sign3 = value < 0 ? "-" : "", string = (sign3 ? -value : value) + "", length3 = string.length;
  return sign3 + (length3 < width ? new Array(width - length3 + 1).join(fill) + string : string);
}
function requote(s2) {
  return s2.replace(requoteRe, "\\$&");
}
function formatRe(names) {
  return new RegExp("^(?:" + names.map(requote).join("|") + ")", "i");
}
function formatLookup(names) {
  return new Map(names.map((name, i) => [name.toLowerCase(), i]));
}
function parseWeekdayNumberSunday(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 1));
  return n ? (d.w = +n[0], i + n[0].length) : -1;
}
function parseWeekdayNumberMonday(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 1));
  return n ? (d.u = +n[0], i + n[0].length) : -1;
}
function parseWeekNumberSunday(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.U = +n[0], i + n[0].length) : -1;
}
function parseWeekNumberISO(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.V = +n[0], i + n[0].length) : -1;
}
function parseWeekNumberMonday(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.W = +n[0], i + n[0].length) : -1;
}
function parseFullYear(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 4));
  return n ? (d.y = +n[0], i + n[0].length) : -1;
}
function parseYear(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.y = +n[0] + (+n[0] > 68 ? 1900 : 2e3), i + n[0].length) : -1;
}
function parseZone(d, string, i) {
  var n = /^(Z)|([+-]\d\d)(?::?(\d\d))?/.exec(string.slice(i, i + 6));
  return n ? (d.Z = n[1] ? 0 : -(n[2] + (n[3] || "00")), i + n[0].length) : -1;
}
function parseQuarter(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 1));
  return n ? (d.q = n[0] * 3 - 3, i + n[0].length) : -1;
}
function parseMonthNumber(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.m = n[0] - 1, i + n[0].length) : -1;
}
function parseDayOfMonth(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.d = +n[0], i + n[0].length) : -1;
}
function parseDayOfYear(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 3));
  return n ? (d.m = 0, d.d = +n[0], i + n[0].length) : -1;
}
function parseHour24(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.H = +n[0], i + n[0].length) : -1;
}
function parseMinutes(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.M = +n[0], i + n[0].length) : -1;
}
function parseSeconds(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 2));
  return n ? (d.S = +n[0], i + n[0].length) : -1;
}
function parseMilliseconds(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 3));
  return n ? (d.L = +n[0], i + n[0].length) : -1;
}
function parseMicroseconds(d, string, i) {
  var n = numberRe.exec(string.slice(i, i + 6));
  return n ? (d.L = Math.floor(n[0] / 1e3), i + n[0].length) : -1;
}
function parseLiteralPercent(d, string, i) {
  var n = percentRe.exec(string.slice(i, i + 1));
  return n ? i + n[0].length : -1;
}
function parseUnixTimestamp(d, string, i) {
  var n = numberRe.exec(string.slice(i));
  return n ? (d.Q = +n[0], i + n[0].length) : -1;
}
function parseUnixTimestampSeconds(d, string, i) {
  var n = numberRe.exec(string.slice(i));
  return n ? (d.s = +n[0], i + n[0].length) : -1;
}
function formatDayOfMonth(d, p) {
  return pad2(d.getDate(), p, 2);
}
function formatHour24(d, p) {
  return pad2(d.getHours(), p, 2);
}
function formatHour12(d, p) {
  return pad2(d.getHours() % 12 || 12, p, 2);
}
function formatDayOfYear(d, p) {
  return pad2(1 + timeDay.count(timeYear(d), d), p, 3);
}
function formatMilliseconds(d, p) {
  return pad2(d.getMilliseconds(), p, 3);
}
function formatMicroseconds(d, p) {
  return formatMilliseconds(d, p) + "000";
}
function formatMonthNumber(d, p) {
  return pad2(d.getMonth() + 1, p, 2);
}
function formatMinutes(d, p) {
  return pad2(d.getMinutes(), p, 2);
}
function formatSeconds(d, p) {
  return pad2(d.getSeconds(), p, 2);
}
function formatWeekdayNumberMonday(d) {
  var day = d.getDay();
  return day === 0 ? 7 : day;
}
function formatWeekNumberSunday(d, p) {
  return pad2(timeSunday.count(timeYear(d) - 1, d), p, 2);
}
function dISO(d) {
  var day = d.getDay();
  return day >= 4 || day === 0 ? timeThursday(d) : timeThursday.ceil(d);
}
function formatWeekNumberISO(d, p) {
  d = dISO(d);
  return pad2(timeThursday.count(timeYear(d), d) + (timeYear(d).getDay() === 4), p, 2);
}
function formatWeekdayNumberSunday(d) {
  return d.getDay();
}
function formatWeekNumberMonday(d, p) {
  return pad2(timeMonday.count(timeYear(d) - 1, d), p, 2);
}
function formatYear2(d, p) {
  return pad2(d.getFullYear() % 100, p, 2);
}
function formatYearISO(d, p) {
  d = dISO(d);
  return pad2(d.getFullYear() % 100, p, 2);
}
function formatFullYear(d, p) {
  return pad2(d.getFullYear() % 1e4, p, 4);
}
function formatFullYearISO(d, p) {
  var day = d.getDay();
  d = day >= 4 || day === 0 ? timeThursday(d) : timeThursday.ceil(d);
  return pad2(d.getFullYear() % 1e4, p, 4);
}
function formatZone(d) {
  var z = d.getTimezoneOffset();
  return (z > 0 ? "-" : (z *= -1, "+")) + pad2(z / 60 | 0, "0", 2) + pad2(z % 60, "0", 2);
}
function formatUTCDayOfMonth(d, p) {
  return pad2(d.getUTCDate(), p, 2);
}
function formatUTCHour24(d, p) {
  return pad2(d.getUTCHours(), p, 2);
}
function formatUTCHour12(d, p) {
  return pad2(d.getUTCHours() % 12 || 12, p, 2);
}
function formatUTCDayOfYear(d, p) {
  return pad2(1 + utcDay.count(utcYear(d), d), p, 3);
}
function formatUTCMilliseconds(d, p) {
  return pad2(d.getUTCMilliseconds(), p, 3);
}
function formatUTCMicroseconds(d, p) {
  return formatUTCMilliseconds(d, p) + "000";
}
function formatUTCMonthNumber(d, p) {
  return pad2(d.getUTCMonth() + 1, p, 2);
}
function formatUTCMinutes(d, p) {
  return pad2(d.getUTCMinutes(), p, 2);
}
function formatUTCSeconds(d, p) {
  return pad2(d.getUTCSeconds(), p, 2);
}
function formatUTCWeekdayNumberMonday(d) {
  var dow = d.getUTCDay();
  return dow === 0 ? 7 : dow;
}
function formatUTCWeekNumberSunday(d, p) {
  return pad2(utcSunday.count(utcYear(d) - 1, d), p, 2);
}
function UTCdISO(d) {
  var day = d.getUTCDay();
  return day >= 4 || day === 0 ? utcThursday(d) : utcThursday.ceil(d);
}
function formatUTCWeekNumberISO(d, p) {
  d = UTCdISO(d);
  return pad2(utcThursday.count(utcYear(d), d) + (utcYear(d).getUTCDay() === 4), p, 2);
}
function formatUTCWeekdayNumberSunday(d) {
  return d.getUTCDay();
}
function formatUTCWeekNumberMonday(d, p) {
  return pad2(utcMonday.count(utcYear(d) - 1, d), p, 2);
}
function formatUTCYear(d, p) {
  return pad2(d.getUTCFullYear() % 100, p, 2);
}
function formatUTCYearISO(d, p) {
  d = UTCdISO(d);
  return pad2(d.getUTCFullYear() % 100, p, 2);
}
function formatUTCFullYear(d, p) {
  return pad2(d.getUTCFullYear() % 1e4, p, 4);
}
function formatUTCFullYearISO(d, p) {
  var day = d.getUTCDay();
  d = day >= 4 || day === 0 ? utcThursday(d) : utcThursday.ceil(d);
  return pad2(d.getUTCFullYear() % 1e4, p, 4);
}
function formatUTCZone() {
  return "+0000";
}
function formatLiteralPercent() {
  return "%";
}
function formatUnixTimestamp(d) {
  return +d;
}
function formatUnixTimestampSeconds(d) {
  return Math.floor(+d / 1e3);
}

// node_modules/d3-time-format/src/defaultLocale.js
var locale2;
var timeFormat;
var timeParse;
var utcFormat;
var utcParse;
defaultLocale2({
  dateTime: "%x, %X",
  date: "%-m/%-d/%Y",
  time: "%-I:%M:%S %p",
  periods: ["AM", "PM"],
  days: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
  shortDays: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
  months: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  shortMonths: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
});
function defaultLocale2(definition) {
  locale2 = formatLocale(definition);
  timeFormat = locale2.format;
  timeParse = locale2.parse;
  utcFormat = locale2.utcFormat;
  utcParse = locale2.utcParse;
  return locale2;
}

// node_modules/d3-time-format/src/isoFormat.js
var isoSpecifier = "%Y-%m-%dT%H:%M:%S.%LZ";
function formatIsoNative(date2) {
  return date2.toISOString();
}
var formatIso = Date.prototype.toISOString ? formatIsoNative : utcFormat(isoSpecifier);
var isoFormat_default = formatIso;

// node_modules/d3-time-format/src/isoParse.js
function parseIsoNative(string) {
  var date2 = new Date(string);
  return isNaN(date2) ? null : date2;
}
var parseIso = +/* @__PURE__ */ new Date("2000-01-01T00:00:00.000Z") ? parseIsoNative : utcParse(isoSpecifier);
var isoParse_default = parseIso;

// node_modules/d3-scale/src/time.js
function date(t) {
  return new Date(t);
}
function number4(t) {
  return t instanceof Date ? +t : +/* @__PURE__ */ new Date(+t);
}
function calendar(ticks2, tickInterval, year, month, week, day, hour, minute, second2, format2) {
  var scale2 = continuous(), invert = scale2.invert, domain = scale2.domain;
  var formatMillisecond = format2(".%L"), formatSecond = format2(":%S"), formatMinute = format2("%I:%M"), formatHour = format2("%I %p"), formatDay = format2("%a %d"), formatWeek = format2("%b %d"), formatMonth = format2("%B"), formatYear3 = format2("%Y");
  function tickFormat2(date2) {
    return (second2(date2) < date2 ? formatMillisecond : minute(date2) < date2 ? formatSecond : hour(date2) < date2 ? formatMinute : day(date2) < date2 ? formatHour : month(date2) < date2 ? week(date2) < date2 ? formatDay : formatWeek : year(date2) < date2 ? formatMonth : formatYear3)(date2);
  }
  scale2.invert = function(y4) {
    return new Date(invert(y4));
  };
  scale2.domain = function(_) {
    return arguments.length ? domain(Array.from(_, number4)) : domain().map(date);
  };
  scale2.ticks = function(interval) {
    var d = domain();
    return ticks2(d[0], d[d.length - 1], interval == null ? 10 : interval);
  };
  scale2.tickFormat = function(count3, specifier) {
    return specifier == null ? tickFormat2 : format2(specifier);
  };
  scale2.nice = function(interval) {
    var d = domain();
    if (!interval || typeof interval.range !== "function") interval = tickInterval(d[0], d[d.length - 1], interval == null ? 10 : interval);
    return interval ? domain(nice2(d, interval)) : scale2;
  };
  scale2.copy = function() {
    return copy(scale2, calendar(ticks2, tickInterval, year, month, week, day, hour, minute, second2, format2));
  };
  return scale2;
}
function time() {
  return initRange.apply(calendar(timeTicks, timeTickInterval, timeYear, timeMonth, timeSunday, timeDay, timeHour, timeMinute, second, timeFormat).domain([new Date(2e3, 0, 1), new Date(2e3, 0, 2)]), arguments);
}

// node_modules/d3-scale/src/utcTime.js
function utcTime() {
  return initRange.apply(calendar(utcTicks, utcTickInterval, utcYear, utcMonth, utcSunday, utcDay, utcHour, utcMinute, second, utcFormat).domain([Date.UTC(2e3, 0, 1), Date.UTC(2e3, 0, 2)]), arguments);
}

// node_modules/d3-scale/src/sequential.js
function transformer3() {
  var x06 = 0, x12 = 1, t02, t12, k10, transform2, interpolator = identity3, clamp = false, unknown;
  function scale2(x4) {
    return x4 == null || isNaN(x4 = +x4) ? unknown : interpolator(k10 === 0 ? 0.5 : (x4 = (transform2(x4) - t02) * k10, clamp ? Math.max(0, Math.min(1, x4)) : x4));
  }
  scale2.domain = function(_) {
    return arguments.length ? ([x06, x12] = _, t02 = transform2(x06 = +x06), t12 = transform2(x12 = +x12), k10 = t02 === t12 ? 0 : 1 / (t12 - t02), scale2) : [x06, x12];
  };
  scale2.clamp = function(_) {
    return arguments.length ? (clamp = !!_, scale2) : clamp;
  };
  scale2.interpolator = function(_) {
    return arguments.length ? (interpolator = _, scale2) : interpolator;
  };
  function range4(interpolate) {
    return function(_) {
      var r0, r1;
      return arguments.length ? ([r0, r1] = _, interpolator = interpolate(r0, r1), scale2) : [interpolator(0), interpolator(1)];
    };
  }
  scale2.range = range4(value_default);
  scale2.rangeRound = range4(round_default);
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : unknown;
  };
  return function(t) {
    transform2 = t, t02 = t(x06), t12 = t(x12), k10 = t02 === t12 ? 0 : 1 / (t12 - t02);
    return scale2;
  };
}
function copy2(source, target) {
  return target.domain(source.domain()).interpolator(source.interpolator()).clamp(source.clamp()).unknown(source.unknown());
}
function sequential() {
  var scale2 = linearish(transformer3()(identity3));
  scale2.copy = function() {
    return copy2(scale2, sequential());
  };
  return initInterpolator.apply(scale2, arguments);
}
function sequentialLog() {
  var scale2 = loggish(transformer3()).domain([1, 10]);
  scale2.copy = function() {
    return copy2(scale2, sequentialLog()).base(scale2.base());
  };
  return initInterpolator.apply(scale2, arguments);
}
function sequentialSymlog() {
  var scale2 = symlogish(transformer3());
  scale2.copy = function() {
    return copy2(scale2, sequentialSymlog()).constant(scale2.constant());
  };
  return initInterpolator.apply(scale2, arguments);
}
function sequentialPow() {
  var scale2 = powish(transformer3());
  scale2.copy = function() {
    return copy2(scale2, sequentialPow()).exponent(scale2.exponent());
  };
  return initInterpolator.apply(scale2, arguments);
}
function sequentialSqrt() {
  return sequentialPow.apply(null, arguments).exponent(0.5);
}

// node_modules/d3-scale/src/sequentialQuantile.js
function sequentialQuantile() {
  var domain = [], interpolator = identity3;
  function scale2(x4) {
    if (x4 != null && !isNaN(x4 = +x4)) return interpolator((bisect_default(domain, x4, 1) - 1) / (domain.length - 1));
  }
  scale2.domain = function(_) {
    if (!arguments.length) return domain.slice();
    domain = [];
    for (let d of _) if (d != null && !isNaN(d = +d)) domain.push(d);
    domain.sort(ascending);
    return scale2;
  };
  scale2.interpolator = function(_) {
    return arguments.length ? (interpolator = _, scale2) : interpolator;
  };
  scale2.range = function() {
    return domain.map((d, i) => interpolator(i / (domain.length - 1)));
  };
  scale2.quantiles = function(n) {
    return Array.from({ length: n + 1 }, (_, i) => quantile(domain, i / n));
  };
  scale2.copy = function() {
    return sequentialQuantile(interpolator).domain(domain);
  };
  return initInterpolator.apply(scale2, arguments);
}

// node_modules/d3-scale/src/diverging.js
function transformer4() {
  var x06 = 0, x12 = 0.5, x22 = 1, s2 = 1, t02, t12, t2, k10, k21, interpolator = identity3, transform2, clamp = false, unknown;
  function scale2(x4) {
    return isNaN(x4 = +x4) ? unknown : (x4 = 0.5 + ((x4 = +transform2(x4)) - t12) * (s2 * x4 < s2 * t12 ? k10 : k21), interpolator(clamp ? Math.max(0, Math.min(1, x4)) : x4));
  }
  scale2.domain = function(_) {
    return arguments.length ? ([x06, x12, x22] = _, t02 = transform2(x06 = +x06), t12 = transform2(x12 = +x12), t2 = transform2(x22 = +x22), k10 = t02 === t12 ? 0 : 0.5 / (t12 - t02), k21 = t12 === t2 ? 0 : 0.5 / (t2 - t12), s2 = t12 < t02 ? -1 : 1, scale2) : [x06, x12, x22];
  };
  scale2.clamp = function(_) {
    return arguments.length ? (clamp = !!_, scale2) : clamp;
  };
  scale2.interpolator = function(_) {
    return arguments.length ? (interpolator = _, scale2) : interpolator;
  };
  function range4(interpolate) {
    return function(_) {
      var r0, r1, r2;
      return arguments.length ? ([r0, r1, r2] = _, interpolator = piecewise(interpolate, [r0, r1, r2]), scale2) : [interpolator(0), interpolator(0.5), interpolator(1)];
    };
  }
  scale2.range = range4(value_default);
  scale2.rangeRound = range4(round_default);
  scale2.unknown = function(_) {
    return arguments.length ? (unknown = _, scale2) : unknown;
  };
  return function(t) {
    transform2 = t, t02 = t(x06), t12 = t(x12), t2 = t(x22), k10 = t02 === t12 ? 0 : 0.5 / (t12 - t02), k21 = t12 === t2 ? 0 : 0.5 / (t2 - t12), s2 = t12 < t02 ? -1 : 1;
    return scale2;
  };
}
function diverging() {
  var scale2 = linearish(transformer4()(identity3));
  scale2.copy = function() {
    return copy2(scale2, diverging());
  };
  return initInterpolator.apply(scale2, arguments);
}
function divergingLog() {
  var scale2 = loggish(transformer4()).domain([0.1, 1, 10]);
  scale2.copy = function() {
    return copy2(scale2, divergingLog()).base(scale2.base());
  };
  return initInterpolator.apply(scale2, arguments);
}
function divergingSymlog() {
  var scale2 = symlogish(transformer4());
  scale2.copy = function() {
    return copy2(scale2, divergingSymlog()).constant(scale2.constant());
  };
  return initInterpolator.apply(scale2, arguments);
}
function divergingPow() {
  var scale2 = powish(transformer4());
  scale2.copy = function() {
    return copy2(scale2, divergingPow()).exponent(scale2.exponent());
  };
  return initInterpolator.apply(scale2, arguments);
}
function divergingSqrt() {
  return divergingPow.apply(null, arguments).exponent(0.5);
}

// node_modules/d3-scale-chromatic/src/colors.js
function colors_default(specifier) {
  var n = specifier.length / 6 | 0, colors = new Array(n), i = 0;
  while (i < n) colors[i] = "#" + specifier.slice(i * 6, ++i * 6);
  return colors;
}

// node_modules/d3-scale-chromatic/src/categorical/category10.js
var category10_default = colors_default("1f77b4ff7f0e2ca02cd627289467bd8c564be377c27f7f7fbcbd2217becf");

// node_modules/d3-scale-chromatic/src/categorical/Accent.js
var Accent_default = colors_default("7fc97fbeaed4fdc086ffff99386cb0f0027fbf5b17666666");

// node_modules/d3-scale-chromatic/src/categorical/Dark2.js
var Dark2_default = colors_default("1b9e77d95f027570b3e7298a66a61ee6ab02a6761d666666");

// node_modules/d3-scale-chromatic/src/categorical/observable10.js
var observable10_default = colors_default("4269d0efb118ff725c6cc5b03ca951ff8ab7a463f297bbf59c6b4e9498a0");

// node_modules/d3-scale-chromatic/src/categorical/Paired.js
var Paired_default = colors_default("a6cee31f78b4b2df8a33a02cfb9a99e31a1cfdbf6fff7f00cab2d66a3d9affff99b15928");

// node_modules/d3-scale-chromatic/src/categorical/Pastel1.js
var Pastel1_default = colors_default("fbb4aeb3cde3ccebc5decbe4fed9a6ffffcce5d8bdfddaecf2f2f2");

// node_modules/d3-scale-chromatic/src/categorical/Pastel2.js
var Pastel2_default = colors_default("b3e2cdfdcdaccbd5e8f4cae4e6f5c9fff2aef1e2cccccccc");

// node_modules/d3-scale-chromatic/src/categorical/Set1.js
var Set1_default = colors_default("e41a1c377eb84daf4a984ea3ff7f00ffff33a65628f781bf999999");

// node_modules/d3-scale-chromatic/src/categorical/Set2.js
var Set2_default = colors_default("66c2a5fc8d628da0cbe78ac3a6d854ffd92fe5c494b3b3b3");

// node_modules/d3-scale-chromatic/src/categorical/Set3.js
var Set3_default = colors_default("8dd3c7ffffb3bebadafb807280b1d3fdb462b3de69fccde5d9d9d9bc80bdccebc5ffed6f");

// node_modules/d3-scale-chromatic/src/categorical/Tableau10.js
var Tableau10_default = colors_default("4e79a7f28e2ce1575976b7b259a14fedc949af7aa1ff9da79c755fbab0ab");

// node_modules/d3-scale-chromatic/src/ramp.js
var ramp_default = (scheme28) => rgbBasis(scheme28[scheme28.length - 1]);

// node_modules/d3-scale-chromatic/src/diverging/BrBG.js
var scheme = new Array(3).concat(
  "d8b365f5f5f55ab4ac",
  "a6611adfc27d80cdc1018571",
  "a6611adfc27df5f5f580cdc1018571",
  "8c510ad8b365f6e8c3c7eae55ab4ac01665e",
  "8c510ad8b365f6e8c3f5f5f5c7eae55ab4ac01665e",
  "8c510abf812ddfc27df6e8c3c7eae580cdc135978f01665e",
  "8c510abf812ddfc27df6e8c3f5f5f5c7eae580cdc135978f01665e",
  "5430058c510abf812ddfc27df6e8c3c7eae580cdc135978f01665e003c30",
  "5430058c510abf812ddfc27df6e8c3f5f5f5c7eae580cdc135978f01665e003c30"
).map(colors_default);
var BrBG_default = ramp_default(scheme);

// node_modules/d3-scale-chromatic/src/diverging/PRGn.js
var scheme2 = new Array(3).concat(
  "af8dc3f7f7f77fbf7b",
  "7b3294c2a5cfa6dba0008837",
  "7b3294c2a5cff7f7f7a6dba0008837",
  "762a83af8dc3e7d4e8d9f0d37fbf7b1b7837",
  "762a83af8dc3e7d4e8f7f7f7d9f0d37fbf7b1b7837",
  "762a839970abc2a5cfe7d4e8d9f0d3a6dba05aae611b7837",
  "762a839970abc2a5cfe7d4e8f7f7f7d9f0d3a6dba05aae611b7837",
  "40004b762a839970abc2a5cfe7d4e8d9f0d3a6dba05aae611b783700441b",
  "40004b762a839970abc2a5cfe7d4e8f7f7f7d9f0d3a6dba05aae611b783700441b"
).map(colors_default);
var PRGn_default = ramp_default(scheme2);

// node_modules/d3-scale-chromatic/src/diverging/PiYG.js
var scheme3 = new Array(3).concat(
  "e9a3c9f7f7f7a1d76a",
  "d01c8bf1b6dab8e1864dac26",
  "d01c8bf1b6daf7f7f7b8e1864dac26",
  "c51b7de9a3c9fde0efe6f5d0a1d76a4d9221",
  "c51b7de9a3c9fde0eff7f7f7e6f5d0a1d76a4d9221",
  "c51b7dde77aef1b6dafde0efe6f5d0b8e1867fbc414d9221",
  "c51b7dde77aef1b6dafde0eff7f7f7e6f5d0b8e1867fbc414d9221",
  "8e0152c51b7dde77aef1b6dafde0efe6f5d0b8e1867fbc414d9221276419",
  "8e0152c51b7dde77aef1b6dafde0eff7f7f7e6f5d0b8e1867fbc414d9221276419"
).map(colors_default);
var PiYG_default = ramp_default(scheme3);

// node_modules/d3-scale-chromatic/src/diverging/PuOr.js
var scheme4 = new Array(3).concat(
  "998ec3f7f7f7f1a340",
  "5e3c99b2abd2fdb863e66101",
  "5e3c99b2abd2f7f7f7fdb863e66101",
  "542788998ec3d8daebfee0b6f1a340b35806",
  "542788998ec3d8daebf7f7f7fee0b6f1a340b35806",
  "5427888073acb2abd2d8daebfee0b6fdb863e08214b35806",
  "5427888073acb2abd2d8daebf7f7f7fee0b6fdb863e08214b35806",
  "2d004b5427888073acb2abd2d8daebfee0b6fdb863e08214b358067f3b08",
  "2d004b5427888073acb2abd2d8daebf7f7f7fee0b6fdb863e08214b358067f3b08"
).map(colors_default);
var PuOr_default = ramp_default(scheme4);

// node_modules/d3-scale-chromatic/src/diverging/RdBu.js
var scheme5 = new Array(3).concat(
  "ef8a62f7f7f767a9cf",
  "ca0020f4a58292c5de0571b0",
  "ca0020f4a582f7f7f792c5de0571b0",
  "b2182bef8a62fddbc7d1e5f067a9cf2166ac",
  "b2182bef8a62fddbc7f7f7f7d1e5f067a9cf2166ac",
  "b2182bd6604df4a582fddbc7d1e5f092c5de4393c32166ac",
  "b2182bd6604df4a582fddbc7f7f7f7d1e5f092c5de4393c32166ac",
  "67001fb2182bd6604df4a582fddbc7d1e5f092c5de4393c32166ac053061",
  "67001fb2182bd6604df4a582fddbc7f7f7f7d1e5f092c5de4393c32166ac053061"
).map(colors_default);
var RdBu_default = ramp_default(scheme5);

// node_modules/d3-scale-chromatic/src/diverging/RdGy.js
var scheme6 = new Array(3).concat(
  "ef8a62ffffff999999",
  "ca0020f4a582bababa404040",
  "ca0020f4a582ffffffbababa404040",
  "b2182bef8a62fddbc7e0e0e09999994d4d4d",
  "b2182bef8a62fddbc7ffffffe0e0e09999994d4d4d",
  "b2182bd6604df4a582fddbc7e0e0e0bababa8787874d4d4d",
  "b2182bd6604df4a582fddbc7ffffffe0e0e0bababa8787874d4d4d",
  "67001fb2182bd6604df4a582fddbc7e0e0e0bababa8787874d4d4d1a1a1a",
  "67001fb2182bd6604df4a582fddbc7ffffffe0e0e0bababa8787874d4d4d1a1a1a"
).map(colors_default);
var RdGy_default = ramp_default(scheme6);

// node_modules/d3-scale-chromatic/src/diverging/RdYlBu.js
var scheme7 = new Array(3).concat(
  "fc8d59ffffbf91bfdb",
  "d7191cfdae61abd9e92c7bb6",
  "d7191cfdae61ffffbfabd9e92c7bb6",
  "d73027fc8d59fee090e0f3f891bfdb4575b4",
  "d73027fc8d59fee090ffffbfe0f3f891bfdb4575b4",
  "d73027f46d43fdae61fee090e0f3f8abd9e974add14575b4",
  "d73027f46d43fdae61fee090ffffbfe0f3f8abd9e974add14575b4",
  "a50026d73027f46d43fdae61fee090e0f3f8abd9e974add14575b4313695",
  "a50026d73027f46d43fdae61fee090ffffbfe0f3f8abd9e974add14575b4313695"
).map(colors_default);
var RdYlBu_default = ramp_default(scheme7);

// node_modules/d3-scale-chromatic/src/diverging/RdYlGn.js
var scheme8 = new Array(3).concat(
  "fc8d59ffffbf91cf60",
  "d7191cfdae61a6d96a1a9641",
  "d7191cfdae61ffffbfa6d96a1a9641",
  "d73027fc8d59fee08bd9ef8b91cf601a9850",
  "d73027fc8d59fee08bffffbfd9ef8b91cf601a9850",
  "d73027f46d43fdae61fee08bd9ef8ba6d96a66bd631a9850",
  "d73027f46d43fdae61fee08bffffbfd9ef8ba6d96a66bd631a9850",
  "a50026d73027f46d43fdae61fee08bd9ef8ba6d96a66bd631a9850006837",
  "a50026d73027f46d43fdae61fee08bffffbfd9ef8ba6d96a66bd631a9850006837"
).map(colors_default);
var RdYlGn_default = ramp_default(scheme8);

// node_modules/d3-scale-chromatic/src/diverging/Spectral.js
var scheme9 = new Array(3).concat(
  "fc8d59ffffbf99d594",
  "d7191cfdae61abdda42b83ba",
  "d7191cfdae61ffffbfabdda42b83ba",
  "d53e4ffc8d59fee08be6f59899d5943288bd",
  "d53e4ffc8d59fee08bffffbfe6f59899d5943288bd",
  "d53e4ff46d43fdae61fee08be6f598abdda466c2a53288bd",
  "d53e4ff46d43fdae61fee08bffffbfe6f598abdda466c2a53288bd",
  "9e0142d53e4ff46d43fdae61fee08be6f598abdda466c2a53288bd5e4fa2",
  "9e0142d53e4ff46d43fdae61fee08bffffbfe6f598abdda466c2a53288bd5e4fa2"
).map(colors_default);
var Spectral_default = ramp_default(scheme9);

// node_modules/d3-scale-chromatic/src/sequential-multi/BuGn.js
var scheme10 = new Array(3).concat(
  "e5f5f999d8c92ca25f",
  "edf8fbb2e2e266c2a4238b45",
  "edf8fbb2e2e266c2a42ca25f006d2c",
  "edf8fbccece699d8c966c2a42ca25f006d2c",
  "edf8fbccece699d8c966c2a441ae76238b45005824",
  "f7fcfde5f5f9ccece699d8c966c2a441ae76238b45005824",
  "f7fcfde5f5f9ccece699d8c966c2a441ae76238b45006d2c00441b"
).map(colors_default);
var BuGn_default = ramp_default(scheme10);

// node_modules/d3-scale-chromatic/src/sequential-multi/BuPu.js
var scheme11 = new Array(3).concat(
  "e0ecf49ebcda8856a7",
  "edf8fbb3cde38c96c688419d",
  "edf8fbb3cde38c96c68856a7810f7c",
  "edf8fbbfd3e69ebcda8c96c68856a7810f7c",
  "edf8fbbfd3e69ebcda8c96c68c6bb188419d6e016b",
  "f7fcfde0ecf4bfd3e69ebcda8c96c68c6bb188419d6e016b",
  "f7fcfde0ecf4bfd3e69ebcda8c96c68c6bb188419d810f7c4d004b"
).map(colors_default);
var BuPu_default = ramp_default(scheme11);

// node_modules/d3-scale-chromatic/src/sequential-multi/GnBu.js
var scheme12 = new Array(3).concat(
  "e0f3dba8ddb543a2ca",
  "f0f9e8bae4bc7bccc42b8cbe",
  "f0f9e8bae4bc7bccc443a2ca0868ac",
  "f0f9e8ccebc5a8ddb57bccc443a2ca0868ac",
  "f0f9e8ccebc5a8ddb57bccc44eb3d32b8cbe08589e",
  "f7fcf0e0f3dbccebc5a8ddb57bccc44eb3d32b8cbe08589e",
  "f7fcf0e0f3dbccebc5a8ddb57bccc44eb3d32b8cbe0868ac084081"
).map(colors_default);
var GnBu_default = ramp_default(scheme12);

// node_modules/d3-scale-chromatic/src/sequential-multi/OrRd.js
var scheme13 = new Array(3).concat(
  "fee8c8fdbb84e34a33",
  "fef0d9fdcc8afc8d59d7301f",
  "fef0d9fdcc8afc8d59e34a33b30000",
  "fef0d9fdd49efdbb84fc8d59e34a33b30000",
  "fef0d9fdd49efdbb84fc8d59ef6548d7301f990000",
  "fff7ecfee8c8fdd49efdbb84fc8d59ef6548d7301f990000",
  "fff7ecfee8c8fdd49efdbb84fc8d59ef6548d7301fb300007f0000"
).map(colors_default);
var OrRd_default = ramp_default(scheme13);

// node_modules/d3-scale-chromatic/src/sequential-multi/PuBuGn.js
var scheme14 = new Array(3).concat(
  "ece2f0a6bddb1c9099",
  "f6eff7bdc9e167a9cf02818a",
  "f6eff7bdc9e167a9cf1c9099016c59",
  "f6eff7d0d1e6a6bddb67a9cf1c9099016c59",
  "f6eff7d0d1e6a6bddb67a9cf3690c002818a016450",
  "fff7fbece2f0d0d1e6a6bddb67a9cf3690c002818a016450",
  "fff7fbece2f0d0d1e6a6bddb67a9cf3690c002818a016c59014636"
).map(colors_default);
var PuBuGn_default = ramp_default(scheme14);

// node_modules/d3-scale-chromatic/src/sequential-multi/PuBu.js
var scheme15 = new Array(3).concat(
  "ece7f2a6bddb2b8cbe",
  "f1eef6bdc9e174a9cf0570b0",
  "f1eef6bdc9e174a9cf2b8cbe045a8d",
  "f1eef6d0d1e6a6bddb74a9cf2b8cbe045a8d",
  "f1eef6d0d1e6a6bddb74a9cf3690c00570b0034e7b",
  "fff7fbece7f2d0d1e6a6bddb74a9cf3690c00570b0034e7b",
  "fff7fbece7f2d0d1e6a6bddb74a9cf3690c00570b0045a8d023858"
).map(colors_default);
var PuBu_default = ramp_default(scheme15);

// node_modules/d3-scale-chromatic/src/sequential-multi/PuRd.js
var scheme16 = new Array(3).concat(
  "e7e1efc994c7dd1c77",
  "f1eef6d7b5d8df65b0ce1256",
  "f1eef6d7b5d8df65b0dd1c77980043",
  "f1eef6d4b9dac994c7df65b0dd1c77980043",
  "f1eef6d4b9dac994c7df65b0e7298ace125691003f",
  "f7f4f9e7e1efd4b9dac994c7df65b0e7298ace125691003f",
  "f7f4f9e7e1efd4b9dac994c7df65b0e7298ace125698004367001f"
).map(colors_default);
var PuRd_default = ramp_default(scheme16);

// node_modules/d3-scale-chromatic/src/sequential-multi/RdPu.js
var scheme17 = new Array(3).concat(
  "fde0ddfa9fb5c51b8a",
  "feebe2fbb4b9f768a1ae017e",
  "feebe2fbb4b9f768a1c51b8a7a0177",
  "feebe2fcc5c0fa9fb5f768a1c51b8a7a0177",
  "feebe2fcc5c0fa9fb5f768a1dd3497ae017e7a0177",
  "fff7f3fde0ddfcc5c0fa9fb5f768a1dd3497ae017e7a0177",
  "fff7f3fde0ddfcc5c0fa9fb5f768a1dd3497ae017e7a017749006a"
).map(colors_default);
var RdPu_default = ramp_default(scheme17);

// node_modules/d3-scale-chromatic/src/sequential-multi/YlGnBu.js
var scheme18 = new Array(3).concat(
  "edf8b17fcdbb2c7fb8",
  "ffffcca1dab441b6c4225ea8",
  "ffffcca1dab441b6c42c7fb8253494",
  "ffffccc7e9b47fcdbb41b6c42c7fb8253494",
  "ffffccc7e9b47fcdbb41b6c41d91c0225ea80c2c84",
  "ffffd9edf8b1c7e9b47fcdbb41b6c41d91c0225ea80c2c84",
  "ffffd9edf8b1c7e9b47fcdbb41b6c41d91c0225ea8253494081d58"
).map(colors_default);
var YlGnBu_default = ramp_default(scheme18);

// node_modules/d3-scale-chromatic/src/sequential-multi/YlGn.js
var scheme19 = new Array(3).concat(
  "f7fcb9addd8e31a354",
  "ffffccc2e69978c679238443",
  "ffffccc2e69978c67931a354006837",
  "ffffccd9f0a3addd8e78c67931a354006837",
  "ffffccd9f0a3addd8e78c67941ab5d238443005a32",
  "ffffe5f7fcb9d9f0a3addd8e78c67941ab5d238443005a32",
  "ffffe5f7fcb9d9f0a3addd8e78c67941ab5d238443006837004529"
).map(colors_default);
var YlGn_default = ramp_default(scheme19);

// node_modules/d3-scale-chromatic/src/sequential-multi/YlOrBr.js
var scheme20 = new Array(3).concat(
  "fff7bcfec44fd95f0e",
  "ffffd4fed98efe9929cc4c02",
  "ffffd4fed98efe9929d95f0e993404",
  "ffffd4fee391fec44ffe9929d95f0e993404",
  "ffffd4fee391fec44ffe9929ec7014cc4c028c2d04",
  "ffffe5fff7bcfee391fec44ffe9929ec7014cc4c028c2d04",
  "ffffe5fff7bcfee391fec44ffe9929ec7014cc4c02993404662506"
).map(colors_default);
var YlOrBr_default = ramp_default(scheme20);

// node_modules/d3-scale-chromatic/src/sequential-multi/YlOrRd.js
var scheme21 = new Array(3).concat(
  "ffeda0feb24cf03b20",
  "ffffb2fecc5cfd8d3ce31a1c",
  "ffffb2fecc5cfd8d3cf03b20bd0026",
  "ffffb2fed976feb24cfd8d3cf03b20bd0026",
  "ffffb2fed976feb24cfd8d3cfc4e2ae31a1cb10026",
  "ffffccffeda0fed976feb24cfd8d3cfc4e2ae31a1cb10026",
  "ffffccffeda0fed976feb24cfd8d3cfc4e2ae31a1cbd0026800026"
).map(colors_default);
var YlOrRd_default = ramp_default(scheme21);

// node_modules/d3-scale-chromatic/src/sequential-single/Blues.js
var scheme22 = new Array(3).concat(
  "deebf79ecae13182bd",
  "eff3ffbdd7e76baed62171b5",
  "eff3ffbdd7e76baed63182bd08519c",
  "eff3ffc6dbef9ecae16baed63182bd08519c",
  "eff3ffc6dbef9ecae16baed64292c62171b5084594",
  "f7fbffdeebf7c6dbef9ecae16baed64292c62171b5084594",
  "f7fbffdeebf7c6dbef9ecae16baed64292c62171b508519c08306b"
).map(colors_default);
var Blues_default = ramp_default(scheme22);

// node_modules/d3-scale-chromatic/src/sequential-single/Greens.js
var scheme23 = new Array(3).concat(
  "e5f5e0a1d99b31a354",
  "edf8e9bae4b374c476238b45",
  "edf8e9bae4b374c47631a354006d2c",
  "edf8e9c7e9c0a1d99b74c47631a354006d2c",
  "edf8e9c7e9c0a1d99b74c47641ab5d238b45005a32",
  "f7fcf5e5f5e0c7e9c0a1d99b74c47641ab5d238b45005a32",
  "f7fcf5e5f5e0c7e9c0a1d99b74c47641ab5d238b45006d2c00441b"
).map(colors_default);
var Greens_default = ramp_default(scheme23);

// node_modules/d3-scale-chromatic/src/sequential-single/Greys.js
var scheme24 = new Array(3).concat(
  "f0f0f0bdbdbd636363",
  "f7f7f7cccccc969696525252",
  "f7f7f7cccccc969696636363252525",
  "f7f7f7d9d9d9bdbdbd969696636363252525",
  "f7f7f7d9d9d9bdbdbd969696737373525252252525",
  "fffffff0f0f0d9d9d9bdbdbd969696737373525252252525",
  "fffffff0f0f0d9d9d9bdbdbd969696737373525252252525000000"
).map(colors_default);
var Greys_default = ramp_default(scheme24);

// node_modules/d3-scale-chromatic/src/sequential-single/Purples.js
var scheme25 = new Array(3).concat(
  "efedf5bcbddc756bb1",
  "f2f0f7cbc9e29e9ac86a51a3",
  "f2f0f7cbc9e29e9ac8756bb154278f",
  "f2f0f7dadaebbcbddc9e9ac8756bb154278f",
  "f2f0f7dadaebbcbddc9e9ac8807dba6a51a34a1486",
  "fcfbfdefedf5dadaebbcbddc9e9ac8807dba6a51a34a1486",
  "fcfbfdefedf5dadaebbcbddc9e9ac8807dba6a51a354278f3f007d"
).map(colors_default);
var Purples_default = ramp_default(scheme25);

// node_modules/d3-scale-chromatic/src/sequential-single/Reds.js
var scheme26 = new Array(3).concat(
  "fee0d2fc9272de2d26",
  "fee5d9fcae91fb6a4acb181d",
  "fee5d9fcae91fb6a4ade2d26a50f15",
  "fee5d9fcbba1fc9272fb6a4ade2d26a50f15",
  "fee5d9fcbba1fc9272fb6a4aef3b2ccb181d99000d",
  "fff5f0fee0d2fcbba1fc9272fb6a4aef3b2ccb181d99000d",
  "fff5f0fee0d2fcbba1fc9272fb6a4aef3b2ccb181da50f1567000d"
).map(colors_default);
var Reds_default = ramp_default(scheme26);

// node_modules/d3-scale-chromatic/src/sequential-single/Oranges.js
var scheme27 = new Array(3).concat(
  "fee6cefdae6be6550d",
  "feeddefdbe85fd8d3cd94701",
  "feeddefdbe85fd8d3ce6550da63603",
  "feeddefdd0a2fdae6bfd8d3ce6550da63603",
  "feeddefdd0a2fdae6bfd8d3cf16913d948018c2d04",
  "fff5ebfee6cefdd0a2fdae6bfd8d3cf16913d948018c2d04",
  "fff5ebfee6cefdd0a2fdae6bfd8d3cf16913d94801a636037f2704"
).map(colors_default);
var Oranges_default = ramp_default(scheme27);

// node_modules/d3-scale-chromatic/src/sequential-multi/cividis.js
function cividis_default(t) {
  t = Math.max(0, Math.min(1, t));
  return "rgb(" + Math.max(0, Math.min(255, Math.round(-4.54 - t * (35.34 - t * (2381.73 - t * (6402.7 - t * (7024.72 - t * 2710.57))))))) + ", " + Math.max(0, Math.min(255, Math.round(32.49 + t * (170.73 + t * (52.82 - t * (131.46 - t * (176.58 - t * 67.37))))))) + ", " + Math.max(0, Math.min(255, Math.round(81.24 + t * (442.36 - t * (2482.43 - t * (6167.24 - t * (6614.94 - t * 2475.67))))))) + ")";
}

// node_modules/d3-scale-chromatic/src/sequential-multi/cubehelix.js
var cubehelix_default2 = cubehelixLong(cubehelix(300, 0.5, 0), cubehelix(-240, 0.5, 1));

// node_modules/d3-scale-chromatic/src/sequential-multi/rainbow.js
var warm = cubehelixLong(cubehelix(-100, 0.75, 0.35), cubehelix(80, 1.5, 0.8));
var cool = cubehelixLong(cubehelix(260, 0.75, 0.35), cubehelix(80, 1.5, 0.8));
var c3 = cubehelix();
function rainbow_default(t) {
  if (t < 0 || t > 1) t -= Math.floor(t);
  var ts = Math.abs(t - 0.5);
  c3.h = 360 * t - 100;
  c3.s = 1.5 - 1.5 * ts;
  c3.l = 0.8 - 0.9 * ts;
  return c3 + "";
}

// node_modules/d3-scale-chromatic/src/sequential-multi/sinebow.js
var c4 = rgb();
var pi_1_3 = Math.PI / 3;
var pi_2_3 = Math.PI * 2 / 3;
function sinebow_default(t) {
  var x4;
  t = (0.5 - t) * Math.PI;
  c4.r = 255 * (x4 = Math.sin(t)) * x4;
  c4.g = 255 * (x4 = Math.sin(t + pi_1_3)) * x4;
  c4.b = 255 * (x4 = Math.sin(t + pi_2_3)) * x4;
  return c4 + "";
}

// node_modules/d3-scale-chromatic/src/sequential-multi/turbo.js
function turbo_default(t) {
  t = Math.max(0, Math.min(1, t));
  return "rgb(" + Math.max(0, Math.min(255, Math.round(34.61 + t * (1172.33 - t * (10793.56 - t * (33300.12 - t * (38394.49 - t * 14825.05))))))) + ", " + Math.max(0, Math.min(255, Math.round(23.31 + t * (557.33 + t * (1225.33 - t * (3574.96 - t * (1073.77 + t * 707.56))))))) + ", " + Math.max(0, Math.min(255, Math.round(27.2 + t * (3211.1 - t * (15327.97 - t * (27814 - t * (22569.18 - t * 6838.66))))))) + ")";
}

// node_modules/d3-scale-chromatic/src/sequential-multi/viridis.js
function ramp(range4) {
  var n = range4.length;
  return function(t) {
    return range4[Math.max(0, Math.min(n - 1, Math.floor(t * n)))];
  };
}
var viridis_default = ramp(colors_default("44015444025645045745055946075a46085c460a5d460b5e470d60470e6147106347116447136548146748166848176948186a481a6c481b6d481c6e481d6f481f70482071482173482374482475482576482677482878482979472a7a472c7a472d7b472e7c472f7d46307e46327e46337f463480453581453781453882443983443a83443b84433d84433e85423f854240864241864142874144874045884046883f47883f48893e49893e4a893e4c8a3d4d8a3d4e8a3c4f8a3c508b3b518b3b528b3a538b3a548c39558c39568c38588c38598c375a8c375b8d365c8d365d8d355e8d355f8d34608d34618d33628d33638d32648e32658e31668e31678e31688e30698e306a8e2f6b8e2f6c8e2e6d8e2e6e8e2e6f8e2d708e2d718e2c718e2c728e2c738e2b748e2b758e2a768e2a778e2a788e29798e297a8e297b8e287c8e287d8e277e8e277f8e27808e26818e26828e26828e25838e25848e25858e24868e24878e23888e23898e238a8d228b8d228c8d228d8d218e8d218f8d21908d21918c20928c20928c20938c1f948c1f958b1f968b1f978b1f988b1f998a1f9a8a1e9b8a1e9c891e9d891f9e891f9f881fa0881fa1881fa1871fa28720a38620a48621a58521a68522a78522a88423a98324aa8325ab8225ac8226ad8127ad8128ae8029af7f2ab07f2cb17e2db27d2eb37c2fb47c31b57b32b67a34b67935b77937b87838b9773aba763bbb753dbc743fbc7340bd7242be7144bf7046c06f48c16e4ac16d4cc26c4ec36b50c46a52c56954c56856c66758c7655ac8645cc8635ec96260ca6063cb5f65cb5e67cc5c69cd5b6ccd5a6ece5870cf5773d05675d05477d1537ad1517cd2507fd34e81d34d84d44b86d54989d5488bd6468ed64590d74393d74195d84098d83e9bd93c9dd93ba0da39a2da37a5db36a8db34aadc32addc30b0dd2fb2dd2db5de2bb8de29bade28bddf26c0df25c2df23c5e021c8e020cae11fcde11dd0e11cd2e21bd5e21ad8e219dae319dde318dfe318e2e418e5e419e7e419eae51aece51befe51cf1e51df4e61ef6e620f8e621fbe723fde725"));
var magma = ramp(colors_default("00000401000501010601010802010902020b02020d03030f03031204041405041606051806051a07061c08071e0907200a08220b09240c09260d0a290e0b2b100b2d110c2f120d31130d34140e36150e38160f3b180f3d19103f1a10421c10441d11471e114920114b21114e22115024125325125527125829115a2a115c2c115f2d11612f116331116533106734106936106b38106c390f6e3b0f703d0f713f0f72400f74420f75440f764510774710784910784a10794c117a4e117b4f127b51127c52137c54137d56147d57157e59157e5a167e5c167f5d177f5f187f601880621980641a80651a80671b80681c816a1c816b1d816d1d816e1e81701f81721f817320817521817621817822817922827b23827c23827e24828025828125818326818426818627818827818928818b29818c29818e2a81902a81912b81932b80942c80962c80982d80992d809b2e7f9c2e7f9e2f7fa02f7fa1307ea3307ea5317ea6317da8327daa337dab337cad347cae347bb0357bb2357bb3367ab5367ab73779b83779ba3878bc3978bd3977bf3a77c03a76c23b75c43c75c53c74c73d73c83e73ca3e72cc3f71cd4071cf4070d0416fd2426fd3436ed5446dd6456cd8456cd9466bdb476adc4869de4968df4a68e04c67e24d66e34e65e44f64e55064e75263e85362e95462ea5661eb5760ec5860ed5a5fee5b5eef5d5ef05f5ef1605df2625df2645cf3655cf4675cf4695cf56b5cf66c5cf66e5cf7705cf7725cf8745cf8765cf9785df9795df97b5dfa7d5efa7f5efa815ffb835ffb8560fb8761fc8961fc8a62fc8c63fc8e64fc9065fd9266fd9467fd9668fd9869fd9a6afd9b6bfe9d6cfe9f6dfea16efea36ffea571fea772fea973feaa74feac76feae77feb078feb27afeb47bfeb67cfeb77efeb97ffebb81febd82febf84fec185fec287fec488fec68afec88cfeca8dfecc8ffecd90fecf92fed194fed395fed597fed799fed89afdda9cfddc9efddea0fde0a1fde2a3fde3a5fde5a7fde7a9fde9aafdebacfcecaefceeb0fcf0b2fcf2b4fcf4b6fcf6b8fcf7b9fcf9bbfcfbbdfcfdbf"));
var inferno = ramp(colors_default("00000401000501010601010802010a02020c02020e03021004031204031405041706041907051b08051d09061f0a07220b07240c08260d08290e092b10092d110a30120a32140b34150b37160b39180c3c190c3e1b0c411c0c431e0c451f0c48210c4a230c4c240c4f260c51280b53290b552b0b572d0b592f0a5b310a5c320a5e340a5f3609613809623909633b09643d09653e0966400a67420a68440a68450a69470b6a490b6a4a0c6b4c0c6b4d0d6c4f0d6c510e6c520e6d540f6d550f6d57106e59106e5a116e5c126e5d126e5f136e61136e62146e64156e65156e67166e69166e6a176e6c186e6d186e6f196e71196e721a6e741a6e751b6e771c6d781c6d7a1d6d7c1d6d7d1e6d7f1e6c801f6c82206c84206b85216b87216b88226a8a226a8c23698d23698f24699025689225689326679526679727669827669a28659b29649d29649f2a63a02a63a22b62a32c61a52c60a62d60a82e5fa92e5eab2f5ead305dae305cb0315bb1325ab3325ab43359b63458b73557b93556ba3655bc3754bd3853bf3952c03a51c13a50c33b4fc43c4ec63d4dc73e4cc83f4bca404acb4149cc4248ce4347cf4446d04545d24644d34743d44842d54a41d74b3fd84c3ed94d3dda4e3cdb503bdd513ade5238df5337e05536e15635e25734e35933e45a31e55c30e65d2fe75e2ee8602de9612bea632aeb6429eb6628ec6726ed6925ee6a24ef6c23ef6e21f06f20f1711ff1731df2741cf3761bf37819f47918f57b17f57d15f67e14f68013f78212f78410f8850ff8870ef8890cf98b0bf98c0af98e09fa9008fa9207fa9407fb9606fb9706fb9906fb9b06fb9d07fc9f07fca108fca309fca50afca60cfca80dfcaa0ffcac11fcae12fcb014fcb216fcb418fbb61afbb81dfbba1ffbbc21fbbe23fac026fac228fac42afac62df9c72ff9c932f9cb35f8cd37f8cf3af7d13df7d340f6d543f6d746f5d949f5db4cf4dd4ff4df53f4e156f3e35af3e55df2e661f2e865f2ea69f1ec6df1ed71f1ef75f1f179f2f27df2f482f3f586f3f68af4f88ef5f992f6fa96f8fb9af9fc9dfafda1fcffa4"));
var plasma = ramp(colors_default("0d088710078813078916078a19068c1b068d1d068e20068f2206902406912605912805922a05932c05942e05952f059631059733059735049837049938049a3a049a3c049b3e049c3f049c41049d43039e44039e46039f48039f4903a04b03a14c02a14e02a25002a25102a35302a35502a45601a45801a45901a55b01a55c01a65e01a66001a66100a76300a76400a76600a76700a86900a86a00a86c00a86e00a86f00a87100a87201a87401a87501a87701a87801a87a02a87b02a87d03a87e03a88004a88104a78305a78405a78606a68707a68808a68a09a58b0aa58d0ba58e0ca48f0da4910ea3920fa39410a29511a19613a19814a099159f9a169f9c179e9d189d9e199da01a9ca11b9ba21d9aa31e9aa51f99a62098a72197a82296aa2395ab2494ac2694ad2793ae2892b02991b12a90b22b8fb32c8eb42e8db52f8cb6308bb7318ab83289ba3388bb3488bc3587bd3786be3885bf3984c03a83c13b82c23c81c33d80c43e7fc5407ec6417dc7427cc8437bc9447aca457acb4679cc4778cc4977cd4a76ce4b75cf4c74d04d73d14e72d24f71d35171d45270d5536fd5546ed6556dd7566cd8576bd9586ada5a6ada5b69db5c68dc5d67dd5e66de5f65de6164df6263e06363e16462e26561e26660e3685fe4695ee56a5de56b5de66c5ce76e5be76f5ae87059e97158e97257ea7457eb7556eb7655ec7754ed7953ed7a52ee7b51ef7c51ef7e50f07f4ff0804ef1814df1834cf2844bf3854bf3874af48849f48948f58b47f58c46f68d45f68f44f79044f79143f79342f89441f89540f9973ff9983ef99a3efa9b3dfa9c3cfa9e3bfb9f3afba139fba238fca338fca537fca636fca835fca934fdab33fdac33fdae32fdaf31fdb130fdb22ffdb42ffdb52efeb72dfeb82cfeba2cfebb2bfebd2afebe2afec029fdc229fdc328fdc527fdc627fdc827fdca26fdcb26fccd25fcce25fcd025fcd225fbd324fbd524fbd724fad824fada24f9dc24f9dd25f8df25f8e125f7e225f7e425f6e626f6e826f5e926f5eb27f4ed27f3ee27f3f027f2f227f1f426f1f525f0f724f0f921"));

// node_modules/d3-shape/src/constant.js
function constant_default7(x4) {
  return function constant2() {
    return x4;
  };
}

// node_modules/d3-shape/src/math.js
var abs4 = Math.abs;
var atan22 = Math.atan2;
var cos3 = Math.cos;
var max4 = Math.max;
var min3 = Math.min;
var sin3 = Math.sin;
var sqrt3 = Math.sqrt;
var epsilon7 = 1e-12;
var pi4 = Math.PI;
var halfPi3 = pi4 / 2;
var tau5 = 2 * pi4;
function acos2(x4) {
  return x4 > 1 ? 0 : x4 < -1 ? pi4 : Math.acos(x4);
}
function asin2(x4) {
  return x4 >= 1 ? halfPi3 : x4 <= -1 ? -halfPi3 : Math.asin(x4);
}

// node_modules/d3-shape/src/path.js
function withPath(shape) {
  let digits = 3;
  shape.digits = function(_) {
    if (!arguments.length) return digits;
    if (_ == null) {
      digits = null;
    } else {
      const d = Math.floor(_);
      if (!(d >= 0)) throw new RangeError(`invalid digits: ${_}`);
      digits = d;
    }
    return shape;
  };
  return () => new Path(digits);
}

// node_modules/d3-shape/src/arc.js
function arcInnerRadius(d) {
  return d.innerRadius;
}
function arcOuterRadius(d) {
  return d.outerRadius;
}
function arcStartAngle(d) {
  return d.startAngle;
}
function arcEndAngle(d) {
  return d.endAngle;
}
function arcPadAngle(d) {
  return d && d.padAngle;
}
function intersect(x06, y06, x12, y12, x22, y22, x32, y32) {
  var x10 = x12 - x06, y10 = y12 - y06, x322 = x32 - x22, y322 = y32 - y22, t = y322 * x10 - x322 * y10;
  if (t * t < epsilon7) return;
  t = (x322 * (y06 - y22) - y322 * (x06 - x22)) / t;
  return [x06 + t * x10, y06 + t * y10];
}
function cornerTangents(x06, y06, x12, y12, r1, rc, cw) {
  var x01 = x06 - x12, y01 = y06 - y12, lo = (cw ? rc : -rc) / sqrt3(x01 * x01 + y01 * y01), ox = lo * y01, oy = -lo * x01, x11 = x06 + ox, y11 = y06 + oy, x10 = x12 + ox, y10 = y12 + oy, x004 = (x11 + x10) / 2, y004 = (y11 + y10) / 2, dx = x10 - x11, dy = y10 - y11, d2 = dx * dx + dy * dy, r = r1 - rc, D2 = x11 * y10 - x10 * y11, d = (dy < 0 ? -1 : 1) * sqrt3(max4(0, r * r * d2 - D2 * D2)), cx0 = (D2 * dy - dx * d) / d2, cy0 = (-D2 * dx - dy * d) / d2, cx1 = (D2 * dy + dx * d) / d2, cy1 = (-D2 * dx + dy * d) / d2, dx0 = cx0 - x004, dy0 = cy0 - y004, dx1 = cx1 - x004, dy1 = cy1 - y004;
  if (dx0 * dx0 + dy0 * dy0 > dx1 * dx1 + dy1 * dy1) cx0 = cx1, cy0 = cy1;
  return {
    cx: cx0,
    cy: cy0,
    x01: -ox,
    y01: -oy,
    x11: cx0 * (r1 / r - 1),
    y11: cy0 * (r1 / r - 1)
  };
}
function arc_default() {
  var innerRadius = arcInnerRadius, outerRadius = arcOuterRadius, cornerRadius = constant_default7(0), padRadius = null, startAngle = arcStartAngle, endAngle = arcEndAngle, padAngle = arcPadAngle, context = null, path2 = withPath(arc);
  function arc() {
    var buffer, r, r0 = +innerRadius.apply(this, arguments), r1 = +outerRadius.apply(this, arguments), a0 = startAngle.apply(this, arguments) - halfPi3, a1 = endAngle.apply(this, arguments) - halfPi3, da2 = abs4(a1 - a0), cw = a1 > a0;
    if (!context) context = buffer = path2();
    if (r1 < r0) r = r1, r1 = r0, r0 = r;
    if (!(r1 > epsilon7)) context.moveTo(0, 0);
    else if (da2 > tau5 - epsilon7) {
      context.moveTo(r1 * cos3(a0), r1 * sin3(a0));
      context.arc(0, 0, r1, a0, a1, !cw);
      if (r0 > epsilon7) {
        context.moveTo(r0 * cos3(a1), r0 * sin3(a1));
        context.arc(0, 0, r0, a1, a0, cw);
      }
    } else {
      var a01 = a0, a11 = a1, a00 = a0, a10 = a1, da0 = da2, da1 = da2, ap = padAngle.apply(this, arguments) / 2, rp = ap > epsilon7 && (padRadius ? +padRadius.apply(this, arguments) : sqrt3(r0 * r0 + r1 * r1)), rc = min3(abs4(r1 - r0) / 2, +cornerRadius.apply(this, arguments)), rc0 = rc, rc1 = rc, t02, t12;
      if (rp > epsilon7) {
        var p02 = asin2(rp / r0 * sin3(ap)), p1 = asin2(rp / r1 * sin3(ap));
        if ((da0 -= p02 * 2) > epsilon7) p02 *= cw ? 1 : -1, a00 += p02, a10 -= p02;
        else da0 = 0, a00 = a10 = (a0 + a1) / 2;
        if ((da1 -= p1 * 2) > epsilon7) p1 *= cw ? 1 : -1, a01 += p1, a11 -= p1;
        else da1 = 0, a01 = a11 = (a0 + a1) / 2;
      }
      var x01 = r1 * cos3(a01), y01 = r1 * sin3(a01), x10 = r0 * cos3(a10), y10 = r0 * sin3(a10);
      if (rc > epsilon7) {
        var x11 = r1 * cos3(a11), y11 = r1 * sin3(a11), x004 = r0 * cos3(a00), y004 = r0 * sin3(a00), oc;
        if (da2 < pi4) {
          if (oc = intersect(x01, y01, x004, y004, x11, y11, x10, y10)) {
            var ax = x01 - oc[0], ay = y01 - oc[1], bx = x11 - oc[0], by = y11 - oc[1], kc = 1 / sin3(acos2((ax * bx + ay * by) / (sqrt3(ax * ax + ay * ay) * sqrt3(bx * bx + by * by))) / 2), lc = sqrt3(oc[0] * oc[0] + oc[1] * oc[1]);
            rc0 = min3(rc, (r0 - lc) / (kc - 1));
            rc1 = min3(rc, (r1 - lc) / (kc + 1));
          } else {
            rc0 = rc1 = 0;
          }
        }
      }
      if (!(da1 > epsilon7)) context.moveTo(x01, y01);
      else if (rc1 > epsilon7) {
        t02 = cornerTangents(x004, y004, x01, y01, r1, rc1, cw);
        t12 = cornerTangents(x11, y11, x10, y10, r1, rc1, cw);
        context.moveTo(t02.cx + t02.x01, t02.cy + t02.y01);
        if (rc1 < rc) context.arc(t02.cx, t02.cy, rc1, atan22(t02.y01, t02.x01), atan22(t12.y01, t12.x01), !cw);
        else {
          context.arc(t02.cx, t02.cy, rc1, atan22(t02.y01, t02.x01), atan22(t02.y11, t02.x11), !cw);
          context.arc(0, 0, r1, atan22(t02.cy + t02.y11, t02.cx + t02.x11), atan22(t12.cy + t12.y11, t12.cx + t12.x11), !cw);
          context.arc(t12.cx, t12.cy, rc1, atan22(t12.y11, t12.x11), atan22(t12.y01, t12.x01), !cw);
        }
      } else context.moveTo(x01, y01), context.arc(0, 0, r1, a01, a11, !cw);
      if (!(r0 > epsilon7) || !(da0 > epsilon7)) context.lineTo(x10, y10);
      else if (rc0 > epsilon7) {
        t02 = cornerTangents(x10, y10, x11, y11, r0, -rc0, cw);
        t12 = cornerTangents(x01, y01, x004, y004, r0, -rc0, cw);
        context.lineTo(t02.cx + t02.x01, t02.cy + t02.y01);
        if (rc0 < rc) context.arc(t02.cx, t02.cy, rc0, atan22(t02.y01, t02.x01), atan22(t12.y01, t12.x01), !cw);
        else {
          context.arc(t02.cx, t02.cy, rc0, atan22(t02.y01, t02.x01), atan22(t02.y11, t02.x11), !cw);
          context.arc(0, 0, r0, atan22(t02.cy + t02.y11, t02.cx + t02.x11), atan22(t12.cy + t12.y11, t12.cx + t12.x11), cw);
          context.arc(t12.cx, t12.cy, rc0, atan22(t12.y11, t12.x11), atan22(t12.y01, t12.x01), !cw);
        }
      } else context.arc(0, 0, r0, a10, a00, cw);
    }
    context.closePath();
    if (buffer) return context = null, buffer + "" || null;
  }
  arc.centroid = function() {
    var r = (+innerRadius.apply(this, arguments) + +outerRadius.apply(this, arguments)) / 2, a4 = (+startAngle.apply(this, arguments) + +endAngle.apply(this, arguments)) / 2 - pi4 / 2;
    return [cos3(a4) * r, sin3(a4) * r];
  };
  arc.innerRadius = function(_) {
    return arguments.length ? (innerRadius = typeof _ === "function" ? _ : constant_default7(+_), arc) : innerRadius;
  };
  arc.outerRadius = function(_) {
    return arguments.length ? (outerRadius = typeof _ === "function" ? _ : constant_default7(+_), arc) : outerRadius;
  };
  arc.cornerRadius = function(_) {
    return arguments.length ? (cornerRadius = typeof _ === "function" ? _ : constant_default7(+_), arc) : cornerRadius;
  };
  arc.padRadius = function(_) {
    return arguments.length ? (padRadius = _ == null ? null : typeof _ === "function" ? _ : constant_default7(+_), arc) : padRadius;
  };
  arc.startAngle = function(_) {
    return arguments.length ? (startAngle = typeof _ === "function" ? _ : constant_default7(+_), arc) : startAngle;
  };
  arc.endAngle = function(_) {
    return arguments.length ? (endAngle = typeof _ === "function" ? _ : constant_default7(+_), arc) : endAngle;
  };
  arc.padAngle = function(_) {
    return arguments.length ? (padAngle = typeof _ === "function" ? _ : constant_default7(+_), arc) : padAngle;
  };
  arc.context = function(_) {
    return arguments.length ? (context = _ == null ? null : _, arc) : context;
  };
  return arc;
}

// node_modules/d3-shape/src/array.js
var slice4 = Array.prototype.slice;
function array_default3(x4) {
  return typeof x4 === "object" && "length" in x4 ? x4 : Array.from(x4);
}

// node_modules/d3-shape/src/curve/linear.js
function Linear(context) {
  this._context = context;
}
Linear.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._point = 0;
  },
  lineEnd: function() {
    if (this._line || this._line !== 0 && this._point === 1) this._context.closePath();
    this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0:
        this._point = 1;
        this._line ? this._context.lineTo(x4, y4) : this._context.moveTo(x4, y4);
        break;
      case 1:
        this._point = 2;
      // falls through
      default:
        this._context.lineTo(x4, y4);
        break;
    }
  }
};
function linear_default(context) {
  return new Linear(context);
}

// node_modules/d3-shape/src/point.js
function x3(p) {
  return p[0];
}
function y3(p) {
  return p[1];
}

// node_modules/d3-shape/src/line.js
function line_default2(x4, y4) {
  var defined = constant_default7(true), context = null, curve = linear_default, output = null, path2 = withPath(line);
  x4 = typeof x4 === "function" ? x4 : x4 === void 0 ? x3 : constant_default7(x4);
  y4 = typeof y4 === "function" ? y4 : y4 === void 0 ? y3 : constant_default7(y4);
  function line(data) {
    var i, n = (data = array_default3(data)).length, d, defined0 = false, buffer;
    if (context == null) output = curve(buffer = path2());
    for (i = 0; i <= n; ++i) {
      if (!(i < n && defined(d = data[i], i, data)) === defined0) {
        if (defined0 = !defined0) output.lineStart();
        else output.lineEnd();
      }
      if (defined0) output.point(+x4(d, i, data), +y4(d, i, data));
    }
    if (buffer) return output = null, buffer + "" || null;
  }
  line.x = function(_) {
    return arguments.length ? (x4 = typeof _ === "function" ? _ : constant_default7(+_), line) : x4;
  };
  line.y = function(_) {
    return arguments.length ? (y4 = typeof _ === "function" ? _ : constant_default7(+_), line) : y4;
  };
  line.defined = function(_) {
    return arguments.length ? (defined = typeof _ === "function" ? _ : constant_default7(!!_), line) : defined;
  };
  line.curve = function(_) {
    return arguments.length ? (curve = _, context != null && (output = curve(context)), line) : curve;
  };
  line.context = function(_) {
    return arguments.length ? (_ == null ? context = output = null : output = curve(context = _), line) : context;
  };
  return line;
}

// node_modules/d3-shape/src/area.js
function area_default5(x06, y06, y12) {
  var x12 = null, defined = constant_default7(true), context = null, curve = linear_default, output = null, path2 = withPath(area);
  x06 = typeof x06 === "function" ? x06 : x06 === void 0 ? x3 : constant_default7(+x06);
  y06 = typeof y06 === "function" ? y06 : y06 === void 0 ? constant_default7(0) : constant_default7(+y06);
  y12 = typeof y12 === "function" ? y12 : y12 === void 0 ? y3 : constant_default7(+y12);
  function area(data) {
    var i, j, k2, n = (data = array_default3(data)).length, d, defined0 = false, buffer, x0z = new Array(n), y0z = new Array(n);
    if (context == null) output = curve(buffer = path2());
    for (i = 0; i <= n; ++i) {
      if (!(i < n && defined(d = data[i], i, data)) === defined0) {
        if (defined0 = !defined0) {
          j = i;
          output.areaStart();
          output.lineStart();
        } else {
          output.lineEnd();
          output.lineStart();
          for (k2 = i - 1; k2 >= j; --k2) {
            output.point(x0z[k2], y0z[k2]);
          }
          output.lineEnd();
          output.areaEnd();
        }
      }
      if (defined0) {
        x0z[i] = +x06(d, i, data), y0z[i] = +y06(d, i, data);
        output.point(x12 ? +x12(d, i, data) : x0z[i], y12 ? +y12(d, i, data) : y0z[i]);
      }
    }
    if (buffer) return output = null, buffer + "" || null;
  }
  function arealine() {
    return line_default2().defined(defined).curve(curve).context(context);
  }
  area.x = function(_) {
    return arguments.length ? (x06 = typeof _ === "function" ? _ : constant_default7(+_), x12 = null, area) : x06;
  };
  area.x0 = function(_) {
    return arguments.length ? (x06 = typeof _ === "function" ? _ : constant_default7(+_), area) : x06;
  };
  area.x1 = function(_) {
    return arguments.length ? (x12 = _ == null ? null : typeof _ === "function" ? _ : constant_default7(+_), area) : x12;
  };
  area.y = function(_) {
    return arguments.length ? (y06 = typeof _ === "function" ? _ : constant_default7(+_), y12 = null, area) : y06;
  };
  area.y0 = function(_) {
    return arguments.length ? (y06 = typeof _ === "function" ? _ : constant_default7(+_), area) : y06;
  };
  area.y1 = function(_) {
    return arguments.length ? (y12 = _ == null ? null : typeof _ === "function" ? _ : constant_default7(+_), area) : y12;
  };
  area.lineX0 = area.lineY0 = function() {
    return arealine().x(x06).y(y06);
  };
  area.lineY1 = function() {
    return arealine().x(x06).y(y12);
  };
  area.lineX1 = function() {
    return arealine().x(x12).y(y06);
  };
  area.defined = function(_) {
    return arguments.length ? (defined = typeof _ === "function" ? _ : constant_default7(!!_), area) : defined;
  };
  area.curve = function(_) {
    return arguments.length ? (curve = _, context != null && (output = curve(context)), area) : curve;
  };
  area.context = function(_) {
    return arguments.length ? (_ == null ? context = output = null : output = curve(context = _), area) : context;
  };
  return area;
}

// node_modules/d3-shape/src/descending.js
function descending_default(a4, b) {
  return b < a4 ? -1 : b > a4 ? 1 : b >= a4 ? 0 : NaN;
}

// node_modules/d3-shape/src/identity.js
function identity_default5(d) {
  return d;
}

// node_modules/d3-shape/src/pie.js
function pie_default() {
  var value = identity_default5, sortValues = descending_default, sort2 = null, startAngle = constant_default7(0), endAngle = constant_default7(tau5), padAngle = constant_default7(0);
  function pie(data) {
    var i, n = (data = array_default3(data)).length, j, k2, sum4 = 0, index3 = new Array(n), arcs = new Array(n), a0 = +startAngle.apply(this, arguments), da2 = Math.min(tau5, Math.max(-tau5, endAngle.apply(this, arguments) - a0)), a1, p = Math.min(Math.abs(da2) / n, padAngle.apply(this, arguments)), pa = p * (da2 < 0 ? -1 : 1), v2;
    for (i = 0; i < n; ++i) {
      if ((v2 = arcs[index3[i] = i] = +value(data[i], i, data)) > 0) {
        sum4 += v2;
      }
    }
    if (sortValues != null) index3.sort(function(i2, j2) {
      return sortValues(arcs[i2], arcs[j2]);
    });
    else if (sort2 != null) index3.sort(function(i2, j2) {
      return sort2(data[i2], data[j2]);
    });
    for (i = 0, k2 = sum4 ? (da2 - n * pa) / sum4 : 0; i < n; ++i, a0 = a1) {
      j = index3[i], v2 = arcs[j], a1 = a0 + (v2 > 0 ? v2 * k2 : 0) + pa, arcs[j] = {
        data: data[j],
        index: i,
        value: v2,
        startAngle: a0,
        endAngle: a1,
        padAngle: p
      };
    }
    return arcs;
  }
  pie.value = function(_) {
    return arguments.length ? (value = typeof _ === "function" ? _ : constant_default7(+_), pie) : value;
  };
  pie.sortValues = function(_) {
    return arguments.length ? (sortValues = _, sort2 = null, pie) : sortValues;
  };
  pie.sort = function(_) {
    return arguments.length ? (sort2 = _, sortValues = null, pie) : sort2;
  };
  pie.startAngle = function(_) {
    return arguments.length ? (startAngle = typeof _ === "function" ? _ : constant_default7(+_), pie) : startAngle;
  };
  pie.endAngle = function(_) {
    return arguments.length ? (endAngle = typeof _ === "function" ? _ : constant_default7(+_), pie) : endAngle;
  };
  pie.padAngle = function(_) {
    return arguments.length ? (padAngle = typeof _ === "function" ? _ : constant_default7(+_), pie) : padAngle;
  };
  return pie;
}

// node_modules/d3-shape/src/curve/radial.js
var curveRadialLinear = curveRadial(linear_default);
function Radial(curve) {
  this._curve = curve;
}
Radial.prototype = {
  areaStart: function() {
    this._curve.areaStart();
  },
  areaEnd: function() {
    this._curve.areaEnd();
  },
  lineStart: function() {
    this._curve.lineStart();
  },
  lineEnd: function() {
    this._curve.lineEnd();
  },
  point: function(a4, r) {
    this._curve.point(r * Math.sin(a4), r * -Math.cos(a4));
  }
};
function curveRadial(curve) {
  function radial2(context) {
    return new Radial(curve(context));
  }
  radial2._curve = curve;
  return radial2;
}

// node_modules/d3-shape/src/lineRadial.js
function lineRadial(l) {
  var c6 = l.curve;
  l.angle = l.x, delete l.x;
  l.radius = l.y, delete l.y;
  l.curve = function(_) {
    return arguments.length ? c6(curveRadial(_)) : c6()._curve;
  };
  return l;
}
function lineRadial_default() {
  return lineRadial(line_default2().curve(curveRadialLinear));
}

// node_modules/d3-shape/src/areaRadial.js
function areaRadial_default() {
  var a4 = area_default5().curve(curveRadialLinear), c6 = a4.curve, x06 = a4.lineX0, x12 = a4.lineX1, y06 = a4.lineY0, y12 = a4.lineY1;
  a4.angle = a4.x, delete a4.x;
  a4.startAngle = a4.x0, delete a4.x0;
  a4.endAngle = a4.x1, delete a4.x1;
  a4.radius = a4.y, delete a4.y;
  a4.innerRadius = a4.y0, delete a4.y0;
  a4.outerRadius = a4.y1, delete a4.y1;
  a4.lineStartAngle = function() {
    return lineRadial(x06());
  }, delete a4.lineX0;
  a4.lineEndAngle = function() {
    return lineRadial(x12());
  }, delete a4.lineX1;
  a4.lineInnerRadius = function() {
    return lineRadial(y06());
  }, delete a4.lineY0;
  a4.lineOuterRadius = function() {
    return lineRadial(y12());
  }, delete a4.lineY1;
  a4.curve = function(_) {
    return arguments.length ? c6(curveRadial(_)) : c6()._curve;
  };
  return a4;
}

// node_modules/d3-shape/src/pointRadial.js
function pointRadial_default(x4, y4) {
  return [(y4 = +y4) * Math.cos(x4 -= Math.PI / 2), y4 * Math.sin(x4)];
}

// node_modules/d3-shape/src/curve/bump.js
var Bump = class {
  constructor(context, x4) {
    this._context = context;
    this._x = x4;
  }
  areaStart() {
    this._line = 0;
  }
  areaEnd() {
    this._line = NaN;
  }
  lineStart() {
    this._point = 0;
  }
  lineEnd() {
    if (this._line || this._line !== 0 && this._point === 1) this._context.closePath();
    this._line = 1 - this._line;
  }
  point(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0: {
        this._point = 1;
        if (this._line) this._context.lineTo(x4, y4);
        else this._context.moveTo(x4, y4);
        break;
      }
      case 1:
        this._point = 2;
      // falls through
      default: {
        if (this._x) this._context.bezierCurveTo(this._x0 = (this._x0 + x4) / 2, this._y0, this._x0, y4, x4, y4);
        else this._context.bezierCurveTo(this._x0, this._y0 = (this._y0 + y4) / 2, x4, this._y0, x4, y4);
        break;
      }
    }
    this._x0 = x4, this._y0 = y4;
  }
};
var BumpRadial = class {
  constructor(context) {
    this._context = context;
  }
  lineStart() {
    this._point = 0;
  }
  lineEnd() {
  }
  point(x4, y4) {
    x4 = +x4, y4 = +y4;
    if (this._point === 0) {
      this._point = 1;
    } else {
      const p02 = pointRadial_default(this._x0, this._y0);
      const p1 = pointRadial_default(this._x0, this._y0 = (this._y0 + y4) / 2);
      const p2 = pointRadial_default(x4, this._y0);
      const p3 = pointRadial_default(x4, y4);
      this._context.moveTo(...p02);
      this._context.bezierCurveTo(...p1, ...p2, ...p3);
    }
    this._x0 = x4, this._y0 = y4;
  }
};
function bumpX(context) {
  return new Bump(context, true);
}
function bumpY(context) {
  return new Bump(context, false);
}
function bumpRadial(context) {
  return new BumpRadial(context);
}

// node_modules/d3-shape/src/link.js
function linkSource(d) {
  return d.source;
}
function linkTarget(d) {
  return d.target;
}
function link2(curve) {
  let source = linkSource, target = linkTarget, x4 = x3, y4 = y3, context = null, output = null, path2 = withPath(link3);
  function link3() {
    let buffer;
    const argv = slice4.call(arguments);
    const s2 = source.apply(this, argv);
    const t = target.apply(this, argv);
    if (context == null) output = curve(buffer = path2());
    output.lineStart();
    argv[0] = s2, output.point(+x4.apply(this, argv), +y4.apply(this, argv));
    argv[0] = t, output.point(+x4.apply(this, argv), +y4.apply(this, argv));
    output.lineEnd();
    if (buffer) return output = null, buffer + "" || null;
  }
  link3.source = function(_) {
    return arguments.length ? (source = _, link3) : source;
  };
  link3.target = function(_) {
    return arguments.length ? (target = _, link3) : target;
  };
  link3.x = function(_) {
    return arguments.length ? (x4 = typeof _ === "function" ? _ : constant_default7(+_), link3) : x4;
  };
  link3.y = function(_) {
    return arguments.length ? (y4 = typeof _ === "function" ? _ : constant_default7(+_), link3) : y4;
  };
  link3.context = function(_) {
    return arguments.length ? (_ == null ? context = output = null : output = curve(context = _), link3) : context;
  };
  return link3;
}
function linkHorizontal() {
  return link2(bumpX);
}
function linkVertical() {
  return link2(bumpY);
}
function linkRadial() {
  const l = link2(bumpRadial);
  l.angle = l.x, delete l.x;
  l.radius = l.y, delete l.y;
  return l;
}

// node_modules/d3-shape/src/symbol/asterisk.js
var sqrt32 = sqrt3(3);
var asterisk_default = {
  draw(context, size) {
    const r = sqrt3(size + min3(size / 28, 0.75)) * 0.59436;
    const t = r / 2;
    const u4 = t * sqrt32;
    context.moveTo(0, r);
    context.lineTo(0, -r);
    context.moveTo(-u4, -t);
    context.lineTo(u4, t);
    context.moveTo(-u4, t);
    context.lineTo(u4, -t);
  }
};

// node_modules/d3-shape/src/symbol/circle.js
var circle_default3 = {
  draw(context, size) {
    const r = sqrt3(size / pi4);
    context.moveTo(r, 0);
    context.arc(0, 0, r, 0, tau5);
  }
};

// node_modules/d3-shape/src/symbol/cross.js
var cross_default2 = {
  draw(context, size) {
    const r = sqrt3(size / 5) / 2;
    context.moveTo(-3 * r, -r);
    context.lineTo(-r, -r);
    context.lineTo(-r, -3 * r);
    context.lineTo(r, -3 * r);
    context.lineTo(r, -r);
    context.lineTo(3 * r, -r);
    context.lineTo(3 * r, r);
    context.lineTo(r, r);
    context.lineTo(r, 3 * r);
    context.lineTo(-r, 3 * r);
    context.lineTo(-r, r);
    context.lineTo(-3 * r, r);
    context.closePath();
  }
};

// node_modules/d3-shape/src/symbol/diamond.js
var tan30 = sqrt3(1 / 3);
var tan30_2 = tan30 * 2;
var diamond_default = {
  draw(context, size) {
    const y4 = sqrt3(size / tan30_2);
    const x4 = y4 * tan30;
    context.moveTo(0, -y4);
    context.lineTo(x4, 0);
    context.lineTo(0, y4);
    context.lineTo(-x4, 0);
    context.closePath();
  }
};

// node_modules/d3-shape/src/symbol/diamond2.js
var diamond2_default = {
  draw(context, size) {
    const r = sqrt3(size) * 0.62625;
    context.moveTo(0, -r);
    context.lineTo(r, 0);
    context.lineTo(0, r);
    context.lineTo(-r, 0);
    context.closePath();
  }
};

// node_modules/d3-shape/src/symbol/plus.js
var plus_default = {
  draw(context, size) {
    const r = sqrt3(size - min3(size / 7, 2)) * 0.87559;
    context.moveTo(-r, 0);
    context.lineTo(r, 0);
    context.moveTo(0, r);
    context.lineTo(0, -r);
  }
};

// node_modules/d3-shape/src/symbol/square.js
var square_default = {
  draw(context, size) {
    const w = sqrt3(size);
    const x4 = -w / 2;
    context.rect(x4, x4, w, w);
  }
};

// node_modules/d3-shape/src/symbol/square2.js
var square2_default = {
  draw(context, size) {
    const r = sqrt3(size) * 0.4431;
    context.moveTo(r, r);
    context.lineTo(r, -r);
    context.lineTo(-r, -r);
    context.lineTo(-r, r);
    context.closePath();
  }
};

// node_modules/d3-shape/src/symbol/star.js
var ka = 0.8908130915292852;
var kr = sin3(pi4 / 10) / sin3(7 * pi4 / 10);
var kx = sin3(tau5 / 10) * kr;
var ky = -cos3(tau5 / 10) * kr;
var star_default = {
  draw(context, size) {
    const r = sqrt3(size * ka);
    const x4 = kx * r;
    const y4 = ky * r;
    context.moveTo(0, -r);
    context.lineTo(x4, y4);
    for (let i = 1; i < 5; ++i) {
      const a4 = tau5 * i / 5;
      const c6 = cos3(a4);
      const s2 = sin3(a4);
      context.lineTo(s2 * r, -c6 * r);
      context.lineTo(c6 * x4 - s2 * y4, s2 * x4 + c6 * y4);
    }
    context.closePath();
  }
};

// node_modules/d3-shape/src/symbol/triangle.js
var sqrt33 = sqrt3(3);
var triangle_default = {
  draw(context, size) {
    const y4 = -sqrt3(size / (sqrt33 * 3));
    context.moveTo(0, y4 * 2);
    context.lineTo(-sqrt33 * y4, -y4);
    context.lineTo(sqrt33 * y4, -y4);
    context.closePath();
  }
};

// node_modules/d3-shape/src/symbol/triangle2.js
var sqrt34 = sqrt3(3);
var triangle2_default = {
  draw(context, size) {
    const s2 = sqrt3(size) * 0.6824;
    const t = s2 / 2;
    const u4 = s2 * sqrt34 / 2;
    context.moveTo(0, -s2);
    context.lineTo(u4, t);
    context.lineTo(-u4, t);
    context.closePath();
  }
};

// node_modules/d3-shape/src/symbol/wye.js
var c5 = -0.5;
var s = sqrt3(3) / 2;
var k = 1 / sqrt3(12);
var a3 = (k / 2 + 1) * 3;
var wye_default = {
  draw(context, size) {
    const r = sqrt3(size / a3);
    const x06 = r / 2, y06 = r * k;
    const x12 = x06, y12 = r * k + r;
    const x22 = -x12, y22 = y12;
    context.moveTo(x06, y06);
    context.lineTo(x12, y12);
    context.lineTo(x22, y22);
    context.lineTo(c5 * x06 - s * y06, s * x06 + c5 * y06);
    context.lineTo(c5 * x12 - s * y12, s * x12 + c5 * y12);
    context.lineTo(c5 * x22 - s * y22, s * x22 + c5 * y22);
    context.lineTo(c5 * x06 + s * y06, c5 * y06 - s * x06);
    context.lineTo(c5 * x12 + s * y12, c5 * y12 - s * x12);
    context.lineTo(c5 * x22 + s * y22, c5 * y22 - s * x22);
    context.closePath();
  }
};

// node_modules/d3-shape/src/symbol/times.js
var times_default = {
  draw(context, size) {
    const r = sqrt3(size - min3(size / 6, 1.7)) * 0.6189;
    context.moveTo(-r, -r);
    context.lineTo(r, r);
    context.moveTo(-r, r);
    context.lineTo(r, -r);
  }
};

// node_modules/d3-shape/src/symbol.js
var symbolsFill = [
  circle_default3,
  cross_default2,
  diamond_default,
  square_default,
  star_default,
  triangle_default,
  wye_default
];
var symbolsStroke = [
  circle_default3,
  plus_default,
  times_default,
  triangle2_default,
  asterisk_default,
  square2_default,
  diamond2_default
];
function Symbol2(type2, size) {
  let context = null, path2 = withPath(symbol);
  type2 = typeof type2 === "function" ? type2 : constant_default7(type2 || circle_default3);
  size = typeof size === "function" ? size : constant_default7(size === void 0 ? 64 : +size);
  function symbol() {
    let buffer;
    if (!context) context = buffer = path2();
    type2.apply(this, arguments).draw(context, +size.apply(this, arguments));
    if (buffer) return context = null, buffer + "" || null;
  }
  symbol.type = function(_) {
    return arguments.length ? (type2 = typeof _ === "function" ? _ : constant_default7(_), symbol) : type2;
  };
  symbol.size = function(_) {
    return arguments.length ? (size = typeof _ === "function" ? _ : constant_default7(+_), symbol) : size;
  };
  symbol.context = function(_) {
    return arguments.length ? (context = _ == null ? null : _, symbol) : context;
  };
  return symbol;
}

// node_modules/d3-shape/src/noop.js
function noop_default2() {
}

// node_modules/d3-shape/src/curve/basis.js
function point2(that, x4, y4) {
  that._context.bezierCurveTo(
    (2 * that._x0 + that._x1) / 3,
    (2 * that._y0 + that._y1) / 3,
    (that._x0 + 2 * that._x1) / 3,
    (that._y0 + 2 * that._y1) / 3,
    (that._x0 + 4 * that._x1 + x4) / 6,
    (that._y0 + 4 * that._y1 + y4) / 6
  );
}
function Basis(context) {
  this._context = context;
}
Basis.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x0 = this._x1 = this._y0 = this._y1 = NaN;
    this._point = 0;
  },
  lineEnd: function() {
    switch (this._point) {
      case 3:
        point2(this, this._x1, this._y1);
      // falls through
      case 2:
        this._context.lineTo(this._x1, this._y1);
        break;
    }
    if (this._line || this._line !== 0 && this._point === 1) this._context.closePath();
    this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0:
        this._point = 1;
        this._line ? this._context.lineTo(x4, y4) : this._context.moveTo(x4, y4);
        break;
      case 1:
        this._point = 2;
        break;
      case 2:
        this._point = 3;
        this._context.lineTo((5 * this._x0 + this._x1) / 6, (5 * this._y0 + this._y1) / 6);
      // falls through
      default:
        point2(this, x4, y4);
        break;
    }
    this._x0 = this._x1, this._x1 = x4;
    this._y0 = this._y1, this._y1 = y4;
  }
};
function basis_default2(context) {
  return new Basis(context);
}

// node_modules/d3-shape/src/curve/basisClosed.js
function BasisClosed(context) {
  this._context = context;
}
BasisClosed.prototype = {
  areaStart: noop_default2,
  areaEnd: noop_default2,
  lineStart: function() {
    this._x0 = this._x1 = this._x2 = this._x3 = this._x4 = this._y0 = this._y1 = this._y2 = this._y3 = this._y4 = NaN;
    this._point = 0;
  },
  lineEnd: function() {
    switch (this._point) {
      case 1: {
        this._context.moveTo(this._x2, this._y2);
        this._context.closePath();
        break;
      }
      case 2: {
        this._context.moveTo((this._x2 + 2 * this._x3) / 3, (this._y2 + 2 * this._y3) / 3);
        this._context.lineTo((this._x3 + 2 * this._x2) / 3, (this._y3 + 2 * this._y2) / 3);
        this._context.closePath();
        break;
      }
      case 3: {
        this.point(this._x2, this._y2);
        this.point(this._x3, this._y3);
        this.point(this._x4, this._y4);
        break;
      }
    }
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0:
        this._point = 1;
        this._x2 = x4, this._y2 = y4;
        break;
      case 1:
        this._point = 2;
        this._x3 = x4, this._y3 = y4;
        break;
      case 2:
        this._point = 3;
        this._x4 = x4, this._y4 = y4;
        this._context.moveTo((this._x0 + 4 * this._x1 + x4) / 6, (this._y0 + 4 * this._y1 + y4) / 6);
        break;
      default:
        point2(this, x4, y4);
        break;
    }
    this._x0 = this._x1, this._x1 = x4;
    this._y0 = this._y1, this._y1 = y4;
  }
};
function basisClosed_default2(context) {
  return new BasisClosed(context);
}

// node_modules/d3-shape/src/curve/basisOpen.js
function BasisOpen(context) {
  this._context = context;
}
BasisOpen.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x0 = this._x1 = this._y0 = this._y1 = NaN;
    this._point = 0;
  },
  lineEnd: function() {
    if (this._line || this._line !== 0 && this._point === 3) this._context.closePath();
    this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0:
        this._point = 1;
        break;
      case 1:
        this._point = 2;
        break;
      case 2:
        this._point = 3;
        var x06 = (this._x0 + 4 * this._x1 + x4) / 6, y06 = (this._y0 + 4 * this._y1 + y4) / 6;
        this._line ? this._context.lineTo(x06, y06) : this._context.moveTo(x06, y06);
        break;
      case 3:
        this._point = 4;
      // falls through
      default:
        point2(this, x4, y4);
        break;
    }
    this._x0 = this._x1, this._x1 = x4;
    this._y0 = this._y1, this._y1 = y4;
  }
};
function basisOpen_default(context) {
  return new BasisOpen(context);
}

// node_modules/d3-shape/src/curve/bundle.js
function Bundle(context, beta) {
  this._basis = new Basis(context);
  this._beta = beta;
}
Bundle.prototype = {
  lineStart: function() {
    this._x = [];
    this._y = [];
    this._basis.lineStart();
  },
  lineEnd: function() {
    var x4 = this._x, y4 = this._y, j = x4.length - 1;
    if (j > 0) {
      var x06 = x4[0], y06 = y4[0], dx = x4[j] - x06, dy = y4[j] - y06, i = -1, t;
      while (++i <= j) {
        t = i / j;
        this._basis.point(
          this._beta * x4[i] + (1 - this._beta) * (x06 + t * dx),
          this._beta * y4[i] + (1 - this._beta) * (y06 + t * dy)
        );
      }
    }
    this._x = this._y = null;
    this._basis.lineEnd();
  },
  point: function(x4, y4) {
    this._x.push(+x4);
    this._y.push(+y4);
  }
};
var bundle_default = (function custom3(beta) {
  function bundle(context) {
    return beta === 1 ? new Basis(context) : new Bundle(context, beta);
  }
  bundle.beta = function(beta2) {
    return custom3(+beta2);
  };
  return bundle;
})(0.85);

// node_modules/d3-shape/src/curve/cardinal.js
function point3(that, x4, y4) {
  that._context.bezierCurveTo(
    that._x1 + that._k * (that._x2 - that._x0),
    that._y1 + that._k * (that._y2 - that._y0),
    that._x2 + that._k * (that._x1 - x4),
    that._y2 + that._k * (that._y1 - y4),
    that._x2,
    that._y2
  );
}
function Cardinal(context, tension) {
  this._context = context;
  this._k = (1 - tension) / 6;
}
Cardinal.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x0 = this._x1 = this._x2 = this._y0 = this._y1 = this._y2 = NaN;
    this._point = 0;
  },
  lineEnd: function() {
    switch (this._point) {
      case 2:
        this._context.lineTo(this._x2, this._y2);
        break;
      case 3:
        point3(this, this._x1, this._y1);
        break;
    }
    if (this._line || this._line !== 0 && this._point === 1) this._context.closePath();
    this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0:
        this._point = 1;
        this._line ? this._context.lineTo(x4, y4) : this._context.moveTo(x4, y4);
        break;
      case 1:
        this._point = 2;
        this._x1 = x4, this._y1 = y4;
        break;
      case 2:
        this._point = 3;
      // falls through
      default:
        point3(this, x4, y4);
        break;
    }
    this._x0 = this._x1, this._x1 = this._x2, this._x2 = x4;
    this._y0 = this._y1, this._y1 = this._y2, this._y2 = y4;
  }
};
var cardinal_default = (function custom4(tension) {
  function cardinal(context) {
    return new Cardinal(context, tension);
  }
  cardinal.tension = function(tension2) {
    return custom4(+tension2);
  };
  return cardinal;
})(0);

// node_modules/d3-shape/src/curve/cardinalClosed.js
function CardinalClosed(context, tension) {
  this._context = context;
  this._k = (1 - tension) / 6;
}
CardinalClosed.prototype = {
  areaStart: noop_default2,
  areaEnd: noop_default2,
  lineStart: function() {
    this._x0 = this._x1 = this._x2 = this._x3 = this._x4 = this._x5 = this._y0 = this._y1 = this._y2 = this._y3 = this._y4 = this._y5 = NaN;
    this._point = 0;
  },
  lineEnd: function() {
    switch (this._point) {
      case 1: {
        this._context.moveTo(this._x3, this._y3);
        this._context.closePath();
        break;
      }
      case 2: {
        this._context.lineTo(this._x3, this._y3);
        this._context.closePath();
        break;
      }
      case 3: {
        this.point(this._x3, this._y3);
        this.point(this._x4, this._y4);
        this.point(this._x5, this._y5);
        break;
      }
    }
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0:
        this._point = 1;
        this._x3 = x4, this._y3 = y4;
        break;
      case 1:
        this._point = 2;
        this._context.moveTo(this._x4 = x4, this._y4 = y4);
        break;
      case 2:
        this._point = 3;
        this._x5 = x4, this._y5 = y4;
        break;
      default:
        point3(this, x4, y4);
        break;
    }
    this._x0 = this._x1, this._x1 = this._x2, this._x2 = x4;
    this._y0 = this._y1, this._y1 = this._y2, this._y2 = y4;
  }
};
var cardinalClosed_default = (function custom5(tension) {
  function cardinal(context) {
    return new CardinalClosed(context, tension);
  }
  cardinal.tension = function(tension2) {
    return custom5(+tension2);
  };
  return cardinal;
})(0);

// node_modules/d3-shape/src/curve/cardinalOpen.js
function CardinalOpen(context, tension) {
  this._context = context;
  this._k = (1 - tension) / 6;
}
CardinalOpen.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x0 = this._x1 = this._x2 = this._y0 = this._y1 = this._y2 = NaN;
    this._point = 0;
  },
  lineEnd: function() {
    if (this._line || this._line !== 0 && this._point === 3) this._context.closePath();
    this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0:
        this._point = 1;
        break;
      case 1:
        this._point = 2;
        break;
      case 2:
        this._point = 3;
        this._line ? this._context.lineTo(this._x2, this._y2) : this._context.moveTo(this._x2, this._y2);
        break;
      case 3:
        this._point = 4;
      // falls through
      default:
        point3(this, x4, y4);
        break;
    }
    this._x0 = this._x1, this._x1 = this._x2, this._x2 = x4;
    this._y0 = this._y1, this._y1 = this._y2, this._y2 = y4;
  }
};
var cardinalOpen_default = (function custom6(tension) {
  function cardinal(context) {
    return new CardinalOpen(context, tension);
  }
  cardinal.tension = function(tension2) {
    return custom6(+tension2);
  };
  return cardinal;
})(0);

// node_modules/d3-shape/src/curve/catmullRom.js
function point4(that, x4, y4) {
  var x12 = that._x1, y12 = that._y1, x22 = that._x2, y22 = that._y2;
  if (that._l01_a > epsilon7) {
    var a4 = 2 * that._l01_2a + 3 * that._l01_a * that._l12_a + that._l12_2a, n = 3 * that._l01_a * (that._l01_a + that._l12_a);
    x12 = (x12 * a4 - that._x0 * that._l12_2a + that._x2 * that._l01_2a) / n;
    y12 = (y12 * a4 - that._y0 * that._l12_2a + that._y2 * that._l01_2a) / n;
  }
  if (that._l23_a > epsilon7) {
    var b = 2 * that._l23_2a + 3 * that._l23_a * that._l12_a + that._l12_2a, m3 = 3 * that._l23_a * (that._l23_a + that._l12_a);
    x22 = (x22 * b + that._x1 * that._l23_2a - x4 * that._l12_2a) / m3;
    y22 = (y22 * b + that._y1 * that._l23_2a - y4 * that._l12_2a) / m3;
  }
  that._context.bezierCurveTo(x12, y12, x22, y22, that._x2, that._y2);
}
function CatmullRom(context, alpha) {
  this._context = context;
  this._alpha = alpha;
}
CatmullRom.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x0 = this._x1 = this._x2 = this._y0 = this._y1 = this._y2 = NaN;
    this._l01_a = this._l12_a = this._l23_a = this._l01_2a = this._l12_2a = this._l23_2a = this._point = 0;
  },
  lineEnd: function() {
    switch (this._point) {
      case 2:
        this._context.lineTo(this._x2, this._y2);
        break;
      case 3:
        this.point(this._x2, this._y2);
        break;
    }
    if (this._line || this._line !== 0 && this._point === 1) this._context.closePath();
    this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    if (this._point) {
      var x23 = this._x2 - x4, y23 = this._y2 - y4;
      this._l23_a = Math.sqrt(this._l23_2a = Math.pow(x23 * x23 + y23 * y23, this._alpha));
    }
    switch (this._point) {
      case 0:
        this._point = 1;
        this._line ? this._context.lineTo(x4, y4) : this._context.moveTo(x4, y4);
        break;
      case 1:
        this._point = 2;
        break;
      case 2:
        this._point = 3;
      // falls through
      default:
        point4(this, x4, y4);
        break;
    }
    this._l01_a = this._l12_a, this._l12_a = this._l23_a;
    this._l01_2a = this._l12_2a, this._l12_2a = this._l23_2a;
    this._x0 = this._x1, this._x1 = this._x2, this._x2 = x4;
    this._y0 = this._y1, this._y1 = this._y2, this._y2 = y4;
  }
};
var catmullRom_default = (function custom7(alpha) {
  function catmullRom(context) {
    return alpha ? new CatmullRom(context, alpha) : new Cardinal(context, 0);
  }
  catmullRom.alpha = function(alpha2) {
    return custom7(+alpha2);
  };
  return catmullRom;
})(0.5);

// node_modules/d3-shape/src/curve/catmullRomClosed.js
function CatmullRomClosed(context, alpha) {
  this._context = context;
  this._alpha = alpha;
}
CatmullRomClosed.prototype = {
  areaStart: noop_default2,
  areaEnd: noop_default2,
  lineStart: function() {
    this._x0 = this._x1 = this._x2 = this._x3 = this._x4 = this._x5 = this._y0 = this._y1 = this._y2 = this._y3 = this._y4 = this._y5 = NaN;
    this._l01_a = this._l12_a = this._l23_a = this._l01_2a = this._l12_2a = this._l23_2a = this._point = 0;
  },
  lineEnd: function() {
    switch (this._point) {
      case 1: {
        this._context.moveTo(this._x3, this._y3);
        this._context.closePath();
        break;
      }
      case 2: {
        this._context.lineTo(this._x3, this._y3);
        this._context.closePath();
        break;
      }
      case 3: {
        this.point(this._x3, this._y3);
        this.point(this._x4, this._y4);
        this.point(this._x5, this._y5);
        break;
      }
    }
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    if (this._point) {
      var x23 = this._x2 - x4, y23 = this._y2 - y4;
      this._l23_a = Math.sqrt(this._l23_2a = Math.pow(x23 * x23 + y23 * y23, this._alpha));
    }
    switch (this._point) {
      case 0:
        this._point = 1;
        this._x3 = x4, this._y3 = y4;
        break;
      case 1:
        this._point = 2;
        this._context.moveTo(this._x4 = x4, this._y4 = y4);
        break;
      case 2:
        this._point = 3;
        this._x5 = x4, this._y5 = y4;
        break;
      default:
        point4(this, x4, y4);
        break;
    }
    this._l01_a = this._l12_a, this._l12_a = this._l23_a;
    this._l01_2a = this._l12_2a, this._l12_2a = this._l23_2a;
    this._x0 = this._x1, this._x1 = this._x2, this._x2 = x4;
    this._y0 = this._y1, this._y1 = this._y2, this._y2 = y4;
  }
};
var catmullRomClosed_default = (function custom8(alpha) {
  function catmullRom(context) {
    return alpha ? new CatmullRomClosed(context, alpha) : new CardinalClosed(context, 0);
  }
  catmullRom.alpha = function(alpha2) {
    return custom8(+alpha2);
  };
  return catmullRom;
})(0.5);

// node_modules/d3-shape/src/curve/catmullRomOpen.js
function CatmullRomOpen(context, alpha) {
  this._context = context;
  this._alpha = alpha;
}
CatmullRomOpen.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x0 = this._x1 = this._x2 = this._y0 = this._y1 = this._y2 = NaN;
    this._l01_a = this._l12_a = this._l23_a = this._l01_2a = this._l12_2a = this._l23_2a = this._point = 0;
  },
  lineEnd: function() {
    if (this._line || this._line !== 0 && this._point === 3) this._context.closePath();
    this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    if (this._point) {
      var x23 = this._x2 - x4, y23 = this._y2 - y4;
      this._l23_a = Math.sqrt(this._l23_2a = Math.pow(x23 * x23 + y23 * y23, this._alpha));
    }
    switch (this._point) {
      case 0:
        this._point = 1;
        break;
      case 1:
        this._point = 2;
        break;
      case 2:
        this._point = 3;
        this._line ? this._context.lineTo(this._x2, this._y2) : this._context.moveTo(this._x2, this._y2);
        break;
      case 3:
        this._point = 4;
      // falls through
      default:
        point4(this, x4, y4);
        break;
    }
    this._l01_a = this._l12_a, this._l12_a = this._l23_a;
    this._l01_2a = this._l12_2a, this._l12_2a = this._l23_2a;
    this._x0 = this._x1, this._x1 = this._x2, this._x2 = x4;
    this._y0 = this._y1, this._y1 = this._y2, this._y2 = y4;
  }
};
var catmullRomOpen_default = (function custom9(alpha) {
  function catmullRom(context) {
    return alpha ? new CatmullRomOpen(context, alpha) : new CardinalOpen(context, 0);
  }
  catmullRom.alpha = function(alpha2) {
    return custom9(+alpha2);
  };
  return catmullRom;
})(0.5);

// node_modules/d3-shape/src/curve/linearClosed.js
function LinearClosed(context) {
  this._context = context;
}
LinearClosed.prototype = {
  areaStart: noop_default2,
  areaEnd: noop_default2,
  lineStart: function() {
    this._point = 0;
  },
  lineEnd: function() {
    if (this._point) this._context.closePath();
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    if (this._point) this._context.lineTo(x4, y4);
    else this._point = 1, this._context.moveTo(x4, y4);
  }
};
function linearClosed_default(context) {
  return new LinearClosed(context);
}

// node_modules/d3-shape/src/curve/monotone.js
function sign2(x4) {
  return x4 < 0 ? -1 : 1;
}
function slope3(that, x22, y22) {
  var h0 = that._x1 - that._x0, h1 = x22 - that._x1, s0 = (that._y1 - that._y0) / (h0 || h1 < 0 && -0), s1 = (y22 - that._y1) / (h1 || h0 < 0 && -0), p = (s0 * h1 + s1 * h0) / (h0 + h1);
  return (sign2(s0) + sign2(s1)) * Math.min(Math.abs(s0), Math.abs(s1), 0.5 * Math.abs(p)) || 0;
}
function slope2(that, t) {
  var h = that._x1 - that._x0;
  return h ? (3 * (that._y1 - that._y0) / h - t) / 2 : t;
}
function point5(that, t02, t12) {
  var x06 = that._x0, y06 = that._y0, x12 = that._x1, y12 = that._y1, dx = (x12 - x06) / 3;
  that._context.bezierCurveTo(x06 + dx, y06 + dx * t02, x12 - dx, y12 - dx * t12, x12, y12);
}
function MonotoneX(context) {
  this._context = context;
}
MonotoneX.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x0 = this._x1 = this._y0 = this._y1 = this._t0 = NaN;
    this._point = 0;
  },
  lineEnd: function() {
    switch (this._point) {
      case 2:
        this._context.lineTo(this._x1, this._y1);
        break;
      case 3:
        point5(this, this._t0, slope2(this, this._t0));
        break;
    }
    if (this._line || this._line !== 0 && this._point === 1) this._context.closePath();
    this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    var t12 = NaN;
    x4 = +x4, y4 = +y4;
    if (x4 === this._x1 && y4 === this._y1) return;
    switch (this._point) {
      case 0:
        this._point = 1;
        this._line ? this._context.lineTo(x4, y4) : this._context.moveTo(x4, y4);
        break;
      case 1:
        this._point = 2;
        break;
      case 2:
        this._point = 3;
        point5(this, slope2(this, t12 = slope3(this, x4, y4)), t12);
        break;
      default:
        point5(this, this._t0, t12 = slope3(this, x4, y4));
        break;
    }
    this._x0 = this._x1, this._x1 = x4;
    this._y0 = this._y1, this._y1 = y4;
    this._t0 = t12;
  }
};
function MonotoneY(context) {
  this._context = new ReflectContext(context);
}
(MonotoneY.prototype = Object.create(MonotoneX.prototype)).point = function(x4, y4) {
  MonotoneX.prototype.point.call(this, y4, x4);
};
function ReflectContext(context) {
  this._context = context;
}
ReflectContext.prototype = {
  moveTo: function(x4, y4) {
    this._context.moveTo(y4, x4);
  },
  closePath: function() {
    this._context.closePath();
  },
  lineTo: function(x4, y4) {
    this._context.lineTo(y4, x4);
  },
  bezierCurveTo: function(x12, y12, x22, y22, x4, y4) {
    this._context.bezierCurveTo(y12, x12, y22, x22, y4, x4);
  }
};
function monotoneX(context) {
  return new MonotoneX(context);
}
function monotoneY(context) {
  return new MonotoneY(context);
}

// node_modules/d3-shape/src/curve/natural.js
function Natural(context) {
  this._context = context;
}
Natural.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x = [];
    this._y = [];
  },
  lineEnd: function() {
    var x4 = this._x, y4 = this._y, n = x4.length;
    if (n) {
      this._line ? this._context.lineTo(x4[0], y4[0]) : this._context.moveTo(x4[0], y4[0]);
      if (n === 2) {
        this._context.lineTo(x4[1], y4[1]);
      } else {
        var px = controlPoints(x4), py = controlPoints(y4);
        for (var i0 = 0, i1 = 1; i1 < n; ++i0, ++i1) {
          this._context.bezierCurveTo(px[0][i0], py[0][i0], px[1][i0], py[1][i0], x4[i1], y4[i1]);
        }
      }
    }
    if (this._line || this._line !== 0 && n === 1) this._context.closePath();
    this._line = 1 - this._line;
    this._x = this._y = null;
  },
  point: function(x4, y4) {
    this._x.push(+x4);
    this._y.push(+y4);
  }
};
function controlPoints(x4) {
  var i, n = x4.length - 1, m3, a4 = new Array(n), b = new Array(n), r = new Array(n);
  a4[0] = 0, b[0] = 2, r[0] = x4[0] + 2 * x4[1];
  for (i = 1; i < n - 1; ++i) a4[i] = 1, b[i] = 4, r[i] = 4 * x4[i] + 2 * x4[i + 1];
  a4[n - 1] = 2, b[n - 1] = 7, r[n - 1] = 8 * x4[n - 1] + x4[n];
  for (i = 1; i < n; ++i) m3 = a4[i] / b[i - 1], b[i] -= m3, r[i] -= m3 * r[i - 1];
  a4[n - 1] = r[n - 1] / b[n - 1];
  for (i = n - 2; i >= 0; --i) a4[i] = (r[i] - a4[i + 1]) / b[i];
  b[n - 1] = (x4[n] + a4[n - 1]) / 2;
  for (i = 0; i < n - 1; ++i) b[i] = 2 * x4[i + 1] - a4[i + 1];
  return [a4, b];
}
function natural_default(context) {
  return new Natural(context);
}

// node_modules/d3-shape/src/curve/step.js
function Step(context, t) {
  this._context = context;
  this._t = t;
}
Step.prototype = {
  areaStart: function() {
    this._line = 0;
  },
  areaEnd: function() {
    this._line = NaN;
  },
  lineStart: function() {
    this._x = this._y = NaN;
    this._point = 0;
  },
  lineEnd: function() {
    if (0 < this._t && this._t < 1 && this._point === 2) this._context.lineTo(this._x, this._y);
    if (this._line || this._line !== 0 && this._point === 1) this._context.closePath();
    if (this._line >= 0) this._t = 1 - this._t, this._line = 1 - this._line;
  },
  point: function(x4, y4) {
    x4 = +x4, y4 = +y4;
    switch (this._point) {
      case 0:
        this._point = 1;
        this._line ? this._context.lineTo(x4, y4) : this._context.moveTo(x4, y4);
        break;
      case 1:
        this._point = 2;
      // falls through
      default: {
        if (this._t <= 0) {
          this._context.lineTo(this._x, y4);
          this._context.lineTo(x4, y4);
        } else {
          var x12 = this._x * (1 - this._t) + x4 * this._t;
          this._context.lineTo(x12, this._y);
          this._context.lineTo(x12, y4);
        }
        break;
      }
    }
    this._x = x4, this._y = y4;
  }
};
function step_default(context) {
  return new Step(context, 0.5);
}
function stepBefore(context) {
  return new Step(context, 0);
}
function stepAfter(context) {
  return new Step(context, 1);
}

// node_modules/d3-shape/src/offset/none.js
function none_default(series, order) {
  if (!((n = series.length) > 1)) return;
  for (var i = 1, j, s0, s1 = series[order[0]], n, m3 = s1.length; i < n; ++i) {
    s0 = s1, s1 = series[order[i]];
    for (j = 0; j < m3; ++j) {
      s1[j][1] += s1[j][0] = isNaN(s0[j][1]) ? s0[j][0] : s0[j][1];
    }
  }
}

// node_modules/d3-shape/src/order/none.js
function none_default2(series) {
  var n = series.length, o = new Array(n);
  while (--n >= 0) o[n] = n;
  return o;
}

// node_modules/d3-shape/src/stack.js
function stackValue(d, key) {
  return d[key];
}
function stackSeries(key) {
  const series = [];
  series.key = key;
  return series;
}
function stack_default() {
  var keys = constant_default7([]), order = none_default2, offset = none_default, value = stackValue;
  function stack(data) {
    var sz = Array.from(keys.apply(this, arguments), stackSeries), i, n = sz.length, j = -1, oz;
    for (const d of data) {
      for (i = 0, ++j; i < n; ++i) {
        (sz[i][j] = [0, +value(d, sz[i].key, j, data)]).data = d;
      }
    }
    for (i = 0, oz = array_default3(order(sz)); i < n; ++i) {
      sz[oz[i]].index = i;
    }
    offset(sz, oz);
    return sz;
  }
  stack.keys = function(_) {
    return arguments.length ? (keys = typeof _ === "function" ? _ : constant_default7(Array.from(_)), stack) : keys;
  };
  stack.value = function(_) {
    return arguments.length ? (value = typeof _ === "function" ? _ : constant_default7(+_), stack) : value;
  };
  stack.order = function(_) {
    return arguments.length ? (order = _ == null ? none_default2 : typeof _ === "function" ? _ : constant_default7(Array.from(_)), stack) : order;
  };
  stack.offset = function(_) {
    return arguments.length ? (offset = _ == null ? none_default : _, stack) : offset;
  };
  return stack;
}

// node_modules/d3-shape/src/offset/expand.js
function expand_default(series, order) {
  if (!((n = series.length) > 0)) return;
  for (var i, n, j = 0, m3 = series[0].length, y4; j < m3; ++j) {
    for (y4 = i = 0; i < n; ++i) y4 += series[i][j][1] || 0;
    if (y4) for (i = 0; i < n; ++i) series[i][j][1] /= y4;
  }
  none_default(series, order);
}

// node_modules/d3-shape/src/offset/diverging.js
function diverging_default(series, order) {
  if (!((n = series.length) > 0)) return;
  for (var i, j = 0, d, dy, yp, yn, n, m3 = series[order[0]].length; j < m3; ++j) {
    for (yp = yn = 0, i = 0; i < n; ++i) {
      if ((dy = (d = series[order[i]][j])[1] - d[0]) > 0) {
        d[0] = yp, d[1] = yp += dy;
      } else if (dy < 0) {
        d[1] = yn, d[0] = yn += dy;
      } else {
        d[0] = 0, d[1] = dy;
      }
    }
  }
}

// node_modules/d3-shape/src/offset/silhouette.js
function silhouette_default(series, order) {
  if (!((n = series.length) > 0)) return;
  for (var j = 0, s0 = series[order[0]], n, m3 = s0.length; j < m3; ++j) {
    for (var i = 0, y4 = 0; i < n; ++i) y4 += series[i][j][1] || 0;
    s0[j][1] += s0[j][0] = -y4 / 2;
  }
  none_default(series, order);
}

// node_modules/d3-shape/src/offset/wiggle.js
function wiggle_default(series, order) {
  if (!((n = series.length) > 0) || !((m3 = (s0 = series[order[0]]).length) > 0)) return;
  for (var y4 = 0, j = 1, s0, m3, n; j < m3; ++j) {
    for (var i = 0, s1 = 0, s2 = 0; i < n; ++i) {
      var si = series[order[i]], sij0 = si[j][1] || 0, sij1 = si[j - 1][1] || 0, s3 = (sij0 - sij1) / 2;
      for (var k2 = 0; k2 < i; ++k2) {
        var sk = series[order[k2]], skj0 = sk[j][1] || 0, skj1 = sk[j - 1][1] || 0;
        s3 += skj0 - skj1;
      }
      s1 += sij0, s2 += s3 * sij0;
    }
    s0[j - 1][1] += s0[j - 1][0] = y4;
    if (s1) y4 -= s2 / s1;
  }
  s0[j - 1][1] += s0[j - 1][0] = y4;
  none_default(series, order);
}

// node_modules/d3-shape/src/order/appearance.js
function appearance_default(series) {
  var peaks = series.map(peak);
  return none_default2(series).sort(function(a4, b) {
    return peaks[a4] - peaks[b];
  });
}
function peak(series) {
  var i = -1, j = 0, n = series.length, vi, vj = -Infinity;
  while (++i < n) if ((vi = +series[i][1]) > vj) vj = vi, j = i;
  return j;
}

// node_modules/d3-shape/src/order/ascending.js
function ascending_default2(series) {
  var sums = series.map(sum3);
  return none_default2(series).sort(function(a4, b) {
    return sums[a4] - sums[b];
  });
}
function sum3(series) {
  var s2 = 0, i = -1, n = series.length, v2;
  while (++i < n) if (v2 = +series[i][1]) s2 += v2;
  return s2;
}

// node_modules/d3-shape/src/order/descending.js
function descending_default2(series) {
  return ascending_default2(series).reverse();
}

// node_modules/d3-shape/src/order/insideOut.js
function insideOut_default(series) {
  var n = series.length, i, j, sums = series.map(sum3), order = appearance_default(series), top2 = 0, bottom2 = 0, tops = [], bottoms = [];
  for (i = 0; i < n; ++i) {
    j = order[i];
    if (top2 < bottom2) {
      top2 += sums[j];
      tops.push(j);
    } else {
      bottom2 += sums[j];
      bottoms.push(j);
    }
  }
  return bottoms.reverse().concat(tops);
}

// node_modules/d3-shape/src/order/reverse.js
function reverse_default(series) {
  return none_default2(series).reverse();
}
export {
  Adder,
  Delaunay,
  FormatSpecifier,
  InternMap,
  InternSet,
  Node,
  Path,
  Voronoi,
  Transform as ZoomTransform,
  active_default as active,
  arc_default as arc,
  area_default5 as area,
  areaRadial_default as areaRadial,
  ascending,
  autoType,
  axisBottom,
  axisLeft,
  axisRight,
  axisTop,
  bin,
  bisect_default as bisect,
  bisectCenter,
  bisectLeft,
  bisectRight,
  bisector,
  blob_default as blob,
  blur,
  blur2,
  blurImage,
  brush_default as brush,
  brushSelection,
  brushX,
  brushY,
  buffer_default as buffer,
  chord_default as chord,
  chordDirected,
  chordTranspose,
  cluster_default as cluster,
  color,
  density_default as contourDensity,
  contours_default as contours,
  count,
  create_default as create,
  creator_default as creator,
  cross,
  csv2 as csv,
  csvFormat,
  csvFormatBody,
  csvFormatRow,
  csvFormatRows,
  csvFormatValue,
  csvParse,
  csvParseRows,
  cubehelix,
  cumsum,
  basis_default2 as curveBasis,
  basisClosed_default2 as curveBasisClosed,
  basisOpen_default as curveBasisOpen,
  bumpX as curveBumpX,
  bumpY as curveBumpY,
  bundle_default as curveBundle,
  cardinal_default as curveCardinal,
  cardinalClosed_default as curveCardinalClosed,
  cardinalOpen_default as curveCardinalOpen,
  catmullRom_default as curveCatmullRom,
  catmullRomClosed_default as curveCatmullRomClosed,
  catmullRomOpen_default as curveCatmullRomOpen,
  linear_default as curveLinear,
  linearClosed_default as curveLinearClosed,
  monotoneX as curveMonotoneX,
  monotoneY as curveMonotoneY,
  natural_default as curveNatural,
  step_default as curveStep,
  stepAfter as curveStepAfter,
  stepBefore as curveStepBefore,
  descending,
  deviation,
  difference,
  disjoint,
  dispatch_default as dispatch,
  drag_default as drag,
  nodrag_default as dragDisable,
  yesdrag as dragEnable,
  dsv,
  dsv_default as dsvFormat,
  backInOut as easeBack,
  backIn as easeBackIn,
  backInOut as easeBackInOut,
  backOut as easeBackOut,
  bounceOut as easeBounce,
  bounceIn as easeBounceIn,
  bounceInOut as easeBounceInOut,
  bounceOut as easeBounceOut,
  circleInOut as easeCircle,
  circleIn as easeCircleIn,
  circleInOut as easeCircleInOut,
  circleOut as easeCircleOut,
  cubicInOut as easeCubic,
  cubicIn as easeCubicIn,
  cubicInOut as easeCubicInOut,
  cubicOut as easeCubicOut,
  elasticOut as easeElastic,
  elasticIn as easeElasticIn,
  elasticInOut as easeElasticInOut,
  elasticOut as easeElasticOut,
  expInOut as easeExp,
  expIn as easeExpIn,
  expInOut as easeExpInOut,
  expOut as easeExpOut,
  linear as easeLinear,
  polyInOut as easePoly,
  polyIn as easePolyIn,
  polyInOut as easePolyInOut,
  polyOut as easePolyOut,
  quadInOut as easeQuad,
  quadIn as easeQuadIn,
  quadInOut as easeQuadInOut,
  quadOut as easeQuadOut,
  sinInOut as easeSin,
  sinIn as easeSinIn,
  sinInOut as easeSinInOut,
  sinOut as easeSinOut,
  every,
  extent,
  fcumsum,
  filter,
  flatGroup,
  flatRollup,
  center_default as forceCenter,
  collide_default as forceCollide,
  link_default as forceLink,
  manyBody_default as forceManyBody,
  radial_default as forceRadial,
  simulation_default as forceSimulation,
  x_default2 as forceX,
  y_default2 as forceY,
  format,
  defaultLocale as formatDefaultLocale,
  locale_default as formatLocale,
  formatPrefix,
  formatSpecifier,
  fsum,
  albers_default as geoAlbers,
  albersUsa_default as geoAlbersUsa,
  area_default2 as geoArea,
  azimuthalEqualArea_default as geoAzimuthalEqualArea,
  azimuthalEqualAreaRaw as geoAzimuthalEqualAreaRaw,
  azimuthalEquidistant_default as geoAzimuthalEquidistant,
  azimuthalEquidistantRaw as geoAzimuthalEquidistantRaw,
  bounds_default as geoBounds,
  centroid_default as geoCentroid,
  circle_default as geoCircle,
  antimeridian_default as geoClipAntimeridian,
  circle_default2 as geoClipCircle,
  extent_default2 as geoClipExtent,
  clipRectangle as geoClipRectangle,
  conicConformal_default as geoConicConformal,
  conicConformalRaw as geoConicConformalRaw,
  conicEqualArea_default as geoConicEqualArea,
  conicEqualAreaRaw as geoConicEqualAreaRaw,
  conicEquidistant_default as geoConicEquidistant,
  conicEquidistantRaw as geoConicEquidistantRaw,
  contains_default2 as geoContains,
  distance_default as geoDistance,
  equalEarth_default as geoEqualEarth,
  equalEarthRaw as geoEqualEarthRaw,
  equirectangular_default as geoEquirectangular,
  equirectangularRaw as geoEquirectangularRaw,
  gnomonic_default as geoGnomonic,
  gnomonicRaw as geoGnomonicRaw,
  graticule as geoGraticule,
  graticule10 as geoGraticule10,
  identity_default4 as geoIdentity,
  interpolate_default as geoInterpolate,
  length_default as geoLength,
  mercator_default as geoMercator,
  mercatorRaw as geoMercatorRaw,
  naturalEarth1_default as geoNaturalEarth1,
  naturalEarth1Raw as geoNaturalEarth1Raw,
  orthographic_default as geoOrthographic,
  orthographicRaw as geoOrthographicRaw,
  path_default as geoPath,
  projection as geoProjection,
  projectionMutator as geoProjectionMutator,
  rotation_default as geoRotation,
  stereographic_default as geoStereographic,
  stereographicRaw as geoStereographicRaw,
  stream_default as geoStream,
  transform_default as geoTransform,
  transverseMercator_default as geoTransverseMercator,
  transverseMercatorRaw as geoTransverseMercatorRaw,
  gray,
  greatest,
  greatestIndex,
  group,
  groupSort,
  groups,
  hcl,
  hierarchy,
  bin as histogram,
  hsl,
  html,
  image_default as image,
  index,
  indexes,
  value_default as interpolate,
  array_default as interpolateArray,
  basis_default as interpolateBasis,
  basisClosed_default as interpolateBasisClosed,
  Blues_default as interpolateBlues,
  BrBG_default as interpolateBrBG,
  BuGn_default as interpolateBuGn,
  BuPu_default as interpolateBuPu,
  cividis_default as interpolateCividis,
  cool as interpolateCool,
  cubehelix_default as interpolateCubehelix,
  cubehelix_default2 as interpolateCubehelixDefault,
  cubehelixLong as interpolateCubehelixLong,
  date_default as interpolateDate,
  discrete_default as interpolateDiscrete,
  GnBu_default as interpolateGnBu,
  Greens_default as interpolateGreens,
  Greys_default as interpolateGreys,
  hcl_default as interpolateHcl,
  hclLong as interpolateHclLong,
  hsl_default as interpolateHsl,
  hslLong as interpolateHslLong,
  hue_default as interpolateHue,
  inferno as interpolateInferno,
  lab2 as interpolateLab,
  magma as interpolateMagma,
  number_default as interpolateNumber,
  numberArray_default as interpolateNumberArray,
  object_default as interpolateObject,
  OrRd_default as interpolateOrRd,
  Oranges_default as interpolateOranges,
  PRGn_default as interpolatePRGn,
  PiYG_default as interpolatePiYG,
  plasma as interpolatePlasma,
  PuBu_default as interpolatePuBu,
  PuBuGn_default as interpolatePuBuGn,
  PuOr_default as interpolatePuOr,
  PuRd_default as interpolatePuRd,
  Purples_default as interpolatePurples,
  rainbow_default as interpolateRainbow,
  RdBu_default as interpolateRdBu,
  RdGy_default as interpolateRdGy,
  RdPu_default as interpolateRdPu,
  RdYlBu_default as interpolateRdYlBu,
  RdYlGn_default as interpolateRdYlGn,
  Reds_default as interpolateReds,
  rgb_default as interpolateRgb,
  rgbBasis as interpolateRgbBasis,
  rgbBasisClosed as interpolateRgbBasisClosed,
  round_default as interpolateRound,
  sinebow_default as interpolateSinebow,
  Spectral_default as interpolateSpectral,
  string_default as interpolateString,
  interpolateTransformCss,
  interpolateTransformSvg,
  turbo_default as interpolateTurbo,
  viridis_default as interpolateViridis,
  warm as interpolateWarm,
  YlGn_default as interpolateYlGn,
  YlGnBu_default as interpolateYlGnBu,
  YlOrBr_default as interpolateYlOrBr,
  YlOrRd_default as interpolateYlOrRd,
  zoom_default as interpolateZoom,
  interrupt_default as interrupt,
  intersection,
  interval_default as interval,
  isoFormat_default as isoFormat,
  isoParse_default as isoParse,
  json_default as json,
  lab,
  lch,
  least,
  leastIndex,
  line_default2 as line,
  lineRadial_default as lineRadial,
  link2 as link,
  linkHorizontal,
  linkRadial,
  linkVertical,
  local,
  map2 as map,
  matcher_default as matcher,
  max,
  maxIndex,
  mean,
  median,
  medianIndex,
  merge,
  min,
  minIndex,
  mode,
  namespace_default as namespace,
  namespaces_default as namespaces,
  nice,
  now,
  pack_default as pack,
  enclose_default as packEnclose,
  siblings_default as packSiblings,
  pairs,
  partition_default as partition,
  path,
  pathRound,
  permute,
  pie_default as pie,
  piecewise,
  pointRadial_default as pointRadial,
  pointer_default as pointer,
  pointers_default as pointers,
  area_default4 as polygonArea,
  centroid_default3 as polygonCentroid,
  contains_default3 as polygonContains,
  hull_default as polygonHull,
  length_default2 as polygonLength,
  precisionFixed_default as precisionFixed,
  precisionPrefix_default as precisionPrefix,
  precisionRound_default as precisionRound,
  quadtree,
  quantile,
  quantileIndex,
  quantileSorted,
  quantize_default as quantize,
  quickselect,
  areaRadial_default as radialArea,
  lineRadial_default as radialLine,
  bates_default as randomBates,
  bernoulli_default as randomBernoulli,
  beta_default as randomBeta,
  binomial_default as randomBinomial,
  cauchy_default as randomCauchy,
  exponential_default as randomExponential,
  gamma_default as randomGamma,
  geometric_default as randomGeometric,
  int_default as randomInt,
  irwinHall_default as randomIrwinHall,
  lcg as randomLcg,
  logNormal_default as randomLogNormal,
  logistic_default as randomLogistic,
  normal_default as randomNormal,
  pareto_default as randomPareto,
  poisson_default as randomPoisson,
  uniform_default as randomUniform,
  weibull_default as randomWeibull,
  range,
  rank,
  reduce,
  reverse,
  rgb,
  ribbon_default as ribbon,
  ribbonArrow,
  rollup,
  rollups,
  band as scaleBand,
  diverging as scaleDiverging,
  divergingLog as scaleDivergingLog,
  divergingPow as scaleDivergingPow,
  divergingSqrt as scaleDivergingSqrt,
  divergingSymlog as scaleDivergingSymlog,
  identity4 as scaleIdentity,
  implicit as scaleImplicit,
  linear2 as scaleLinear,
  log2 as scaleLog,
  ordinal as scaleOrdinal,
  point as scalePoint,
  pow3 as scalePow,
  quantile2 as scaleQuantile,
  quantize as scaleQuantize,
  radial as scaleRadial,
  sequential as scaleSequential,
  sequentialLog as scaleSequentialLog,
  sequentialPow as scaleSequentialPow,
  sequentialQuantile as scaleSequentialQuantile,
  sequentialSqrt as scaleSequentialSqrt,
  sequentialSymlog as scaleSequentialSymlog,
  sqrt2 as scaleSqrt,
  symlog as scaleSymlog,
  threshold as scaleThreshold,
  time as scaleTime,
  utcTime as scaleUtc,
  scan,
  Accent_default as schemeAccent,
  scheme22 as schemeBlues,
  scheme as schemeBrBG,
  scheme10 as schemeBuGn,
  scheme11 as schemeBuPu,
  category10_default as schemeCategory10,
  Dark2_default as schemeDark2,
  scheme12 as schemeGnBu,
  scheme23 as schemeGreens,
  scheme24 as schemeGreys,
  observable10_default as schemeObservable10,
  scheme13 as schemeOrRd,
  scheme27 as schemeOranges,
  scheme2 as schemePRGn,
  Paired_default as schemePaired,
  Pastel1_default as schemePastel1,
  Pastel2_default as schemePastel2,
  scheme3 as schemePiYG,
  scheme15 as schemePuBu,
  scheme14 as schemePuBuGn,
  scheme4 as schemePuOr,
  scheme16 as schemePuRd,
  scheme25 as schemePurples,
  scheme5 as schemeRdBu,
  scheme6 as schemeRdGy,
  scheme17 as schemeRdPu,
  scheme7 as schemeRdYlBu,
  scheme8 as schemeRdYlGn,
  scheme26 as schemeReds,
  Set1_default as schemeSet1,
  Set2_default as schemeSet2,
  Set3_default as schemeSet3,
  scheme9 as schemeSpectral,
  Tableau10_default as schemeTableau10,
  scheme19 as schemeYlGn,
  scheme18 as schemeYlGnBu,
  scheme20 as schemeYlOrBr,
  scheme21 as schemeYlOrRd,
  select_default as select,
  selectAll_default as selectAll,
  selection_default as selection,
  selector_default as selector,
  selectorAll_default as selectorAll,
  shuffle_default as shuffle,
  shuffler,
  some,
  sort,
  stack_default as stack,
  diverging_default as stackOffsetDiverging,
  expand_default as stackOffsetExpand,
  none_default as stackOffsetNone,
  silhouette_default as stackOffsetSilhouette,
  wiggle_default as stackOffsetWiggle,
  appearance_default as stackOrderAppearance,
  ascending_default2 as stackOrderAscending,
  descending_default2 as stackOrderDescending,
  insideOut_default as stackOrderInsideOut,
  none_default2 as stackOrderNone,
  reverse_default as stackOrderReverse,
  stratify_default as stratify,
  styleValue as style,
  subset,
  sum,
  superset,
  svg,
  Symbol2 as symbol,
  asterisk_default as symbolAsterisk,
  circle_default3 as symbolCircle,
  cross_default2 as symbolCross,
  diamond_default as symbolDiamond,
  diamond2_default as symbolDiamond2,
  plus_default as symbolPlus,
  square_default as symbolSquare,
  square2_default as symbolSquare2,
  star_default as symbolStar,
  times_default as symbolTimes,
  triangle_default as symbolTriangle,
  triangle2_default as symbolTriangle2,
  wye_default as symbolWye,
  times_default as symbolX,
  symbolsFill as symbols,
  symbolsFill,
  symbolsStroke,
  text_default as text,
  thresholdFreedmanDiaconis,
  thresholdScott,
  thresholdSturges,
  tickFormat,
  tickIncrement,
  tickStep,
  ticks,
  timeDay,
  timeDays,
  timeFormat,
  defaultLocale2 as timeFormatDefaultLocale,
  formatLocale as timeFormatLocale,
  timeFriday,
  timeFridays,
  timeHour,
  timeHours,
  timeInterval,
  millisecond as timeMillisecond,
  milliseconds as timeMilliseconds,
  timeMinute,
  timeMinutes,
  timeMonday,
  timeMondays,
  timeMonth,
  timeMonths,
  timeParse,
  timeSaturday,
  timeSaturdays,
  second as timeSecond,
  seconds as timeSeconds,
  timeSunday,
  timeSundays,
  timeThursday,
  timeThursdays,
  timeTickInterval,
  timeTicks,
  timeTuesday,
  timeTuesdays,
  timeWednesday,
  timeWednesdays,
  timeSunday as timeWeek,
  timeSundays as timeWeeks,
  timeYear,
  timeYears,
  timeout_default as timeout,
  timer,
  timerFlush,
  transition,
  transpose,
  tree_default as tree,
  treemap_default as treemap,
  binary_default as treemapBinary,
  dice_default as treemapDice,
  resquarify_default as treemapResquarify,
  slice_default as treemapSlice,
  sliceDice_default as treemapSliceDice,
  squarify_default as treemapSquarify,
  tsv2 as tsv,
  tsvFormat,
  tsvFormatBody,
  tsvFormatRow,
  tsvFormatRows,
  tsvFormatValue,
  tsvParse,
  tsvParseRows,
  union,
  unixDay,
  unixDays,
  utcDay,
  utcDays,
  utcFormat,
  utcFriday,
  utcFridays,
  utcHour,
  utcHours,
  millisecond as utcMillisecond,
  milliseconds as utcMilliseconds,
  utcMinute,
  utcMinutes,
  utcMonday,
  utcMondays,
  utcMonth,
  utcMonths,
  utcParse,
  utcSaturday,
  utcSaturdays,
  second as utcSecond,
  seconds as utcSeconds,
  utcSunday,
  utcSundays,
  utcThursday,
  utcThursdays,
  utcTickInterval,
  utcTicks,
  utcTuesday,
  utcTuesdays,
  utcWednesday,
  utcWednesdays,
  utcSunday as utcWeek,
  utcSundays as utcWeeks,
  utcYear,
  utcYears,
  variance,
  window_default as window,
  xml_default as xml,
  zip,
  zoom_default2 as zoom,
  identity as zoomIdentity,
  transform as zoomTransform
};
//# sourceMappingURL=d3.js.map
