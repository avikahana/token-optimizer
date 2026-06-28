import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath } from "node:url";

const SERVER_NAME = "Token Optimizer Hook Control";
const STATUS_TOOL = "token_optimizer_hook_status";
const TOGGLE_TOOL = "token_optimizer_hook_toggle";
const APP_TOOL = "token_optimizer_hook_control_app";
const APPLY_TOOL = "token_optimizer_hook_apply";
const MANAGED_MARKER = "TOKEN_OPTIMIZER_MANAGED";
const HOOK_MODE = "inactive-placeholder-v1";
const MANAGED_COMMAND =
  `token-optimizer summarize --hook stop --hook-mode ${HOOK_MODE}`;
const LEGACY_MANAGED_COMMAND = "token-optimizer summarize --hook stop";
const HOOK_WARNING =
  "Stop-hook entry installation is experimental in 0.1.0 and invokes an intentionally no-op command; use hook control only after reviewing the dry-run plan.";
const SERVER_DIR = path.dirname(fileURLToPath(import.meta.url));
const WIDGET_URI = "ui://token-optimizer/hook-control.html";
const WIDGET_MIME_TYPE = "text/html;profile=mcp-app";
const REQUEST_TIMEOUT_MS = 30000;

const JsonRpcError = {
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
};

let nextRequestId = 1;
const pendingRequests = new Map();

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function sendResult(id, result) {
  send({ jsonrpc: "2.0", id, result });
}

function sendError(id, code, message) {
  send({ jsonrpc: "2.0", id, error: { code, message } });
}

function request(method, params) {
  const id = `server-${nextRequestId++}`;
  send({ jsonrpc: "2.0", id, method, params });
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      if (pendingRequests.delete(id)) {
        reject(new Error(`${method} timed out before the host responded.`));
      }
    }, REQUEST_TIMEOUT_MS);
    pendingRequests.set(id, {
      resolve: (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      reject: (error) => {
        clearTimeout(timer);
        reject(error);
      },
    });
  });
}

function rejectPendingRequests(error) {
  for (const [, pending] of pendingRequests) {
    pending.reject(error);
  }
  pendingRequests.clear();
}

function logProtocolWarning(message) {
  process.stderr.write(`[token-optimizer-mcp] ${message}\n`);
}

function requireProjectPath(value) {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error("projectPath must be a non-empty absolute project path.");
  }
  const project = path.resolve(value);
  if (!fs.existsSync(project) || !fs.statSync(project).isDirectory()) {
    throw new Error(`projectPath must be an existing directory: ${project}`);
  }
  return project;
}

function hooksPathFor(project) {
  const hooksPath = path.resolve(project, ".codex", "hooks.json");
  const relative = path.relative(project, hooksPath);
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    throw new Error("hooks path must stay inside the selected project.");
  }
  const codexDir = path.join(project, ".codex");
  if (fs.existsSync(codexDir) && fs.lstatSync(codexDir).isSymbolicLink()) {
    throw new Error(".codex must not be a symlink.");
  }
  if (fs.existsSync(hooksPath)) {
    const stat = fs.lstatSync(hooksPath);
    if (stat.isSymbolicLink()) {
      throw new Error(".codex/hooks.json must not be a symlink.");
    }
    if (!stat.isFile()) {
      throw new Error(`hooks path exists but is not a file: ${hooksPath}`);
    }
  }
  return hooksPath;
}

function managedBlock() {
  return {
    _tokenOptimizer: {
      marker: MANAGED_MARKER,
      profile: "quiet",
      feature: "experimental-stop-hook",
      behavior: HOOK_MODE,
      requiresFreshConsentForActiveBehavior: true,
      description:
        "Managed by Token Optimizer. Experimental Stop-hook entry invoking a no-op command; remove with uninstall.",
    },
    Stop: [
      {
        matcher: "*",
        hooks: [
          {
            type: "command",
            command: MANAGED_COMMAND,
            timeout: 30,
          },
        ],
      },
    ],
  };
}

function sortKeys(value) {
  if (Array.isArray(value)) {
    return value.map(sortKeys);
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, sortKeys(value[key])]),
    );
  }
  return value;
}

function renderHooksJson(document) {
  return JSON.stringify(sortKeys(document), null, 2);
}

function readExistingHooks(hooksPath) {
  if (!fs.existsSync(hooksPath)) {
    return null;
  }
  return fs.readFileSync(hooksPath, "utf8");
}

function parseHooksJson(contents) {
  let parsed;
  try {
    parsed = JSON.parse(contents);
  } catch (error) {
    throw new Error(`hooks JSON is invalid: ${error.message}`);
  }
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("hooks JSON must be an object.");
  }
  return parsed;
}

function isManagedMetadata(value) {
  return value !== null && typeof value === "object" && value.marker === MANAGED_MARKER;
}

function isManagedCommand(hook) {
  return (
    hook !== null &&
    typeof hook === "object" &&
    (hook.command === MANAGED_COMMAND || hook.command === LEGACY_MANAGED_COMMAND)
  );
}

function isManagedEntry(entry) {
  return (
    entry !== null &&
    typeof entry === "object" &&
    Array.isArray(entry.hooks) &&
    entry.hooks.some(isManagedCommand)
  );
}

function removeManagedBlocks(existing) {
  const document = existing === null ? {} : structuredClone(existing);
  const metadata = document._tokenOptimizer;
  if (!isManagedMetadata(metadata)) {
    return document;
  }
  delete document._tokenOptimizer;
  for (const event of Object.keys(document)) {
    if (!Array.isArray(document[event])) {
      continue;
    }
    const remaining = document[event].filter((entry) => !isManagedEntry(entry));
    if (remaining.length > 0) {
      document[event] = remaining;
    } else {
      delete document[event];
    }
  }
  return document;
}

function mergeManagedBlock(existing) {
  let document = existing === null ? {} : structuredClone(existing);
  const metadata = document._tokenOptimizer;
  if (metadata !== undefined && !isManagedMetadata(metadata)) {
    throw new Error("existing hooks document has foreign _tokenOptimizer metadata.");
  }
  document = removeManagedBlocks(document);
  const block = managedBlock();
  document._tokenOptimizer = block._tokenOptimizer;
  for (const [event, entries] of Object.entries(block)) {
    if (event === "_tokenOptimizer") {
      continue;
    }
    if (document[event] === undefined) {
      document[event] = [];
    }
    if (!Array.isArray(document[event])) {
      throw new Error(`existing hook event must be a list: ${event}`);
    }
    document[event].push(...structuredClone(entries));
  }
  return document;
}

function fileChangePlan(project, hooksPath, operation, action, experimental, before, after, warnings) {
  const plan = {
    project,
    hooksPath,
    operation,
    action,
    experimental,
    managedMarker: MANAGED_MARKER,
    wouldCreate: action === "create",
    wouldUpdate: action === "update",
    wouldRemove: action === "remove",
    unchanged: action === "unchanged",
    before,
    after,
    warnings,
  };
  plan.planDigest = planDigest(plan);
  return plan;
}

function planDigest(plan) {
  const digestPayload = {
    project: plan.project,
    hooksPath: plan.hooksPath,
    operation: plan.operation,
    action: plan.action,
    experimental: plan.experimental,
    managedMarker: plan.managedMarker,
    before: plan.before,
    after: plan.after,
    warnings: plan.warnings,
  };
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(digestPayload))
    .digest("hex");
}

function planInstall(project) {
  const hooksPath = hooksPathFor(project);
  const before = readExistingHooks(hooksPath);
  const existing = before === null ? null : parseHooksJson(before);
  const after = renderHooksJson(mergeManagedBlock(existing));
  const action = before === null ? "create" : before === after ? "unchanged" : "update";
  const warnings = [HOOK_WARNING];
  if (before !== null) {
    warnings.push(
      before.includes(MANAGED_MARKER)
        ? "Existing Token Optimizer managed marker found."
        : "Existing hooks file found; install will merge without overwriting user hooks.",
    );
  }
  return fileChangePlan(project, hooksPath, "install", action, true, before, after, warnings);
}

function planUninstall(project) {
  const hooksPath = hooksPathFor(project);
  const before = readExistingHooks(hooksPath);
  if (before === null) {
    return fileChangePlan(project, hooksPath, "uninstall", "unchanged", false, null, null, [
      "No hooks file found; nothing to uninstall.",
    ]);
  }
  const existing = parseHooksJson(before);
  const afterDocument = removeManagedBlocks(existing);
  if (JSON.stringify(afterDocument) === JSON.stringify(existing)) {
    return fileChangePlan(project, hooksPath, "uninstall", "unchanged", false, before, before, []);
  }
  if (Object.keys(afterDocument).length === 0) {
    return fileChangePlan(project, hooksPath, "uninstall", "remove", false, before, null, []);
  }
  return fileChangePlan(
    project,
    hooksPath,
    "uninstall",
    "update",
    false,
    before,
    renderHooksJson(afterDocument),
    [],
  );
}

function isInstalled(project) {
  const hooksPath = hooksPathFor(project);
  const before = readExistingHooks(hooksPath);
  if (before === null) {
    return false;
  }
  const existing = parseHooksJson(before);
  return isManagedMetadata(existing._tokenOptimizer);
}

function applyPlan(plan) {
  const before = readExistingHooks(plan.hooksPath);
  if (before !== plan.before) {
    throw new Error("hooks file changed since the hook-control plan was created.");
  }
  if (plan.action === "unchanged") {
    return;
  }
  if (plan.action === "remove") {
    if (fs.existsSync(plan.hooksPath)) {
      fs.unlinkSync(plan.hooksPath);
    }
    return;
  }
  if (plan.after === null) {
    throw new Error("planned hooks output is missing.");
  }
  fs.mkdirSync(path.dirname(plan.hooksPath), { recursive: true });
  fs.writeFileSync(plan.hooksPath, plan.after, "utf8");
}

function formatPlanSummary(plan) {
  const lines = [
    `Operation: ${plan.operation}`,
    `Target file: .codex/hooks.json`,
    `Action: ${plan.action}`,
  ];
  if (plan.wouldCreate) {
    lines.push("Result: create the Token Optimizer managed hook block.");
  } else if (plan.wouldUpdate) {
    lines.push("Result: update only the Token Optimizer managed hook block.");
  } else if (plan.wouldRemove) {
    lines.push("Result: remove only Token Optimizer managed hook content.");
  } else {
    lines.push("Result: no file change.");
  }
  if (plan.operation === "install") {
    lines.push(`Command: ${MANAGED_COMMAND}`);
  }
  if (plan.warnings.length > 0) {
    lines.push("Warnings:", ...plan.warnings.map((warning) => `- ${warning}`));
  }
  return lines.join("\n");
}

function toolResult(text, structuredContent, extra = {}) {
  return {
    content: [{ type: "text", text }],
    structuredContent,
    ...extra,
  };
}

function hookStatePayload(project) {
  const installed = isInstalled(project);
  return {
    status: installed ? "enabled" : "disabled",
    enabled: installed,
    projectPath: project,
    hooksPath: hooksPathFor(project),
    managedCommand: MANAGED_COMMAND,
    hookMode: HOOK_MODE,
    installPlan: planInstall(project),
    uninstallPlan: planUninstall(project),
  };
}

function readWidgetHtml() {
  return fs.readFileSync(path.join(SERVER_DIR, "hook-control-widget.html"), "utf8");
}

async function handleStatus(id, args) {
  const project = requireProjectPath(args.projectPath);
  const state = hookStatePayload(project);
  sendResult(
    id,
    toolResult(
      `Experimental Stop-hook entry is ${state.enabled ? "installed" : "not installed"} for ${project}.`,
      state,
    ),
  );
}

async function handleApp(id, args) {
  const project = requireProjectPath(args.projectPath);
  const state = hookStatePayload(project);
  sendResult(
    id,
    toolResult(
      `Opened Token Optimizer hook control app for ${project}. Current state: ${state.enabled ? "on" : "off"}.`,
      state,
      {
        _meta: {
          ui: { resourceUri: WIDGET_URI },
          "openai/outputTemplate": WIDGET_URI,
        },
      },
    ),
  );
}

async function handleApply(id, args) {
  const project = requireProjectPath(args.projectPath);
  const desiredEnabled = Boolean(args.enabled);
  const reviewedDryRun = Boolean(args.reviewedDryRun);
  const currentlyEnabled = isInstalled(project);
  const plan = desiredEnabled ? planInstall(project) : planUninstall(project);
  if (desiredEnabled !== currentlyEnabled && !reviewedDryRun) {
    sendResult(
      id,
      toolResult("No files were changed because dry-run approval was not checked.", {
        ...hookStatePayload(project),
        status: "not_approved",
        desiredEnabled,
      }),
    );
    return;
  }
  if (desiredEnabled !== currentlyEnabled && args.reviewedPlanDigest !== plan.planDigest) {
    sendResult(
      id,
      toolResult("No files were changed because the dry-run plan changed after review.", {
        ...hookStatePayload(project),
        status: "stale_plan",
        desiredEnabled,
        reviewedPlanDigest:
          typeof args.reviewedPlanDigest === "string" ? args.reviewedPlanDigest : null,
        currentPlanDigest: plan.planDigest,
      }),
    );
    return;
  }

  if (desiredEnabled !== currentlyEnabled) {
    const confirmation = await request("elicitation/create", {
      mode: "form",
      message: [
        "Token Optimizer hook-control app approval",
        "",
        `Project: ${project}`,
        `Requested state: ${desiredEnabled ? "installed" : "not installed"}`,
        "",
        formatPlanSummary(plan),
        "",
        "Approve only if this dry-run summary matches the change you reviewed in the app.",
      ].join("\n"),
      requestedSchema: {
        type: "object",
        properties: {
          approveChange: {
            type: "boolean",
            title: "I approve this project-local hook change",
            default: false,
          },
        },
        required: ["approveChange"],
      },
    });

    if (confirmation?.action !== "accept" || !confirmation.content?.approveChange) {
      sendResult(
        id,
        toolResult("Hook control approval was cancelled. No files were changed.", {
          ...hookStatePayload(project),
          status: "cancelled",
          desiredEnabled,
        }),
      );
      return;
    }
  }

  applyPlan(plan);
  const state = hookStatePayload(project);
  sendResult(
    id,
    toolResult(
      `Experimental Stop-hook entry is now ${state.enabled ? "installed" : "not installed"} for ${project}.`,
      {
        ...state,
        appliedPlan: plan,
      },
    ),
  );
}

async function handleToggle(id, args) {
  const project = requireProjectPath(args.projectPath);
  const currentlyEnabled = isInstalled(project);
  const enablePlan = planInstall(project);
  const disablePlan = planUninstall(project);
  const reviewText = [
    "Token Optimizer advanced hook control",
    "",
    `Project: ${project}`,
    `Current state: ${currentlyEnabled ? "on" : "off"}`,
    "",
    "This controls only the experimental Stop-hook entry for this project.",
    "Turning on installs a Token Optimizer managed block in .codex/hooks.json.",
    "The installed entry invokes an intentionally no-op command in 0.1.0.",
    "Turning off removes only Token Optimizer managed hook content.",
    "Future active Stop-hook behavior still requires fresh consent.",
    "",
    "If switched ON:",
    formatPlanSummary(enablePlan),
    "",
    "If switched OFF:",
    formatPlanSummary(disablePlan),
  ].join("\n");

  const elicitation = await request("elicitation/create", {
    mode: "form",
    message: reviewText,
    requestedSchema: {
      type: "object",
      properties: {
        enabled: {
          type: "boolean",
          title: "Install experimental no-op Stop-hook entry",
          default: currentlyEnabled,
        },
        reviewedDryRun: {
          type: "boolean",
          title: "I reviewed the dry-run plan and approve this project-local change",
          default: false,
        },
      },
      required: ["enabled", "reviewedDryRun"],
    },
  });

  if (elicitation?.action !== "accept") {
    sendResult(
      id,
      toolResult("Hook toggle was cancelled. No files were changed.", {
        status: "cancelled",
        action: elicitation?.action ?? "cancel",
        projectPath: project,
      }),
    );
    return;
  }

  const desiredEnabled = Boolean(elicitation.content?.enabled);
  const reviewedDryRun = Boolean(elicitation.content?.reviewedDryRun);
  if (desiredEnabled !== currentlyEnabled && !reviewedDryRun) {
    sendResult(
      id,
      toolResult("No files were changed because dry-run approval was not checked.", {
        status: "not_approved",
        projectPath: project,
        desiredEnabled,
      }),
    );
    return;
  }

  const plan = desiredEnabled ? enablePlan : disablePlan;
  applyPlan(plan);
  sendResult(
    id,
    toolResult(
      `Experimental Stop-hook entry is now ${desiredEnabled ? "installed" : "not installed"} for ${project}.`,
      {
        status: desiredEnabled ? "enabled" : "disabled",
        projectPath: project,
        hooksPath: hooksPathFor(project),
        appliedPlan: plan,
      },
    ),
  );
}

async function handleToolCall(id, params) {
  const args = params?.arguments ?? {};
  if (params?.name === STATUS_TOOL) {
    await handleStatus(id, args);
    return;
  }
  if (params?.name === TOGGLE_TOOL) {
    await handleToggle(id, args);
    return;
  }
  if (params?.name === APP_TOOL) {
    await handleApp(id, args);
    return;
  }
  if (params?.name === APPLY_TOOL) {
    await handleApply(id, args);
    return;
  }
  sendError(id, JsonRpcError.METHOD_NOT_FOUND, `Unknown tool: ${params?.name ?? ""}`);
}

async function handleRequest(message) {
  const { id, method, params } = message;

  if (method === "initialize") {
    sendResult(id, {
      protocolVersion: params?.protocolVersion ?? "2025-11-25",
      capabilities: { tools: {}, resources: {} },
      serverInfo: {
        name: SERVER_NAME,
        version: "0.1.0",
      },
      instructions:
        "Use token_optimizer_hook_control_app for Token Optimizer hook control when MCP UI resources are available; use token_optimizer_hook_toggle as the native approval-form fallback. Both control only the project-local experimental Stop-hook entry, whose command is intentionally no-op in 0.1.0, and write .codex/hooks.json only after dry-run approval.",
    });
    return;
  }

  if (method === "ping") {
    sendResult(id, {});
    return;
  }

  if (method === "tools/list") {
    sendResult(id, {
      tools: [
        {
          name: STATUS_TOOL,
          title: "Token Optimizer Hook Status",
          description:
            "Read the Token Optimizer experimental Stop-hook entry status for a project.",
          inputSchema: {
            type: "object",
            properties: {
              projectPath: {
                type: "string",
                description:
                  "Absolute path to the project whose .codex/hooks.json should be inspected.",
              },
            },
            required: ["projectPath"],
          },
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
        },
        {
          name: TOGGLE_TOOL,
          title: "Token Optimizer Hook Toggle",
          description:
            "Open a native approval form for the experimental no-op Stop-hook entry. Writes only after dry-run review is checked.",
          inputSchema: {
            type: "object",
            properties: {
              projectPath: {
                type: "string",
                description:
                  "Absolute path to the project whose .codex/hooks.json should be updated.",
              },
            },
            required: ["projectPath"],
          },
          annotations: {
            readOnlyHint: false,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
        },
        {
          name: APP_TOOL,
          title: "Token Optimizer Hook Control App",
          description:
            "Open an interactive app for reviewing and installing or removing Token Optimizer's experimental no-op Stop-hook entry for a project.",
          inputSchema: {
            type: "object",
            properties: {
              projectPath: {
                type: "string",
                description:
                  "Absolute path to the project whose .codex/hooks.json should be inspected and optionally updated.",
              },
            },
            required: ["projectPath"],
          },
          annotations: {
            readOnlyHint: true,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          _meta: {
            ui: { resourceUri: WIDGET_URI },
            "openai/outputTemplate": WIDGET_URI,
            "openai/toolInvocation/invoking": "Opening Token Optimizer hook control",
            "openai/toolInvocation/invoked": "Token Optimizer hook control ready",
          },
        },
        {
          name: APPLY_TOOL,
          title: "Token Optimizer Apply Hook Toggle",
          description:
            "Apply the app-approved experimental no-op Stop-hook entry change for a project.",
          inputSchema: {
            type: "object",
            properties: {
              projectPath: {
                type: "string",
                description:
                  "Absolute path to the project whose .codex/hooks.json should be updated.",
              },
              enabled: {
                type: "boolean",
                description: "Whether the experimental no-op Stop-hook entry should be installed.",
              },
              reviewedDryRun: {
                type: "boolean",
                description: "Must be true after the user reviews and approves the dry-run summary.",
              },
              reviewedPlanDigest: {
                type: "string",
                description: "Digest of the dry-run plan shown to the user.",
              },
            },
            required: ["projectPath", "enabled", "reviewedDryRun", "reviewedPlanDigest"],
          },
          annotations: {
            readOnlyHint: false,
            destructiveHint: false,
            idempotentHint: true,
            openWorldHint: false,
          },
          _meta: {
            ui: { visibility: ["app"] },
          },
        },
      ],
    });
    return;
  }

  if (method === "resources/list") {
    sendResult(id, {
      resources: [
        {
          uri: WIDGET_URI,
          name: "Token Optimizer Hook Control",
          title: "Token Optimizer Hook Control",
          description: "Interactive project-local control for the experimental no-op Stop-hook entry.",
          mimeType: WIDGET_MIME_TYPE,
          _meta: {
            ui: {
              prefersBorder: true,
              csp: {
                connectDomains: [],
                resourceDomains: [],
              },
            },
            "openai/widgetDescription":
              "Review and install or remove Token Optimizer's experimental no-op Stop-hook entry for the selected project.",
          },
        },
      ],
    });
    return;
  }

  if (method === "resources/read") {
    if (params?.uri !== WIDGET_URI) {
      sendError(id, JsonRpcError.INVALID_PARAMS, `Unknown resource: ${params?.uri ?? ""}`);
      return;
    }
    sendResult(id, {
      contents: [
        {
          uri: WIDGET_URI,
          mimeType: WIDGET_MIME_TYPE,
          text: readWidgetHtml(),
          _meta: {
            ui: {
              prefersBorder: true,
              csp: {
                connectDomains: [],
                resourceDomains: [],
              },
            },
            "openai/widgetDescription":
              "Review and install or remove Token Optimizer's experimental no-op Stop-hook entry for the selected project.",
          },
        },
      ],
    });
    return;
  }

  if (method === "tools/call") {
    try {
      await handleToolCall(id, params);
    } catch (error) {
      sendError(
        id,
        JsonRpcError.INVALID_PARAMS,
        error instanceof Error ? error.message : String(error),
      );
    }
    return;
  }

  if (id !== undefined) {
    sendError(id, JsonRpcError.METHOD_NOT_FOUND, `Method not found: ${method}`);
  }
}

const lines = readline.createInterface({
  input: process.stdin,
  crlfDelay: Infinity,
});

lines.on("line", (line) => {
  if (line.trim().length === 0) {
    return;
  }

  let message;
  try {
    message = JSON.parse(line);
  } catch (error) {
    logProtocolWarning(
      `dropped invalid JSON-RPC line: ${error instanceof Error ? error.message : String(error)}`,
    );
    return;
  }

  if (message.method === undefined && message.id !== undefined) {
    const pending = pendingRequests.get(message.id);
    if (pending !== undefined) {
      pendingRequests.delete(message.id);
      if (message.error !== undefined) {
        pending.reject(new Error(message.error.message ?? "MCP request failed."));
      } else {
        pending.resolve(message.result);
      }
    } else {
      logProtocolWarning(`dropped response for unknown request id: ${String(message.id)}`);
    }
    return;
  }

  void handleRequest(message);
});

lines.on("close", () => {
  rejectPendingRequests(new Error("MCP input stream closed before the host responded."));
});

lines.on("error", (error) => {
  rejectPendingRequests(error instanceof Error ? error : new Error(String(error)));
});
