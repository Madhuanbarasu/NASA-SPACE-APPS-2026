import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/app.css";
import "ol/ol.css";
import App from "./App";
import { S } from "./i18n";
import { StoreProvider } from "./state/store";

document.title = S.app.documentTitle; // same text as the static <title> in index.html (checked by check:strings)

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <StoreProvider>
      <App />
    </StoreProvider>
  </StrictMode>,
);
