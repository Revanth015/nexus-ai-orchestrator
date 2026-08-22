import React from "react";
import { createRoot } from "react-dom/client";
import ManagerDashboard from "./ManagerDashboard";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ManagerDashboard />
  </React.StrictMode>
);
