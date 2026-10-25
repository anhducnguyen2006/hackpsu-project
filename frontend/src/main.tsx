import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/foundation.css";
import "./styles/landing.css";
import "./styles/workspace.css";
import "./styles/graph.css";
import "./styles/analysis.css";

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
