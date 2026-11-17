import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Observatory } from "./components/observatory/shell";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Observatory />
  </StrictMode>,
);

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {
      /* Local records still save; offline shell availability is not assumed. */
    });
  });
}
