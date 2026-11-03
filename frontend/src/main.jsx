import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Configure Monaco Editor environment so web workers load correctly under Vite.
if (typeof window !== 'undefined') {
  window.MonacoEnvironment = {
    getWorkerUrl: function (moduleId, label) {
      if (label === 'editor') {
        return '';
      }
      // Build a blob URL for language/worker scripts so they load in Vite.
      const workerTypes = {
        css: 'css',
        js: 'javascript',
        ts: 'typescript',
        html: 'html',
        json: 'json',
      };
      const lang = workerTypes[label] || 'javascript';
      const blob = new Blob(
        [`importScripts('https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs/editor/editor.main.nls.js');importScripts('https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs/editor/editor.main.js');`],
        { type: 'application/javascript' }
      );
      return URL.createObjectURL(blob);
    },
  };
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);