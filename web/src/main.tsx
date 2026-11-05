import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { applyTheme, savedTheme } from "./lib/theme";
import "./styles/index.css";

applyTheme(savedTheme());   // before the first paint, so a dark theme doesn't flash light

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
