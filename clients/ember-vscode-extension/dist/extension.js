"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
let apiHost = 'http://127.0.0.1:8000';
let apiKey = 'ember-secret-key-123';
let lastSentTime = 0;
const THROTTLE_MS = 2000; // Only sync editor changes at most every 2 seconds to save bandwidth
function activate(context) {
    console.log('Ember Companion VS Code Extension is now active!');
    // Read initial settings
    updateConfig();
    // Register configuration change listener
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(e => {
        if (e.affectsConfiguration('ember')) {
            updateConfig();
        }
    }));
    // Register active editor listeners
    context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(editor => {
        if (editor) {
            syncEditorContext(editor);
        }
    }));
    context.subscriptions.push(vscode.window.onDidChangeTextEditorSelection(event => {
        if (event.textEditor) {
            syncEditorContext(event.textEditor);
        }
    }));
    // Register Task End listener (detect build/compilation errors)
    context.subscriptions.push(vscode.tasks.onDidEndTaskProcess(event => {
        const exitCode = event.exitCode;
        if (exitCode !== undefined && exitCode !== 0) {
            const taskName = event.execution.task.name;
            handleBuildError(taskName, exitCode);
        }
    }));
    // Register Commands
    context.subscriptions.push(vscode.commands.registerCommand('ember.syncWorkspace', () => {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            syncEditorContext(editor, true);
            vscode.window.showInformationMessage('Synced workspace context with Ember.');
        }
        else {
            vscode.window.showWarningMessage('No active editor open to sync.');
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('ember.explainCode', async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            return;
        }
        const selection = editor.selection;
        const text = editor.document.getText(selection);
        if (!text) {
            vscode.window.showWarningMessage('Please select some code to explain.');
            return;
        }
        vscode.window.showInformationMessage('Sending code to Ember...');
        await sendCommandToEmber(`Hey Ember, can you explain this code snippet:\n\`\`\`${editor.document.languageId}\n${text}\n\`\`\``);
    }));
    // Initial sync
    if (vscode.window.activeTextEditor) {
        syncEditorContext(vscode.window.activeTextEditor);
    }
}
function updateConfig() {
    const config = vscode.workspace.getConfiguration('ember');
    apiHost = config.get('apiHost') || 'http://127.0.0.1:8000';
    apiKey = config.get('apiKey') || 'ember-secret-key-123';
}
async function syncEditorContext(editor, force = false) {
    const now = Date.now();
    if (!force && now - lastSentTime < THROTTLE_MS) {
        return;
    }
    lastSentTime = now;
    const doc = editor.document;
    const selection = editor.selection;
    // Grab basic context
    const filepath = doc.uri.fsPath;
    const language = doc.languageId;
    const activeLine = selection.active.line + 1; // 1-indexed for human readability
    const totalLines = doc.lineCount;
    const selectedText = doc.getText(selection);
    // Extract small window of code context around the cursor line (10 lines above and below)
    const startLine = Math.max(0, activeLine - 10);
    const endLine = Math.min(totalLines - 1, activeLine + 10);
    let codeContext = '';
    for (let i = startLine; i <= endLine; i++) {
        const line = doc.lineAt(i);
        const prefix = (i + 1) === activeLine ? '=> ' : '   ';
        codeContext += `${prefix}${i + 1}: ${line.text}\n`;
    }
    const payload = {
        filepath,
        language,
        activeLine,
        totalLines,
        selectedText,
        codeContext
    };
    try {
        const url = `${apiHost.replace(/\/$/, '')}/editor_context`;
        await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': apiKey
            },
            body: JSON.stringify(payload)
        });
    }
    catch (err) {
        // Fail silently in background
        console.error('Failed to sync context to Ember API:', err.message);
    }
}
async function handleBuildError(taskName, exitCode) {
    // Send a system trigger warning about the build task failure
    const errorText = `[SYSTEM NOTIFICATION: The user just ran a build task named '${taskName}' which failed with exit code ${exitCode}. Please alert Chris immediately, tease him slightly, and offer to help debug it!]`;
    await sendCommandToEmber(errorText);
}
async function sendCommandToEmber(text) {
    try {
        const url = `${apiHost.replace(/\/$/, '')}/api/remote_command`;
        await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': apiKey
            },
            body: JSON.stringify({ text })
        });
    }
    catch (err) {
        console.error('Failed to send command to Ember:', err.message);
    }
}
function deactivate() { }
//# sourceMappingURL=extension.js.map