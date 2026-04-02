/**
 * App.tsx — Root application component.
 *
 * Sets up routing and wraps the app in the WalletProvider context.
 * The landing page is the CharacterCreationFlow — the funnel starts
 * immediately when a user arrives.
 */

import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { WalletProvider } from "./components/WalletProvider/WalletProvider";
import { CharacterCreationFlow } from "./components/CharacterCreation/CharacterCreationFlow";

// Global reset styles (injected as a style tag for this tutorial;
// use a CSS file or CSS-in-JS library in production).
const globalStyles = `
  *, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    background: #0a0a0f;
    color: #fff;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing: antialiased;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`;

export default function App() {
  return (
    <>
      {/* Inject global styles */}
      <style>{globalStyles}</style>

      {/* WalletProvider wraps everything so any component can access
          wallet state without prop drilling. */}
      <WalletProvider>
        <BrowserRouter>
          <Routes>
            {/* Main funnel — the landing experience */}
            <Route path="/" element={<CharacterCreationFlow />} />

            {/* Future routes */}
            {/* <Route path="/gallery" element={<Gallery />} /> */}
            {/* <Route path="/character/:id" element={<CharacterDetail />} /> */}

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </WalletProvider>
    </>
  );
}
