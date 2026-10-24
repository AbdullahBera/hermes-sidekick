# Privacy and capability boundaries

> **Planned change:** the project is moving to a local-first design in which a local model
> handles personal data and only narrow, explicit flows leave the machine. See the
> [local-first plan](LOCAL-AGENT-PLAN.md). **It is not implemented yet.** Everything below
> describes the current deployment, which sends conversations to a hosted model.

Sidekick runs Hermes inside a Linux VM. That separates Linux processes from native Mac
processes, but **a VM with host filesystem sharing is not a filesystem sandbox for your Mac**.
OrbStack's reference setup exposes host directories including `/Users` and `/mnt/mac`.
Hermes shell/file tools can use the permissions of the VM user on those mounts. A notes or
tasks path is a preference, not an operating-system restriction to that file or folder.

## Choose the boundary before connecting accounts

- **Shared-host setup:** keep OrbStack's host mounts for convenience, understanding that
  the agent can access mounted host files. Use a dedicated account with minimal permissions.
- **No host-file sharing:** use a dedicated Linux machine or a VM configured without host
  shares. Put the Sidekick checkout and notes/tasks inside that environment. Run
  `HERMES_LOCAL=1 ./scripts/status.sh --require-isolation` there before connecting accounts.
  This gate fails on detected shared filesystem types (including bind aliases), or if mount
  inspection is unavailable. It does not configure the hypervisor, detect every possible
  network/bind mount, or certify the sandbox. Verify the hypervisor's sharing configuration too.

Host wrappers read the checkout through the OrbStack mount. For an environment without that
mount, clone the checkout inside it and use `HERMES_LOCAL=1 ./scripts/sync.sh --check` (or
`--apply`). Turning sharing off on a live deployment can break existing file paths; migrate
those paths first. Sync and health checks never change host sharing or firewall settings.

## What disabling actually does

| Capability | Effect after profile change and successful sync |
| --- | --- |
| Automation | Its known standalone cron is paused; removing its standalone schedule also pauses it. Prompt instructions stop disabled runs, including triage called by a brief. A run already in progress may finish. |
| Google MCP connector | The `gmail`, `calendar`, or `contacts` server's `enabled` flag is reconciled in Hermes config, then the gateway is reloaded. Credentials, permissions, and unrelated servers are preserved. Restart any already-open CLI sessions too. |
| Shell/model connector (notes, tasks, research, weather, etc.) | The assistant is instructed to check the profile and decline when disabled. Its general shell/network/model capabilities remain available. This is behavioral policy. |
| Channel | Sync uses the enabled channel for scheduled delivery. Transport configuration and inbound access lists still require the channel recipe; disabling the profile flag alone does not disconnect Signal. |

MCP reconciliation assumes the recipe's separate registration named exactly after the plugin.
Custom/shared server registrations are not managed automatically. Removing a tool from the
normal MCP surface **does not revoke OAuth tokens** or prevent a shell with credential access
from calling an API. To revoke account access, revoke the relevant provider grant and remove
local credentials; Google connectors may share a token, so account-wide revocation can affect
several connectors. Never describe prompt-based ask-first or no-send rules as API enforcement.

## Where data goes

Credentials are stored in the VM, outside the repository. Conversation and retrieved context
are sent to the configured model provider. Google connectors call Google; geocoding, weather,
research, and page-reading send requests to their respective services. Self-hosted does not
mean offline or that only the model sees data. Local notes/tasks have no separate storage
service, but their contents can enter model context when read.

The current guardrails combine tool configuration and agent instructions. They reduce risk;
they cannot guarantee that hostile content will never influence an agent with shell access.
For stronger isolation, use an environment with minimal filesystem access and credentials,
and enforce permissions outside the model.

The opt-in [controlled task service](CONTROL.md) implements this separation for its browser and
approved-memory tools: private owner socket, separate service identity, exact action approval,
and task/pause/disconnect enforcement in code. Those guarantees apply only to work through that
service. Existing raw Hermes tools and scheduled runs are not automatically migrated or governed
by its pause control.
