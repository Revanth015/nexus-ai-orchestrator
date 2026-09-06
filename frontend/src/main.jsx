import React from "react";
import { createRoot } from "react-dom/client";
import NexusWorkspace from "./NexusWorkspace";
import "./styles.css";
import "./workspace.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <NexusWorkspace />
  </React.StrictMode>
);
