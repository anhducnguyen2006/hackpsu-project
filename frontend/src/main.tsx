import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/foundation.css";
import "./styles/landing.css";

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
