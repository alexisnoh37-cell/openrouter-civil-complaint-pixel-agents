import type { HookProvider } from '../../../../../core/src/provider.js';

/**
 * Standalone provider for the civil-complaint office.
 *
 * OpenRouter calls happen in the FastAPI application. The browser translates
 * its SSE events into Pixel Agents messages, so this provider intentionally
 * has no CLI hooks, transcript scanner, or launch command.
 */
export const openrouterProvider: HookProvider = {
  kind: 'hook',
  id: 'openrouter',
  displayName: 'OpenRouter Civil Complaint Agents',
  protocolVersion: 1,
  normalizeHookEvent: () => null,
  installHooks: async () => undefined,
  uninstallHooks: async () => undefined,
  areHooksInstalled: async () => true,
  formatToolStatus: (toolName, input) => {
    if (typeof input === 'object' && input && 'message' in input) {
      return String((input as { message?: unknown }).message ?? toolName);
    }
    return toolName;
  },
  permissionExemptTools: new Set(['Read', 'Write']),
  subagentToolNames: new Set(),
  readingTools: new Set(['Read']),
};
