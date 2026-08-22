import {
  ArrowSquareOut,
  LockSimple,
  PlugsConnected,
  ShieldCheck,
  SlidersHorizontal,
} from "@phosphor-icons/react";

const GITHUB_URL = "https://github.com/AbdullahBera/hermes-sidekick";

const assistantMessages = [
  {
    id: "brief",
    time: "7:30 AM",
    content: (
      <p>
        Morning 👋 Team sync at 9. One important email. Six messages sorted. 63°F and partly cloudy.
      </p>
    ),
  },
  {
    id: "nudges",
    time: "7:31 AM",
    content: (
      <p>Two nudges: Reply to Maya — 3 days. Sarah’s birthday is tomorrow 🎂</p>
    ),
  },
  {
    id: "email",
    time: "7:32 AM",
    content: (
      <p>finance@acme.io sent “Q2 budget confirmation.” Action required. Draft a reply? ✍️</p>
    ),
  },
];

const userMessages = [
  { id: "brief", text: "Morning brief? ☀️", time: "7:30 AM" },
  { id: "nudges", text: "Anything I might miss?", time: "7:31 AM" },
  { id: "email", text: "Show the flagged email.", time: "7:32 AM" },
];

function GitHubLink({ className, children, label }) {
  return (
    <a
      className={className}
      href={GITHUB_URL}
      target="_blank"
      rel="noreferrer noopener"
      aria-label={label}
    >
      <span>{children}</span>
      {className === "nav-link" ? <ArrowSquareOut aria-hidden="true" /> : null}
    </a>
  );
}

function AssistantMessage({ message }) {
  return (
    <div className="message-row assistant-row">
      <span className="assistant-avatar" aria-hidden="true">
        HS
      </span>
      <article className="message assistant-message">
        <div className="message-copy">{message.content}</div>
        <time dateTime={`2026-05-12T${message.time === "7:30 AM" ? "07:30" : message.time === "7:31 AM" ? "07:31" : "07:32"}`}>
          {message.time}
        </time>
      </article>
    </div>
  );
}

function UserMessage({ message }) {
  return (
    <article className="message user-message">
      <p>{message.text}</p>
      <time dateTime={`2026-05-12T${message.time === "7:30 AM" ? "07:30" : message.time === "7:31 AM" ? "07:31" : "07:32"}`}>
        {message.time}
      </time>
    </article>
  );
}

function ConversationPreview() {
  return (
    <section className="conversation" aria-label="Example private conversation with Hermes Sidekick">
      <header className="conversation-header">
        <h2>Hermes Sidekick</h2>
        <p className="privacy-status">
          <LockSimple aria-hidden="true" weight="regular" />
          <span>Running privately</span>
        </p>
      </header>
      <div className="conversation-body">
        {assistantMessages.map((assistantMessage, index) => (
          <div className="conversation-pair" key={assistantMessage.id}>
            <UserMessage message={userMessages[index]} />
            <AssistantMessage message={assistantMessage} />
          </div>
        ))}
      </div>
    </section>
  );
}

const proofItems = [
  { label: "Connect your apps", Icon: PlugsConnected },
  { label: "Choose your routines", Icon: SlidersHorizontal },
  { label: "Stay private", Icon: ShieldCheck },
];

export function App() {
  return (
    <div className="site-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>

      <header className="site-header">
        <a className="wordmark" href="#main-content" aria-label="Hermes Sidekick home">
          hermes-sidekick
        </a>
        <nav aria-label="Primary navigation">
          <GitHubLink className="nav-link" label="View Hermes Sidekick on GitHub (opens in a new tab)">
            GitHub
          </GitHubLink>
        </nav>
      </header>

      <main id="main-content">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">Private <span>•</span> Self-hosted <span>•</span> Yours</p>
            <h1 id="hero-title">Your own private AI sidekick.</h1>
            <p className="hero-description">
              Connect Gmail, Calendar, and Signal. Switch on morning briefs, inbox sorting, reminders, and follow-ups.
            </p>
            <p className="hero-promise">Plug in what you use. Turn on what you need. Sidekick handles the rest.</p>
            <GitHubLink className="primary-cta" label="View Hermes Sidekick on GitHub (opens in a new tab)">
              View on GitHub
            </GitHubLink>
          </div>

          <ConversationPreview />
        </section>

        <section className="proof-strip" aria-label="Project qualities">
          {proofItems.map(({ label, Icon }) => (
            <div className="proof-item" key={label}>
              <Icon aria-hidden="true" weight="regular" />
              <span>{label}</span>
            </div>
          ))}
        </section>
      </main>

      <footer className="site-footer">
        <p>Built on Hermes Agent</p>
      </footer>
    </div>
  );
}
