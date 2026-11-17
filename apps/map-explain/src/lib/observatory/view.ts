import { positions, type Layer } from "./model.js";

/** Iterate across layers so valid large projects do not hit JS argument limits. */
export function mapFrame(layers: Layer[]) {
  let x0 = Infinity,
    x1 = -Infinity,
    y0 = Infinity,
    y1 = -Infinity;
  for (const layer of layers)
    for (const feature of layer.features) {
      for (const [x, y] of positions(feature.geometry)) {
        x0 = Math.min(x0, x);
        x1 = Math.max(x1, x);
        y0 = Math.min(y0, y);
        y1 = Math.max(y1, y);
      }
    }
  if (x0 === Infinity) {
    x0 = -71.46;
    x1 = -71.36;
    y0 = 41.79;
    y1 = 41.86;
  }
  const cos = Math.max(0.05, Math.cos((((y0 + y1) / 2) * Math.PI) / 180));
  const scale = Math.min(
    820 / Math.max((x1 - x0) * cos, 0.005),
    500 / Math.max(y1 - y0, 0.005),
  );
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, cos, scale };
}
