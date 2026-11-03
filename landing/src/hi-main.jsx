import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import HindiPage from "./HindiPage.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <HindiPage />
  </StrictMode>
);
