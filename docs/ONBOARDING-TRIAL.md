# Second-user onboarding acceptance trial

**Status: pending a second participant.** Automated fixtures validate script behavior. The
previous fresh-VM trial reused credentials; neither it nor passing fixtures proves fresh
Google consent, fresh Signal registration, or successful delivery for a new person.

Use a separate VM/account owned by the participant. Do not copy the reference user's tokens,
profile, memory, or Signal registration. Never publish phone numbers, email addresses, keys,
OAuth URLs/codes, screenshots of private content, or raw logs in the trial record.

## Run and resume

1. Record commit ID, date, OS/architecture, VM runtime, and installed Hermes version. Choose
   and record the host-sharing boundary from [PRIVACY.md](PRIVACY.md).
2. Run `./onboarder/bootstrap.sh`. Supply the participant's model key through the silent prompt.
   The initial profile has every capability off. Existing keys/profile are preserved on rerun.
   Bootstrap verifies executables, gateway installation, checkout files, and profile structure;
   it stops at failures rather than reporting readiness.
3. Run `./onboarder/bootstrap.sh --launch` for an interactive chat and enter the displayed
   playbook instruction. Do not use the old one-shot command for a multi-step conversation.
   The onboarder re-reads actual installed state at every resume. Keep a private checkpoint
   record in `~/.hermes/sidekick/onboarding-progress.md`: step name, pending/verified, timestamp,
   and a short redacted result. No secrets or account identifiers. Reverify before skipping.
4. Complete **new Signal registration** using the channel recipe, then configure the allowlist
   and gateway. From the participant's phone, send a harmless question and verify the reply.
5. Create the participant's **new Google OAuth client** and complete consent. Enable only
   chosen connectors. Verify a harmless Calendar/Gmail/Contacts read for each enabled connector.
   Tool discovery alone does not prove OAuth works. Calendar/Contacts may share OAuth setup
   without enabling Gmail tools.
6. Confirm timezone, quiet hours, and one routine. Set its time to a near-future local slot
   outside quiet hours. From the VM checkout run `HERMES_LOCAL=1 ./scripts/sync.sh --check`,
   review the proposed actions, then `HERMES_LOCAL=1 ./scripts/sync.sh --apply`.
7. Run `HERMES_LOCAL=1 ./scripts/status.sh` and optionally `--probe-connectors`. Wait for the
   scheduled brief and have the participant confirm its receipt, timing, and useful content.
   Do not count a manually triggered run as proof of scheduling. Restore the chosen daily time.
8. Rerun bootstrap and sync: credentials/profile survive, no duplicate crons, no repeated
   registration. Interrupt the onboarding between OAuth and scheduling, then resume from the
   checkpoint and prove completed steps are retained. Check recovery after a VM reboot.

## Record results (redacted, explicit)

| Check | Result | Evidence to record |
| --- | --- | --- |
| Fresh runtime and gateway installed | Pending | Versions, exit status |
| Selected host sharing boundary checked | Pending | Shared / no shares detected; limitations acknowledged |
| New Signal registration | Pending | Human confirmation; no number/code |
| New Google client and consent | Pending | Human confirmation; no identifiers |
| Enabled connector account reads | Pending | Connector name + pass/fail |
| Signal question and reply | Pending | Human confirmation; no message contents |
| Scheduled brief received on time | Pending | Intended/received times, pass/fail |
| Quiet-hours behavior | Pending | No proactive message in chosen quiet window |
| Interrupted setup resumes | Pending | Verified step retained |
| Rerun/reboot recovery | Pending | No duplicate crons; services active |

A failed or pending row remains visible. Record blockers and the next human action. Never mark
the product ready for second-user onboarding until the account and delivery rows pass.
