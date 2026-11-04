// A tiny inline-SVG sparkline (no libraries). sparkPoints is pure, for tests.

const r2 = (v) => Math.round(v * 100) / 100;

/** Polyline points for `values` in a w×h box with `pad` inside; zeroY is the y of
 *  the zero line when the values cross zero, else null. */
export function sparkPoints(values, w, h, pad = 2) {
  const n = values.length;
  if (!n) return { points: [], zeroY: null };
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min;
  const y = (v) => (span ? pad + ((max - v) / span) * (h - 2 * pad) : h / 2);
  const x = (i) => (n > 1 ? pad + (i * (w - 2 * pad)) / (n - 1) : w / 2);
  return {
    points: values.map((v, i) => [r2(x(i)), r2(y(v))]),
    zeroY: min < 0 && max > 0 ? r2(y(0)) : null,
  };
}

/** <svg> sparkline of `values`, the last point marked. */
export function sparkline(values, opts = {}) {
  const { w = 120, h = 32, pad = 3, label = "" } = opts;
  const NS = "http://www.w3.org/2000/svg";
  const make = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
    return e;
  };
  const svg = make("svg", { class: "spark", viewBox: `0 0 ${w} ${h}`, width: w, height: h,
    role: "img", "aria-label": label || `trend over ${values.length} games` });
  const { points, zeroY } = sparkPoints(values, w, h, pad);
  if (zeroY !== null) svg.append(make("line", { class: "spark-zero", x1: 0, x2: w, y1: zeroY, y2: zeroY }));
  if (points.length > 1) {
    svg.append(make("polyline", { class: "spark-line", points: points.map((p) => p.join(",")).join(" ") }));
  }
  const last = points[points.length - 1];
  if (last) svg.append(make("circle", { class: "spark-dot", cx: last[0], cy: last[1], r: 2.5 }));
  return svg;
}
