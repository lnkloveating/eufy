import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";

import "./styles/fonts.css";
import "./styles/tokens.css";
import "./styles/globals.css";
import "./styles/components.css";
import "./styles/research.css";
import "./styles/validation.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root element #root not found");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
